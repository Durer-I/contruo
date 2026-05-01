import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.ai_run import AiRun as AiRunModel


class AiRunCreate(BaseModel):
    """Request body for ``POST /projects/{project_id}/ai/runs``.

    ``scope`` is reserved for future per-sheet runs; today only ``full_plan``
    is accepted.
    """

    plan_id: uuid.UUID
    scope: str = Field(default="full_plan", pattern="^(full_plan)$")


class AiRunStageEntry(BaseModel):
    """Per-stage timing payload as stored in ``summary_jsonb["stages"][stage]``."""

    duration_ms: int
    cache_hit: bool
    started_at: str
    finished_at: str
    error: str | None = None


class AiRunResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    triggered_by: uuid.UUID
    status: str
    scope: str
    model_versions: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    cost_cents: int
    tokens_used: int
    items_total: int
    items_accepted_auto: int
    items_pending: int
    items_low_confidence: int
    summary_jsonb: dict[str, Any]
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, run: "AiRunModel") -> "AiRunResponse":
        return cls(
            id=run.id,
            org_id=run.org_id,
            project_id=run.project_id,
            plan_id=run.plan_id,
            triggered_by=run.triggered_by,
            status=run.status,
            scope=run.scope,
            model_versions=run.model_versions or {},
            started_at=run.started_at,
            finished_at=run.finished_at,
            cost_cents=run.cost_cents,
            tokens_used=run.tokens_used,
            items_total=run.items_total,
            items_accepted_auto=run.items_accepted_auto,
            items_pending=run.items_pending,
            items_low_confidence=run.items_low_confidence,
            summary_jsonb=run.summary_jsonb or {},
            error_message=run.error_message,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class AiRunListResponse(BaseModel):
    runs: list[AiRunResponse]


class AiCostByOrgRow(BaseModel):
    org_id: uuid.UUID
    cost_cents: int
    tokens_used: int
    run_count: int


class AiCostByOrgResponse(BaseModel):
    window_hours: int
    rows: list[AiCostByOrgRow]
