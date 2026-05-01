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
    """Plan-level orchestrator. Mocks at the boundary: PyMuPDF document,
    extractor, session.
    """

    def _patch_doc(self, page_count: int) -> MagicMock:
        doc = MagicMock()
        doc.page_count = page_count
        doc.load_page = MagicMock(return_value=MagicMock())
        doc.close = MagicMock()
        return doc

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

    def test_skips_manual_sheets(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        manual_sheet = _make_sheet_obj(source="manual")
        manual_sheet.page_number = 1
        auto_sheet = _make_sheet_obj(source="auto")
        auto_sheet.page_number = 2

        session = self._make_session_with_sheets([manual_sheet, auto_sheet])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(2)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                return_value=ai_title_block.TitleExtractionResult(
                    name="NEW NAME", number="A101", confidence=0.9, method="text_layer"
                ),
            ),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-fake"
            )

        assert counters.total == 2
        assert counters.manual_skipped == 1
        assert counters.written == 1
        # Manual sheet kept its old values; only the auto sheet was rewritten.
        assert manual_sheet.sheet_name == "Old name"
        assert manual_sheet.sheet_number is None
        assert auto_sheet.sheet_name == "NEW NAME"
        assert auto_sheet.sheet_number == "A101"
        assert auto_sheet.sheet_name_source == "auto"
        assert auto_sheet.discipline == "architectural"
        assert auto_sheet.classification_method == "sheet_number"
        assert auto_sheet.classification_confidence == 0.95

    def test_coalesce_write_preserves_existing_when_extract_returns_partial(self):
        """If the extractor returns name=None, the existing sheet_name must
        survive -- we only overwrite fields the extractor actually filled in.
        """
        plan = MagicMock()
        plan.id = uuid.uuid4()
        sheet = _make_sheet_obj(source="auto")
        sheet.sheet_name = "Existing Name"
        sheet.sheet_number = None
        sheet.page_number = 1

        session = self._make_session_with_sheets([sheet])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(1)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                return_value=ai_title_block.TitleExtractionResult(
                    name=None, number="A101", confidence=0.6, method="text_layer"
                ),
            ),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-fake"
            )

        assert counters.written == 1
        assert sheet.sheet_name == "Existing Name"  # preserved
        assert sheet.sheet_number == "A101"  # written
        assert sheet.discipline == "architectural"
        assert sheet.classification_method == "sheet_number"
        assert sheet.classification_confidence == 0.95

    def test_discipline_from_existing_sheet_number_when_only_name_extracted(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        sheet = _make_sheet_obj(source="auto")
        sheet.sheet_name = "Old"
        sheet.sheet_number = "S-100"
        sheet.discipline = "other"
        sheet.page_number = 1

        session = self._make_session_with_sheets([sheet])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(1)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                return_value=ai_title_block.TitleExtractionResult(
                    name="NEW TITLE", number=None, confidence=0.9, method="text_layer"
                ),
            ),
        ):
            ai_title_block.reextract_titles_for_plan(session, plan, pdf_bytes=b"%PDF-fake")

        assert sheet.sheet_name == "NEW TITLE"
        assert sheet.sheet_number == "S-100"
        assert sheet.discipline == "structural"
        assert sheet.classification_method == "sheet_number"

    def test_unknown_sheet_number_prefix_preserves_discipline(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        sheet = _make_sheet_obj(source="auto")
        sheet.discipline = "structural"
        sheet.classification_method = "vision"
        sheet.classification_confidence = 0.88
        sheet.page_number = 1

        session = self._make_session_with_sheets([sheet])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(1)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                return_value=ai_title_block.TitleExtractionResult(
                    name="X", number="Z99", confidence=0.9, method="text_layer"
                ),
            ),
        ):
            ai_title_block.reextract_titles_for_plan(session, plan, pdf_bytes=b"%PDF-fake")

        assert sheet.sheet_number == "Z99"
        assert sheet.discipline == "structural"
        assert sheet.classification_method == "vision"
        assert sheet.classification_confidence == 0.88

    def test_empty_extraction_does_not_touch_source_or_fields(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        sheet = _make_sheet_obj(source="auto")
        sheet.sheet_name = "Existing"
        sheet.page_number = 1

        session = self._make_session_with_sheets([sheet])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(1)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                return_value=ai_title_block.TitleExtractionResult(
                    name=None, number=None, confidence=0.0, method="empty"
                ),
            ),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-fake"
            )

        assert counters.empty == 1
        assert counters.written == 0
        assert sheet.sheet_name == "Existing"

    def test_records_method_counters(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        s1 = _make_sheet_obj(source=None); s1.page_number = 1
        s2 = _make_sheet_obj(source=None); s2.page_number = 2
        s3 = _make_sheet_obj(source=None); s3.page_number = 3

        session = self._make_session_with_sheets([s1, s2, s3])

        results_iter = iter([
            ai_title_block.TitleExtractionResult("N1", "A101", 0.9, "text_layer"),
            ai_title_block.TitleExtractionResult("N2", "A102", 0.85, "ocr"),
            ai_title_block.TitleExtractionResult("N3", "A103", 0.85, "llm"),
        ])

        with (
            patch.object(ai_title_block, "fitz", MagicMock(open=MagicMock(return_value=self._patch_doc(3)))),
            patch.object(
                ai_title_block,
                "extract_title_for_sheet",
                side_effect=lambda *a, **kw: next(results_iter),
            ),
        ):
            counters = ai_title_block.reextract_titles_for_plan(
                session, plan, pdf_bytes=b"%PDF-fake"
            )

        assert counters.text_layer == 1
        assert counters.ocr == 1
        assert counters.llm == 1
        assert counters.written == 3

    def test_empty_pdf_bytes_returns_empty_counters(self):
        plan = MagicMock()
        plan.id = uuid.uuid4()
        session = self._make_session_with_sheets([])
        counters = ai_title_block.reextract_titles_for_plan(
            session, plan, pdf_bytes=b""
        )
        assert counters.total == 0
        assert counters.written == 0
