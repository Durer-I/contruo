"""Rate limiting middleware backed by SlowAPI.

In production we use Redis as the storage backend so multiple FastAPI workers share
counters; in development we fall back to in-memory (single process) to avoid a hard
Redis dependency for local runs without docker.

Apply per-route limits via ``@limiter.limit("...")`` on a route function. The limiter
needs ``request: Request`` as a parameter (SlowAPI extracts the client identifier
from it) — most routes already accept that or accept ``Depends(...)`` which we leave
untouched.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.middleware.error_handler import request_id_ctx

logger = logging.getLogger(__name__)


def _key_func(request: Request) -> str:
    """Identify the caller: prefer authenticated user, fall back to client IP.

    Using the user id when available means a noisy NAT (multiple users behind one IP)
    is not punished collectively, while unauthenticated traffic is still bucketed by IP.
    """
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return f"bearer:{auth[7:][:32]}"
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    settings = get_settings()
    storage_uri: str | None = None
    if settings.redis_url and not settings.redis_url.startswith("redis://localhost"):
        storage_uri = settings.redis_url
    elif settings.is_production:
        storage_uri = settings.redis_url

    return Limiter(
        key_func=_key_func,
        storage_uri=storage_uri,
        default_limits=["300/minute"],
        headers_enabled=True,
    )


limiter: Limiter = _build_limiter()


async def _rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests. Please slow down and try again shortly.",
                "details": {"limit": str(exc.detail)},
                "request_id": request_id_ctx.get(),
            }
        },
        headers={"Retry-After": "30"},
    )


def register_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
