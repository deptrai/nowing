"""Tests for MCP workspace memory list + revalidate tools (Slice 2 expansion)."""

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
    """Records calls and serves canned workspace/tool/memory responses."""

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
                {"name": "nowing_memory_list", "enabled": True},
                {"name": "nowing_memory_revalidate", "enabled": True},
            ]
        if (method, path) == ("GET", "/workspaces/1/memories"):
            return [
                {
                    "id": 7,
                    "content": "Competitor X raised prices by 10%.",
                    "type": "semantic",
                    "tags": ["pricing"],
                    "confidence": 0.95,
                },
                {
                    "id": 3,
                    "content": "User prefers async reports.",
                    "type": "preference",
                    "tags": [],
                    "confidence": 0.8,
                },
            ]
        if method == "POST" and path.endswith("/memories/7/revalidate"):
            return {
                "id": 7,
                "content": "Competitor X raised prices by 15%.",
                "type": "semantic",
                "confidence": 0.98,
                "previous_versions": [{"previous_content": "10%"}],
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


def test_selfcheck_includes_slice2_memory_tools():
    """Offline selfcheck catalog must include the two Slice 2 tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_memory_list" in EXPECTED_TOOLS
    assert "nowing_memory_revalidate" in EXPECTED_TOOLS


def test_memory_list_tools_appear_in_manifest(settings):
    """Both Slice 2 memory tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_memory_list" in names
    assert "nowing_memory_revalidate" in names


def test_memory_list_calls_endpoint(monkeypatch, settings):
    """nowing_memory_list calls GET /workspaces/{id}/memories."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(mcp.call_tool("nowing_memory_list", {}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "Competitor X raised prices" in str(result)
    assert "prefers async reports" in str(result)
    assert any(
        call == ("GET", "/workspaces/1/memories", {"params": {"limit": 20}})
        for call in _client.calls
    )


def test_memory_list_passes_type_and_tags(monkeypatch, settings):
    """nowing_memory_list forwards type/tags filters to the endpoint."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        asyncio.run(
            mcp.call_tool(
                "nowing_memory_list",
                {"type": "semantic", "tags": ["pricing", "urgent"], "limit": 5},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert any(
        call
        == (
            "GET",
            "/workspaces/1/memories",
            {"params": {"limit": 5, "type": "semantic", "tags": "pricing,urgent"}},
        )
        for call in _client.calls
    )


def test_memory_revalidate_calls_endpoint(monkeypatch, settings):
    """nowing_memory_revalidate POSTs the revalidate endpoint."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool("nowing_memory_revalidate", {"memory_id": 7})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "raised prices by 15%" in str(result)
    assert any(
        call == ("POST", "/workspaces/1/memories/7/revalidate", {})
        for call in _client.calls
    )


def test_memory_revalidate_is_update_annotation(monkeypatch, settings):
    """Revalidate must be non-readonly (it mutates the stored fact)."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    tool = next(t for t in tools if t.name == "nowing_memory_revalidate")
    annotations = tool.annotations
    assert annotations is not None
    assert annotations.readOnlyHint is False
    assert annotations.destructiveHint is False
