"""Sprint AI-02b: ``ai_pipeline.reextract_plan_titles_task`` Celery task.

Boundary-mocked tests:

* ``SyncSession`` factory returns a fake session whose ``.get(Plan, id)``
  yields a hand-built plan object.
* ``ai_run_service.acquire_sheet_lock_sync`` / ``release_sheet_lock_sync``
  are stubbed.
* ``storage.download_bytes`` returns a tiny fake byte string.
* ``ai_title_block.reextract_titles_for_plan`` is patched -- the orchestrator
  itself has its own tests.
* ``liveblocks_service.broadcast_event_sync`` is patched.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services.ai_title_block import ReextractCounters
from app.tasks import ai_pipeline


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSession:
    def __init__(self, plan: MagicMock) -> None:
        self._plan = plan
        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.execute = MagicMock()

    def get(self, _model, _ident):
        return self._plan

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _make_plan(*, status: str = "ready") -> MagicMock:
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.project_id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.status = status
    plan.storage_path = "plans/test.pdf"
    return plan


def test_task_acquires_lock_runs_orchestrator_releases_lock_and_broadcasts():
    plan = _make_plan(status="ready")
    counters = ReextractCounters(total=3, written=2, text_layer=2, manual_skipped=1)

    with (
        patch.object(ai_pipeline, "SyncSession", lambda: _FakeSession(plan)),
        patch.object(
            ai_pipeline.ai_run_service,
            "acquire_sheet_lock_sync",
            return_value=True,
        ) as acquire,
        patch.object(ai_pipeline.ai_run_service, "release_sheet_lock_sync") as release,
        patch.object(
            ai_pipeline.storage,
            "download_bytes",
            return_value=b"%PDF-fake-bytes",
        ),
        patch.object(
            ai_pipeline.ai_title_block,
            "reextract_titles_for_plan",
            return_value=counters,
        ) as orchestrator,
        patch.object(
            ai_pipeline.liveblocks_service,
            "broadcast_event_sync",
            return_value=True,
        ) as bx,
    ):
        result = ai_pipeline.reextract_plan_titles_task.run(str(plan.id))

    assert result["plan_id"] == str(plan.id)
    assert result["counters"]["written"] == 2
    assert result["counters"]["manual_skipped"] == 1
    acquire.assert_called_once()
    orchestrator.assert_called_once()
    assert orchestrator.call_args.kwargs.get("overwrite_manual") is False
    # Lock released even on success.
    assert release.call_count >= 1
    # Broadcast emitted the right event_type into the project room.
    bx.assert_called_once()
    assert bx.call_args.kwargs["event_type"] == "sheets.auto_named"
    assert bx.call_args.kwargs["data"]["plan_id"] == str(plan.id)


def test_task_skips_when_feature_flag_disabled(monkeypatch):
    monkeypatch.setenv("AI_AUTO_NAME_ENABLED", "false")
    get_settings.cache_clear()

    plan = _make_plan(status="ready")
    with (
        patch.object(ai_pipeline, "SyncSession", lambda: _FakeSession(plan)),
        patch.object(ai_pipeline.ai_run_service, "acquire_sheet_lock_sync") as acquire,
        patch.object(
            ai_pipeline.ai_title_block, "reextract_titles_for_plan"
        ) as orchestrator,
    ):
        result = ai_pipeline.reextract_plan_titles_task.run(str(plan.id))

    assert result == {"plan_id": str(plan.id), "skipped": "feature_disabled"}
    acquire.assert_not_called()
    orchestrator.assert_not_called()


def test_task_skips_when_plan_not_ready():
    plan = _make_plan(status="processing")
    with (
        patch.object(ai_pipeline, "SyncSession", lambda: _FakeSession(plan)),
        patch.object(ai_pipeline.ai_run_service, "acquire_sheet_lock_sync") as acquire,
        patch.object(
            ai_pipeline.ai_title_block, "reextract_titles_for_plan"
        ) as orchestrator,
    ):
        result = ai_pipeline.reextract_plan_titles_task.run(str(plan.id))

    assert result == {"plan_id": str(plan.id), "skipped": "plan_not_ready"}
    acquire.assert_not_called()
    orchestrator.assert_not_called()


def test_task_releases_lock_on_orchestrator_failure():
    """An exception inside ``reextract_titles_for_plan`` MUST still release
    the per-plan advisory lock -- otherwise the next click hangs.
    """
    plan = _make_plan(status="ready")

    with (
        patch.object(ai_pipeline, "SyncSession", lambda: _FakeSession(plan)),
        patch.object(
            ai_pipeline.ai_run_service,
            "acquire_sheet_lock_sync",
            return_value=True,
        ),
        patch.object(ai_pipeline.ai_run_service, "release_sheet_lock_sync") as release,
        patch.object(
            ai_pipeline.storage, "download_bytes", return_value=b"%PDF-fake-bytes"
        ),
        patch.object(
            ai_pipeline.ai_title_block,
            "reextract_titles_for_plan",
            side_effect=RuntimeError("boom"),
        ),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            ai_pipeline.reextract_plan_titles_task.run(str(plan.id))

    # Released by the inner finally block AND defensively in the outer
    # except branch -- at least once is the contract.
    assert release.call_count >= 1


def test_task_passes_overwrite_manual_to_orchestrator():
    plan = _make_plan(status="ready")
    counters = ReextractCounters(total=2, written=2, text_layer=2, manual_skipped=0)

    with (
        patch.object(ai_pipeline, "SyncSession", lambda: _FakeSession(plan)),
        patch.object(
            ai_pipeline.ai_run_service,
            "acquire_sheet_lock_sync",
            return_value=True,
        ),
        patch.object(ai_pipeline.ai_run_service, "release_sheet_lock_sync"),
        patch.object(
            ai_pipeline.storage,
            "download_bytes",
            return_value=b"%PDF-fake-bytes",
        ),
        patch.object(
            ai_pipeline.ai_title_block,
            "reextract_titles_for_plan",
            return_value=counters,
        ) as orchestrator,
        patch.object(
            ai_pipeline.liveblocks_service,
            "broadcast_event_sync",
            return_value=True,
        ),
    ):
        ai_pipeline.reextract_plan_titles_task.run(str(plan.id), overwrite_manual=True)

    assert orchestrator.call_args.kwargs.get("overwrite_manual") is True
