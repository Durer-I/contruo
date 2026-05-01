"""Sheet classifier (Sprint AI-02 / Stage 2).

Two-pass classifier:

* ``classify_lexical`` -- deterministic prefix + keyword rules. Cost = 0.
  Resolves ~90% of well-named sheets ("A-101 Floor Plan", "M-201 Mechanical
  Schedule", "E-501 Electrical Details") with ~0.85 confidence.

* ``classify_vision_batch`` -- batches of N (default 6) sheet thumbnails are
  passed to the multimodal vision model in a single call when the lexical
  classifier returns low confidence AND the sheet doesn't match the
  "skip-uninteresting" allowlist (cover/index/spec). The skip allowlist is
  the user's explicit ask in D6: even if the lexical confidence is low, we
  do NOT pay for vision on sheets that are clearly not plans.

* ``bulk_upsert_classifications`` -- single ``UPDATE ... FROM (VALUES ...)``
  per stage run. Avoids N round-trips when a plan has 200+ sheets.

The file deliberately avoids any DB read concerns -- callers pass in lists
of ``(sheet_id, sheet_name, content_hash)`` tuples and get back lists of
``ClassificationResult``.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Discipline + sheet-type taxonomies ────────────────────────────────────

#: Sheet name prefix -> discipline. Order matters only for documentation;
#: the lookup is a dict. Values match the AIA US National CAD Standard.
DISCIPLINE_PREFIXES: dict[str, str] = {
    "A": "architectural",
    "S": "structural",
    "M": "mechanical",
    "E": "electrical",
    "P": "plumbing",
    "C": "civil",
    "L": "landscape",
    "T": "telecom",
    "F": "fire_protection",
    "I": "interiors",
    "G": "general",  # cover sheet, index, code summary
    "Q": "equipment",
}


#: Allowed discipline values (kept in sync with the frontend dot-color map).
ALL_DISCIPLINES: tuple[str, ...] = (
    "architectural",
    "structural",
    "mechanical",
    "electrical",
    "plumbing",
    "civil",
    "landscape",
    "telecom",
    "fire_protection",
    "interiors",
    "general",
    "equipment",
    "other",
)


def infer_discipline_from_sheet_number(sheet_number: str | None) -> str | None:
    """Map drawing sheet ID prefix to discipline after auto-name.

    Uses common US sheet numbering (A=architectural, S=structural, …). Longest
    literal prefix wins so ``FP`` maps to fire protection before single ``F``.
    Leading punctuation/spaces are skipped (e.g. ``"- A101"``).

    Returns ``None`` when no configured prefix matches — callers should leave
    ``Sheet.discipline`` unchanged in that case.
    """
    if not sheet_number:
        return None
    raw = sheet_number.strip().upper()
    if not raw:
        return None
    i = 0
    while i < len(raw) and not raw[i].isalpha():
        i += 1
    if i >= len(raw):
        return None
    tail = raw[i:]
    if tail.startswith("FP"):
        return "fire_protection"
    letter = tail[0]
    single_letter: dict[str, str] = {
        "A": "architectural",
        "S": "structural",
        "P": "plumbing",
        "E": "electrical",
        "M": "mechanical",
        "F": "fire_protection",
        "L": "landscape",
    }
    d = single_letter.get(letter)
    if d is not None and d in ALL_DISCIPLINES:
        return d
    return None


#: Allowed sheet types. ``plan`` is the most common; ``schedule`` and
#: ``legend`` are first-class because Stage 3 needs to extract from them.
ALL_SHEET_TYPES: tuple[str, ...] = (
    "plan",
    "elevation",
    "section",
    "detail",
    "schedule",
    "legend",
    "diagram",
    "cover",
    "index",
    "spec",
    "other",
)

#: Sheet types where the lexical classifier confidently won out and the user
#: explicitly does NOT want to pay for a vision recheck (D6 optimization).
#: A cover sheet is a cover sheet; vision is wasted budget.
UNINTERESTING_SHEET_TYPES: frozenset[str] = frozenset({"cover", "index", "spec"})

#: Keyword -> sheet_type. First match wins. Patterns are *substrings*
#: matched case-insensitively against the *normalized* sheet name (lower
#: cased, punctuation collapsed). We bias toward broader keywords (``plan``)
#: at the END of the list so ``"floor plan schedule"`` still classifies as
#: ``schedule`` (the more specific term dominates).
SHEET_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("schedule", "schedule"),
    ("legend", "legend"),
    ("symbol", "legend"),
    ("notes", "legend"),
    ("abbrev", "legend"),
    ("cover", "cover"),
    ("title", "cover"),
    ("index", "index"),
    ("sheet list", "index"),
    ("specification", "spec"),
    ("spec", "spec"),
    ("elevation", "elevation"),
    ("section", "section"),
    ("detail", "detail"),
    ("riser", "diagram"),
    ("diagram", "diagram"),
    ("one-line", "diagram"),
    ("oneline", "diagram"),
    ("plan", "plan"),
)

#: Number-prefix -> typical sheet type. For example AIA convention says
#: ``A-001`` is general/cover, ``A-1xx`` is plans, ``A-2xx`` is elevations,
#: ``A-3xx`` is sections, ``A-4xx`` is enlarged plans/details, ``A-5xx`` is
#: details, ``A-6xx`` is schedules. Used as a backstop when the keyword
#: pass returns nothing.
NUMBER_TO_TYPE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-?0\d{2}\b"), "cover"),
    (re.compile(r"-?1\d{2}\b"), "plan"),
    (re.compile(r"-?2\d{2}\b"), "elevation"),
    (re.compile(r"-?3\d{2}\b"), "section"),
    (re.compile(r"-?4\d{2}\b"), "plan"),  # enlarged plans
    (re.compile(r"-?5\d{2}\b"), "detail"),
    (re.compile(r"-?6\d{2}\b"), "schedule"),
)

#: Confidence assigned to each lexical decision branch. Tuned so the
#: vision-fallback escalation lands on the truly ambiguous sheets only.
_CONFIDENCE_PREFIX_AND_KEYWORD = 0.90  # discipline prefix + sheet-type keyword
_CONFIDENCE_PREFIX_AND_NUMBER = 0.75  # discipline prefix + AIA number range
_CONFIDENCE_KEYWORD_ONLY = 0.65  # sheet-type keyword but no recognizable prefix
_CONFIDENCE_PREFIX_ONLY = 0.55  # discipline prefix but no usable type signal
_CONFIDENCE_NONE = 0.20  # neither prefix nor keyword matched


@dataclass(frozen=True)
class ClassificationResult:
    sheet_id: uuid.UUID
    discipline: str
    sheet_type: str
    confidence: float
    method: str  # 'lexical' | 'vision' | 'manual'
    notes: str = ""


@dataclass(frozen=True)
class SheetForClassification:
    """Caller-supplied input row.

    ``content_hash`` is required only for the vision-fallback path; pass
    ``""`` (empty) to skip vision caching.
    """

    sheet_id: uuid.UUID
    sheet_name: str | None
    content_hash: str = ""
    thumbnail_png: bytes | None = None


# ─── Lexical pass ─────────────────────────────────────────────────────────


_PREFIX_RE = re.compile(r"^\s*([A-Za-z])\s*[-_/.]?\s*(\d{1,4})", re.IGNORECASE)


def _normalize(text_value: str | None) -> str:
    if not text_value:
        return ""
    return re.sub(r"[\s_/]+", " ", text_value).strip().lower()


def _classify_discipline(sheet_name: str | None) -> tuple[str, str]:
    """Returns (discipline, captured_number_token_or_'')."""
    if not sheet_name:
        return "other", ""
    m = _PREFIX_RE.match(sheet_name)
    if not m:
        return "other", ""
    letter = m.group(1).upper()
    number = m.group(0).lower()
    return DISCIPLINE_PREFIXES.get(letter, "other"), number


def _classify_sheet_type_from_keywords(normalized_name: str) -> str | None:
    if not normalized_name:
        return None
    # Strip the leading prefix so "A101 Floor Plan" matches "plan" but
    # "G001 Plan Index" still matches "index" (kept after).
    name_after_prefix = re.sub(r"^[a-z]+\s*[-_/.]?\s*\d{1,4}\b\s*", "", normalized_name)
    target = name_after_prefix or normalized_name
    for keyword, kind in SHEET_TYPE_KEYWORDS:
        if keyword in target:
            return kind
    return None


def _classify_sheet_type_from_number(captured_number: str) -> str | None:
    if not captured_number:
        return None
    for pattern, kind in NUMBER_TO_TYPE:
        if pattern.search(captured_number):
            return kind
    return None


def classify_lexical(sheet_id: uuid.UUID, sheet_name: str | None) -> ClassificationResult:
    """Deterministic prefix + keyword pass. Cost = 0.

    Returns ``ClassificationResult`` with ``method='lexical'``. The confidence
    is high (>= 0.9) when both the discipline prefix and a sheet-type keyword
    matched, decaying through the matrix in this module's constants.
    """
    discipline, number_token = _classify_discipline(sheet_name)
    normalized = _normalize(sheet_name)
    keyword_type = _classify_sheet_type_from_keywords(normalized)
    number_type = _classify_sheet_type_from_number(number_token)

    if discipline != "other" and keyword_type is not None:
        return ClassificationResult(
            sheet_id=sheet_id,
            discipline=discipline,
            sheet_type=keyword_type,
            confidence=_CONFIDENCE_PREFIX_AND_KEYWORD,
            method="lexical",
            notes="prefix+keyword",
        )
    if discipline != "other" and number_type is not None:
        return ClassificationResult(
            sheet_id=sheet_id,
            discipline=discipline,
            sheet_type=number_type,
            confidence=_CONFIDENCE_PREFIX_AND_NUMBER,
            method="lexical",
            notes="prefix+number_range",
        )
    if discipline == "other" and keyword_type is not None:
        return ClassificationResult(
            sheet_id=sheet_id,
            discipline="other",
            sheet_type=keyword_type,
            confidence=_CONFIDENCE_KEYWORD_ONLY,
            method="lexical",
            notes="keyword_only",
        )
    if discipline != "other":
        return ClassificationResult(
            sheet_id=sheet_id,
            discipline=discipline,
            sheet_type="plan",  # most plausible default given a discipline prefix
            confidence=_CONFIDENCE_PREFIX_ONLY,
            method="lexical",
            notes="prefix_only_default_plan",
        )
    return ClassificationResult(
        sheet_id=sheet_id,
        discipline="other",
        sheet_type="other",
        confidence=_CONFIDENCE_NONE,
        method="lexical",
        notes="no_signal",
    )


# ─── Vision-fallback bucket selection ─────────────────────────────────────


def needs_vision_fallback(
    lexical: ClassificationResult,
    *,
    threshold: float | None = None,
) -> bool:
    """D6 optimization: skip vision on uninteresting sheet types even if confidence is low.

    A sheet escalates to vision iff:
      1. Its lexical confidence is below the configured threshold, AND
      2. Its lexical sheet_type is NOT in ``UNINTERESTING_SHEET_TYPES``.

    Cover/index/spec sheets often have unconventional names but are always
    correctly identified by keywords -- the vision model adds no signal.
    """
    if threshold is None:
        threshold = get_settings().ai_classification_confidence_threshold
    if lexical.confidence >= threshold:
        return False
    if lexical.sheet_type in UNINTERESTING_SHEET_TYPES:
        return False
    return True


# ─── Vision-fallback batch dispatch ───────────────────────────────────────


def _build_classify_schema(sheet_count: int) -> dict[str, Any]:
    """JSON schema for a multi-sheet classification reply.

    The model is asked to return one entry per ordered sheet in the strip.
    Validation is lenient -- if the model returns the wrong count, we drop
    extras and pad missing with low-confidence ``other``.
    """
    return {
        "type": "object",
        "properties": {
            "sheets": {
                "type": "array",
                "minItems": sheet_count,
                "maxItems": sheet_count,
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "minimum": 0},
                        "discipline": {"type": "string", "enum": list(ALL_DISCIPLINES)},
                        "sheet_type": {"type": "string", "enum": list(ALL_SHEET_TYPES)},
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": ["index", "discipline", "sheet_type", "confidence"],
                },
            }
        },
        "required": ["sheets"],
    }


def _stitch_thumbnails_vertically(
    pngs: Sequence[bytes],
    *,
    pad_px: int = 8,
    background: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """Compose N thumbnails into a single PNG strip (top to bottom).

    Sized so the model sees one image per call (cheaper + simpler prompt).
    Each thumbnail is letterboxed to the strip's max width with a white
    pad band between sheets so the model can tell them apart.
    """
    if not pngs:
        raise ValueError("_stitch_thumbnails_vertically: empty input")
    images = [Image.open(io.BytesIO(p)).convert("RGB") for p in pngs]
    max_w = max(img.width for img in images)
    total_h = sum(img.height for img in images) + pad_px * (len(images) - 1)
    strip = Image.new("RGB", (max_w, total_h), background)
    y = 0
    for img in images:
        # Center horizontally in case sheets have different aspect ratios.
        x = (max_w - img.width) // 2
        strip.paste(img, (x, y))
        y += img.height + pad_px
    buf = io.BytesIO()
    strip.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _coerce_classification(
    sheet_id: uuid.UUID,
    obj: Any,
    *,
    fallback_lexical: ClassificationResult | None,
) -> ClassificationResult:
    """Coerce a raw model response item into a validated ``ClassificationResult``.

    Falls back to the lexical guess (or ``other``) when fields are missing
    or out of the allowlist.
    """
    discipline = "other"
    sheet_type = "other"
    confidence = _CONFIDENCE_NONE
    if isinstance(obj, dict):
        d = str(obj.get("discipline", "other")).lower()
        if d in ALL_DISCIPLINES:
            discipline = d
        st = str(obj.get("sheet_type", "other")).lower()
        if st in ALL_SHEET_TYPES:
            sheet_type = st
        try:
            c = float(obj.get("confidence", 0.0))
        except (TypeError, ValueError):
            c = 0.0
        confidence = max(0.0, min(1.0, c))

    if discipline == "other" and fallback_lexical is not None:
        discipline = fallback_lexical.discipline
    if sheet_type == "other" and fallback_lexical is not None:
        sheet_type = fallback_lexical.sheet_type
    return ClassificationResult(
        sheet_id=sheet_id,
        discipline=discipline,
        sheet_type=sheet_type,
        confidence=confidence,
        method="vision",
        notes="vision_batch",
    )


def classify_vision_batch(
    sheets: Sequence[SheetForClassification],
    *,
    vision_model: Any,
    batch_size: int | None = None,
    lexical_by_id: dict[uuid.UUID, ClassificationResult] | None = None,
) -> list[ClassificationResult]:
    """Run vision classification on the supplied sheets in batches of N.

    ``vision_model`` is duck-typed against the ``VisionModel`` protocol --
    only ``classify_image(image_bytes, schema=...)`` is called.

    Sheets without ``thumbnail_png`` are dropped with a warning -- the caller
    must render thumbnails before calling. ``lexical_by_id`` is used purely
    as a fallback when the model returns malformed entries.

    Returns one ``ClassificationResult`` per *input* sheet whose thumbnail
    was provided. The result list is in the same order as the input.
    """
    settings = get_settings()
    if batch_size is None:
        batch_size = settings.ai_vision_classify_batch_size
    if batch_size <= 0:
        batch_size = 6

    valid_inputs: list[SheetForClassification] = []
    for s in sheets:
        if not s.thumbnail_png:
            logger.warning(
                "classify_vision_batch: sheet %s has no thumbnail; skipping", s.sheet_id
            )
            continue
        valid_inputs.append(s)

    out: list[ClassificationResult] = []
    for i in range(0, len(valid_inputs), batch_size):
        batch = valid_inputs[i : i + batch_size]
        try:
            strip = _stitch_thumbnails_vertically([s.thumbnail_png for s in batch if s.thumbnail_png])
        except Exception:
            logger.exception("classify_vision_batch: failed to stitch thumbnails")
            for s in batch:
                fallback = (lexical_by_id or {}).get(s.sheet_id)
                out.append(
                    fallback
                    if fallback is not None
                    else ClassificationResult(
                        sheet_id=s.sheet_id,
                        discipline="other",
                        sheet_type="other",
                        confidence=_CONFIDENCE_NONE,
                        method="lexical",
                        notes="stitch_failed",
                    )
                )
            continue

        schema = _build_classify_schema(len(batch))
        try:
            response = vision_model.classify_image(strip, schema=schema)
        except Exception:
            logger.exception("classify_vision_batch: vision_model.classify_image failed")
            # Fall back to the lexical guess for the whole batch.
            for s in batch:
                fallback = (lexical_by_id or {}).get(s.sheet_id)
                out.append(
                    fallback
                    if fallback is not None
                    else ClassificationResult(
                        sheet_id=s.sheet_id,
                        discipline="other",
                        sheet_type="other",
                        confidence=_CONFIDENCE_NONE,
                        method="lexical",
                        notes="vision_call_failed",
                    )
                )
            continue

        items: list[Any] = []
        if isinstance(response, dict):
            items = list(response.get("sheets") or [])
        if not items:
            for s in batch:
                fallback = (lexical_by_id or {}).get(s.sheet_id)
                out.append(
                    fallback
                    if fallback is not None
                    else ClassificationResult(
                        sheet_id=s.sheet_id,
                        discipline="other",
                        sheet_type="other",
                        confidence=_CONFIDENCE_NONE,
                        method="lexical",
                        notes="vision_no_sheets_field",
                    )
                )
            continue

        # Map by index when present; otherwise zip in order.
        indexed: dict[int, Any] = {}
        for entry in items:
            if isinstance(entry, dict) and isinstance(entry.get("index"), int):
                indexed[int(entry["index"])] = entry
        for j, sheet in enumerate(batch):
            entry = indexed.get(j) if indexed else (items[j] if j < len(items) else None)
            fallback = (lexical_by_id or {}).get(sheet.sheet_id)
            out.append(_coerce_classification(sheet.sheet_id, entry, fallback_lexical=fallback))

    return out


# ─── Bulk DB writeback ─────────────────────────────────────────────────────


def bulk_upsert_classifications(
    session: Session,
    results: Iterable[ClassificationResult],
) -> int:
    """Single ``UPDATE sheets SET ... FROM (VALUES ...)`` for all results.

    Returns the count of rows updated. ``method`` is stored verbatim;
    ``confidence`` and ``discipline`` / ``sheet_type`` are validated by the
    Postgres CHECK constraints we control via the application allowlists.

    No-ops on empty input. Every result row's sheet_id MUST already exist
    -- a stray ID is a bug, not a runtime condition.
    """
    rows = list(results)
    if not rows:
        return 0

    payload = [
        {
            "sheet_id": str(r.sheet_id),
            "discipline": r.discipline,
            "sheet_type": r.sheet_type,
            "confidence": float(r.confidence),
            "method": r.method,
        }
        for r in rows
    ]

    # NOTE: Use ``CAST(:payload AS jsonb)`` rather than ``:payload::jsonb``.
    # SQLAlchemy's ``text()`` bind-param parser treats ``:name`` followed by
    # PostgreSQL's ``::`` cast operator ambiguously and can fail to register
    # the bind, which then breaks ``.bindparams(...)`` and any execution. The
    # ANSI ``CAST(...)`` form is unambiguous and identical at the SQL level.
    stmt = text(
        """
        UPDATE sheets AS s
           SET discipline = v.discipline,
               sheet_type = v.sheet_type,
               classification_confidence = v.confidence,
               classification_method = v.method
          FROM (
            SELECT
              CAST(elem->>'sheet_id' AS uuid) AS sheet_id,
              elem->>'discipline' AS discipline,
              elem->>'sheet_type' AS sheet_type,
              CAST(elem->>'confidence' AS float) AS confidence,
              elem->>'method' AS method
            FROM jsonb_array_elements(CAST(:payload AS jsonb)) AS elem
          ) AS v
         WHERE s.id = v.sheet_id
        """
    )

    import json as _json

    result = session.execute(stmt, {"payload": _json.dumps(payload)})
    return int(result.rowcount or 0)


# ─── Aggregation helper for summary_jsonb ──────────────────────────────────


@dataclass
class ClassificationCounters:
    total: int = 0
    by_discipline: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    lexical_count: int = 0
    vision_count: int = 0
    low_confidence_count: int = 0

    def add(self, r: ClassificationResult, *, low_threshold: float) -> None:
        self.total += 1
        self.by_discipline[r.discipline] = self.by_discipline.get(r.discipline, 0) + 1
        self.by_type[r.sheet_type] = self.by_type.get(r.sheet_type, 0) + 1
        if r.method == "lexical":
            self.lexical_count += 1
        elif r.method == "vision":
            self.vision_count += 1
        if r.confidence < low_threshold:
            self.low_confidence_count += 1

    def as_summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_discipline": dict(self.by_discipline),
            "by_type": dict(self.by_type),
            "lexical_count": self.lexical_count,
            "vision_count": self.vision_count,
            "low_confidence_count": self.low_confidence_count,
        }


__all__ = [
    "ALL_DISCIPLINES",
    "ALL_SHEET_TYPES",
    "ClassificationCounters",
    "ClassificationResult",
    "DISCIPLINE_PREFIXES",
    "SheetForClassification",
    "UNINTERESTING_SHEET_TYPES",
    "bulk_upsert_classifications",
    "classify_lexical",
    "classify_vision_batch",
    "infer_discipline_from_sheet_number",
    "needs_vision_fallback",
]
