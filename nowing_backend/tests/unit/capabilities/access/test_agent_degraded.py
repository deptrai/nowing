"""Red-phase scaffolds for agent door ChainLens degradation (9.1a)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput
from app.capabilities.core.access import agent as agent_mod
from app.capabilities.core.types import BillingUnit, Capability, CapabilityContext

pytestmark = pytest.mark.unit


class _FakeSessionCtx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def isolate_agent(monkeypatch):
    monkeypatch.setattr(agent_mod, "async_session_maker", lambda: _FakeSessionCtx())
    monkeypatch.setattr(
        agent_mod.config, "DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED", True
    )
    charge = AsyncMock(return_value=0)
    gate = AsyncMock()
    monkeypatch.setattr(agent_mod, "charge_capability", charge)
    monkeypatch.setattr(agent_mod, "gate_capability", gate)
    record = AsyncMock(return_value="agent-run-id")
    monkeypatch.setattr(agent_mod, "record_run", record)
    return SimpleNamespace(charge=charge, gate=gate, record=record)


class _ResearchSpy:
    def __init__(self, output: ResearchOutput):
        self.output = output
        self.calls: list[tuple[tuple, dict]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.output


def _research_capability(output: ResearchOutput) -> Capability:
    return Capability(
        name="chainlens.research",
        description="Research.",
        input_schema=ResearchInput,
        output_schema=ResearchOutput,
        executor=_ResearchSpy(output),
        billing_unit=BillingUnit.CHAINLENS_QUERY,
    )


async def test_agent_tool_passes_capability_context_to_chainlens(isolate_agent):
    output = ResearchOutput()
    output.status = "engine_unavailable"
    output.next_action = "Deep research is not available in self-host Phase 1."
    cap = _research_capability(output)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    await tool.ainvoke({"query": "hello"})

    spy = cap.executor
    assert any(
        isinstance(arg, CapabilityContext) for args, _ in spy.calls for arg in args
    ), "CapabilityContext was not passed to the agent executor"


async def test_agent_tool_does_not_raise_for_engine_unavailable(isolate_agent):
    output = ResearchOutput()
    output.status = "engine_unavailable"
    output.next_action = "Deep research is not available in self-host Phase 1."
    cap = _research_capability(output)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert isinstance(result, dict)
    assert result["status"] == "engine_unavailable"
    assert result["degraded"] is True
    assert result["next_step"] is not None or result["next_action"] is not None
    assert "answer" not in result or not result.get("answer")


async def test_agent_tool_returns_partial_with_fallback_hits(isolate_agent):
    output = ResearchOutput(
        answer="partial answer",
        sources=[{"title": "KB", "url": "nowing://documents/7/chunks/12"}],
    )
    output.status = "partial"
    cap = _research_capability(output)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert result["status"] == "partial"
    assert result["degraded"] is True
    assert result["fallback_hit_count"] == 1


async def test_agent_tool_charge_failure_does_not_raise(isolate_agent):
    """FM-12: a failing charge_capability must not make the agent tool raise."""
    output = ResearchOutput(
        status="engine_unavailable",
        degradation_reason="not_configured",
    )
    cap = _research_capability(output)

    # Make the wallet charge fail inside the tool; the executor already degraded.
    isolate_agent.charge.side_effect = RuntimeError("wallet down")

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert isinstance(result, dict)
    assert result["status"] == "engine_unavailable"
    assert result["degraded"] is True
    assert result.get("degradation_reason") == "not_configured"
    assert "next_action" in result or "next_step" in result


async def test_agent_tool_rejects_unauthorized_workspace(isolate_agent, monkeypatch):
    """Agent door must re-validate workspace access before executing the tool."""
    from fastapi import HTTPException

    from app.exceptions import ForbiddenError

    output = ResearchOutput(status="engine_unavailable")
    output.next_action = "Deep research is not available in self-host Phase 1."
    cap = _research_capability(output)

    auth = SimpleNamespace(
        user=SimpleNamespace(id="u-1"), pat=None, is_gated=False, method="session"
    )

    async def _deny(*args, **kwargs):
        raise HTTPException(status_code=403, detail="Unauthorized workspace")

    monkeypatch.setattr(agent_mod, "check_workspace_access", _deny)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1", auth_context=auth
    )
    tool = next(t for t in tools if t.name == "chainlens_research")

    with pytest.raises(ForbiddenError, match="Unauthorized workspace"):
        await tool.ainvoke({"query": "hello"})

    # The capability executor must not run when workspace access is denied.
    assert not cap.executor.calls


async def test_agent_tool_quality_remains_async_even_when_sync_enabled(
    isolate_agent, monkeypatch
):
    """NFR-9: quality mode is async-only in chat even when DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED."""
    output = ResearchOutput(status="engine_unavailable")
    output.next_action = "Deep research is not available in self-host Phase 1."
    cap = _research_capability(output)

    monkeypatch.setattr(agent_mod, "_current_research_mode", lambda: "quality")
    start_async = AsyncMock(return_value="agent-quality-run")
    monkeypatch.setattr(agent_mod, "start_async_run", start_async, raising=True)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert result["run_id"] == "run_agent-quality-run"
    assert result["status"] == "running"
    start_async.assert_awaited_once()


async def test_agent_tool_auto_remains_async_even_when_sync_enabled(
    isolate_agent, monkeypatch
):
    """NFR-9: auto mode is async-only because the engine may resolve to quality/deep."""
    output = ResearchOutput(status="engine_unavailable")
    output.next_action = "Deep research is not available in self-host Phase 1."
    cap = _research_capability(output)

    monkeypatch.setattr(agent_mod, "_current_research_mode", lambda: "auto")
    start_async = AsyncMock(return_value="agent-auto-run")
    monkeypatch.setattr(agent_mod, "start_async_run", start_async, raising=True)

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert result["run_id"] == "run_agent-auto-run"
    assert result["status"] == "running"
    start_async.assert_awaited_once()


async def test_agent_tool_balanced_sync_allowed_when_sync_enabled(
    isolate_agent, monkeypatch
):
    """NFR-9: balanced mode may run synchronously when the sync flag is on."""
    output = ResearchOutput(
        answer="inline answer",
        sources=[{"title": "KB", "url": "nowing://documents/7/chunks/12"}],
        status="complete",
    )
    cap = _research_capability(output)

    monkeypatch.setattr(agent_mod, "_current_research_mode", lambda: "balanced")

    tools = agent_mod.build_capability_tools(
        workspace_id=7, capabilities=[cap], user_id="u-1"
    )
    tool = next(t for t in tools if t.name == "chainlens_research")
    result = await tool.ainvoke({"query": "hello"})

    assert isinstance(result, dict)
    assert result.get("answer") == "inline answer"
