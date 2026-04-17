from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.router import api_router
from app.middleware.error_handler import register_error_handlers

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Contruo API",
        description="Construction takeoff platform API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    register_error_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    # CORS registered after routes so it wraps the full stack (including error responses).
    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.app_url],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return app


app = create_app()
