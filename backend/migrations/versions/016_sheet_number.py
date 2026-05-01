"""Add ``sheets.sheet_number`` for the auto-name-sheets flow.

Sprint AI-02b's title-block extractor returns two structured fields:

* ``drawing_name`` (e.g. ``"DEMOLITION FLOOR PLANS"``) -> ``sheets.sheet_name``.
* ``drawing_number`` (e.g. ``"D101"``, ``"A0.1"``, ``"S-100"``)
  -> ``sheets.sheet_number`` (this column).

Storing the number separately (rather than concatenating into ``sheet_name``)
keeps it cheap to:

* Sort the sheet index by sheet number.
* Group quantities by sheet identifier across plans/revisions.
* Show the number as a monospace badge in the row UI.

The existing ``sheet_name_source`` flag (``'auto'`` | ``'manual'`` | ``NULL``)
guards both fields together: a manual rename of either name or number marks
the row ``'manual'`` and protects both columns from any future re-extract.
There is intentionally no FK and no unique constraint -- sheet numbers can
repeat across plans (revisions, multi-discipline drawings, etc.).

Revision ID: 016_sheet_number
Revises: 015_sheet_name_source
Create Date: 2026-05-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_sheet_number"
down_revision: Union[str, None] = "015_sheet_name_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sheets",
        sa.Column("sheet_number", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sheets", "sheet_number")
