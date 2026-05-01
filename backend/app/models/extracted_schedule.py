import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExtractedSchedule(Base):
    """A schedule table extracted from a plan sheet by Stage 3a.

    Empty until AI-03 implements pdfplumber + vision-table extraction; the
    schema is defined here so the AI-01 pipeline scaffolding compiles.
    """

    __tablename__ = "extracted_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: PDF-points bbox: ``{"x0": ..., "y0": ..., "x1": ..., "y1": ...}``.
    bbox_pdf: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tag_column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ``{"headers": [...], "rows": [[...], ...]}``
    extracted_table_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    #: 'pdfplumber_lines' | 'pdfplumber_text' | 'vision'
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
