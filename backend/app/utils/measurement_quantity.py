"""Convert PDF polyline length to stored ``measured_value`` using sheet scale + condition unit."""

from __future__ import annotations

import math
from typing import Any

from app.models.condition import Condition
from app.models.sheet import Sheet


def polyline_length_pdf_points(vertices: list[dict[str, Any]]) -> float:
    """Sum of segment lengths in PDF user space (points)."""
    if len(vertices) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(vertices)):
        try:
            x0 = float(vertices[i - 1]["x"])
            y0 = float(vertices[i - 1]["y"])
            x1 = float(vertices[i]["x"])
            y1 = float(vertices[i]["y"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid vertex") from None
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def linear_measured_value(
    pdf_length_points: float,
    sheet: Sheet,
    condition: Condition,
) -> float:
    """Real-world length in the condition's primary unit (e.g. LF, m)."""
    if sheet.scale_value is None:
        raise ValueError("sheet_not_calibrated")
    raw = pdf_length_points * sheet.scale_value
    su = (sheet.scale_unit or "ft").lower()
    cu = condition.unit.strip().upper()

    def lf_like() -> bool:
        return cu in ("LF", "FT", "'", "LS") or "LF" in cu

    def metric_line() -> bool:
        return cu in ("M",) or cu == "LINEAR M"

    if su == "ft":
        feet = raw
        if lf_like():
            return feet
        if metric_line():
            return feet * 0.3048
        return feet
    meters = raw
    if metric_line():
        return meters
    if lf_like():
        return meters * 3.280839895
    return meters


def area_measured_value(
    pdf_area_sq_points: float,
    sheet: Sheet,
    condition: Condition,
) -> float:
    """Real-world area in the condition's primary unit (e.g. SF, m²)."""
    if sheet.scale_value is None:
        raise ValueError("sheet_not_calibrated")
    area_real = pdf_area_sq_points * (sheet.scale_value**2)
    su = (sheet.scale_unit or "ft").lower()
    cu = condition.unit.strip().upper().replace("²", "2")

    def imperial_area() -> float:
        if cu in ("SF", "SQ FT", "FT2", "SQUARE FEET", "SF."):
            return area_real
        if cu in ("SY", "SQ YD", "SY."):
            return area_real / 9.0
        if cu in ("M2", "SQM"):
            return area_real * 0.09290304
        return area_real

    def metric_area() -> float:
        if cu in ("M2", "SQM", "M²"):
            return area_real
        if cu in ("SF", "SQ FT", "FT2", "SQUARE FEET"):
            return area_real / 0.09290304
        if cu in ("SY", "SQ YD"):
            return area_real / 0.83612736
        return area_real

    if su == "ft":
        return imperial_area()
    return metric_area()
