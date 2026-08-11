"""Unit tests for ``app.services.chainlens.gap_fill``."""

from __future__ import annotations

import json
import types
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import config
from app.services.chainlens.gap_fill import (
    GapFillRequest,
    GapFillResponse,
    GapFillService,
)

pytestmark = pytest.mark.unit


class _FakeAuth:
    def __init__(self, config_obj: Any | None = None) -> None:
        self.config = config_obj or config

    @property
    def configured(self) -> bool:
        return bool(
            getattr(self.config, "CHAINLENS_SERVICE_TOKEN", "")
            or getattr(self.config, "CHAINLENS_API_KEY", "")
        )

    def get_outbound_headers(
        self,
        workspace_id: int,
        correlation_id: str | None = None,
        content_type: str = "application/json",
    ) -> dict[str, str]:
        return {"Authorization": "Bearer service-secret"}


def _fake_config() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        CHAINLENS_API_URL="https://chainlens.test",
        CHAINLENS_SERVICE_TOKEN="service-secret",
        CHAINLENS_API_KEY="",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=5.0,
    )


def _httpx_client_class(calls: list[dict[str, Any]], responses: list[Any]):
    """Return a fake httpx.AsyncClient class that replays a list of responses."""

    class _FakeResponse:
        def __init__(
            self,
            status_code: int,
            json_data: dict[str, Any] | None = None,
        ):
            self.status_code = status_code
            self._json = json_data or {}
            self.content = json.dumps(self._json).encode()

        def json(self) -> dict[str, Any]:
            return self._json

    class _FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self._client_kwargs = kwargs

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            calls.append({"url": url, "kwargs": kwargs})
            if not responses:
                return _FakeResponse(500)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            status_code, json_data = item
            return _FakeResponse(status_code, json_data)

    return _FakeClient


def _patch_auth(monkeypatch: Any, module: Any) -> None:
    monkeypatch.setattr(module, "ChainLensServiceAuth", _FakeAuth)


@pytest.mark.asyncio
async def test_gap_fill_request_calls_post_with_service_auth(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config())
    _patch_auth(monkeypatch, gap_fill_mod)

    calls: list[dict[str, Any]] = []
    responses = [
        (
            200,
            {
                "runId": "run-123",
                "status": "complete",
                "costDollars": 0.025,
                "costBreakdown": {
                    "searchCostDollars": 0.01,
                    "gapFillCostDollars": 0.01,
                    "scraperCostDollars": 0.005,
                    "scraperId": "batdongsan",
                },
            },
        )
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = GapFillService()
    request = GapFillRequest(
        query="latest houses in Hanoi",
        workspace_id=42,
        domains=["batdongsan"],
    )
    response = await service.request(request)

    assert response.status == "complete"
    assert response.run_id == "run-123"
    assert response.cost_dollars == 0.025
    assert response.cost_breakdown is not None
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://chainlens.test/v1/gap-fill"
    assert call["kwargs"]["headers"]["Authorization"] == "Bearer service-secret"
    body = call["kwargs"]["json"]
    assert body["query"] == "latest houses in Hanoi"
    assert body["workspaceId"] == 42
    assert body["domains"] == ["batdongsan"]


@pytest.mark.asyncio
async def test_gap_fill_request_returns_auth_unavailable_when_not_configured(
    monkeypatch,
):
    import app.services.chainlens.gap_fill as gap_fill_mod

    fake = _fake_config()
    fake.CHAINLENS_SERVICE_TOKEN = ""
    fake.CHAINLENS_API_KEY = ""
    monkeypatch.setattr(gap_fill_mod, "config", fake)
    _patch_auth(monkeypatch, gap_fill_mod)

    service = GapFillService()
    response = await service.request(GapFillRequest(query="test", workspace_id=1))

    assert response.status == "service_auth_unavailable"
    assert response.message is not None


@pytest.mark.asyncio
async def test_gap_fill_request_async_appends_query_param(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config())
    _patch_auth(monkeypatch, gap_fill_mod)

    calls: list[dict[str, Any]] = []
    responses = [(202, {"runId": "async-run-1", "status": "accepted"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = GapFillService()
    response = await service.request(
        GapFillRequest(
            query="test",
            workspace_id=1,
            mode="async",
        )
    )

    assert response.status == "accepted"
    assert response.run_id == "async-run-1"
    assert calls[0]["url"] == "https://chainlens.test/v1/gap-fill?mode=async"


@pytest.mark.asyncio
async def test_gap_fill_request_sync_or_async_falls_back_on_timeout(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config())
    _patch_auth(monkeypatch, gap_fill_mod)

    calls: list[dict[str, Any]] = []
    responses = [(202, {"runId": "async-run-2", "status": "accepted"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    # Patch out the DB-backed pending-run creation so the test stays unit.
    monkeypatch.setattr(
        gap_fill_mod,
        "create_pending_run",
        AsyncMock(return_value="12345678-1234-1234-1234-123456789abc"),
    )
    monkeypatch.setattr(
        gap_fill_mod,
        "finalize_run",
        AsyncMock(return_value=True),
    )

    service = GapFillService()
    # Make the sync request take longer than the tiny sync timeout.
    original_request = service.request

    async def slow_request(
        payload: GapFillRequest, **kwargs: Any
    ) -> GapFillResponse:
        import asyncio

        await asyncio.sleep(0.05)
        return await original_request(payload, **kwargs)

    monkeypatch.setattr(service, "request", slow_request)

    response = await service.request_sync_or_async(
        GapFillRequest(query="slow test", workspace_id=1),
        sync_timeout_seconds=0.001,
    )

    assert response.status == "running"
    assert response.run_id == "run_12345678-1234-1234-1234-123456789abc"
