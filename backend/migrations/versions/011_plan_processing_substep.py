"""Optional plan.processing_substep for extract vs persist progress (Celery PDF task)."""

from alembic import op
import sqlalchemy as sa

revision = "011_plan_processing_substep"
down_revision = "010_project_cover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("processing_substep", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plans", "processing_substep")
