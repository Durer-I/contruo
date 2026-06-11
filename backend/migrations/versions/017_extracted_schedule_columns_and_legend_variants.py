"""AI-03 Stage 3a schema additions.

Two unrelated changes ride one migration because they're both Stage 3a outputs
and both depend on the same downstream consumers (AI-04 resolver, AI-06 symbol
detector):

1. ``extracted_schedules`` gains four optional column-index fields written by
   the tag-column heuristic / LLM fallback. ``tag_column_index`` already exists
   from migration ``013``; the new columns are siblings -- ``description``,
   ``quantity``, ``dimension`` (array of column indexes), ``material``. All
   nullable -- a schedule may legitimately lack any of them.

2. New table ``extracted_legend_variants``: one row per (legend symbol, scale,
   rotation) variant. AI-03 produces 5 scales x 4 rotations = 20 variants per
   logical symbol. Splitting variants out of ``extracted_legends`` keeps the
   primary table small (one row per symbol) so AI-04's resolver -- which only
   needs labels -- doesn't pay 20x egress on its read path. AI-06 joins to
   variants when it actually needs templates for matching.

RLS follows the existing ``extracted_legends`` policy (org-scoped via the join
to the parent's ``org_id``); the variants table also carries ``org_id``
directly so a stray broken FK doesn't bypass the policy.

Revision ID: 017_extracted_schedule_n_legend
Revises: 016_sheet_number
Create Date: 2026-05-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "017_extracted_schedule_n_legend"
down_revision: Union[str, None] = "016_sheet_number"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── extracted_schedules: column-index fields for the resolver ────────────
    op.add_column(
        "extracted_schedules",
        sa.Column("description_column_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extracted_schedules",
        sa.Column("quantity_column_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extracted_schedules",
        sa.Column(
            "dimension_column_indexes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "extracted_schedules",
        sa.Column("material_column_index", sa.Integer(), nullable=True),
    )

    # ── extracted_legend_variants: 20-variant template grid per symbol ───────
    op.create_table(
        "extracted_legend_variants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "extracted_legend_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        # NUMERIC(3,2) covers 0.00..9.99 -- our defaults are 0.70/0.85/1.00/1.15/1.30
        # but leaving headroom is cheap.
        sa.Column("scale", sa.Numeric(3, 2), nullable=False),
        # 0 / 90 / 180 / 270 today; SMALLINT keeps room for finer rotations later.
        sa.Column("rotation", sa.SmallInteger(), nullable=False),
        sa.Column("template_storage_path", sa.Text(), nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["extracted_legend_id"],
            ["extracted_legends.id"],
            ondelete="CASCADE",
        ),
        # One row per (symbol, scale, rotation). A re-run that produces an
        # identical PNG gets ON CONFLICT DO NOTHING / handled by the writer.
        sa.UniqueConstraint(
            "extracted_legend_id",
            "scale",
            "rotation",
            name="uq_extracted_legend_variants_symbol_scale_rot",
        ),
    )
    op.create_index(
        "ix_extracted_legend_variants_org_id",
        "extracted_legend_variants",
        ["org_id"],
    )
    # AI-06 hot path: "give me every variant for these symbols on this sheet"
    op.create_index(
        "ix_extracted_legend_variants_legend_id",
        "extracted_legend_variants",
        ["extracted_legend_id"],
    )

    op.execute(
        "ALTER TABLE extracted_legend_variants ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY "Users can only access their org's extracted_legend_variants"
            ON extracted_legend_variants FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )


def downgrade() -> None:
    op.execute(
        'DROP POLICY IF EXISTS "Users can only access their org\'s extracted_legend_variants"'
        " ON extracted_legend_variants"
    )
    op.drop_index(
        "ix_extracted_legend_variants_legend_id",
        table_name="extracted_legend_variants",
    )
    op.drop_index(
        "ix_extracted_legend_variants_org_id",
        table_name="extracted_legend_variants",
    )
    op.drop_table("extracted_legend_variants")

    op.drop_column("extracted_schedules", "material_column_index")
    op.drop_column("extracted_schedules", "dimension_column_indexes")
    op.drop_column("extracted_schedules", "quantity_column_index")
    op.drop_column("extracted_schedules", "description_column_index")
