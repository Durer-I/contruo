"""JWT validation middleware for Supabase Auth.

Validates the JWT from the Authorization header using Supabase's JWKS,
then looks up the user's org_id and role from the database.
"""

import uuid
import logging
from dataclasses import dataclass

import httpx
from fastapi import Depends, Request
from jose import jwt, JWTError, jwk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models.user import User
from app.middleware.error_handler import UnauthorizedException, ForbiddenException

logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None


@dataclass
class AuthContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    email: str


async def _get_jwks() -> dict:
    """Fetch and cache Supabase JWKS for JWT verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    settings = get_settings()
    if not settings.supabase_url:
        raise UnauthorizedException("Auth service not configured")

    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except Exception as e:
        logger.error("Failed to fetch JWKS: %s", e)
        raise UnauthorizedException("Auth service unavailable")


def _decode_jwt(token: str, jwks: dict) -> dict:
    """Decode and validate the JWT using the JWKS public keys."""
    settings = get_settings()
    base = settings.supabase_url.rstrip("/")
    # GoTrue may emit iss with or without trailing slash; env must still match project host.
    expected_issuers = (
        f"{base}/auth/v1",
        f"{base}/auth/v1/",
    )

    # Find the signing key
    keys = jwks.get("keys", [])
    if not keys:
        raise UnauthorizedException("Invalid token configuration")

    # Get the header to find the key id
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise UnauthorizedException("Invalid token format")

    kid = unverified_header.get("kid")
    token_alg = unverified_header.get("alg") or "RS256"
    algorithms = list(
        dict.fromkeys([a for a in (token_alg, "RS256", "ES256") if a])
    )

    # Find matching key
    rsa_key = None
    for key in keys:
        if key.get("kid") == kid:
            rsa_key = key
            break

    if rsa_key is None:
        # If no kid match, use the first key (Supabase typically has one key)
        rsa_key = keys[0]

    try:
        public_key = jwk.construct(rsa_key)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=algorithms,
            audience="authenticated",
            issuer=expected_issuers,
        )
        return payload
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        raise UnauthorizedException("Invalid or expired token")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Extract and validate the JWT, then look up the user's org membership."""

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedException()

    token = auth_header[7:]  # Strip "Bearer "

    # Validate JWT
    jwks = await _get_jwks()
    payload = _decode_jwt(token, jwks)

    supabase_user_id = payload.get("sub")
    email = payload.get("email", "")
    if not supabase_user_id:
        raise UnauthorizedException("Token missing user identity")

    user_id = uuid.UUID(supabase_user_id)

    # Look up user in our database
    stmt = select(User).where(User.id == user_id, User.deactivated_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException(
            "No Contruo account for this user. Complete sign up or use an invited account.",
            code="APP_USER_NOT_FOUND",
        )

    return AuthContext(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
        email=email,
    )


def require_role(*roles: str):
    """Dependency factory that checks the user has one of the required roles."""

    async def _check(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if user.role not in roles:
            raise ForbiddenException()
        return user

    return _check
