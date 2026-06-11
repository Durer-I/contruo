"""Stage 3a: schedule table extraction.

Heuristic-first escalation chain on a single PDF page:

    pdfplumber.lines_strict   ─┐
    pdfplumber.lines           ├─ deterministic, free
    pdfplumber.text            ─┘
    AnthropicVisionModel       ── vision fallback, costs tokens

Each strategy is tried in order; we stop the moment a strategy yields at least
one *quality-passing* candidate. The quality gate is a row-width-variance
score (``_score_table_quality``) that filters pdfplumber's notorious noise
matches: floating control bars, page borders that look like a 1xN table, etc.

The prototype (``AI/controller/find_tables.py`` + ``AI/controller/tables.py``)
proved ``lines_strict`` is the best primary strategy for construction-doc
schedules -- they almost universally have a full grid of horizontal +
vertical rules. The looser strategies catch the long-tail of partially-ruled
or alignment-only schedules; vision is the explicit safety net.

This module is pure: it returns a list of ``ScheduleCandidate`` dataclasses.
The Celery task body persists to ``extracted_schedules`` and runs the
tag-column scorer on each candidate.
"""
from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config import get_settings
from app.services.ai_models import VisionModel

logger = logging.getLogger(__name__)


#: Padding (PDF user-space pts) applied to pdfplumber's table bbox before
#: cropping for ``extract_table``. Matches the prototype constant -- gives
#: ``extract_table`` enough whitespace to anchor outer rules without dragging
#: in adjacent text. 40 is large enough that border-clipping is rare on the
#: schedules we've inspected; smaller values caused dropped header rows.
BBOX_PADDING_PTS = 20

#: pdfplumber strategies tried in order. String identifiers that map directly
#: to ``find_tables({"vertical_strategy": s, "horizontal_strategy": s})``.
PDFPLUMBER_STRATEGIES: tuple[tuple[str, str], ...] = (
    ("pdfplumber_lines_strict", "lines_strict"),
    ("pdfplumber_lines", "lines"),
    ("pdfplumber_text", "text"),
)

#: JSON schema handed to the vision fallback. Constrains output to a list of
#: ``{headers, rows}`` objects so the model can return *multiple* tables when
#: a sheet has more than one (door + window schedule on the same page is
#: common). Cells are strings -- coercing to other types is the resolver's
#: job, not the extractor's.
VISION_TABLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headers": {"type": "array", "items": {"type": "string"}},
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "required": ["headers", "rows"],
            },
        }
    },
    "required": ["tables"],
}

VISION_PROMPT = (
    "Extract every schedule TABLE on this construction drawing sheet. "
    "Schedules are gridded data -- door schedules, window schedules, equipment "
    "schedules, fixture schedules, panel schedules, etc. Ignore narrative "
    "text, title blocks, plan views, and notes. For each table, return its "
    "header row separately from the data rows. Preserve cell text verbatim "
    "(do not normalize abbreviations, units, or letter case). If a cell is "
    "empty, return an empty string. Return tables in top-to-bottom, "
    "left-to-right order."
)


@dataclass
class ScheduleCandidate:
    """A single extracted schedule table on a single sheet.

    The pipeline body fills in the column-index fields via
    ``ai_tag_column.score_columns`` before persisting to ``extracted_schedules``;
    the extractor's job ends at the table data + bbox.
    """

    bbox_pdf: dict[str, float]
    headers: list[str]
    rows: list[list[str]]
    extraction_method: str
    #: 0..1 -- ``_score_table_quality`` output; informational, not persisted.
    quality: float = 0.0
    #: Optional vision-only metadata (e.g. retry count) so the cost-tracking
    #: layer can correlate without re-querying the run.
    notes: dict[str, Any] = field(default_factory=dict)

    def as_table_jsonb(self) -> dict[str, Any]:
        """Serialize for the ``extracted_schedules.extracted_table_jsonb`` column."""
        return {"headers": list(self.headers), "rows": [list(r) for r in self.rows]}


def extract_schedules_for_page(
    *,
    plumber_page: Any,
    page_width: float,
    page_height: float,
    vision_model: VisionModel | None = None,
    vision_image_bytes: Callable[[], bytes] | None = None,
) -> list[ScheduleCandidate]:
    """Run the full strategy chain on one pdfplumber page.

    Args:
        plumber_page: A ``pdfplumber.Page`` object (open inside a ``pdfplumber.open``
            context). The caller owns the document lifetime.
        page_width / page_height: Page dims in PDF user-space points -- used
            for bbox padding bounds and as the vision fallback's ``bbox_pdf``
            (since vision sees a rasterized whole page, the per-table bbox
            isn't recoverable from the model's output).
        vision_model: Active ``VisionModel`` for the fallback. Passed in (not
            built from settings inside) so tests inject a mock without
            patching factories.
        vision_image_bytes: Lazy producer of the page render. Only invoked
            when every heuristic strategy comes back empty -- avoids the
            renderer cost on the common path. ``None`` disables vision.

    Returns:
        List of candidates. Empty list when nothing passes the quality gate
        (the caller's ``summary_jsonb`` counter will reflect "no schedules
        found on this sheet" in that case).
    """
    settings = get_settings()
    quality_floor = settings.ai_schedule_table_min_quality

    for method, strategy in PDFPLUMBER_STRATEGIES:
        candidates = _try_pdfplumber_strategy(
            plumber_page=plumber_page,
            method=method,
            strategy=strategy,
            page_width=page_width,
            page_height=page_height,
            quality_floor=quality_floor,
        )
        if candidates:
            logger.info(
                "schedule_extractor: page strategy=%s candidates=%d", method, len(candidates)
            )
            return candidates

    if vision_model is None or vision_image_bytes is None:
        logger.info("schedule_extractor: no heuristic candidates; vision disabled")
        return []

    try:
        image_bytes = vision_image_bytes()
    except Exception:
        logger.exception("schedule_extractor: vision image render failed; skipping fallback")
        return []

    return _try_vision_fallback(
        vision_model=vision_model,
        image_bytes=image_bytes,
        page_width=page_width,
        page_height=page_height,
    )


def _try_pdfplumber_strategy(
    *,
    plumber_page: Any,
    method: str,
    strategy: str,
    page_width: float,
    page_height: float,
    quality_floor: float,
) -> list[ScheduleCandidate]:
    try:
        tables = plumber_page.find_tables(
            {
                "vertical_strategy": strategy,
                "horizontal_strategy": strategy,
            }
        )
    except Exception:
        logger.exception(
            "pdfplumber.find_tables raised on strategy=%s; treating as no-match", strategy
        )
        return []

    out: list[ScheduleCandidate] = []
    for table in tables:
        try:
            x0, top, x1, bottom = table.bbox
        except Exception:
            continue
        padded = _pad_bbox(x0, top, x1, bottom, page_width, page_height)
        try:
            cropped = plumber_page.crop(padded)
            raw = cropped.extract_table()
        except Exception:
            logger.exception(
                "pdfplumber extract_table failed on strategy=%s bbox=%s",
                strategy,
                padded,
            )
            continue
        if not raw:
            continue
        cleaned = _clean_table(raw)
        if cleaned is None:
            continue
        headers, rows = cleaned
        quality = _score_table_quality(headers=headers, rows=rows)
        if quality < quality_floor:
            continue
        out.append(
            ScheduleCandidate(
                bbox_pdf={
                    "x0": float(padded[0]),
                    "y0": float(padded[1]),
                    "x1": float(padded[2]),
                    "y1": float(padded[3]),
                },
                headers=headers,
                rows=rows,
                extraction_method=method,
                quality=quality,
            )
        )
    return out


def _try_vision_fallback(
    *,
    vision_model: VisionModel,
    image_bytes: bytes,
    page_width: float,
    page_height: float,
) -> list[ScheduleCandidate]:
    try:
        response = vision_model.extract_structured(
            image_bytes,
            prompt=VISION_PROMPT,
            schema=VISION_TABLE_SCHEMA,
        )
    except NotImplementedError:
        # Stage 3a hard-requires the vision fallback; if a provider hasn't
        # wired it yet, skip rather than crash the whole pipeline.
        logger.warning(
            "schedule_extractor: vision provider has no extract_structured wired; skipping"
        )
        return []
    except Exception:
        logger.exception("schedule_extractor: vision call failed; skipping fallback")
        return []

    tables = response.get("tables") if isinstance(response, dict) else None
    if not isinstance(tables, list):
        logger.warning(
            "schedule_extractor: vision response missing 'tables' list; payload=%s",
            json.dumps(response)[:200] if isinstance(response, dict) else type(response).__name__,
        )
        return []

    page_bbox = {
        "x0": 0.0,
        "y0": 0.0,
        "x1": float(page_width),
        "y1": float(page_height),
    }
    out: list[ScheduleCandidate] = []
    for tbl in tables:
        if not isinstance(tbl, dict):
            continue
        headers_raw = tbl.get("headers") or []
        rows_raw = tbl.get("rows") or []
        if not isinstance(headers_raw, list) or not isinstance(rows_raw, list):
            continue
        headers = [str(h or "") for h in headers_raw]
        rows = [
            [str(c or "") for c in (row if isinstance(row, list) else [])]
            for row in rows_raw
        ]
        if not headers and not rows:
            continue
        out.append(
            ScheduleCandidate(
                bbox_pdf=dict(page_bbox),
                headers=headers,
                rows=rows,
                extraction_method="vision",
                quality=1.0,  # vision matches are accepted as-is
                notes={"reason": "no_pdfplumber_match"},
            )
        )
    return out


def _pad_bbox(
    x0: float,
    top: float,
    x1: float,
    bottom: float,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    return (
        max(0.0, x0 - BBOX_PADDING_PTS),
        max(0.0, top - BBOX_PADDING_PTS),
        min(page_width, x1 + BBOX_PADDING_PTS),
        min(page_height, bottom + BBOX_PADDING_PTS),
    )


def _clean_table(
    raw: list[list[str | None]],
) -> tuple[list[str], list[list[str]]] | None:
    """Drop empty rows, coerce ``None`` cells to ``""``, split header from data.

    Returns ``None`` when the table has no usable header (a 0-column table is
    nonsense and shouldn't be persisted).
    """
    coerced: list[list[str]] = []
    for row in raw:
        cells = [(c or "").strip() if isinstance(c, str) else "" for c in (row or [])]
        if any(cells):
            coerced.append(cells)
    if not coerced:
        return None
    width = max(len(r) for r in coerced)
    if width == 0:
        return None
    # Pad ragged rows so the resolver can index by column safely.
    padded = [r + [""] * (width - len(r)) for r in coerced]
    headers = padded[0]
    rows = padded[1:]
    if not headers:
        return None
    return headers, rows


def _score_table_quality(*, headers: list[str], rows: list[list[str]]) -> float:
    """A 0..1 quality score for a pdfplumber-extracted table.

    Three signals, weighted equally:

    * Header completeness: fraction of header cells that are non-empty.
      A real schedule has every column labelled; pdfplumber's noise matches
      typically have one or two header cells filled.
    * Row width consistency: 1 minus the variance of "non-empty cells per row"
      relative to the header width. A real schedule has rows all the same
      width as the header; noise matches have wildly inconsistent widths.
    * Minimum row count: penalty if fewer than 2 data rows. A "schedule"
      with one row is probably a stray title block.

    Returns 0.0 when ``rows`` is empty (no data = not a schedule).
    """
    if not headers:
        return 0.0
    header_filled = sum(1 for h in headers if h.strip())
    header_score = header_filled / len(headers)

    if not rows:
        return 0.0

    width = len(headers)
    if width == 0:
        return 0.0
    fills = [sum(1 for c in row if c.strip()) / width for row in rows]
    mean = sum(fills) / len(fills)
    variance = sum((f - mean) ** 2 for f in fills) / len(fills)
    consistency_score = max(0.0, 1.0 - variance * 4)  # variance of [0..1] caps near 0.25

    rows_score = 1.0 if len(rows) >= 2 else 0.5

    return (header_score + consistency_score + rows_score) / 3.0


def serialize_candidates(candidates: list[ScheduleCandidate]) -> list[dict[str, Any]]:
    """JSON-safe serialization for ``ai_stage_cache``."""
    return [
        {
            "bbox_pdf": dict(c.bbox_pdf),
            "headers": list(c.headers),
            "rows": [list(r) for r in c.rows],
            "extraction_method": c.extraction_method,
            "quality": float(c.quality),
            "notes": dict(c.notes),
        }
        for c in candidates
    ]


def deserialize_candidates(payload: list[dict[str, Any]]) -> list[ScheduleCandidate]:
    out: list[ScheduleCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                ScheduleCandidate(
                    bbox_pdf=dict(item.get("bbox_pdf") or {}),
                    headers=list(item.get("headers") or []),
                    rows=[list(r) for r in (item.get("rows") or [])],
                    extraction_method=str(item.get("extraction_method") or ""),
                    quality=float(item.get("quality") or 0.0),
                    notes=dict(item.get("notes") or {}),
                )
            )
        except Exception:
            logger.exception("Failed to deserialize ScheduleCandidate; skipping item")
    return out


def render_page_for_vision_factory(page: Any, *, dpi: int) -> Callable[[], bytes]:
    """Return a thunk that renders ``page`` (a ``fitz.Page``) at ``dpi``.

    Wrapped as a thunk so the schedule extractor only pays the render cost
    when every heuristic strategy has come up empty. Importing PIL/fitz at
    module level is fine (they're in requirements.txt), but the caller may
    legitimately have a non-fitz page object in tests; use of a thunk keeps
    the contract minimal.
    """
    import fitz  # type: ignore[import-untyped]
    from PIL import Image

    def _thunk() -> bytes:
        scale = max(1.0, dpi / 72.0)
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    return _thunk
