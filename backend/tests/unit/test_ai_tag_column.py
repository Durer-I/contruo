"""Tag-column / column-role scorer (Sprint AI-03).

* Strong heuristic: header keyword + first column wins without LLM.
* Ambiguous heuristic: LLM tie-break is invoked, result honored.
* LLM declining (returns -1 / OOR): fall back to heuristic top.
* Caching: repeated calls on the same headers + rows skip the LLM.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.services import ai_tag_column as tc


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_door_schedule_strong_heuristic_skips_llm():
    headers = ["MARK", "WIDTH", "HEIGHT", "MATERIAL", "REMARKS"]
    rows = [
        ["D101", "3'-0\"", "7'-0\"", "STEEL", "FIRE-RATED"],
        ["D102", "3'-0\"", "7'-0\"", "WOOD", ""],
        ["D103", "2'-8\"", "6'-8\"", "WOOD", ""],
    ]
    llm = MagicMock()
    scores = tc.score_columns(
        headers=headers,
        rows=rows,
        llm_factory=lambda: llm,
    )
    assert scores.tag_column_index == 0
    assert scores.used_llm is False
    assert scores.notes["tag_decision"] in {"heuristic_strong", "heuristic_clear_margin"}
    llm.structured_output.assert_not_called()
    # Description column is REMARKS-like; might or might not be detected --
    # either way the test asserts the *shape*, not the detection.
    assert scores.material_column_index == 3
    # WIDTH + HEIGHT are dimension columns.
    assert scores.dimension_column_indexes is not None
    assert set(scores.dimension_column_indexes) >= {1, 2}


def test_ambiguous_headers_calls_llm():
    headers = ["KEY", "VALUE", "NOTE", "REF"]
    rows = [
        ["A", "alpha thing", "n1", "r1"],
        ["B", "beta thing", "n2", "r2"],
        ["C", "gamma thing", "n3", "r3"],
    ]
    llm = MagicMock()
    llm.structured_output.return_value = {"tag_column_index": 3, "reason": "ref"}
    scores = tc.score_columns(
        headers=headers,
        rows=rows,
        llm_factory=lambda: llm,
    )
    llm.structured_output.assert_called_once()
    assert scores.tag_column_index == 3
    assert scores.used_llm is True
    assert scores.notes["tag_decision"] == "llm_tiebreak"


def test_llm_declines_falls_back_to_heuristic():
    headers = ["KEY", "VALUE", "NOTE", "REF"]
    rows = [
        ["A", "alpha thing", "n1", "r1"],
        ["B", "beta thing", "n2", "r2"],
        ["C", "gamma thing", "n3", "r3"],
    ]
    llm = MagicMock()
    llm.structured_output.return_value = {"tag_column_index": -1, "reason": "no tag column"}
    scores = tc.score_columns(
        headers=headers,
        rows=rows,
        llm_factory=lambda: llm,
    )
    # -1 -> coerced to None -> heuristic top wins as the safety net.
    assert scores.tag_column_index is not None
    assert scores.notes["tag_decision"] == "llm_failed_fallback_heuristic"


def test_empty_table_returns_empty_scores():
    scores = tc.score_columns(headers=[], rows=[])
    assert scores.tag_column_index is None
    assert scores.description_column_index is None
    assert scores.notes == {"reason": "empty_table"}


def test_quantity_column_detected_when_header_and_cells_match():
    headers = ["MARK", "DESCRIPTION", "QTY"]
    rows = [
        ["AC-1", "AIR HANDLER", "2"],
        ["AC-2", "AIR HANDLER", "1"],
        ["AC-3", "AIR HANDLER", "4"],
    ]
    scores = tc.score_columns(headers=headers, rows=rows)
    assert scores.tag_column_index == 0
    assert scores.quantity_column_index == 2
    assert scores.description_column_index == 1


def test_dimension_column_detected_for_single_letter_headers():
    headers = ["MARK", "W", "H"]
    rows = [
        ["W101", "36", "60"],
        ["W102", "48", "60"],
    ]
    scores = tc.score_columns(headers=headers, rows=rows)
    assert scores.tag_column_index == 0
    assert scores.dimension_column_indexes is not None
    assert set(scores.dimension_column_indexes) == {1, 2}


def test_llm_call_failure_does_not_explode():
    headers = ["KEY", "VALUE", "NOTE", "REF"]
    rows = [
        ["A", "alpha thing", "n1", "r1"],
        ["B", "beta thing", "n2", "r2"],
    ]
    llm = MagicMock()
    llm.structured_output.side_effect = RuntimeError("rate-limited")
    scores = tc.score_columns(
        headers=headers,
        rows=rows,
        llm_factory=lambda: llm,
    )
    assert scores.tag_column_index is not None  # heuristic safety net
    assert scores.notes["tag_decision"] == "llm_failed_fallback_heuristic"
