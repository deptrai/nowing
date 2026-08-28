"""The agent door (05): generate one LangChain tool per registry verb."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain.tools import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationSourceType,
)
from app.capabilities.core.types import BillingUnit, Capability
from app.services.web_crawl_credit_service import InsufficientCreditsError

pytestmark = pytest.mark.asyncio


class _EchoInput(BaseModel):
    text: str = Field(description="The text to echo back.")


class _EchoOutput(BaseModel):
    echoed: str

    @property
    def billable_units(self) -> int:
        return 1


def _capability(
    *, name: str, output: _EchoOutput, unit=BillingUnit.WEB_CRAWL
) -> Capability:
    async def _executor(payload: _EchoInput) -> _EchoOutput:
        _executor.seen = payload
        return output

    cap = Capability(
        name=name,
        description=f"{name} does a thing.",
        input_schema=_EchoInput,
        output_schema=_EchoOutput,
        executor=_executor,
        billing_unit=unit,
    )
    cap.executor.seen = None  # type: ignore[attr-defined]
    return cap


class _FakeSessionCtx:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, *exc):
        return False


def _make_runtime(*, tool_call_id: str = "call-1") -> ToolRuntime:
    """Minimal stand-in for the LangGraph runtime the tool receives in a graph."""
    return ToolRuntime(
        state={},
        context=None,
        config={},
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


async def _invoke(tool, **kwargs):
    """Call the raw tool coroutine with a synthetic runtime."""
    runtime = _make_runtime()
    return await tool.coroutine(runtime=runtime, **kwargs)


@pytest.fixture
def isolate(monkeypatch):
    """Stub the billing session + charge/gate so tools never hit the DB."""
    from app.capabilities.core.access import agent as mod

    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCtx())
    charge = AsyncMock()
    gate = AsyncMock()
    monkeypatch.setattr(mod, "charge_capability", charge)
    monkeypatch.setattr(mod, "gate_capability", gate)
    return SimpleNamespace(module=mod, charge=charge, gate=gate)


def _verb_tool(tools, name: str):
    """Pick one capability tool out of the list (readers are appended after)."""
    return next(t for t in tools if t.name == name)


async def test_registry_becomes_one_tool_per_verb_plus_readers(isolate):
    caps = [
        _capability(name="web.scrape", output=_EchoOutput(echoed="a")),
        _capability(name="web.discover", output=_EchoOutput(echoed="b"), unit=None),
    ]

    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=caps)

    by_name = {t.name: t for t in tools}
    # One tool per verb, plus the shared run-reader tools, plus any static
    # cross-cutting tools (e.g. Telegram helpers) that are always mounted.
    from app.capabilities.core.access.agent import ALL_AVAILABLE_TOOLS

    assert set(by_name) == {
        "web_scrape",
        "web_discover",
        "read_run",
        "search_run",
        "export_run",
    } | {t.name for t in ALL_AVAILABLE_TOOLS}
    assert by_name["web_scrape"].description == "web.scrape does a thing."
    assert by_name["web_scrape"].args_schema is _EchoInput


async def test_input_field_docs_reach_the_model(isolate):
    """Per-field descriptions must surface in the tool's args schema (LLM context)."""
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="a"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    assert tool.args["text"]["description"] == "The text to echo back."


class _AntiBotOutput(BaseModel):
    """Output shape that looks like a degraded scraper result."""

    degraded: bool = True
    degradation_reason: str = "bot_detected"
    next_action: str = (
        "Escalated to human review; retry after credentials/proxy rotation"
    )
    items: list = Field(default_factory=list)

    @property
    def billable_units(self) -> int:
        return 0


async def test_tool_runs_executor_and_returns_serialized_output(isolate):
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi there"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    result = await _invoke(tool, text="ping")

    # Fake session makes record_run fail -> no run_id key, plain serialized output.
    assert result == {"echoed": "hi there"}
    assert cap.executor.seen.text == "ping"


async def test_repeated_anti_bot_tool_call_uses_cache(isolate, monkeypatch):
    """A second identical call in the same thread must not re-execute the tool."""
    from app.capabilities.core.access import agent as mod

    cap = _capability(name="web.scrape", output=_AntiBotOutput())
    tools = mod.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    monkeypatch.setattr(mod, "_current_thread_id", lambda: "thread-10-5")
    run_id = "550e8400-e29b-41d4-a716-446655440999"
    monkeypatch.setattr(mod, "record_run", AsyncMock(return_value=run_id))
    monkeypatch.setattr(
        mod, "enqueue_run_memory_extraction_after_commit", lambda _: None
    )

    first = await _invoke(tool, text="https://example.com/blocked")
    assert first.update["messages"][0].tool_call_id == "call-1"
    first_content = first.update["messages"][0].content
    assert '"degraded": true' in first_content
    assert '"next_step"' in first_content
    assert cap.executor.seen.text == "https://example.com/blocked"

    cap.executor.seen = None
    second = await _invoke(tool, text="https://example.com/blocked")
    assert cap.executor.seen is None  # executor was not invoked again
    second_content = second.update["messages"][0].content
    assert second_content == first_content


async def test_tool_charges_owner(isolate):
    output = _EchoOutput(echoed="hi")
    cap = _capability(name="web.scrape", output=output)
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    await _invoke(tool, text="ping")

    isolate.charge.assert_awaited_once()
    (charged_output, unit, ctx), _ = isolate.charge.call_args
    assert charged_output is output
    assert unit is BillingUnit.WEB_CRAWL
    assert ctx.workspace_id == 7


async def test_over_budget_returns_friendly_message(isolate):
    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi"))
    isolate.gate.side_effect = InsufficientCreditsError(
        message="This run would exceed your available credit.",
        balance_micros=0,
        required_micros=1_000_000,
    )
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    result = await _invoke(tool, text="ping")

    assert isinstance(result, str)
    assert "credit" in result.lower()
    assert cap.executor.seen is None
    isolate.charge.assert_not_awaited()


async def test_tool_registers_run_citation_when_stored(isolate, monkeypatch):
    """A stored run returns a Command with a RUN citation and a label."""
    from app.capabilities.core.access import agent as mod

    run_id = "550e8400-e29b-41d4-a716-446655440000"
    monkeypatch.setattr(mod, "record_run", AsyncMock(return_value=run_id))
    monkeypatch.setattr(
        mod, "enqueue_run_memory_extraction_after_commit", lambda _: None
    )

    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="hi"))
    tools = isolate.module.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    runtime = _make_runtime(tool_call_id="call-run-1")
    result = await tool.coroutine(runtime=runtime, text="ping")

    assert isinstance(result, Command)
    messages = result.update["messages"]
    assert len(messages) == 1
    assert "run_" + run_id in messages[0].content
    assert "Cite this scraper run" in messages[0].content
    assert messages[0].tool_call_id == "call-run-1"

    registry = result.update["citation_registry"]
    entry = registry.resolve(1)
    assert entry is not None
    assert entry.source_type == CitationSourceType.RUN
    assert entry.locator["run_id"] == f"run_{run_id}"
    assert entry.display["capability"] == "web.scrape"


async def test_runtime_survives_langchain_arg_parsing():
    """The runtime arg is injected, not exposed to the model args schema."""
    from app.capabilities.core.access.agent import build_capability_tools

    cap = _capability(name="web.scrape", output=_EchoOutput(echoed="a"))
    tools = build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "web_scrape")

    parsed = tool._parse_input({"text": "ping", "runtime": "RT"}, tool_call_id="call-1")
    assert parsed == {"text": "ping", "runtime": "RT"}
    # The model must never see "runtime" as an input field.
    assert tool.args_schema is not None
    assert "runtime" not in tool.args_schema.model_fields


class _WebSource(BaseModel):
    """Minimal source shape matching ``ResearchOutput.sources[]``."""

    url: str = Field(min_length=1)
    title: str = ""


class _ResearchOutput(BaseModel):
    """Output shape with ``sources`` for WEB_RESULT citation registration."""

    answer: str = ""
    sources: list[_WebSource] = Field(default_factory=list)

    @property
    def billable_units(self) -> int:
        return 1


async def test_tool_registers_web_result_citations_when_output_has_sources(
    isolate, monkeypatch
):
    """Output with ``sources`` → Command carries WEB_RESULT entries + RUN citation."""
    from app.capabilities.core.access import agent as mod

    monkeypatch.setattr(mod.config, "DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED", True)
    run_id = "660e8400-e29b-41d4-a716-446655440001"
    monkeypatch.setattr(mod, "record_run", AsyncMock(return_value=run_id))
    monkeypatch.setattr(
        mod, "enqueue_run_memory_extraction_after_commit", lambda _: None
    )

    output = _ResearchOutput(
        answer="Synthesis text",
        sources=[
            _WebSource(url="https://example.com/a", title="Source A"),
            _WebSource(url="https://example.com/b", title="Source B"),
        ],
    )
    cap = _capability(name="chainlens.research", output=output)
    tools = mod.build_capability_tools(workspace_id=7, capabilities=[cap])
    tool = _verb_tool(tools, "chainlens_research")

    runtime = _make_runtime(tool_call_id="call-web-1")
    result = await tool.coroutine(runtime=runtime, text="query")

    assert isinstance(result, Command)
    registry = result.update["citation_registry"]

    # RUN citation gets ordinal 1 (attach_run_citation is called first).
    run_entry = registry.resolve(1)
    assert run_entry is not None
    assert run_entry.source_type == CitationSourceType.RUN

    # WEB_RESULT citations get ordinals 2 and 3.
    web_a = registry.resolve(2)
    assert web_a is not None
    assert web_a.source_type == CitationSourceType.WEB_RESULT
    assert web_a.locator["url"] == "https://example.com/a"
    assert web_a.display["title"] == "Source A"

    web_b = registry.resolve(3)
    assert web_b is not None
    assert web_b.source_type == CitationSourceType.WEB_RESULT
    assert web_b.locator["url"] == "https://example.com/b"

    # ToolMessage content includes the run citation label.
    messages = result.update["messages"]
    assert "Cite this scraper run" in messages[0].content
