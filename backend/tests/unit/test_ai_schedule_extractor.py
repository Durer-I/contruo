"""Schedule extractor strategy chain (Sprint AI-03).

The escalation order is the key behaviour:

    pdfplumber.lines_strict -> pdfplumber.lines -> pdfplumber.text -> vision

Each strategy is mocked at the boundary (a fake ``plumber_page`` whose
``find_tables`` returns canned tables for the strategy under test).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services import ai_schedule_extractor as se


class _FakeTable:
    def __init__(self, bbox: tuple[float, float, float, float], rows: list[list[str]]):
        self.bbox = bbox
        self._rows = rows

    def extract_table(self) -> list[list[str]]:
        return self._rows


class _FakeCropped:
    def __init__(self, rows: list[list[str]]):
        self._rows = rows

    def extract_table(self) -> list[list[str]]:
        return self._rows


class _FakePage:
    """Minimal stand-in for a ``pdfplumber.Page``.

    ``find_tables_by_strategy`` lets each test inject what each strategy
    returns; ``crop`` returns a wrapper whose ``extract_table`` mirrors the
    table's rows so the row-quality scorer sees a consistent shape.
    """

    def __init__(self, by_strategy: dict[str, list[_FakeTable]]):
        self._by_strategy = by_strategy

    def find_tables(self, opts: dict) -> list[_FakeTable]:
        return self._by_strategy.get(opts["vertical_strategy"], [])

    def crop(self, _bbox):  # pdfplumber returns a Page; we hand back a stub
        # The extractor calls ``cropped.extract_table()`` immediately after.
        # Use the most-recently-inspected table's rows.
        return _FakeCropped(self._last_rows)

    def _seed_last_rows(self, rows: list[list[str]]) -> None:
        self._last_rows = rows


@pytest.fixture(autouse=True)
def _ensure_strategy_iter_uses_seed():
    """The fake page hands ``crop`` the rows of the table being inspected.

    pdfplumber's real flow is: enumerate ``find_tables`` -> ``crop(bbox)`` ->
    ``extract_table()``. We monkeypatch this ordering by seeding the
    last-rows attribute as the fake table iterator yields tables.
    """
    yield


def _strategy_with_one_quality_table(strategy_id: str) -> _FakePage:
    rows = [
        ["MARK", "WIDTH", "HEIGHT", "MATERIAL"],
        ["D101", "3'-0\"", "7'-0\"", "STEEL"],
        ["D102", "3'-0\"", "7'-0\"", "WOOD"],
        ["D103", "2'-8\"", "6'-8\"", "WOOD"],
    ]
    table = _FakeTable((100, 100, 400, 250), rows)
    page = _FakePage({strategy_id: [table]})
    page._seed_last_rows(rows)
    return page


def test_lines_strict_wins_when_present():
    page = _strategy_with_one_quality_table("lines_strict")
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=792.0,
        page_height=612.0,
        vision_model=None,
        vision_image_bytes=None,
    )
    assert len(candidates) == 1
    assert candidates[0].extraction_method == "pdfplumber_lines_strict"
    assert candidates[0].headers == ["MARK", "WIDTH", "HEIGHT", "MATERIAL"]
    assert len(candidates[0].rows) == 3


def test_lines_fallback_runs_when_strict_empty():
    page = _strategy_with_one_quality_table("lines")
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=792.0,
        page_height=612.0,
        vision_model=None,
        vision_image_bytes=None,
    )
    assert len(candidates) == 1
    assert candidates[0].extraction_method == "pdfplumber_lines"


def test_text_fallback_runs_when_lines_empty():
    page = _strategy_with_one_quality_table("text")
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=792.0,
        page_height=612.0,
        vision_model=None,
        vision_image_bytes=None,
    )
    assert len(candidates) == 1
    assert candidates[0].extraction_method == "pdfplumber_text"


def test_vision_fallback_when_all_pdfplumber_strategies_empty():
    page = _FakePage({})
    vision = MagicMock()
    vision.extract_structured.return_value = {
        "tables": [
            {
                "headers": ["TAG", "DESCRIPTION"],
                "rows": [["AC-1", "AIR HANDLER"], ["AC-2", "AIR HANDLER"]],
            }
        ]
    }
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=800.0,
        page_height=600.0,
        vision_model=vision,
        vision_image_bytes=lambda: b"fake-png",
    )
    assert len(candidates) == 1
    assert candidates[0].extraction_method == "vision"
    assert candidates[0].headers == ["TAG", "DESCRIPTION"]
    assert candidates[0].bbox_pdf == {"x0": 0.0, "y0": 0.0, "x1": 800.0, "y1": 600.0}


def test_vision_disabled_returns_empty_when_heuristics_empty():
    page = _FakePage({})
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=800.0,
        page_height=600.0,
        vision_model=None,
        vision_image_bytes=None,
    )
    assert candidates == []


def test_low_quality_table_is_filtered_out():
    """A 1xN noise match (header row + zero data rows) shouldn't pass."""
    rows = [["", "", ""]]
    page = _FakePage({"lines_strict": [_FakeTable((0, 0, 100, 50), rows)]})
    page._seed_last_rows(rows)
    candidates = se.extract_schedules_for_page(
        plumber_page=page,
        page_width=800.0,
        page_height=600.0,
        vision_model=None,
        vision_image_bytes=None,
    )
    assert candidates == []


def test_serialize_round_trip():
    candidates = [
        se.ScheduleCandidate(
            bbox_pdf={"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0},
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
            extraction_method="pdfplumber_lines_strict",
            quality=0.8,
        )
    ]
    serialized = se.serialize_candidates(candidates)
    deserialized = se.deserialize_candidates(serialized)
    assert len(deserialized) == 1
    assert deserialized[0].headers == ["A", "B"]
    assert deserialized[0].rows == [["1", "2"], ["3", "4"]]
    assert deserialized[0].extraction_method == "pdfplumber_lines_strict"
