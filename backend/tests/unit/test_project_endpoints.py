"""Tests for project + plan API endpoints (mocked services)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import AuthContext


def _ctx(role: str) -> AuthContext:
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


# ── Project listing ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_projects_returns_array():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())

    fake_projects = [
        {
            "id": uuid.uuid4(),
            "org_id": ctx.org_id,
            "name": "Proj A",
            "description": None,
            "status": "active",
            "created_by": ctx.user_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "sheet_count": 3,
            "member_count": 2,
        }
    ]

    with patch(
        "app.services.project_service.list_projects",
        new_callable=AsyncMock,
        return_value=fake_projects,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/v1/projects")
            assert r.status_code == 200
            assert r.json()["projects"][0]["name"] == "Proj A"
            assert r.json()["projects"][0]["sheet_count"] == 3


# ── Project creation ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_project_succeeds_for_admin():
    ctx = _ctx("admin")
    _override_auth(ctx)
    _override_db(_mock_db())

    project = MagicMock()
    project.id = uuid.uuid4()
    project.org_id = ctx.org_id
    project.name = "New Project"
    project.description = "desc"
    project.status = "active"
    project.created_by = ctx.user_id
    project.created_at = datetime.now(timezone.utc)
    project.updated_at = datetime.now(timezone.utc)

    with patch(
        "app.services.project_service.create_project",
        new_callable=AsyncMock,
        return_value=project,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/projects",
                json={"name": "New Project", "description": "desc"},
            )
            assert r.status_code == 201
            assert r.json()["name"] == "New Project"


@pytest.mark.anyio
async def test_create_project_forbidden_for_estimator():
    """Estimators do not have CREATE_PROJECTS per the permission matrix."""
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/projects", json={"name": "Sneaky"})
        assert r.status_code == 403


@pytest.mark.anyio
async def test_create_project_requires_name():
    ctx = _ctx("admin")
    _override_auth(ctx)
    _override_db(_mock_db())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/projects", json={"description": "no name"})
        assert r.status_code == 422


# ── Plan upload ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_upload_plan_forbidden_for_viewer():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{uuid.uuid4()}/plans",
            files={"file": ("test.pdf", b"%PDF-1.7\n...", "application/pdf")},
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_upload_plan_succeeds_for_estimator():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())

    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.project_id = uuid.uuid4()
    plan.filename = "test.pdf"
    plan.file_size = 128
    plan.page_count = None
    plan.status = "processing"
    plan.processed_pages = 0
    plan.error_message = None
    plan.uploaded_by = ctx.user_id
    plan.created_at = datetime.now(timezone.utc)
    plan.updated_at = datetime.now(timezone.utc)

    with patch(
        "app.services.plan_service.create_plan",
        new_callable=AsyncMock,
        return_value=plan,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{uuid.uuid4()}/plans",
                files={"file": ("test.pdf", b"%PDF-1.7\n...", "application/pdf")},
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["status"] == "processing"
            assert body["filename"] == "test.pdf"


# ── Plan status polling ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_plan_status():
    ctx = _ctx("viewer")  # read-only is allowed
    _override_auth(ctx)
    _override_db(_mock_db())

    plan = MagicMock()
    plan_id = uuid.uuid4()
    plan.id = plan_id
    plan.project_id = uuid.uuid4()
    plan.filename = "done.pdf"
    plan.file_size = 1024
    plan.page_count = 10
    plan.status = "ready"
    plan.processed_pages = 10
    plan.error_message = None
    plan.uploaded_by = ctx.user_id
    plan.created_at = datetime.now(timezone.utc)
    plan.updated_at = datetime.now(timezone.utc)

    with patch(
        "app.services.plan_service.get_plan",
        new_callable=AsyncMock,
        return_value=plan,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/plans/{plan_id}")
            assert r.status_code == 200
            assert r.json()["status"] == "ready"
            assert r.json()["page_count"] == 10


@pytest.mark.anyio
async def test_get_plan_document_url_returns_signed_url():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())

    plan_id = uuid.uuid4()
    with patch(
        "app.services.plan_service.get_plan_document_signed_url",
        new_callable=AsyncMock,
        return_value=("https://signed.example/plan.pdf", 3600),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/plans/{plan_id}/document-url")
            assert r.status_code == 200
            body = r.json()
            assert body["url"] == "https://signed.example/plan.pdf"
            assert body["expires_in"] == 3600


# ── Sheets listing ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_sheets_returns_thumbnails():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())

    sheet = MagicMock()
    sheet.id = uuid.uuid4()
    sheet.plan_id = uuid.uuid4()
    sheet.project_id = uuid.uuid4()
    sheet.page_number = 1
    sheet.sheet_name = "A1.01 - First Floor Plan"
    sheet.scale_value = None
    sheet.scale_unit = None
    sheet.scale_label = None
    sheet.scale_source = None
    sheet.width_px = 2448
    sheet.height_px = 1584
    sheet.thumbnail_path = "org/plans/plan/thumbs/page-1.png"
    sheet.created_at = datetime.now(timezone.utc)

    with (
        patch(
            "app.services.plan_service.list_project_sheets",
            new_callable=AsyncMock,
            return_value=[sheet],
        ),
        patch(
            "app.services.plan_service.sheet_thumbnail_url",
            return_value="https://signed.example/thumb.png",
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/projects/{uuid.uuid4()}/sheets")
            assert r.status_code == 200
            body = r.json()
            assert len(body["sheets"]) == 1
            assert body["sheets"][0]["thumbnail_url"] == "https://signed.example/thumb.png"
            assert body["sheets"][0]["sheet_name"] == "A1.01 - First Floor Plan"
