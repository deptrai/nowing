"""Unit tests for the main-agent tool registry filter (Story 18.4)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.main_agent.tools import registry as _registry
from app.agents.chat.multi_agent_chat.main_agent.tools.registry import (
    build_main_agent_tools,
)

pytestmark = pytest.mark.unit


def _fake_tool(name: str) -> BaseTool:
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    return tool


@pytest.fixture
def _fake_factories(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the real factories with cheap fakes so tests only exercise filtering."""
    fake_factories = {
        "create_automation": (lambda _deps: _fake_tool("create_automation"), ()),
        "update_memory": (lambda _deps: _fake_tool("update_memory"), ()),
    }
    monkeypatch.setattr(_registry, "_MAIN_AGENT_TOOL_FACTORIES", fake_factories)


def test_build_main_agent_tools_with_no_restrictions(_fake_factories) -> None:
    """AC-2: when enabled_tools is None all main-agent tools are built."""
    tools = build_main_agent_tools(dependencies={})
    assert [t.name for t in tools] == ["create_automation", "update_memory"]


def test_build_main_agent_tools_with_allowlist(_fake_factories) -> None:
    """AC-2: non-empty enabled_tools is an allowlist."""
    tools = build_main_agent_tools(dependencies={}, enabled_tools=["update_memory"])
    assert [t.name for t in tools] == ["update_memory"]


def test_build_main_agent_tools_empty_allowlist_is_fail_closed(_fake_factories) -> None:
    """AC-2: empty enabled_tools means no main-agent tools."""
    tools = build_main_agent_tools(dependencies={}, enabled_tools=[])
    assert tools == []


def test_build_main_agent_tools_disabled_overrides_enabled(_fake_factories) -> None:
    """AC-2: disabled_tools drop tools even if in the allowlist."""
    tools = build_main_agent_tools(
        dependencies={},
        enabled_tools=["create_automation", "update_memory"],
        disabled_tools=["create_automation"],
    )
    assert [t.name for t in tools] == ["update_memory"]


def test_build_main_agent_tools_unknown_names_are_ignored_and_logged(
    _fake_factories, caplog
) -> None:
    """Dev notes: unknown tool names in lists are ignored with a warning."""
    with caplog.at_level("WARNING"):
        tools = build_main_agent_tools(
            dependencies={},
            enabled_tools=["update_memory", "unknown_tool"],
        )
    assert [t.name for t in tools] == ["update_memory"]
    assert "unknown_tool" in caplog.text
