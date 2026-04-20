"""Tests for condition API routes (mocked service)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

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


def _mock_db():
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def _override_auth(ctx: AuthContext):
    from app.middleware.auth import get_current_user

    async def _fake():
        return ctx

    app.dependency_overrides[get_current_user] = _fake


def _override_db(db):
    from app.dependencies import get_db

    async def _fake():
        yield db

    app.dependency_overrides[get_db] = _fake


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_list_conditions_returns_array():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()

    from app.schemas.condition import ConditionPropertiesPayload, ConditionResponse

    fake = ConditionResponse(
        id=uuid.uuid4(),
        org_id=ctx.org_id,
        project_id=pid,
        name="Wall",
        measurement_type="linear",
        unit="LF",
        color="#ef4444",
        line_style="solid",
        line_width=2.0,
        fill_opacity=0.3,
        fill_pattern="solid",
        properties=ConditionPropertiesPayload(),
        trade=None,
        description=None,
        notes=None,
        sort_order=0,
        measurement_count=0,
        total_quantity=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.condition_service.list_conditions_for_project",
        new_callable=AsyncMock,
        return_value=[fake],
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/projects/{pid}/conditions")
            assert r.status_code == 200
            assert r.json()["conditions"][0]["name"] == "Wall"


@pytest.mark.anyio
async def test_create_condition_requires_manage_permission():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{pid}/conditions",
            json={
                "name": "X",
                "measurement_type": "linear",
                "unit": "LF",
                "color": "#ef4444",
            },
        )
        assert r.status_code == 403
