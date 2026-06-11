"""Legend symbol detector (Sprint AI-03).

Verified on synthetic word + rect arrays so we don't depend on a real PDF.
LLM cleanup is disabled by default in tests to avoid OpenAI calls.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services import ai_legend_detector as ld


@pytest.fixture(autouse=True)
def _disable_legend_cleanup_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_LEGEND_CLEANUP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeLegendPage:
    """Minimal stand-in for ``pdfplumber.Page``: ``rects`` + ``extract_words``."""

    def __init__(self, rects, words):
        self._rects = rects
        self._words = words

    @property
    def rects(self):
        return self._rects

    def extract_words(self):
        return self._words


def _rect(x0, top, w, h):
    return {
        "x0": x0,
        "x1": x0 + w,
        "top": top,
        "bottom": top + h,
        "width": w,
        "height": h,
    }


def _word(x0, top, text, w=40, h=10):
    return {
        "x0": x0,
        "x1": x0 + w,
        "top": top,
        "bottom": top + h,
        "text": text,
    }


def test_detects_aligned_column_with_right_labels():
    """Three same-size rects in a vertical column with right-adjacent labels."""
    rects = [
        _rect(100, 100, 20, 20),
        _rect(100, 140, 20, 20),
        _rect(100, 180, 20, 20),
    ]
    words = [
        _word(130, 105, "PUMP"),
        _word(130, 145, "VALVE"),
        _word(130, 185, "TANK"),
    ]
    page = _FakeLegendPage(rects, words)
    candidates = ld.detect_legend_symbols(plumber_page=page)
    labels = {c.label for c in candidates}
    assert labels == {"PUMP", "VALVE", "TANK"}
    for c in candidates:
        assert c.sibling_count == 1
        assert c.confidence == 1.0
        assert c.extraction_method == "pdfplumber_legends_proto"


def test_detects_legend_when_label_repeats_across_aligned_rects():
    """Rects sharing the same label merge into one candidate (prototype behaviour)."""
    rects = [
        _rect(100, 100, 20, 20),
        _rect(100, 140, 20, 20),
        _rect(100, 180, 20, 20),
    ]
    words = [
        _word(130, 105, "AC-1"),
        _word(130, 145, "AC-1"),
        _word(130, 185, "AC-1"),
    ]
    page = _FakeLegendPage(rects, words)
    candidates = ld.detect_legend_symbols(plumber_page=page)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.label == "AC-1"
    assert candidate.sibling_count == 3
    assert candidate.bbox_pdf["x0"] == 100
    assert candidate.bbox_pdf["y0"] == 100
    assert candidate.bbox_pdf["y1"] == 200
    assert candidate.confidence == 1.0


def test_rect_with_text_inside_is_skipped():
    """Rects containing text are table cells, not legend symbols."""
    rects = [
        _rect(100, 100, 50, 30),
        _rect(100, 140, 50, 30),
    ]
    words = [
        _word(110, 105, "INSIDE"),
        _word(160, 145, "OUTSIDE"),
    ]
    page = _FakeLegendPage(rects, words)
    candidates = ld.detect_legend_symbols(plumber_page=page)
    labels = {c.label for c in candidates}
    assert labels == {"OUTSIDE"}


def test_size_filter_rejects_tiny_rects():
    rects = [
        _rect(100, 100, 4, 4),
        _rect(100, 140, 4, 4),
    ]
    words = [
        _word(130, 105, "X"),
        _word(130, 145, "X"),
    ]
    page = _FakeLegendPage(rects, words)
    candidates = ld.detect_legend_symbols(plumber_page=page)
    assert candidates == []


def test_serialize_round_trip():
    candidate = ld.LegendCandidate(
        bbox_pdf={"x0": 1, "y0": 2, "x1": 3, "y1": 4},
        label="AC-1",
        extraction_method="pdfplumber_legends_proto",
        confidence=1.0,
        sibling_count=3,
    )
    serialized = ld.serialize_candidates([candidate])
    deserialized = ld.deserialize_candidates(serialized)
    assert len(deserialized) == 1
    assert deserialized[0].label == "AC-1"
    assert deserialized[0].sibling_count == 3
    assert deserialized[0].confidence == 1.0
