"""Unit tests for vn_jobs subagent load_tools."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.vn_jobs.tools.index import (
    load_tools,
)


@pytest.mark.unit
def test_load_tools_returns_empty_when_workspace_id_missing():
    """Verify load_tools returns empty list when workspace_id is None or invalid."""
    assert load_tools() == []
    assert load_tools(dependencies={}) == []
    assert load_tools(dependencies={"workspace_id": None}) == []
    assert load_tools(dependencies={"workspace_id": "invalid"}) == []
    assert load_tools(dependencies={"workspace_id": -5}) == []
    assert load_tools(dependencies={"workspace_id": 0}) == []


@pytest.mark.unit
def test_load_tools_returns_tools_when_workspace_id_valid():
    """Verify load_tools returns list of tools when workspace_id is positive integer."""
    tools = load_tools(dependencies={"workspace_id": 10})
    assert len(tools) > 0
