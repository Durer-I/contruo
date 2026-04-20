"""CRUD for assembly items on a condition."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import NotFoundException
from app.models.assembly_item import AssemblyItem
from app.models.condition import Condition
from app.schemas.assembly import (
    AssemblyItemListResponse,
    AssemblyItemResponse,
    CreateAssemblyItemRequest,
    PreviewAssemblyFormulaRequest,
    PreviewAssemblyFormulaResponse,
    UpdateAssemblyItemRequest,
)
from app.services import condition_service
from app.services import assembly_derived
from app.services.event_service import log_event
from app.services.formula_engine import FormulaError, evaluate_formula


def _to_item_response(row: AssemblyItem) -> AssemblyItemResponse:
    return AssemblyItemResponse(
        id=row.id,
        org_id=row.org_id,
        condition_id=row.condition_id,
        parent_id=row.parent_id,
        name=row.name,
        unit=row.unit,
        formula=row.formula,
        description=row.description,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _next_item_sort_order(db: AsyncSession, condition_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.max(AssemblyItem.sort_order), -1)).where(
        AssemblyItem.condition_id == condition_id
    )
    m = (await db.execute(stmt)).scalar_one()
    return int(m) + 1


async def list_assembly_items(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
) -> AssemblyItemListResponse:
    await condition_service._get_condition(db, org_id, condition_id)
    stmt = (
        select(AssemblyItem)
        .where(AssemblyItem.org_id == org_id, AssemblyItem.condition_id == condition_id)
        .order_by(AssemblyItem.sort_order.asc(), AssemblyItem.created_at.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return AssemblyItemListResponse(items=[_to_item_response(r) for r in rows])


async def create_assembly_item(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    user_id: uuid.UUID,
    body: CreateAssemblyItemRequest,
) -> AssemblyItemResponse:
    c = await condition_service._get_condition(db, org_id, condition_id)
    sort_order = body.sort_order if body.sort_order is not None else await _next_item_sort_order(db, condition_id)
    row = AssemblyItem(
        org_id=org_id,
        condition_id=condition_id,
        parent_id=None,
        name=body.name,
        unit=body.unit,
        formula=body.formula,
        description=body.description,
        sort_order=sort_order,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=c.project_id,
        event_type="assembly_item.created",
        entity_type="assembly_item",
        entity_id=row.id,
        payload={"condition_id": str(condition_id), "name": row.name},
    )
    return _to_item_response(row)


async def update_assembly_item(
    db: AsyncSession,
    org_id: uuid.UUID,
    assembly_item_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateAssemblyItemRequest,
) -> AssemblyItemResponse:
    stmt = select(AssemblyItem).where(AssemblyItem.id == assembly_item_id, AssemblyItem.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise NotFoundException("assembly_item", str(assembly_item_id))

    data = body.model_dump(exclude_unset=True)
    if not data:
        return _to_item_response(row)

    for k, v in data.items():
        setattr(row, k, v)
    await db.flush()
    await db.refresh(row)

    c = await condition_service._get_condition(db, org_id, row.condition_id)
    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=c.project_id,
        event_type="assembly_item.updated",
        entity_type="assembly_item",
        entity_id=row.id,
        payload={"fields": list(data.keys())},
    )
    return _to_item_response(row)


async def delete_assembly_item(
    db: AsyncSession,
    org_id: uuid.UUID,
    assembly_item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    stmt = select(AssemblyItem).where(AssemblyItem.id == assembly_item_id, AssemblyItem.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise NotFoundException("assembly_item", str(assembly_item_id))
    cid = row.condition_id
    c = await condition_service._get_condition(db, org_id, cid)
    await db.execute(delete(AssemblyItem).where(AssemblyItem.id == assembly_item_id, AssemblyItem.org_id == org_id))
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=c.project_id,
        event_type="assembly_item.deleted",
        entity_type="assembly_item",
        entity_id=assembly_item_id,
        payload={"condition_id": str(cid)},
    )


async def preview_assembly_formula(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    body: PreviewAssemblyFormulaRequest,
) -> PreviewAssemblyFormulaResponse:
    c = await condition_service._get_condition(db, org_id, condition_id)
    vars_ = assembly_derived.build_preview_variables(
        c.measurement_type,
        body.sample_primary,
        body.sample_perimeter,
        c,
    )
    try:
        v = evaluate_formula(body.formula, vars_)
    except FormulaError as e:
        return PreviewAssemblyFormulaResponse(value=None, error=e.message)
    return PreviewAssemblyFormulaResponse(value=v, error=None)


async def bulk_create_items_from_snapshot(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    snapshot: list[dict],
) -> None:
    """Insert assembly rows from template JSON snapshot (no events)."""
    for i, raw in enumerate(snapshot):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        unit = str(raw.get("unit", "EA")).strip() or "EA"
        formula = str(raw.get("formula", "0")).strip() or "0"
        desc = raw.get("description")
        sort_order = int(raw.get("sort_order", i))
        if not name:
            continue
        db.add(
            AssemblyItem(
                org_id=org_id,
                condition_id=condition_id,
                parent_id=None,
                name=name[:255],
                unit=unit[:20],
                formula=formula,
                description=str(desc)[:2000] if desc is not None else None,
                sort_order=sort_order,
            )
        )
    await db.flush()
