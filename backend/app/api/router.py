from fastapi import APIRouter, Depends

from app.api.v1 import (
    ai_runs,
    assemblies,
    auth,
    billing,
    conditions,
    export_routes,
    health,
    internal_ai,
    liveblocks,
    measurements,
    org,
    plan_title_block,
    plans,
    projects,
    sheets,
    webhooks_dodopayments,
)
from app.middleware.subscription_guard import enforce_org_subscription_state

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(webhooks_dodopayments.router)

protected = APIRouter(dependencies=[Depends(enforce_org_subscription_state)])
protected.include_router(org.router, tags=["organization"])
protected.include_router(projects.router, tags=["projects"])
protected.include_router(plans.router, tags=["plans"])
protected.include_router(plan_title_block.router)
protected.include_router(sheets.router, tags=["sheets"])
protected.include_router(conditions.router, tags=["conditions"])
protected.include_router(assemblies.router, tags=["assemblies"])
protected.include_router(measurements.router, tags=["measurements"])
protected.include_router(export_routes.router)
protected.include_router(liveblocks.router)
protected.include_router(billing.router, tags=["billing"])
protected.include_router(ai_runs.router, tags=["ai-runs"])
protected.include_router(internal_ai.router, tags=["internal-ai"])

api_router.include_router(protected)
