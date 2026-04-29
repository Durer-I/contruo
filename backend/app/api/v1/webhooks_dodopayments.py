"""DodoPayments Standard Webhooks (no JWT)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rate_limit import limiter
from app.services import billing_service

router = APIRouter(prefix="/webhooks")


@router.post("/dodopayments")
@limiter.limit("60/minute")
async def dodopayments_webhook(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    status, body = await billing_service.process_dodopayments_webhook(db, raw, headers)
    return JSONResponse(content=body, status_code=status)
