"""Heuristic scale detection from PDF metadata and page text (title blocks).

Stores calibration as **real-world units per PDF point** (``scale_value`` + ``scale_unit``),
which is zoom-independent and matches manual calibration from a drawn line.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# PDF user space units match 1/72 inch per point; 1 inch = 72 points.
_PTS_PER_INCH = 72.0
_MM_PER_INCH = 25.4


@dataclass(frozen=True)
class DetectedScale:
    scale_value: float
    scale_unit: str  # 'ft' | 'm'
    scale_label: str


def _feet_per_pdf_point_from_inch_scale(
    drawing_inches: float, real_feet: float
) -> float:
    """Given a segment of ``drawing_inches`` on the PDF that represents ``real_feet`` real."""
    if drawing_inches <= 0 or real_feet <= 0:
        raise ValueError("positive lengths required")
    return real_feet / (drawing_inches * _PTS_PER_INCH)


def _meters_per_pdf_point_from_ratio(denominator: int) -> float:
    """Architectural metric 1:N where 1 mm on the plan = N mm in reality."""
    if denominator <= 0:
        raise ValueError("positive ratio required")
    mm_per_pt = _MM_PER_INCH / _PTS_PER_INCH
    return (mm_per_pt * denominator) / 1000.0


# e.g. 1/4" = 1'-0"  or  1/4" = 1' - 0"
_RE_ARCH_EQ = re.compile(
    r"""
    (?P<num>\d+)\s*/\s*(?P<den>\d+)\s*["\u201d]\s*
    [=]\s*
    (?P<ft>\d+)\s*['\u2019]\s*
    (?:[-\u2013]?\s*(?P<inch>\d+)\s*["\u201d])?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# e.g. 1" = 10'  or  1" = 10'-0"
_RE_INCH_TO_FEET = re.compile(
    r"""
    (?P<din>\d+(?:\.\d+)?)\s*["\u201d]\s*
    [=]\s*
    (?P<ft>\d+(?:\.\d+)?)\s*['\u2019]
    (?:\s*(?:[-\u2013]\s*)?(?P<fin>\d+(?:\.\d+)?)\s*["\u201d])?
    """,
    re.VERBOSE | re.IGNORECASE,
)

# e.g. Scale: 1:100  or  SCALE 1 : 48
_RE_RATIO = re.compile(
    r"""
    \b(?:scale\s*)?[:.]?\s*
    1\s*:\s*(?P<n>\d+)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)


def detect_scale_from_text(text: str) -> DetectedScale | None:
    """Scan extracted page text for common architectural scale notations."""
    if not text or not text.strip():
        return None

    sample = text[:12000]

    m = _RE_ARCH_EQ.search(sample)
    if m:
        num, den = int(m.group("num")), int(m.group("den"))
        if den <= 0:
            return None
        drawing_inches = num / den
        real_feet = float(m.group("ft"))
        if m.group("inch"):
            real_feet += float(m.group("inch")) / 12.0
        try:
            fpp = _feet_per_pdf_point_from_inch_scale(drawing_inches, real_feet)
        except ValueError:
            return None
        label = f'{num}/{den}" = {m.group("ft")}\'-0"'
        return DetectedScale(scale_value=fpp, scale_unit="ft", scale_label=label)

    m2 = _RE_INCH_TO_FEET.search(sample)
    if m2:
        drawing_inches = float(m2.group("din"))
        real_feet = float(m2.group("ft"))
        if m2.group("fin"):
            real_feet += float(m2.group("fin")) / 12.0
        try:
            fpp = _feet_per_pdf_point_from_inch_scale(drawing_inches, real_feet)
        except ValueError:
            return None
        return DetectedScale(
            scale_value=fpp,
            scale_unit="ft",
            scale_label=f'{m2.group("din")}" = {real_feet:g}\'',
        )

    m3 = _RE_RATIO.search(sample)
    if m3:
        n = int(m3.group("n"))
        # Only accept common drawing scales to avoid misreading unrelated "1:20" ratios.
        _metric = {50, 75, 100, 125, 150, 200, 250, 500, 1000}
        _imperial = {24, 48, 96, 120, 192}
        if n in _metric:
            try:
                mpp = _meters_per_pdf_point_from_ratio(n)
            except ValueError:
                return None
            return DetectedScale(
                scale_value=mpp,
                scale_unit="m",
                scale_label=f"1:{n}",
            )
        if n in _imperial:
            # 1 inch on the plan = N inches in the field.
            real_feet = n / 12.0
            try:
                fpp = _feet_per_pdf_point_from_inch_scale(1.0, real_feet)
            except ValueError:
                return None
            return DetectedScale(
                scale_value=fpp,
                scale_unit="ft",
                scale_label=f"1:{n}",
            )

    return None


def _metadata_blob(meta: dict[str, str | None]) -> str:
    parts: list[str] = []
    for k in ("subject", "title", "keywords", "creator", "producer"):
        v = meta.get(k)
        if v:
            parts.append(str(v))
    return "\n".join(parts)


def detect_scale_from_metadata(meta: dict[str, str | None]) -> DetectedScale | None:
    """Try to parse scale hints from the PDF Info dictionary."""
    blob = _metadata_blob(meta)
    if not blob.strip():
        return None
    return detect_scale_from_text(blob)


def detect_scale(
    page_text: str,
    *,
    pdf_metadata: dict[str, str | None] | None = None,
) -> DetectedScale | None:
    """Prefer explicit page text; fall back to document metadata."""
    hit = detect_scale_from_text(page_text)
    if hit:
        return hit
    if pdf_metadata:
        hit = detect_scale_from_metadata(pdf_metadata)
    return hit


def compute_scale_from_calibration_line(
    pdf_line_length_points: float,
    real_distance: float,
    real_unit: str,
) -> DetectedScale:
    """Compute stored scale from a user-drawn calibration segment (manual)."""
    u = real_unit.lower().strip()
    if pdf_line_length_points <= 0 or real_distance <= 0:
        raise ValueError("Lengths must be positive")
    if u in ("ft", "feet", "'"):
        per_pt = real_distance / pdf_line_length_points
        return DetectedScale(per_pt, "ft", f"{real_distance:g} ft (manual)")
    if u in ("in", "inch", "inches", '"'):
        per_ft = real_distance / 12.0
        per_pt = per_ft / pdf_line_length_points
        return DetectedScale(per_pt, "ft", f"{real_distance:g} in (manual)")
    if u in ("m", "meter", "meters", "metre", "metres"):
        per_pt = real_distance / pdf_line_length_points
        return DetectedScale(per_pt, "m", f"{real_distance:g} m (manual)")
    if u in ("mm", "millimeter", "millimeters"):
        per_pt = (real_distance / 1000.0) / pdf_line_length_points
        return DetectedScale(per_pt, "m", f"{real_distance:g} mm (manual)")
    if u in ("cm", "centimeter", "centimeters"):
        per_pt = (real_distance / 100.0) / pdf_line_length_points
        return DetectedScale(per_pt, "m", f"{real_distance:g} cm (manual)")
    raise ValueError(f"Unsupported real_unit: {real_unit!r}")


def format_scale_for_status(
    scale_value: float | None,
    scale_unit: str | None,
    scale_label: str | None,
) -> str:
    """Human-readable scale for status bar / UI."""
    if scale_value is None or not scale_unit:
        return "Not calibrated"
    if scale_label:
        return scale_label
    u = scale_unit.lower()
    if u == "ft":
        inv = 1.0 / scale_value if scale_value > 0 else float("nan")
        if math.isfinite(inv) and inv > 1:
            return f"~{inv:.1f} ft/pt"
        return f"{scale_value:.6g} ft/pt"
    inv_m = 1.0 / scale_value if scale_value > 0 else float("nan")
    if math.isfinite(inv_m):
        return f"~{inv_m:.3g} m/pt"
    return f"{scale_value:.6g} m/pt"
