import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client

from app.config import get_settings
from app.middleware.error_handler import AppException
from app.models.organization import Organization
from app.models.user import User
from app.services import billing_service
from app.services.event_service import log_event

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_supabase_admin():
    """Create a Supabase client with the service_role key for admin operations."""
    if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
        raise AppException(
            code="MISCONFIGURED",
            message="Supabase env missing. Ensure backend loads .env or .env.local with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
            status_code=503,
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def register_user(
    db: AsyncSession,
    *,
    full_name: str,
    email: str,
    password: str,
    org_name: str,
) -> dict:
    """Register a new user: create Supabase auth user, org, and user record."""

    supabase = _get_supabase_admin()

    # 1. Create auth user in Supabase (confirm email in dev or when AUTH_AUTO_CONFIRM_REGISTERED_USERS=true)
    email_confirm = settings.is_development or settings.auth_auto_confirm_registered_users
    try:
        auth_response = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": email_confirm,
                "user_metadata": {"full_name": full_name},
            }
        )
    except Exception as e:
        error_msg = str(e)
        if "already been registered" in error_msg or "already exists" in error_msg:
            raise AppException(
                code="EMAIL_ALREADY_EXISTS",
                message="An account with this email already exists",
                status_code=409,
            )
        logger.error("Supabase auth error: %s", error_msg)
        raise AppException(
            code="AUTH_ERROR",
            message="Failed to create account",
            status_code=500,
        )

    supabase_user_id = uuid.UUID(auth_response.user.id)

    # 2. Create organization
    org = Organization(name=org_name)
    db.add(org)
    await db.flush()

    # 3. Create user record linked to both Supabase auth and the org
    user = User(
        id=supabase_user_id,
        org_id=org.id,
        full_name=full_name,
        role="owner",
        is_guest=False,
    )
    db.add(user)
    await db.flush()

    if not auth_response or not auth_response.user:
        raise AppException(
            code="AUTH_ERROR",
            message="Failed to create user in auth system",
            status_code=500,
        )

    # 4. Log the event
    await log_event(
        db,
        org_id=org.id,
        user_id=user.id,
        event_type="user.registered",
        entity_type="user",
        entity_id=user.id,
        payload={"email": email, "org_name": org_name},
    )

    await db.commit()
    # 5. Sign in immediately to return tokens
    try:
        sign_in = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:
        # User created but sign-in failed -- they can log in manually
        raise AppException(
            code="SIGN_IN_FAILED",
            message="Account created but automatic sign-in failed. Please log in.",
            status_code=201,
        )

    sub_status = await billing_service.get_org_subscription_status(db, org.id)
    has_sub = await billing_service.get_subscription(db, org.id)
    banner = await billing_service.billing_banner_message(db, org.id)
    seat_overage = await billing_service.org_seat_capacity_overage(db, org.id)
    user_payload = {
        "id": user.id,
        "email": email,
        "full_name": user.full_name,
        "org_id": org.id,
        "org_name": org.name,
        "role": user.role,
        "is_guest": user.is_guest,
        "subscription_status": sub_status,
        "needs_subscription": has_sub is None,
        "reactivation_required": billing_service.subscription_requires_resubscribe(has_sub),
        "billing_banner": banner,
        "seat_overage": seat_overage,
    }
    return {
        "access_token": sign_in.session.access_token,
        "refresh_token": sign_in.session.refresh_token,
        "user": user_payload,
    }


async def login_user(email: str, password: str) -> dict:
    """Authenticate via Supabase and return tokens + user info."""
    supabase = _get_supabase_admin()

    try:
        response = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as e:
        error_msg = str(e)
        if "Invalid login" in error_msg or "invalid" in error_msg.lower():
            raise AppException(
                code="INVALID_CREDENTIALS",
                message="Invalid email or password",
                status_code=401,
            )
        logger.error("Supabase login error: %s", error_msg)
        raise AppException(
            code="AUTH_ERROR",
            message="Login failed",
            status_code=500,
        )

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "supabase_user_id": uuid.UUID(response.user.id),
    }


async def get_user_with_org(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Look up a user and their org from the database."""
    stmt = (
        select(User, Organization)
        .join(Organization, User.org_id == Organization.id)
        .where(User.id == user_id)
        .where(User.deactivated_at.is_(None))
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User account not found or deactivated",
            status_code=404,
        )
    user, org = row
    sub_status = await billing_service.get_org_subscription_status(db, org.id)
    has_sub = await billing_service.get_subscription(db, org.id)
    banner = await billing_service.billing_banner_message(db, org.id)
    seat_overage = await billing_service.org_seat_capacity_overage(db, org.id)
    return {
        "id": user.id,
        "email": "",  # filled by caller from JWT
        "full_name": user.full_name,
        "org_id": org.id,
        "org_name": org.name,
        "role": user.role,
        "is_guest": user.is_guest,
        "subscription_status": sub_status,
        "needs_subscription": has_sub is None,
        "reactivation_required": billing_service.subscription_requires_resubscribe(has_sub),
        "billing_banner": banner,
        "seat_overage": seat_overage,
    }


async def get_org_owner_auth_email(db: AsyncSession, org_id: uuid.UUID) -> str | None:
    """Supabase Auth email for the active org owner (for billing notifications)."""
    result = await db.execute(
        select(User.id).where(
            User.org_id == org_id,
            User.role == "owner",
            User.deactivated_at.is_(None),
        )
    )
    owner_id = result.scalar_one_or_none()
    if not owner_id:
        return None

    supabase = _get_supabase_admin()

    def _fetch() -> str | None:
        try:
            resp = supabase.auth.admin.get_user_by_id(str(owner_id))
            u = getattr(resp, "user", None)
            raw = (getattr(u, "email", None) or "").strip()
            return raw or None
        except Exception as e:
            logger.warning("Could not load auth email for owner %s: %s", owner_id, e)
            return None

    return await asyncio.to_thread(_fetch)


async def update_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    full_name: str,
) -> dict:
    """Update app user row and sync display name to Supabase Auth user_metadata."""
    stmt = select(User).where(User.id == user_id, User.deactivated_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User account not found or deactivated",
            status_code=404,
        )
    user.full_name = full_name
    await db.flush()

    supabase = _get_supabase_admin()
    try:
        supabase.auth.admin.update_user_by_id(
            str(user_id),
            {"user_metadata": {"full_name": full_name}},
        )
    except Exception as e:
        logger.warning("Supabase user_metadata sync failed (DB updated): %s", e)

    await db.commit()
    return await get_user_with_org(db, user_id)


async def request_password_reset(email: str) -> None:
    """Send a password reset email via Supabase."""
    supabase = _get_supabase_admin()
    try:
        supabase.auth.reset_password_email(
            email,
            {"redirect_to": f"{settings.app_url}/reset-password/confirm"},
        )
    except Exception as e:
        logger.error("Password reset error: %s", e)
        # Don't reveal whether email exists
        pass


async def logout_user(access_token: str) -> None:
    """Revoke the user's session in Supabase."""
    supabase = _get_supabase_admin()
    try:
        supabase.auth.admin.sign_out(access_token)
    except Exception as e:
        logger.warning("Logout error (non-fatal): %s", e)
