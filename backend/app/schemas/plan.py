import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_size: int | None
    page_count: int | None
    status: str
    processed_pages: int
    error_message: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]


class SheetResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    project_id: uuid.UUID
    page_number: int
    sheet_name: str | None
    scale_value: float | None
    scale_unit: str | None
    scale_label: str | None
    scale_source: str | None = None
    width_px: int | None
    height_px: int | None
    thumbnail_url: str | None = None
    created_at: datetime


class PatchSheetScaleRequest(BaseModel):
    """Manual calibration: real distance along a segment measured in PDF points."""

    pdf_line_length_points: float = Field(gt=0)
    real_distance: float = Field(gt=0)
    real_unit: str = Field(min_length=1, max_length=20)


class SearchHit(BaseModel):
    sheet_id: uuid.UUID
    plan_id: uuid.UUID
    page_number: int
    sheet_name: str | None
    snippet: str
    match_char_offset: int | None = None


class ProjectSearchResponse(BaseModel):
    query: str
    matches: list[SearchHit]


class SheetListResponse(BaseModel):
    sheets: list[SheetResponse]


class PlanDocumentUrlResponse(BaseModel):
    """Short-lived signed URL for loading the raw PDF in the browser (e.g. pdf.js)."""

    url: str
    expires_in: int
