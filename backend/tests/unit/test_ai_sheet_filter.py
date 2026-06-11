"""Sheet keyword filters (Sprint AI-03).

Pure-Python predicate tests; the SQL-emitting helpers are verified indirectly
by ``test_ai_pipeline_tasks`` (which mocks the session).
"""

from __future__ import annotations

from app.services import ai_sheet_filter


def test_schedule_keywords_match_door_window_finish():
    assert ai_sheet_filter.matches_schedule_keywords("DOOR SCHEDULE")
    assert ai_sheet_filter.matches_schedule_keywords("Window Schedule - First Floor")
    assert ai_sheet_filter.matches_schedule_keywords("FINISH SCHEDULE")


def test_schedule_keywords_match_equipment_and_panel_lists():
    assert ai_sheet_filter.matches_schedule_keywords("M-601 EQUIPMENT")
    assert ai_sheet_filter.matches_schedule_keywords("E-602 Panel Schedule")
    assert ai_sheet_filter.matches_schedule_keywords("P-601 FIXTURE LIST")


def test_schedule_keywords_reject_plan_sheets():
    assert not ai_sheet_filter.matches_schedule_keywords("A-101 First Floor Plan")
    assert not ai_sheet_filter.matches_schedule_keywords("S-201 Foundation Plan")
    assert not ai_sheet_filter.matches_schedule_keywords(None)
    assert not ai_sheet_filter.matches_schedule_keywords("")


def test_legend_keywords_match_typical_titles():
    assert ai_sheet_filter.matches_legend_keywords("Symbol Legend")
    assert ai_sheet_filter.matches_legend_keywords("ABBREVIATIONS & NOTES")
    assert ai_sheet_filter.matches_legend_keywords("Reflected Ceiling Plan")
    assert ai_sheet_filter.matches_legend_keywords("RCP - Level 2")


def test_legend_keywords_reject_unrelated_sheets():
    assert not ai_sheet_filter.matches_legend_keywords("DEMOLITION PLAN")
    assert not ai_sheet_filter.matches_legend_keywords("Title Sheet")
    assert not ai_sheet_filter.matches_legend_keywords(None)


def test_keywords_are_case_insensitive():
    """The SQL filter uses ``ilike``; the predicate must match it semantically."""
    assert ai_sheet_filter.matches_schedule_keywords("door schedule")
    assert ai_sheet_filter.matches_schedule_keywords("DOOR SCHEDULE")
    assert ai_sheet_filter.matches_schedule_keywords("Door Schedule")
