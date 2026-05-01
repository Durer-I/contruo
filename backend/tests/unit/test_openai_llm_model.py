"""Sprint AI-02b: ``OpenAILLMModel.structured_output`` + factory wiring.

We don't hit the real OpenAI API in unit tests. The strategy is:

* Patch ``openai.OpenAI`` (after a first call brings the symbol into the
  module's lazy import) and return a stub client whose
  ``chat.completions.create`` returns a hand-crafted response object.
* Assert the model parses the JSON content, surfaces the right cost via the
  ``with_cost_tracking`` context, and bubbles up structured failures cleanly.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services import ai_models


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _build_chat_response(content: str, *, in_tokens: int = 100, out_tokens: int = 30):
    """Construct a minimally-complete OpenAI-shaped response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=in_tokens, completion_tokens=out_tokens)
    return response


# ─── structured_output ────────────────────────────────────────────────────


def test_structured_output_parses_valid_json():
    expected = {"drawing_name": "FLOOR PLAN", "drawing_number": "A101"}
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _build_chat_response(
        json.dumps(expected)
    )

    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client", return_value=fake_client):
        result = llm.structured_output(
            "extract this", schema={"title": "test", "type": "object"}
        )

    assert result == expected
    # Sanity: temperature=0 and strict JSON schema were sent.
    call = fake_client.chat.completions.create.call_args
    assert call.kwargs["temperature"] == 0
    assert call.kwargs["response_format"]["type"] == "json_schema"
    assert call.kwargs["response_format"]["json_schema"]["strict"] is True
    assert call.kwargs["response_format"]["json_schema"]["name"] == "test"
    assert call.kwargs["model"] == "gpt-4o-mini"


def test_structured_output_strips_code_fences_if_present():
    expected = {"drawing_name": "ROOF", "drawing_number": "A102"}
    fenced = f"```json\n{json.dumps(expected)}\n```"
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _build_chat_response(fenced)

    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client", return_value=fake_client):
        result = llm.structured_output("p", schema={"title": "x", "type": "object"})
    assert result == expected


def test_structured_output_raises_on_empty_content():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _build_chat_response("")

    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client", return_value=fake_client):
        with pytest.raises(RuntimeError, match="empty message content"):
            llm.structured_output("p", schema={"title": "x", "type": "object"})


def test_structured_output_raises_on_non_json_content():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _build_chat_response(
        "I am sorry but I cannot do that"
    )

    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client", return_value=fake_client):
        with pytest.raises(RuntimeError, match="not JSON"):
            llm.structured_output("p", schema={"title": "x", "type": "object"})


def test_structured_output_propagates_create_exception():
    """Regression: ``with_cost_tracking`` must not swallow API errors before
    ``response`` is assigned (would otherwise surface as UnboundLocalError).
    """
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = ConnectionError("upstream")

    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client", return_value=fake_client):
        with pytest.raises(ConnectionError, match="upstream"):
            llm.structured_output("p", schema={"title": "x", "type": "object"})


def test_structured_output_returns_empty_dict_for_empty_prompt():
    """No API call should be made for empty input."""
    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="sk-test")
    with patch.object(llm, "_get_client") as get_client:
        result = llm.structured_output("", schema={"title": "x", "type": "object"})
    assert result == {}
    get_client.assert_not_called()


def test_structured_output_requires_api_key():
    llm = ai_models.OpenAILLMModel(model_id="gpt-4o-mini", api_key="")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        llm.structured_output("p", schema={"title": "x", "type": "object"})


# ─── Factory + provider routing ───────────────────────────────────────────


def test_get_title_block_llm_returns_openai_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    # Defaults are openai/gpt-4o-mini per app/config.py.
    llm = ai_models.get_title_block_llm()
    assert isinstance(llm, ai_models.OpenAILLMModel)
    assert llm.model_id == "gpt-4o-mini"


def test_get_title_block_llm_independent_of_global_llm_provider(monkeypatch):
    """Flipping ``ai_llm_provider`` to anthropic must NOT affect the
    title-block LLM (decoupled by design).
    """
    monkeypatch.setenv("AI_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_LLM_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    title_llm = ai_models.get_title_block_llm()
    assert isinstance(title_llm, ai_models.OpenAILLMModel)
    global_llm = ai_models.get_llm_model()
    assert isinstance(global_llm, ai_models.AnthropicLLMModel)


def test_get_title_block_llm_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_TITLE_BLOCK_LLM_PROVIDER", "made-up")
    with pytest.raises(RuntimeError, match="Unknown title_block_llm provider"):
        ai_models.get_title_block_llm()
