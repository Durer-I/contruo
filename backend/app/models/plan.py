import uuid
from datetime import datetime

from sqlalchemy import String, Text, BigInteger, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="processing"
    )
    #: Null until processing completes or fails. Populated by Celery worker during page extraction.
    processed_pages: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    #: During ``status=processing``: ``extract`` (PDF pages) or ``persist`` (DB sheet rows); null when idle/ready.
    processing_substep: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    #: Title-block region in PDF user-space points (origin top-left, y down):
    #: ``{"x0": float, "y0": float, "x1": float, "y1": float}``. Null until
    #: AI-02b's manual-bbox flow lands. Reused across every sheet in the plan
    #: because title-block geometry is constant per sheet set. Column kept
    #: from migration 014 so AI-02b can drop straight in.
    title_block_bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: AI-02b: 1.0 when the user draws the bbox; reserved for a future
    #: confidence score if auto-detection is ever revisited.
    title_block_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: ``'manual'`` (user-drawn bbox) reserved values: ``'auto'`` /
    #: ``'vision'`` for any future detection path. Currently always 'manual'
    #: when set, NULL otherwise.
    title_block_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
