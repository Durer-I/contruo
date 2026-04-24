"""Transactional email via Resend HTTP API."""

from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)

RESEND_SEND_URL = "https://api.resend.com/emails"


def _role_label(role: str) -> str:
    return role.replace("_", " ").title()


def build_invitation_email_body(
    *,
    org_name: str,
    role: str,
    invite_url: str,
    expires_at: datetime,
    inviter_name: str | None,
    guest_project_name: str | None,
) -> tuple[str, str]:
    """Return (subject, html) for an org invitation."""
    org_safe = html.escape(org_name, quote=True)
    role_l = html.escape(_role_label(role), quote=True)
    exp = expires_at.strftime("%Y-%m-%d %H:%M UTC")
    inviter_safe = html.escape(inviter_name, quote=True) if inviter_name else None
    project_safe = html.escape(guest_project_name, quote=True) if guest_project_name else None
    inviter_line = (
        f"<p>{inviter_safe} invited you to join <strong>{org_safe}</strong> on Contruo.</p>"
        if inviter_safe
        else f"<p>You have been invited to join <strong>{org_safe}</strong> on Contruo.</p>"
    )
    if project_safe:
        guest_line = (
            f"<p>This invitation is for <strong>guest access</strong> to the project "
            f"<strong>{project_safe}</strong> (role: {role_l}).</p>"
        )
    else:
        guest_line = f"<p>Your role will be: <strong>{role_l}</strong>.</p>"

    subject = f"Invitation to join {org_name} on Contruo"
    url_attr = html.escape(invite_url, quote=True)
    url_body = html.escape(invite_url, quote=True)
    html_out = f"""\
<!DOCTYPE html>
<html><body style="font-family: system-ui, sans-serif; line-height: 1.5;">
{inviter_line}
{guest_line}
<p>This link expires on <strong>{html.escape(exp)}</strong>.</p>
<p><a href="{url_attr}" style="display:inline-block;padding:10px 16px;background:#111827;color:#fff;\
text-decoration:none;border-radius:6px;">Accept invitation</a></p>
<p style="font-size:12px;color:#6b7280;">If the button does not work, copy this URL:<br/>{url_body}</p>
</body></html>"""
    return subject, html_out


async def send_invitation_email(
    *,
    to_email: str,
    invite_token: str,
    org_name: str,
    role: str,
    expires_at: datetime,
    inviter_name: str | None = None,
    guest_project_name: str | None = None,
) -> bool:
    """POST to Resend. Returns True on 2xx, False if skipped or on API error."""
    s = get_settings()
    key = (s.email_api_key or "").strip()
    if not key:
        logger.info("Skipping invitation email: EMAIL_API_KEY is empty")
        return False
    if (s.email_provider or "").strip().lower() != "resend":
        logger.warning(
            "Skipping invitation email: EMAIL_PROVIDER=%r is not supported (use resend)",
            s.email_provider,
        )
        return False

    app_url = (s.app_url or "").rstrip("/")
    invite_url = f"{app_url}/invite/{invite_token}"
    subject, html = build_invitation_email_body(
        org_name=org_name,
        role=role,
        invite_url=invite_url,
        expires_at=expires_at,
        inviter_name=inviter_name,
        guest_project_name=guest_project_name,
    )
    payload = {
        "from": s.email_from,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(RESEND_SEND_URL, json=payload, headers=headers)

    if r.is_success:
        logger.info("Invitation email queued for %s", to_email)
        return True

    logger.error(
        "Resend API error for invitation to %s: status=%s body=%s",
        to_email,
        r.status_code,
        r.text[:500],
    )
    return False


def _format_money(amount_cents: int, currency: str) -> str:
    cur = (currency or "USD").strip().upper() or "USD"
    amt = amount_cents / 100.0
    if cur == "USD":
        return f"${amt:,.2f}"
    return f"{amt:,.2f} {cur}"


def build_invoice_receipt_email(
    *,
    org_name: str,
    amount_cents: int,
    currency: str,
    issued_at: datetime,
    pdf_url: str | None,
    billing_url: str,
) -> tuple[str, str]:
    """Return (subject, html) for a successful subscription payment / invoice."""
    org_safe = html.escape(org_name, quote=True)
    money = html.escape(_format_money(amount_cents, currency), quote=True)
    ia = issued_at
    if ia.tzinfo is None:
        ia = ia.replace(tzinfo=UTC)
    else:
        ia = ia.astimezone(UTC)
    when = html.escape(ia.strftime("%Y-%m-%d %H:%M UTC"), quote=True)
    billing_attr = html.escape(billing_url, quote=True)
    billing_body = html.escape(billing_url, quote=True)

    pdf_block = ""
    if pdf_url:
        pu = html.escape(pdf_url, quote=True)
        pdf_block = (
            f'<p><a href="{pu}" style="display:inline-block;padding:10px 16px;'
            'background:#111827;color:#fff;text-decoration:none;border-radius:6px;">'
            "View invoice PDF</a></p>"
        )

    subject = f"Receipt: {org_name} — Contruo subscription payment"
    html_out = f"""\
<!DOCTYPE html>
<html><body style="font-family: system-ui, sans-serif; line-height: 1.5;">
<p>We received a payment for <strong>{org_safe}</strong> on Contruo.</p>
<p><strong>Amount:</strong> {money}<br/><strong>Date:</strong> {when}</p>
{pdf_block}
<p><a href="{billing_attr}">Open Billing</a> in Contruo for invoices and seat usage.</p>
<p style="font-size:12px;color:#6b7280;">If links do not work, copy: {billing_body}</p>
</body></html>"""
    return subject, html_out


async def send_invoice_receipt_to_org_owner(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    org_name: str,
    amount_cents: int,
    currency: str,
    issued_at: datetime,
    pdf_url: str | None,
) -> bool:
    """Email the org owner when a new invoice row is created from a Dodo payment.succeeded event."""
    from app.services import auth_service

    s = get_settings()
    key = (s.email_api_key or "").strip()
    if not key:
        logger.info("Skipping invoice email: EMAIL_API_KEY is empty")
        return False
    if (s.email_provider or "").strip().lower() != "resend":
        logger.warning(
            "Skipping invoice email: EMAIL_PROVIDER=%r is not supported (use resend)",
            s.email_provider,
        )
        return False

    to_email = await auth_service.get_org_owner_auth_email(db, org_id)
    if not to_email:
        logger.warning("Skipping invoice email: no owner email for org %s", org_id)
        return False

    app_url = (s.app_url or "").rstrip("/")
    billing_url = f"{app_url}/settings/billing"
    subject, html_body = build_invoice_receipt_email(
        org_name=org_name,
        amount_cents=amount_cents,
        currency=currency,
        issued_at=issued_at,
        pdf_url=pdf_url,
        billing_url=billing_url,
    )
    payload = {
        "from": s.email_from,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(RESEND_SEND_URL, json=payload, headers=headers)

    if r.is_success:
        logger.info("Invoice receipt email queued for org %s → %s", org_id, to_email)
        return True

    logger.error(
        "Resend API error for invoice email org=%s: status=%s body=%s",
        org_id,
        r.status_code,
        r.text[:500],
    )
    return False
