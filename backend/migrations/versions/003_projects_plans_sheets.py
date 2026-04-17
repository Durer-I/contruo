"""Add projects, plans, and sheets tables with RLS

Revision ID: 003
Revises: 002
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── projects ─────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])
    op.create_index("ix_projects_org_status", "projects", ["org_id", "status"])

    # ── plans ────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="processing", nullable=False),
        sa.Column("processed_pages", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
    )
    op.create_index("ix_plans_org_id", "plans", ["org_id"])
    op.create_index("ix_plans_project_id", "plans", ["project_id"])

    # ── sheets ───────────────────────────────────────────────────────
    op.create_table(
        "sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.String(255), nullable=True),
        sa.Column("scale_value", sa.Float(), nullable=True),
        sa.Column("scale_unit", sa.String(20), nullable=True),
        sa.Column("scale_label", sa.String(100), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("thumbnail_path", sa.Text(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("plan_id", "page_number", name="uq_sheets_plan_page"),
    )
    op.create_index("ix_sheets_org_id", "sheets", ["org_id"])
    op.create_index("ix_sheets_plan_id", "sheets", ["plan_id"])
    op.create_index("ix_sheets_project_id", "sheets", ["project_id"])

    # ── RLS policies ─────────────────────────────────────────────────
    # Every table is org-scoped. Guest access to specific projects is enforced in
    # application code via guest_project_access; RLS here gates by org membership first.
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE plans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sheets ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Users can only access their org's projects"
            ON projects FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access their org's plans"
            ON plans FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access their org's sheets"
            ON sheets FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s sheets" ON sheets')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s plans" ON plans')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s projects" ON projects')

    op.drop_table("sheets")
    op.drop_table("plans")
    op.drop_table("projects")
