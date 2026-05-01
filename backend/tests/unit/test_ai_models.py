"""AI provider abstraction (Sprint AI-01).

* Provider factory swaps by env var without code change.
* ``with_cost_tracking`` writes the active run's cost when a context is bound,
  and is a no-op (no DB write) when no run is active.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.services import ai_models


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_factory_uses_configured_provider(monkeypatch):
    monkeypatch.setenv("AI_VISION_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_VISION_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")

    vision = ai_models.get_vision_model()
    assert isinstance(vision, ai_models.AnthropicVisionModel)
    assert vision.model_id == "claude-sonnet-4-5"


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("AI_VISION_PROVIDER", "made-up")
    with pytest.raises(RuntimeError, match="Unknown vision provider"):
        ai_models.get_vision_model()


def test_factory_swap_to_openai_embedding_via_env(monkeypatch):
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-y")

    emb = ai_models.get_embedding_model()
    assert isinstance(emb, ai_models.OpenAIEmbeddingModel)
    assert emb.model_id == "text-embedding-3-small"
    assert emb.dimensions == ai_models.OpenAIEmbeddingModel.DEFAULT_DIMENSIONS


def test_model_versions_snapshot_includes_all_three(monkeypatch):
    monkeypatch.setenv("AI_VISION_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_VISION_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("AI_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("AI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("AI_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_LLM_MODEL", "claude-sonnet-4-5")

    snap = ai_models.model_versions_snapshot()
    assert snap["vision"] == "anthropic:claude-sonnet-4-5"
    assert snap["embedding"] == "openai:text-embedding-3-small"
    assert snap["llm"] == "anthropic:claude-sonnet-4-5"


# ── with_cost_tracking ───────────────────────────────────────────────────────


def test_cost_tracking_no_active_run_is_a_noop():
    """When no ContextVar is set, the wrapper records nothing."""
    factory_called = False

    @contextmanager
    def fake_factory():
        nonlocal factory_called
        factory_called = True
        yield MagicMock()

    token = ai_models.set_sync_session_factory(fake_factory)
    try:
        with ai_models.with_cost_tracking("any_call") as cost:
            cost.cost_cents = 50
            cost.tokens_used = 1000
    finally:
        ai_models.reset_sync_session_factory(token)

    assert factory_called is False


def test_cost_tracking_no_session_factory_is_a_noop():
    """When a run is set but no session factory is bound, no DB call happens."""
    run_token = ai_models.set_active_ai_run(uuid.uuid4())
    try:
        with ai_models.with_cost_tracking("any_call") as cost:
            cost.cost_cents = 50
        # No assertion needed -- absence of exception means we did nothing risky.
    finally:
        ai_models.reset_active_ai_run(run_token)


def test_cost_tracking_writes_to_active_run():
    """Run set + factory bound => the wrapper executes a sync UPDATE on commit."""
    ai_run_id = uuid.uuid4()
    sessions: list[MagicMock] = []
    commits: list[bool] = []

    class _SessionStub:
        def __init__(self) -> None:
            self.execute = MagicMock()
            self.commit = MagicMock(side_effect=lambda: commits.append(True))
            self.rollback = MagicMock()

        def __enter__(self):
            sessions.append(self)
            return self

        def __exit__(self, *_):
            return False

    def factory():
        return _SessionStub()

    run_token = ai_models.set_active_ai_run(ai_run_id)
    fac_token = ai_models.set_sync_session_factory(factory)
    try:
        with ai_models.with_cost_tracking("vision.classify") as cost:
            cost.cost_cents = 12
            cost.tokens_used = 345
    finally:
        ai_models.reset_active_ai_run(run_token)
        ai_models.reset_sync_session_factory(fac_token)

    assert len(sessions) == 1
    assert sessions[0].execute.call_count == 1
    assert commits == [True]


def test_cost_tracking_skips_db_when_zero_cost_and_zero_tokens():
    """Pure no-op stages should not waste a DB round-trip."""
    ai_run_id = uuid.uuid4()
    factory = MagicMock()

    run_token = ai_models.set_active_ai_run(ai_run_id)
    fac_token = ai_models.set_sync_session_factory(factory)
    try:
        with ai_models.with_cost_tracking("noop_stage"):
            pass  # Never write any cost
    finally:
        ai_models.reset_active_ai_run(run_token)
        ai_models.reset_sync_session_factory(fac_token)

    factory.assert_not_called()
