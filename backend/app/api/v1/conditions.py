import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.schemas.condition import (
    ConditionListResponse,
    ConditionResponse,
    CreateConditionRequest,
    UpdateConditionRequest,
)
from app.services import condition_service
from app.services.permission_service import Permission, require_permission

router = APIRouter()


@router.get("/projects/{project_id}/conditions", response_model=ConditionListResponse)
async def list_project_conditions(
    project_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    conditions = await condition_service.list_conditions_for_project(
        db, auth.org_id, project_id
    )
    return ConditionListResponse(conditions=conditions)


@router.post("/projects/{project_id}/conditions", response_model=ConditionResponse, status_code=201)
async def create_project_condition(
    project_id: uuid.UUID,
    body: CreateConditionRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await condition_service.create_condition(
        db, auth.org_id, project_id, auth.user_id, body
    )


@router.patch("/conditions/{condition_id}", response_model=ConditionResponse)
async def update_condition(
    condition_id: uuid.UUID,
    body: UpdateConditionRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    return await condition_service.update_condition(
        db, auth.org_id, condition_id, auth.user_id, body
    )


@router.delete("/conditions/{condition_id}", status_code=204)
async def delete_condition(
    condition_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_CONDITIONS)),
    db: AsyncSession = Depends(get_db),
):
    await condition_service.delete_condition(db, auth.org_id, condition_id, auth.user_id)
    return Response(status_code=204)
