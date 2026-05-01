import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sheets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conditions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    measured_value: Mapped[float] = mapped_column(Float, nullable=False)
    override_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    deductions: Mapped[dict | list] = mapped_column(JSONB, nullable=False, server_default="[]")
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    #: 'user' (default) or 'ai'. AI-created measurements set this on accept.
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="user", default="user"
    )
    #: When ``source = 'ai'``, the run this measurement was promoted from. Lets
    #: us answer "show me everything created by Run #7" and bulk-undo a run.
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: Optimistic-lock counter. Bumped on every successful PATCH; clients that
    #: send ``If-Match: <version>`` get a 409 if their copy is stale.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
