from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.router import api_router
from app.middleware.error_handler import RequestIdMiddleware, register_error_handlers
from app.middleware.rate_limit import register_rate_limiter

settings = get_settings()
settings.assert_production_secrets()


def create_app() -> FastAPI:
    in_prod = settings.is_production

    app = FastAPI(
        title="Contruo API",
        description="Construction takeoff platform API",
        version="0.1.0",
        # Hide interactive docs and machine-readable schema in production —
        # they make route enumeration trivial for opportunistic scanners.
        docs_url=None if in_prod else "/docs",
        redoc_url=None if in_prod else "/redoc",
        openapi_url=None if in_prod else "/openapi.json",
    )

    register_error_handlers(app)
    register_rate_limiter(app)

    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_router, prefix="/api/v1")

    # CORS registered after routes so it wraps the full stack (including error responses).
    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.app_url],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id"],
        )

    return app


app = create_app()
