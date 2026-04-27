"""Project service: CRUD for projects and dashboard aggregates."""

from __future__ import annotations

import uuid
import logging

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.sheet import Sheet
from app.models.user import User
from app.models.guest_project_access import GuestProjectAccess
from app.models.event_log import EventLog
from app.services.event_service import log_event
from app.middleware.error_handler import AppException, NotFoundException
from app.utils import storage

logger = logging.getLogger(__name__)

#: Max cover upload size (JPEG/PNG/WebP).
MAX_PROJECT_COVER_BYTES = 8 * 1024 * 1024
_COVER_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def project_cover_signed_url(path: str | None) -> str | None:
    if not path:
        return None
    return storage.signed_url(storage.PROJECT_COVERS_BUCKET, path)


async def create_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    created_by: uuid.UUID,
    *,
    name: str,
    description: str | None = None,
) -> Project:
    project = Project(
        org_id=org_id,
        name=name,
        description=description,
        created_by=created_by,
        status="active",
    )
    db.add(project)
    await db.flush()

    await log_event(
        db,
        org_id=org_id,
        user_id=created_by,
        project_id=project.id,
        event_type="project.created",
        entity_type="project",
        entity_id=project.id,
        payload={"name": name},
    )
    return project


async def list_projects(db: AsyncSession, org_id: uuid.UUID) -> list[dict]:
    """List projects with sheet + member counts.

    Member count is the number of active (non-deactivated) users in the org, since
    we don't have per-project membership at MVP. Guest access adds guest users to
    specific projects, but counting them would require joining guest_project_access
    — defer until we have real per-project members.
    """
    # Sheet counts per project
    sheet_counts_stmt = (
        select(Sheet.project_id, func.count(Sheet.id).label("c"))
        .where(Sheet.org_id == org_id)
        .group_by(Sheet.project_id)
    )
    sheet_counts_result = await db.execute(sheet_counts_stmt)
    sheet_counts = {row.project_id: row.c for row in sheet_counts_result}

    member_count = await count_active_org_members(db, org_id)

    projects_stmt = (
        select(Project)
        .where(Project.org_id == org_id, Project.status == "active")
        .order_by(Project.updated_at.desc())
    )
    result = await db.execute(projects_stmt)
    projects = result.scalars().all()

    return [
        {
            "id": p.id,
            "org_id": p.org_id,
            "name": p.name,
            "description": p.description,
            "status": p.status,
            "created_by": p.created_by,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "cover_image_url": project_cover_signed_url(p.cover_image_path),
            "sheet_count": sheet_counts.get(p.id, 0),
            "member_count": member_count,
        }
        for p in projects
    ]


async def count_sheets_for_project(
    db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID
) -> int:
    stmt = select(func.count(Sheet.id)).where(
        Sheet.org_id == org_id, Sheet.project_id == project_id
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def count_active_org_members(db: AsyncSession, org_id: uuid.UUID) -> int:
    """Active non-guest users in the org (same aggregate as the project list cards)."""
    stmt = select(func.count(User.id)).where(
        User.org_id == org_id,
        User.deactivated_at.is_(None),
        User.is_guest.is_(False),
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def get_project(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.org_id == org_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundException("project", str(project_id))
    return project


async def update_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    acting_user_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    #: True when the client JSON included ``description`` (including explicit ``null`` to clear).
    description_provided: bool = False,
    status: str | None = None,
) -> Project:
    project = await get_project(db, org_id, project_id)
    changes: dict[str, object] = {}
    if name is not None and name != project.name:
        changes["name"] = name
        project.name = name
    if description_provided and description != project.description:
        changes["description"] = description
        project.description = description
    if status is not None and status != project.status:
        if status not in ("active", "archived"):
            raise AppException(code="INVALID_STATUS", message="Invalid project status", status_code=400)
        changes["status"] = status
        project.status = status

    if changes:
        await db.flush()
        await log_event(
            db,
            org_id=org_id,
            user_id=acting_user_id,
            project_id=project.id,
            event_type="project.updated",
            entity_type="project",
            entity_id=project.id,
            payload=changes,
        )
        await db.refresh(project)
    return project


async def upload_project_cover(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    acting_user_id: uuid.UUID,
    *,
    content: bytes,
    content_type: str | None,
) -> Project:
    """Store a JPEG/PNG/WebP cover in Supabase; replaces any previous cover object."""
    project = await get_project(db, org_id, project_id)
    raw_ct = (content_type or "").split(";")[0].strip().lower()
    ext = _COVER_CONTENT_TYPES.get(raw_ct)
    if not ext:
        raise AppException(
            code="INVALID_COVER_TYPE",
            message="Cover must be a JPEG, PNG, or WebP image",
            status_code=400,
        )
    if len(content) > MAX_PROJECT_COVER_BYTES:
        raise AppException(
            code="COVER_TOO_LARGE",
            message=f"Cover image must be at most {MAX_PROJECT_COVER_BYTES // (1024 * 1024)} MB",
            status_code=400,
        )

    storage.ensure_bucket(storage.PROJECT_COVERS_BUCKET, public=False)
    new_path = storage.project_cover_storage_path(org_id, project_id, ext)
    old_path = project.cover_image_path
    if old_path and old_path != new_path:
        storage.remove_files(storage.PROJECT_COVERS_BUCKET, [old_path])

    storage.upload_bytes(
        storage.PROJECT_COVERS_BUCKET,
        new_path,
        content,
        content_type=raw_ct,
        upsert=True,
    )
    project.cover_image_path = new_path
    await db.flush()
    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        project_id=project.id,
        event_type="project.cover_updated",
        entity_type="project",
        entity_id=project.id,
        payload={},
    )
    # ``flush`` for EventLog can expire ``Project`` columns (e.g. ``updated_at``); avoid lazy IO in async route.
    await db.refresh(project)
    return project


async def delete_project(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    acting_user_id: uuid.UUID,
) -> None:
    """Permanently delete a project, its plans/sheets (DB cascade), guest access, and storage files."""
    from app.services import plan_service

    project = await get_project(db, org_id, project_id)
    name = project.name

    plans = await plan_service.list_project_plans(db, org_id, project_id)
    sheets = await plan_service.list_project_sheets(db, org_id, project_id)

    plan_paths = [p.storage_path for p in plans if p.storage_path]
    thumb_paths = [s.thumbnail_path for s in sheets if s.thumbnail_path]
    cover_path = project.cover_image_path

    if plan_paths:
        storage.remove_files(storage.PLANS_BUCKET, plan_paths)
    if thumb_paths:
        storage.remove_files(storage.THUMBNAILS_BUCKET, thumb_paths)
    if cover_path:
        storage.remove_files(storage.PROJECT_COVERS_BUCKET, [cover_path])

    await db.execute(
        delete(GuestProjectAccess).where(
            GuestProjectAccess.org_id == org_id,
            GuestProjectAccess.project_id == project_id,
        )
    )
    await db.execute(
        update(EventLog)
        .where(EventLog.org_id == org_id, EventLog.project_id == project_id)
        .values(project_id=None)
    )

    await log_event(
        db,
        org_id=org_id,
        user_id=acting_user_id,
        project_id=project.id,
        event_type="project.deleted",
        entity_type="project",
        entity_id=project.id,
        payload={"name": name},
    )

    await db.execute(delete(Project).where(Project.id == project_id, Project.org_id == org_id))
    await db.flush()
