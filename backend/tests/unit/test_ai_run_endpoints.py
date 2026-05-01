"""AI run API endpoints (Sprint AI-01).

* ``POST`` requires ``EDIT_MEASUREMENTS`` (Estimator+).
* Concurrent click on the same plan returns 409 ``AI_RUN_LOCKED``.
* Non-ready plans return 409 ``PLAN_NOT_READY``.
* Plan/project mismatch returns 400.
* Internal cost endpoint requires ``owner`` role.
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
    """Skip the per-request subscription DB lookup so AI tests stay focused."""
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


def _make_plan(plan_id: uuid.UUID, project_id: uuid.UUID, status: str = "ready") -> MagicMock:
    plan = MagicMock()
    plan.id = plan_id
    plan.project_id = project_id
    plan.status = status
    return plan


def _make_run(
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    triggered_by: uuid.UUID,
) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.org_id = org_id
    run.project_id = project_id
    run.plan_id = plan_id
    run.triggered_by = triggered_by
    run.status = "queued"
    run.scope = "full_plan"
    run.model_versions = {"vision": "anthropic:claude-sonnet-4-5"}
    run.started_at = None
    run.finished_at = None
    run.cost_cents = 0
    run.tokens_used = 0
    run.items_total = 0
    run.items_accepted_auto = 0
    run.items_pending = 0
    run.items_low_confidence = 0
    run.summary_jsonb = {"stages": {}, "lock_state": "unlocked"}
    run.error_message = None
    run.created_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    return run


# ── POST /projects/{id}/ai/runs ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_ai_run_requires_edit_permission():
    ctx = _ctx("viewer")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    plan_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/v1/projects/{pid}/ai/runs",
            json={"plan_id": str(plan_id)},
        )
        assert r.status_code == 403


@pytest.mark.anyio
async def test_create_ai_run_succeeds_for_estimator():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    plan_id = uuid.uuid4()

    plan = _make_plan(plan_id, pid)
    run = _make_run(org_id=ctx.org_id, project_id=pid, plan_id=plan_id, triggered_by=ctx.user_id)

    chain_mock = MagicMock()

    with (
        patch(
            "app.services.project_service.assert_project_visible",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
        patch(
            "app.services.ai_run_service.check_circuit_breaker",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.ai_run_service.assert_no_active_run_for_plan",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.ai_run_service.create_run",
            new_callable=AsyncMock,
            return_value=run,
        ),
        patch(
            "app.tasks.ai_pipeline.build_pipeline_chain",
            return_value=chain_mock,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{pid}/ai/runs",
                json={"plan_id": str(plan_id)},
            )

    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["plan_id"] == str(plan_id)
    assert chain_mock.apply_async.called


@pytest.mark.anyio
async def test_create_ai_run_returns_409_when_concurrent_run_active():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    plan_id = uuid.uuid4()
    plan = _make_plan(plan_id, pid)

    from app.middleware.error_handler import ConflictException

    with (
        patch(
            "app.services.project_service.assert_project_visible",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
        patch(
            "app.services.ai_run_service.check_circuit_breaker",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.ai_run_service.assert_no_active_run_for_plan",
            new_callable=AsyncMock,
            side_effect=ConflictException(
                "An AI run is already in progress for this plan.",
                code="AI_RUN_LOCKED",
            ),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{pid}/ai/runs",
                json={"plan_id": str(plan_id)},
            )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "AI_RUN_LOCKED"


@pytest.mark.anyio
async def test_create_ai_run_returns_409_when_plan_not_ready():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    plan_id = uuid.uuid4()
    plan = _make_plan(plan_id, pid, status="processing")

    with (
        patch(
            "app.services.project_service.assert_project_visible",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{pid}/ai/runs",
                json={"plan_id": str(plan_id)},
            )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PLAN_NOT_READY"


@pytest.mark.anyio
async def test_create_ai_run_returns_400_on_plan_project_mismatch():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    other_project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    plan = _make_plan(plan_id, other_project_id, status="ready")

    with (
        patch(
            "app.services.project_service.assert_project_visible",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.plan_service.get_plan",
            new_callable=AsyncMock,
            return_value=plan,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/v1/projects/{pid}/ai/runs",
                json={"plan_id": str(plan_id)},
            )

    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PLAN_PROJECT_MISMATCH"


# ── GET endpoints ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_list_ai_runs_returns_array():
    ctx = _ctx("estimator")
    _override_auth(ctx)
    _override_db(_mock_db())
    pid = uuid.uuid4()
    plan_id = uuid.uuid4()
    runs = [_make_run(org_id=ctx.org_id, project_id=pid, plan_id=plan_id, triggered_by=ctx.user_id)]

    with (
        patch(
            "app.services.project_service.assert_project_visible",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.ai_run_service.list_runs",
            new_callable=AsyncMock,
            return_value=runs,
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(f"/api/v1/projects/{pid}/ai/runs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["plan_id"] == str(plan_id)


# ── Internal cost endpoint ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_internal_cost_endpoint_requires_owner():
    ctx = _ctx("admin")
    _override_auth(ctx)
    _override_db(_mock_db())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/internal/ai/cost-by-org")
    assert r.status_code == 403


@pytest.mark.anyio
async def test_internal_cost_endpoint_returns_only_own_org_for_owner():
    ctx = _ctx("owner")
    _override_auth(ctx)
    _override_db(_mock_db())

    other_org = uuid.uuid4()
    fake_rows = [
        {"org_id": str(ctx.org_id), "cost_cents": 250, "tokens_used": 1200, "run_count": 4},
        {"org_id": str(other_org), "cost_cents": 99, "tokens_used": 50, "run_count": 1},
    ]

    with patch(
        "app.services.ai_run_service.cost_by_org_last_24h",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/v1/internal/ai/cost-by-org")

    assert r.status_code == 200
    body = r.json()
    assert body["window_hours"] == 24
    assert len(body["rows"]) == 1
    assert body["rows"][0]["org_id"] == str(ctx.org_id)
    assert body["rows"][0]["cost_cents"] == 250
