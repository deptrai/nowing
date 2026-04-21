"""
API-layer test fixtures.
Provides an httpx.AsyncClient wired to the FastAPI app.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for FastAPI API tests (no real server needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(api_client: AsyncClient) -> dict[str, str]:
    """Authorization headers for a test user."""
    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")
    password = os.environ.get("TEST_USER_PASSWORD", "test-password")

    response = await api_client.post(
        "/api/auth/login",
        json={"username": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
