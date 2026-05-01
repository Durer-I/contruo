"""Tesseract OCR wrapper for the AI Auto-Takeoff pipeline (Sprint AI-02).

Used as the fallback in Stage 1 when ``page.get_text("text", clip=rect)``
returns nothing (scanned PDFs, image-only title blocks). Kept in its own
module so:

* The Celery worker, tests, and ad-hoc scripts can mock at this boundary.
* The Tesseract binary path resolves once via ``AI_TESSERACT_CMD`` env var
  (Linux container) or PATH (typical CI) without leaking ``pytesseract``
  imports throughout the codebase.
* Missing-binary cases degrade gracefully -- ``ocr_image_bytes`` returns
  ``""`` instead of raising, so a worker without Tesseract installed still
  finishes the run (it just won't recover OCR-only titles).

Cost: zero. OCR is a local CPU call -- no model API hit -- so calls are
*not* wrapped in ``with_cost_tracking``. The whole point is to keep the
expensive vision model out of the loop for sheets that already have a
title-block region.
"""

from __future__ import annotations

import logging
import shutil
from typing import Any, Literal

from app.config import get_settings

logger = logging.getLogger(__name__)

#: Tesseract config used for title-block OCR. Mirrors the prototype in
#: ``AI/controller/title.py``: PSM 6 = "assume a uniform block of text",
#: OEM 3 = "default LSTM + legacy combined". This is markedly more accurate
#: than Tesseract's default (PSM 3 = fully automatic) on the small,
#: tightly-packed labels typical of construction title blocks.
TITLE_BLOCK_TESSERACT_CONFIG = "--oem 3 --psm 6"

#: Threshold cutoff (0..255) for the title-block preprocessing path. Same
#: constant as the prototype's ``cv2.threshold(..., 150, 255, ...)`` step --
#: drops mid-tone pixels (background bleed, faint hatching) and keeps
#: ink-dark text intact. Tuned for the typical 144-DPI clip render produced
#: by ``app.utils.pdf.render_clip_to_png``.
TITLE_BLOCK_THRESHOLD = 150

#: Cached "is tesseract available?" probe. ``None`` = not yet probed,
#: ``True/False`` = result of the most recent probe. Reset by calling
#: ``_reset_probe_cache_for_tests`` from tests.
_tesseract_available: bool | None = None
#: Cached resolved binary path, ``""`` when unresolved.
_resolved_cmd: str = ""


def _reset_probe_cache_for_tests() -> None:
    """Clear the availability probe (test helper)."""
    global _tesseract_available, _resolved_cmd
    _tesseract_available = None
    _resolved_cmd = ""


def _resolve_tesseract_cmd() -> str:
    """Return the Tesseract binary path or empty string when unresolved.

    Resolution order:
      1. ``AI_TESSERACT_CMD`` env var (set on Windows dev boxes).
      2. ``shutil.which("tesseract")`` (Linux Celery workers, CI).
      3. Empty string (graceful degradation).
    """
    global _resolved_cmd
    if _resolved_cmd:
        return _resolved_cmd
    settings = get_settings()
    candidate = (settings.ai_tesseract_cmd or "").strip()
    if candidate:
        _resolved_cmd = candidate
        return candidate
    found = shutil.which("tesseract") or ""
    _resolved_cmd = found
    return found


def is_available() -> bool:
    """Return True when a usable Tesseract install is reachable.

    Probes once per process; cached to avoid repeated ``which`` calls under
    high-volume per-sheet OCR. Tests reset the cache via
    ``_reset_probe_cache_for_tests``.
    """
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available

    cmd = _resolve_tesseract_cmd()
    if not cmd:
        logger.warning(
            "Tesseract not configured (AI_TESSERACT_CMD empty and `tesseract` "
            "not on PATH); Stage 1 OCR fallback will return empty strings."
        )
        _tesseract_available = False
        return False

    try:
        import pytesseract  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("pytesseract is not installed; OCR fallback disabled.")
        _tesseract_available = False
        return False

    pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        # pytesseract.TesseractNotFoundError + generic OS errors when binary is
        # broken or wrong arch.
        logger.warning("Tesseract probe failed (%s); OCR fallback disabled.", exc)
        _tesseract_available = False
        return False

    _tesseract_available = True
    return True


def ocr_image_bytes(
    png_bytes: bytes,
    *,
    lang: str = "eng",
    preprocess: Literal["none", "title_block"] = "none",
    tesseract_config: str | None = None,
) -> str:
    """OCR a PNG byte string and return the recognized text.

    Returns ``""`` (not None) for graceful caller composition. Failure modes:

    * Tesseract not installed / not on PATH -> ``""``
    * pytesseract import fails -> ``""``
    * Tesseract crashes on the input -> ``""`` (logged, not raised)

    ``preprocess="title_block"`` mirrors the prototype OCR path in
    ``AI/controller/title.py``: convert to grayscale, then apply a fixed
    binary threshold at :data:`TITLE_BLOCK_THRESHOLD`. This boosts contrast
    on tinted / hatched title-block backgrounds where the default
    PIL-passthrough route under-recognizes characters.

    ``tesseract_config`` is forwarded to ``pytesseract.image_to_string``;
    callers that want the title-block preset can pass
    :data:`TITLE_BLOCK_TESSERACT_CONFIG` (PSM 6 / OEM 3).

    The caller is responsible for any post-processing (whitespace normalize,
    line-break collapse). ``backend.app.utils.pdf._normalize_title_text``
    handles that for the Stage 1 path.
    """
    if not png_bytes:
        return ""
    if not is_available():
        return ""

    import io
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image
    except ImportError:  # pragma: no cover -- gated by is_available()
        return ""

    try:
        img = Image.open(io.BytesIO(png_bytes))
    except Exception:
        logger.exception("OCR: failed to open PNG bytes (%d bytes)", len(png_bytes))
        return ""

    if preprocess == "title_block":
        try:
            # ``"L"`` = 8-bit grayscale; ``point`` applies a per-pixel
            # threshold without a NumPy/OpenCV dependency. The lambda
            # returns 0 for dim pixels, 255 for ink -- exactly the binary
            # output ``cv2.threshold(..., 150, 255, THRESH_BINARY)`` produces
            # in the prototype.
            img = img.convert("L").point(
                lambda px, t=TITLE_BLOCK_THRESHOLD: 255 if px > t else 0,
                mode="1",
            )
        except Exception:
            # Preprocessing is best-effort -- fall through to OCR on the
            # original image rather than fail the whole extraction.
            logger.exception("OCR: title_block preprocess failed; using raw image")

    kwargs: dict[str, Any] = {"lang": lang}
    if tesseract_config:
        kwargs["config"] = tesseract_config

    try:
        text = pytesseract.image_to_string(img, **kwargs) or ""
    except Exception:
        logger.exception("OCR: pytesseract.image_to_string failed")
        return ""

    return text.strip()


def get_resolved_cmd_for_diagnostics() -> str:
    """Public accessor for the resolved binary path. Used by ops endpoints."""
    return _resolve_tesseract_cmd()


__all__: list[str] = [
    "is_available",
    "ocr_image_bytes",
    "get_resolved_cmd_for_diagnostics",
    "TITLE_BLOCK_TESSERACT_CONFIG",
    "TITLE_BLOCK_THRESHOLD",
]


# Re-export for tests.
def _set_probe_cache_for_tests(value: bool | None, cmd: str = "") -> None:  # pragma: no cover
    """Test helper to bypass the probe and force availability state."""
    global _tesseract_available, _resolved_cmd
    _tesseract_available = value
    _resolved_cmd = cmd
