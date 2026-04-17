"""Sheet-level operations: calibration and text search within a project."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppException, NotFoundException
from app.models.project import Project
from app.models.sheet import Sheet
from app.utils.scale_detect import compute_scale_from_calibration_line

_MAX_SEARCH_LEN = 200
_MAX_RESULTS = 80


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_sheet(
    db: AsyncSession, org_id: uuid.UUID, sheet_id: uuid.UUID
) -> Sheet:
    stmt = select(Sheet).where(Sheet.id == sheet_id, Sheet.org_id == org_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise NotFoundException("sheet", str(sheet_id))
    return row


async def update_sheet_scale(
    db: AsyncSession,
    org_id: uuid.UUID,
    sheet_id: uuid.UUID,
    *,
    pdf_line_length_points: float,
    real_distance: float,
    real_unit: str,
) -> Sheet:
    """Apply manual calibration from a known segment length in PDF user space."""
    if pdf_line_length_points <= 0:
        raise AppException(
            code="INVALID_SCALE_LINE",
            message="pdf_line_length_points must be positive",
            status_code=400,
        )
    if real_distance <= 0:
        raise AppException(
            code="INVALID_SCALE_DISTANCE",
            message="real_distance must be positive",
            status_code=400,
        )

    try:
        detected = compute_scale_from_calibration_line(
            pdf_line_length_points, real_distance, real_unit
        )
    except ValueError as e:
        raise AppException(
            code="INVALID_SCALE_UNIT",
            message=str(e),
            status_code=400,
        ) from e

    sheet = await get_sheet(db, org_id, sheet_id)
    sheet.scale_value = detected.scale_value
    sheet.scale_unit = detected.scale_unit
    sheet.scale_label = detected.scale_label[:100]
    sheet.scale_source = "manual"
    await db.flush()
    return sheet


async def search_project_sheets(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    query: str,
) -> list[dict]:
    """Full-text-ish search across cached ``text_content`` blobs (ILIKE)."""
    q = (query or "").strip()
    if len(q) < 2:
        raise AppException(
            code="SEARCH_QUERY_SHORT",
            message="Search query must be at least 2 characters",
            status_code=400,
        )

    stmt_proj = select(Project.id).where(
        Project.id == project_id, Project.org_id == org_id
    )
    if (await db.execute(stmt_proj)).scalar_one_or_none() is None:
        raise NotFoundException("project", str(project_id))

    esc = _escape_like(q)
    pattern = f"%{esc}%"

    stmt = (
        select(Sheet)
        .where(
            Sheet.org_id == org_id,
            Sheet.project_id == project_id,
            Sheet.text_content.isnot(None),
            Sheet.text_content.ilike(pattern, escape="\\"),
        )
        .order_by(Sheet.plan_id, Sheet.page_number)
        .limit(_MAX_RESULTS)
    )
    sheets = list((await db.execute(stmt)).scalars().all())

    out: list[dict] = []
    q_lower = q.lower()
    for s in sheets:
        text = s.text_content or ""
        lower = text.lower()
        pos = lower.find(q_lower)
        snippet = _snippet_at(text, pos, q)
        out.append(
            {
                "sheet_id": str(s.id),
                "plan_id": str(s.plan_id),
                "page_number": s.page_number,
                "sheet_name": s.sheet_name,
                "snippet": snippet,
                "match_char_offset": pos if pos >= 0 else None,
            }
        )
    return out


_ws = re.compile(r"\s+")


def _snippet_at(text: str, pos: int, query: str) -> str:
    if pos < 0:
        t = _ws.sub(" ", text.strip())
        return t[:_MAX_SEARCH_LEN] + ("…" if len(t) > _MAX_SEARCH_LEN else "")
    start = max(0, pos - 60)
    end = min(len(text), pos + len(query) + 80)
    chunk = text[start:end]
    chunk = _ws.sub(" ", chunk.strip())
    if start > 0:
        chunk = "…" + chunk
    if end < len(text):
        chunk = chunk + "…"
    if len(chunk) > _MAX_SEARCH_LEN:
        chunk = chunk[: _MAX_SEARCH_LEN - 1] + "…"
    return chunk
