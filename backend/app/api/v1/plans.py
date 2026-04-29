import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.services.permission_service import Permission, require_permission
from app.services import plan_service, project_service
from app.schemas.plan import PlanDocumentUrlResponse, PlanResponse

router = APIRouter(prefix="/plans")


async def _ensure_plan_visible(
    db: AsyncSession, auth: AuthContext, plan_id: uuid.UUID
) -> None:
    """Resolve plan -> project, then run guest scope check before any further work."""
    plan = await plan_service.get_plan(db, auth.org_id, plan_id)
    await project_service.assert_project_visible(db, auth, plan.project_id)


@router.get("/{plan_id}/document-url", response_model=PlanDocumentUrlResponse)
async def get_plan_document_url(
    plan_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    """Signed URL for the raw PDF (used by the browser pdf.js viewer)."""
    await _ensure_plan_visible(db, auth, plan_id)
    url, expires_in = await plan_service.get_plan_document_signed_url(
        db, auth.org_id, plan_id
    )
    return PlanDocumentUrlResponse(url=url, expires_in=expires_in)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    """Return processing status for a plan. Frontend polls this during upload."""
    plan = await plan_service.get_plan(db, auth.org_id, plan_id)
    await project_service.assert_project_visible(db, auth, plan.project_id)
    return PlanResponse.from_model(plan)


@router.post("/{plan_id}/retry", response_model=PlanResponse)
async def retry_plan(
    plan_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.UPLOAD_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_plan_visible(db, auth, plan_id)
    plan = await plan_service.retry_plan(db, auth.org_id, plan_id, auth.user_id)
    return PlanResponse.from_model(plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.UPLOAD_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an in-progress upload or delete a processed plan.

    Refuses to delete the project's last remaining plan (returns 400 ``LAST_PLAN_REQUIRED``).
    """
    await _ensure_plan_visible(db, auth, plan_id)
    await plan_service.delete_plan(db, auth.org_id, plan_id, auth.user_id)
    return Response(status_code=204)
