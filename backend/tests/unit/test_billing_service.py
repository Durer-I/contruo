"""Billing service unit tests (mocked DB)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from dodopayments import ConflictError

from app.models.subscription import Subscription
from app.services import billing_service


def test_total_seats_from_dodo_uses_addon_when_configured():
    addon = MagicMock()
    addon.addon_id = "addon_seat"
    addon.quantity = 4
    dsub = MagicMock()
    dsub.quantity = 1
    dsub.addons = [addon]
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="addon_seat")
        assert billing_service._total_seats_from_dodo_subscription(dsub) == 4


def test_total_seats_from_dodo_falls_back_without_addon_env():
    dsub = MagicMock()
    dsub.quantity = 3
    dsub.addons = []
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="")
        assert billing_service._total_seats_from_dodo_subscription(dsub) == 3


def test_seats_from_scheduled_change_addon():
    addon = MagicMock()
    addon.addon_id = "addon_seat"
    addon.quantity = 2
    sch = MagicMock()
    sch.addons = [addon]
    sch.quantity = 1
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="addon_seat")
        assert billing_service._seats_from_scheduled_change_payload(sch) == 2


def test_seats_from_scheduled_change_base_quantity():
    sch = MagicMock()
    sch.addons = []
    sch.quantity = 4
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="")
        assert billing_service._seats_from_scheduled_change_payload(sch) == 4


def test_current_purchased_and_scheduled_drop_addon():
    addon_cur = MagicMock()
    addon_cur.addon_id = "addon_seat"
    addon_cur.quantity = 10
    addon_sch = MagicMock()
    addon_sch.addon_id = "addon_seat"
    addon_sch.quantity = 7
    sch = MagicMock()
    sch.addons = [addon_sch]
    sch.quantity = 1
    dsub = MagicMock()
    dsub.addons = [addon_cur]
    dsub.scheduled_change = sch
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="addon_seat")
        p, x = billing_service._current_purchased_and_scheduled_drop(dsub)
    assert p == 10
    assert x == 3


def test_estimate_prorated_seat_add_full_when_no_period():
    assert (
        billing_service._estimate_prorated_seat_add_cents(
            n_seats=3,
            price_per_seat_cents=1000,
            period_start=None,
            period_end=None,
        )
        == 3000
    )


def test_estimate_prorated_seat_add_zero_n():
    assert (
        billing_service._estimate_prorated_seat_add_cents(
            n_seats=0,
            price_per_seat_cents=5000,
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        == 0
    )


def test_current_purchased_and_scheduled_drop_none_when_no_reduction():
    dsub = MagicMock()
    dsub.quantity = 5
    dsub.addons = []
    dsub.scheduled_change = None
    with patch("app.services.billing_service.get_settings") as gs:
        gs.return_value = MagicMock(dodopayments_seat_addon_id="")
        p, x = billing_service._current_purchased_and_scheduled_drop(dsub)
    assert p == 5
    assert x == 0


def test_dodo_conflict_error_code_reads_body():
    req = httpx.Request("POST", "https://api.test/subscriptions/x/change-plan/preview")
    resp = httpx.Response(409, request=req)
    exc = ConflictError("x", response=resp, body={"code": "SCHEDULED_PLAN_CHANGE_EXISTS"})
    assert billing_service._dodo_conflict_error_code(exc) == "SCHEDULED_PLAN_CHANGE_EXISTS"
    assert billing_service._dodo_conflict_error_code(ValueError("n")) is None


@pytest.mark.anyio
async def test_dodo_subscription_op_cancel_scheduled_then_retry():
    n = 0

    def op():
        nonlocal n
        n += 1
        if n == 1:
            req = httpx.Request("POST", "https://api.test/subscriptions/x/change-plan/preview")
            resp = httpx.Response(409, request=req)
            raise ConflictError("conflict", response=resp, body={"code": "SCHEDULED_PLAN_CHANGE_EXISTS"})
        return 42

    cancel_called = False

    def cancel(_subscription_id: str) -> None:
        nonlocal cancel_called
        cancel_called = True
        assert _subscription_id == "sub_1"

    async def fake_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("app.services.billing_service.asyncio.to_thread", side_effect=fake_to_thread):
        with patch(
            "app.services.billing_service.billing_dodo.subscription_cancel_scheduled_change_plan",
            cancel,
        ):
            out = await billing_service._dodo_subscription_op_cancel_scheduled_then_retry(
                "sub_1", op, op_label="test_op"
            )
    assert out == 42
    assert n == 2
    assert cancel_called


@pytest.mark.anyio
async def test_schedule_remove_seat_rejects_remove_more_than_allowed():
    db = AsyncMock()
    sub = MagicMock(spec=Subscription)
    sub.payment_provider_id = "sub_dodo"
    sub.seat_count = 4

    n = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal n
        n += 1
        r = MagicMock()
        if n == 1:
            r.scalar_one_or_none = lambda: sub
        else:
            r.scalar_one = lambda: 0  # billable seats in use
        return r

    db.execute = execute_side_effect
    org_id = uuid.uuid4()
    with pytest.raises(ValueError, match="at most 3"):
        await billing_service.schedule_remove_seat_at_renewal(db, org_id, remove=10)


@pytest.mark.anyio
async def test_schedule_remove_seat_rejects_below_billable_members():
    db = AsyncMock()
    sub = MagicMock(spec=Subscription)
    sub.payment_provider_id = "sub_dodo"
    sub.seat_count = 5

    n = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal n
        n += 1
        r = MagicMock()
        if n == 1:
            r.scalar_one_or_none = lambda: sub
        else:
            r.scalar_one = lambda: 4  # 4 active members use seats
        return r

    db.execute = execute_side_effect
    org_id = uuid.uuid4()
    with pytest.raises(ValueError, match="at most 1"):
        await billing_service.schedule_remove_seat_at_renewal(db, org_id, remove=3)


@pytest.mark.anyio
async def test_get_billing_summary_no_subscription():
    db = AsyncMock()
    n = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal n
        n += 1
        r = MagicMock()
        # refresh_subscription + get_subscription for summary
        if n <= 2:
            r.scalar_one_or_none = lambda: None
        else:
            r.scalar_one = lambda: 4
        return r

    db.execute = execute_side_effect
    org_id = uuid.uuid4()
    out = await billing_service.get_billing_summary(db, org_id)
    assert out["has_subscription"] is False
    assert out["seats_used"] == 4
    assert out["seat_count"] is None
    assert out.get("grace_period_ends_at") is None


@pytest.mark.anyio
async def test_get_billing_summary_with_subscription():
    db = AsyncMock()
    sub = MagicMock(spec=Subscription)
    sub.status = "active"
    sub.seat_count = 5
    sub.price_per_seat = 12000
    sub.currency = "USD"
    sub.billing_cycle_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sub.billing_cycle_end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    sub.payment_provider_id = "sub_test"

    n = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal n
        n += 1
        r = MagicMock()
        if n <= 2:
            r.scalar_one_or_none = lambda: sub
        else:
            r.scalar_one = lambda: 3
        return r

    db.execute = execute_side_effect
    org_id = uuid.uuid4()
    with patch("app.services.billing_service._scheduled_seat_change_for_summary", new_callable=AsyncMock) as sch:
        sch.return_value = {
            "scheduled_billed_seats": None,
            "scheduled_seat_change_effective_at": None,
        }
        out = await billing_service.get_billing_summary(db, org_id)
    assert out["has_subscription"] is True
    assert out["seat_count"] == 5
    assert out["seats_used"] == 3
    assert out["next_renewal_total_cents"] == 5 * 12000


@pytest.mark.anyio
@pytest.mark.parametrize("terminal_status", ["cancelled", "suspended"])
async def test_get_billing_summary_terminal_status_offers_resubscribe(terminal_status):
    db = AsyncMock()
    sub = MagicMock(spec=Subscription)
    sub.status = terminal_status
    sub.seat_count = 3
    sub.price_per_seat = 1000
    sub.currency = "USD"
    sub.billing_cycle_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sub.billing_cycle_end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    sub.payment_provider_id = "sub_old"
    sub.card_last_four = None
    sub.card_brand = None
    sub.grace_period_ends_at = None
    sub.first_payment_failed_at = None

    n = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal n
        n += 1
        r = MagicMock()
        if n <= 2:
            r.scalar_one_or_none = lambda: sub
        else:
            r.scalar_one = lambda: 2
        return r

    db.execute = execute_side_effect
    org_id = uuid.uuid4()
    out = await billing_service.get_billing_summary(db, org_id)
    assert out["has_subscription"] is False
    assert out["status"] == terminal_status
    assert out["seat_count"] is None
    assert out["seats_used"] == 2
    assert out["payment_provider_id"] is None


@pytest.mark.anyio
async def test_process_dodopayments_webhook_rejects_when_not_configured():
    db = AsyncMock()
    with patch("app.services.billing_service.get_settings") as gs:
        m = MagicMock()
        m.dodopayments_webhook_secret = ""
        m.is_development = False
        gs.return_value = m
        status, body = await billing_service.process_dodopayments_webhook(
            db, b"{}", {"webhook-id": "wh_test"}
        )
    assert status == 503
    assert body.get("error") == "webhook_not_configured"
