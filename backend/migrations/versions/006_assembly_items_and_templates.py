"""Assembly items + condition templates (Sprint 10)

Revision ID: 006
Revises: 005
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assembly_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["condition_id"], ["conditions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["assembly_items.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_assembly_items_org_id", "assembly_items", ["org_id"])
    op.create_index("ix_assembly_items_condition_id", "assembly_items", ["condition_id"])

    op.create_table(
        "condition_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("measurement_type", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("line_style", sa.String(20), server_default="solid", nullable=False),
        sa.Column("line_width", sa.Float(), server_default="2.0", nullable=False),
        sa.Column("fill_opacity", sa.Float(), server_default="0.3", nullable=False),
        sa.Column("fill_pattern", sa.String(20), server_default="solid", nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("trade", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assembly_items", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_condition_templates_org_id", "condition_templates", ["org_id"])

    op.execute("ALTER TABLE assembly_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE condition_templates ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Users can only access their org's assembly_items"
            ON assembly_items FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access their org's condition_templates"
            ON condition_templates FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute(
        'DROP POLICY IF EXISTS "Users can only access their org\'s condition_templates" ON condition_templates'
    )
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s assembly_items" ON assembly_items')
    op.drop_table("condition_templates")
    op.drop_table("assembly_items")
