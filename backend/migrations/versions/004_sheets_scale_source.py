"""Add sheets.scale_source for auto vs manual calibration (Sprint 06)

Revision ID: 004
Revises: 003
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sheets",
        sa.Column("scale_source", sa.String(20), nullable=True),
    )
    op.execute(
        "COMMENT ON COLUMN sheets.scale_source IS 'auto | manual'"
    )


def downgrade() -> None:
    op.drop_column("sheets", "scale_source")
