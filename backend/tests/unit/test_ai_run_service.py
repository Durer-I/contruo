"""AI run service (Sprint AI-01).

Covers the business logic that the API and Celery worker share:

* Lock acquisition is idempotent and reflects ``pg_try_advisory_lock``.
* The circuit breaker raises a 429 ``AI_COST_LIMIT`` over the configured cap.
* Concurrent-run guard raises a 409 ``AI_RUN_LOCKED``.
* ``record_stage_timing_sync`` rejects unknown stage names.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import get_settings
from app.middleware.error_handler import AppException, ConflictException
from app.services import ai_run_service


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Circuit breaker ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_circuit_breaker_passes_under_cap(monkeypatch):
    monkeypatch.setenv("AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG", "5000")
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = 1234
    db.execute.return_value = result

    await ai_run_service.check_circuit_breaker(db, uuid.uuid4())  # no raise


@pytest.mark.anyio
async def test_circuit_breaker_trips_at_cap(monkeypatch):
    monkeypatch.setenv("AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG", "5000")
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = 5000  # exactly at cap
    db.execute.return_value = result

    with pytest.raises(AppException) as ei:
        await ai_run_service.check_circuit_breaker(db, uuid.uuid4())
    assert ei.value.code == "AI_COST_LIMIT"
    assert ei.value.status_code == 429


@pytest.mark.anyio
async def test_circuit_breaker_disabled_when_cap_is_zero(monkeypatch):
    monkeypatch.setenv("AI_DAILY_COST_CIRCUIT_BREAKER_CENTS_PER_ORG", "0")
    db = AsyncMock()  # No execute call is expected; configure to fail loudly.
    db.execute.side_effect = AssertionError("DB must not be queried when cap=0")

    await ai_run_service.check_circuit_breaker(db, uuid.uuid4())


# ── Concurrent run guard ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_concurrent_run_guard_rejects_when_active_exists():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    db.execute.return_value = result

    with pytest.raises(ConflictException) as ei:
        await ai_run_service.assert_no_active_run_for_plan(
            db, uuid.uuid4(), uuid.uuid4()
        )
    assert ei.value.code == "AI_RUN_LOCKED"
    assert ei.value.status_code == 409


@pytest.mark.anyio
async def test_concurrent_run_guard_passes_when_no_active_run():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    # Should not raise.
    await ai_run_service.assert_no_active_run_for_plan(
        db, uuid.uuid4(), uuid.uuid4()
    )


# ── Stage timing validation ──────────────────────────────────────────────────


def test_record_stage_timing_rejects_unknown_stage():
    """Defensive: stage names are interpolated into a JSON path and must be safe."""
    session = MagicMock()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="Unknown pipeline stage"):
        ai_run_service.record_stage_timing_sync(
            session,
            ai_run_id=uuid.uuid4(),
            stage="; DROP TABLE ai_runs;--",
            duration_ms=10,
            cache_hit=False,
            started_at=now,
            finished_at=now,
        )


def test_record_stage_timing_accepts_canonical_stage():
    session = MagicMock()
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    ai_run_service.record_stage_timing_sync(
        session,
        ai_run_id=uuid.uuid4(),
        stage="classification",
        duration_ms=10,
        cache_hit=False,
        started_at=now,
        finished_at=now,
    )
    assert session.execute.call_count == 1
    assert session.commit.call_count == 1


# ── Advisory lock key stability ──────────────────────────────────────────────


def test_advisory_lock_key_is_deterministic():
    plan = uuid.uuid4()
    a = ai_run_service._advisory_lock_key(plan, None)
    b = ai_run_service._advisory_lock_key(plan, None)
    assert a == b
    assert isinstance(a, int)
    # 64-bit signed range (Postgres bigint).
    assert -(2**63) <= a < 2**63


def test_advisory_lock_key_differs_per_sheet():
    plan = uuid.uuid4()
    plan_lock = ai_run_service._advisory_lock_key(plan, None)
    sheet_lock = ai_run_service._advisory_lock_key(plan, uuid.uuid4())
    assert plan_lock != sheet_lock


def test_acquire_lock_returns_true_when_pg_returns_true():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = True
    session.execute.return_value = result

    got = ai_run_service.acquire_sheet_lock_sync(
        session, plan_id=uuid.uuid4(), sheet_id=None
    )
    assert got is True


def test_acquire_lock_returns_false_when_pg_returns_false():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = False
    session.execute.return_value = result

    got = ai_run_service.acquire_sheet_lock_sync(
        session, plan_id=uuid.uuid4(), sheet_id=None
    )
    assert got is False
