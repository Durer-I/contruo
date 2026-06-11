"""GPT false-positive filter for prototype legend detection (``AI/controller/legends.py``).

Ports the commented cleanup block from the prototype script: given a JSON array of
label + bbox rows, return which row indices to keep. Uses OpenAI strict JSON-schema
mode; on failure or when disabled, returns the input unchanged.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from app.config import get_settings
from app.services.ai_models import OpenAILLMModel, get_legend_cleanup_llm

logger = logging.getLogger(__name__)

_LEGEND_CLEANUP_PROMPT = """You are given a JSON array of coordinates and label data for supposedly legends on a PDF page.

Your task is to analyze this data and remove any false positives. Keep only rows that are most likely to be construction-drawing legend symbols (short equipment/tag labels next to small rectangles).

False positives often have labels that are gibberish, full sentences, notes, dimensions, or text that could not be a legend entry.

Return only the zero-based indices of rows to KEEP (from the input array order). If nothing should be kept, return an empty array."""


def _cleanup_schema() -> dict[str, Any]:
    return {
        "title": "legend_cleanup",
        "type": "object",
        "properties": {
            "keep_indices": {
                "type": "array",
                "items": {"type": "integer"},
            }
        },
        "required": ["keep_indices"],
        "additionalProperties": False,
    }


def filter_merged_results_with_llm(
    merged_results: dict[str, dict[str, float]],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, dict[str, float]]:
    """Filter prototype ``merged_results`` (label -> pdfplumber bbox) via LLM.

    ``merged_results`` values use keys ``x0``, ``x1``, ``top``, ``bottom`` (pdfplumber).
    """
    settings = get_settings()
    if not settings.ai_legend_cleanup_enabled:
        return merged_results
    if not merged_results:
        return merged_results

    factory = llm_factory or get_legend_cleanup_llm
    llm = factory()
    if not isinstance(llm, OpenAILLMModel):
        logger.warning(
            "legend_cleanup: only OpenAILLMModel.structured_output is supported; "
            "skipping cleanup (provider=%s)",
            type(llm).__name__,
        )
        return merged_results

    labels_ordered = sorted(merged_results.keys())
    rows = [
        {
            "index": i,
            "label": lab,
            "bbox": {
                "x0": merged_results[lab]["x0"],
                "x1": merged_results[lab]["x1"],
                "top": merged_results[lab]["top"],
                "bottom": merged_results[lab]["bottom"],
            },
        }
        for i, lab in enumerate(labels_ordered)
    ]
    payload = json.dumps(rows, indent=2)
    prompt = _LEGEND_CLEANUP_PROMPT + "\n\nINPUT:\n" + payload

    try:
        result = llm.structured_output(prompt, schema=_cleanup_schema())
    except Exception:
        logger.exception("legend_cleanup: LLM call failed; keeping all prototype rows")
        return merged_results

    if not isinstance(result, dict):
        return merged_results
    raw_indices = result.get("keep_indices")
    if not isinstance(raw_indices, list):
        return merged_results

    n = len(labels_ordered)
    keep: set[int] = set()
    for x in raw_indices:
        if isinstance(x, int) and 0 <= x < n:
            keep.add(x)

    out: dict[str, dict[str, float]] = {}
    for i in sorted(keep):
        lab = labels_ordered[i]
        out[lab] = dict(merged_results[lab])
    return out


__all__ = ["filter_merged_results_with_llm"]
