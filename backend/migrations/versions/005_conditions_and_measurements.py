"""Conditions and measurements (Sprint 07)

Revision ID: 005
Revises: 004
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conditions_org_id", "conditions", ["org_id"])
    op.create_index("ix_conditions_project_id", "conditions", ["project_id"])

    op.create_table(
        "measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measurement_type", sa.String(20), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("measured_value", sa.Float(), nullable=False),
        sa.Column("override_value", sa.Float(), nullable=True),
        sa.Column("deductions", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["condition_id"], ["conditions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_measurements_org_id", "measurements", ["org_id"])
    op.create_index("ix_measurements_project_id", "measurements", ["project_id"])
    op.create_index("ix_measurements_sheet_id", "measurements", ["sheet_id"])
    op.create_index("ix_measurements_condition_id", "measurements", ["condition_id"])

    op.execute("ALTER TABLE conditions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE measurements ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Users can only access their org's conditions"
            ON conditions FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access their org's measurements"
            ON measurements FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s measurements" ON measurements')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s conditions" ON conditions')
    op.drop_table("measurements")
    op.drop_table("conditions")
