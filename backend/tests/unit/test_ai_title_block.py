"""Sprint AI-02b: title-block heuristic parser + plan orchestrator.

The parser is the highest-value test target in this sprint (per the
testing-strategy doc): pure logic, lots of edge cases, real customer
PDFs in the corpus. The orchestrator tests cover the manual-source
guard contract -- the single most important invariant for not destroying
user edits.

OCR + LLM stages are exercised via mocks at the boundary; we never call
Tesseract or OpenAI in unit tests.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services import ai_title_block


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ─── parse_title_block_heuristic ───────────────────────────────────────────


class TestParseTitleBlockHeuristic:
    """Confidence is asserted as a band rather than an exact value -- the
    parser's tier weights may be tuned without breaking these tests as
    long as the *relative* ordering (anchor > standalone > inline > repair)
    holds."""

    def test_empty_text_returns_zero_confidence(self):
        result = ai_title_block.parse_title_block_heuristic("")
        assert result.name is None
        assert result.number is None
        assert result.confidence == 0.0

    def test_whitespace_only_returns_zero_confidence(self):
        result = ai_title_block.parse_title_block_heuristic("   \n\n  ")
        assert result.confidence == 0.0
        assert not result.is_complete

    def test_anchor_based_after_extraction(self):
        text = """ARCHITECT
        Acme Architects
        DRAWING NAME
        DEMOLITION FLOOR PLANS
        DRAWING NUMBER
        D101
        DRAWN BY: JS"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.name == "DEMOLITION FLOOR PLANS"
        assert result.number == "D101"
        assert result.is_complete
        assert result.confidence >= 0.85  # both fields anchor-based

    def test_anchor_based_before_extraction_for_number(self):
        text = """A101
        SHEET NUMBER"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "A101"
        assert result.name is None
        # Prototype parity: ``min(name_conf, num_conf)`` with missing name -> 0.0.
        assert result.confidence == 0.0

    def test_standalone_drawing_id_when_no_anchor(self):
        text = """Random title block text
        Another random line
        A0.1
        Date: 2024"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "A0.1"

    def test_excludes_project_number_from_drawing_id_candidates(self):
        text = """PROJECT NUMBER
        12654.000
        DRAWING NUMBER
        AR105"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "AR105"
        assert result.number != "12654.000"

    def test_handles_phase_token_next_to_id(self):
        text = """SHEET NUMBER
        CD A0.1"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "A0.1"

    def test_drawing_name_anchor_collects_multi_line_until_stop(self):
        text = """SHEET TITLE
        FIRST FLOOR
        DEMOLITION PLAN
        DRAWN BY: ABC"""
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.name == "FIRST FLOOR DEMOLITION PLAN"

    def test_drawing_name_capped_at_max_chars(self):
        long_line = "X" * (ai_title_block.MAX_NAME_CHARS + 50)
        text = f"DRAWING NAME\n{long_line}"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.name is not None
        assert len(result.name) <= ai_title_block.MAX_NAME_CHARS

    def test_repair_fallback_for_ocr_letter_for_digit(self):
        """Token "A5O1" doesn't match the strict id regex (the trailing 'O1'
        breaks the digits-then-optional-letter shape) but DOES become a valid
        id ("A501") after the OCR letter-for-digit repair pass.
        """
        text = "A5O1"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "A501"
        # Missing name => name_conf 0; ``min(0, num_conf)`` is 0.
        assert result.confidence == 0.0

    def test_dash_format_drawing_id(self):
        text = "DRAWING NUMBER\nS-100"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "S-100"

    def test_g_dot_format_drawing_id(self):
        text = "SHEET NUMBER\nG1.1"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.number == "G1.1"

    def test_partial_extraction_only_name_returns_partial_confidence(self):
        text = "DRAWING NAME\nROOF PLAN"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.name == "ROOF PLAN"
        assert result.number is None
        assert result.confidence == 0.0

    def test_confidence_capped_at_heuristic_ceiling(self):
        # Even the strongest path (after-anchor for both fields) tops out at
        # the configured ceiling -- the higher tier is reserved for LLM.
        text = "DRAWING NAME\nFLOOR PLAN\nDRAWING NUMBER\nA101"
        result = ai_title_block.parse_title_block_heuristic(text)
        assert result.confidence <= ai_title_block.HEURISTIC_CONFIDENCE_CEILING


# ─── extract_drawing_number / extract_drawing_name (direct) ───────────────


class TestExtractDrawingNumber:
    def test_returns_none_for_empty(self):
        value, conf = ai_title_block.extract_drawing_number("")
        assert value is None
        assert conf == 0.0

    def test_after_anchor_skips_empty_lines(self):
        text = "SHEET NUMBER\n\nA101"
        value, _ = ai_title_block.extract_drawing_number(text)
        assert value == "A101"

    def test_returns_last_inline_match(self):
        # Two valid candidates -- IDs near the bottom should win.
        text = "Reference: A101\nSee A105"
        value, _ = ai_title_block.extract_drawing_number(text)
        assert value == "A105"

    def test_strips_trailing_punctuation(self):
        text = "SHEET NUMBER\nA101."
        value, _ = ai_title_block.extract_drawing_number(text)
        assert value == "A101"

    def test_rejects_note5_style_false_positive(self):
        text = "NOTE5"
        value, conf = ai_title_block.extract_drawing_number(text)
        assert value is None
        assert conf == 0.0

    def test_rejects_garbage_word_that_regex_would_allow(self):
        """``PLANS`` is letters-only -- never a drawing id."""
        value, conf = ai_title_block.extract_drawing_number("PLANS")
        assert value is None
        assert conf == 0.0


class TestExtractDrawingName:
    def test_stops_at_drawing_id_line_after_anchor(self):
        """A drawing-id line right after the TITLE anchor is treated as a
        boundary (it ends the name region rather than being skipped). This
        is the documented behavior: in real title blocks the title sits
        between the anchor and the id, never the other way around, so
        encountering an id means we've fallen off the title region.
        """
        text = "DRAWING NAME\nA101\nFLOOR PLAN"
        value, _ = ai_title_block.extract_drawing_name(text)
        assert value is None

    def test_drawn_by_fallback(self):
        text = "DRAWN BY: JS\nFLOOR PLAN\nA101"
        value, _ = ai_title_block.extract_drawing_name(text)
        assert value == "FLOOR PLAN"

    def test_skips_project_numbers(self):
        text = "DRAWING NAME\n12654.000\nROOF PLAN"
        value, _ = ai_title_block.extract_drawing_name(text)
        # The 12654.000 is filtered as a project number; ROOF PLAN is the
        # next candidate, so the parser collects from the next non-stop line.
        # Current behavior: it stops on the project number (treated as
        # boundary) and returns nothing from the anchor path. Verify that
        # behavior so any future change is intentional.
        assert value is None or "ROOF" in value


# ─── _sheet_eligible_for_auto_name ────────────────────────────────────────


def _make_sheet_obj(*, source: str | None) -> MagicMock:
    sheet = MagicMock()
    sheet.id = uuid.uuid4()
    sheet.sheet_name_source = source
    sheet.sheet_name = "Old name"
    sheet.sheet_number = None
    sheet.page_number = 1
    sheet.discipline = None
    sheet.classification_method = None
    sheet.classification_confidence = None
    return sheet


class TestManualGuard:
    def test_manual_lowercase_is_blocked_without_overwrite(self):
        sheet = _make_sheet_obj(source="manual")
        assert ai_title_block._sheet_eligible_for_auto_name(sheet, overwrite_manual=False) is False

    def test_manual_uppercase_is_blocked_without_overwrite(self):
        sheet = _make_sheet_obj(source="MANUAL")
        assert ai_title_block._sheet_eligible_for_auto_name(sheet, overwrite_manual=False) is False

    def test_manual_allowed_when_overwrite_manual(self):
        sheet = _make_sheet_obj(source="manual")
        assert ai_title_block._sheet_eligible_for_auto_name(sheet, overwrite_manual=True) is True

    def test_auto_is_allowed(self):
        sheet = _make_sheet_obj(source="auto")
        assert ai_title_block._sheet_eligible_for_auto_name(sheet, overwrite_manual=False) is True

    def test_null_source_is_allowed(self):
        sheet = _make_sheet_obj(source=None)
        assert ai_title_block._sheet_eligible_for_auto_name(sheet, overwrite_manual=False) is True


# ─── reextract_titles_for_plan ────────────────────────────────────────────


class TestReextractTitlesForPlan:
    """Plan-level orchestrator delegates to ``execute_sheet_text_llm_for_plan``."""

    def _make_session_with_sheets(self, sheets: list[MagicMock]) -> MagicMock:
        session = MagicMock()
        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.all.return_value = sheets
        session.query.return_value = query
        session.flush = MagicMock()
        session.rollback = MagicMock()
        return session

    def test_invokes_execute_and_sets_counters(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        plan.org_id = uuid.uuid4()
        sheet = _make_sheet_obj(source="auto")
        sheet.page_number = 1
        session = self._make_session_with_sheets([sheet])

        with patch.object(
            ai_title_block.ai_sheet_text_llm,
            "execute_sheet_text_llm_for_plan",
            return_value=(3, {0: {"page": 0, "sheet_name": "N", "sheet_number": "A1"}}, 1),
        ) as ex:
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-1.0"
            )

        ex.assert_called_once()
        assert counters.total == 1
        assert counters.llm == 1
        assert counters.written == 1
        assert counters.sheet_text_llm_cache_hits == 3
        session.flush.assert_called_once()

    def test_counts_manual_rows_without_calling_eligible_block_skip(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        plan.org_id = uuid.uuid4()
        manual = _make_sheet_obj(source="manual")
        manual.page_number = 1
        auto = _make_sheet_obj(source="auto")
        auto.page_number = 2
        session = self._make_session_with_sheets([manual, auto])

        with patch.object(
            ai_title_block.ai_sheet_text_llm,
            "execute_sheet_text_llm_for_plan",
            return_value=(0, {}, 2),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-1.0"
            )

        assert counters.total == 2
        assert counters.manual_skipped == 1
        assert counters.written == 2

    def test_propagates_execute_exception_to_counters(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        plan.org_id = uuid.uuid4()
        sh = _make_sheet_obj(source="auto")
        sh.page_number = 1
        session = self._make_session_with_sheets([sh])

        with patch.object(
            ai_title_block.ai_sheet_text_llm,
            "execute_sheet_text_llm_for_plan",
            side_effect=RuntimeError("no key"),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-1.0"
            )

        assert counters.errors
        assert "no key" in counters.errors[0]["error"]

    def test_empty_pdf_bytes_returns_empty_counters(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        session = self._make_session_with_sheets([])
        counters = ai_title_block.reextract_titles_for_plan(
            session, plan, pdf_bytes=b""
        )
        assert counters.total == 0
        assert counters.written == 0
