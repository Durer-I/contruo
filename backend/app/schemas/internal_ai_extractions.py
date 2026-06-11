"""Internal-only response shapes for the AI extractions debug endpoint.

Not part of the public API contract -- field shape can change as long as the
consumers in ``frontend/app/internal/ai/...`` are updated in lockstep. The
endpoint is owner+admin-only.
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class ExtractedScheduleRow(BaseModel):
    id: uuid.UUID
    sheet_id: uuid.UUID
    sheet_name: str | None
    sheet_number: str | None
    page_number: int | None
    bbox_pdf: dict[str, float]
    extraction_method: str
    tag_column_index: int | None
    description_column_index: int | None
    quantity_column_index: int | None
    dimension_column_indexes: list[int] | None
    material_column_index: int | None
    headers: list[str]
    row_count: int
    #: First N rows of the extracted table; UI shows the full table on demand.
    sample_rows: list[list[str]]


class ExtractedLegendVariantRow(BaseModel):
    scale: float
    rotation: int
    template_storage_path: str
    signed_url: str | None


class ExtractedLegendRow(BaseModel):
    id: uuid.UUID
    sheet_id: uuid.UUID
    sheet_name: str | None
    sheet_number: str | None
    page_number: int | None
    label: str
    bbox_pdf: dict[str, float]
    template_hash: str
    template_storage_path: str
    primary_signed_url: str | None
    extraction_method: str
    variants: list[ExtractedLegendVariantRow]


class AiRunExtractionsResponse(BaseModel):
    ai_run_id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    schedules: list[ExtractedScheduleRow]
    legends: list[ExtractedLegendRow]
    summary: dict[str, Any]
