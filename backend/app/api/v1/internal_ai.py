"""Internal AI ops endpoints (Sprint AI-01).

Not exposed to customers. Owner-only, scoped to the caller's own org. A future
superadmin role will widen this to cross-org aggregation; until then the
endpoint returns the caller's own org's stats so the route exists for ops
runbooks to reference.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import AuthContext, require_role
from app.schemas.ai_run import AiCostByOrgResponse, AiCostByOrgRow
from app.services import ai_run_service

router = APIRouter(prefix="/internal/ai")


@router.get("/cost-by-org", response_model=AiCostByOrgResponse)
async def cost_by_org(
    auth: AuthContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    """Per-org AI cost rollup over the last 24 hours.

    Owner-only, returns only the caller's own org until a superadmin role exists.
    Useful for debugging the abuse circuit breaker and validating the pricing
    model against real usage.
    """
    rows = await ai_run_service.cost_by_org_last_24h(db)
    own_org_id = str(auth.org_id)
    filtered = [r for r in rows if r["org_id"] == own_org_id]
    return AiCostByOrgResponse(
        window_hours=24,
        rows=[
            AiCostByOrgRow(
                org_id=r["org_id"],
                cost_cents=r["cost_cents"],
                tokens_used=r["tokens_used"],
                run_count=r["run_count"],
            )
            for r in filtered
        ],
    )
