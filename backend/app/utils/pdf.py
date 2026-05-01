"""PDF parsing utilities backed by PyMuPDF.

Isolated in a module so the Celery worker and tests can swap the implementation
or patch ``fitz`` without touching the task layer.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover -- fitz is declared in requirements.txt
    fitz = None

from PIL import Image

logger = logging.getLogger(__name__)

#: Default DPI for clip rendering (used by Stage 1 OCR fallback). 144 = 2x the
#: native PDF resolution (72 DPI) -- a sweet spot for Tesseract on title-block
#: text without exploding memory on large clips. Increase to 200 for faint
#: scans; the OCR layer caps at 300 to bound RAM.
DEFAULT_CLIP_DPI = 144

#: Default thumbnail max-dimension for sheet classification (Stage 2 vision
#: fallback). 512px keeps the multimodal prompt under typical token budgets
#: while preserving enough detail to recognize discipline + sheet type.
DEFAULT_CLASSIFICATION_THUMB_MAX_DIM = 512

#: AIA/common construction sheet-number patterns, e.g. "A1.01", "A-101", "M2.03", "S1.1",
#: "E2.1a", "SD-101". Matched at the start of a trimmed line to reduce false positives.
_SHEET_NUMBER_PATTERN = re.compile(
    r"^([A-Z]{1,3}-?\d{1,3}(?:\.\d{1,3})?[A-Za-z]?)\b",
    flags=re.MULTILINE,
)

#: Match "SHEET 3 OF 47" style markers.
_SHEET_OF_PATTERN = re.compile(
    r"SHEET\s+(\d+)\s+OF\s+(\d+)",
    flags=re.IGNORECASE,
)


@dataclass
class PageInfo:
    page_number: int
    width_px: int
    height_px: int
    sheet_name: str | None = None
    text_content: str = ""
    thumbnail_png: bytes | None = None
    #: Flattened line segments from vector paths (PDF user space) for snap-to-geometry.
    vector_snap_segments: list[dict[str, float]] = field(default_factory=list)


def extract_vector_snap_segments(page: Any, *, max_segments: int = 30_000) -> list[dict[str, float]]:
    """Collect straight segments from PyMuPDF drawing paths (best-effort)."""
    if fitz is None:
        return []
    out: list[dict[str, float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:  # pragma: no cover
        logger.exception("get_drawings failed")
        return []
    for path in drawings:
        for it in path.get("items") or []:
            if len(out) >= max_segments:
                return out
            if not it:
                continue
            kind = it[0]
            try:
                if kind == "l" and len(it) >= 3:
                    p1, p2 = it[1], it[2]
                    out.append(
                        {
                            "x1": float(p1.x),
                            "y1": float(p1.y),
                            "x2": float(p2.x),
                            "y2": float(p2.y),
                        }
                    )
                elif kind == "re" and len(it) >= 2:
                    r = it[1]
                    x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
                    for a, b, c, d in (
                        (x0, y0, x1, y0),
                        (x1, y0, x1, y1),
                        (x1, y1, x0, y1),
                        (x0, y1, x0, y0),
                    ):
                        if len(out) >= max_segments:
                            return out
                        out.append({"x1": a, "y1": b, "x2": c, "y2": d})
            except (TypeError, ValueError, AttributeError):
                continue
    return out


@dataclass
class PdfExtractResult:
    page_count: int
    pages: list[PageInfo] = field(default_factory=list)
    #: PDF ``/Info`` dictionary (strings), used for scale hints in the Celery worker.
    metadata: dict[str, str] = field(default_factory=dict)


def _extract_sheet_name(text: str) -> str | None:
    """Heuristic sheet-name detector from a page's title block text.

    Construction title blocks typically include the sheet number (e.g. "A1.01") and
    a descriptive title ("First Floor Plan"). We scan for a sheet-number token first;
    if found, we try to find a neighbouring descriptive line that looks like a title.

    Returns a formatted string like "A1.01 - First Floor Plan", or just the sheet
    number, or None if nothing is found.
    """
    if not text:
        return None

    number_match = _SHEET_NUMBER_PATTERN.search(text)
    if not number_match:
        # Fall back to SHEET X OF Y if nothing else
        of_match = _SHEET_OF_PATTERN.search(text)
        if of_match:
            return f"Sheet {of_match.group(1)} of {of_match.group(2)}"
        return None

    number = number_match.group(1)

    # Look for a reasonable title within ~5 lines after the sheet number. Title-case or
    # all-caps phrasing is typical ("FIRST FLOOR PLAN", "Ground Floor Plan").
    tail = text[number_match.end():]
    candidates = []
    for line in tail.splitlines()[:8]:
        s = line.strip()
        if not s:
            continue
        # Skip obvious non-titles (dates, pure numbers, units).
        if re.fullmatch(r"[\d\s/:\-.]+", s):
            continue
        if len(s) < 4 or len(s) > 60:
            continue
        candidates.append(s)
        if len(candidates) >= 2:
            break

    if candidates:
        title = candidates[0].title() if candidates[0].isupper() else candidates[0]
        return f"{number} - {title}"
    return number


def extract_pdf(
    pdf_bytes: bytes,
    *,
    thumbnail_width_px: int = 480,
    on_page: Callable[[int, int], None] | None = None,
) -> PdfExtractResult:
    """Parse a PDF into page-level metadata.

    Generates thumbnails, extracts text, and runs the sheet-name heuristic on each page.

    Args:
        pdf_bytes: Raw PDF bytes.
        thumbnail_width_px: Target width for thumbnail rendering; height is derived from the
            page's aspect ratio. We prefer a fixed width since the sheet index panel has a
            fixed width in the UI.
        on_page: Optional callback ``(page_number, total_pages)`` invoked after each page
            is processed. Used to report progress back to the DB.

    Returns:
        PdfExtractResult with one PageInfo per page.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total = doc.page_count
        pages: list[PageInfo] = []
        meta_raw = doc.metadata or {}
        pdf_meta = {str(k): (str(v) if v is not None else "") for k, v in meta_raw.items()}

        for i in range(total):
            page = doc.load_page(i)
            rect = page.rect
            width_pts = rect.width
            height_pts = rect.height

            # Render a full-resolution mental model is unnecessary; PyMuPDF's default DPI is 72.
            # For thumbnails we downscale to the target width.
            thumb_scale = thumbnail_width_px / width_pts if width_pts else 1.0
            thumb_matrix = fitz.Matrix(thumb_scale, thumb_scale)
            pix = page.get_pixmap(matrix=thumb_matrix, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            thumb_png = buf.getvalue()

            text = page.get_text("text") or ""
            sheet_name = _extract_sheet_name(text)
            snap_segs = extract_vector_snap_segments(page)

            pages.append(
                PageInfo(
                    page_number=i + 1,
                    width_px=int(width_pts),
                    height_px=int(height_pts),
                    sheet_name=sheet_name,
                    text_content=text,
                    thumbnail_png=thumb_png,
                    vector_snap_segments=snap_segs,
                )
            )

            if on_page is not None:
                try:
                    on_page(i + 1, total)
                except Exception:  # pragma: no cover -- progress callback must never kill extraction
                    logger.exception("on_page progress callback failed")

        return PdfExtractResult(page_count=total, pages=pages, metadata=pdf_meta)
    finally:
        doc.close()


# ─── AI-02 helpers: clip extraction + thumbnail rendering ──────────────────


def _coerce_rect(rect_or_dict: Any) -> Any:
    """Accept either a fitz.Rect or ``{"x0","y0","x1","y1"}`` dict."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    if hasattr(rect_or_dict, "x0") and hasattr(rect_or_dict, "y0"):
        return rect_or_dict
    if isinstance(rect_or_dict, dict):
        return fitz.Rect(
            float(rect_or_dict["x0"]),
            float(rect_or_dict["y0"]),
            float(rect_or_dict["x1"]),
            float(rect_or_dict["y1"]),
        )
    raise TypeError(f"Cannot coerce {type(rect_or_dict).__name__} to fitz.Rect")


def extract_text_in_rect(page: Any, rect_pts: Any) -> str:
    """Extract text from a single rect of a PDF page in PDF user-space points.

    Used by Stage 1 (title-block extraction) to read the title cell without
    pulling the entire page's text. Returns the empty string when the clip
    contains no text layer (caller should escalate to OCR).

    The cleanup matches the spec: collapse whitespace, strip line breaks.
    Multiple blank lines between fields collapse to a single space so the
    final ``sheet_name`` reads naturally ("A1.01 First Floor Plan", not
    "A1.01\\n\\nFirst Floor Plan\\n\\n").
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    rect = _coerce_rect(rect_pts)
    try:
        raw = page.get_text("text", clip=rect) or ""
    except Exception:  # pragma: no cover -- fitz raises on malformed clips
        logger.exception("get_text(clip=) failed")
        return ""
    return _normalize_title_text(raw)


def _normalize_title_text(raw: str) -> str:
    """Collapse runs of whitespace and trim. Used for both PyMuPDF and OCR text."""
    if not raw:
        return ""
    # Collapse all whitespace (incl. newlines) to single spaces, then trim.
    return re.sub(r"\s+", " ", raw).strip()


def render_clip_to_png(
    page: Any,
    rect_pts: Any,
    *,
    dpi: int = DEFAULT_CLIP_DPI,
) -> bytes:
    """Render a sub-rectangle of a PDF page as a PNG.

    Used by:
      * Stage 1 OCR fallback (when ``extract_text_in_rect`` returns empty).
      * Stage 2 vision-fallback if a future caller wants a region crop.

    DPI defaults to 144 (2x the PDF's native 72 DPI) to give Tesseract enough
    detail without ballooning the image. Memory bound: a typical title-block
    clip at 144 DPI produces a ~600x300 PNG (<100 KB).
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    rect = _coerce_rect(rect_pts)
    # PyMuPDF default is 72 DPI; scale = dpi / 72.
    scale = max(1.0, dpi / 72.0)
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_thumbnail_for_classification(
    page: Any,
    *,
    max_dim: int = DEFAULT_CLASSIFICATION_THUMB_MAX_DIM,
) -> bytes:
    """Render a downsampled thumbnail of the full page for vision classification.

    Used by Stage 2 (sheet classification fallback). Targets ``max_dim`` on
    the longer page edge so portrait and landscape sheets get similar token
    cost in the multimodal prompt. PNG output keeps line drawings legible
    (vs JPEG which would smear thin construction-drawing lines).

    NOTE: callers should cache the bytes by sheet content hash via
    ``ai_cache``; this function does not memoize.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    rect = page.rect
    longer = max(rect.width, rect.height) or 1.0
    scale = max(0.05, min(1.0, max_dim / longer))
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def get_words_in_rect(page: Any, rect_pts: Any) -> list[tuple[float, float, float, float, str]]:
    """Return word-level bboxes within a clip rect as (x0, y0, x1, y1, text) tuples.

    Used by the title-block heuristic to cluster small text near page edges.
    Returns an empty list when the page has no text layer.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    rect = _coerce_rect(rect_pts)
    try:
        words = page.get_text("words", clip=rect) or []
    except Exception:  # pragma: no cover
        logger.exception("get_text('words', clip=) failed")
        return []
    out: list[tuple[float, float, float, float, str]] = []
    for w in words:
        # PyMuPDF format: (x0, y0, x1, y1, text, block_no, line_no, word_no)
        if len(w) < 5:
            continue
        try:
            out.append((float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])))
        except (TypeError, ValueError):
            continue
    return out


def get_all_words(page: Any) -> list[tuple[float, float, float, float, str]]:
    """All word-level bboxes on a page. Same tuple shape as ``get_words_in_rect``."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed")
    try:
        words = page.get_text("words") or []
    except Exception:  # pragma: no cover
        logger.exception("get_text('words') failed")
        return []
    out: list[tuple[float, float, float, float, str]] = []
    for w in words:
        if len(w) < 5:
            continue
        try:
            out.append((float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])))
        except (TypeError, ValueError):
            continue
    return out
