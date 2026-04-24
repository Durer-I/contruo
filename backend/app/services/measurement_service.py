"""Measurement CRUD — linear, area, and count takeoff."""

from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppException, NotFoundException
from app.models.assembly_item import AssemblyItem
from app.models.condition import Condition
from app.models.measurement import Measurement
from app.models.sheet import Sheet
from app.schemas.measurement import (
    CreateMeasurementRequest,
    DerivedQuantityItem,
    MeasurementAggregates,
    MeasurementConditionAggregate,
    MeasurementListResponse,
    MeasurementResponse,
    UpdateMeasurementRequest,
)
from app.services import project_service
from app.services.assembly_derived import build_formula_variables, evaluate_assembly_items
from app.services.event_service import log_event
from app.utils.area_geometry import (
    compute_area_metrics,
    ellipse_area_pdf_sq,
    ellipse_outline,
    ellipse_params_from_corners,
    ellipse_perimeter_approx,
    normalize_ring,
    polygon_area_abs,
    rectangle_from_corners,
)
from app.utils.measurement_quantity import (
    area_measured_value,
    linear_measured_value,
    polyline_length_pdf_points,
)


def _parse_linear_vertices(geometry: dict[str, Any]) -> list[dict[str, Any]]:
    if geometry.get("type") != "linear":
        raise AppException(
            code="INVALID_GEOMETRY",
            message="geometry.type must be 'linear' for linear measurements",
            status_code=400,
        )
    verts = geometry.get("vertices")
    if not isinstance(verts, list) or len(verts) < 2:
        raise AppException(
            code="INVALID_GEOMETRY",
            message="linear geometry requires at least two vertices",
            status_code=400,
        )
    out = []
    for p in verts:
        if not isinstance(p, dict):
            raise AppException(code="INVALID_GEOMETRY", message="invalid vertex", status_code=400)
        try:
            out.append({"x": float(p["x"]), "y": float(p["y"])})
        except (KeyError, TypeError, ValueError) as e:
            raise AppException(
                code="INVALID_GEOMETRY",
                message="vertices must have numeric x and y",
                status_code=400,
            ) from e
    return out


def _geometry_dict_linear(vertices: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "linear", "vertices": vertices}


def _parse_linear_deductions(raw: Any) -> list[list[dict[str, Any]]]:
    """Each deduction is an open polyline with at least two vertices (PDF points)."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AppException(
            code="INVALID_DEDUCTIONS",
            message="deductions must be a list",
            status_code=400,
        )
    out: list[list[dict[str, Any]]] = []
    for i, item in enumerate(raw):
        verts_raw: Any = None
        if isinstance(item, dict):
            verts_raw = item.get("vertices")
        elif isinstance(item, list):
            verts_raw = item
        if not isinstance(verts_raw, list) or len(verts_raw) < 2:
            raise AppException(
                code="INVALID_DEDUCTIONS",
                message=f"deduction[{i}] needs at least two vertices",
                status_code=400,
            )
        verts = _parse_linear_vertices({"type": "linear", "vertices": verts_raw})
        out.append(verts)
    return out


def _deduction_polylines_stored(polylines: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"vertices": ring} for ring in polylines]


def _stored_deduction_polylines(m: Measurement) -> list[list[dict[str, Any]]]:
    if m.measurement_type != "linear":
        return []
    try:
        return _parse_linear_deductions(m.deductions)
    except AppException:
        return []


def _linear_net_pdf_length(vertices: list[dict[str, Any]], deductions: list[list[dict[str, Any]]]) -> float:
    gross = polyline_length_pdf_points(vertices)
    deduct = 0.0
    for ring in deductions:
        if len(ring) >= 2:
            deduct += polyline_length_pdf_points(ring)
    return max(0.0, gross - deduct)


def _parse_count_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    if geometry.get("type") != "count":
        raise AppException(
            code="INVALID_GEOMETRY",
            message="geometry.type must be 'count' for count measurements",
            status_code=400,
        )
    pos = geometry.get("position")
    if not isinstance(pos, dict):
        raise AppException(code="INVALID_GEOMETRY", message="count geometry requires position", status_code=400)
    try:
        return {"type": "count", "position": {"x": float(pos["x"]), "y": float(pos["y"])}}
    except (KeyError, TypeError, ValueError) as e:
        raise AppException(code="INVALID_GEOMETRY", message="position must have x and y", status_code=400) from e


def _normalize_area_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    if geometry.get("type") != "area":
        raise AppException(
            code="INVALID_GEOMETRY",
            message="geometry.type must be 'area' for area measurements",
            status_code=400,
        )
    shape = geometry.get("shape") or "polygon"
    if shape not in ("polygon", "rectangle", "ellipse"):
        raise AppException(code="INVALID_GEOMETRY", message="invalid area shape", status_code=400)

    holes_in = geometry.get("holes")
    holes: list[list[dict[str, float]]] = []
    if isinstance(holes_in, list):
        for ring in holes_in:
            if not isinstance(ring, list) or len(ring) < 3:
                continue
            hr: list[dict[str, float]] = []
            for p in ring:
                if not isinstance(p, dict):
                    raise AppException(code="INVALID_GEOMETRY", message="invalid hole vertex", status_code=400)
                hr.append({"x": float(p["x"]), "y": float(p["y"])})
            holes.append(normalize_ring(hr))

    outer: list[dict[str, float]]

    if shape == "rectangle":
        corners = geometry.get("corners")
        if not isinstance(corners, list) or len(corners) != 2:
            raise AppException(
                code="INVALID_GEOMETRY",
                message="rectangle area requires corners: two {x,y} points",
                status_code=400,
            )
        outer = rectangle_from_corners(corners[0], corners[1])
        metrics = compute_area_metrics(outer=outer, holes=holes)
        return {
            "type": "area",
            "shape": "rectangle",
            "outer": outer,
            "holes": holes,
            "corners": [
                {"x": float(corners[0]["x"]), "y": float(corners[0]["y"])},
                {"x": float(corners[1]["x"]), "y": float(corners[1]["y"])},
            ],
            "metrics": metrics,
        }
    if shape == "ellipse":
        ell = geometry.get("ellipse")
        if isinstance(ell, dict) and "rx" in ell and "ry" in ell:
            cx = float(ell["cx"])
            cy = float(ell["cy"])
            rx = max(float(ell["rx"]), 1e-9)
            ry = max(float(ell["ry"]), 1e-9)
            eparams = {"cx": cx, "cy": cy, "rx": rx, "ry": ry}
        else:
            corners = geometry.get("corners")
            if not isinstance(corners, list) or len(corners) != 2:
                raise AppException(
                    code="INVALID_GEOMETRY",
                    message="ellipse area requires ellipse params or two corner points",
                    status_code=400,
                )
            eparams = ellipse_params_from_corners(corners[0], corners[1])
        outer = ellipse_outline(eparams)
        metrics_el = {
            "gross_area_pdf_sq": ellipse_area_pdf_sq(eparams),
            "void_area_pdf_sq": sum(polygon_area_abs(normalize_ring(h)) for h in holes if len(h) >= 3),
            "net_area_pdf_sq": 0.0,
            "perimeter_outer_pdf": ellipse_perimeter_approx(eparams),
            "perimeter_holes_pdf": 0.0,
            "perimeter_total_pdf": 0.0,
        }
        metrics_el["net_area_pdf_sq"] = max(
            0.0, metrics_el["gross_area_pdf_sq"] - metrics_el["void_area_pdf_sq"]
        )
        hsum = sum(
            open_polyline_len_closed(normalize_ring(h)) for h in holes if len(h) >= 3
        )
        metrics_el["perimeter_holes_pdf"] = hsum
        metrics_el["perimeter_total_pdf"] = metrics_el["perimeter_outer_pdf"] + hsum
        return {
            "type": "area",
            "shape": "ellipse",
            "outer": outer,
            "holes": holes,
            "ellipse": {k: float(v) for k, v in eparams.items()},
            "metrics": metrics_el,
        }

    # polygon
    raw_outer = geometry.get("outer")
    if not isinstance(raw_outer, list) or len(raw_outer) < 3:
        raise AppException(
            code="INVALID_GEOMETRY",
            message="polygon area requires outer ring with at least three vertices",
            status_code=400,
        )
    outer = []
    for p in raw_outer:
        if not isinstance(p, dict):
            raise AppException(code="INVALID_GEOMETRY", message="invalid outer vertex", status_code=400)
        outer.append({"x": float(p["x"]), "y": float(p["y"])})
    outer = normalize_ring(outer)
    if len(outer) < 3:
        raise AppException(code="INVALID_GEOMETRY", message="outer ring too small after normalize", status_code=400)

    metrics = compute_area_metrics(outer=outer, holes=holes)
    return {
        "type": "area",
        "shape": "polygon",
        "outer": outer,
        "holes": holes,
        "metrics": metrics,
    }


def open_polyline_len_closed(vertices: list[dict[str, float]]) -> float:
    n = len(vertices)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        j = (i + 1) % n
        total += math.hypot(vertices[j]["x"] - vertices[i]["x"], vertices[j]["y"] - vertices[i]["y"])
    return total


def _compute_measured_value(
    measurement_type: str,
    geometry: dict[str, Any],
    sheet: Sheet,
    condition: Condition,
    *,
    deductions: list[list[dict[str, Any]]] | None = None,
) -> float:
    if measurement_type == "linear":
        if condition.measurement_type != "linear":
            raise AppException(
                code="INVALID_CONDITION_TYPE",
                message="Condition measurement type does not support linear geometry",
                status_code=400,
            )
        verts = _parse_linear_vertices(geometry)
        ded = deductions if deductions is not None else []
        pdf_len = _linear_net_pdf_length(verts, ded)
        try:
            return linear_measured_value(pdf_len, sheet, condition)
        except ValueError as e:
            if str(e) == "sheet_not_calibrated":
                raise AppException(
                    code="SHEET_NOT_CALIBRATED",
                    message="Calibrate scale on this sheet before measuring",
                    status_code=409,
                ) from e
            raise

    if measurement_type == "area":
        if condition.measurement_type != "area":
            raise AppException(
                code="INVALID_CONDITION_TYPE",
                message="Condition measurement type does not support area geometry",
                status_code=400,
            )
        geom = (
            geometry
            if geometry.get("type") == "area" and isinstance(geometry.get("metrics"), dict)
            else _normalize_area_geometry(geometry)
        )
        net_pdf = float(geom["metrics"]["net_area_pdf_sq"])
        try:
            return area_measured_value(net_pdf, sheet, condition)
        except ValueError as e:
            if str(e) == "sheet_not_calibrated":
                raise AppException(
                    code="SHEET_NOT_CALIBRATED",
                    message="Calibrate scale on this sheet before measuring",
                    status_code=409,
                ) from e
            raise

    if measurement_type == "count":
        if condition.measurement_type != "count":
            raise AppException(
                code="INVALID_CONDITION_TYPE",
                message="Condition measurement type does not support count geometry",
                status_code=400,
            )
        _parse_count_geometry(geometry)
        return 1.0

    raise AppException(code="INVALID_MEASUREMENT_TYPE", message="Unknown measurement type", status_code=400)


async def _get_measurement(
    db: AsyncSession, org_id: uuid.UUID, measurement_id: uuid.UUID
) -> Measurement:
    stmt = select(Measurement).where(
        Measurement.id == measurement_id, Measurement.org_id == org_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise NotFoundException("measurement", str(measurement_id))
    return row


def _to_response(
    m: Measurement,
    derived: list[DerivedQuantityItem] | None = None,
    *,
    gross_measured_value: float | None = None,
) -> MeasurementResponse:
    geom = m.geometry if isinstance(m.geometry, dict) else {}
    ded_raw = m.deductions if isinstance(m.deductions, list) else []
    ded_out: list[dict[str, Any]] = [x for x in ded_raw if isinstance(x, dict)]
    return MeasurementResponse(
        id=m.id,
        org_id=m.org_id,
        project_id=m.project_id,
        sheet_id=m.sheet_id,
        condition_id=m.condition_id,
        measurement_type=m.measurement_type,
        geometry=geom,
        measured_value=m.measured_value,
        override_value=m.override_value,
        label=m.label,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
        derived_quantities=derived if derived is not None else [],
        deductions=ded_out,
        gross_measured_value=gross_measured_value,
    )


async def _load_derived_context(
    db: AsyncSession,
    org_id: uuid.UUID,
    measurements: list[Measurement],
) -> tuple[dict[uuid.UUID, Condition], dict[uuid.UUID, Sheet], dict[uuid.UUID, list[AssemblyItem]]]:
    if not measurements:
        return {}, {}, {}
    c_ids = list({m.condition_id for m in measurements})
    s_ids = list({m.sheet_id for m in measurements})
    cond_rows = (
        await db.execute(select(Condition).where(Condition.org_id == org_id, Condition.id.in_(c_ids)))
    ).scalars().all()
    sheet_rows = (
        await db.execute(select(Sheet).where(Sheet.org_id == org_id, Sheet.id.in_(s_ids)))
    ).scalars().all()
    item_rows = (
        await db.execute(
            select(AssemblyItem).where(
                AssemblyItem.org_id == org_id, AssemblyItem.condition_id.in_(c_ids)
            )
        )
    ).scalars().all()
    cd = {c.id: c for c in cond_rows}
    sd = {s.id: s for s in sheet_rows}
    by_c: dict[uuid.UUID, list[AssemblyItem]] = {}
    for it in item_rows:
        by_c.setdefault(it.condition_id, []).append(it)
    return cd, sd, by_c


def _derive_for_measurement(
    m: Measurement,
    cd: dict[uuid.UUID, Condition],
    sd: dict[uuid.UUID, Sheet],
    by_c: dict[uuid.UUID, list[AssemblyItem]],
) -> list[DerivedQuantityItem]:
    c = cd.get(m.condition_id)
    sh = sd.get(m.sheet_id)
    if not c or not sh:
        return []
    vars_ = build_formula_variables(m, sh, c)
    raw = evaluate_assembly_items(by_c.get(m.condition_id, []), vars_)
    return [
        DerivedQuantityItem(
            assembly_item_id=r["assembly_item_id"],
            name=r["name"],
            unit=r["unit"],
            value=r["value"],
            error=r["error"],
        )
        for r in raw
    ]


def _linear_gross_measured_for_row(
    m: Measurement,
    cd: dict[uuid.UUID, Condition],
    sd: dict[uuid.UUID, Sheet],
) -> float | None:
    if m.measurement_type != "linear":
        return None
    c = cd.get(m.condition_id)
    sh = sd.get(m.sheet_id)
    if not c or not sh or sh.scale_value is None:
        return None
    try:
        verts = _parse_linear_vertices(m.geometry if isinstance(m.geometry, dict) else {})
        pdf_len = polyline_length_pdf_points(verts)
        return linear_measured_value(pdf_len, sh, c)
    except (AppException, ValueError, KeyError, TypeError):
        return None


async def _responses_with_derived(
    db: AsyncSession, org_id: uuid.UUID, measurements: list[Measurement]
) -> list[MeasurementResponse]:
    cd, sd, by_c = await _load_derived_context(db, org_id, measurements)
    out: list[MeasurementResponse] = []
    for m in measurements:
        gross = _linear_gross_measured_for_row(m, cd, sd)
        out.append(
            _to_response(
                m,
                _derive_for_measurement(m, cd, sd, by_c),
                gross_measured_value=gross,
            )
        )
    return out


async def _aggregates_for_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    sheet_id: uuid.UUID | None,
) -> MeasurementAggregates:
    stmt_proj = (
        select(
            Measurement.condition_id,
            Measurement.measurement_type,
            func.count(Measurement.id),
            func.coalesce(func.sum(Measurement.measured_value), 0.0),
        )
        .where(Measurement.org_id == org_id, Measurement.project_id == project_id)
        .group_by(Measurement.condition_id, Measurement.measurement_type)
    )
    rows_proj = (await db.execute(stmt_proj)).all()

    project_rows = [
        MeasurementConditionAggregate(
            condition_id=r[0],
            measurement_type=str(r[1]),
            row_count=int(r[2]),
            sum_measured_value=float(r[3]),
        )
        for r in rows_proj
    ]

    sheet_rows: list[MeasurementConditionAggregate] = []
    if sheet_id is not None:
        stmt_sheet = (
            select(
                Measurement.condition_id,
                Measurement.measurement_type,
                func.count(Measurement.id),
                func.coalesce(func.sum(Measurement.measured_value), 0.0),
            )
            .where(
                Measurement.org_id == org_id,
                Measurement.project_id == project_id,
                Measurement.sheet_id == sheet_id,
            )
            .group_by(Measurement.condition_id, Measurement.measurement_type)
        )
        rows_sheet = (await db.execute(stmt_sheet)).all()
        sheet_rows = [
            MeasurementConditionAggregate(
                condition_id=r[0],
                measurement_type=str(r[1]),
                row_count=int(r[2]),
                sum_measured_value=float(r[3]),
            )
            for r in rows_sheet
        ]

    return MeasurementAggregates(sheet_by_condition=sheet_rows, project_by_condition=project_rows)


async def list_project_measurements(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    sheet_id: uuid.UUID | None = None,
    include_aggregates: bool = False,
) -> MeasurementListResponse:
    await project_service.get_project(db, org_id, project_id)
    stmt = select(Measurement).where(
        Measurement.org_id == org_id, Measurement.project_id == project_id
    )
    if sheet_id is not None:
        stmt = stmt.where(Measurement.sheet_id == sheet_id)
    stmt = stmt.order_by(Measurement.created_at.asc())
    rows = list((await db.execute(stmt)).scalars().all())
    measurements = await _responses_with_derived(db, org_id, rows)

    aggregates: MeasurementAggregates | None = None
    if include_aggregates:
        aggregates = await _aggregates_for_project(db, org_id, project_id, sheet_id=sheet_id)

    return MeasurementListResponse(measurements=measurements, aggregates=aggregates)


async def create_measurement(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: CreateMeasurementRequest,
) -> MeasurementResponse:
    await project_service.get_project(db, org_id, project_id)

    stmt_sh = select(Sheet).where(
        Sheet.id == body.sheet_id,
        Sheet.org_id == org_id,
        Sheet.project_id == project_id,
    )
    sheet = (await db.execute(stmt_sh)).scalar_one_or_none()
    if not sheet:
        raise NotFoundException("sheet", str(body.sheet_id))

    stmt_c = select(Condition).where(
        Condition.id == body.condition_id,
        Condition.org_id == org_id,
        Condition.project_id == project_id,
    )
    condition = (await db.execute(stmt_c)).scalar_one_or_none()
    if not condition:
        raise NotFoundException("condition", str(body.condition_id))

    if body.measurement_type != condition.measurement_type:
        raise AppException(
            code="CONDITION_TYPE_MISMATCH",
            message="Measurement type must match the selected condition",
            status_code=400,
        )

    if sheet.scale_value is None:
        raise AppException(
            code="SHEET_NOT_CALIBRATED",
            message="Calibrate scale on this sheet before measuring",
            status_code=409,
        )

    if body.measurement_type != "linear" and body.deductions:
        raise AppException(
            code="INVALID_DEDUCTIONS",
            message="deductions are only allowed for linear measurements",
            status_code=400,
        )

    geom = body.geometry if isinstance(body.geometry, dict) else {}

    deduction_polylines: list[list[dict[str, Any]]] = []
    if body.measurement_type == "linear":
        verts = _parse_linear_vertices(geom)
        geom_stored = _geometry_dict_linear(verts)
        deduction_polylines = _parse_linear_deductions(body.deductions)
        measured = _compute_measured_value(
            "linear", geom_stored, sheet, condition, deductions=deduction_polylines
        )
    elif body.measurement_type == "area":
        geom_stored = _normalize_area_geometry(geom)
        measured = _compute_measured_value("area", geom_stored, sheet, condition)
    elif body.measurement_type == "count":
        geom_stored = _parse_count_geometry(geom)
        measured = 1.0
    else:
        raise AppException(code="INVALID_MEASUREMENT_TYPE", message="Unknown measurement type", status_code=400)

    ded_stored: list[dict[str, Any]] = (
        _deduction_polylines_stored(deduction_polylines) if body.measurement_type == "linear" else []
    )
    m = Measurement(
        org_id=org_id,
        project_id=project_id,
        sheet_id=body.sheet_id,
        condition_id=body.condition_id,
        measurement_type=body.measurement_type,
        geometry=geom_stored,
        measured_value=measured,
        override_value=body.override_value,
        deductions=ded_stored,
        label=body.label,
        created_by=user_id,
    )
    db.add(m)
    await db.flush()
    await db.refresh(m)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        event_type="measurement.created",
        entity_type="measurement",
        entity_id=m.id,
        payload={"sheet_id": str(body.sheet_id), "condition_id": str(body.condition_id)},
    )
    out = await _responses_with_derived(db, org_id, [m])
    return out[0]


async def update_measurement(
    db: AsyncSession,
    org_id: uuid.UUID,
    measurement_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMeasurementRequest,
) -> MeasurementResponse:
    m = await _get_measurement(db, org_id, measurement_id)

    stmt_sh = select(Sheet).where(Sheet.id == m.sheet_id, Sheet.org_id == org_id)
    sheet = (await db.execute(stmt_sh)).scalar_one_or_none()
    if not sheet:
        raise NotFoundException("sheet", str(m.sheet_id))

    stmt_c = select(Condition).where(Condition.id == m.condition_id, Condition.org_id == org_id)
    condition = (await db.execute(stmt_c)).scalar_one_or_none()
    if not condition:
        raise NotFoundException("condition", str(m.condition_id))

    data = body.model_dump(exclude_unset=True)
    if not data:
        outs = await _responses_with_derived(db, org_id, [m])
        return outs[0]

    if "condition_id" in data and data["condition_id"] is not None:
        nid = data["condition_id"]
        if nid != m.condition_id:
            stmt_new = select(Condition).where(
                Condition.id == nid,
                Condition.org_id == org_id,
                Condition.project_id == m.project_id,
            )
            new_condition = (await db.execute(stmt_new)).scalar_one_or_none()
            if not new_condition:
                raise NotFoundException("condition", str(nid))
            if new_condition.measurement_type != m.measurement_type:
                raise AppException(
                    code="CONDITION_TYPE_MISMATCH",
                    message="New condition must have the same measurement type as the measurement",
                    status_code=400,
                )
            m.condition_id = nid
            deds = _stored_deduction_polylines(m)
            m.measured_value = _compute_measured_value(
                m.measurement_type,
                m.geometry,
                sheet,
                new_condition,
                deductions=deds if m.measurement_type == "linear" else None,
            )
            condition = new_condition

    if "geometry" in data and data["geometry"] is not None:
        if sheet.scale_value is None:
            raise AppException(
                code="SHEET_NOT_CALIBRATED",
                message="Calibrate scale on this sheet before measuring",
                status_code=409,
            )
        geom = data["geometry"] if isinstance(data["geometry"], dict) else {}
        mt = m.measurement_type
        if mt == "linear":
            verts = _parse_linear_vertices(geom)
            m.geometry = _geometry_dict_linear(verts)
            deds = _stored_deduction_polylines(m)
            m.measured_value = _compute_measured_value(
                "linear", m.geometry, sheet, condition, deductions=deds
            )
        elif mt == "area":
            m.geometry = _normalize_area_geometry(geom)
            m.measured_value = _compute_measured_value("area", m.geometry, sheet, condition)
        elif mt == "count":
            m.geometry = _parse_count_geometry(geom)
            m.measured_value = 1.0
        else:
            raise AppException(code="INVALID_MEASUREMENT_TYPE", message="Unknown measurement type", status_code=400)

    if "deductions" in data and data["deductions"] is not None:
        if m.measurement_type != "linear":
            raise AppException(
                code="INVALID_DEDUCTIONS",
                message="deductions apply only to linear measurements",
                status_code=400,
            )
        polylines = _parse_linear_deductions(data["deductions"])
        m.deductions = _deduction_polylines_stored(polylines)
        m.measured_value = _compute_measured_value(
            "linear", m.geometry, sheet, condition, deductions=polylines
        )

    if "label" in data:
        m.label = data["label"]
    if "override_value" in data:
        m.override_value = data["override_value"]

    await db.flush()
    await db.refresh(m)

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=m.project_id,
        event_type="measurement.edited",
        entity_type="measurement",
        entity_id=m.id,
        payload={"fields": list(data.keys())},
    )
    out = await _responses_with_derived(db, org_id, [m])
    return out[0]


async def delete_measurement(
    db: AsyncSession,
    org_id: uuid.UUID,
    measurement_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    m = await _get_measurement(db, org_id, measurement_id)
    pid = m.project_id

    await db.execute(
        delete(Measurement).where(
            Measurement.id == measurement_id, Measurement.org_id == org_id
        )
    )
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=pid,
        event_type="measurement.deleted",
        entity_type="measurement",
        entity_id=measurement_id,
        payload={},
    )
