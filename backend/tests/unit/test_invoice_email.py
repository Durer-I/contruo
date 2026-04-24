"""Invoice receipt email helpers (Sprint 14)."""

from datetime import UTC, datetime

from app.services.email_service import _format_money, build_invoice_receipt_email


def test_format_money_usd():
    assert _format_money(1999, "usd") == "$19.99"
    assert _format_money(100000, "USD") == "$1,000.00"


def test_format_money_non_usd():
    assert "50.00" in _format_money(5000, "EUR")


def test_build_invoice_receipt_email_contains_amount_and_links():
    issued = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    subject, html = build_invoice_receipt_email(
        org_name="Acme Co",
        amount_cents=12000,
        currency="USD",
        issued_at=issued,
        pdf_url="https://pay.example/inv.pdf",
        billing_url="https://app.example/settings/billing",
    )
    assert "Acme Co" in subject
    assert "$120.00" in html
    assert "https://pay.example/inv.pdf" in html
    assert "/settings/billing" in html
