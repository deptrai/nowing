"""Red-phase scaffolds for REST sync/async ChainLens degradation (9.1a)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput
from app.capabilities.core import async_runner
from app.capabilities.core.access import rest
from app.capabilities.core.types import BillingUnit, Capability, CapabilityContext
from app.config import config

pytestmark = pytest.mark.unit


class _ResearchSpy:
    def __init__(self, output: ResearchOutput):
        self.output = output
        self.calls: list[tuple[tuple, dict]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.output


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _noop_async(*args, **kwargs) -> None:
    return None


class _FakeSessionCtx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


async def _fake_record(**kwargs) -> str:
    return "test-run-id"


def _build_app(capabilities, monkeypatch) -> FastAPI:
    monkeypatch.setattr(rest, "check_workspace_access", _noop_async, raising=True)
    monkeypatch.setattr(
        rest, "record_and_publish_sync_run", _fake_record, raising=False
    )
    monkeypatch.setattr(
        rest, "record_and_publish_sync_run_error", _fake_record, raising=False
    )
    monkeypatch.setattr(rest, "charge_capability", AsyncMock(return_value=0))
    monkeypatch.setattr(rest, "gate_capability", AsyncMock())
    monkeypatch.setattr(
        config, "DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED", True
    )

    from app.db import get_async_session
    from app.users import get_auth_context

    app = FastAPI()
    app.include_router(rest.build_capabilities_router(capabilities), prefix="/api/v1")
    app.dependency_overrides[get_auth_context] = lambda: SimpleNamespace(user=None)

    async def _session():
        yield SimpleNamespace()

    app.dependency_overrides[get_async_session] = _session
    return app


async def test_rest_sync_passes_capability_context_to_chainlens_research(monkeypatch):
    output = ResearchOutput()
    output.status = "engine_unavailable"
    output.next_action = "Deep research is not available in self-host Phase 1."
    spy = _ResearchSpy(output)

    capability = Capability(
        name="chainlens.research",
        description="Research.",
        input_schema=ResearchInput,
        output_schema=ResearchOutput,
        executor=spy,
        billing_unit=BillingUnit.CHAINLENS_QUERY,
    )

    app = _build_app([capability], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/chainlens/research",
            json={"query": "hello"},
        )

    assert resp.status_code == 200
    assert any(
        isinstance(arg, CapabilityContext) for args, _ in spy.calls for arg in args
    ), "CapabilityContext was not passed to the executor"


async def test_rest_sync_body_contains_degraded_status(monkeypatch):
    output = ResearchOutput()
    output.status = "engine_unavailable"
    output.next_action = "Deep research is not available in self-host Phase 1."

    capability = Capability(
        name="chainlens.research",
        description="Research.",
        input_schema=ResearchInput,
        output_schema=ResearchOutput,
        executor=_ResearchSpy(output),
        billing_unit=BillingUnit.CHAINLENS_QUERY,
    )

    app = _build_app([capability], monkeypatch)
    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/chainlens/research",
            json={"query": "hello"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "engine_unavailable"
    assert body["degraded"] is True
    assert body["next_action"] is not None
    assert body["billable_units"] == 0


async def _fake_execute_with_context(executor, *, payload, ctx):
    return await executor(payload, ctx)


def _stub_async_runner(monkeypatch, finalize, charge):
    monkeypatch.setattr(async_runner, "async_session_maker", _FakeSessionCtx)
    monkeypatch.setattr(
        async_runner, "enqueue_run_memory_extraction_after_commit", Mock(return_value=True)
    )
    monkeypatch.setattr(
        async_runner, "execute_with_context", _fake_execute_with_context
    )
    monkeypatch.setattr(async_runner, "charge_capability", charge)
    monkeypatch.setattr(async_runner, "finalize_run", finalize)


async def test_rest_async_executor_receives_capability_context(monkeypatch):
    output = ResearchOutput()
    output.status = "engine_unavailable"
    output.next_action = "Deep research is not available in self-host Phase 1."
    spy = _ResearchSpy(output)

    from app.capabilities.core.events import run_event_bus

    monkeypatch.setattr(run_event_bus, "publish", Mock())
    monkeypatch.setattr(run_event_bus, "close", Mock())
    _stub_async_runner(
        monkeypatch,
        finalize=AsyncMock(return_value=True),
        charge=AsyncMock(return_value=0),
    )

    await async_runner._execute_async_run(
        run_id="run-1",
        workspace_id=7,
        capability="chainlens.research",
        unit=BillingUnit.CHAINLENS_QUERY,
        executor=spy,
        payload=ResearchInput(query="hello"),
    )

    assert any(
        isinstance(arg, CapabilityContext) for args, _ in spy.calls for arg in args
    ), "CapabilityContext was not passed to the async executor"


async def test_rest_async_degraded_run_persists_cost_micros_none(monkeypatch):
    output = ResearchOutput()
    output.status = "engine_unavailable"

    spy = _ResearchSpy(output)
    finalize = AsyncMock(return_value=True)
    from app.capabilities.core.events import run_event_bus

    monkeypatch.setattr(run_event_bus, "publish", Mock())
    monkeypatch.setattr(run_event_bus, "close", Mock())
    _stub_async_runner(
        monkeypatch,
        finalize=finalize,
        charge=AsyncMock(return_value=0),
    )

    await async_runner._execute_async_run(
        run_id="run-1",
        workspace_id=7,
        capability="chainlens.research",
        unit=BillingUnit.CHAINLENS_QUERY,
        executor=spy,
        payload=ResearchInput(query="hello"),
    )

    _, kwargs = finalize.call_args
    assert kwargs["cost_micros"] is None


async def test_rest_async_degraded_output_text_matches_sync_and_sse_terminal(
    monkeypatch,
):
    """AC-7: async run persists the same status/reason as sync and emits a terminal event."""
    from unittest.mock import Mock

    from app.capabilities.core.events import run_event_bus

    output = ResearchOutput(
        status="engine_unavailable",
        degradation_reason="not_configured",
    )
    spy = _ResearchSpy(output)

    finalize = AsyncMock(return_value=True)
    publish = Mock()
    close = Mock()
    monkeypatch.setattr(run_event_bus, "publish", publish)
    monkeypatch.setattr(run_event_bus, "close", close)
    _stub_async_runner(
        monkeypatch,
        finalize=finalize,
        charge=AsyncMock(side_effect=RuntimeError("wallet down")),
    )

    await async_runner._execute_async_run(
        run_id="run-ac7",
        workspace_id=7,
        capability="chainlens.research",
        unit=BillingUnit.CHAINLENS_QUERY,
        executor=spy,
        payload=ResearchInput(query="hello"),
    )

    _, f_kwargs = finalize.call_args
    serialized = f_kwargs["serialized"]
    assert serialized is not None
    assert "engine_unavailable" in serialized.text
    assert "not_configured" in serialized.text

    finished = [
        call
        for call in publish.call_args_list
        if len(call.args) > 1 and call.args[1].get("type") == "run.finished"
    ]
    assert len(finished) == 1
    assert finished[0].args[1]["status"] == "success"
    close.assert_called_once_with("run-ac7")


async def test_rest_sync_charge_failure_still_returns_degraded_status(monkeypatch):
    """FM-12: a failing charge_capability must not turn a degraded result into HTTP 500."""
    output = ResearchOutput(
        status="engine_unavailable",
        degradation_reason="not_configured",
    )
    spy = _ResearchSpy(output)

    capability = Capability(
        name="chainlens.research",
        description="Research.",
        input_schema=ResearchInput,
        output_schema=ResearchOutput,
        executor=spy,
        billing_unit=BillingUnit.CHAINLENS_QUERY,
    )

    app = _build_app([capability], monkeypatch)
    monkeypatch.setattr(
        rest, "charge_capability", AsyncMock(side_effect=RuntimeError("wallet down"))
    )

    async with _client(app) as client:
        resp = await client.post(
            "/api/v1/workspaces/7/scrapers/chainlens/research",
            json={"query": "hello"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "engine_unavailable"
    assert body.get("degraded") is True
    assert body.get("degradation_reason") == "not_configured"
    assert "next_action" in body
