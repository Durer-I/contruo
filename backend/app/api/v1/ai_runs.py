"""AI Auto-Takeoff run endpoints (Sprint AI-01).

Surface area:

* ``POST /api/v1/projects/{project_id}/ai/runs`` -- start a new run.
* ``GET  /api/v1/projects/{project_id}/ai/runs`` -- list runs for a project.
* ``GET  /api/v1/projects/{project_id}/ai/runs/{ai_run_id}`` -- run detail.

All gated to ``EDIT_MEASUREMENTS`` -- estimators and above. Viewers and guests
do not trigger runs but will see them via Liveblocks broadcasts in AI-05.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.middleware.error_handler import AppException
from app.schemas.ai_run import (
    AiRunCreate,
    AiRunListResponse,
    AiRunResponse,
)
from app.services import ai_run_service, plan_service, project_service
from app.services.permission_service import Permission, require_permission

router = APIRouter(prefix="/projects")


async def _ensure_plan_belongs_to_project(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> None:
    plan = await plan_service.get_plan(db, org_id, plan_id)
    if plan.project_id != project_id:
        raise AppException(
            code="PLAN_PROJECT_MISMATCH",
            message="The specified plan does not belong to this project.",
            status_code=400,
        )
    if plan.status != "ready":
        raise AppException(
            code="PLAN_NOT_READY",
            message=(
                "AI Auto-Takeoff can only run on a fully-processed plan. "
                f"This plan is currently '{plan.status}'."
            ),
            status_code=409,
            details={"plan_status": plan.status},
        )


@router.post(
    "/{project_id}/ai/runs",
    response_model=AiRunResponse,
    status_code=202,
)
async def create_ai_run(
    project_id: uuid.UUID,
    body: AiRunCreate,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI Auto-Takeoff run for ``plan_id`` in ``project_id``.

    Returns 202 with the queued ``ai_runs`` row. The Celery worker picks it up
    and walks through the six pipeline stages, broadcasting progress to the
    project's Liveblocks room. Returns 409 if a run is already active for the
    plan, or 429 if the org's 24h cost cap has tripped.
    """
    await project_service.assert_project_visible(db, auth, project_id)
    await _ensure_plan_belongs_to_project(
        db, org_id=auth.org_id, project_id=project_id, plan_id=body.plan_id
    )
    await ai_run_service.check_circuit_breaker(db, auth.org_id)
    await ai_run_service.assert_no_active_run_for_plan(db, auth.org_id, body.plan_id)

    run = await ai_run_service.create_run(
        db,
        org_id=auth.org_id,
        project_id=project_id,
        plan_id=body.plan_id,
        triggered_by=auth.user_id,
        scope=body.scope,
    )
    # Flush + commit happens in the get_db dependency wrapper.
    await db.commit()
    await db.refresh(run)

    # Enqueue the chain after commit so the worker never reads a row the API
    # transaction later rolled back.
    from app.tasks.ai_pipeline import build_pipeline_chain  # local: avoid celery import in API tests
    build_pipeline_chain(run.id).apply_async()

    return AiRunResponse.from_model(run)


@router.get(
    "/{project_id}/ai/runs",
    response_model=AiRunListResponse,
)
async def list_ai_runs(
    project_id: uuid.UUID,
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    await project_service.assert_project_visible(db, auth, project_id)
    runs = await ai_run_service.list_runs(
        db, auth.org_id, project_id, status=status, limit=limit
    )
    return AiRunListResponse(runs=[AiRunResponse.from_model(r) for r in runs])


@router.get(
    "/{project_id}/ai/runs/{ai_run_id}",
    response_model=AiRunResponse,
)
async def get_ai_run(
    project_id: uuid.UUID,
    ai_run_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    await project_service.assert_project_visible(db, auth, project_id)
    run = await ai_run_service.get_run(db, auth.org_id, ai_run_id)
    if run.project_id != project_id:
        raise AppException(
            code="AI_RUN_PROJECT_MISMATCH",
            message="The specified run does not belong to this project.",
            status_code=400,
        )
    return AiRunResponse.from_model(run)

