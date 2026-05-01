import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    line_style: Mapped[str] = mapped_column(String(20), nullable=False, server_default="solid")
    line_width: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.0")
    fill_opacity: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3")
    fill_pattern: Mapped[str] = mapped_column(String(20), nullable=False, server_default="solid")
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    trade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: 'user' (default) | 'template_clone' | 'ai_created' | 'imported'.
    #: Drives the "This condition was created by AI. Save to your team library?"
    #: nudge in the AI-04 condition resolver.
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="user", default="user"
    )
    #: When ``source = 'template_clone'``, the org template the resolver cloned.
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("condition_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: When ``source = 'ai_created'``, the run that created this condition.
    source_ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
