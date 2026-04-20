"""Build formula variable context from a measurement + condition + sheet."""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from app.models.condition import Condition
from app.models.measurement import Measurement
from app.models.sheet import Sheet
from app.models.assembly_item import AssemblyItem
from app.services.formula_engine import FormulaError, evaluate_formula
from app.utils.measurement_quantity import linear_measured_value

_LF_STUB = SimpleNamespace(unit="LF", measurement_type="linear")


def _sanitize_var_key(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip())
    if s and s[0].isdigit():
        s = "_" + s
    return s or "_"


def build_preview_variables(
    measurement_type: str,
    primary: float,
    perimeter_real: float,
    condition: Condition,
) -> dict[str, float]:
    """Variables for formula preview without a persisted measurement."""
    ctx: dict[str, float] = {
        "length": 0.0,
        "area": 0.0,
        "count": 0.0,
        "perimeter": 0.0,
    }
    if measurement_type == "linear":
        ctx["length"] = float(primary)
    elif measurement_type == "area":
        ctx["area"] = float(primary)
        ctx["perimeter"] = float(perimeter_real)
    elif measurement_type == "count":
        ctx["count"] = float(primary)

    props = condition.properties if isinstance(condition.properties, dict) else {}
    custom = props.get("custom")
    if isinstance(custom, list):
        for row in custom:
            if not isinstance(row, dict):
                continue
            raw_name = row.get("name")
            if not raw_name or not str(raw_name).strip():
                continue
            key = _sanitize_var_key(str(raw_name))
            raw_val = str(row.get("value", "")).strip()
            try:
                ctx[key] = float(raw_val) if raw_val else 0.0
            except ValueError:
                ctx[key] = 0.0
    return ctx


def build_formula_variables(
    measurement: Measurement,
    sheet: Sheet,
    condition: Condition,
) -> dict[str, float]:
    """Variables available to assembly formulas for this measurement."""
    primary = float(measurement.override_value) if measurement.override_value is not None else float(
        measurement.measured_value
    )
    geom = measurement.geometry if isinstance(measurement.geometry, dict) else {}
    mt = measurement.measurement_type

    ctx: dict[str, float] = {
        "length": 0.0,
        "area": 0.0,
        "count": 0.0,
        "perimeter": 0.0,
    }
    if mt == "linear":
        ctx["length"] = primary
    elif mt == "area":
        ctx["area"] = primary
        metrics = geom.get("metrics")
        if isinstance(metrics, dict):
            p_pdf = float(metrics.get("perimeter_total_pdf", 0.0) or 0.0)
            try:
                ctx["perimeter"] = linear_measured_value(p_pdf, sheet, _LF_STUB)  # type: ignore[arg-type]
            except ValueError:
                ctx["perimeter"] = 0.0
    elif mt == "count":
        ctx["count"] = primary

    props = condition.properties if isinstance(condition.properties, dict) else {}
    custom = props.get("custom")
    if isinstance(custom, list):
        for row in custom:
            if not isinstance(row, dict):
                continue
            raw_name = row.get("name")
            if not raw_name or not str(raw_name).strip():
                continue
            key = _sanitize_var_key(str(raw_name))
            raw_val = str(row.get("value", "")).strip()
            try:
                ctx[key] = float(raw_val) if raw_val else 0.0
            except ValueError:
                ctx[key] = 0.0
    return ctx


def evaluate_assembly_items(
    items: list[AssemblyItem],
    variables: dict[str, float],
) -> list[dict[str, Any]]:
    """Return list of dicts: assembly_item_id, name, unit, value|error."""
    out: list[dict[str, Any]] = []
    for it in sorted(items, key=lambda x: (x.sort_order, str(x.id))):
        try:
            val = evaluate_formula(it.formula, variables)
        except FormulaError as e:
            out.append(
                {
                    "assembly_item_id": it.id,
                    "name": it.name,
                    "unit": it.unit,
                    "value": None,
                    "error": e.message,
                }
            )
        else:
            out.append(
                {
                    "assembly_item_id": it.id,
                    "name": it.name,
                    "unit": it.unit,
                    "value": val,
                    "error": None,
                }
            )
    return out
