"""Add optional vector segment index for snap-to-geometry (Sprint 15)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009_sheet_vector_snap"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sheets",
        sa.Column(
            "vector_snap_segments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("sheets", "vector_snap_segments")
