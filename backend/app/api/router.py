from fastapi import APIRouter
from app.api.v1 import health, auth, org, projects, plans, sheets, conditions, measurements, assemblies

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(org.router, tags=["organization"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(sheets.router, tags=["sheets"])
api_router.include_router(conditions.router, tags=["conditions"])
api_router.include_router(assemblies.router, tags=["assemblies"])
api_router.include_router(measurements.router, tags=["measurements"])
