"""Unit tests for ``app.services.chainlens.gap_fill``."""

from __future__ import annotations

import json
import types
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from pydantic import ValidationError

from app.config import config
from app.services.chainlens.gap_fill import (
    GapFillRequest,
    GapFillResponse,
    GapFillService,
)
from app.services.token_tracking_service import UsageType

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

    def rotate(self, **kwargs: Any) -> bool:
        return False


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


# ===================================================================
# Targeted mutation-killing tests for Story 20.2
# ===================================================================


class _FakeSessionCM:
    """Callable async context manager that yields a supplied session."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionCM:
        return self

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _patch_gap_fill_db(monkeypatch: Any, module: Any) -> tuple[Any, Any]:
    """Patch DB and billing helpers so unit tests never hit Postgres."""
    session = AsyncMock()
    session.add = Mock()

    monkeypatch.setattr(module, "async_session_maker", _FakeSessionCM(session))
    monkeypatch.setattr(module, "create_pending_run", AsyncMock(return_value="123"))
    monkeypatch.setattr(module, "finalize_run", AsyncMock(return_value=True))
    monkeypatch.setattr(module, "_resolve_workspace_owner", AsyncMock(return_value=42))
    monkeypatch.setattr(module, "check_balance", AsyncMock())
    monkeypatch.setattr(module, "apply_debit", AsyncMock())
    monkeypatch.setattr(module, "record_token_usage", AsyncMock())
    monkeypatch.setattr(module, "emit_progress", Mock())
    monkeypatch.setattr(
        module, "run_event_bus", types.SimpleNamespace(publish=Mock())
    )

    # ``progress_scope`` is a context manager; the worker just needs a no-op scope.
    from contextlib import nullcontext

    monkeypatch.setattr(module, "progress_scope", lambda **kwargs: nullcontext())
    return session, module


def _fake_config_with_costs() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        CHAINLENS_API_URL="https://chainlens.test",
        CHAINLENS_SERVICE_TOKEN="service-secret",
        CHAINLENS_API_KEY="",
        CHAINLENS_REQUEST_TIMEOUT_SECONDS=5.0,
    )


@pytest.mark.asyncio
async def test_request_strips_query_and_validates_boundaries():
    """Pydantic must strip the query and enforce min/max length."""
    with pytest.raises(ValidationError):
        GapFillRequest(query="", workspace_id=1)

    with pytest.raises(ValidationError):
        GapFillRequest(query="x" * 501, workspace_id=1)

    with pytest.raises(ValidationError):
        GapFillRequest(query="test", workspace_id=0)

    request = GapFillRequest(query="  spaces  ", workspace_id=1)
    assert request.query == "spaces"
    assert request.workspace_id == 1
    assert request.mode == "sync"


@pytest.mark.asyncio
async def test_url_uses_async_query_param_and_default_base():
    service = GapFillService(config_obj=_fake_config_with_costs())
    assert service._url("sync") == "https://chainlens.test/v1/gap-fill"
    assert service._url("async") == "https://chainlens.test/v1/gap-fill?mode=async"

    default_service = GapFillService(config_obj=types.SimpleNamespace())
    assert default_service._url("sync") == "http://localhost:3001/v1/gap-fill"


@pytest.mark.asyncio
async def test_parse_response_handles_statuses_and_aliases():
    service = GapFillService(config_obj=_fake_config_with_costs())

    complete = service._parse_response(
        {"runId": "r1", "suggestedDomains": ["a"]}, 200
    )
    assert complete.status == "complete"
    assert complete.run_id == "r1"
    assert complete.suggested_domains == ["a"]

    accepted = service._parse_response({"run_id": "r2"}, 202)
    assert accepted.status == "accepted"
    assert accepted.run_id == "r2"

    failed = service._parse_response({"message": "boom"}, 418)
    assert failed.status == "failed"
    assert failed.message == "boom"

    empty = service._parse_response({}, 201)
    assert empty.status == "failed"
    assert empty.suggested_domains == []


@pytest.mark.asyncio
async def test_request_retries_401_and_returns_client_error_without_rotation(
    monkeypatch,
):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    calls: list[dict[str, Any]] = []
    responses = [(401, {"message": "no"}), (401, {"message": "no"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = GapFillService()
    response = await service.request(GapFillRequest(query="test", workspace_id=1))

    assert response.status == "client_error"
    assert "401" in response.message
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_request_retries_401_and_succeeds_after_rotation(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    class _RotatingFakeAuth(_FakeAuth):
        def rotate(self, **kwargs: Any) -> bool:
            return True

    monkeypatch.setattr(gap_fill_mod, "ChainLensServiceAuth", _RotatingFakeAuth)

    calls: list[dict[str, Any]] = []
    responses = [
        (401, {"message": "no"}),
        (202, {"runId": "rotated", "status": "accepted"}),
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = GapFillService()
    response = await service.request(
        GapFillRequest(query="test", workspace_id=1, mode="async")
    )

    assert response.status == "accepted"
    assert response.run_id == "rotated"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_request_returns_status_specific_errors(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    cases = [
        (429, "rate_limited"),
        (503, "upstream_error"),
        (422, "client_error"),
    ]

    for status_code, expected in cases:
        calls: list[dict[str, Any]] = []
        responses = [(status_code, {"message": "x"})]
        monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

        service = GapFillService()
        response = await service.request(GapFillRequest(query="test", workspace_id=1))
        assert response.status == expected, f"{status_code} -> {expected}"


@pytest.mark.asyncio
async def test_request_handles_httpx_errors(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    for exc in [httpx.TimeoutException("timeout"), httpx.RequestError("error")]:
        calls: list[dict[str, Any]] = []
        responses = [exc]
        monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

        service = GapFillService()
        response = await service.request(GapFillRequest(query="test", workspace_id=1))
        assert response.status in {"timeout", "unreachable"}


@pytest.mark.asyncio
async def test_request_parses_malformed_json_gracefully(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    class _BadJsonResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.content = b"not json"

        def json(self) -> dict[str, Any]:
            raise ValueError("boom")

    class _BadClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _BadClient:
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> _BadJsonResponse:
            return _BadJsonResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _BadClient)

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    service = GapFillService()
    response = await service.request(GapFillRequest(query="test", workspace_id=1))

    assert response.status == "complete"


@pytest.mark.asyncio
async def test_record_gap_fill_cost_uses_breakdown_and_debits_total(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)
    parsed = GapFillResponse(
        status="complete",
        cost_breakdown={
            "gap_fill_micros": 12_000,
            "scraper_micros": 5_000,
            "scraper_id": "batdongsan",
        },
    )

    await service._record_gap_fill_cost(payload, parsed, run_id="run-1")

    gap_fill_mod.check_balance.assert_awaited_once()
    gap_fill_mod.apply_debit.assert_awaited_once()
    assert gap_fill_mod.check_balance.await_args.args[2] == 17_000
    assert gap_fill_mod.apply_debit.await_args.args[2] == 17_000

    assert gap_fill_mod.record_token_usage.await_count == 2
    costs = {
        c.kwargs["usage_type"]: c.kwargs["cost_micros"]
        for c in gap_fill_mod.record_token_usage.await_args_list
    }
    assert costs[UsageType.CHAINLENS_GAP_FILL.value] == 12_000
    assert costs[UsageType.CHAINLENS_INGEST.value] == 5_000


@pytest.mark.asyncio
async def test_record_gap_fill_cost_falls_back_to_cost_dollars(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)
    parsed = GapFillResponse(status="complete", cost_dollars=0.123)

    await service._record_gap_fill_cost(payload, parsed, run_id="run-2")

    expected_micros = 123_000
    assert gap_fill_mod.check_balance.await_args.args[2] == expected_micros
    assert gap_fill_mod.apply_debit.await_args.args[2] == expected_micros

    cost = gap_fill_mod.record_token_usage.await_args.kwargs["cost_micros"]
    assert cost == expected_micros


@pytest.mark.asyncio
async def test_record_gap_fill_cost_skips_zero_or_negative_total(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)

    await service._record_gap_fill_cost(
        payload,
        GapFillResponse(
            status="complete",
            cost_breakdown={"gap_fill_micros": 0, "scraper_micros": -1},
        ),
        run_id="run-3",
    )

    gap_fill_mod.check_balance.assert_not_called()
    gap_fill_mod.apply_debit.assert_not_called()
    gap_fill_mod.record_token_usage.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_gap_fill_cost_skips_when_owner_missing(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    gap_fill_mod._resolve_workspace_owner.return_value = None

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)

    await service._record_gap_fill_cost(
        payload,
        GapFillResponse(status="complete", cost_dollars=0.01),
        run_id="run-4",
    )

    gap_fill_mod.check_balance.assert_not_called()
    gap_fill_mod.apply_debit.assert_not_called()


@pytest.mark.asyncio
async def test_record_gap_fill_cost_swallows_debit_exceptions(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    gap_fill_mod.check_balance.side_effect = RuntimeError("wallet down")

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)

    await service._record_gap_fill_cost(
        payload,
        GapFillResponse(status="complete", cost_dollars=0.01),
        run_id="run-5",
    )

    gap_fill_mod.apply_debit.assert_not_called()


@pytest.mark.asyncio
async def test_record_gap_fill_cost_uses_camel_case_aliases(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)

    service = GapFillService()
    payload = GapFillRequest(query="test", workspace_id=1)
    parsed = GapFillResponse(
        status="complete",
        cost_breakdown={
            "gapFillCostMicros": 7_000,
            "scraperCostMicros": 3_000,
            "scraperId": "muaban_bds",
        },
    )

    await service._record_gap_fill_cost(payload, parsed, run_id="run-6")

    assert gap_fill_mod.apply_debit.await_args.args[2] == 10_000
    details = gap_fill_mod.record_token_usage.await_args.kwargs["call_details"]
    assert details["scraper_id"] == "muaban_bds"


@pytest.mark.asyncio
async def test_async_worker_records_duration_and_publishes_events(monkeypatch):
    import time as time_mod

    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    # Two perf_counter ticks give a deterministic 123 ms duration.
    monkeypatch.setattr(
        time_mod, "perf_counter", Mock(side_effect=[1000.0, 1000.123])
    )
    monkeypatch.setattr(time_mod, "time", Mock(return_value=1_700_000_000.0))

    calls: list[dict[str, Any]] = []
    responses = [(200, {"runId": "w1"})]
    monkeypatch.setattr(httpx, "AsyncClient", _httpx_client_class(calls, responses))

    service = GapFillService()
    response = await service._async_worker(
        GapFillRequest(query="test", workspace_id=1), run_id="run-7"
    )

    assert response is not None
    assert response.run_id == "run_run-7"
    assert gap_fill_mod.finalize_run.awaited
    assert gap_fill_mod.finalize_run.await_args.kwargs["duration_ms"] == 123
    assert gap_fill_mod.finalize_run.await_args.kwargs["status"] == "success"

    publish = gap_fill_mod.run_event_bus.publish
    assert publish.call_count == 2
    started = publish.call_args_list[0][0][1]
    assert started["type"] == "run.started"
    assert started["ts"] == 1_700_000_000_000
    finished = publish.call_args_list[1][0][1]
    assert finished["type"] == "run.finished"
    assert finished["ts"] == 1_700_000_000_000


@pytest.mark.asyncio
async def test_async_worker_marks_error_and_publishes_on_exception(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)

    service = GapFillService()

    async def boom(*args: Any, **kwargs: Any) -> GapFillResponse:
        raise RuntimeError("worker boom")

    monkeypatch.setattr(service, "request", boom)

    response = await service._async_worker(
        GapFillRequest(query="test", workspace_id=1), run_id="run-8"
    )

    assert response.status == "error"
    assert response.run_id == "run_run-8"
    assert gap_fill_mod.finalize_run.awaited
    assert gap_fill_mod.finalize_run.await_args.kwargs["status"] == "error"
    assert gap_fill_mod.finalize_run.await_args.kwargs["error"] == "worker boom"


@pytest.mark.asyncio
async def test_request_sync_or_async_returns_async_running_immediately(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    service = GapFillService()
    response = await service.request_sync_or_async(
        GapFillRequest(query="test", workspace_id=1, mode="async")
    )

    assert response.status == "running"
    assert response.run_id.startswith("run_")


@pytest.mark.asyncio
async def test_request_sync_or_async_completes_when_fast(monkeypatch):
    import app.services.chainlens.gap_fill as gap_fill_mod

    _patch_gap_fill_db(monkeypatch, gap_fill_mod)
    monkeypatch.setattr(gap_fill_mod, "config", _fake_config_with_costs())
    _patch_auth(monkeypatch, gap_fill_mod)

    service = GapFillService()
    expected = GapFillResponse(status="complete", run_id="fast-run")
    monkeypatch.setattr(service, "request", AsyncMock(return_value=expected))

    response = await service.request_sync_or_async(
        GapFillRequest(query="test", workspace_id=1),
        sync_timeout_seconds=30.0,
    )

    assert response.status == "complete"
    assert response.run_id == "run_123"
