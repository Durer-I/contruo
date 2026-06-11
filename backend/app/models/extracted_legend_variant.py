import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, SmallInteger, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExtractedLegendVariant(Base):
    """One scaled+rotated PNG of an ``ExtractedLegend`` symbol.

    AI-03 produces 5 scales x 4 rotations = 20 variants per logical symbol so
    AI-06's template matcher can match symbols at the actual scale they're
    drawn on the plan without computing transforms at match time.

    Lives in its own table -- not as JSONB on ``extracted_legends`` and not as
    20 rows on ``extracted_legends`` -- to keep AI-04's resolver query, which
    only reads labels, light. AI-06 joins to this table when it actually needs
    the templates for matching.
    """

    __tablename__ = "extracted_legend_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    extracted_legend_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_legends.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: 0.70 / 0.85 / 1.00 / 1.15 / 1.30 by default -- the primary 1.00 row also
    #: lives here as a peer (denormalized one extra row to keep the variant
    #: query self-contained for AI-06).
    scale: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    #: 0 / 90 / 180 / 270.
    rotation: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    template_storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    template_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
