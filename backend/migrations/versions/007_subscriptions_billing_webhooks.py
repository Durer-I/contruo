"""Subscriptions, invoices, webhook idempotency (Sprint 14)

Revision ID: 007
Revises: 006
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("seat_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("price_per_seat", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("billing_cycle_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("billing_cycle_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_provider_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("org_id", name="uq_subscriptions_org_id"),
    )
    op.create_index("ix_subscriptions_org_id", "subscriptions", ["org_id"])

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("provider_invoice_id", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invoices_org_id", "invoices", ["org_id"])
    op.create_index("ix_invoices_org_issued_at", "invoices", ["org_id", "issued_at"])

    # Written only by the API (no JWT); RLS not enabled so webhook + worker paths stay simple.
    op.create_table(
        "billing_webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("webhook_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=True),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("webhook_id", name="uq_billing_webhook_deliveries_webhook_id"),
    )

    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY "Org members can read subscriptions"
            ON subscriptions FOR SELECT
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)
    op.execute("""
        CREATE POLICY "Org members can read invoices"
            ON invoices FOR SELECT
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Org members can read invoices" ON invoices')
    op.execute('DROP POLICY IF EXISTS "Org members can read subscriptions" ON subscriptions')
    op.drop_table("billing_webhook_deliveries")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
