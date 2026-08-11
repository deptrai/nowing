"""Integration tests for chainlens-research service-to-service callbacks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.app import app, limiter
from app.routes.chainlens_internal import chainlens_auth_dependency
from app.services.chainlens.auth import ChainLensAuthContext, get_chainlens_auth

pytestmark = [pytest.mark.integration]

limiter.enabled = False


@pytest_asyncio.fixture
async def chainlens_internal_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async def _valid_auth() -> ChainLensAuthContext:
        return ChainLensAuthContext(
            workspace_id=7,
            correlation_id="corr-test",
            token="test-token",
        )

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[chainlens_auth_dependency] = _valid_auth
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def chainlens_auth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client that exercises the real service-token auth dependency."""
    import app.services.chainlens.auth as auth_mod

    fake_config = type(
        "Config",
        (),
        {
            "CHAINLENS_SERVICE_TOKEN": "valid-token",
            "CHAINLENS_API_KEY": "",
        },
    )()
    monkeypatch.setattr(auth_mod, "config", fake_config)
    get_chainlens_auth.cache_clear()

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.pop(chainlens_auth_dependency, None)
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as client:
            yield client
    finally:
        get_chainlens_auth.cache_clear()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.asyncio
async def test_scraper_run_callback_returns_accepted(chainlens_internal_client):
    response = await chainlens_internal_client.post("/v1/scraper/batdongsan/run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["scraper_id"] == "batdongsan"
    assert body["workspace_id"] == 7


@pytest.mark.asyncio
async def test_private_data_search_callback_returns_accepted(chainlens_internal_client):
    response = await chainlens_internal_client.post("/v1/private-data/search")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["workspace_id"] == 7


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_invalid_service_token(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"Authorization": "Bearer wrong-token", "X-Workspace-Id": "7"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_accepts_valid_service_token(chainlens_auth_client):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"Authorization": "Bearer valid-token", "X-Workspace-Id": "7"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["workspace_id"] == 7


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_missing_workspace_id(chainlens_auth_client):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_rejects_negative_workspace_id(
    chainlens_auth_client,
):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"Authorization": "Bearer valid-token", "X-Workspace-Id": "-1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scraper_run_callback_accepts_lowercase_bearer(chainlens_auth_client):
    response = await chainlens_auth_client.post(
        "/v1/scraper/batdongsan/run",
        headers={"authorization": "bearer valid-token", "x-workspace-id": "7"},
    )
    assert response.status_code == 200
