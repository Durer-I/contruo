"""Synchronous DodoPayments API client (used from asyncio.to_thread)."""

from __future__ import annotations

from typing import Any

from app.config import get_settings


def dodo_client():
    from dodopayments import DodoPayments

    s = get_settings()
    key = (s.dodopayments_api_key or "").strip()
    if not key:
        raise RuntimeError("DODOPAYMENTS_API_KEY is not configured")
    return DodoPayments(
        bearer_token=key,
        environment=(s.dodopayments_environment or "test_mode").strip(),
    )


def checkout_session_create(**kwargs: Any) -> Any:
    return dodo_client().checkout_sessions.create(**kwargs)


def subscription_preview_change_plan(subscription_id: str, **kwargs: Any) -> Any:
    return dodo_client().subscriptions.preview_change_plan(subscription_id, **kwargs)


def subscription_change_plan(subscription_id: str, **kwargs: Any) -> None:
    return dodo_client().subscriptions.change_plan(subscription_id, **kwargs)


def subscription_cancel_scheduled_change_plan(subscription_id: str) -> None:
    """Remove pending next-cycle plan change so a new preview/change_plan can run."""
    return dodo_client().subscriptions.cancel_change_plan(subscription_id)


def subscription_update_payment_method(subscription_id: str, **kwargs: Any) -> Any:
    return dodo_client().subscriptions.update_payment_method(subscription_id, **kwargs)


def subscription_retrieve(subscription_id: str) -> Any:
    return dodo_client().subscriptions.retrieve(subscription_id)
