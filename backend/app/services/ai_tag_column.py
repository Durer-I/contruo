"""Stage 3a: schedule column-role classifier.

Given an extracted schedule (``headers + rows``), decide which column index is:

* The TAG column -- the row's MARK key. AI-04's resolver joins on this. The
  most important field; LLM-gated when the heuristic scorer is ambiguous.
* The DESCRIPTION column -- human-readable description used to seed the
  condition name AI-04 creates ("D-101: SOLID CORE 6'x7'").
* The QUANTITY column -- count, when present (rare on door schedules,
  common on equipment / panel schedules). Suppresses double-counting later.
* The DIMENSION column(s) -- width / height / depth / etc. Multi-valued
  because schedules legitimately have 1-3 dim columns.
* The MATERIAL column -- material/type, used as the second resolver axis
  when tag alone is ambiguous (two doors share MARK but differ by material).

Pure-Python heuristics only for everything except the tag column. Tag column
is the only one with an LLM fallback because:

1. It's the only field the resolver REQUIRES to function. A wrong tag means a
   wrong condition link; a wrong description just shows up as a worse name.
2. The other column-roles are advisory enrichment AI-04 can survive without.
3. Spending tokens on every schedule for fields we can live without
   would blow the cost budget the locked-decisions doc set for Stage 3a.

The 4-feature tag scorer (header-keyword, shape-regularity, uniqueness,
first-column bias) was tuned against the prototype's door / window /
equipment schedules. Skip-above 0.85 + margin 0.15 is the LLM gate the
spec calls out -- a strong heuristic signal stands on its own; an
ambiguous one (tied first place) pays for a tie-break.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.ai_cache import cache_get, cache_put
from app.services.ai_models import LLMModel, get_schedules_llm

logger = logging.getLogger(__name__)


#: Header keywords -> role. Substring match against the lower-cased,
#: punctuation-collapsed header. First match wins per role.
TAG_HEADER_KEYWORDS: tuple[str, ...] = (
    "mark",
    "tag",
    "type",
    "id",
    "symbol",
    "number",
    "no.",
    "no ",
    "ref",
    "code",
)
DESCRIPTION_HEADER_KEYWORDS: tuple[str, ...] = (
    "description",
    "remarks",
    "notes",
    "name",
    "title",
    "label",
)
QUANTITY_HEADER_KEYWORDS: tuple[str, ...] = (
    "qty",
    "quantity",
    "count",
    "ea",
    "each",
)
DIMENSION_HEADER_KEYWORDS: tuple[str, ...] = (
    "width",
    "height",
    "depth",
    "length",
    "size",
    "thickness",
    "dim",
    "dimension",
    "frame",
    "wxh",
    "w x h",
    "w/h",
)
SINGLE_LETTER_DIM_HEADERS: frozenset[str] = frozenset({"w", "h", "d", "l", "t"})

MATERIAL_HEADER_KEYWORDS: tuple[str, ...] = (
    "material",
    "finish",
    "hardware",
    "mfr",
    "mfg",
    "manufacturer",
    "model",
    "spec",
    "construction",
)

#: Tag-cell shape. Schedule MARK keys are almost universally short alphanumeric
#: codes -- ``D101``, ``W-A2``, ``P-1``, ``M101A``, ``101``. Strict pattern
#: avoids confusing "ROOM 121" or "DETAIL 1/A2.1" cells with tags.
TAG_SHAPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-/]{0,8}$")

#: Cell looks like a quantity (integer or simple decimal, optionally with
#: leading sign). Rejects "5'-0\"" and "5 EA" -- those land in dimension /
#: description.
QUANTITY_CELL_PATTERN = re.compile(r"^-?\d+(\.\d+)?$")

#: Cell looks like a dimension. Imperial fractional inches, metric, decimals,
#: or "WxH" forms. Intentionally permissive -- false positives are cheap
#: because dimension is the lowest-priority resolver hint.
DIMENSION_CELL_PATTERN = re.compile(
    r"""^(
        \d+'\-?\d*\"?         |   # 5'-0", 5'-0, 5'
        \d+\"                 |   # 36"
        \d+(\.\d+)?\s*(mm|cm|m|in|ft)?  |  # 1200mm, 5.0
        \d+\s*x\s*\d+         |   # 5x10
        \d+(\.\d+)?
    )$""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class ColumnScores:
    """Result of ``score_columns``. Mirrors the persisted schema 1:1.

    Index fields are ``None`` when no column scored above the per-role
    threshold -- a schedule legitimately may not have, say, a quantity
    column at all.
    """

    tag_column_index: int | None
    description_column_index: int | None
    quantity_column_index: int | None
    dimension_column_indexes: list[int] | None
    material_column_index: int | None
    used_llm: bool
    notes: dict[str, Any] = field(default_factory=dict)


def score_columns(
    *,
    headers: list[str],
    rows: list[list[str]],
    db: Session | None = None,
    org_id: uuid.UUID | None = None,
    llm_factory: Callable[[], LLMModel] | None = None,
) -> ColumnScores:
    """Run the 4-feature heuristic scorer + LLM tag-column fallback.

    Args:
        headers / rows: As returned by ``ai_schedule_extractor``.
        db / org_id: Provided -> the LLM tag-column decision is cached in
            ``ai_stage_cache`` keyed by a hash of (headers + first 5 rows).
            Both ``None`` -> LLM cache is bypassed (used by tests).
        llm_factory: Defaults to ``get_schedules_llm``; tests inject a mock.

    Returns:
        ``ColumnScores``.
    """
    if not headers or not rows:
        return ColumnScores(
            tag_column_index=None,
            description_column_index=None,
            quantity_column_index=None,
            dimension_column_indexes=None,
            material_column_index=None,
            used_llm=False,
            notes={"reason": "empty_table"},
        )

    settings = get_settings()
    width = len(headers)

    tag_scores = [_score_tag_column(headers, rows, idx) for idx in range(width)]
    desc_scores = [_score_description_column(headers, rows, idx) for idx in range(width)]
    qty_scores = [_score_quantity_column(headers, rows, idx) for idx in range(width)]
    dim_scores = [_score_dimension_column(headers, rows, idx) for idx in range(width)]
    mat_scores = [_score_material_column(headers, rows, idx) for idx in range(width)]

    tag_top, tag_runner = _top_two(tag_scores)
    tag_idx: int | None = None
    used_llm = False
    notes: dict[str, Any] = {
        "tag_top_score": tag_top[1],
        "tag_runner_score": tag_runner[1],
    }

    if tag_top[1] >= settings.ai_tag_column_llm_skip_above:
        tag_idx = tag_top[0]
        notes["tag_decision"] = "heuristic_strong"
    elif (tag_top[1] - tag_runner[1]) >= settings.ai_tag_column_llm_margin and tag_top[1] >= 0.5:
        tag_idx = tag_top[0]
        notes["tag_decision"] = "heuristic_clear_margin"
    elif tag_top[1] >= 0.4:
        # Ambiguous heuristic signal -- spend tokens on an LLM tie-break.
        # ``llm_factory`` defaults to the schedules LLM factory; the ``or``
        # exists so tests can pass an explicit ``None`` to disable the call.
        factory = llm_factory or get_schedules_llm
        llm_idx, used_llm = _llm_tag_column(
            headers=headers,
            rows=rows,
            db=db,
            org_id=org_id,
            llm_factory=factory,
        )
        if llm_idx is not None:
            tag_idx = llm_idx
            notes["tag_decision"] = "llm_tiebreak" if used_llm else "llm_cache_hit"
        else:
            tag_idx = tag_top[0]
            notes["tag_decision"] = (
                "llm_failed_fallback_heuristic" if used_llm else "heuristic_weak_no_llm"
            )
    else:
        notes["tag_decision"] = "no_match"

    desc_idx = _argmax_above(desc_scores, threshold=0.4, exclude={tag_idx})
    qty_idx = _argmax_above(qty_scores, threshold=0.5, exclude={tag_idx, desc_idx})
    mat_idx = _argmax_above(
        mat_scores, threshold=0.5, exclude={tag_idx, desc_idx, qty_idx}
    )
    dim_indexes = _all_above(
        dim_scores,
        threshold=0.6,
        exclude={tag_idx, desc_idx, qty_idx, mat_idx},
    )

    return ColumnScores(
        tag_column_index=tag_idx,
        description_column_index=desc_idx,
        quantity_column_index=qty_idx,
        dimension_column_indexes=dim_indexes if dim_indexes else None,
        material_column_index=mat_idx,
        used_llm=used_llm,
        notes=notes,
    )


def _normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (h or "").lower()).strip()


def _score_tag_column(
    headers: list[str],
    rows: list[list[str]],
    idx: int,
) -> float:
    if idx >= len(headers):
        return 0.0
    header_norm = _normalize_header(headers[idx])
    header_score = (
        1.0 if any(kw in header_norm for kw in TAG_HEADER_KEYWORDS) else 0.0
    )
    cells = _column_cells(rows, idx)
    if not cells:
        return 0.0
    shape_hits = sum(1 for c in cells if TAG_SHAPE_PATTERN.match(c))
    shape_score = shape_hits / len(cells)
    unique_count = len({c.lower() for c in cells})
    uniqueness_score = unique_count / len(cells)
    # First-column bias: 1.0 at idx 0, 0.5 at idx 1, then 0.
    if idx == 0:
        position_score = 1.0
    elif idx == 1:
        position_score = 0.5
    else:
        position_score = 0.0
    return (header_score + shape_score + uniqueness_score + position_score) / 4.0


def _score_description_column(
    headers: list[str], rows: list[list[str]], idx: int
) -> float:
    if idx >= len(headers):
        return 0.0
    header_norm = _normalize_header(headers[idx])
    header_score = (
        1.0 if any(kw in header_norm for kw in DESCRIPTION_HEADER_KEYWORDS) else 0.0
    )
    cells = _column_cells(rows, idx)
    if not cells:
        return header_score * 0.5
    avg_len = sum(len(c) for c in cells) / len(cells)
    # Description cells average 15+ chars on real schedules; saturate at 30.
    length_score = min(1.0, avg_len / 30.0)
    return (header_score * 2 + length_score) / 3.0


def _score_quantity_column(
    headers: list[str], rows: list[list[str]], idx: int
) -> float:
    if idx >= len(headers):
        return 0.0
    header_norm = _normalize_header(headers[idx])
    header_score = (
        1.0 if any(kw in header_norm for kw in QUANTITY_HEADER_KEYWORDS) else 0.0
    )
    cells = _column_cells(rows, idx)
    if not cells:
        return 0.0
    qty_hits = sum(1 for c in cells if QUANTITY_CELL_PATTERN.match(c))
    cell_score = qty_hits / len(cells)
    return (header_score * 2 + cell_score) / 3.0


def _score_dimension_column(
    headers: list[str], rows: list[list[str]], idx: int
) -> float:
    if idx >= len(headers):
        return 0.0
    header_norm = _normalize_header(headers[idx])
    header_score = (
        1.0
        if any(kw in header_norm for kw in DIMENSION_HEADER_KEYWORDS)
        or header_norm in SINGLE_LETTER_DIM_HEADERS
        else 0.0
    )
    cells = _column_cells(rows, idx)
    if not cells:
        return 0.0
    dim_hits = sum(1 for c in cells if DIMENSION_CELL_PATTERN.match(c))
    cell_score = dim_hits / len(cells)
    return (header_score * 2 + cell_score) / 3.0


def _score_material_column(
    headers: list[str], rows: list[list[str]], idx: int
) -> float:
    if idx >= len(headers):
        return 0.0
    header_norm = _normalize_header(headers[idx])
    header_score = (
        1.0 if any(kw in header_norm for kw in MATERIAL_HEADER_KEYWORDS) else 0.0
    )
    # Material is fully header-driven: cell content is too varied to
    # heuristic-classify (a material could be a brand, a finish code, a
    # spec section number).
    return header_score


def _column_cells(rows: list[list[str]], idx: int) -> list[str]:
    out: list[str] = []
    for row in rows:
        if idx < len(row):
            cell = (row[idx] or "").strip()
            if cell:
                out.append(cell)
    return out


def _top_two(scores: list[float]) -> tuple[tuple[int, float], tuple[int, float]]:
    if not scores:
        return ((0, 0.0), (0, 0.0))
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    top = indexed[0]
    runner = indexed[1] if len(indexed) > 1 else (top[0], 0.0)
    return top, runner


def _argmax_above(
    scores: list[float],
    *,
    threshold: float,
    exclude: set[int | None],
) -> int | None:
    best_idx: int | None = None
    best_score = threshold
    for idx, score in enumerate(scores):
        if idx in exclude:
            continue
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def _all_above(
    scores: list[float],
    *,
    threshold: float,
    exclude: set[int | None],
) -> list[int]:
    return [
        idx
        for idx, score in enumerate(scores)
        if score >= threshold and idx not in exclude
    ]


# ─── LLM tag-column tie-break ─────────────────────────────────────────────


_LLM_TAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tag_column_index": {
            "type": "integer",
            "description": (
                "0-based index of the column that contains the row's MARK / "
                "TAG / unique identifier. -1 if none of the columns is a "
                "tag column."
            ),
        },
        "reason": {"type": "string"},
    },
    "required": ["tag_column_index", "reason"],
    "additionalProperties": False,
}

_LLM_TAG_PROMPT_HEAD = (
    "You are reviewing a schedule table extracted from a construction drawing. "
    "Identify the column that contains the row's MARK / TAG / ID -- the unique "
    "identifier the rest of the project document refers to. Answer with the "
    "0-based column index. Respond -1 if no column qualifies."
)


def _llm_tag_column(
    *,
    headers: list[str],
    rows: list[list[str]],
    db: Session | None,
    org_id: uuid.UUID | None,
    llm_factory: Callable[[], LLMModel],
) -> tuple[int | None, bool]:
    """Returns ``(tag_index_or_none, used_llm)``.

    ``used_llm == False`` only when the LLM call was skipped due to a cache
    hit; cost-tracking on the call itself records the spend either way.
    """
    sample_rows = rows[:5]
    cache_key_input = json.dumps(
        {"h": headers, "r": sample_rows}, sort_keys=True, separators=(",", ":")
    )
    content_hash = hashlib.sha256(cache_key_input.encode("utf-8")).hexdigest()
    settings = get_settings()
    model_version = (
        f"{settings.ai_schedules_llm_provider}:{settings.ai_schedules_llm_model}"
    )

    cached: dict[str, Any] | None = None
    if db is not None and org_id is not None:
        cached = cache_get(
            db,
            org_id=org_id,
            content_hash=content_hash,
            stage="tag_column",
            model_version=model_version,
        )
    if cached is not None:
        idx_raw = cached.get("tag_column_index")
        idx = _coerce_tag_index(idx_raw, width=len(headers))
        return idx, False

    try:
        llm = llm_factory()
    except Exception:
        logger.exception("ai_tag_column: llm_factory raised; skipping LLM fallback")
        return None, False

    prompt = (
        _LLM_TAG_PROMPT_HEAD
        + "\n\nHeaders: "
        + json.dumps(headers, ensure_ascii=False)
        + "\nSample rows (first 5):\n"
        + json.dumps(sample_rows, ensure_ascii=False, indent=2)
    )
    try:
        response = llm.structured_output(prompt, schema=_LLM_TAG_SCHEMA)
    except NotImplementedError:
        logger.warning("ai_tag_column: LLM provider has no structured_output wired")
        # Provider not wired -- no call was actually made; treat like a skip.
        return None, False
    except Exception:
        # Call WAS made and failed (rate limit, network, etc.) -- count it
        # so the failure surface is visible in the run summary.
        logger.exception("ai_tag_column: LLM call failed")
        return None, True

    if not isinstance(response, dict):
        return None, True

    idx = _coerce_tag_index(response.get("tag_column_index"), width=len(headers))

    if db is not None and org_id is not None:
        cache_put(
            db,
            org_id=org_id,
            content_hash=content_hash,
            stage="tag_column",
            model_version=model_version,
            value={
                "tag_column_index": -1 if idx is None else idx,
                "reason": str(response.get("reason") or ""),
            },
        )
    return idx, True


def _coerce_tag_index(raw: Any, *, width: int) -> int | None:
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= width:
        return None
    return idx
