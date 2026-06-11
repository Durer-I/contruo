"""Stage 3a sheet selection.

The schedule and legend extractors should NEVER run on every page of a plan
set. The prototype (``AI/controller/title.py`` -> ``AI/controller/schedules.py``)
proves the right gate is a keyword match on the sheet's *title* (our
``sheets.sheet_name``) -- the AI-02 sheet-type classifier has accuracy
problems that AI-03c will address separately, and skipping classified-but-
unrelated sheets would silently drop real schedules whenever the classifier
guesses wrong.

Two helpers, one query each, sorted by ``page_number`` so the worker
processes sheets in document order (matches operator intuition when
inspecting the run summary).
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.sheet import Sheet


#: Substrings (lowercase) that flag a sheet as worth a schedule-extract pass.
#: Mirrors the prototype's ``keywords = ['schedule']`` but slightly broader --
#: equipment / fixture / panel schedules are common on MEP sets and routinely
#: omit the word "schedule" from the sheet title (e.g. ``"M-601 EQUIPMENT"``,
#: ``"P-601 FIXTURE LIST"``).
SCHEDULE_KEYWORDS: tuple[str, ...] = (
    "schedule",
)

#: Substrings (lowercase) that flag a sheet as worth a legend-extract pass.
#: Targeted -- expanding too far re-introduces the "extract on every sheet"
#: cost problem the user explicitly called out. ``finish floor plan`` /
#: ``rcp`` are included because MEP / interior sets often place the legend
#: directly on the first plan sheet of the discipline (no dedicated legend
#: sheet), and the detector is cheap when nothing matches.
LEGEND_KEYWORDS: tuple[str, ...] = (
    "reflected ceiling",
    "rcp",
    "finish floor plan",
    "finishes",
    "finish",
    "floor",
    "plan",
    "floor plan",
)


def _build_or_filter(column, keywords: tuple[str, ...]):
    return or_(*(column.ilike(f"%{kw}%") for kw in keywords))


def select_schedule_sheets(
    db: Session,
    *,
    plan_id: uuid.UUID,
) -> list[Sheet]:
    """Return sheets in ``plan_id`` whose ``sheet_name`` flags them as
    schedule-bearing.

    Caller is the Celery worker, holding a sync ``Session`` with service-role
    credentials -- RLS is bypassed; the explicit ``plan_id`` filter is the
    boundary. Order is by page number so the schedule extractor walks the
    plan top-to-bottom.

    Returns an empty list (not None) when no sheets match -- the extractor's
    no-op handling is uniform.
    """
    stmt = (
        select(Sheet)
        .where(
            Sheet.plan_id == plan_id,
            Sheet.sheet_name.is_not(None),
            _build_or_filter(Sheet.sheet_name, SCHEDULE_KEYWORDS),
        )
        .order_by(Sheet.page_number.asc())
    )
    return list(db.execute(stmt).scalars().all())


def select_legend_sheets(
    db: Session,
    *,
    plan_id: uuid.UUID,
) -> list[Sheet]:
    """Mirror of ``select_schedule_sheets`` but for legend-bearing sheets."""
    stmt = (
        select(Sheet)
        .where(
            Sheet.plan_id == plan_id,
            Sheet.sheet_name.is_not(None),
            _build_or_filter(Sheet.sheet_name, LEGEND_KEYWORDS),
        )
        .order_by(Sheet.page_number.asc())
    )
    return list(db.execute(stmt).scalars().all())


def matches_schedule_keywords(sheet_name: str | None) -> bool:
    """In-Python predicate version of the SQL filter -- lets tests assert
    the keyword set without spinning up a database session.
    """
    if not sheet_name:
        return False
    lowered = sheet_name.lower()
    return any(kw in lowered for kw in SCHEDULE_KEYWORDS)


def matches_legend_keywords(sheet_name: str | None) -> bool:
    if not sheet_name:
        return False
    lowered = sheet_name.lower()
    return any(kw in lowered for kw in LEGEND_KEYWORDS)
