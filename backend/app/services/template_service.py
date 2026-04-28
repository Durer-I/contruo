"""Org-level condition templates (library + import)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import NotFoundException
from app.models.assembly_item import AssemblyItem
from app.models.condition import Condition
from app.models.condition_template import ConditionTemplate
from app.schemas.assembly import (
    ConditionTemplateDetailResponse,
    ConditionTemplateListResponse,
    ConditionTemplateResponse,
    SaveConditionAsTemplateRequest,
    UpdateConditionTemplateRequest,
)
from app.schemas.condition import (
    ConditionPropertiesPayload,
    ConditionResponse,
    CreateConditionRequest,
)
from app.services import assembly_service, condition_service
from app.services.condition_service import _props_to_db, _to_response as condition_to_response
from app.services.event_service import log_event
from app.utils.condition_name_disambiguation import disambiguate_condition_name


async def _get_template_row(
    db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID
) -> ConditionTemplate:
    stmt = select(ConditionTemplate).where(
        ConditionTemplate.id == template_id,
        ConditionTemplate.org_id == org_id,
    )
    t = (await db.execute(stmt)).scalar_one_or_none()
    if not t:
        raise NotFoundException("condition_template", str(template_id))
    return t


async def _condition_names_in_project(
    db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID
) -> set[str]:
    stmt = select(Condition.name).where(
        Condition.org_id == org_id,
        Condition.project_id == project_id,
    )
    rows = (await db.execute(stmt)).all()
    return {str(r[0]) for r in rows}


def _normalize_assembly_snapshot(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        unit = str(row.get("unit", "EA")).strip() or "EA"
        formula = str(row.get("formula", "0")).strip() or "0"
        desc = row.get("description")
        sort_order = int(row.get("sort_order", i))
        out.append(
            {
                "name": name[:255],
                "unit": unit[:20],
                "formula": formula,
                "description": str(desc)[:2000] if desc is not None else None,
                "sort_order": sort_order,
            }
        )
    return out


def _template_to_response(t: ConditionTemplate) -> ConditionTemplateResponse:
    snap = t.assembly_items if isinstance(t.assembly_items, list) else []
    return ConditionTemplateResponse(
        id=t.id,
        org_id=t.org_id,
        name=t.name,
        measurement_type=t.measurement_type,
        unit=t.unit,
        color=t.color,
        line_style=t.line_style,
        line_width=float(t.line_width),
        fill_opacity=float(t.fill_opacity),
        fill_pattern=t.fill_pattern,
        properties=t.properties if isinstance(t.properties, dict) else {},
        trade=t.trade,
        description=t.description,
        assembly_item_count=len(snap),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


async def list_templates(db: AsyncSession, org_id: uuid.UUID) -> ConditionTemplateListResponse:
    stmt = (
        select(ConditionTemplate)
        .where(ConditionTemplate.org_id == org_id)
        .order_by(ConditionTemplate.name.asc(), ConditionTemplate.created_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return ConditionTemplateListResponse(templates=[_template_to_response(t) for t in rows])


async def get_template(
    db: AsyncSession, org_id: uuid.UUID, template_id: uuid.UUID
) -> ConditionTemplateDetailResponse:
    t = await _get_template_row(db, org_id, template_id)
    snap = t.assembly_items if isinstance(t.assembly_items, list) else []
    base = _template_to_response(t)
    return ConditionTemplateDetailResponse(**base.model_dump(), assembly_items=list(snap))


async def update_template(
    db: AsyncSession,
    org_id: uuid.UUID,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateConditionTemplateRequest,
) -> ConditionTemplateDetailResponse:
    t = await _get_template_row(db, org_id, template_id)
    data = body.model_dump(exclude_unset=True)
    if not data:
        return await get_template(db, org_id, template_id)

    if "name" in data:
        t.name = str(data["name"]).strip()[:255]
    if "unit" in data:
        t.unit = str(data["unit"]).strip()[:20]
    if "color" in data:
        t.color = str(data["color"]).strip().lower()[:7]
    if "line_style" in data and data["line_style"] is not None:
        t.line_style = str(data["line_style"])
    if "line_width" in data and data["line_width"] is not None:
        t.line_width = float(data["line_width"])
    if "fill_opacity" in data and data["fill_opacity"] is not None:
        t.fill_opacity = float(data["fill_opacity"])
    if "fill_pattern" in data and data["fill_pattern"] is not None:
        t.fill_pattern = str(data["fill_pattern"])
    if "trade" in data:
        v = data["trade"]
        t.trade = str(v).strip()[:100] if v else None
    if "description" in data:
        t.description = data["description"]
    if "properties" in data and data["properties"] is not None:
        p = (
            data["properties"]
            if isinstance(data["properties"], ConditionPropertiesPayload)
            else ConditionPropertiesPayload.model_validate(data["properties"])
        )
        t.properties = _props_to_db(p)
    if "assembly_items" in data and data["assembly_items"] is not None:
        t.assembly_items = _normalize_assembly_snapshot(list(data["assembly_items"]))

    await db.flush()
    await db.refresh(t)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=None,
        event_type="condition_template.updated",
        entity_type="condition_template",
        entity_id=t.id,
        payload={"fields": list(data.keys())},
    )
    return await get_template(db, org_id, template_id)


async def save_condition_as_template(
    db: AsyncSession,
    org_id: uuid.UUID,
    condition_id: uuid.UUID,
    user_id: uuid.UUID,
    body: SaveConditionAsTemplateRequest,
) -> ConditionTemplateResponse:
    c = await condition_service._get_condition(db, org_id, condition_id)
    stmt = (
        select(AssemblyItem)
        .where(AssemblyItem.org_id == org_id, AssemblyItem.condition_id == condition_id)
        .order_by(AssemblyItem.sort_order.asc(), AssemblyItem.created_at.asc())
    )
    items = list((await db.execute(stmt)).scalars().all())
    snapshot: list[dict[str, Any]] = [
        {
            "name": it.name,
            "unit": it.unit,
            "formula": it.formula,
            "description": it.description,
            "sort_order": it.sort_order,
        }
        for it in items
    ]
    props = c.properties if isinstance(c.properties, dict) else {}
    name = (body.name or c.name).strip()[:255]
    t = ConditionTemplate(
        org_id=org_id,
        name=name,
        measurement_type=c.measurement_type,
        unit=c.unit,
        color=c.color,
        line_style=c.line_style,
        line_width=float(c.line_width),
        fill_opacity=float(c.fill_opacity),
        fill_pattern=c.fill_pattern,
        properties=props,
        trade=c.trade,
        description=c.description,
        assembly_items=snapshot,
    )
    db.add(t)
    await db.flush()
    await db.refresh(t)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=c.project_id,
        event_type="condition_template.created",
        entity_type="condition_template",
        entity_id=t.id,
        payload={"source_condition_id": str(condition_id), "name": t.name},
    )
    return _template_to_response(t)


async def delete_template(
    db: AsyncSession,
    org_id: uuid.UUID,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    stmt = select(ConditionTemplate).where(
        ConditionTemplate.id == template_id, ConditionTemplate.org_id == org_id
    )
    t = (await db.execute(stmt)).scalar_one_or_none()
    if not t:
        raise NotFoundException("condition_template", str(template_id))
    await db.execute(
        delete(ConditionTemplate).where(
            ConditionTemplate.id == template_id, ConditionTemplate.org_id == org_id
        )
    )
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=None,
        event_type="condition_template.deleted",
        entity_type="condition_template",
        entity_id=template_id,
        payload={"name": t.name},
    )


async def import_template_to_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    template_id: uuid.UUID,
) -> ConditionResponse:
    stmt = select(ConditionTemplate).where(
        ConditionTemplate.id == template_id, ConditionTemplate.org_id == org_id
    )
    t = (await db.execute(stmt)).scalar_one_or_none()
    if not t:
        raise NotFoundException("condition_template", str(template_id))

    taken = await _condition_names_in_project(db, org_id, project_id)
    unique_name = disambiguate_condition_name(t.name, taken)

    props = ConditionPropertiesPayload.model_validate(t.properties if isinstance(t.properties, dict) else {})
    create_body = CreateConditionRequest(
        name=unique_name,
        measurement_type=t.measurement_type,  # type: ignore[arg-type]
        unit=t.unit,
        color=t.color,
        line_style=t.line_style,  # type: ignore[arg-type]
        line_width=float(t.line_width),
        fill_opacity=float(t.fill_opacity),
        fill_pattern=t.fill_pattern,  # type: ignore[arg-type]
        properties=props,
        trade=t.trade,
        description=t.description,
        notes=None,
    )
    created = await condition_service.create_condition(db, org_id, project_id, user_id, create_body)

    snap = t.assembly_items if isinstance(t.assembly_items, list) else []
    await assembly_service.bulk_create_items_from_snapshot(db, org_id, created.id, snap)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        event_type="condition.imported_from_template",
        entity_type="condition",
        entity_id=created.id,
        payload={"template_id": str(template_id)},
    )
    mc, tq = await condition_service._aggregates_for_condition(db, org_id, created.id)
    c_row = await condition_service._get_condition(db, org_id, created.id)
    return condition_to_response(c_row, measurement_count=mc, total_quantity=tq)
