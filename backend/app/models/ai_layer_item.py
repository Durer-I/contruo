import uuid
from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiLayerItem(Base):
    """A single AI-detected geometric primitive awaiting accept/reject.

    Layer items are the AI Layer's source of truth -- they live alongside (not
    inside) the user's measurements until the resolver picks a condition and the
    user (or the auto-accept threshold) promotes them to a real Measurement row.
    """

    __tablename__ = "ai_layer_items"

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
    #: Nullable until the resolver runs in Stage 6.
    condition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conditions.id", ondelete="SET NULL"),
        nullable=True,
    )
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Geometry in PDF user space points -- same shape as ``measurements.geometry``.
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    #: Pipeline stage that produced this primitive.
    source_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    #: 'pending' | 'accepted_auto' | 'accepted_user' | 'rejected'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    #: Free-form per-item metadata: matched_legend_label, source_template_id,
    #: divergence info, etc.
    metadata_jsonb: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    #: When status=accepted_*, the resulting measurement row id (denormalized
    #: for cheap "highlight on plan" lookups in the review panel).
    accepted_measurement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
