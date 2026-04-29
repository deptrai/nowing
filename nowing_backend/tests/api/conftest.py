"""
API-layer test fixtures.
Provides an httpx.AsyncClient wired to the FastAPI app.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.app import app


@pytest.fixture(autouse=True)
def mock_celery_tasks():
    """
    Mock tất cả Celery task .delay() / .apply_async() calls trong API tests.
    Tránh Redis connection timeout (~20s per call) khi Celery không chạy local.
    """
    mock_result = MagicMock()
    mock_result.id = "mock-task-id"

    patches = [
        patch("app.tasks.celery_tasks.document_tasks.delete_search_space_task.delay", return_value=mock_result),
    ]

    started = []
    for p in patches:
        try:
            started.append(p.start())
        except AttributeError:
            pass  # module chưa load hoặc path không tồn tại — bỏ qua

    yield

    for p in patches:
        try:
            p.stop()
        except RuntimeError:
            pass


@pytest_asyncio.fixture(scope="session")
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for FastAPI API tests (no real server needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def auth_headers(api_client: AsyncClient) -> dict[str, str]:
    """
    Authorization headers cho test user (session-scoped — 1 lần login per CI run).
    KHÔNG dùng cho destructive tests (revoke, logout-all) — dùng one_time_auth_headers.
    """
    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")
    password = os.environ.get("TEST_USER_PASSWORD", "test-password")

    response = await api_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    body = response.json()
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    headers["X-Refresh-Token"] = body.get("refresh_token", "")
    return headers


@pytest_asyncio.fixture
async def one_time_auth_headers(api_client: AsyncClient) -> dict[str, str]:
    """
    Fresh auth headers cho destructive token tests (revoke, logout-all).
    Function-scoped — thực hiện login mới cho mỗi test sử dụng fixture này.
    """
    email = os.environ.get("TEST_USER_EMAIL", "test@nowing.test")
    password = os.environ.get("TEST_USER_PASSWORD", "test-password")

    response = await api_client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, f"Login failed (one_time): {response.text}"
    body = response.json()
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    headers["X-Refresh-Token"] = body.get("refresh_token", "")
    return headers
