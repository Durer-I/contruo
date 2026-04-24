"""Invitation email helpers."""

from datetime import datetime, timezone

import pytest

from app.services.email_service import build_invitation_email_body


def test_build_invitation_email_body_member():
    exp = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
    subject, html_out = build_invitation_email_body(
        org_name="Acme & Co",
        role="estimator",
        invite_url="http://localhost:3000/invite/tok<en>",
        expires_at=exp,
        inviter_name="Pat O'Neil",
        guest_project_name=None,
    )
    assert "Acme &amp; Co" in html_out
    assert "Pat O" in html_out and "Neil" in html_out
    assert "Estimator" in html_out
    assert "http://localhost:3000/invite/tok&lt;en&gt;" in html_out
    assert "Acme & Co" in subject


def test_build_invitation_email_body_guest_project():
    exp = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
    _, html_out = build_invitation_email_body(
        org_name="Org",
        role="viewer",
        invite_url="http://x/invite/abc",
        expires_at=exp,
        inviter_name=None,
        guest_project_name="Site <A>",
    )
    assert "guest access" in html_out
    assert "Site &lt;A&gt;" in html_out


@pytest.mark.anyio
async def test_send_invitation_email_skips_without_key():
    from unittest.mock import MagicMock, patch

    from app.services import email_service

    mock = MagicMock()
    mock.email_api_key = ""
    mock.email_provider = "resend"

    with patch.object(email_service, "get_settings", return_value=mock):
        ok = await email_service.send_invitation_email(
            to_email="a@b.com",
            invite_token="t",
            org_name="O",
            role="viewer",
            expires_at=datetime.now(timezone.utc),
        )
    assert ok is False
