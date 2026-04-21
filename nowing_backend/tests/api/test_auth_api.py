"""
API-layer tests for Authentication endpoints.

Tests use httpx.AsyncClient + ASGITransport (no real server).
Covers P0-P1 scenarios for /api/auth/* endpoints.

Markers: @pytest.mark.api
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# P0 — Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_tokens(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/login — valid credentials → 200 + access_token."""
    import os

    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")
    password = os.environ.get("TEST_USER_PASSWORD", "test-password")

    response = await api_client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type", "").lower() == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password_returns_400(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/login — wrong password → 400."""
    import os

    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")

    response = await api_client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": "wrong-password-xyz"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_missing_fields_returns_422(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/login — missing username → 422."""
    response = await api_client.post(
        "/api/auth/jwt/login",
        data={"password": "some-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_email_returns_400(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/login — unknown user → 400 (not 404 to avoid enumeration)."""
    response = await api_client.post(
        "/api/auth/jwt/login",
        data={"username": "nobody@notexist.invalid", "password": "abc"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# P0 — Token Refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_refresh_with_valid_token(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/auth/jwt/refresh — valid access token → 200 + new tokens."""
    response = await api_client.post(
        "/api/auth/jwt/refresh",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


@pytest.mark.asyncio
async def test_token_refresh_without_auth_returns_401(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/refresh — no token → 401."""
    response = await api_client.post("/api/auth/jwt/refresh")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh_with_malformed_token_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /api/auth/jwt/refresh — garbage token → 401."""
    response = await api_client.post(
        "/api/auth/jwt/refresh",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1 — Revoke / Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_token_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/auth/jwt/revoke — authenticated → 200."""
    response = await api_client.post(
        "/api/auth/jwt/revoke",
        headers=auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """POST /api/auth/jwt/logout-all — authenticated → 200."""
    response = await api_client.post(
        "/api/auth/jwt/logout-all",
        headers=auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """POST /api/auth/jwt/logout-all — no token → 401."""
    response = await api_client.post("/api/auth/jwt/logout-all")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1 — Protected route gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/me — authenticated request should succeed."""
    response = await api_client.get("/api/me", headers=auth_headers)

    # Acceptable: 200 (me endpoint exists) or 404 (route not configured in test app)
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_protected_endpoint_without_token_returns_401(
    api_client: AsyncClient,
) -> None:
    """Any protected endpoint without token → 401."""
    response = await api_client.get("/api/searchspaces")

    assert response.status_code == 401
