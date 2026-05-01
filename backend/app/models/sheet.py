import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Sheet(Base):
    __tablename__ = "sheets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: ``'auto'`` (extracted at upload or by AI Stage 1) | ``'manual'`` (user
    #: rename) | ``NULL`` (legacy; treated as ``'auto'``). Re-extract paths
    #: skip rows where this is ``'manual'`` so user edits are never clobbered.
    sheet_name_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: Real-world units (``scale_unit``) per PDF point — independent of zoom/canvas.
    scale_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scale_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: ``auto`` (from metadata/title block heuristics) or ``manual`` (user calibration).
    scale_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Cached extracted text layer for search (Sprint 06). Stored as a single blob, not searchable yet.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Line segments from PDF vector paths for snap-to-geometry (JSON list of {x1,y1,x2,y2} in PDF points).
    vector_snap_segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: AI-02 sheet classification. NULL until that sprint runs against the sheet.
    #: Allowed values mirror ``app.services.ai_sheet_classifier.ALL_DISCIPLINES``:
    #: 'architectural' | 'structural' | 'mechanical' | 'plumbing' | 'electrical'
    #: | 'fire_protection' | 'civil' | 'landscape' | 'telecom' | 'interiors'
    #: | 'general' | 'equipment' | 'other'.
    discipline: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: Mirrors ``app.services.ai_sheet_classifier.ALL_SHEET_TYPES``:
    #: 'plan' | 'elevation' | 'section' | 'detail' | 'schedule' | 'legend'
    #: | 'diagram' | 'cover' | 'index' | 'spec' | 'other'.
    sheet_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: 'lexical' | 'vision' | 'manual' -- which path produced the result.
    classification_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "page_number", name="uq_sheets_plan_page"),
    )
