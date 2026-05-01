"""Schemas for the title-block / auto-name-sheets API surface (Sprint AI-02b).

Today this module exposes a single response shape for the
``POST /projects/{pid}/plans/{plan_id}/auto-name-sheets`` endpoint. A future
``SetManualTitleBlockRequest`` (the user-drawn-bbox follow-on) belongs here
too -- keeping all title-block schemas in one file gives the redesign a
single import surface to evolve without touching ``schemas/plan.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AutoNameSheetsRequest(BaseModel):
    """Optional flags for the user-triggered auto-name task."""

    #: When true, sheets with ``sheet_name_source = 'manual'`` are processed too.
    overwrite_manual: bool = Field(default=False)


class AutoNameSheetsResponse(BaseModel):
    """Returned by the auto-name endpoint immediately after the task is queued.

    The endpoint replies 202 -- the actual rename happens in the background
    Celery task ``ai_pipeline.reextract_plan_titles``. The frontend uses the
    Liveblocks ``sheets.auto_named`` broadcast to refetch the sheet list, with
    a polling backstop on top.
    """

    plan_id: uuid.UUID
    task_id: str
    queued_at: datetime
