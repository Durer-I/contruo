import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiRun(Base):
    """One row per AI Auto-Takeoff pipeline invocation.

    Carries the full lifecycle of a run: status transitions, model snapshot,
    rolled-up cost/token totals, and a per-stage ``summary_jsonb`` populated
    incrementally by the Celery stage tasks.
    """

    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    #: ``'queued'`` | ``'running'`` | ``'completed'`` | ``'failed'`` |
    #: ``'cancelled'``. Column widened to VARCHAR(40) in migration 014 to
    #: leave room for future ``awaiting_*`` pause states (planned for
    #: AI-02b's title-block flow); only the five values above are written
    #: by current code.
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="queued"
    )
    #: Reserved for AI-future per-sheet runs; defaults to 'full_plan' today.
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="full_plan"
    )
    #: Snapshot of provider/model ids at run start so cache hits and divergences
    #: can be detected against the live config.
    model_versions: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    items_total: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    items_accepted_auto: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    items_pending: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    items_low_confidence: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    #: Per-stage timings, divergences, errors, and per-condition counts.
    #: Schema: {"stages": {"<stage_name>": {"duration_ms": int, "cost_cents": int,
    #: "tokens_used": int, "started_at": iso8601, "finished_at": iso8601,
    #: "cache_hit": bool, "error": str | None}}, "lock_state": "..."}.
    summary_jsonb: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
