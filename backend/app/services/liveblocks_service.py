"""Issue Liveblocks access tokens via REST."""

from __future__ import annotations

import logging
import re
import uuid

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

LIVEBLOCKS_AUTHORIZE_URL = "https://api.liveblocks.io/v2/authorize-user"

# contruo:{org_uuid}:{project_uuid}
_ROOM_RE = re.compile(
    r"^contruo:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}):"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def parse_collaboration_room(room: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    m = _ROOM_RE.match(room.strip())
    if not m:
        return None
    return uuid.UUID(m.group(1)), uuid.UUID(m.group(2))


async def issue_access_token(
    *,
    room_id: str,
    liveblocks_user_id: str,
    organization_id: str,
    user_info: dict,
    permissions: list[str],
) -> str:
    settings = get_settings()
    secret = (settings.liveblocks_secret_key or "").strip()
    if not secret:
        raise RuntimeError("LIVEBLOCKS_SECRET_KEY is not configured")

    payload = {
        "userId": liveblocks_user_id,
        "userInfo": user_info,
        "organizationId": organization_id,
        "permissions": {room_id: permissions},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LIVEBLOCKS_AUTHORIZE_URL,
                headers={"Authorization": f"Bearer {secret}"},
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else ""
        logger.warning(
            "Liveblocks authorize failed: status=%s body=%s",
            e.response.status_code if e.response else "?",
            detail,
        )
        raise RuntimeError("Liveblocks authorization failed") from e
    except httpx.RequestError as e:
        logger.warning("Liveblocks authorize request error: %s", e)
        raise RuntimeError("Liveblocks service unreachable") from e

    token = data.get("token")
    if not token or not isinstance(token, str):
        raise RuntimeError("Liveblocks response missing token")
    return token
