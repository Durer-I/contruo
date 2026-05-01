"""Sprint AI-02b: POST /projects/{pid}/plans/{plan_id}/auto-name-sheets.

Endpoint-level tests only -- the heavy lifting (heuristic parser,
orchestrator, Celery task) is covered in dedicated test modules. Here we
verify routing, permission gating, status guards, and the feature flag.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app
from app.middleware.auth import AuthContext


def _ctx(role: str = "estimator") -> AuthContext:
    return AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=role,
        email=f"{role}@test.com",
    )


def _override_auth(ctx: AuthContext) -> None:
    from app.middleware.auth import get_current_user

    async def _fake() -> AuthContext:
        return ctx

    app.dependency_overrides[get_current_user] = _fake


def _override_db_with_plan(plan: object | None) -> None:
    """Override the get_db dep with an AsyncSession whose .execute returns plan."""
    from app.dependencies import get_db

    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=plan)
    db.execute = AsyncMock(return_value=result)

    async def _fake():
        yield db

    app.dependency_overrides[get_db] = _fake


def _make_plan(*, status: str = "ready") -> MagicMock:
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.project_id = uuid.uuid4()
    plan.org_id = uuid.uuid4()
    plan.status = status
    return plan


@pytest.fixture(autouse=True)
def _disable_subscription_guard():
    with patch(
        "app.services.billing_service.get_subscription",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """SlowAPI limiter is a module-level singleton with shared in-memory
    storage; cumulative request counts across the entire test session can
    push our 202-path test over the default 300/min limit (and surface as a
    bizarre `'ConnectionError' has no attribute 'detail'` error from
    slowapi's exception handler). Disabling the limiter for the test avoids
    that flakiness without touching production behavior.
    """
    from app.middleware.rate_limit import limiter

    with patch.object(limiter, "enabled", False):
        yield


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_returns_202_with_task_id_on_success():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    plan = _make_plan(status="ready")
    _override_db_with_plan(plan)

    fake_async_result = MagicMock()
    fake_async_result.id = "celery-task-id-123"
    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=fake_async_result)

    # Patch the task object itself (not just .delay) -- patching .delay
    # alone doesn't survive when other tests have already imported the
    # Celery-bound task descriptor first.
    with patch(
        "app.tasks.ai_pipeline.reextract_plan_titles_task",
        fake_task,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{plan.project_id}/plans/{plan.id}/auto-name-sheets",
                json={},
            )

    assert r.status_code == 202, r.text
    body = r.json()
    assert body["plan_id"] == str(plan.id)
    assert body["task_id"] == "celery-task-id-123"
    assert "queued_at" in body
    fake_task.delay.assert_called_once_with(str(plan.id), overwrite_manual=False)


@pytest.mark.asyncio
async def test_returns_404_when_plan_missing():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db_with_plan(None)

    plan_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{project_id}/plans/{plan_id}/auto-name-sheets",
            json={},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_returns_409_when_plan_processing():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    plan = _make_plan(status="processing")
    _override_db_with_plan(plan)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{plan.project_id}/plans/{plan.id}/auto-name-sheets",
            json={},
        )
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "PLAN_NOT_READY"


@pytest.mark.asyncio
async def test_returns_503_when_feature_flag_disabled(monkeypatch):
    monkeypatch.setenv("AI_AUTO_NAME_ENABLED", "false")
    get_settings.cache_clear()

    ctx = _ctx("estimator")
    _override_auth(ctx)
    plan = _make_plan(status="ready")
    _override_db_with_plan(plan)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{plan.project_id}/plans/{plan.id}/auto-name-sheets",
            json={},
        )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "AUTO_NAME_DISABLED"


@pytest.mark.asyncio
async def test_returns_403_when_viewer():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db_with_plan(_make_plan(status="ready"))

    pid = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{pid}/plans/{plan_id}/auto-name-sheets",
            json={},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_forwards_overwrite_manual_to_task():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    plan = _make_plan(status="ready")
    _override_db_with_plan(plan)

    fake_async_result = MagicMock()
    fake_async_result.id = "task-xyz"
    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=fake_async_result)

    with patch(
        "app.tasks.ai_pipeline.reextract_plan_titles_task",
        fake_task,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{plan.project_id}/plans/{plan.id}/auto-name-sheets",
                json={"overwrite_manual": True},
            )

    assert r.status_code == 202
    fake_task.delay.assert_called_once_with(str(plan.id), overwrite_manual=True)
