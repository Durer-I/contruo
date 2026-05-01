"""Track whether ``sheets.sheet_name`` came from extraction or a user edit.

Adds ``sheets.sheet_name_source VARCHAR(20) NULL`` with three logical states:

* ``'auto'``  -- written by either the upload-time heuristic
  (``backend/app/utils/pdf.py::_extract_sheet_name``) or the AI Stage 1
  extractor (``backend/app/services/ai_title_block.py``). Safe to overwrite
  on a re-extract.
* ``'manual'`` -- user typed the name (inline rename UI). The re-extract
  task and Stage 1 MUST NOT overwrite these rows. Manual edits are sacred.
* ``NULL`` -- legacy rows from before this migration. Treated as ``'auto'``
  by writers; eligible to be overwritten on the next re-extract.

The column is intentionally NOT a CHECK-constrained enum so the app can
introduce future sources (e.g. ``'imported'``) without a schema change.

Revision ID: 015_sheet_name_source
Revises: 014_ai_title_block_and_pause
Create Date: 2026-04-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_sheet_name_source"
down_revision: Union[str, None] = "014_ai_title_block_and_pause"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sheets",
        sa.Column("sheet_name_source", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sheets", "sheet_name_source")
