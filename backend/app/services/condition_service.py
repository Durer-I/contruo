"""Condition CRUD for a project."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppException, NotFoundException
from app.models.condition import Condition
from app.models.measurement import Measurement
from app.models.project import Project
from app.schemas.condition import (
    ConditionPropertiesPayload,
    ConditionResponse,
    CreateConditionRequest,
    UpdateConditionRequest,
)
from app.services import project_service
from app.services.event_service import log_event


def _parse_properties(raw: dict[str, Any] | None) -> ConditionPropertiesPayload:
    if not raw:
        return ConditionPropertiesPayload()
    custom_raw = raw.get("custom")
    if not isinstance(custom_raw, list):
        return ConditionPropertiesPayload()
    items = []
    for row in custom_raw:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if not name or not str(name).strip():
            continue
        items.append(
            {
                "name": str(name).strip(),
                "value": str(row.get("value", "")),
                "unit": str(row.get("unit", "")),
            }
        )
    return ConditionPropertiesPayload.model_validate({"custom": items})


def _props_to_db(p: ConditionPropertiesPayload) -> dict[str, Any]:
    return {"custom": [x.model_dump() for x in p.custom]}


def _to_response(
    c: Condition,
    *,
    measurement_count: int = 0,
    total_quantity: float = 0.0,
) -> ConditionResponse:
    return ConditionResponse(
        id=c.id,
        org_id=c.org_id,
        project_id=c.project_id,
        name=c.name,
        measurement_type=c.measurement_type,
        unit=c.unit,
        color=c.color,
        line_style=c.line_style,
        line_width=c.line_width,
        fill_opacity=c.fill_opacity,
        fill_pattern=c.fill_pattern,
        properties=_parse_properties(c.properties if isinstance(c.properties, dict) else None),
        trade=c.trade,
        description=c.description,
        notes=c.notes,
        sort_order=c.sort_order,
        measurement_count=measurement_count,
        total_quantity=total_quantity,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def list_conditions_for_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[ConditionResponse]:
    await project_service.get_project(db, org_id, project_id)

    cond_stmt = (
        select(Condition)
        .where(Condition.org_id == org_id, Condition.project_id == project_id)
        .order_by(Condition.sort_order.asc(), Condition.created_at.asc())
    )
    conditions = (await db.execute(cond_stmt)).scalars().all()
    if not conditions:
        return []

    agg_stmt = (
        select(
            Measurement.condition_id,
            func.count(Measurement.id),
            func.coalesce(func.sum(Measurement.measured_value), 0.0),
        )
        .where(
            Measurement.org_id == org_id,
            Measurement.project_id == project_id,
        )
        .group_by(Measurement.condition_id)
    )
    agg_result = await db.execute(agg_stmt)
    agg: dict[uuid.UUID, tuple[int, float]] = {
        row[0]: (int(row[1]), float(row[2])) for row in agg_result.all()
    }

    return [
        _to_response(
            c,
            measurement_count=agg.get(c.id, (0, 0.0))[0],
            total_quantity=agg.get(c.id, (0, 0.0))[1],
        )
        for c in conditions
    ]


async def _next_sort_order(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.max(Condition.sort_order), -1)).where(
        Condition.org_id == org_id,
        Condition.project_id == project_id,
    )
    m = (await db.execute(stmt)).scalar_one()
    return int(m) + 1


async def create_condition(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: CreateConditionRequest,
) -> ConditionResponse:
    await project_service.get_project(db, org_id, project_id)

    sort_order = await _next_sort_order(db, org_id, project_id)
    c = Condition(
        org_id=org_id,
        project_id=project_id,
        name=body.name,
        measurement_type=body.measurement_type,
        unit=body.unit,
        color=body.color,
        line_style=body.line_style,
        line_width=body.line_width,
        fill_opacity=body.fill_opacity,
        fill_pattern=body.fill_pattern,
        properties=_props_to_db(body.properties),
        trade=body.trade,
        description=body.description,
        notes=body.notes,
        sort_order=sort_order,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        event_type="condition.created",
        entity_type="condition",
        entity_id=c.id,
        payload={"name": c.name, "measurement_type": c.measurement_type},
    )
    return _to_response(c)


async def _get_condition(
    db: AsyncSession, org_id: uuid.UUID, condition_id: uuid.UUID
) -> Condition:
    stmt = select(Condition).where(Condition.id == condition_id, Condition.org_id == org_id)
    result = await db.execute(stmt)
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundException("condition", str(condition_id))
    return c


async def _aggregates_for_condition(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
) -> tuple[int, float]:
    stmt = select(
        func.count(Measurement.id),
        func.coalesce(func.sum(Measurement.measured_value), 0.0),
    ).where(Measurement.org_id == org_id, Measurement.condition_id == condition_id)
    row = (await db.execute(stmt)).one()
    return int(row[0] or 0), float(row[1] or 0.0)


async def update_condition(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateConditionRequest,
) -> ConditionResponse:
    c = await _get_condition(db, org_id, condition_id)

    data = body.model_dump(exclude_unset=True)
    if not data:
        mc, tq = await _aggregates_for_condition(db, org_id, condition_id)
        return _to_response(c, measurement_count=mc, total_quantity=tq)

    if "measurement_type" in data and data["measurement_type"] != c.measurement_type:
        mc, _ = await _aggregates_for_condition(db, org_id, condition_id)
        if mc > 0:
            raise AppException(
                code="CONDITION_HAS_MEASUREMENTS",
                message="Cannot change measurement type while measurements exist for this condition.",
                status_code=409,
            )

    if "properties" in data and data["properties"] is not None:
        data["properties"] = _props_to_db(
            ConditionPropertiesPayload.model_validate(data["properties"])
        )

    for k, v in data.items():
        setattr(c, k, v)

    await db.flush()
    await db.refresh(c)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=c.project_id,
        event_type="condition.updated",
        entity_type="condition",
        entity_id=c.id,
        payload={"fields": list(data.keys())},
    )

    mc, tq = await _aggregates_for_condition(db, org_id, condition_id)
    return _to_response(c, measurement_count=mc, total_quantity=tq)


async def delete_condition(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    c = await _get_condition(db, org_id, condition_id)
    pid = c.project_id
    name = c.name

    await db.execute(delete(Condition).where(Condition.id == condition_id, Condition.org_id == org_id))
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=pid,
        event_type="condition.deleted",
        entity_type="condition",
        entity_id=condition_id,
        payload={"name": name},
    )

