"""Issue Liveblocks access tokens via REST and broadcast room events."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

LIVEBLOCKS_AUTHORIZE_URL = "https://api.liveblocks.io/v2/authorize-user"
# OpenAPI path is ``/rooms/{roomId}/broadcast_event`` (underscore) -- the
# hyphenated ``broadcast-event`` URL returns 404 NOT_FOUND from the API.
LIVEBLOCKS_BROADCAST_URL_FMT = "https://api.liveblocks.io/v2/rooms/{room_id}/broadcast_event"

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


def collaboration_room_id(org_id: uuid.UUID, project_id: uuid.UUID) -> str:
    """Canonical room id format: ``contruo:{org_id}:{project_id}``."""
    return f"contruo:{org_id}:{project_id}"


def broadcast_event_sync(
    *,
    room_id: str,
    event_type: str,
    data: dict[str, Any],
    timeout_seconds: float = 5.0,
) -> bool:
    """Push an event into a Liveblocks room via the REST API (sync, for Celery).

    The Celery worker has no async loop and no client connection -- it can't
    use the WebSocket path that the browser SDK does. Instead it POSTs to the
    REST broadcast endpoint, which Liveblocks fans out to every connected
    client in the room.

    Returns True on success, False on any failure. Broadcast failures are
    intentionally non-fatal: AI run state is persisted in Postgres and the
    frontend polls as a backstop, so a missed broadcast just delays the UI
    update by a poll interval. Never raises; always logs.
    """
    settings = get_settings()
    secret = (settings.liveblocks_secret_key or "").strip()
    if not secret:
        logger.warning(
            "broadcast_event_sync skipped: LIVEBLOCKS_SECRET_KEY not configured"
        )
        return False

    payload = {"type": event_type, "data": data}
    url = LIVEBLOCKS_BROADCAST_URL_FMT.format(room_id=room_id)
    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300] if e.response else ""
        logger.warning(
            "Liveblocks broadcast failed room=%s event=%s status=%s body=%s",
            room_id,
            event_type,
            e.response.status_code if e.response else "?",
            body,
        )
        return False
    except httpx.RequestError as e:
        logger.warning(
            "Liveblocks broadcast unreachable room=%s event=%s err=%s",
            room_id,
            event_type,
            e,
        )
        return False
    except Exception:
        logger.exception(
            "Unexpected error broadcasting Liveblocks event room=%s event=%s",
            room_id,
            event_type,
        )
        return False
