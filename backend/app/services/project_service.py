"""Project service: CRUD for projects and dashboard aggregates."""

from __future__ import annotations

import uuid
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.sheet import Sheet
from app.models.user import User
from app.services.event_service import log_event
from app.middleware.error_handler import AppException, NotFoundException

logger = logging.getLogger(__name__)


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

    member_count_stmt = select(func.count(User.id)).where(
        User.org_id == org_id, User.deactivated_at.is_(None), User.is_guest.is_(False)
    )
    member_count = (await db.execute(member_count_stmt)).scalar_one()

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
            "sheet_count": sheet_counts.get(p.id, 0),
            "member_count": member_count,
        }
        for p in projects
    ]


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
    status: str | None = None,
) -> Project:
    project = await get_project(db, org_id, project_id)
    changes: dict[str, object] = {}
    if name is not None and name != project.name:
        changes["name"] = name
        project.name = name
    if description is not None and description != project.description:
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
    return project
