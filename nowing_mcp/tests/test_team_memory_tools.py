"""Tests for MCP workspace team-memory tools (Slice 1 MCP expansion)."""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "nowing_backend")
)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from mcp.server.lowlevel.server import request_ctx as mcp_request_ctx  # noqa: E402
from mcp_server.config import Settings  # noqa: E402
from mcp_server.core.auth import identity  # noqa: E402
from mcp_server.server import build_server  # noqa: E402


class FakeNowingClient:
    """Records calls and serves canned workspace/tool/team-memory responses."""

    def __init__(
        self, *, api_base: str, timeout: float, fallback_api_key: str | None
    ) -> None:
        self.api_base = api_base
        self.timeout = timeout
        self.fallback_api_key = fallback_api_key
        self.calls: list[tuple[str, str, dict | None]] = []

    async def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/workspaces"):
            return [{"id": 1, "name": "Test"}]
        if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
            return [
                {"name": "nowing_list_workspaces", "enabled": True},
                {"name": "nowing_select_workspace", "enabled": True},
                {"name": "nowing_workspace_memory_get", "enabled": True},
                {"name": "nowing_workspace_memory_update", "enabled": True},
            ]
        if (method, path) == ("GET", "/workspaces/1/memory"):
            return {
                "memory_md": "# Team brief\n- target: SEA market",
                "limits": {"soft": 10000, "hard": 20000},
            }
        if (method, path) == ("PUT", "/workspaces/1/memory"):
            return {
                "memory_md": kwargs.get("json", {}).get("memory_md", ""),
                "limits": {"soft": 10000, "hard": 20000},
            }
        return []


@pytest.fixture
def settings() -> Settings:
    return Settings(
        base_url="http://localhost:8000",
        api_key="nw_pat_test",
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace="Test",
        host="127.0.0.1",
        port=8080,
    )


def test_selfcheck_includes_team_memory_tools():
    """Offline selfcheck catalog must include the two team-memory tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_workspace_memory_get" in EXPECTED_TOOLS
    assert "nowing_workspace_memory_update" in EXPECTED_TOOLS


def test_team_memory_tools_appear_in_manifest(settings):
    """Both team-memory tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_workspace_memory_get" in names
    assert "nowing_workspace_memory_update" in names


def test_get_team_memory_reads_endpoint(monkeypatch, settings):
    """nowing_workspace_memory_get calls GET /workspaces/{id}/memory."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(mcp.call_tool("nowing_workspace_memory_get", {}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "SEA market" in str(result)
    assert any(call == ("GET", "/workspaces/1/memory", {}) for call in _client.calls)


def test_update_team_memory_overwrites_endpoint(monkeypatch, settings):
    """nowing_workspace_memory_update calls PUT with the full new markdown."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    new_brief = "# Team brief\n- target: NA market"
    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_workspace_memory_update",
                {"memory_md": new_brief},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "NA market" in str(result)
    assert any(
        call
        == (
            "PUT",
            "/workspaces/1/memory",
            {"json": {"memory_md": new_brief}},
        )
        for call in _client.calls
    )


def test_update_team_memory_is_destructive_hint(monkeypatch, settings):
    """The update tool must advertise destructiveHint so clients confirm first."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    tool = next(t for t in tools if t.name == "nowing_workspace_memory_update")
    annotations = tool.annotations
    assert annotations is not None
    assert annotations.destructiveHint is True
    assert annotations.readOnlyHint is False


def test_disabled_team_memory_tool_is_hidden(monkeypatch, settings):
    """A workspace that disables the update tool omits it from tools/list."""

    class DisabledUpdateClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            self.calls.append((method, path, kwargs))
            if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
                return [
                    {"name": "nowing_list_workspaces", "enabled": True},
                    {"name": "nowing_select_workspace", "enabled": True},
                    {"name": "nowing_workspace_memory_get", "enabled": True},
                    {"name": "nowing_workspace_memory_update", "enabled": False},
                ]
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", DisabledUpdateClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        tools = asyncio.run(mcp.list_tools())
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    names = {tool.name for tool in tools}
    assert "nowing_workspace_memory_update" not in names
    assert "nowing_workspace_memory_get" in names
