"""
API-layer tests for Authentication endpoints.

Tests use httpx.AsyncClient + ASGITransport (no real server).
Covers P0-P1 scenarios for /api/auth/* endpoints.

Markers: @pytest.mark.api
"""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# P0 — Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_tokens(api_client: AsyncClient) -> None:
    """POST /auth/jwt/login — valid credentials → 200 + access_token."""
    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")
    password = os.environ.get("TEST_USER_PASSWORD", "test-password")

    response = await api_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type", "").lower() == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password_returns_400(api_client: AsyncClient) -> None:
    """POST /auth/jwt/login — wrong password → 400."""
    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")

    response = await api_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "wrong-password-xyz"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_missing_fields_returns_422(api_client: AsyncClient) -> None:
    """POST /auth/jwt/login — missing username → 422."""
    response = await api_client.post(
        "/auth/jwt/login",
        data={"password": "some-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_email_returns_400(api_client: AsyncClient) -> None:
    """POST /auth/jwt/login — unknown user → 400 (not 404 to avoid enumeration)."""
    response = await api_client.post(
        "/auth/jwt/login",
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
    """POST /auth/jwt/refresh — valid access token → 200 + new tokens."""
    refresh_token = auth_headers.get("X-Refresh-Token", "")
    response = await api_client.post(
        "/auth/jwt/refresh",
        json={"refresh_token": refresh_token},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body


@pytest.mark.asyncio
async def test_token_refresh_without_auth_returns_401(api_client: AsyncClient) -> None:
    """POST /auth/jwt/refresh — no token → 401."""
    response = await api_client.post("/auth/jwt/refresh")

    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_token_refresh_with_malformed_token_returns_401(
    api_client: AsyncClient,
) -> None:
    """POST /auth/jwt/refresh — garbage token → 401."""
    response = await api_client.post(
        "/auth/jwt/refresh",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )

    assert response.status_code in (401, 422)


# ---------------------------------------------------------------------------
# P0 — Token Revocation (destructive — uses one_time_auth_headers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_token_returns_200(
    api_client: AsyncClient, one_time_auth_headers: dict[str, str]
) -> None:
    """POST /auth/jwt/revoke — authenticated → 200. Uses fresh token (destructive)."""
    refresh_token = one_time_auth_headers.get("X-Refresh-Token", "")
    response = await api_client.post(
        "/auth/jwt/revoke",
        json={"refresh_token": refresh_token},
        headers=one_time_auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_returns_200(
    api_client: AsyncClient, one_time_auth_headers: dict[str, str]
) -> None:
    """POST /auth/jwt/logout-all — authenticated → 200. Uses fresh token (destructive)."""
    response = await api_client.post(
        "/auth/jwt/logout-all",
        headers=one_time_auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    """POST /auth/jwt/logout-all — no token → 401."""
    response = await api_client.post("/auth/jwt/logout-all")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P1 — Protected route gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token_returns_200(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /api/v1/searchspaces — authenticated request should succeed."""
    response = await api_client.get("/api/v1/searchspaces", headers=auth_headers)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_without_token_returns_401(
    api_client: AsyncClient,
) -> None:
    """Any protected endpoint without token → 401."""
    response = await api_client.get("/api/v1/searchspaces")

    assert response.status_code == 401
