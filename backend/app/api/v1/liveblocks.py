"""Custom authentication for Liveblocks rooms."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext, get_current_user
from app.middleware.error_handler import AppException, ForbiddenException
from app.models.user import User
from app.schemas.liveblocks import LiveblocksAuthRequest, LiveblocksAuthResponse
from app.services import project_service
from app.services.liveblocks_service import issue_access_token, parse_collaboration_room
from app.services.permission_service import Permission, has_permission

router = APIRouter(prefix="/liveblocks", tags=["liveblocks"])


def collaboration_room_id(org_id: uuid.UUID, project_id: uuid.UUID) -> str:
    return f"contruo:{org_id}:{project_id}"


@router.post("/auth", response_model=LiveblocksAuthResponse)
async def liveblocks_auth(
    body: LiveblocksAuthRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a Liveblocks access token for the requested room.

    Room id must be ``contruo:{org_id}:{project_id}`` with the caller's org_id,
    and the project must exist in that org.
    """
    parsed = parse_collaboration_room(body.room)
    if not parsed:
        raise AppException(
            code="INVALID_ROOM",
            message="Invalid collaboration room id",
            status_code=400,
        )
    room_org_id, project_id = parsed
    if room_org_id != auth.org_id:
        raise ForbiddenException("Room does not belong to your organization")

    await project_service.get_project(db, auth.org_id, project_id)

    result = await db.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AppException(code="USER_NOT_FOUND", message="User not found", status_code=404)

    if has_permission(auth.role, Permission.EDIT_MEASUREMENTS):
        perms = ["room:write"]
    else:
        perms = ["room:read", "room:presence:write"]

    user_info: dict = {"name": user.full_name}
    if auth.email:
        user_info["email"] = auth.email

    try:
        token = await issue_access_token(
            room_id=body.room.strip(),
            liveblocks_user_id=str(auth.user_id),
            organization_id=str(auth.org_id),
            user_info=user_info,
            permissions=perms,
        )
    except RuntimeError as e:
        raise AppException(
            code="LIVEBLOCKS_UNAVAILABLE",
            message=str(e),
            status_code=503,
        ) from e

    return LiveblocksAuthResponse(token=token)
