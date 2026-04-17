"""Tests for the PDF sheet-name heuristic.

The heuristic is pure-string logic so we can unit-test without invoking PyMuPDF.
"""

from app.utils.pdf import _extract_sheet_name


def test_extracts_aia_sheet_number_with_title():
    text = """ACME ARCHITECTS
Project #2024-001
A1.01
FIRST FLOOR PLAN
Date: 2024-03-15
"""
    assert _extract_sheet_name(text) == "A1.01 - First Floor Plan"


def test_extracts_dash_format_sheet_number():
    text = """M-201
Mechanical Second Floor
Scale: 1/4"=1'-0"
"""
    assert _extract_sheet_name(text) == "M-201 - Mechanical Second Floor"


def test_falls_back_to_sheet_x_of_y():
    text = "SOMETHING ELSE\nSHEET 3 OF 47\nmore text"
    assert _extract_sheet_name(text) == "Sheet 3 of 47"


def test_returns_number_only_when_no_title_found():
    text = "E2.1\n2024-03-15\n"
    assert _extract_sheet_name(text) == "E2.1"


def test_handles_empty_text():
    assert _extract_sheet_name("") is None
    assert _extract_sheet_name("just random words here no sheet number") is None


def test_lowercase_letters_not_matched_as_sheet():
    text = "interior\nsome text\n"
    assert _extract_sheet_name(text) is None
