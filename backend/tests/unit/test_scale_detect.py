"""Tests for title-block scale heuristics."""

import pytest

from app.utils.scale_detect import (
    compute_scale_from_calibration_line,
    detect_scale_from_text,
    detect_scale,
)


def test_quarter_inch_scale():
    text = 'TITLE\nScale: 1/4" = 1\'-0"\n'
    d = detect_scale_from_text(text)
    assert d is not None
    assert d.scale_unit == "ft"
    assert abs(d.scale_value - (1.0 / 18.0)) < 1e-9


def test_one_inch_to_ten_feet():
    text = 'Reference 1" = 10\''
    d = detect_scale_from_text(text)
    assert d is not None
    assert d.scale_unit == "ft"
    assert abs(d.scale_value - (10.0 / 72.0)) < 1e-9


def test_metric_ratio():
    text = "Scale 1:100\n"
    d = detect_scale_from_text(text)
    assert d is not None
    assert d.scale_unit == "m"


def test_imperial_ratio_48():
    text = "SCALE 1:48"
    d = detect_scale_from_text(text)
    assert d is not None
    assert d.scale_unit == "ft"
    assert abs(d.scale_value - (4.0 / 72.0)) < 1e-9


def test_ambiguous_ratio_skipped():
    assert detect_scale_from_text("ratio 1:33") is None


def test_manual_calibration_ft():
    d = compute_scale_from_calibration_line(500.0, 10.0, "ft")
    assert d.scale_unit == "ft"
    assert abs(d.scale_value - 0.02) < 1e-12


def test_manual_calibration_m():
    d = compute_scale_from_calibration_line(1000.0, 2.5, "m")
    assert d.scale_unit == "m"
    assert abs(d.scale_value - 0.0025) < 1e-12


def test_detect_prefers_page_text():
    meta = {"subject": 'Scale 1:100'}
    d = detect_scale("nothing", pdf_metadata=meta)
    assert d is not None
    assert d.scale_unit == "m"


@pytest.mark.parametrize(
    "bad",
    [
        (0, 10, "ft"),
        (10, 0, "ft"),
        (10, 10, "yards"),
    ],
)
def test_manual_invalid(bad):
    a, b, u = bad
    with pytest.raises(ValueError):
        compute_scale_from_calibration_line(float(a), float(b), u)
