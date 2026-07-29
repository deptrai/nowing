"""Red-phase scaffolds for agent door ChainLens degradation (9.1a)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

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
        isinstance(arg, CapabilityContext)
        for args, _ in spy.calls
        for arg in args
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
