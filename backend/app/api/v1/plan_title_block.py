"""Title-block / auto-name-sheets endpoints (Sprint AI-02b).

Today this module exposes one endpoint: a user-triggered "auto-name sheets"
button enqueues a Celery task that reads each sheet's title-block region and
writes structured ``sheet_name`` + ``sheet_number`` columns. The task
respects the ``sheet_name_source = 'manual'`` guard unless the client sends
``overwrite_manual: true``.

A future ``POST .../title-block`` (the user-drawn-bbox flow) belongs in this
file too -- keeping all title-block routes together gives the redesign one
URL prefix to evolve.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.middleware.error_handler import AppException, NotFoundException
from app.models.plan import Plan
from app.schemas.plan_title_block import AutoNameSheetsRequest, AutoNameSheetsResponse
from app.services.permission_service import Permission, require_permission

router = APIRouter(prefix="/projects/{project_id}/plans/{plan_id}", tags=["plans"])


@router.post(
    "/auto-name-sheets",
    response_model=AutoNameSheetsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def auto_name_sheets(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: AutoNameSheetsRequest = Body(default_factory=AutoNameSheetsRequest),
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
) -> AutoNameSheetsResponse:
    """Enqueue a re-extract of every sheet's name + number from its title block.

    Idempotent at the task level (the per-plan advisory lock serializes
    concurrent calls). Returns 202 with the queued task id immediately --
    completion is signaled via the Liveblocks ``sheets.auto_named`` event;
    the frontend uses a short polling backstop on top.

    Errors:
      * 404 ``PLAN_NOT_FOUND`` -- plan id doesn't belong to this org/project.
      * 409 ``PLAN_NOT_READY`` -- plan is still processing or errored.
      * 503 ``AUTO_NAME_DISABLED`` -- the feature flag is off in this env.
    """
    settings = get_settings()
    if not settings.ai_auto_name_enabled:
        raise AppException(
            code="AUTO_NAME_DISABLED",
            message="Auto-name sheets is disabled in this environment.",
            status_code=503,
        )

    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.project_id == project_id,
        Plan.org_id == auth.org_id,
    )
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if not plan:
        raise NotFoundException("plan", str(plan_id))
    if plan.status != "ready":
        raise AppException(
            code="PLAN_NOT_READY",
            message="Plan is not ready for auto-naming yet.",
            status_code=409,
            details={"plan_status": plan.status},
        )

    # Local import keeps the API process free of Celery's heavy import chain
    # at module load (matches the pattern used by other AI endpoints).
    from app.tasks.ai_pipeline import reextract_plan_titles_task

    queued_at = datetime.now(timezone.utc)
    async_result = reextract_plan_titles_task.delay(
        str(plan_id), overwrite_manual=payload.overwrite_manual
    )

    return AutoNameSheetsResponse(
        plan_id=plan_id,
        task_id=str(async_result.id),
        queued_at=queued_at,
    )
