from fastapi import APIRouter, Depends

from app.api.v1 import (
    assemblies,
    auth,
    billing,
    conditions,
    export_routes,
    health,
    liveblocks,
    measurements,
    org,
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
protected.include_router(sheets.router, tags=["sheets"])
protected.include_router(conditions.router, tags=["conditions"])
protected.include_router(assemblies.router, tags=["assemblies"])
protected.include_router(measurements.router, tags=["measurements"])
protected.include_router(export_routes.router)
protected.include_router(liveblocks.router)
protected.include_router(billing.router, tags=["billing"])

api_router.include_router(protected)
