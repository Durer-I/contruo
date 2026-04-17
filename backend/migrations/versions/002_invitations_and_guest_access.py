"""Add invitations and guest_project_access tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), server_default="estimator", nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_invitations_org_id", "invitations", ["org_id"])
    op.create_index("ix_invitations_token", "invitations", ["token"])
    op.create_index("ix_invitations_email_org", "invitations", ["email", "org_id"])

    op.create_table(
        "guest_project_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
    )
    op.create_index("ix_guest_project_access_org_id", "guest_project_access", ["org_id"])
    op.create_index("ix_guest_project_access_user", "guest_project_access", ["user_id", "project_id"])

    # RLS
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE guest_project_access ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Org members can access their invitations"
            ON invitations FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)

    op.execute("""
        CREATE POLICY "Org members can access guest access records"
            ON guest_project_access FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Org members can access guest access records" ON guest_project_access')
    op.execute('DROP POLICY IF EXISTS "Org members can access their invitations" ON invitations')

    op.drop_table("guest_project_access")
    op.drop_table("invitations")
