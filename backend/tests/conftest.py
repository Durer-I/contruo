"""Shared pytest helpers — single source of truth for the route-test boilerplate.

Before this lived as identical ``_ctx`` / ``_mock_db`` / ``_override_auth`` /
``_override_db`` / ``_cleanup`` blocks copy-pasted into every ``test_*_endpoints.py``.
The helpers below are exposed as both fixtures and importable functions so old
tests can migrate without churn.
"""

from __future__ import annotations

import uuid
from typing import Callable
from unittest.mock import AsyncMock

import pytest

from app.dependencies import get_db
from app.main import app
from app.middleware.auth import AuthContext, get_current_user


def make_auth_context(role: str = "estimator") -> AuthContext:
    return AuthContext(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=role,
        email=f"{role}@test.com",
    )


def make_async_db_mock() -> AsyncMock:
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def override_auth(ctx: AuthContext) -> None:
    async def _fake() -> AuthContext:
        return ctx

    app.dependency_overrides[get_current_user] = _fake


def override_db(db: AsyncMock) -> None:
    async def _fake():
        yield db

    app.dependency_overrides[get_db] = _fake


@pytest.fixture
def auth_context() -> Callable[[str], AuthContext]:
    """Factory: ``ctx = auth_context("viewer")``."""
    return make_auth_context


@pytest.fixture
def async_db() -> AsyncMock:
    return make_async_db_mock()


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()
