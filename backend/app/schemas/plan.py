import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.plan import Plan as PlanModel
    from app.models.sheet import Sheet as SheetModel


class PlanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_size: int | None
    page_count: int | None
    status: str
    processed_pages: int
    #: ``extract`` | ``persist`` while processing; null when not applicable.
    processing_substep: str | None = None
    error_message: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, p: "PlanModel") -> "PlanResponse":
        """Single conversion path so adding a new column updates every endpoint at once."""
        return cls(
            id=p.id,
            project_id=p.project_id,
            filename=p.filename,
            file_size=p.file_size,
            page_count=p.page_count,
            status=p.status,
            processed_pages=p.processed_pages,
            processing_substep=p.processing_substep,
            error_message=p.error_message,
            uploaded_by=p.uploaded_by,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


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
    #: PDF vector line segments for snap-to-geometry; null if not extracted yet.
    vector_snap_segments: list[dict[str, float]] | None = None


class SheetListItemResponse(BaseModel):
    """Sheet row for project listing — omits heavy ``vector_snap_segments`` (see vector-snap endpoint)."""

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
    #: Signed URL omitted on list; use ``POST .../sheets/thumbnail-urls`` (or PATCH scale response).
    thumbnail_url: str | None = None
    created_at: datetime
    vector_snap_segment_count: int = 0

    @classmethod
    def from_model(cls, s: "SheetModel", *, thumbnail_url: str | None = None) -> "SheetListItemResponse":
        return cls(
            id=s.id,
            plan_id=s.plan_id,
            project_id=s.project_id,
            page_number=s.page_number,
            sheet_name=s.sheet_name,
            scale_value=s.scale_value,
            scale_unit=s.scale_unit,
            scale_label=s.scale_label,
            scale_source=s.scale_source,
            width_px=s.width_px,
            height_px=s.height_px,
            thumbnail_url=thumbnail_url,
            created_at=s.created_at,
            vector_snap_segment_count=s.vector_snap_segment_count,
        )


class SheetThumbnailUrlsRequest(BaseModel):
    """Batch-resolve signed thumbnail URLs for sheets in a project."""

    sheet_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class SheetThumbnailUrlsResponse(BaseModel):
    """Map sheet id (string) to signed URL or null when no thumbnail object."""

    urls: dict[str, str | None]


class SheetVectorSnapResponse(BaseModel):
    """Full snap segments for one sheet (lazy-loaded by the viewer)."""

    segments: list[dict[str, float]] | None = None


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
    sheets: list[SheetListItemResponse]


class PlanDocumentUrlResponse(BaseModel):
    """Short-lived signed URL for loading the raw PDF in the browser (e.g. pdf.js)."""

    url: str
    expires_in: int
