"""Subscription billing extensions: payment method, failure tracking, invoice payment id

Revision ID: 008
Revises: 007
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("dodopayments_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("dodopayments_product_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("card_last_four", sa.String(4), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("card_brand", sa.String(32), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("first_payment_failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_invoices_org_provider_payment",
        "invoices",
        ["org_id", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_org_provider_payment", table_name="invoices")
    op.drop_column("invoices", "provider_payment_id")
    op.drop_column("subscriptions", "grace_period_ends_at")
    op.drop_column("subscriptions", "first_payment_failed_at")
    op.drop_column("subscriptions", "card_brand")
    op.drop_column("subscriptions", "card_last_four")
    op.drop_column("subscriptions", "dodopayments_product_id")
    op.drop_column("subscriptions", "dodopayments_customer_id")
