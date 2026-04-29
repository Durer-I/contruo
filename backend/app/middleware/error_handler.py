import logging
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

#: Per-request correlation id (set by RequestIdMiddleware, surfaced in logs and 500 responses).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(
            code=f"{entity.upper()}_NOT_FOUND",
            message=f"{entity} with ID {entity_id} not found",
            status_code=404,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(code="FORBIDDEN", message=message, status_code=403)


class UnauthorizedException(AppException):
    def __init__(
        self,
        message: str = "Authentication required",
        *,
        code: str = "UNAUTHORIZED",
    ):
        super().__init__(code=code, message=message, status_code=401)


class ConflictException(AppException):
    def __init__(self, message: str, *, code: str = "CONFLICT", details: dict | None = None):
        super().__init__(code=code, message=message, status_code=409, details=details)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request for log correlation + 500 responses."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("x-request-id") or uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["x-request-id"] = rid
        return response


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id_ctx.get(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = request_id_ctx.get()
        logger.exception(
            "Unhandled exception (request_id=%s, path=%s): %s",
            rid,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred. Please try again or contact support with the request id.",
                    "details": {},
                    "request_id": rid,
                }
            },
        )
