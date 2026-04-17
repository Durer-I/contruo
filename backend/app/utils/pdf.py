"""PDF parsing utilities backed by PyMuPDF.

Isolated in a module so the Celery worker and tests can swap the implementation
or patch ``fitz`` without touching the task layer.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Callable

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover -- fitz is declared in requirements.txt
    fitz = None

from PIL import Image

logger = logging.getLogger(__name__)

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

            pages.append(
                PageInfo(
                    page_number=i + 1,
                    width_px=int(width_pts),
                    height_px=int(height_pts),
                    sheet_name=sheet_name,
                    text_content=text,
                    thumbnail_png=thumb_png,
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
