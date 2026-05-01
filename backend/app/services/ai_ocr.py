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

#: Threshold cutoff (0..255) for the optional fixed-threshold title-block
#: preprocessing path (``preprocess="title_block_fixed"``).
TITLE_BLOCK_THRESHOLD = 150


def _otsu_threshold_from_histogram(hist: list[int]) -> int:
    """Otsu threshold from a 256-bin grayscale histogram (PIL ``.histogram()``).

    Pure Python -- matches the intent of ``cv2.threshold(..., THRESH_OTSU)``
    without pulling NumPy/OpenCV into the worker image.
    """
    total = sum(hist)
    if total <= 0:
        return TITLE_BLOCK_THRESHOLD
    sum_all = sum(i * c for i, c in enumerate(hist))
    sum_b = 0
    w_b = 0
    best_t = 0
    max_var = -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = float(w_b) * float(w_f) * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            best_t = t
    return best_t


#: Tesseract config for title-block OCR. Matches the standalone prototype
#: (``--oem 1 --psm 4``).
TITLE_BLOCK_TESSERACT_CONFIG = "--oem 1 --psm 4"

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
    preprocess: Literal["none", "title_block", "title_block_fixed"] = "none",
    tesseract_config: str | None = None,
) -> str:
    """OCR a PNG byte string and return the recognized text.

    Returns ``""`` (not None) for graceful caller composition. Failure modes:

    * Tesseract not installed / not on PATH -> ``""``
    * pytesseract import fails -> ``""``
    * Tesseract crashes on the input -> ``""`` (logged, not raised)

    ``preprocess="title_block"`` converts to grayscale, applies **Otsu's**
    automatic global threshold (same idea as ``cv2.THRESH_OTSU`` in the
    standalone prototype, implemented without OpenCV/NumPy), then binarizes
    to black-on-white for Tesseract. This adapts to tinted / hatched
    backgrounds better than the legacy fixed cutoff at :data:`TITLE_BLOCK_THRESHOLD`.

    ``preprocess="title_block_fixed"`` (rarely used) keeps the historical fixed
    threshold at :data:`TITLE_BLOCK_THRESHOLD` for debugging regressions.

    ``tesseract_config`` is forwarded to ``pytesseract.image_to_string``;
    callers that want the title-block preset can pass
    :data:`TITLE_BLOCK_TESSERACT_CONFIG` (PSM 4 / OEM 1).

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
            gray = img.convert("L")
            thresh = _otsu_threshold_from_histogram(gray.histogram())
            img = gray.point(lambda px, t=thresh: 255 if px > t else 0, mode="1")
        except Exception:
            logger.exception("OCR: title_block preprocess failed; using raw image")
    elif preprocess == "title_block_fixed":
        try:
            img = img.convert("L").point(
                lambda px, t=TITLE_BLOCK_THRESHOLD: 255 if px > t else 0,
                mode="1",
            )
        except Exception:
            logger.exception("OCR: title_block_fixed preprocess failed; using raw image")

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
