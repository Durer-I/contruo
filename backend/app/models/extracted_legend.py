import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExtractedLegend(Base):
    """A single legend symbol cropped from a plan sheet by Stage 3a.

    Empty until AI-03 implements legend region detection + symbol cropping; the
    schema is defined here so the AI-01 pipeline scaffolding compiles.
    """

    __tablename__ = "extracted_legends"

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
    bbox_pdf: Mapped[dict] = mapped_column(JSONB, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Supabase Storage path: ``legends/{plan_id}/{legend_label}.png``.
    template_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    #: SHA-256 of the cropped template bytes -- drives cache invalidation when
    #: a re-uploaded plan revision changes the legend artwork.
    template_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 'vector' | 'raster' | 'vision'
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
