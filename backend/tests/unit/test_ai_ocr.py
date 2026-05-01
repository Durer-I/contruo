"""Sprint AI-02: Tesseract OCR wrapper.

Verifies:
* `is_available()` resolves the binary via the configured env var first, then PATH.
* Missing-binary path returns False and `ocr_image_bytes` returns "" gracefully.
* The probe is cached -- repeated calls don't re-shell out to ``which``.
* The title-block preset forwards PSM 4 / OEM 1 to pytesseract and
  binarizes the image with Otsu (Sprint AI-02b: prototype OCR parity).
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services import ai_ocr


def _make_png(size: tuple[int, int] = (40, 20), color: int = 220) -> bytes:
    """Build a minimal valid PNG for the OCR pipeline to open."""
    img = Image.new("L", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_probe():
    ai_ocr._reset_probe_cache_for_tests()
    yield
    ai_ocr._reset_probe_cache_for_tests()


def test_is_available_returns_false_when_no_tesseract_anywhere():
    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value=None),
    ):
        mock_settings.return_value.ai_tesseract_cmd = ""
        assert ai_ocr.is_available() is False


def test_is_available_uses_env_var_path_when_set():
    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value="/should/not/be/used"),
    ):
        mock_settings.return_value.ai_tesseract_cmd = "/explicit/tesseract"
        # Stub the import + version check so this passes even where the SDK is missing.
        fake_pyt = type("Mod", (), {})()
        fake_pyt.pytesseract = type("Inner", (), {})()
        fake_pyt.pytesseract.tesseract_cmd = ""
        fake_pyt.get_tesseract_version = lambda: "5.3.0"
        with patch.dict("sys.modules", {"pytesseract": fake_pyt}):
            assert ai_ocr.is_available() is True
        assert ai_ocr._resolved_cmd == "/explicit/tesseract"


def test_ocr_image_bytes_returns_empty_when_unavailable():
    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value=None),
    ):
        mock_settings.return_value.ai_tesseract_cmd = ""
        assert ai_ocr.ocr_image_bytes(b"\x89PNG\r\n\x1a\nfake-bytes") == ""


def test_ocr_image_bytes_short_circuits_on_empty_input():
    # Doesn't matter whether tesseract is installed -- empty bytes always return "".
    assert ai_ocr.ocr_image_bytes(b"") == ""


def test_ocr_image_bytes_title_block_preset_forwards_config_and_preprocesses():
    """The ``preprocess="title_block"`` path must:

    1. binarize the image (we assert by checking the PIL object handed to
       ``pytesseract`` is mode ``"1"``), and
    2. forward the PSM 4 / OEM 1 string in the ``config`` kwarg.

    Without both, the OCR fallback regresses to Tesseract defaults that
    under-recognize tightly-packed title-block text -- exactly the failure
    mode that motivated AI-02b.
    """
    fake_pyt = MagicMock()
    fake_pyt.pytesseract = MagicMock()
    fake_pyt.pytesseract.tesseract_cmd = ""
    fake_pyt.get_tesseract_version = MagicMock(return_value="5.3.0")
    fake_pyt.image_to_string = MagicMock(return_value="A1.01 First Floor Plan\n")

    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value="/usr/bin/tesseract"),
        patch.dict("sys.modules", {"pytesseract": fake_pyt}),
    ):
        mock_settings.return_value.ai_tesseract_cmd = ""
        out = ai_ocr.ocr_image_bytes(
            _make_png(),
            preprocess="title_block",
            tesseract_config=ai_ocr.TITLE_BLOCK_TESSERACT_CONFIG,
        )

    assert out == "A1.01 First Floor Plan"
    fake_pyt.image_to_string.assert_called_once()
    args, kwargs = fake_pyt.image_to_string.call_args
    assert "psm 4" in kwargs["config"]
    assert "oem 1" in kwargs["config"]
    # Image preprocessing converted the input to a 1-bit binary image so
    # Tesseract sees clean black-on-white pixels.
    forwarded_img = args[0]
    assert forwarded_img.mode == "1"


def test_ocr_image_bytes_default_path_does_not_pass_config():
    """The legacy/default callers must continue to call pytesseract without a
    ``config`` kwarg so this change stays backward-compatible for any future
    OCR call site that's not the title-block fallback.
    """
    fake_pyt = MagicMock()
    fake_pyt.pytesseract = MagicMock()
    fake_pyt.pytesseract.tesseract_cmd = ""
    fake_pyt.get_tesseract_version = MagicMock(return_value="5.3.0")
    fake_pyt.image_to_string = MagicMock(return_value="raw text")

    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value="/usr/bin/tesseract"),
        patch.dict("sys.modules", {"pytesseract": fake_pyt}),
    ):
        mock_settings.return_value.ai_tesseract_cmd = ""
        ai_ocr.ocr_image_bytes(_make_png())

    kwargs = fake_pyt.image_to_string.call_args.kwargs
    assert "config" not in kwargs
    # No preprocess: image preserved as-is (mode != "1" for the L-mode test PNG).
    assert fake_pyt.image_to_string.call_args.args[0].mode != "1"


def test_is_available_cache_avoids_repeat_resolution():
    with (
        patch("app.services.ai_ocr.get_settings") as mock_settings,
        patch("app.services.ai_ocr.shutil.which", return_value=None) as which_mock,
    ):
        mock_settings.return_value.ai_tesseract_cmd = ""
        ai_ocr.is_available()
        ai_ocr.is_available()
        ai_ocr.is_available()
        # Probe path should only have called `which` once due to caching.
        assert which_mock.call_count == 1
