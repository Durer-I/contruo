from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.middleware.auth import AuthContext
from app.middleware.error_handler import AppException
from app.schemas.billing import (
    BillingSummaryResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    InvoiceListResponse,
    InvoiceResponse,
    MessageResponse,
    SeatAddConfirmRequest,
    SeatPreviewRequest,
    SeatPreviewResponse,
    SeatScheduleRemoveRequest,
    UpdatePaymentMethodRequest,
    UpdatePaymentMethodResponse,
)
from app.services import billing_service
from app.services.permission_service import Permission, require_permission

router = APIRouter(prefix="/billing")


def _map_billing_value_error(e: ValueError, *, default_code: str = "NO_SUBSCRIPTION") -> AppException:
    msg = str(e)
    if "DODOPAYMENTS_" in msg or "not configured" in msg.lower():
        return AppException(code="BILLING_CONFIG", message=msg, status_code=503)
    return AppException(code=default_code, message=msg, status_code=400)


def _billing_return_urls(return_path: str | None, cancel_path: str | None) -> tuple[str, str]:
    s = get_settings()
    base = (s.app_url or "http://localhost:3000").rstrip("/")
    rp = return_path or "/settings/billing"
    cp = cancel_path or "/settings/billing"
    if not rp.startswith("/"):
        rp = "/" + rp
    if not cp.startswith("/"):
        cp = "/" + cp
    return f"{base}{rp}", f"{base}{cp}"


@router.get("", response_model=BillingSummaryResponse)
async def get_billing_summary(
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_billing_summary(db, auth.org_id)


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    rows = await billing_service.list_invoices(db, auth.org_id)
    return {
        "invoices": [
            InvoiceResponse(
                id=inv.id,
                amount_cents=inv.amount_cents,
                currency=inv.currency,
                description=inv.description,
                pdf_url=inv.pdf_url,
                issued_at=inv.issued_at,
                provider_invoice_id=inv.provider_invoice_id,
                provider_payment_id=inv.provider_payment_id,
            )
            for inv in rows
        ]
    }


@router.get("/invoices/{invoice_id}/file")
async def download_invoice_file(
    invoice_id: str,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    import uuid as uuid_mod

    try:
        iid = uuid_mod.UUID(invoice_id)
    except ValueError:
        raise AppException(code="INVALID_ID", message="Invalid invoice id", status_code=400)
    inv = await billing_service.get_invoice(db, auth.org_id, iid)
    if not inv or not inv.pdf_url:
        raise AppException(
            code="INVOICE_NOT_FOUND",
            message="Invoice or PDF not available",
            status_code=404,
        )
    return RedirectResponse(url=inv.pdf_url, status_code=302)


@router.post("/checkout-session", response_model=CheckoutSessionResponse, status_code=201)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    return_url, cancel_url = _billing_return_urls(body.return_path, body.cancel_path)
    try:
        url = await billing_service.create_checkout_session_for_org(
            org_id=auth.org_id,
            user_email=auth.email,
            return_url=return_url,
            cancel_url=cancel_url,
            seat_count=body.seat_count,
        )
    except ValueError as e:
        raise AppException(code="BILLING_CONFIG", message=str(e), status_code=503) from e
    except RuntimeError as e:
        raise AppException(code="CHECKOUT_FAILED", message=str(e), status_code=502) from e
    return {"checkout_url": url}


@router.post("/seats/preview-add", response_model=SeatPreviewResponse)
async def preview_add_seats(
    body: SeatPreviewRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await billing_service.preview_add_seats(db, auth.org_id, body.add)
    except ValueError as e:
        raise _map_billing_value_error(e, default_code="NO_SUBSCRIPTION") from e


@router.post("/seats/add-confirm", response_model=MessageResponse)
async def confirm_add_seats(
    body: SeatAddConfirmRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    try:
        await billing_service.confirm_add_seats(db, auth.org_id, body.add)
    except ValueError as e:
        raise _map_billing_value_error(e, default_code="SEAT_CHANGE_FAILED") from e
    return {"message": "Seats added; subscription updated."}


@router.post("/seats/schedule-remove", response_model=MessageResponse)
async def schedule_remove_seat(
    body: SeatScheduleRemoveRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    try:
        await billing_service.schedule_remove_seat_at_renewal(db, auth.org_id, body.remove)
    except ValueError as e:
        raise _map_billing_value_error(e, default_code="SEAT_CHANGE_FAILED") from e
    n = body.remove
    return {
        "message": (
            f"{n} seat(s) will be removed at the next renewal (no refund)."
            if n != 1
            else "One seat will be removed at the next renewal (no refund)."
        )
    }


@router.post("/update-payment-method", response_model=UpdatePaymentMethodResponse)
async def update_payment_method(
    body: UpdatePaymentMethodRequest,
    auth: AuthContext = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: AsyncSession = Depends(get_db),
):
    return_url, _ = _billing_return_urls(body.return_path, None)
    try:
        url = await billing_service.create_update_payment_method_session(
            db, auth.org_id, return_url
        )
    except ValueError as e:
        raise AppException(code="NO_SUBSCRIPTION", message=str(e), status_code=400) from e
    except RuntimeError as e:
        raise AppException(code="PAYMENT_METHOD_FAILED", message=str(e), status_code=502) from e
    return {"payment_url": url}
