"""Organization management service: settings, members, invitations, guests."""

import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client

from app.config import get_settings
from app.models.organization import Organization
from app.models.user import User
from app.models.invitation import Invitation
from app.models.guest_project_access import GuestProjectAccess
from app.services.event_service import log_event
from app.middleware.error_handler import AppException, NotFoundException

logger = logging.getLogger(__name__)
settings = get_settings()

INVITATION_EXPIRY_DAYS = 7


def _supabase_admin():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ── Organization Settings ────────────────────────────────────────────

async def get_org(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundException("organization", str(org_id))
    return org


async def update_org(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    default_units: str | None = None,
    logo_url: str | None = None,
) -> Organization:
    org = await get_org(db, org_id)
    if name is not None:
        org.name = name
    if default_units is not None:
        org.default_units = default_units
    if logo_url is not None:
        org.logo_url = logo_url
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=user_id,
        event_type="org.updated",
        entity_type="organization",
        entity_id=org_id,
        payload={"name": name, "default_units": default_units},
    )
    return org


# ── Members ──────────────────────────────────────────────────────────

async def list_members(db: AsyncSession, org_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(User).where(User.org_id == org_id).order_by(User.created_at)
    )
    users = result.scalars().all()

    supabase = _supabase_admin()
    members = []
    for u in users:
        email = ""
        try:
            auth_user = supabase.auth.admin.get_user_by_id(str(u.id))
            email = auth_user.user.email or ""
        except Exception:
            pass
        members.append({
            "id": u.id,
            "email": email,
            "full_name": u.full_name,
            "role": u.role,
            "is_guest": u.is_guest,
            "deactivated_at": u.deactivated_at,
            "created_at": u.created_at,
        })
    return members


async def update_member_role(
    db: AsyncSession,
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    new_role: str,
    acting_user_id: uuid.UUID,
) -> User:
    result = await db.execute(
        select(User).where(User.id == member_id, User.org_id == org_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundException("member", str(member_id))
    if member.role == "owner":
        raise AppException(code="CANNOT_CHANGE_OWNER", message="Cannot change the owner's role", status_code=400)

    old_role = member.role
    member.role = new_role
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        event_type="member.role_changed",
        entity_type="user",
        entity_id=member_id,
        payload={"old_role": old_role, "new_role": new_role},
    )
    return member


async def deactivate_member(
    db: AsyncSession,
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(User).where(User.id == member_id, User.org_id == org_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundException("member", str(member_id))
    if member.role == "owner":
        raise AppException(code="CANNOT_DEACTIVATE_OWNER", message="Cannot deactivate the organization owner", status_code=400)
    if member.deactivated_at is not None:
        raise AppException(code="ALREADY_DEACTIVATED", message="Member is already deactivated", status_code=400)

    member.deactivated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        event_type="member.deactivated",
        entity_type="user",
        entity_id=member_id,
    )


# ── Invitations ──────────────────────────────────────────────────────

async def create_invitation(
    db: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID,
) -> Invitation:
    existing = await db.execute(
        select(Invitation).where(
            Invitation.org_id == org_id,
            Invitation.email == email,
            Invitation.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise AppException(
            code="INVITATION_ALREADY_PENDING",
            message="An invitation to this email is already pending",
            status_code=409,
        )

    token = secrets.token_urlsafe(48)
    invitation = Invitation(
        org_id=org_id,
        email=email,
        role=role,
        token=token,
        invited_by=invited_by,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS),
    )
    db.add(invitation)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=invited_by,
        event_type="invitation.created",
        entity_type="invitation",
        entity_id=invitation.id,
        payload={"email": email, "role": role},
    )
    return invitation


async def list_invitations(db: AsyncSession, org_id: uuid.UUID) -> list[Invitation]:
    result = await db.execute(
        select(Invitation)
        .where(Invitation.org_id == org_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


async def cancel_invitation(
    db: AsyncSession,
    org_id: uuid.UUID,
    invitation_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.org_id == org_id,
            Invitation.status == "pending",
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise NotFoundException("invitation", str(invitation_id))

    invitation.status = "cancelled"
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        event_type="invitation.cancelled",
        entity_type="invitation",
        entity_id=invitation_id,
    )


async def resend_invitation(
    db: AsyncSession,
    org_id: uuid.UUID,
    invitation_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> Invitation:
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.org_id == org_id,
            Invitation.status == "pending",
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise NotFoundException("invitation", str(invitation_id))

    invitation.token = secrets.token_urlsafe(48)
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)
    await db.flush()
    return invitation


async def accept_invitation(
    db: AsyncSession,
    token: str,
    full_name: str,
    password: str,
) -> dict:
    result = await db.execute(
        select(Invitation).where(Invitation.token == token, Invitation.status == "pending")
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise AppException(code="INVALID_INVITATION", message="Invitation not found or already used", status_code=404)

    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = "expired"
        await db.flush()
        raise AppException(code="INVITATION_EXPIRED", message="This invitation has expired", status_code=410)

    supabase = _supabase_admin()
    try:
        auth_response = supabase.auth.admin.create_user({
            "email": invitation.email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name},
        })
    except Exception as e:
        error_msg = str(e)
        if "already been registered" in error_msg or "already exists" in error_msg:
            raise AppException(
                code="EMAIL_ALREADY_EXISTS",
                message="An account with this email already exists. Please log in and accept the invitation.",
                status_code=409,
            )
        raise AppException(code="AUTH_ERROR", message="Failed to create account", status_code=500)

    supabase_user_id = uuid.UUID(auth_response.user.id)

    user = User(
        id=supabase_user_id,
        org_id=invitation.org_id,
        full_name=full_name,
        role=invitation.role,
        is_guest=False,
    )
    db.add(user)

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    await db.flush()

    # Sign in to return tokens
    try:
        sign_in = supabase.auth.sign_in_with_password(
            {"email": invitation.email, "password": password}
        )
    except Exception:
        raise AppException(
            code="SIGN_IN_FAILED",
            message="Account created but sign-in failed. Please log in manually.",
            status_code=201,
        )

    org = await get_org(db, invitation.org_id)

    await log_event(
        db,
        org_id=invitation.org_id,
        user_id=user.id,
        event_type="invitation.accepted",
        entity_type="invitation",
        entity_id=invitation.id,
    )

    return {
        "access_token": sign_in.session.access_token,
        "refresh_token": sign_in.session.refresh_token,
        "user": {
            "id": user.id,
            "email": invitation.email,
            "full_name": user.full_name,
            "org_id": org.id,
            "org_name": org.name,
            "role": user.role,
            "is_guest": user.is_guest,
        },
    }


# ── Guest Access ─────────────────────────────────────────────────────

async def invite_guest(
    db: AsyncSession,
    org_id: uuid.UUID,
    email: str,
    project_id: uuid.UUID,
    invited_by: uuid.UUID,
) -> Invitation:
    """Invite an external user as a guest to view a specific project."""
    invitation = await create_invitation(db, org_id, email, "viewer", invited_by)

    await log_event(
        db,
        org_id=org_id,
        user_id=invited_by,
        event_type="guest.invited",
        entity_type="guest_project_access",
        payload={"email": email, "project_id": str(project_id)},
    )
    return invitation


async def revoke_guest_access(
    db: AsyncSession,
    org_id: uuid.UUID,
    guest_user_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(User).where(
            User.id == guest_user_id,
            User.org_id == org_id,
            User.is_guest.is_(True),
        )
    )
    guest = result.scalar_one_or_none()
    if not guest:
        raise NotFoundException("guest", str(guest_user_id))

    await db.execute(
        GuestProjectAccess.__table__.delete().where(
            GuestProjectAccess.user_id == guest_user_id,
            GuestProjectAccess.org_id == org_id,
        )
    )

    guest.deactivated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        event_type="guest.revoked",
        entity_type="user",
        entity_id=guest_user_id,
    )
