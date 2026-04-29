from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Minimal liveness probe — never exposes environment/version metadata."""
    return {"status": "ok"}
