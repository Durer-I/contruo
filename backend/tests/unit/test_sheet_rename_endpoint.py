"""Sprint AI-02b: PATCH /api/v1/sheets/{id} inline rename endpoint.

Mocks at the boundaries:

* ``sheet_service.rename_sheet`` -- exercised separately in service tests; the
  endpoint test only verifies routing, permission, and serialization.
* ``plan_service.sheet_thumbnail_signed_url`` -- avoids a real Supabase
  signed-URL call.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import AuthContext


def _ctx(role: str = "estimator") -> AuthContext:
    return AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=role,
        email=f"{role}@test.com",
    )


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def _override_auth(ctx: AuthContext) -> None:
    from app.middleware.auth import get_current_user

    async def _fake() -> AuthContext:
        return ctx

    app.dependency_overrides[get_current_user] = _fake


def _override_db(db) -> None:
    from app.dependencies import get_db

    async def _fake():
        yield db

    app.dependency_overrides[get_db] = _fake


@pytest.fixture(autouse=True)
def _disable_subscription_guard():
    with patch(
        "app.services.billing_service.get_subscription",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()


def _make_sheet(*, sheet_name: str, source: str | None = "manual") -> MagicMock:
    """Build a Sheet-shaped mock that satisfies ``_serialize_sheet``."""
    sheet = MagicMock()
    sheet.id = uuid.uuid4()
    sheet.plan_id = uuid.uuid4()
    sheet.project_id = uuid.uuid4()
    sheet.page_number = 1
    sheet.sheet_name = sheet_name
    sheet.sheet_number = None
    sheet.sheet_name_source = source
    sheet.scale_value = None
    sheet.scale_unit = None
    sheet.scale_label = None
    sheet.scale_source = None
    sheet.width_px = 1024
    sheet.height_px = 768
    sheet.thumbnail_path = None
    sheet.created_at = datetime.now(timezone.utc)
    sheet.vector_snap_segments = None
    return sheet


@pytest.mark.asyncio
async def test_rename_sheet_returns_200_with_manual_source():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    updated = _make_sheet(sheet_name="A1.01 First Floor", source="manual")

    with patch(
        "app.services.sheet_service.rename_sheet",
        new_callable=AsyncMock,
        return_value=updated,
    ) as mocked:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.patch(
                f"/api/v1/sheets/{updated.id}",
                json={"sheet_name": "  A1.01 First Floor  "},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheet_name"] == "A1.01 First Floor"
    assert body["sheet_name_source"] == "manual"

    # The service is the one responsible for trimming + the source flag, but
    # we assert the endpoint actually invoked it with the body string and the
    # acting user id (audit log requirement).
    args, kwargs = mocked.call_args
    assert kwargs["sheet_name"] == "  A1.01 First Floor  "
    assert kwargs["acting_user_id"] == ctx.user_id


@pytest.mark.asyncio
async def test_rename_sheet_rejects_empty_payload_with_422():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    sid = uuid.uuid4()

    # Pydantic min_length=1 catches the obvious empty string before we hit
    # the service. (The service has its own whitespace-trim guard for the
    # case where a 1-char body is whitespace.)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.patch(f"/api/v1/sheets/{sid}", json={"sheet_name": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_rename_sheet_propagates_service_422_for_whitespace():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    sid = uuid.uuid4()

    from app.middleware.error_handler import AppException

    with patch(
        "app.services.sheet_service.rename_sheet",
        new_callable=AsyncMock,
        side_effect=AppException(
            code="SHEET_NAME_EMPTY",
            message="Sheet name cannot be empty.",
            status_code=422,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.patch(f"/api/v1/sheets/{sid}", json={"sheet_name": "   "})

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SHEET_NAME_EMPTY"


@pytest.mark.asyncio
async def test_rename_sheet_rejects_viewer_with_403():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    sid = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.patch(f"/api/v1/sheets/{sid}", json={"sheet_name": "anything"})
    assert r.status_code == 403
