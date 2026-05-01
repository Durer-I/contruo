"""AI pipeline tasks (Sprint AI-01).

The Celery tasks are exercised by calling the run helpers directly with a
fake sync session (mock-at-the-boundary). We verify:

* ``_run_stage`` writes a per-stage timing entry on success and broadcasts
  ``ai_run.status_changed``.
* On stage exception, the run transitions to ``failed``, the lock is released,
  and the failure is broadcast.
* The Celery chain is ordered correctly (stage tasks between start and
  finalize).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.tasks import ai_pipeline


class _FakeSession:
    """Stand-in for a sync SQLAlchemy session."""

    def __init__(self) -> None:
        self.execute = MagicMock()
        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.refresh = MagicMock()
        self._objects: dict = {}
        self.add = MagicMock(side_effect=self._add)
        self.get = MagicMock(side_effect=self._get)

    def _add(self, obj):
        self._objects[id(obj)] = obj

    def _get(self, model, ident):
        # Tests inject the run and plan via class-level attribute.
        return self._registry.get((model.__name__, ident))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _make_run(*, plan_id: uuid.UUID, status: str = "running") -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.org_id = uuid.uuid4()
    run.project_id = uuid.uuid4()
    run.plan_id = plan_id
    run.status = status
    return run


def _make_plan(plan_id: uuid.UUID) -> MagicMock:
    plan = MagicMock()
    plan.id = plan_id
    return plan


@contextmanager
def _patched_session(run, plan):
    """Provide a SyncSession factory whose .get() returns our fake run/plan."""
    factory_calls: list[_FakeSession] = []
    registry = {("AiRun", run.id): run, ("Plan", plan.id): plan}

    def factory():
        s = _FakeSession()
        s._registry = registry  # type: ignore[attr-defined]
        factory_calls.append(s)
        return s

    with patch.object(ai_pipeline, "SyncSession", factory):
        yield factory_calls


# ── Successful stage ────────────────────────────────────────────────────────


def test_run_stage_writes_timing_and_broadcasts_on_success():
    plan = _make_plan(uuid.uuid4())
    run = _make_run(plan_id=plan.id, status="running")
    body_calls: list[tuple] = []

    def _body(session, ai_run, plan_arg):
        body_calls.append((session, ai_run, plan_arg))
        return {"cache_hit": False}

    with (
        _patched_session(run, plan) as sessions,
        patch.object(ai_pipeline.ai_run_service, "record_stage_timing_sync") as record_timing,
        patch.object(ai_pipeline.liveblocks_service, "broadcast_event_sync", return_value=True) as bx,
    ):
        result = ai_pipeline._run_stage(
            ai_run_id_str=str(run.id), stage="classification", body=_body
        )

    assert result == str(run.id)
    assert len(body_calls) == 1
    record_timing.assert_called_once()
    kwargs = record_timing.call_args.kwargs
    assert kwargs["stage"] == "classification"
    assert kwargs["cache_hit"] is False
    assert isinstance(kwargs["duration_ms"], int)
    bx.assert_called_once()
    assert bx.call_args.kwargs["event_type"] == "ai_run.status_changed"
    assert bx.call_args.kwargs["data"]["status"] == "running"
    assert bx.call_args.kwargs["data"]["stage"] == "classification"
    assert bx.call_args.kwargs["data"]["stage_index"] == 1
    # Sessions should have been opened more than once (load context, record timing, fetch org/project).
    assert len(sessions) >= 2


def test_run_stage_short_circuits_when_run_already_terminal():
    plan = _make_plan(uuid.uuid4())
    run = _make_run(plan_id=plan.id, status="completed")
    body_calls: list[tuple] = []

    def _body(session, ai_run, plan_arg):
        body_calls.append((session, ai_run, plan_arg))
        return None

    with (
        _patched_session(run, plan),
        patch.object(ai_pipeline.ai_run_service, "record_stage_timing_sync") as record_timing,
    ):
        ai_pipeline._run_stage(
            ai_run_id_str=str(run.id), stage="classification", body=_body
        )

    assert body_calls == []
    record_timing.assert_not_called()


# ── Failure path ────────────────────────────────────────────────────────────


def test_run_stage_failure_marks_failed_releases_lock_and_broadcasts():
    plan = _make_plan(uuid.uuid4())
    run = _make_run(plan_id=plan.id, status="running")

    def _body(_session, _run, _plan):
        raise RuntimeError("boom")

    with (
        _patched_session(run, plan),
        patch.object(ai_pipeline.ai_run_service, "record_stage_timing_sync") as record_timing,
        patch.object(ai_pipeline.ai_run_service, "release_sheet_lock_sync") as release,
        patch.object(ai_pipeline.ai_run_service, "finalize_run_sync") as finalize,
        patch.object(ai_pipeline.liveblocks_service, "broadcast_event_sync") as bx,
        patch.object(ai_pipeline.ai_run_service, "_advisory_lock_key", return_value=42),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            ai_pipeline._run_stage(
                ai_run_id_str=str(run.id),
                stage="element_detection",
                body=_body,
            )

    # The error path records a failure timing, releases the lock, finalizes failed, and broadcasts.
    assert record_timing.call_count == 1
    assert record_timing.call_args.kwargs["error"] == "boom"
    release.assert_called_once()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert "element_detection" in finalize.call_args.kwargs["error_message"]
    bx.assert_called_once()
    assert bx.call_args.kwargs["data"]["status"] == "failed"


# ── Chain shape ──────────────────────────────────────────────────────────────


def test_pipeline_chain_stages_in_order():
    chain = ai_pipeline.build_pipeline_chain(uuid.uuid4(), uuid.uuid4())
    # Celery's chain stores its tasks on .tasks. Prep -> start -> stages -> finalize.
    task_names = [t.name for t in chain.tasks]
    assert task_names == [
        "ai_pipeline.pipeline_prep_auto_name",
        "ai_pipeline.start_ai_run",
        "ai_pipeline.stage_classification",
        "ai_pipeline.stage_schedules_legends",
        "ai_pipeline.stage_element_detection",
        "ai_pipeline.stage_resolver_and_layer_write",
        "ai_pipeline.finalize_ai_run",
    ]
    assert chain.tasks[1].immutable is True


def test_pipeline_stages_constant_matches_chain_order():
    """``PIPELINE_STAGES`` is the canonical list; the chain must respect it."""
    expected_run_stages = (
        "classification",
        "schedules_legends",
        "element_detection",
        "resolver_and_layer_write",
        "finalize",
    )
    assert ai_pipeline.PIPELINE_STAGES == expected_run_stages
    assert ai_pipeline.TOTAL_STAGES == 5
