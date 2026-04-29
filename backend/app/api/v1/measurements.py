import uuid

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.middleware.error_handler import AppException
from app.schemas.measurement import (
    CreateMeasurementRequest,
    MeasurementListResponse,
    MeasurementResponse,
    UpdateMeasurementRequest,
)
from app.services import measurement_service
from app.services.permission_service import Permission, require_permission

router = APIRouter()


def _parse_if_match(if_match: str | None) -> int | None:
    """``If-Match`` is RFC-7232 entity-tagged but we use the simpler integer
    version we expose in the response. Strip optional surrounding quotes/W/."""
    if not if_match:
        return None
    raw = if_match.strip().lstrip("Ww/").strip().strip('"')
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as e:
        raise AppException(
            code="INVALID_IF_MATCH",
            message="If-Match header must be the integer version returned in the previous response",
            status_code=400,
        ) from e


@router.get("/projects/{project_id}/measurements", response_model=MeasurementListResponse)
async def list_project_measurements(
    project_id: uuid.UUID,
    sheet_id: uuid.UUID | None = None,
    include_aggregates: bool = False,
    limit: int = Query(
        measurement_service.DEFAULT_MEASUREMENT_PAGE_SIZE,
        ge=1,
        le=measurement_service.MAX_MEASUREMENT_PAGE_SIZE,
        description="Page size; capped server-side.",
    ),
    cursor: str | None = Query(
        default=None, description="Opaque cursor returned as next_cursor on the previous page."
    ),
    auth: AuthContext = Depends(require_permission(Permission.VIEW_PLANS)),
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.list_project_measurements(
        db,
        auth.org_id,
        project_id,
        sheet_id=sheet_id,
        include_aggregates=include_aggregates,
        limit=limit,
        cursor=cursor,
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
    if_match: str | None = Header(default=None, alias="If-Match"),
    auth: AuthContext = Depends(require_permission(Permission.EDIT_MEASUREMENTS)),
    db: AsyncSession = Depends(get_db),
):
    """Update a measurement.

    Optional ``If-Match`` header: send the ``version`` returned in the previous
    response to enable optimistic locking. A mismatch returns 409 ``VERSION_MISMATCH``
    so the client can refetch and merge instead of clobbering a peer's edit.
    """
    return await measurement_service.update_measurement(
        db,
        auth.org_id,
        measurement_id,
        auth.user_id,
        body,
        expected_version=_parse_if_match(if_match),
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
