"""Legend LLM cleanup (prototype GPT filter)."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.ai_legend_cleanup import filter_merged_results_with_llm
from app.services.ai_models import OpenAILLMModel


@pytest.fixture
def sample_merged() -> dict[str, dict[str, float]]:
    return {
        "PUMP": {"x0": 0.0, "x1": 10.0, "top": 0.0, "bottom": 10.0},
        "THIS IS A LONG SENTENCE THAT IS NOT A LEGEND": {
            "x0": 20.0,
            "x1": 30.0,
            "top": 0.0,
            "bottom": 10.0,
        },
    }


def test_cleanup_disabled_returns_input(
    monkeypatch: pytest.MonkeyPatch, sample_merged: dict[str, dict[str, float]]
) -> None:
    monkeypatch.setenv("AI_LEGEND_CLEANUP_ENABLED", "false")
    get_settings.cache_clear()
    out = filter_merged_results_with_llm(sample_merged)
    assert out == sample_merged
    get_settings.cache_clear()


def test_cleanup_calls_llm_and_filters(
    monkeypatch: pytest.MonkeyPatch, sample_merged: dict[str, dict[str, float]]
) -> None:
    monkeypatch.setenv("AI_LEGEND_CLEANUP_ENABLED", "true")
    get_settings.cache_clear()

    class _Fake(OpenAILLMModel):
        def __init__(self) -> None:
            self.model_id = "gpt-4o-mini"
            self._api_key = "test-key"

        def structured_output(self, prompt: str, *, schema: dict) -> dict:
            return {"keep_indices": [0]}

    out = filter_merged_results_with_llm(
        sample_merged, llm_factory=lambda: _Fake()
    )
    assert set(out.keys()) == {"PUMP"}
    get_settings.cache_clear()


def test_cleanup_failure_returns_unfiltered(
    monkeypatch: pytest.MonkeyPatch, sample_merged: dict[str, dict[str, float]]
) -> None:
    monkeypatch.setenv("AI_LEGEND_CLEANUP_ENABLED", "true")
    get_settings.cache_clear()

    class _Boom(OpenAILLMModel):
        def __init__(self) -> None:
            self.model_id = "gpt-4o-mini"
            self._api_key = "test-key"

        def structured_output(self, prompt: str, *, schema: dict) -> dict:
            raise RuntimeError("boom")

    out = filter_merged_results_with_llm(sample_merged, llm_factory=lambda: _Boom())
    assert out == sample_merged
    get_settings.cache_clear()
