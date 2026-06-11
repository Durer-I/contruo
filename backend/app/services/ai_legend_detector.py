"""Stage 3a: legend symbol detector.

Implements ``AI/controller/legends.py`` verbatim (group rects, dominant size,
``has_text_inside``, right-adjacent ``get_adjacent_text``, ``merge_rects``), then
optional GPT cleanup of false positives (the commented block in the prototype).

Outputs ``LegendCandidate`` rows for ``ai_legend_extractor`` (fitz bbox:
``x0,y0,x1,y1`` with ``y0`` = top, ``y1`` = bottom in pdfplumber-aligned space).
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.services.ai_legend_cleanup import filter_merged_results_with_llm

logger = logging.getLogger(__name__)

#: Matches ``AI/controller/legends.py`` ``min_size = 16``.
PROTOTYPE_MIN_SIZE_PTS = 16.0


@dataclass
class LegendCandidate:
    """A detected legend symbol on a single sheet."""

    bbox_pdf: dict[str, float]
    label: str
    extraction_method: str
    confidence: float
    sibling_count: int = 1
    notes: dict[str, Any] = field(default_factory=dict)


def has_text_inside(
    rect: dict[str, Any], words: list[dict[str, Any]], tol: float = 0
) -> bool:
    for w in words:
        if w["x1"] < rect["x0"] - tol or w["x0"] > rect["x1"] + tol:
            continue
        if (
            w["x0"] >= rect["x0"] - tol
            and w["x1"] <= rect["x1"] + tol
            and w["top"] >= rect["top"] - tol
            and w["bottom"] <= rect["bottom"] + tol
        ):
            return True
    return False


def get_adjacent_text(
    rect: dict[str, Any],
    words: list[dict[str, Any]],
    *,
    x_tol: float = 10,
    y_tol: float = 3,
    max_gap: float = 200,
) -> list[dict[str, Any]]:
    matched_words: list[dict[str, Any]] = []
    for w in words:
        if w["bottom"] < rect["top"] - y_tol or w["top"] > rect["bottom"] + y_tol:
            continue
        if rect["x1"] - x_tol <= w["x0"] <= rect["x1"] + max_gap:
            matched_words.append(w)
    return sorted(matched_words, key=lambda w: w["x0"])


def merge_rects_pdfplumber(rects: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "x0": min(r["x0"] for r in rects),
        "x1": max(r["x1"] for r in rects),
        "top": min(r["top"] for r in rects),
        "bottom": max(r["bottom"] for r in rects),
    }


def _pdfplumber_merged_to_bbox_pdf(merged: dict[str, float]) -> dict[str, float]:
    """pdfplumber top/bottom -> keys expected by fitz clip in ``ai_legend_extractor``."""
    return {
        "x0": float(merged["x0"]),
        "y0": float(merged["top"]),
        "x1": float(merged["x1"]),
        "y1": float(merged["bottom"]),
    }


def detect_legend_symbols(
    *,
    plumber_page: Any,
    tolerance: float | None = None,
) -> list[LegendCandidate]:
    """Run prototype detection + optional LLM cleanup; return ``LegendCandidate`` list."""
    settings = get_settings()
    tol = tolerance if tolerance is not None else settings.ai_legend_merge_tolerance

    try:
        rectangles = list(plumber_page.rects or [])
        words = list(plumber_page.extract_words() or [])
    except Exception:
        logger.exception("legend_detector: pdfplumber raised reading rects/words")
        return []

    if not rectangles:
        return []

    for r in rectangles:
        r["rx0"] = round(float(r.get("x0", 0.0)) / tol) * tol
        r["rx1"] = round(float(r.get("x1", 0.0)) / tol) * tol
        r["rwidth"] = round(float(r.get("width", 0.0)) / tol) * tol
        r["rheight"] = round(float(r.get("height", 0.0)) / tol) * tol

    groups: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    for r in rectangles:
        groups[(r["rx0"], r["rx1"])].append(r)

    label_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rects in groups.values():
        if len(rects) <= 1:
            continue
        size_count = Counter((r["rwidth"], r["rheight"]) for r in rects)
        most_common_size = size_count.most_common(1)[0][0]

        for r in rects:
            if (r["rwidth"], r["rheight"]) != most_common_size:
                continue
            if r["width"] < PROTOTYPE_MIN_SIZE_PTS or r["height"] < PROTOTYPE_MIN_SIZE_PTS:
                continue
            if has_text_inside(r, words):
                continue
            adjacent_words = get_adjacent_text(r, words)
            if not adjacent_words:
                continue
            text = " ".join(str(w.get("text", "")) for w in adjacent_words).strip()
            if text:
                label_map[text].append(r)

    merged_results: dict[str, dict[str, float]] = {
        text: merge_rects_pdfplumber(rects) for text, rects in label_map.items()
    }

    merged_results = filter_merged_results_with_llm(merged_results)

    out: list[LegendCandidate] = []
    for label, merged_pl in merged_results.items():
        rects = label_map.get(label, [])
        sibling_count = len(rects) if rects else 1
        bbox_pdf = _pdfplumber_merged_to_bbox_pdf(merged_pl)
        out.append(
            LegendCandidate(
                bbox_pdf=bbox_pdf,
                label=label,
                extraction_method="pdfplumber_legends_proto",
                confidence=1.0,
                sibling_count=sibling_count,
                notes={},
            )
        )
    return out


def serialize_candidates(candidates: list[LegendCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "bbox_pdf": dict(c.bbox_pdf),
            "label": c.label,
            "extraction_method": c.extraction_method,
            "confidence": float(c.confidence),
            "sibling_count": int(c.sibling_count),
            "notes": dict(c.notes),
        }
        for c in candidates
    ]


def deserialize_candidates(payload: list[dict[str, Any]]) -> list[LegendCandidate]:
    out: list[LegendCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                LegendCandidate(
                    bbox_pdf=dict(item.get("bbox_pdf") or {}),
                    label=str(item.get("label") or ""),
                    extraction_method=str(item.get("extraction_method") or ""),
                    confidence=float(item.get("confidence") or 0.0),
                    sibling_count=int(item.get("sibling_count") or 1),
                    notes=dict(item.get("notes") or {}),
                )
            )
        except Exception:
            logger.exception("Failed to deserialize LegendCandidate; skipping item")
    return out


__all__ = [
    "LegendCandidate",
    "detect_legend_symbols",
    "deserialize_candidates",
    "get_adjacent_text",
    "has_text_inside",
    "merge_rects_pdfplumber",
    "serialize_candidates",
]
