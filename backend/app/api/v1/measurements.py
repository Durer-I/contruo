import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.schemas.measurement import (
    CreateMeasurementRequest,
    MeasurementListResponse,
    MeasurementResponse,
    UpdateMeasurementRequest,
)
from app.services import measurement_service
from app.services.permission_service import Permission, require_permission

router = APIRouter()


@router.get("/projects/{project_id}/measurements", response_model=MeasurementListResponse)
async def list_project_measurements(
    project_id: uuid.UUID,
    sheet_id: uuid.UUID | None = None,
    include_aggregates: bool = False,
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.list_project_measurements(
        db,
        auth.org_id,
        project_id,
        sheet_id=sheet_id,
        include_aggregates=include_aggregates,
    )


@router.post("/projects/{project_id}/measurements", response_model=MeasurementResponse, status_code=201)
async def create_measurement(
    project_id: uuid.UUID,
    body: CreateMeasurementRequest,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.create_measurement(
        db, auth.org_id, project_id, auth.user_id, body
    )


@router.patch("/measurements/{measurement_id}", response_model=MeasurementResponse)
async def update_measurement(
    measurement_id: uuid.UUID,
    body: UpdateMeasurementRequest,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.update_measurement(
        db, auth.org_id, measurement_id, auth.user_id, body
    )


@router.delete("/measurements/{measurement_id}", status_code=204)
async def delete_measurement(
    measurement_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    await measurement_service.delete_measurement(
        db, auth.org_id, measurement_id, auth.user_id
    )
    return Response(status_code=204)
