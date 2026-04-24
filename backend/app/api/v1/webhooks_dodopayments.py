"""DodoPayments Standard Webhooks (no JWT)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services import billing_service

router = APIRouter(prefix="/webhooks")


@router.post("/dodopayments")
async def dodopayments_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    status, body = await billing_service.process_dodopayments_webhook(db, raw, headers)
    return JSONResponse(content=body, status_code=status)
