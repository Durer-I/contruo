from fastapi import APIRouter
from app.api.v1 import health, auth, org, projects, plans, sheets

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(org.router, tags=["organization"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(sheets.router, tags=["sheets"])
