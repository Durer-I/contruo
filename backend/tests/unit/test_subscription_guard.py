"""Subscription guard path rules."""

from app.middleware.subscription_guard import (
    _path_allowed_seat_overage,
    _path_allowed_when_suspended,
)


def test_suspended_org_allows_billing_summary_path():
    assert _path_allowed_when_suspended("/api/v1/billing") is True


def test_suspended_org_allows_billing_subpaths():
    assert _path_allowed_when_suspended("/api/v1/billing/invoices") is True
    assert _path_allowed_when_suspended("/api/v1/billing/checkout-session") is True


def test_suspended_org_allows_auth_me():
    assert _path_allowed_when_suspended("/api/v1/auth/me") is True


def test_suspended_org_blocks_unrelated_paths():
    assert _path_allowed_when_suspended("/api/v1/projects") is False
    assert _path_allowed_when_suspended("/api/v1/billing-evil") is False


def test_seat_overage_allows_billing_and_member_writes():
    mid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert _path_allowed_seat_overage("/api/v1/billing", "GET") is True
    assert _path_allowed_seat_overage("/api/v1/billing/checkout-session", "POST") is True
    assert _path_allowed_seat_overage(f"/api/v1/org/members/{mid}", "PATCH") is True
    assert _path_allowed_seat_overage(f"/api/v1/org/members/{mid}", "DELETE") is True
    assert _path_allowed_seat_overage(
        f"/api/v1/org/invitations/{mid}/cancel", "POST"
    ) is True
    assert _path_allowed_seat_overage("/api/v1/org/guests/invite", "POST") is True
    assert _path_allowed_seat_overage("/api/v1/liveblocks/auth", "POST") is True


def test_seat_overage_blocks_invite_and_project_writes():
    mid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert _path_allowed_seat_overage("/api/v1/org/members/invite", "POST") is False
    assert _path_allowed_seat_overage(f"/api/v1/org/invitations/{mid}/resend", "POST") is False
    assert _path_allowed_seat_overage("/api/v1/projects", "POST") is False
    assert _path_allowed_seat_overage(f"/api/v1/org/members/{mid}", "POST") is False
