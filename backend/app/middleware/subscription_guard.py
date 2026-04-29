"""Enforce org subscription state on authenticated API routes (Sprint 14)."""

from __future__ import annotations

import re

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext, get_current_user
from app.middleware.error_handler import ForbiddenException
from app.services import billing_service
from app.services.billing_service import WRITE_METHODS

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_MEMBER_BY_ID_PATH = re.compile(rf"^/api/v1/org/members/{_UUID}$", re.I)
_INVITATION_CANCEL_PATH = re.compile(rf"^/api/v1/org/invitations/{_UUID}/cancel$", re.I)

READ_ONLY_BILLING_WRITE_PREFIXES = (
    "/api/v1/billing/checkout-session",
    "/api/v1/billing/update-payment-method",
    "/api/v1/billing/seats/",
    # Liveblocks auth is POST but does not mutate Contruo DB — allow read-only orgs to view plans.
    "/api/v1/liveblocks/",
)

def _path_allowed_seat_overage(path: str, method: str) -> bool:
    """Writes allowed while billable headcount exceeds purchased seats (resolve via Billing or Team)."""
    m = method.upper()
    if path == "/api/v1/billing" or path.startswith("/api/v1/billing/"):
        return True
    if path.startswith("/api/v1/auth/me"):
        return True
    if path.startswith("/api/v1/liveblocks/"):
        return True
    if path == "/api/v1/org/guests/invite" and m == "POST":
        return True
    if m == "POST" and _INVITATION_CANCEL_PATH.match(path):
        return True
    if m in ("PATCH", "DELETE") and _MEMBER_BY_ID_PATH.match(path):
        return True
    return False


def _path_allowed_when_suspended(path: str) -> bool:
    """GET /api/v1/billing has no trailing slash; must still be allowed for reactivation."""
    if path.startswith("/api/v1/auth/me"):
        return True
    return path == "/api/v1/billing" or path.startswith("/api/v1/billing/")


async def enforce_org_subscription_state(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Block writes when subscription is read-only; block (almost) all when suspended."""
    path = request.url.path
    method = request.method.upper()

    sub = await billing_service.get_subscription(db, auth.org_id)
    if not sub:
        return

    # Apply automatic state transitions in-place; avoid a second SELECT round-trip
    # by relying on the (refresh-aware) status returned alongside the row.
    refreshed = await billing_service.refresh_subscription_automatic_transitions(
        db, auth.org_id
    )
    sub = refreshed or sub
    if not sub:
        return

    status = sub.status

    if status in ("suspended", "cancelled"):
        if _path_allowed_when_suspended(path):
            return
        raise ForbiddenException(
            "This organization is suspended for billing. Visit Billing to reactivate."
        )

    if status == "read_only":
        if method not in WRITE_METHODS:
            return
        for p in READ_ONLY_BILLING_WRITE_PREFIXES:
            if path.startswith(p):
                return
        raise ForbiddenException(
            "This organization is in read-only mode until billing is resolved."
        )

    if status == "active" and method in WRITE_METHODS:
        if await billing_service.org_seat_capacity_overage(db, auth.org_id):
            if _path_allowed_seat_overage(path, method):
                return
            raise ForbiddenException(
                "This organization has more active members than purchased seats. "
                "Add seats in Billing or deactivate members in Team."
            )

    # past_due: full access until grace ends (handled by transition to read_only)
    return
