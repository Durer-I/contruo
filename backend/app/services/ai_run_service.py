"""AI Auto-Takeoff run lifecycle (Sprint AI-01).

Owns:

* ``create_run`` / ``enqueue_run`` -- API entrypoint, called from FastAPI.
* ``cancel_run`` -- cooperative cancel for ``queued`` / ``running`` rows.
* ``check_circuit_breaker`` -- 24h per-org cost rollup vs the configured cap.
* ``acquire_sheet_lock`` / ``release_sheet_lock`` -- Postgres advisory locks
  keyed by sheet uuid so two estimators can't race the same plan/sheet.
* ``record_stage_timing`` -- write a per-stage entry into ``summary_jsonb``.
* ``update_status`` / ``finalize_run`` -- transitions + audit log entries.

Async functions take ``AsyncSession`` and run from FastAPI handlers. Sync
functions take ``Session`` and run from Celery worker stage tasks. Naming
prefix tells you which world you're in.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import get_settings
from app.middleware.error_handler import AppException, ConflictException, NotFoundException
from app.models.ai_run import AiRun
from app.services.ai_models import model_versions_snapshot
from app.services.event_service import log_event
from app.services import liveblocks_service

logger = logging.getLogger(__name__)


#: Pipeline stages between ``start_ai_run`` and ``finalize_ai_run``, in order.
#: Title-block extraction is not part of Auto Takeoff; use Auto-name sheets for names.
PIPELINE_STAGES: tuple[str, ...] = (
    "classification",
    "schedules_legends",
    "element_detection",
    "resolver_and_layer_write",
    "finalize",
)

#: Stage names a sheet-lock applies to (locks per (plan, sheet) for the
#: full pipeline; AI-01 acquires once at start and releases on finalize/fail).
LOCKED_STAGES: tuple[str, ...] = PIPELINE_STAGES


# ─── Async (API) ─────────────────────────────────────────────────────────────


async def check_circuit_breaker(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Reject new runs when the org's 24h spend exceeds the configured cap.

    This is *abuse* protection -- the cap is intentionally far above any
    legitimate per-org daily cost. Customer-facing usage caps do not exist;
    AI is included in the subscription.
    """
    settings = get_settings()
    cap_cents = settings.ai_daily_cost_circuit_breaker_cents_per_org
    if cap_cents <= 0:
        return  # disabled
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(func.coalesce(func.sum(AiRun.cost_cents), 0)).where(
        AiRun.org_id == org_id,
        AiRun.created_at >= since,
    )
    spent = int((await db.execute(stmt)).scalar_one() or 0)
    if spent >= cap_cents:
        logger.warning(
            "ai_circuit_breaker_tripped org_id=%s spent_cents=%s cap_cents=%s",
            org_id,
            spent,
            cap_cents,
        )
        raise AppException(
            code="AI_COST_LIMIT",
            message=(
                "AI is temporarily paused for this organization while we investigate "
                "unusual activity. Please contact support if this is unexpected."
            ),
            status_code=429,
            details={"window_hours": 24, "spent_cents": spent, "cap_cents": cap_cents},
        )


async def assert_no_active_run_for_plan(
    db: AsyncSession, org_id: uuid.UUID, plan_id: uuid.UUID
) -> None:
    """Reject a new run when one is already ``queued`` or ``running`` for this plan.

    The advisory lock in the worker handles per-sheet contention; this
    guards the API surface so the user gets a clean 409 rather than a queued
    run that later collides on the lock.
    """
    stmt = select(AiRun.id).where(
        AiRun.org_id == org_id,
        AiRun.plan_id == plan_id,
        AiRun.status.in_(("queued", "running")),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictException(
            "An AI run is already in progress for this plan.",
            code="AI_RUN_LOCKED",
            details={"existing_ai_run_id": str(existing)},
        )


async def create_run(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    triggered_by: uuid.UUID,
    scope: str = "full_plan",
) -> AiRun:
    """Create a new ``ai_runs`` row in ``queued`` state and audit-log it.

    Caller is responsible for enqueuing the Celery task after commit.
    """
    run = AiRun(
        org_id=org_id,
        project_id=project_id,
        plan_id=plan_id,
        triggered_by=triggered_by,
        status="queued",
        scope=scope,
        model_versions=model_versions_snapshot(),
        summary_jsonb={"stages": {}, "lock_state": "unlocked"},
    )
    db.add(run)
    await db.flush()
    await log_event(
        db,
        org_id=org_id,
        user_id=triggered_by,
        project_id=project_id,
        event_type="ai_run.created",
        entity_type="ai_run",
        entity_id=run.id,
        payload={"plan_id": str(plan_id), "scope": scope},
    )
    return run


async def get_run(
    db: AsyncSession, org_id: uuid.UUID, ai_run_id: uuid.UUID
) -> AiRun:
    stmt = select(AiRun).where(AiRun.id == ai_run_id, AiRun.org_id == org_id)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise NotFoundException("ai_run", str(ai_run_id))
    return run


async def list_runs(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[AiRun]:
    stmt = (
        select(AiRun)
        .where(AiRun.org_id == org_id, AiRun.project_id == project_id)
        .order_by(AiRun.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if status:
        stmt = stmt.where(AiRun.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def cancel_run(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    ai_run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AiRun:
    """Mark a ``queued`` or ``running`` run ``cancelled`` and notify Liveblocks.

    Cooperative: Celery stages short-circuit when they next read the row.
    Idempotent when the run is already ``cancelled``.
    """
    run = await get_run(db, org_id, ai_run_id)
    if run.project_id != project_id:
        raise AppException(
            code="AI_RUN_PROJECT_MISMATCH",
            message="The specified run does not belong to this project.",
            status_code=400,
        )
    if run.status == "cancelled":
        return run
    if run.status not in ("queued", "running"):
        raise ConflictException(
            "This AI run is no longer active and cannot be cancelled.",
            code="AI_RUN_NOT_CANCELLABLE",
        )

    def _sync_cancel(session: Session) -> bool:
        row = session.get(AiRun, ai_run_id)
        if row is None or row.status not in ("queued", "running"):
            return False
        release_sheet_lock_sync(session, plan_id=row.plan_id, sheet_id=None)
        finalize_run_sync(
            session,
            ai_run_id=ai_run_id,
            status="cancelled",
            error_message="Cancelled by user",
        )
        return True

    changed = await db.run_sync(_sync_cancel)
    fresh = await get_run(db, org_id, ai_run_id)
    if not changed:
        if fresh.status == "cancelled":
            return fresh
        raise ConflictException(
            "This AI run is no longer active and cannot be cancelled.",
            code="AI_RUN_NOT_CANCELLABLE",
        )

    room = liveblocks_service.collaboration_room_id(org_id, project_id)
    liveblocks_service.broadcast_event_sync(
        room_id=room,
        event_type="ai_run.status_changed",
        data={
            "ai_run_id": str(ai_run_id),
            "status": "cancelled",
            "total_stages": len(PIPELINE_STAGES),
            "error_message": "Cancelled by user",
        },
    )

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        event_type="ai_run.cancelled",
        entity_type="ai_run",
        entity_id=ai_run_id,
        payload={"plan_id": str(fresh.plan_id)},
    )
    await db.commit()
    await db.refresh(fresh)
    return fresh


async def cost_by_org_last_24h(db: AsyncSession) -> list[dict[str, Any]]:
    """Internal admin rollup: total AI cost per org over the last 24h.

    Used by ``GET /internal/ai/cost-by-org`` (owner-scoped to the caller's
    own org in AI-01; cross-org aggregation requires a future superadmin role).
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = (
        select(
            AiRun.org_id,
            func.coalesce(func.sum(AiRun.cost_cents), 0).label("cost_cents"),
            func.coalesce(func.sum(AiRun.tokens_used), 0).label("tokens_used"),
            func.count(AiRun.id).label("run_count"),
        )
        .where(AiRun.created_at >= since)
        .group_by(AiRun.org_id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "org_id": str(r.org_id),
            "cost_cents": int(r.cost_cents),
            "tokens_used": int(r.tokens_used),
            "run_count": int(r.run_count),
        }
        for r in rows
    ]


# ─── Sync (Celery worker) ────────────────────────────────────────────────────


def _advisory_lock_key(plan_id: uuid.UUID, sheet_id: uuid.UUID | None) -> int:
    """Stable 64-bit signed int for ``pg_advisory_lock``.

    Falls back to plan-level locking when ``sheet_id`` is None (full-plan runs
    in AI-01 acquire one plan-scoped lock instead of N sheet locks; future
    sprints will move to per-sheet locking once Stage 5 element detection
    actually parallelizes by sheet).
    """
    payload = f"contruo:ai:{plan_id}:{sheet_id or 'plan'}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    # Take first 8 bytes as signed int64 (Postgres advisory locks use bigint).
    raw = int.from_bytes(digest[:8], byteorder="big", signed=True)
    return raw


def acquire_sheet_lock_sync(
    session: Session, *, plan_id: uuid.UUID, sheet_id: uuid.UUID | None
) -> bool:
    """Try to acquire the session-level advisory lock for a (plan, sheet).

    Returns ``True`` on success, ``False`` when another worker holds it.
    Use ``release_sheet_lock_sync`` to release; the lock auto-releases when
    the session closes, so a worker crash never leaves a permanent lock.
    """
    key = _advisory_lock_key(plan_id, sheet_id)
    got = session.execute(
        select(func.pg_try_advisory_lock(key))
    ).scalar_one()
    return bool(got)


def release_sheet_lock_sync(
    session: Session, *, plan_id: uuid.UUID, sheet_id: uuid.UUID | None
) -> None:
    key = _advisory_lock_key(plan_id, sheet_id)
    try:
        session.execute(select(func.pg_advisory_unlock(key)))
        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "Failed to release advisory lock for plan=%s sheet=%s", plan_id, sheet_id
        )


def update_status_sync(
    session: Session,
    *,
    ai_run_id: uuid.UUID,
    status: str,
    error_message: str | None = None,
) -> None:
    """Transition an ``ai_runs.status`` and stamp ``started_at`` / ``finished_at``."""
    values: dict[str, Any] = {"status": status}
    now = datetime.now(timezone.utc)
    if status == "running":
        values["started_at"] = now
    if status in ("completed", "failed", "cancelled"):
        values["finished_at"] = now
    if error_message:
        values["error_message"] = error_message[:1000]
    session.execute(update(AiRun).where(AiRun.id == ai_run_id).values(**values))
    session.commit()


def record_stage_timing_sync(
    session: Session,
    *,
    ai_run_id: uuid.UUID,
    stage: str,
    duration_ms: int,
    cache_hit: bool,
    started_at: datetime,
    finished_at: datetime,
    error: str | None = None,
) -> None:
    """Append a per-stage timing entry into ``summary_jsonb["stages"][stage]``.

    ``stage`` MUST come from ``PIPELINE_STAGES`` (validated here) -- it is
    interpolated into the path argument of ``jsonb_set`` and untrusted input
    would be a SQL-injection vector.
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Unknown pipeline stage: {stage!r}")
    entry: dict[str, Any] = {
        "duration_ms": duration_ms,
        "cache_hit": cache_hit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
    if error:
        entry["error"] = error[:500]

    session.execute(
        text(
            """
            UPDATE ai_runs
               SET summary_jsonb = jsonb_set(
                       summary_jsonb,
                       ARRAY['stages', :stage_name]::text[],
                       CAST(:entry AS jsonb),
                       true
                   ),
                   updated_at = now()
             WHERE id = :ai_run_id
            """
        ),
        {
            "stage_name": stage,
            "entry": json.dumps(entry, separators=(",", ":")),
            "ai_run_id": str(ai_run_id),
        },
    )
    session.commit()


def finalize_run_sync(
    session: Session,
    *,
    ai_run_id: uuid.UUID,
    status: str,
    error_message: str | None = None,
) -> None:
    """Mark a run terminal and release its lock state in summary_jsonb."""
    update_status_sync(
        session,
        ai_run_id=ai_run_id,
        status=status,
        error_message=error_message,
    )
    try:
        session.execute(
            text(
                """
                UPDATE ai_runs
                   SET summary_jsonb = jsonb_set(
                           summary_jsonb,
                           '{lock_state}'::text[],
                           '"released"'::jsonb,
                           true
                       )
                 WHERE id = :ai_run_id
                """
            ),
            {"ai_run_id": str(ai_run_id)},
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to update lock_state for run %s", ai_run_id)


# ─── AI-02: summary counters ────────────────────────────────────────────────


def update_summary_counters_sync(
    session: Session,
    *,
    ai_run_id: uuid.UUID,
    deltas: dict[str, Any],
) -> None:
    """Merge ``deltas`` into ``ai_runs.summary_jsonb["counters"]``.

    Numeric keys are *added* to the existing value (so multiple stages can
    increment the same counter); non-numeric keys overwrite. Used by Stage 1
    to record ``stage_1_titles_written`` / ``stage_1_total_sheets`` and by
    Stage 2 to record per-discipline aggregates.
    """
    if not deltas:
        return
    # Read-modify-write on the counters subkey. Cheaper than building a
    # SQL-side merge and we have at most 1 writer per run by lock invariant.
    row = session.execute(
        text("SELECT COALESCE(summary_jsonb, '{}'::jsonb) FROM ai_runs WHERE id = :id"),
        {"id": str(ai_run_id)},
    ).scalar_one_or_none()
    summary: dict[str, Any] = dict(row or {})
    counters: dict[str, Any] = dict(summary.get("counters") or {})
    for key, value in deltas.items():
        if isinstance(value, (int, float)) and isinstance(counters.get(key), (int, float)):
            counters[key] = counters[key] + value
        else:
            counters[key] = value
    summary["counters"] = counters

    session.execute(
        text(
            """
            UPDATE ai_runs
               SET summary_jsonb = CAST(:summary AS jsonb),
                   updated_at = now()
             WHERE id = :id
            """
        ),
        {
            "summary": json.dumps(summary, separators=(",", ":"), default=str),
            "id": str(ai_run_id),
        },
    )
    session.commit()


def merge_summary_jsonb_sync(
    session: Session,
    *,
    ai_run_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    """Merge a top-level dict into ``summary_jsonb`` (overwriting same keys).

    Used by stages that emit structured per-stage details (e.g. Stage 2
    writes ``classification: {by_discipline, by_type, ...}``). Numeric
    delta accumulation is handled separately by ``update_summary_counters_sync``.
    """
    if not payload:
        return
    session.execute(
        text(
            """
            UPDATE ai_runs
               SET summary_jsonb = COALESCE(summary_jsonb, '{}'::jsonb) || CAST(:payload AS jsonb),
                   updated_at = now()
             WHERE id = :id
            """
        ),
        {
            "payload": json.dumps(payload, separators=(",", ":"), default=str),
            "id": str(ai_run_id),
        },
    )
    session.commit()
