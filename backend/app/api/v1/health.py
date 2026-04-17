from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": "0.1.0",
    }
