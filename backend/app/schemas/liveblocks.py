"""Request/response for Liveblocks custom auth."""

from pydantic import BaseModel, Field


class LiveblocksAuthRequest(BaseModel):
    """Body from the Liveblocks client (and our SPA) when requesting a room token."""

    room: str = Field(..., min_length=1, description="Room id, e.g. contruo:{org_id}:{project_id}")


class LiveblocksAuthResponse(BaseModel):
    """Plain JSON expected by @liveblocks/client (not wrapped in error envelope)."""

    token: str
