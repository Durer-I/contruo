"""Unit tests for batched sheet-text OpenAI classification helpers."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services import ai_sheet_text_llm as st


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_extract_structured_text_skips_non_text_blocks():
    page = MagicMock()
    page.get_text.return_value = {
        "blocks": [
            {"type": 1},  # skipped
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {"text": "  Hello "},
                            {"text": "World"},
                        ]
                    },
                    {"spans": [{"text": ""}]},
                ],
            },
        ]
    }
    assert st.extract_structured_text(page) == "Hello  World"


def test_coerce_sheet_type_maps_notes_and_unknown():
    assert st.coerce_sheet_type("notes") == "legend"
    assert st.coerce_sheet_type("unknown") == "other"
    assert st.coerce_sheet_type("plan") == "plan"


def test_run_sheet_text_llm_batches_two_batches_for_eleven_pages(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    pages = {i: f"t{i}" for i in range(11)}
    responses = []

    def fake_create(**kwargs):
        m = MagicMock()
        user = kwargs["input"][1]["content"]
        out = []
        for segment in user.split("--- PAGE ")[1:]:
            idx_str = segment.split(" ---", 1)[0].strip()
            p = int(idx_str)
            out.append(
                {
                    "page": p,
                    "confidence": 1.0,
                    "sheet_type": "plan",
                    "category": "takeoff_required",
                }
            )
        m.output_text = json.dumps(out)
        u = MagicMock()
        u.input_tokens = 10
        u.output_tokens = 5
        m.usage = u
        responses.append(m)
        return m

    with patch("openai.OpenAI") as oc:
        oc.return_value.responses.create.side_effect = fake_create
        out = st.run_sheet_text_llm_batches(page_texts=pages, batch_size=10)

    assert len(responses) == 2
    assert len(out) == 11


def test_run_sheet_text_llm_duplicate_hash_skips_second_api_row(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    calls = []

    def fake_create(**kwargs):
        calls.append(1)
        m = MagicMock()
        m.output_text = json.dumps(
            [{"page": 0, "confidence": 1.0, "sheet_type": "plan", "category": "reference_only"}]
        )
        u = MagicMock()
        u.input_tokens = 1
        u.output_tokens = 1
        m.usage = u
        return m

    same = "identical text body"
    pages = {0: same, 1: same}

    with patch("openai.OpenAI") as oc:
        oc.return_value.responses.create.side_effect = fake_create
        out = st.run_sheet_text_llm_batches(page_texts=pages, batch_size=1)

    assert calls == [1]
    assert out[0]["page"] == 0
    assert out[1]["page"] == 1


def test_run_sheet_text_llm_batches_full_doc_only_needing_pages_call_api(monkeypatch):
    """Batches walk 0..N-1; only pages in ``pages_needing_llm`` are sent to the API."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    full = {i: f"t{i}" for i in range(12)}
    responses = []

    def fake_create(**kwargs):
        m = MagicMock()
        user = kwargs["input"][1]["content"]
        out = []
        for segment in user.split("--- PAGE ")[1:]:
            idx_str = segment.split(" ---", 1)[0].strip()
            p = int(idx_str)
            out.append(
                {
                    "page": p,
                    "confidence": 1.0,
                    "sheet_type": "plan",
                    "category": "takeoff_required",
                }
            )
        m.output_text = json.dumps(out)
        u = MagicMock()
        u.input_tokens = 10
        u.output_tokens = 5
        m.usage = u
        responses.append(m)
        return m

    with patch("openai.OpenAI") as oc:
        oc.return_value.responses.create.side_effect = fake_create
        out = st.run_sheet_text_llm_batches(
            page_texts=full,
            batch_size=10,
            pages_needing_llm={10, 11},
        )

    assert len(responses) == 1
    assert len(out) == 2
    assert set(out.keys()) == {10, 11}


def test_build_upsert_rows_fallback_when_no_llm_item():
    sid = uuid.uuid4()
    sheet = MagicMock()
    sheet.id = sid
    sheet.page_number = 1
    rows = st.build_upsert_rows_for_sheets(
        [sheet],
        llm_by_page={},
        sheet_eligible_for_names={sid: True},
    )
    assert len(rows) == 1
    assert rows[0].discipline == "other"
    assert rows[0].patch_names is False
