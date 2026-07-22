"""Red-phase acceptance tests for MCP tool filtering by workspace (Story 2.5).

These tests will fail until `WorkspaceAwareFastMCP` is implemented and
`mcp_server/selfcheck.py` `EXPECTED_TOOLS` is updated to include
`nowing_chainlens_research`.
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

from mcp.server.lowlevel.server import request_ctx as mcp_request_ctx
from mcp_server.config import Settings
from mcp_server.core.auth import identity
from mcp_server.selfcheck import EXPECTED_TOOLS, run as selfcheck_run
from mcp_server.server import build_server

_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "nowing_backend")
)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.mcp_tools import MCP_TOOL_NAMES  # noqa: E402


class FakeNowingClient:
    """Records calls and serves canned workspace/tool-setting responses."""

    def __init__(self, *, api_base: str, timeout: float, fallback_api_key: str | None) -> None:
        self.api_base = api_base
        self.timeout = timeout
        self.fallback_api_key = fallback_api_key
        self.calls: list[tuple[str, str]] = []

    async def request(self, method: str, path: str, **_kwargs):
        self.calls.append((method, path))
        if (method, path) == ("GET", "/workspaces"):
            return [{"id": 1, "name": "Test"}]
        if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
            # Every tool is enabled except one scraper.
            return [
                {"name": "nowing_list_workspaces", "enabled": True},
                {"name": "nowing_select_workspace", "enabled": True},
                {"name": "nowing_google_search", "enabled": False},
            ]
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


def test_selfcheck_expects_chainlens_research():
    """The offline selfcheck catalog must include `nowing_chainlens_research`."""
    assert "nowing_chainlens_research" in EXPECTED_TOOLS


def test_backend_catalog_matches_selfcheck():
    """The backend tool catalog and the MCP server selfcheck must agree on tool names."""
    assert MCP_TOOL_NAMES == EXPECTED_TOOLS


def test_selfcheck_passes_after_catalog_sync():
    """The offline manifest is healthy once the catalog is in sync."""
    problems = selfcheck_run()
    assert problems == []


def test_list_tools_filters_by_workspace_settings(monkeypatch, settings):
    """Given a disabled tool in backend settings, `tools/list` omits it."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)

    # Simulate an active request context so the server attempts workspace resolution.
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        tools = asyncio.run(mcp.list_tools())
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    names = {tool.name for tool in tools}
    assert "nowing_list_workspaces" in names
    assert "nowing_select_workspace" in names
    assert "nowing_google_search" not in names


def test_call_tool_rejects_disabled_tool(monkeypatch, settings):
    """Calling a disabled tool for the active workspace returns an error."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)

    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(
                mcp.call_tool("nowing_google_search", {"queries": ["anything"]})
            )
        assert "disabled" in str(exc_info.value).lower()
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)


def test_call_tool_uses_workspace_argument(monkeypatch, settings):
    """When `workspace` argument differs from active workspace, guard uses it."""
    # This test documents the expected behavior for workspace-scoped tool calls.
    # It will fail until `WorkspaceAwareFastMCP.call_tool` resolves the
    # `workspace` argument and fetches that workspace's settings.

    class WorkspaceArgumentClient(FakeNowingClient):
        async def request(self, method: str, path: str, **_kwargs):
            self.calls.append((method, path))
            if (method, path) == ("GET", "/workspaces"):
                return [
                    {"id": 1, "name": "Active"},
                    {"id": 2, "name": "Other"},
                ]
            if (method, path) == ("GET", "/workspaces/2/mcp-tools"):
                return [
                    {"name": "nowing_list_workspaces", "enabled": True},
                    {"name": "nowing_select_workspace", "enabled": True},
                    {"name": "nowing_google_search", "enabled": False},
                ]
            return []

    monkeypatch.setattr("mcp_server.server.NowingClient", WorkspaceArgumentClient)

    mcp, _client = build_server(settings)
    mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        # Active workspace would be 1; explicit argument is 2 and disables search.
        with pytest.raises(Exception) as exc_info:
            asyncio.run(
                mcp.call_tool(
                    "nowing_google_search",
                    {"queries": ["anything"], "workspace": "Other"},
                )
            )
        assert "disabled" in str(exc_info.value).lower()
    finally:
        identity.unbind_api_key(identity_token)


def test_call_tool_fail_closed_on_backend_error(monkeypatch, settings):
    """If backend settings cannot be fetched, `call_tool` is denied."""

    class FailingClient(FakeNowingClient):
        async def request(self, method: str, path: str, **_kwargs):
            self.calls.append((method, path))
            raise RuntimeError("backend unreachable")

    monkeypatch.setattr("mcp_server.server.NowingClient", FailingClient)

    mcp, _client = build_server(settings)
    mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(mcp.call_tool("nowing_google_search", {"queries": ["x"]}))
        assert "enabled" in str(exc_info.value).lower()
    finally:
        identity.unbind_api_key(identity_token)
