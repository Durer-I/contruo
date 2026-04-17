import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event_log import EventLog

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    payload: dict | None = None,
    session_id: uuid.UUID | None = None,
) -> EventLog:
    """Record an event to the audit log. Called from service layer on every data mutation."""
    event = EventLog(
        org_id=org_id,
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        payload=payload or {},
        session_id=session_id,
    )
    db.add(event)
    await db.flush()
    logger.info(
        "Event logged: %s %s/%s by user %s",
        event_type,
        entity_type,
        entity_id,
        user_id,
    )
    return event
