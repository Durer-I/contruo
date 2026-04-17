"""Initial tables: organizations, users, event_log

Revision ID: 001
Revises: None
Create Date: 2026-04-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("default_units", sa.String(20), server_default="imperial", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="estimator", nullable=False),
        sa.Column("is_guest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])

    op.create_table(
        "event_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("idx_event_log_org_project", "event_log", ["org_id", "project_id", sa.text("created_at DESC")])
    op.create_index("idx_event_log_entity", "event_log", ["entity_type", "entity_id", sa.text("created_at DESC")])

    # Row-Level Security policies
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE event_log ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Users can only access their own organization"
            ON organizations FOR ALL
            USING (id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access members of their org"
            ON users FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Users can only access their org events"
            ON event_log FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS \"Users can only access their org events\" ON event_log")
    op.execute("DROP POLICY IF EXISTS \"Users can only access members of their org\" ON users")
    op.execute("DROP POLICY IF EXISTS \"Users can only access their own organization\" ON organizations")

    op.drop_table("event_log")
    op.drop_table("users")
    op.drop_table("organizations")
