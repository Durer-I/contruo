"""Subscription billing: DodoPayments, webhooks, seats, invoices (Sprint 14)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing_webhook_delivery import BillingWebhookDelivery
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.models.user import User
from app.services import billing_dodo

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Ended plans: billing UI should offer checkout, not seat management on a dead subscription.
_TERMINAL_BILLING_STATUSES = frozenset({"cancelled", "suspended"})


def subscription_requires_resubscribe(sub: Subscription | None) -> bool:
    """True when a subscription row exists but the plan is no longer active (subscribe again)."""
    return sub is not None and sub.status in _TERMINAL_BILLING_STATUSES


def _payment_method_summary(sub: Subscription) -> str | None:
    if sub.card_last_four and sub.card_brand:
        return f"{sub.card_brand} ····{sub.card_last_four}"
    if sub.card_last_four:
        return f"····{sub.card_last_four}"
    return None


async def count_billable_seats_used(db: AsyncSession, org_id: uuid.UUID) -> int:
    """Active members excluding guests (guests do not consume paid seats)."""
    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.org_id == org_id,
            User.is_guest.is_(False),
            User.deactivated_at.is_(None),
        )
    )
    return int(result.scalar_one())


async def get_subscription(db: AsyncSession, org_id: uuid.UUID) -> Subscription | None:
    result = await db.execute(select(Subscription).where(Subscription.org_id == org_id))
    return result.scalar_one_or_none()


async def find_org_id_by_dodo_subscription_id(
    db: AsyncSession, dodo_subscription_id: str
) -> uuid.UUID | None:
    r = await db.execute(
        select(Subscription.org_id).where(Subscription.payment_provider_id == dodo_subscription_id)
    )
    row = r.scalar_one_or_none()
    return row


async def refresh_subscription_automatic_transitions(
    db: AsyncSession, org_id: uuid.UUID
) -> Subscription | None:
    """Apply time-based status transitions (lazy evaluation on API requests)."""
    sub = await get_subscription(db, org_id)
    if not sub:
        return None
    now = datetime.now(UTC)
    changed = False
    if sub.status == "past_due" and sub.grace_period_ends_at and now >= sub.grace_period_ends_at:
        sub.status = "read_only"
        changed = True
    if (
        sub.status == "read_only"
        and sub.first_payment_failed_at
        and now >= sub.first_payment_failed_at + timedelta(days=30)
    ):
        sub.status = "suspended"
        changed = True
    if changed:
        await db.flush()
    return sub


async def get_org_subscription_status(db: AsyncSession, org_id: uuid.UUID) -> str | None:
    """Expose in /auth/me for banners (any member)."""
    sub = await get_subscription(db, org_id)
    if not sub:
        return None
    await refresh_subscription_automatic_transitions(db, org_id)
    sub2 = await get_subscription(db, org_id)
    return sub2.status if sub2 else None


async def org_seat_capacity_overage(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """True when subscription is active and active billable members exceed purchased seats."""
    await refresh_subscription_automatic_transitions(db, org_id)
    sub = await get_subscription(db, org_id)
    if not sub or sub.status != "active":
        return False
    used = await count_billable_seats_used(db, org_id)
    return used > int(sub.seat_count)


async def scheduled_seat_change_for_org(
    db: AsyncSession, org_id: uuid.UUID, *, skip_refresh: bool = False
) -> dict[str, Any]:
    """Pending seat count after renewal from Dodo (if any), for Team / admin warnings."""
    if not skip_refresh:
        await refresh_subscription_automatic_transitions(db, org_id)
    sub = await get_subscription(db, org_id)
    if not sub:
        return {
            "scheduled_billed_seats": None,
            "scheduled_seat_change_effective_at": None,
        }
    return await _scheduled_seat_change_for_summary(sub)


async def billing_banner_message(db: AsyncSession, org_id: uuid.UUID) -> str | None:
    sub = await get_subscription(db, org_id)
    if not sub:
        return None
    await refresh_subscription_automatic_transitions(db, org_id)
    sub = await get_subscription(db, org_id)
    if not sub:
        return None
    if sub.status == "past_due":
        if sub.grace_period_ends_at:
            g = sub.grace_period_ends_at
            if g.tzinfo is None:
                g = g.replace(tzinfo=UTC)
            return (
                "Payment failed. Update your payment method in Billing — "
                f"grace period ends {g.strftime('%Y-%m-%d %H:%M UTC')}."
            )
        return "Payment failed. Update your payment method in Billing."
    if sub.status == "read_only":
        return (
            "This organization is in read-only mode until billing is resolved. "
            "Open Billing to fix."
        )
    if sub.status in ("suspended", "cancelled"):
        return "This organization is suspended. Open Billing to reactivate."
    if sub.status == "active":
        used = await count_billable_seats_used(db, org_id)
        if used > int(sub.seat_count):
            return (
                "You have more active members than purchased seats. "
                "Add seats in Billing or deactivate members in Team — some actions are limited until this is fixed."
            )
    return None


async def get_billing_summary(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    await refresh_subscription_automatic_transitions(db, org_id)
    sub = await get_subscription(db, org_id)
    seats_used = await count_billable_seats_used(db, org_id)
    if not sub:
        return {
            "has_subscription": False,
            "status": None,
            "seat_count": None,
            "seats_used": seats_used,
            "price_per_seat_cents": None,
            "currency": None,
            "billing_cycle_start": None,
            "billing_cycle_end": None,
            "payment_provider_id": None,
            "next_renewal_total_cents": None,
            "payment_method_summary": None,
            "grace_period_ends_at": None,
            "first_payment_failed_at": None,
            "scheduled_billed_seats": None,
            "scheduled_seat_change_effective_at": None,
        }

    if sub.status in _TERMINAL_BILLING_STATUSES:
        return {
            "has_subscription": False,
            "status": sub.status,
            "seat_count": None,
            "seats_used": seats_used,
            "price_per_seat_cents": None,
            "currency": None,
            "billing_cycle_start": None,
            "billing_cycle_end": None,
            "payment_provider_id": None,
            "next_renewal_total_cents": None,
            "payment_method_summary": None,
            "grace_period_ends_at": None,
            "first_payment_failed_at": None,
            "scheduled_billed_seats": None,
            "scheduled_seat_change_effective_at": None,
        }

    next_total = sub.seat_count * sub.price_per_seat
    scheduled = await _scheduled_seat_change_for_summary(sub)
    return {
        "has_subscription": True,
        "status": sub.status,
        "seat_count": sub.seat_count,
        "seats_used": seats_used,
        "price_per_seat_cents": sub.price_per_seat,
        "currency": sub.currency,
        "billing_cycle_start": sub.billing_cycle_start,
        "billing_cycle_end": sub.billing_cycle_end,
        "payment_provider_id": sub.payment_provider_id,
        "next_renewal_total_cents": next_total,
        "payment_method_summary": _payment_method_summary(sub),
        "grace_period_ends_at": sub.grace_period_ends_at,
        "first_payment_failed_at": sub.first_payment_failed_at,
        **scheduled,
    }


async def list_invoices(db: AsyncSession, org_id: uuid.UUID) -> list[Invoice]:
    result = await db.execute(
        select(Invoice)
        .where(Invoice.org_id == org_id)
        .order_by(Invoice.issued_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())


async def get_invoice(db: AsyncSession, org_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice | None:
    r = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    return r.scalar_one_or_none()


def _org_id_from_metadata(metadata: dict[str, Any] | None) -> uuid.UUID | None:
    if not metadata:
        return None
    raw = metadata.get("org_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _currency_str(cur: Any) -> str:
    if cur is None:
        return "USD"
    if hasattr(cur, "value"):
        return str(cur.value)
    return str(cur)


def _seat_addon_id_optional() -> str | None:
    s = (get_settings().dodopayments_seat_addon_id or "").strip()
    return s or None


def _total_seats_from_dodo_subscription(dsub: Any) -> int:
    """Paid seats: Seat add-on quantity when configured, else subscription line quantity."""
    addon_id = _seat_addon_id_optional()
    addons = list(getattr(dsub, "addons", None) or [])
    if addon_id and addons:
        for a in addons:
            if str(getattr(a, "addon_id", "")) == addon_id:
                return max(int(getattr(a, "quantity", 0)), 1)
        logger.warning(
            "Dodo subscription %s: seat add-on %s not in addons; using line quantity",
            getattr(dsub, "subscription_id", "?"),
            addon_id,
        )
    return max(int(getattr(dsub, "quantity", 1)), 1)


def _price_per_seat_from_dodo(dsub: Any, total_seats: int) -> int:
    recurring = int(getattr(dsub, "recurring_pre_tax_amount", 0))
    q = max(total_seats, 1)
    return max(recurring // q, 1)


def _seats_from_scheduled_change_payload(change: Any) -> int | None:
    """Billable seat count after Dodo's pending scheduled plan change, if parseable."""
    if change is None:
        return None
    addon_id = _seat_addon_id_optional()
    addons = list(getattr(change, "addons", None) or [])
    if addon_id and addons:
        for a in addons:
            if str(getattr(a, "addon_id", "")) == addon_id:
                return max(int(getattr(a, "quantity", 0)), 1)
        return None
    q = getattr(change, "quantity", None)
    if q is not None:
        return max(int(q), 1)
    return None


async def _scheduled_seat_change_for_summary(sub: Subscription) -> dict[str, Any]:
    """Live Dodo state: pending seat count after renewal (scheduled_change), if any."""
    empty: dict[str, Any] = {
        "scheduled_billed_seats": None,
        "scheduled_seat_change_effective_at": None,
    }
    if not sub.payment_provider_id or sub.status in _TERMINAL_BILLING_STATUSES:
        return empty
    try:

        def _fetch():
            return billing_dodo.subscription_retrieve(sub.payment_provider_id)

        dsub = await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.debug("Billing summary: could not retrieve Dodo subscription: %s", e)
        return empty

    sch = getattr(dsub, "scheduled_change", None)
    if not sch:
        return empty
    future = _seats_from_scheduled_change_payload(sch)
    if future is None:
        return empty
    current = int(sub.seat_count)
    if future == current:
        return empty
    eff = getattr(sch, "effective_at", None)
    if eff is not None and getattr(eff, "tzinfo", None) is None:
        eff = eff.replace(tzinfo=UTC)
    if eff is None and sub.billing_cycle_end is not None:
        eff = sub.billing_cycle_end
        if getattr(eff, "tzinfo", None) is None:
            eff = eff.replace(tzinfo=UTC)
    return {
        "scheduled_billed_seats": future,
        "scheduled_seat_change_effective_at": eff,
    }


async def upsert_subscription_from_dodo_subscription(
    db: AsyncSession,
    org_id: uuid.UUID,
    dsub: Any,
) -> Subscription:
    qty = _total_seats_from_dodo_subscription(dsub)
    per_seat = _price_per_seat_from_dodo(dsub, qty)
    cur = _currency_str(getattr(dsub, "currency", None))
    start = dsub.previous_billing_date
    end = dsub.next_billing_date
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    existing = await get_subscription(db, org_id)
    cust_id = None
    if getattr(dsub, "customer", None) is not None:
        cust_id = dsub.customer.customer_id

    if existing:
        row = existing
        row.status = "active"
        row.seat_count = qty
        row.price_per_seat = per_seat
        row.currency = cur
        row.billing_cycle_start = start
        row.billing_cycle_end = end
        row.payment_provider_id = dsub.subscription_id
        row.dodopayments_product_id = dsub.product_id
        if cust_id:
            row.dodopayments_customer_id = str(cust_id)
        row.first_payment_failed_at = None
        row.grace_period_ends_at = None
    else:
        row = Subscription(
            org_id=org_id,
            status="active",
            seat_count=qty,
            price_per_seat=per_seat,
            currency=cur,
            billing_cycle_start=start,
            billing_cycle_end=end,
            payment_provider_id=dsub.subscription_id,
            dodopayments_product_id=dsub.product_id,
            dodopayments_customer_id=str(cust_id) if cust_id else None,
        )
        db.add(row)
    await db.flush()
    return row


async def record_invoice_from_dodo_payment(
    db: AsyncSession, org_id: uuid.UUID, pay: Any
) -> Invoice | None:
    pid = str(pay.payment_id)
    existing = await db.execute(
        select(Invoice.id).where(
            Invoice.org_id == org_id,
            Invoice.provider_payment_id == pid,
        )
    )
    if existing.scalar_one_or_none():
        return None
    ia = getattr(pay, "created_at", None) or datetime.now(UTC)
    if getattr(ia, "tzinfo", None) is None:
        ia = ia.replace(tzinfo=UTC)
    inv = Invoice(
        org_id=org_id,
        amount_cents=int(pay.total_amount),
        currency=_currency_str(getattr(pay, "currency", None)),
        provider_invoice_id=getattr(pay, "invoice_id", None),
        provider_payment_id=pid,
        description="Payment",
        pdf_url=getattr(pay, "invoice_url", None) or None,
        issued_at=ia,
    )
    db.add(inv)
    await db.flush()
    return inv


async def apply_payment_method_from_card(db: AsyncSession, org_id: uuid.UUID, pay: Any) -> None:
    sub = await get_subscription(db, org_id)
    if not sub:
        return
    last4 = getattr(pay, "card_last_four", None)
    brand = getattr(pay, "card_network", None) or getattr(pay, "card_type", None)
    if last4:
        sub.card_last_four = str(last4)
    if brand:
        sub.card_brand = str(brand)[:32]
    await db.flush()


async def clear_billing_failure_flags(db: AsyncSession, org_id: uuid.UUID) -> None:
    sub = await get_subscription(db, org_id)
    if not sub:
        return
    sub.first_payment_failed_at = None
    sub.grace_period_ends_at = None
    if sub.status in ("past_due", "read_only"):
        sub.status = "active"
    await db.flush()


async def mark_subscription_payment_failed(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> None:
    sub = await get_subscription(db, org_id)
    if not sub:
        return
    now = datetime.now(UTC)
    if sub.first_payment_failed_at is None:
        sub.first_payment_failed_at = now
    sub.grace_period_ends_at = sub.first_payment_failed_at + timedelta(days=14)
    if sub.status == "active":
        sub.status = "past_due"
    await db.flush()
    logger.warning(
        "Billing: payment failed for org %s — past_due until %s",
        org_id,
        sub.grace_period_ends_at,
    )


async def dispatch_dodo_webhook_event(db: AsyncSession, event: Any, event_type: str | None) -> None:
    t = event_type or ""

    if t in (
        "subscription.active",
        "subscription.renewed",
        "subscription.updated",
        "subscription.plan_changed",
    ):
        dsub = event.data
        org_id = _org_id_from_metadata(dsub.metadata)
        if not org_id:
            org_id = await find_org_id_by_dodo_subscription_id(db, dsub.subscription_id)
        if not org_id:
            logger.warning("Dodo webhook %s: missing org_id metadata", t)
            return
        await upsert_subscription_from_dodo_subscription(db, org_id, dsub)
        return

    if t == "payment.succeeded":
        pay = event.data
        org_id = _org_id_from_metadata(pay.metadata)
        if not org_id and pay.subscription_id:
            org_id = await find_org_id_by_dodo_subscription_id(db, str(pay.subscription_id))
        if not org_id:
            logger.warning("payment.succeeded: could not resolve org_id")
            return
        inv = await record_invoice_from_dodo_payment(db, org_id, pay)
        await apply_payment_method_from_card(db, org_id, pay)
        await clear_billing_failure_flags(db, org_id)
        if inv is not None:
            try:
                from app.services import email_service, org_service

                org = await org_service.get_org(db, org_id)
                await email_service.send_invoice_receipt_to_org_owner(
                    db,
                    org_id,
                    org_name=org.name,
                    amount_cents=inv.amount_cents,
                    currency=inv.currency,
                    issued_at=inv.issued_at,
                    pdf_url=inv.pdf_url,
                )
            except Exception:
                logger.exception("Invoice receipt email failed for org %s", org_id)
        return

    if t in ("payment.failed",):
        pay = event.data
        org_id = _org_id_from_metadata(pay.metadata)
        if not org_id and getattr(pay, "subscription_id", None):
            org_id = await find_org_id_by_dodo_subscription_id(db, str(pay.subscription_id))
        if org_id:
            await mark_subscription_payment_failed(db, org_id)
        return

    if t in ("subscription.on_hold", "subscription.failed"):
        dsub = event.data
        org_id = _org_id_from_metadata(dsub.metadata) or await find_org_id_by_dodo_subscription_id(
            db, dsub.subscription_id
        )
        if org_id:
            await mark_subscription_payment_failed(db, org_id)
        return

    if t in ("subscription.cancelled", "subscription.expired"):
        dsub = event.data
        org_id = _org_id_from_metadata(dsub.metadata) or await find_org_id_by_dodo_subscription_id(
            db, dsub.subscription_id
        )
        if org_id:
            sub = await get_subscription(db, org_id)
            if sub:
                sub.status = "cancelled" if t == "subscription.cancelled" else "suspended"
                await db.flush()
        return


# ── Checkout & seats (Dodo API) ──────────────────────────────────────


def _require_product_id() -> str:
    s = get_settings()
    pid = (s.dodopayments_subscription_product_id or "").strip()
    if not pid:
        raise ValueError("DODOPAYMENTS_SUBSCRIPTION_PRODUCT_ID is not configured")
    return pid


def _require_seat_addon_id() -> str:
    aid = _seat_addon_id_optional()
    if not aid:
        raise ValueError("DODOPAYMENTS_SEAT_ADDON_ID is not configured")
    return aid


def _seat_addon_cart(seat_quantity: int) -> list[dict[str, int | str]]:
    return [{"addon_id": _require_seat_addon_id(), "quantity": max(int(seat_quantity), 1)}]


def _current_purchased_and_scheduled_drop(dsub: Any) -> tuple[int, int]:
    """P = current purchased seats on Dodo; drop = seats scheduled to come off at renewal (0 if none)."""
    p = _total_seats_from_dodo_subscription(dsub)
    sch = getattr(dsub, "scheduled_change", None)
    if not sch:
        return p, 0
    future = _seats_from_scheduled_change_payload(sch)
    if future is None or future >= p:
        return p, 0
    return p, p - int(future)


def _estimate_prorated_seat_add_cents(
    *,
    n_seats: int,
    price_per_seat_cents: int,
    period_start: datetime | None,
    period_end: datetime | None,
) -> int:
    """Rough prorated charge for adding n_seats mid-cycle (no tax), when Dodo preview cannot run."""
    n = max(int(n_seats), 0)
    if n == 0:
        return 0
    unit = max(int(price_per_seat_cents), 0)
    if unit == 0:
        return 0
    if not period_start or not period_end:
        return n * unit
    pstart = period_start if period_start.tzinfo else period_start.replace(tzinfo=UTC)
    pend = period_end if period_end.tzinfo else period_end.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    total_sec = (pend - pstart).total_seconds()
    if total_sec <= 0:
        return n * unit
    remaining_sec = (pend - now).total_seconds()
    frac = max(0.0, min(1.0, remaining_sec / total_sec))
    return int(n * unit * frac)


async def _cancel_dodo_scheduled_plan_if_present(subscription_id: str) -> None:
    def _fetch() -> Any:
        return billing_dodo.subscription_retrieve(subscription_id)

    dsub = await asyncio.to_thread(_fetch)
    if not getattr(dsub, "scheduled_change", None):
        return

    def _cancel() -> None:
        billing_dodo.subscription_cancel_scheduled_change_plan(subscription_id)

    await asyncio.to_thread(_cancel)


def _preview_change_plan_to_total_seats_callable(
    subscription_id: str, product_id: str, new_total: int
) -> Callable[[], Any]:
    def _call() -> Any:
        if _subscription_uses_seat_addon():
            _require_seat_addon_id()
            return billing_dodo.subscription_preview_change_plan(
                subscription_id,  # type: ignore[arg-type]
                product_id=product_id,
                proration_billing_mode="prorated_immediately",
                quantity=1,
                addons=_seat_addon_cart(new_total),
            )
        return billing_dodo.subscription_preview_change_plan(
            subscription_id,  # type: ignore[arg-type]
            product_id=product_id,
            proration_billing_mode="prorated_immediately",
            quantity=new_total,
        )

    return _call


def _change_plan_immediate_to_total_seats_callable(
    subscription_id: str, product_id: str, new_total: int
) -> Callable[[], None]:
    def _call() -> None:
        if _subscription_uses_seat_addon():
            _require_seat_addon_id()
            billing_dodo.subscription_change_plan(
                subscription_id,  # type: ignore[arg-type]
                product_id=product_id,
                proration_billing_mode="prorated_immediately",
                quantity=1,
                addons=_seat_addon_cart(new_total),
                effective_at="immediately",
            )
        else:
            billing_dodo.subscription_change_plan(
                subscription_id,  # type: ignore[arg-type]
                product_id=product_id,
                proration_billing_mode="prorated_immediately",
                quantity=new_total,
                effective_at="immediately",
            )

    return _call


def _dodo_conflict_error_code(exc: BaseException) -> str | None:
    from dodopayments import ConflictError

    if not isinstance(exc, ConflictError):
        return None
    body = exc.body
    if isinstance(body, dict):
        raw = body.get("code")
        return str(raw) if raw is not None else None
    return None


async def _dodo_subscription_op_cancel_scheduled_then_retry(
    subscription_id: str,
    op: Callable[[], Any],
    *,
    op_label: str,
) -> Any:
    """Run a Dodo preview/change_plan op; on SCHEDULED_PLAN_CHANGE_EXISTS cancel schedule and retry once."""
    from dodopayments import ConflictError

    def _run() -> Any:
        return op()

    try:
        return await asyncio.to_thread(_run)
    except ConflictError as e:
        if _dodo_conflict_error_code(e) != "SCHEDULED_PLAN_CHANGE_EXISTS":
            raise
        logger.info(
            "Dodo: cancelling scheduled plan change then retrying %s (subscription_id=%s)",
            op_label,
            subscription_id,
        )

        def _cancel() -> None:
            billing_dodo.subscription_cancel_scheduled_change_plan(subscription_id)

        await asyncio.to_thread(_cancel)
        return await asyncio.to_thread(_run)


def _subscription_uses_seat_addon() -> bool:
    return _seat_addon_id_optional() is not None


async def create_checkout_session_for_org(
    *,
    org_id: uuid.UUID,
    user_email: str,
    return_url: str,
    cancel_url: str,
    seat_count: int = 1,
) -> str:
    meta = {"org_id": str(org_id), "intent": "subscribe"}
    product_id = _require_product_id()
    seats = max(int(seat_count), 1)

    if _subscription_uses_seat_addon():
        _require_seat_addon_id()
        cart_item: dict[str, Any] = {
            "product_id": product_id,
            "quantity": 1,
            "addons": _seat_addon_cart(seats),
        }
    else:
        cart_item = {"product_id": product_id, "quantity": seats}

    def _call():
        return billing_dodo.checkout_session_create(
            product_cart=[cart_item],
            return_url=return_url,
            cancel_url=cancel_url,
            metadata=meta,
            customer={"email": user_email},
        )

    resp = await asyncio.to_thread(_call)
    url = getattr(resp, "checkout_url", None)
    if not url:
        raise RuntimeError("Dodo checkout did not return checkout_url")
    return str(url)


async def preview_add_seats(db: AsyncSession, org_id: uuid.UUID, add: int) -> dict[str, Any]:
    sub = await get_subscription(db, org_id)
    if not sub or not sub.payment_provider_id:
        raise ValueError("No active Dodo subscription for this organization")
    product_id = sub.dodopayments_product_id or _require_product_id()
    r = max(int(add), 1)

    def _retrieve() -> Any:
        return billing_dodo.subscription_retrieve(sub.payment_provider_id)

    dsub0 = await asyncio.to_thread(_retrieve)
    p, x = _current_purchased_and_scheduled_drop(dsub0)
    cur = _currency_str(getattr(dsub0, "currency", None)) or (sub.currency or "USD")

    # No scheduled reduction: same as before (preview may cancel+retry on Dodo conflict).
    if x == 0:
        new_qty = max(p + r, 1)
        preview = await _dodo_subscription_op_cancel_scheduled_then_retry(
            sub.payment_provider_id,
            _preview_change_plan_to_total_seats_callable(
                sub.payment_provider_id,  # type: ignore[arg-type]
                product_id,
                new_qty,
            ),
            op_label="preview_add_seats",
        )
        total = 0
        ich = getattr(preview, "immediate_charge", None)
        if ich and getattr(ich, "summary", None) is not None and ich.summary.total_amount is not None:
            total = int(ich.summary.total_amount)
        return {
            "current_seats": p,
            "new_seats": new_qty,
            "estimated_charge_cents": total,
            "currency": cur,
            "had_scheduled_reduction": False,
            "renewal_target_seats": None,
            "estimated_charge_is_approximate": False,
        }

    # Scheduled drop x>0; user adds r seats (Interpretation 1: target purchased = p + r - x).
    had = True
    target_now = max(p + r - x, 1)
    renewal_target = max(p - (x - r), 1) if r < x else target_now

    if r < x:
        return {
            "current_seats": p,
            "new_seats": p,
            "estimated_charge_cents": 0,
            "currency": cur,
            "had_scheduled_reduction": had,
            "renewal_target_seats": renewal_target,
            "estimated_charge_is_approximate": False,
        }

    if r == x:
        return {
            "current_seats": p,
            "new_seats": p,
            "estimated_charge_cents": 0,
            "currency": cur,
            "had_scheduled_reduction": had,
            "renewal_target_seats": renewal_target,
            "estimated_charge_is_approximate": False,
        }

    # r > x: preview must NOT cancel the scheduled change (user may abandon the dialog).
    from dodopayments import ConflictError

    op = _preview_change_plan_to_total_seats_callable(
        sub.payment_provider_id,  # type: ignore[arg-type]
        product_id,
        target_now,
    )
    total = 0
    is_approx = False
    try:

        def _run_preview() -> Any:
            return op()

        preview = await asyncio.to_thread(_run_preview)
        ich = getattr(preview, "immediate_charge", None)
        if ich and getattr(ich, "summary", None) is not None and ich.summary.total_amount is not None:
            total = int(ich.summary.total_amount)
    except ConflictError as e:
        if _dodo_conflict_error_code(e) != "SCHEDULED_PLAN_CHANGE_EXISTS":
            raise
        total = _estimate_prorated_seat_add_cents(
            n_seats=r - x,
            price_per_seat_cents=int(sub.price_per_seat or 0),
            period_start=getattr(dsub0, "previous_billing_date", None),
            period_end=getattr(dsub0, "next_billing_date", None),
        )
        is_approx = True
    return {
        "current_seats": p,
        "new_seats": target_now,
        "estimated_charge_cents": total,
        "currency": cur,
        "had_scheduled_reduction": had,
        "renewal_target_seats": renewal_target,
        "estimated_charge_is_approximate": is_approx,
    }


async def _refresh_subscription_row_from_dodo(sub: Subscription) -> None:
    try:

        def _fetch():
            return billing_dodo.subscription_retrieve(sub.payment_provider_id)

        dsub = await asyncio.to_thread(_fetch)
        sub.billing_cycle_start = dsub.previous_billing_date
        sub.billing_cycle_end = dsub.next_billing_date
        total = _total_seats_from_dodo_subscription(dsub)
        sub.seat_count = total
        sub.price_per_seat = _price_per_seat_from_dodo(dsub, total)
    except Exception as e:
        logger.warning("Could not refresh subscription from Dodo: %s", e)


async def confirm_add_seats(db: AsyncSession, org_id: uuid.UUID, add: int) -> Subscription:
    sub = await get_subscription(db, org_id)
    if not sub or not sub.payment_provider_id:
        raise ValueError("No active Dodo subscription for this organization")
    product_id = sub.dodopayments_product_id or _require_product_id()
    r = max(int(add), 1)

    def _retrieve() -> Any:
        return billing_dodo.subscription_retrieve(sub.payment_provider_id)

    dsub0 = await asyncio.to_thread(_retrieve)
    p, x = _current_purchased_and_scheduled_drop(dsub0)

    if x == 0:
        new_qty = max(p + r, 1)
        await _dodo_subscription_op_cancel_scheduled_then_retry(
            sub.payment_provider_id,
            _change_plan_immediate_to_total_seats_callable(
                sub.payment_provider_id,  # type: ignore[arg-type]
                product_id,
                new_qty,
            ),
            op_label="confirm_add_seats",
        )
        sub.seat_count = new_qty
        await _refresh_subscription_row_from_dodo(sub)
        await db.flush()
        return sub

    if r < x:
        await _cancel_dodo_scheduled_plan_if_present(sub.payment_provider_id)
        await schedule_remove_seat_at_renewal(db, org_id, remove=x - r)
        await _refresh_subscription_row_from_dodo(sub)
        await db.flush()
        return sub

    if r == x:
        await _cancel_dodo_scheduled_plan_if_present(sub.payment_provider_id)
        await _refresh_subscription_row_from_dodo(sub)
        await db.flush()
        return sub

    target_now = max(p + r - x, 1)
    await _cancel_dodo_scheduled_plan_if_present(sub.payment_provider_id)
    await _dodo_subscription_op_cancel_scheduled_then_retry(
        sub.payment_provider_id,
        _change_plan_immediate_to_total_seats_callable(
            sub.payment_provider_id,  # type: ignore[arg-type]
            product_id,
            target_now,
        ),
        op_label="confirm_add_seats",
    )
    sub.seat_count = target_now
    await _refresh_subscription_row_from_dodo(sub)
    await db.flush()
    return sub


async def schedule_remove_seat_at_renewal(db: AsyncSession, org_id: uuid.UUID, remove: int = 1) -> Subscription:
    """Lower billed seat count at next renewal (no refund for current period)."""
    sub = await get_subscription(db, org_id)
    if not sub or not sub.payment_provider_id:
        raise ValueError("No active Dodo subscription for this organization")
    rm = max(int(remove), 1)
    seats_used = await count_billable_seats_used(db, org_id)
    # After renewal, purchased seats = seat_count - rm; must stay >= billable seats in use (and >= 1).
    max_by_min_one = max(sub.seat_count - 1, 0)
    max_by_usage = sub.seat_count - seats_used
    max_removable = max(0, min(max_by_min_one, max_by_usage))
    if max_removable == 0:
        if seats_used >= sub.seat_count:
            raise ValueError(
                "Every purchased seat is taken by an active member. Remove or deactivate members first "
                "before you can schedule fewer seats at renewal."
            )
        raise ValueError("Seat count is already at minimum (1)")
    if rm > max_removable:
        raise ValueError(
            f"You can schedule removing at most {max_removable} seat(s) at renewal "
            f"({seats_used} active member(s) use purchased seats; at least one purchased seat must remain)."
        )
    new_qty = sub.seat_count - rm
    product_id = sub.dodopayments_product_id or _require_product_id()

    def _call():
        if _subscription_uses_seat_addon():
            _require_seat_addon_id()
            billing_dodo.subscription_change_plan(
                sub.payment_provider_id,  # type: ignore[arg-type]
                product_id=product_id,
                proration_billing_mode="full_immediately",
                quantity=1,
                addons=_seat_addon_cart(new_qty),
                effective_at="next_billing_date",
            )
        else:
            billing_dodo.subscription_change_plan(
                sub.payment_provider_id,  # type: ignore[arg-type]
                product_id=product_id,
                proration_billing_mode="full_immediately",
                quantity=new_qty,
                effective_at="next_billing_date",
            )

    await asyncio.to_thread(_call)
    # Local seat_count stays until Dodo sends subscription.updated / renewed (next cycle).
    await db.flush()
    return sub


async def create_update_payment_method_session(
    db: AsyncSession, org_id: uuid.UUID, return_url: str
) -> str:
    sub = await get_subscription(db, org_id)
    if not sub or not sub.payment_provider_id:
        raise ValueError("No active Dodo subscription for this organization")

    def _call():
        r = billing_dodo.subscription_update_payment_method(
            sub.payment_provider_id, type="new", return_url=return_url
        )
        return getattr(r, "payment_link", None) or getattr(r, "client_secret", None)

    link = await asyncio.to_thread(_call)
    if not link:
        raise RuntimeError("Dodo did not return a payment link for update-payment-method")
    return str(link)


async def can_invite_billable_member(db: AsyncSession, org_id: uuid.UUID) -> bool:
    sub = await get_subscription(db, org_id)
    if not sub:
        return True
    if sub.status in ("suspended", "cancelled"):
        return False
    used = await count_billable_seats_used(db, org_id)
    return used < sub.seat_count


def _unwrap_webhook_sync(
    payload: str,
    headers: Mapping[str, str],
    *,
    webhook_secret: str,
    api_key: str,
    environment: str,
    unsafe_without_secret: bool,
) -> Any:
    from dodopayments import DodoPayments

    if unsafe_without_secret:
        client = DodoPayments(bearer_token=api_key or "unused")
        return client.webhooks.unsafe_unwrap(payload)

    client = DodoPayments(
        bearer_token=api_key or "unused",
        webhook_key=webhook_secret,
        environment=environment,
    )
    return client.webhooks.unwrap(
        payload,
        headers={
            "webhook-id": headers.get("webhook-id") or headers.get("Webhook-Id") or "",
            "webhook-signature": headers.get("webhook-signature")
            or headers.get("Webhook-Signature")
            or "",
            "webhook-timestamp": headers.get("webhook-timestamp")
            or headers.get("Webhook-Timestamp")
            or "",
        },
    )


def _event_type_from_unwrapped(event: Any) -> str | None:
    if hasattr(event, "type"):
        return str(getattr(event, "type"))
    return None


def _event_to_payload_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        try:
            return event.model_dump(mode="json")
        except Exception:
            pass
    return {"repr": repr(event)}


async def try_record_webhook_delivery(
    db: AsyncSession,
    *,
    webhook_id: str,
    event_type: str | None,
    payload: dict[str, Any],
) -> bool:
    existing = await db.execute(
        select(BillingWebhookDelivery.id).where(BillingWebhookDelivery.webhook_id == webhook_id)
    )
    if existing.scalar_one_or_none():
        return False
    db.add(
        BillingWebhookDelivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
        )
    )
    await db.flush()
    return True


async def process_dodopayments_webhook(
    db: AsyncSession,
    raw_body: bytes,
    headers: Mapping[str, str],
) -> tuple[int, dict[str, Any]]:
    settings = get_settings()
    body_str = raw_body.decode("utf-8")

    wid = (headers.get("webhook-id") or headers.get("Webhook-Id") or "").strip()
    if not wid:
        import hashlib

        wid = hashlib.sha256(raw_body).hexdigest()

    secret = (settings.dodopayments_webhook_secret or "").strip()
    unsafe_dev = not secret and settings.is_development

    if not secret and not unsafe_dev:
        logger.warning("DodoPayments webhook rejected: DODOPAYMENTS_WEBHOOK_SECRET not set")
        return 503, {"error": "webhook_not_configured"}

    try:
        event = await asyncio.to_thread(
            _unwrap_webhook_sync,
            body_str,
            headers,
            webhook_secret=secret,
            api_key=(settings.dodopayments_api_key or "").strip(),
            environment=(settings.dodopayments_environment or "test_mode").strip(),
            unsafe_without_secret=unsafe_dev,
        )
    except Exception as e:
        logger.warning("DodoPayments webhook verify failed: %s", e)
        return 401, {"error": "invalid_signature"}

    event_type = _event_type_from_unwrapped(event)
    payload_dict = _event_to_payload_dict(event)

    is_new = await try_record_webhook_delivery(
        db, webhook_id=wid, event_type=event_type, payload=payload_dict
    )
    if not is_new:
        return 200, {"received": True, "duplicate": True}

    try:
        await dispatch_dodo_webhook_event(db, event, event_type)
    except Exception as e:
        logger.exception("Dodo webhook handler error: %s", e)
        return 500, {"error": "handler_failed", "detail": str(e)[:200]}

    return 200, {"received": True, "duplicate": False}
