import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BillingSummaryResponse(BaseModel):
    """Owner-facing subscription snapshot for the billing dashboard."""

    has_subscription: bool = Field(
        ...,
        description="True when org has an active paid plan (excludes cancelled/suspended)",
    )
    status: str | None = None
    seat_count: int | None = None
    seats_used: int = Field(..., description="Active, non-guest members (billable seats in use)")
    price_per_seat_cents: int | None = None
    currency: str | None = None
    billing_cycle_start: datetime | None = None
    billing_cycle_end: datetime | None = None
    payment_provider_id: str | None = None
    next_renewal_total_cents: int | None = Field(
        None, description="seat_count * price_per_seat when both are set"
    )
    payment_method_summary: str | None = None
    grace_period_ends_at: datetime | None = None
    first_payment_failed_at: datetime | None = None
    scheduled_billed_seats: int | None = Field(
        None,
        description="Purchased seats after pending Dodo scheduled_change (if different from seat_count)",
    )
    scheduled_seat_change_effective_at: datetime | None = Field(
        None, description="When scheduled seat/plan change takes effect (usually next renewal)"
    )


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    amount_cents: int
    currency: str
    description: str | None
    pdf_url: str | None
    issued_at: datetime
    provider_invoice_id: str | None
    provider_payment_id: str | None = None


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]


class CheckoutSessionRequest(BaseModel):
    return_path: str | None = Field(None, description="Path on app (e.g. /settings/billing)")
    cancel_path: str | None = None
    seat_count: int = Field(default=1, ge=1, le=500)


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class SeatPreviewRequest(BaseModel):
    add: int = Field(default=1, ge=1, le=100)


class SeatPreviewResponse(BaseModel):
    current_seats: int
    new_seats: int
    estimated_charge_cents: int
    currency: str
    had_scheduled_reduction: bool = Field(
        False,
        description="True when a seat drop was scheduled at renewal before this preview",
    )
    renewal_target_seats: int | None = Field(
        None,
        description="Purchased seats after next renewal when it differs from new_seats (mid-cycle)",
    )
    estimated_charge_is_approximate: bool = Field(
        False,
        description="True when charge was estimated locally (Dodo preview unavailable until confirm)",
    )


class SeatAddConfirmRequest(BaseModel):
    add: int = Field(default=1, ge=1, le=100)


class SeatScheduleRemoveRequest(BaseModel):
    remove: int = Field(default=1, ge=1, le=100, description="Seats to drop at next renewal (min 1 seat stays)")


class UpdatePaymentMethodRequest(BaseModel):
    return_path: str | None = Field(default="/settings/billing")


class UpdatePaymentMethodResponse(BaseModel):
    payment_url: str


class MessageResponse(BaseModel):
    message: str
