"""Tests for measurement API routes (mocked service)."""

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
async def test_list_measurements_returns_array():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    sid = uuid.uuid4()
    cid = uuid.uuid4()

    from app.schemas.measurement import MeasurementListResponse, MeasurementResponse

    now = datetime.now(timezone.utc)
    fake = MeasurementResponse(
        id=uuid.uuid4(),
        org_id=ctx.org_id,
        project_id=pid,
        sheet_id=sid,
        condition_id=cid,
        measurement_type="linear",
        geometry={"type": "linear", "vertices": [{"x": 0.0, "y": 0.0}, {"x": 10.0, "y": 0.0}]},
        measured_value=10.0,
        override_value=None,
        label=None,
        created_by=ctx.user_id,
        created_at=now,
        updated_at=now,
        deductions=[],
        gross_measured_value=None,
    )

    with patch(
        "app.services.measurement_service.list_project_measurements",
        new_callable=AsyncMock,
        return_value=MeasurementListResponse(measurements=[fake]),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/projects/{pid}/measurements?sheet_id={sid}")
            assert r.status_code == 200
            data = r.json()["measurements"][0]
            assert data["measurement_type"] == "linear"
            assert data["measured_value"] == 10.0


@pytest.mark.anyio
async def test_create_measurement_requires_edit_permission():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    sid = uuid.uuid4()
    cid = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{pid}/measurements",
            json={
                "sheet_id": str(sid),
                "condition_id": str(cid),
                "measurement_type": "linear",
                "geometry": {
                    "type": "linear",
                    "vertices": [{"x": 0, "y": 0}, {"x": 1, "y": 0}],
                },
            },
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_delete_measurement_requires_edit_permission():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    mid = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.delete(f"/api/v1/measurements/{mid}")
        assert r.status_code == 403
