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
    #: Index (0-based) of the column the resolver should treat as the row's
    #: tag/MARK key (e.g. ``"D-101"`` for a door schedule). Heuristic-first;
    #: LLM fallback when the deterministic scorer is ambiguous. Nullable when
    #: no column matched the threshold.
    tag_column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Index of the column carrying the human description (e.g.
    #: ``"6'-0\" SOLID CORE"``). Used by AI-04 for condition naming.
    description_column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Index of the column carrying counts/quantities (rare on door schedules,
    #: common on equipment schedules). Used by AI-04 to suppress double-counting
    #: when a tag also appears on the plan via symbol detection.
    quantity_column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Indexes of dimension columns (width, height, depth, etc.). Stored as a
    #: JSON array because schedules can have 1-3 dimension columns -- a single
    #: int can't carry that.
    dimension_column_indexes: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    #: Index of a "material" / "type" column when present. Optional second axis
    #: AI-04 uses for condition disambiguation when the tag column alone is
    #: ambiguous (e.g. two doors share ``MARK = D101`` but differ by material).
    material_column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ``{"headers": [...], "rows": [[...], ...]}``
    extracted_table_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    #: ``'pdfplumber_lines'`` | ``'pdfplumber_lines_strict'`` |
    #: ``'pdfplumber_text'`` | ``'vision'``. Driver of cost telemetry --
    #: heuristic strategies are free, ``'vision'`` rows show non-zero
    #: ``tokens_used`` on the run.
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
