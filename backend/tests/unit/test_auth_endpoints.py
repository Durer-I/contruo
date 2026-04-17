"""Tests for auth endpoints.

These tests mock Supabase calls since we don't want to hit the real
Supabase API during testing. They verify the endpoint routing, request
validation, and response format.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_missing_fields():
    """Registration should fail with 422 when required fields are missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email():
    """Registration should fail with 422 for invalid email format."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Test User",
                "email": "not-an-email",
                "password": "securepass123",
                "org_name": "Test Org",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password():
    """Registration should fail with 422 for passwords < 8 chars."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Test User",
                "email": "test@example.com",
                "password": "short",
                "org_name": "Test Org",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_fields():
    """Login should fail with 422 when required fields are missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_me_no_token():
    """GET /auth/me should return 401 without a token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_me_invalid_token():
    """GET /auth/me should return 401 with an invalid token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_always_200():
    """Reset password should return 200 regardless of whether email exists."""
    transport = ASGITransport(app=app)
    with patch("app.services.auth_service.request_password_reset", new_callable=AsyncMock):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/reset-password",
                json={"email": "anyone@example.com"},
            )
    assert response.status_code == 200
    assert "reset link" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_logout_without_token():
    """Logout should succeed (200) even without a token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
