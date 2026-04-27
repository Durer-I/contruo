"""Optional project cover image path (Supabase Storage)."""

from alembic import op
import sqlalchemy as sa

revision = "010_project_cover"
down_revision = "009_sheet_vector_snap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("cover_image_path", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "cover_image_path")
