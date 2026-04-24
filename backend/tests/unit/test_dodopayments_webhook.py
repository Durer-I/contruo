"""DodoPayments webhook route (mocked billing_service)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_dodopayments_webhook_delegates_to_service():
    with patch(
        "app.api.v1.webhooks_dodopayments.billing_service.process_dodopayments_webhook",
        new_callable=AsyncMock,
        return_value=(200, {"received": True, "duplicate": False}),
    ) as proc:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/webhooks/dodopayments",
                content=b'{"type":"payment.succeeded"}',
                headers={"webhook-id": "wh_1", "content-type": "application/json"},
            )
        assert r.status_code == 200
        assert r.json()["received"] is True
        proc.assert_awaited_once()
