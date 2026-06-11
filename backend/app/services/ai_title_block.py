"""Title-block extraction + auto-name-sheets pipeline (Sprint AI-02b).

Three layers, all sync (called from the Celery worker):

1. **Heuristic parser** -- ``parse_title_block_heuristic(text)``. Pure-Python
   regex + anchor-based extraction of ``drawing_name`` / ``drawing_number``
   from messy OCR or PDF-text-layer output. Cost = 0. Confidence in [0, 1].

2. **Per-sheet extractor** -- ``extract_title_for_sheet(page, ...)``. Reads
   the bottom-right corner of the page, falls back to a full-height right
   strip, then OCR via :func:`ai_ocr.ocr_image_bytes`, then optionally an
   LLM cleanup pass when the heuristic confidence is below threshold.

3. **Plan-level orchestrator** -- ``reextract_titles_for_plan(session, plan)``.
   Iterates sheets in page order, respects the ``sheet_name_source='manual'``
   guard, writes ``sheets.sheet_name`` + ``sheets.sheet_number``, and returns
   ``ReextractCounters`` for telemetry.

Design notes
------------

* No ``numpy`` / ``opencv`` / ``matplotlib`` -- the original prototype used
  cv2 + numpy for thresholding; we delegate that to
  :func:`ai_ocr.ocr_image_bytes(..., preprocess="title_block")` which uses
  PIL only. Sprint AI-02b explicitly bans those deps for OCR work.
* Per-page rect stays in PDF user-space points and respects ``page.rect``
  (which already accounts for rotation), so landscape sheets and rotated
  pages get the right corner without manual matrix math.
* Manual-source contract: rows where ``sheet.sheet_name_source == 'manual'``
  are skipped unless the auto-name request sets ``overwrite_manual=True``. The
  guard lives in :func:`_sheet_eligible_for_auto_name` -- a single chokepoint.
* COALESCE writes: a partial extraction (number found but name missing)
  preserves the existing value of the missing field. Empty extractions are
  no-ops. This keeps an upload-time auto name from being wiped by a later
  re-extract that returned nothing useful.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.plan import Plan
from app.models.sheet import Sheet
from app.services import ai_models, ai_ocr, ai_sheet_text_llm
from app.utils.pdf import extract_text_in_rect, render_clip_to_png

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover -- declared in requirements.txt
    fitz = None

logger = logging.getLogger(__name__)


# ─── Constants & regex ─────────────────────────────────────────────────────


#: Minimum text length to consider the vector text-layer "rich enough"; below
#: this we still try OCR (some PDFs have a tiny stray text node in an
#: otherwise raster title block).
MIN_TEXT_LENGTH = 10

#: Hard caps mirroring the DB columns. ``sheet_name`` is VARCHAR(255) but the
#: existing rename API trims to 200; use 200 for parity.
MAX_NAME_CHARS = 200
MAX_NUMBER_CHARS = 40

#: Confidence ceiling we attribute to heuristic-only results (regardless of
#: anchor strength). Reserves the higher tier for LLM-confirmed answers.
HEURISTIC_CONFIDENCE_CEILING = 0.95

TITLE_ANCHORS: tuple[str, ...] = (
    "DRAWING NAME",
    "SHEET TITLE",
    "DRAWINGTITLE",
    "TITLE",
)
NUMBER_ANCHORS: tuple[str, ...] = (
    "DRAWING NUMBER",
    "SHEET NUMBER",
    "SHEET NO",
    "SHEET:",
    "DWG NO",
    "DWG NUMBER",
)
STOP_ANCHORS: tuple[str, ...] = TITLE_ANCHORS + NUMBER_ANCHORS + (
    "PROJECT NUMBER",
    "PROPERTY NUMBER",
    "DRAWN BY",
    "CHECKED",
    "ISSUE DATE",
    "DATE:",
    "SCALE",
    "REVISION",
    "PROJECT NO",
)

#: A drawing identifier: 1-4 leading letters, optional dash, 1-4 digits,
#: optional ``.NN`` suffix(es), optional trailing letter (e.g. ``A101a``).
#: Examples: ``A101``, ``G1.1``, ``AD2.1``, ``S-100``, ``D101``, ``G002``,
#: ``AR105``, ``A0.2``.
DRAWING_ID_RE = re.compile(r"^[A-Z]{1,4}-?\d{1,4}(?:\.\d+)*[A-Z]?$")
DRAWING_ID_INLINE_RE = re.compile(r"\b([A-Z]{1,4}-?\d{1,4}(?:\.\d+)*[A-Z]?)\b")

#: A project / property number: pure digits, 4+ chars, optional ``.NNN``.
#: Used to EXCLUDE these from drawing-id candidates (they're the most common
#: false positive on construction title blocks).
PROJECT_NUMBER_RE = re.compile(r"^\d{4,}(?:\.\d+)*$")

#: Tokens that sometimes appear in marginal OCR / LLM hallucinations but are
#: never real AIA-style sheet numbers when they stand alone as the whole id.
_DRAWING_NUMBER_GARBAGE: frozenset[str] = frozenset(
    {
        "NOTES",
        "NOTE",
        "PLANS",
        "PLAN",
        "SHEET",
        "SHEETS",
        "LEGEND",
        "DETAILS",
        "DETAIL",
        "GENERAL",
        "TYPICAL",
        "COVER",
        "INDEX",
        "SCALE",
        "TITLE",
        "DRAWING",
        "SCHEDULE",
        "SPECIFICATION",
        "SKETCH",
        "SECTION",
        "ELEVATION",
        "KEY",
        "REVISION",
        "REV",
        "DATE",
        "PROJECT",
    }
)

#: Lowercase OCR characters that are almost always digits when they appear in
#: the trailing portion of a drawing identifier (``"AS11"`` -> ``"A511"``).
_OCR_DIGIT_FIX = str.maketrans(
    {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "Z": "2", "B": "8"}
)

#: Phase tokens that often appear next to the drawing number in noisy OCR
#: (e.g. ``"CD A0.1"`` or ``"G1.1  CD"``). Strip them before regex matching.
PHASE_TOKENS: frozenset[str] = frozenset(
    {"CD", "DD", "SD", "BID", "PERMIT", "IFC", "IFR"}
)


# ─── Result types ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedTitleBlock:
    """Pure-text parser output. No I/O performed."""

    name: str | None
    number: str | None
    confidence: float

    @property
    def is_complete(self) -> bool:
        return bool(self.name) and bool(self.number)


@dataclass(frozen=True)
class TitleExtractionResult:
    """Per-sheet extraction outcome."""

    name: str | None
    number: str | None
    confidence: float
    #: ``'text_layer'`` | ``'ocr'`` | ``'llm'`` | ``'empty'`` | ``'llm_failed'``.
    method: str

    @property
    def has_any_field(self) -> bool:
        return bool(self.name) or bool(self.number)


@dataclass
class ReextractCounters:
    """Plan-level rollup written into broadcast payload + (future) ai_run summary."""

    total: int = 0
    manual_skipped: int = 0
    text_layer: int = 0
    ocr: int = 0
    llm: int = 0
    empty: int = 0
    llm_failed: int = 0
    written: int = 0
    sheet_text_llm_cache_hits: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "manual_skipped": self.manual_skipped,
            "text_layer": self.text_layer,
            "ocr": self.ocr,
            "llm": self.llm,
            "empty": self.empty,
            "llm_failed": self.llm_failed,
            "written": self.written,
            "sheet_text_llm_cache_hits": self.sheet_text_llm_cache_hits,
            "errors": self.errors[:10],  # cap; full list lives in worker logs
        }


# ─── Heuristic parser ──────────────────────────────────────────────────────


def _clean_token(token: str) -> str:
    return token.strip().rstrip(".,;:")


def _looks_like_drawing_id(token: str) -> bool:
    t = _clean_token(token)
    if not t or PROJECT_NUMBER_RE.match(t):
        return False
    if not bool(DRAWING_ID_RE.match(t)):
        return False
    return _drawing_number_passes_sanity(t)


def _drawing_number_passes_sanity(t: str) -> bool:
    """Extra guards on top of the strict regex -- kills ``NOTE5``-style OCR
    where a margin note accidentally matches ``[A-Z]{4}\\d``.
    """
    u = t.upper()
    if u in _DRAWING_NUMBER_GARBAGE:
        return False
    # ``NOTE5``, ``TITLE1``, …: long alpha prefix + only 1–2 trailing digits,
    # no hyphen / dot segment (real ids are ``A101``, ``G1.1``, ``S-100``, …).
    if re.fullmatch(r"[A-Z]{4,}\d{1,2}", u) and "-" not in t and "." not in t:
        return False
    return True


def _repair_drawing_id(candidate: str) -> str:
    """Fix common OCR letter-for-digit mistakes in the trailing digit portion.

    Only the *tail* (everything after the leading letter prefix) is repaired;
    the prefix itself is left alone since ``A``/``S`` etc. are valid.
    """
    m = re.match(r"^([A-Z]{1,4})(.+)$", candidate)
    if not m:
        return candidate
    prefix, tail = m.groups()
    repaired = "".join(
        ch.translate(_OCR_DIGIT_FIX) if ch.isalpha() else ch for ch in tail
    )
    return prefix + repaired


def extract_drawing_number(text: str) -> tuple[str | None, float]:
    """Locate the drawing identifier in ``text`` and return ``(value, confidence)``.

    Strategy (highest to lowest confidence):

    1. Token immediately AFTER a number anchor (``"SHEET NUMBER\\nA101"``).
    2. Token immediately BEFORE a number anchor (``"A101  CD\\nSHEET NUMBER"``).
    3. A standalone short line that matches the drawing-id shape.
    4. An inline match anywhere in the text (last line wins -- IDs are
       conventionally near the bottom of the title block).
    5. OCR repair: a token that becomes a valid id after letter-for-digit fix.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    upper_lines = [ln.upper() for ln in lines]

    # Tier 1: after-anchor.
    for i, ln_up in enumerate(upper_lines):
        if any(a in ln_up for a in NUMBER_ANCHORS):
            for j in range(i + 1, min(i + 4, len(lines))):
                tokens = [
                    t for t in re.split(r"\s+", lines[j])
                    if t.upper() not in PHASE_TOKENS
                ]
                for tok in tokens:
                    if _looks_like_drawing_id(tok):
                        return _clean_token(tok), 0.95

    # Tier 2: before-anchor.
    for i, ln_up in enumerate(upper_lines):
        if any(a in ln_up for a in NUMBER_ANCHORS):
            for j in range(max(0, i - 3), i):
                tokens = [
                    t for t in re.split(r"\s+", lines[j])
                    if t.upper() not in PHASE_TOKENS
                ]
                for tok in tokens:
                    if _looks_like_drawing_id(tok):
                        return _clean_token(tok), 0.9

    # Tier 3: standalone candidates (last wins -- IDs are near the bottom).
    candidates = [ln for ln in lines if _looks_like_drawing_id(ln)]
    if len(candidates) == 1:
        return _clean_token(candidates[0]), 0.75
    if candidates:
        return _clean_token(candidates[-1]), 0.6

    # Tier 4: inline match anywhere.
    for ln in reversed(lines):
        m = DRAWING_ID_INLINE_RE.search(ln)
        if m and not PROJECT_NUMBER_RE.match(m.group(1)):
            cand = m.group(1)
            if _looks_like_drawing_id(cand):
                return cand, 0.4

    # Tier 5: repair-and-retry.
    for ln in lines:
        for tok in re.split(r"\s+", ln):
            tok = _clean_token(tok)
            if not tok:
                continue
            repaired = _repair_drawing_id(tok)
            if repaired != tok and _looks_like_drawing_id(repaired):
                return repaired, 0.3

    return None, 0.0


def extract_drawing_name(text: str) -> tuple[str | None, float]:
    """Locate the drawing name in ``text`` and return ``(value, confidence)``.

    Strategy:

    1. Anchor-based: lines after a TITLE anchor, until the next stop anchor
       or a drawing-id line. Up to 4 lines collected, joined with spaces.
    2. Output-1 fallback: title sits between ``"DRAWN BY"`` and the sheet ID.
       Lower confidence since it relies on a structural convention rather
       than an explicit label.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    upper_lines = [ln.upper() for ln in lines]

    for i, ln_up in enumerate(upper_lines):
        if any(a in ln_up for a in TITLE_ANCHORS):
            collected: list[str] = []
            for j in range(i + 1, len(lines)):
                up = upper_lines[j]
                if any(a in up for a in STOP_ANCHORS):
                    break
                if _looks_like_drawing_id(lines[j]):
                    break
                if PROJECT_NUMBER_RE.match(lines[j]):
                    break
                collected.append(lines[j])
                if len(collected) >= 4:
                    break
            if collected:
                return _normalize_name(" ".join(collected)), 0.9

    for i, ln_up in enumerate(upper_lines):
        if "DRAWN BY" in ln_up:
            collected = []
            for j in range(i + 1, len(lines)):
                if _looks_like_drawing_id(lines[j]):
                    break
                if any(a in upper_lines[j] for a in STOP_ANCHORS):
                    break
                collected.append(lines[j])
                if len(collected) >= 4:
                    break
            if collected:
                return _normalize_name(" ".join(collected)), 0.7

    return None, 0.0


def _normalize_name(name: str) -> str:
    """Collapse whitespace, strip stray punctuation, cap to ``MAX_NAME_CHARS``."""
    s = re.sub(r"\s+", " ", name).strip(" -")
    if len(s) > MAX_NAME_CHARS:
        s = s[:MAX_NAME_CHARS].rstrip()
    return s


def _normalize_number(number: str) -> str:
    """Trim + cap to ``MAX_NUMBER_CHARS``."""
    s = _clean_token(number)
    if len(s) > MAX_NUMBER_CHARS:
        s = s[:MAX_NUMBER_CHARS].rstrip()
    return s


def parse_title_block_heuristic(text: str) -> ParsedTitleBlock:
    """Deterministic parse of title-block text -> structured fields.

    Confidence matches the standalone prototype: ``min(name_conf, num_conf)``
    (when one field is missing the missing side contributes ``0.0`` so the
    product-style minimum still drives LLM escalation). Capped at
    :data:`HEURISTIC_CONFIDENCE_CEILING`.
    """
    if not text or not text.strip():
        return ParsedTitleBlock(name=None, number=None, confidence=0.0)
    name, name_conf = extract_drawing_name(text)
    number, num_conf = extract_drawing_number(text)
    confidence = round(min(name_conf, num_conf), 2)
    return ParsedTitleBlock(
        name=name,
        number=_normalize_number(number) if number else None,
        confidence=round(min(confidence, HEURISTIC_CONFIDENCE_CEILING), 2),
    )


# ─── LLM cleanup ───────────────────────────────────────────────────────────


_LLM_PROMPT_TEMPLATE = """Extract the drawing name and drawing number from this title block text.

Rules:
- drawing_name: the human-readable sheet title (e.g. "DEMOLITION FLOOR PLANS").
  If multi-line in the source, join with single spaces. Use ALL CAPS.
- drawing_number: the short sheet identifier (e.g. "A101", "G1.1", "S-100", "D101", "AR105").
  It is NEVER a project/property number (those are 4+ pure digits like "12654.000" or "5167450").
  Strip phase prefixes/suffixes like "CD", "DD", "SD", "IFC".
- If a field cannot be determined with reasonable confidence, return null.

TEXT:
\"\"\"
{text}
\"\"\"
"""


def _llm_schema() -> dict[str, Any]:
    """Strict JSON schema matching ``OpenAILLMModel.structured_output``'s contract.

    ``additionalProperties: false`` and every property in ``required`` are
    mandatory for OpenAI strict-mode; ``["string", "null"]`` lets the model
    return null for either field without violating the schema.
    """
    return {
        "title": "title_block",
        "type": "object",
        "properties": {
            "drawing_name": {"type": ["string", "null"]},
            "drawing_number": {"type": ["string", "null"]},
        },
        "required": ["drawing_name", "drawing_number"],
        "additionalProperties": False,
    }


def _sanitize_llm_drawing_number(raw: object, *, fallback: str | None) -> str | None:
    """Reject LLM garbage (``Notes``, ``Plans``, …) that slips past JSON decode."""
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    candidate = _normalize_number(raw)
    if not candidate or not _looks_like_drawing_id(candidate):
        return fallback
    return candidate


def _sanitize_llm_drawing_name(raw: object, *, fallback: str | None) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    name = _normalize_name(raw)
    if not name:
        return fallback
    u = name.upper()
    if u in _DRAWING_NUMBER_GARBAGE and len(name) <= 12:
        return fallback
    return name


def llm_extract(text: str) -> dict[str, Any] | None:
    """Ask the configured title-block LLM to extract the two fields.

    Returns the parsed dict on success, or ``None`` on any failure (missing
    SDK, missing API key, network error, malformed response). Failure is
    intentionally non-fatal -- the caller falls back to whatever the
    heuristic produced (which may be a partial result or nothing).
    """
    if not text or not text.strip():
        return None
    try:
        llm = ai_models.get_title_block_llm()
        result = llm.structured_output(
            _LLM_PROMPT_TEMPLATE.format(text=text),
            schema=_llm_schema(),
        )
    except Exception:
        logger.exception("ai_title_block: LLM extract failed")
        return None
    if not isinstance(result, dict):
        logger.warning("ai_title_block: LLM returned non-dict: %r", type(result))
        return None
    return result


# ─── Per-sheet extractor ───────────────────────────────────────────────────


def _corner_rect(page: Any, *, width_pts: float, height_pts: float) -> Any:
    """Bottom-right ``width_pts`` x ``height_pts`` corner box.

    Uses ``page.rect`` (which already accounts for rotation) so landscape
    and rotated pages get the correct corner. Caps the box to the actual
    page dimensions when the page is smaller than the configured size.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    r = page.rect
    w = min(width_pts, r.width)
    h = min(height_pts, r.height)
    return fitz.Rect(r.x1 - w, r.y1 - h, r.x1, r.y1)


def _right_strip_rect(page: Any, *, width_pts: float) -> Any:
    """Full-height right strip of width ``width_pts`` -- common ARCH layout."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    r = page.rect
    w = min(width_pts, r.width)
    return fitz.Rect(r.x1 - w, r.y0, r.x1, r.y1)


def _ocr_rect(page: Any, rect: Any, *, dpi: int) -> str:
    """Render ``rect`` to PNG and OCR it via ``ai_ocr.ocr_image_bytes``.

    Returns ``""`` when Tesseract isn't installed (graceful degradation --
    the caller treats empty as "no text recovered" and proceeds).
    """
    try:
        png = render_clip_to_png(page, rect, dpi=dpi)
    except Exception:
        logger.exception("ai_title_block: render_clip_to_png failed")
        return ""
    return ai_ocr.ocr_image_bytes(
        png,
        preprocess="title_block",
        tesseract_config=ai_ocr.TITLE_BLOCK_TESSERACT_CONFIG,
    )


def extract_title_for_sheet(
    page: Any,
    *,
    ocr_fallback: bool = True,
    llm_fallback: bool = True,
    width_pts: float | None = None,
    height_pts: float | None = None,
    clip_dpi: int | None = None,
    llm_min_confidence: float | None = None,
) -> TitleExtractionResult:
    """Run the four-stage extractor on a single PDF page.

    Stages:
      1. ``extract_text_in_rect`` on the corner; if empty try right strip.
      2. If both empty and ``ocr_fallback`` is True: OCR the corner; if
         that's also empty try OCR on the right strip.
      3. ``parse_title_block_heuristic`` on whichever text we got.
      4. If heuristic confidence < threshold or fields missing, and
         ``llm_fallback`` is True: call the title-block LLM.

    The ``method`` field on the result tells you which stage produced the
    final answer (useful for the per-plan summary counters).
    """
    settings = get_settings()
    width = width_pts if width_pts is not None else settings.ai_title_block_box_width_pts
    height = height_pts if height_pts is not None else settings.ai_title_block_box_height_pts
    dpi = clip_dpi if clip_dpi is not None else settings.ai_title_block_clip_dpi
    min_conf = (
        llm_min_confidence
        if llm_min_confidence is not None
        else settings.ai_title_block_llm_min_confidence
    )

    corner = _corner_rect(page, width_pts=width, height_pts=height)
    strip = _right_strip_rect(page, width_pts=width)

    # Stage 1: vector text layer.
    text = extract_text_in_rect(page, corner)
    text_method = "text_layer"
    if len(text) < MIN_TEXT_LENGTH:
        strip_text = extract_text_in_rect(page, strip)
        if len(strip_text) >= MIN_TEXT_LENGTH:
            text = strip_text

    # Stage 2: OCR fallback.
    if len(text) < MIN_TEXT_LENGTH and ocr_fallback:
        ocr_text = _ocr_rect(page, corner, dpi=dpi)
        if len(ocr_text) < MIN_TEXT_LENGTH:
            ocr_text = _ocr_rect(page, strip, dpi=dpi)
        if len(ocr_text) >= MIN_TEXT_LENGTH:
            text = ocr_text
            text_method = "ocr"

    if not text or not text.strip():
        return TitleExtractionResult(
            name=None, number=None, confidence=0.0, method="empty"
        )

    # Stage 3: heuristic parser.
    parsed = parse_title_block_heuristic(text)
    needs_llm = (
        llm_fallback
        and (parsed.confidence < min_conf or not parsed.is_complete)
    )
    if not needs_llm:
        return TitleExtractionResult(
            name=parsed.name,
            number=parsed.number,
            confidence=parsed.confidence,
            method=text_method,
        )

    # Stage 4: LLM cleanup.
    llm_result = llm_extract(text)
    if not llm_result:
        # Keep whatever the heuristic produced (may be partial or empty) but
        # tag the result so telemetry can surface "LLM unavailable" cases
        # separately from "we genuinely couldn't read this title block".
        return TitleExtractionResult(
            name=parsed.name,
            number=parsed.number,
            confidence=parsed.confidence,
            method="llm_failed",
        )

    raw_name = llm_result.get("drawing_name")
    raw_number = llm_result.get("drawing_number")
    name = _sanitize_llm_drawing_name(raw_name, fallback=parsed.name)
    number = _sanitize_llm_drawing_number(raw_number, fallback=parsed.number)
    confidence = 0.85 if (name and number) else 0.5
    return TitleExtractionResult(
        name=name,
        number=number,
        confidence=confidence,
        method="llm",
    )


# ─── Manual-source guard ───────────────────────────────────────────────────


def _sheet_eligible_for_auto_name(sheet: Sheet, *, overwrite_manual: bool) -> bool:
    """Return True when this sheet may be auto-named on this run."""
    if (sheet.sheet_name_source or "").lower() == "manual":
        return overwrite_manual
    return True


# ─── Plan-level orchestrator ───────────────────────────────────────────────


def reextract_titles_for_plan(
    session: Session,
    plan: Plan,
    *,
    pdf_bytes: bytes,
    overwrite_manual: bool = False,
    llm_fallback: bool = True,
) -> ReextractCounters:
    """Apply full-page text extraction + batched OpenAI sheet classification/naming.

    Same underlying path as AI Stage 2 (``execute_sheet_text_llm_for_plan``).
    Rows with ``sheet_name_source='manual'`` do not receive name updates unless
    ``overwrite_manual`` is True; classification columns still update.

    ``llm_fallback`` is retained for API compatibility and ignored.
    """
    _ = llm_fallback

    counters = ReextractCounters()
    if not pdf_bytes:
        logger.warning("reextract_titles_for_plan: empty PDF bytes for plan=%s", plan.id)
        return counters

    sheets: list[Sheet] = list(
        session.query(Sheet)
        .filter(Sheet.plan_id == plan.id)
        .order_by(Sheet.page_number)
        .all()
    )
    counters.total = len(sheets)
    if not sheets:
        return counters

    for sheet in sheets:
        if not _sheet_eligible_for_auto_name(sheet, overwrite_manual=overwrite_manual):
            counters.manual_skipped += 1

    eligible = {
        s.id: _sheet_eligible_for_auto_name(s, overwrite_manual=overwrite_manual)
        for s in sheets
    }

    try:
        cache_hits, _llm_by_page, rowcount = (
            ai_sheet_text_llm.execute_sheet_text_llm_for_plan(
                session,
                org_id=plan.org_id,
                sheets=sheets,
                pdf_bytes=pdf_bytes,
                sheet_eligible_for_names=eligible,
            )
        )
    except Exception as exc:
        logger.exception(
            "reextract_titles_for_plan: sheet text LLM failed plan=%s", plan.id
        )
        counters.errors.append({"error": str(exc)[:200]})
        return counters

    counters.sheet_text_llm_cache_hits = cache_hits
    counters.written = rowcount
    counters.llm = len(sheets)

    try:
        session.flush()
    except Exception:
        logger.exception("reextract_titles_for_plan: flush failed plan=%s", plan.id)
        session.rollback()
        counters.errors.append({"error": "flush_failed"})

    return counters


__all__ = [
    "DRAWING_ID_RE",
    "MAX_NAME_CHARS",
    "MAX_NUMBER_CHARS",
    "MIN_TEXT_LENGTH",
    "NUMBER_ANCHORS",
    "PHASE_TOKENS",
    "PROJECT_NUMBER_RE",
    "ParsedTitleBlock",
    "ReextractCounters",
    "STOP_ANCHORS",
    "TITLE_ANCHORS",
    "TitleExtractionResult",
    "extract_drawing_name",
    "extract_drawing_number",
    "extract_title_for_sheet",
    "llm_extract",
    "parse_title_block_heuristic",
    "reextract_titles_for_plan",
]
