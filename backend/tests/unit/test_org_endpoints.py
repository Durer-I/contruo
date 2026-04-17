"""Tests for org API endpoints (mocked dependencies)."""

import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.auth import AuthContext


@pytest.fixture
def owner_ctx():
    return AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role="owner",
        email="owner@test.com",
    )


@pytest.fixture
def viewer_ctx():
    return AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role="viewer",
        email="viewer@test.com",
    )


def _mock_db():
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def _override_auth(ctx: AuthContext):
    from app.middleware.auth import get_current_user

    async def _fake_auth():
        return ctx

    app.dependency_overrides[get_current_user] = _fake_auth


def _override_db(db):
    from app.dependencies import get_db

    async def _fake_db():
        yield db

    app.dependency_overrides[get_db] = _fake_db


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_org(owner_ctx):
    _override_auth(owner_ctx)
    db = _mock_db()
    _override_db(db)

    mock_org = MagicMock()
    mock_org.id = owner_ctx.org_id
    mock_org.name = "Acme"
    mock_org.logo_url = None
    mock_org.default_units = "imperial"
    mock_org.created_at = datetime.now(timezone.utc)

    with patch("app.services.org_service.get_org", new_callable=AsyncMock, return_value=mock_org):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/org")
            assert r.status_code == 200
            assert r.json()["name"] == "Acme"


@pytest.mark.anyio
async def test_update_org_forbidden_for_viewer(viewer_ctx):
    _override_auth(viewer_ctx)
    db = _mock_db()
    _override_db(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.patch("/api/v1/org", json={"name": "Hacked"})
        assert r.status_code == 403


@pytest.mark.anyio
async def test_list_members(owner_ctx):
    _override_auth(owner_ctx)
    db = _mock_db()
    _override_db(db)

    members = [
        {
            "id": str(owner_ctx.user_id),
            "email": "owner@test.com",
            "full_name": "Owner",
            "role": "owner",
            "is_guest": False,
            "deactivated_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    with patch("app.services.org_service.list_members", new_callable=AsyncMock, return_value=members):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/v1/org/members")
            assert r.status_code == 200
            assert len(r.json()["members"]) == 1


@pytest.mark.anyio
async def test_invite_member_forbidden_for_estimator():
    ctx = AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role="estimator",
        email="est@test.com",
    )
    _override_auth(ctx)
    db = _mock_db()
    _override_db(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/org/members/invite", json={"email": "new@test.com", "role": "viewer"})
        assert r.status_code == 403


@pytest.mark.anyio
async def test_deactivate_member_forbidden_for_viewer(viewer_ctx):
    _override_auth(viewer_ctx)
    db = _mock_db()
    _override_db(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete(f"/api/v1/org/members/{uuid.uuid4()}")
        assert r.status_code == 403
