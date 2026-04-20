"""PDF-space polygon / rectangle / ellipse areas and perimeters for area takeoff."""

from __future__ import annotations

import math
from typing import Any


def _pt(vertices: list[dict[str, Any]], i: int) -> tuple[float, float]:
    j = i % len(vertices)
    return float(vertices[j]["x"]), float(vertices[j]["y"])


def polygon_area_signed(vertices: list[dict[str, Any]]) -> float:
    """Shoelace signed area; positive if CCW in PDF coords (y down)."""
    n = len(vertices)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = _pt(vertices, i)
        x1, y1 = _pt(vertices, i + 1)
        s += x0 * y1 - x1 * y0
    return s / 2.0


def polygon_area_abs(vertices: list[dict[str, Any]]) -> float:
    return abs(polygon_area_signed(vertices))


def open_polyline_length(vertices: list[dict[str, Any]], *, closed: bool) -> float:
    """Edge length sum; if closed, includes edge from last to first."""
    n = len(vertices)
    if n < 2:
        return 0.0
    total = 0.0
    limit = n if closed else n - 1
    for i in range(limit):
        x0, y0 = _pt(vertices, i)
        x1, y1 = _pt(vertices, i + 1)
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def normalize_ring(vertices: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Drop duplicate closing point if first == last."""
    if len(vertices) < 3:
        out = []
        for p in vertices:
            out.append({"x": float(p["x"]), "y": float(p["y"])})
        return out
    out = [{"x": float(p["x"]), "y": float(p["y"])} for p in vertices]
    if len(out) >= 2 and out[0] == out[-1]:
        out = out[:-1]
    return out


def rectangle_from_corners(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, float]]:
    """Axis-aligned rectangle as CCW quad from two opposite corners."""
    x0, y0 = float(a["x"]), float(a["y"])
    x1, y1 = float(b["x"]), float(b["y"])
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)
    return [
        {"x": xmin, "y": ymin},
        {"x": xmax, "y": ymin},
        {"x": xmax, "y": ymax},
        {"x": xmin, "y": ymax},
    ]


def ellipse_params_from_corners(a: dict[str, Any], b: dict[str, Any]) -> dict[str, float]:
    """Axis-aligned ellipse from bounding box corners."""
    x0, y0 = float(a["x"]), float(a["y"])
    x1, y1 = float(b["x"]), float(b["y"])
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)
    rx = (xmax - xmin) / 2.0
    ry = (ymax - ymin) / 2.0
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    return {"cx": cx, "cy": cy, "rx": max(rx, 1e-9), "ry": max(ry, 1e-9)}


def ellipse_outline(ellipse: dict[str, Any], segments: int = 64) -> list[dict[str, float]]:
    """Sample an axis-aligned ellipse as a closed polygon in PDF space."""
    cx = float(ellipse["cx"])
    cy = float(ellipse["cy"])
    rx = float(ellipse["rx"])
    ry = float(ellipse["ry"])
    out: list[dict[str, float]] = []
    for i in range(segments):
        t = 2 * math.pi * i / segments
        out.append({"x": cx + rx * math.cos(t), "y": cy + ry * math.sin(t)})
    return out


def ellipse_area_pdf_sq(ellipse: dict[str, Any]) -> float:
    rx = float(ellipse["rx"])
    ry = float(ellipse["ry"])
    return math.pi * rx * ry


def ellipse_perimeter_approx(ellipse: dict[str, Any]) -> float:
    """Ramanujan-ish approximation for ellipse perimeter."""
    rx = float(ellipse["rx"])
    ry = float(ellipse["ry"])
    a, b = max(rx, ry), min(rx, ry)
    h = ((a - b) ** 2) / ((a + b) ** 2) if (a + b) > 0 else 0.0
    return math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))


def compute_area_metrics(
    *,
    outer: list[dict[str, float]],
    holes: list[list[dict[str, float]]],
) -> dict[str, float]:
    gross = polygon_area_abs(outer)
    void_area = sum(polygon_area_abs(normalize_ring(h)) for h in holes if len(h) >= 3)
    net = max(0.0, gross - void_area)
    per_outer = open_polyline_length(outer, closed=True)
    per_holes = sum(open_polyline_length(normalize_ring(h), closed=True) for h in holes if len(h) >= 3)
    return {
        "gross_area_pdf_sq": gross,
        "void_area_pdf_sq": void_area,
        "net_area_pdf_sq": net,
        "perimeter_outer_pdf": per_outer,
        "perimeter_holes_pdf": per_holes,
        "perimeter_total_pdf": per_outer + per_holes,
    }
