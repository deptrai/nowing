"""Green-phase ATDD tests for Story 27.2a — main-agent generate_presentation tool."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def tool_factory():
    """Return the configured tool factory, disabling unrelated tools."""
    pytest.importorskip("app.agents.chat.multi_agent_chat.main_agent.tools.index")
    from app.agents.chat.multi_agent_chat.main_agent.tools.registry import (
        build_main_agent_tools,
    )

    def _factory(deps):
        return build_main_agent_tools(
            deps,
            enabled_tools=["generate_presentation"],
        )

    return _factory


@pytest.fixture
def enable_presentation_studio(monkeypatch):
    """Turn the global gate on so later guards are actually exercised."""
    monkeypatch.setattr(
        "app.config.config.PRESENTATION_STUDIO_ENABLED", True, raising=False
    )


@pytest.mark.unit
async def test_tool_is_in_main_agent_tool_list():
    """AC-1: `generate_presentation` is present in the ordered main-agent tool names."""
    pytest.importorskip("app.agents.chat.multi_agent_chat.main_agent.tools.index")
    from app.agents.chat.multi_agent_chat.main_agent.tools.index import (
        MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED,
    )

    assert "generate_presentation" in MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED


@pytest.mark.unit
async def test_tool_factory_registered_with_workspace_and_user_deps():
    """AC-1: `_MAIN_AGENT_TOOL_FACTORIES` includes `generate_presentation` with the right deps."""
    pytest.importorskip("app.agents.chat.multi_agent_chat.main_agent.tools.registry")
    from app.agents.chat.multi_agent_chat.main_agent.tools.registry import (
        _MAIN_AGENT_TOOL_FACTORIES,
    )

    assert "generate_presentation" in _MAIN_AGENT_TOOL_FACTORIES
    _factory, deps = _MAIN_AGENT_TOOL_FACTORIES["generate_presentation"]
    assert deps == ("workspace_id", "user_id")


@pytest.mark.unit
async def test_chat_mode_enables_only_generate_presentation():
    """AC-1: presentation_studio ChatMode replaces the tool list with generate_presentation."""
    from app.tasks.chat.streaming.flows.new_chat.chat_modes import CHAT_MODES

    mode = CHAT_MODES["presentation_studio"]
    assert mode.enabled_tools == ["generate_presentation"]
    assert "optional title" not in (mode.system_prompt or "").lower()


@pytest.mark.unit
async def test_generate_presentation_is_a_deliverable_tool():
    """AC-1: SSE card wiring requires the name in DELIVERABLE_TOOLS."""
    from app.tasks.chat.streaming.handlers.tools.deliverables.tool_names import (
        DELIVERABLE_TOOLS,
    )

    assert "generate_presentation" in DELIVERABLE_TOOLS


@pytest.mark.unit
async def test_tool_returns_validation_failed_for_empty_prompt(
    tool_factory, enable_presentation_studio
):
    """AC-6/AC-2: empty prompt returns a typed JSON status=validation_failed."""
    tools = tool_factory(
        {
            "workspace_id": 1,
            "user_id": uuid4(),
        }
    )
    tool = next(t for t in tools if t.name == "generate_presentation")
    result = await tool.ainvoke({"prompt": "   ", "output_format": "pptx"})
    assert result["status"] == "validation_failed"
    assert "prompt is required" in result["error"].lower()
    assert not result.get("presentation_id")


@pytest.mark.unit
async def test_tool_returns_validation_failed_when_flag_off(tool_factory, monkeypatch):
    """AC-6: when PRESENTATION_STUDIO_ENABLED=false the tool fails closed with a typed error."""
    monkeypatch.setattr(
        "app.config.config.PRESENTATION_STUDIO_ENABLED", False, raising=False
    )
    tools = tool_factory(
        {
            "workspace_id": 1,
            "user_id": uuid4(),
        }
    )
    tool = next(t for t in tools if t.name == "generate_presentation")
    result = await tool.ainvoke({"prompt": "Pitch deck", "output_format": "pptx"})
    assert result["status"] == "validation_failed"
    assert "not enabled" in result["error"].lower()


@pytest.mark.unit
async def test_tool_returns_validation_failed_for_invalid_user_id(
    tool_factory, enable_presentation_studio
):
    """AC-5: an unparseable user_id returns validation_failed without opening a DB session."""
    tools = tool_factory(
        {
            "workspace_id": 1,
            "user_id": "not-a-uuid",
        }
    )
    tool = next(t for t in tools if t.name == "generate_presentation")
    result = await tool.ainvoke({"prompt": "Pitch deck", "output_format": "pptx"})
    assert result["status"] == "validation_failed"
    assert "permission" in result["error"].lower()
    assert not result.get("presentation_id")


@pytest.mark.unit
async def test_tool_returns_validation_failed_for_invalid_output_format(
    tool_factory, enable_presentation_studio
):
    """AC-2: unknown output_format is typed validation_failed, not a pydantic error leak."""
    tools = tool_factory(
        {
            "workspace_id": 1,
            "user_id": uuid4(),
        }
    )
    tool = next(t for t in tools if t.name == "generate_presentation")
    result = await tool.ainvoke({"prompt": "Pitch deck", "output_format": "pdf"})
    assert result["status"] == "validation_failed"
    assert "pptx" in result["error"].lower()
    assert "validation error" not in result["error"].lower()
    assert not result.get("presentation_id")


class _FakeStreaming:
    def __init__(self) -> None:
        self.terminals: list[tuple[str, str]] = []

    def format_terminal_info(self, text: str, message_type: str = "info") -> str:
        self.terminals.append((text, message_type))
        return f"TERM::{message_type}"


class _FakeCtx:
    def __init__(self, tool_output: object) -> None:
        self.tool_output = tool_output
        self.cards: list[object] = []
        self.streaming_service = _FakeStreaming()

    def emit_tool_output_card(self, payload: object) -> str:
        self.cards.append(payload)
        return "CARD"


@pytest.mark.unit
def test_emission_degraded_is_warning_not_success():
    """AC-3: Marp preview skipped must not print 'generated successfully'."""
    from app.tasks.chat.streaming.handlers.tools.deliverables.generate_presentation.emission import (
        iter_completion_emission_frames,
    )

    ctx = _FakeCtx(
        {
            "status": "degraded",
            "title": "Q3 Pitch",
            "degradation_reason": "dependency_missing",
        }
    )
    list(iter_completion_emission_frames(ctx))
    assert ctx.cards[0]["status"] == "degraded"
    text, kind = ctx.streaming_service.terminals[-1]
    assert kind == "warning"
    assert "successfully" not in text.lower()
    assert "preview unavailable" in text.lower()


@pytest.mark.unit
def test_emission_failed_without_error_is_error_terminal():
    from app.tasks.chat.streaming.handlers.tools.deliverables.generate_presentation.emission import (
        iter_completion_emission_frames,
    )

    ctx = _FakeCtx({"status": "failed", "title": "Q3 Pitch"})
    list(iter_completion_emission_frames(ctx))
    text, kind = ctx.streaming_service.terminals[-1]
    assert kind == "error"
    assert "failed" in text.lower()


@pytest.mark.unit
def test_thinking_degraded_does_not_claim_success():
    from app.tasks.chat.streaming.handlers.tools.deliverables.generate_presentation.thinking import (
        resolve_completed_thinking,
    )

    title, items = resolve_completed_thinking(
        "generate_presentation",
        {
            "status": "degraded",
            "title": "Q3 Pitch",
            "degradation_reason": "dependency_missing",
        },
        ["Prompt: pitch"],
    )
    assert "limited preview" in title.lower()
    assert "successfully" not in " ".join(items).lower()
    assert any("dependency_missing" in item for item in items)


@pytest.mark.unit
def test_thinking_validation_failed_without_error_is_failure():
    from app.tasks.chat.streaming.handlers.tools.deliverables.generate_presentation.thinking import (
        resolve_completed_thinking,
    )

    title, items = resolve_completed_thinking(
        "generate_presentation",
        {"status": "validation_failed"},
        [],
    )
    assert "failed" in title.lower()
    assert any("error:" in item.lower() for item in items)
