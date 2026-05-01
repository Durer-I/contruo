import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiStageCache(Base):
    """Per-stage output cache keyed by ``(org_id, content_hash, stage, model_version)``.

    Re-runs on unchanged sheets short-circuit by reading the cached payload and
    skipping the stage body. ``hit_count`` and ``last_accessed_at`` are bumped
    on every hit so we can spot hot keys and prune cold ones later.
    """

    __tablename__ = "ai_stage_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    #: SHA-256 of the stage's input payload (PDF bytes for the sheet, scale
    #: calibration, model id, etc.) -- see ``ai_cache.compute_sheet_content_hash``.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Provider+model id snapshot, e.g. ``anthropic:claude-sonnet-4-5``.
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    value_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hit_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "content_hash",
            "stage",
            "model_version",
            name="uq_ai_stage_cache_key",
        ),
    )
