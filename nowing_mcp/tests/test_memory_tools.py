"""Red-phase tests for MCP memory tools (Story 4.5).

These tests will fail until `mcp_server.features.memory` is implemented and
registered in `mcp_server.server.build_server`, and `selfcheck.py` is updated.
"""

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
from mcp_server.core.client import ToolError  # noqa: E402
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
                {"name": "nowing_remember", "enabled": True},
                {"name": "nowing_recall", "enabled": True},
                {"name": "nowing_update_fact", "enabled": True},
                {"name": "nowing_continue_research", "enabled": True},
            ]
        if (method, path) == ("POST", "/workspaces/1/memories"):
            return {
                "id": 42,
                "workspace_id": 1,
                "content": kwargs.get("json", {}).get("content", ""),
                "type": kwargs.get("json", {}).get("type", "semantic"),
                "tags": kwargs.get("json", {}).get("tags", []),
            }
        if (method, path) == ("POST", "/workspaces/1/memories/search"):
            return {
                "items": [
                    {
                        "id": 7,
                        "content": "Competitor X raised prices by 10%.",
                        "type": "semantic",
                        "confidence": 0.95,
                    }
                ]
            }
        if (method, path) == ("PATCH", "/memories/42"):
            return {
                "id": 42,
                "content": kwargs.get("json", {}).get("corrected_content", ""),
                "previous_versions": [
                    {"previous_content": "Old fact"}
                ],
            }
        if method == "GET" and "/research-threads/" in path and path.endswith(
            "/context"
        ):
            return {
                "thread_id": 9,
                "title": "Q3 research",
                "memories": [
                    {
                        "id": 7,
                        "content": "Competitor X raised prices by 10%.",
                        "type": "semantic",
                        "confidence": 0.95,
                    }
                ],
                "citations": [
                    {
                        "label": "example.com",
                        "url": "https://example.com/pricing",
                        "source_type": "url",
                    }
                ],
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


def test_selfcheck_includes_memory_tools():
    """Offline selfcheck catalog must include the four memory tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_remember" in EXPECTED_TOOLS
    assert "nowing_recall" in EXPECTED_TOOLS
    assert "nowing_update_fact" in EXPECTED_TOOLS
    assert "nowing_continue_research" in EXPECTED_TOOLS


def test_memory_tools_appear_in_manifest(settings):
    """All four memory tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_remember" in names
    assert "nowing_recall" in names
    assert "nowing_update_fact" in names
    assert "nowing_continue_research" in names


def test_remember_calls_create_memory_endpoint(monkeypatch, settings):
    """nowing_remember calls POST /workspaces/{id}/memories and returns the saved memory."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_remember",
                {
                    "content": "Competitor X raised prices by 10%.",
                    "type": "semantic",
                    "tags": ["competitor", "pricing"],
                    "confidence": 0.95,
                },
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "Competitor X" in str(result)
    assert any(
        call == ("POST", "/workspaces/1/memories", {
            "json": {
                "content": "Competitor X raised prices by 10%.",
                "type": "semantic",
                "tags": ["competitor", "pricing"],
                "confidence": 0.95,
                "source_type": "manual",
                "source_id": None,
                "research_thread_id": None,
            }
        })
        for call in _client.calls
    )


def test_recall_calls_search_endpoint(monkeypatch, settings):
    """nowing_recall calls POST /workspaces/{id}/memories/search and returns hits."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_recall",
                {"query": "pricing", "top_k": 5, "type": "semantic"},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "Competitor X" in str(result)
    assert any(
        call[0] == "POST" and "/memories/search" in call[1]
        for call in _client.calls
    )


def test_update_fact_calls_patch_endpoint(monkeypatch, settings):
    """nowing_update_fact calls PATCH /memories/{id} and returns the updated memory."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_update_fact",
                {"memory_id": 42, "corrected_content": "Competitor X raised prices by 12%."},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "12%" in str(result)
    assert any(
        call == ("PATCH", "/memories/42", {
            "json": {"corrected_content": "Competitor X raised prices by 12%."}
        })
        for call in _client.calls
    )


def test_continue_research_reads_context_endpoint(monkeypatch, settings):
    """nowing_continue_research reads the research-thread context endpoint and
    renders BOTH the recalled memories and the thread's prior citations."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_continue_research",
                {"research_thread_id": 9, "query": "pricing", "top_k": 3},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "Competitor X" in str(result)  # memory rendered
    assert "https://example.com/pricing" in str(result)  # citation rendered
    assert any(
        call[0] == "GET" and "/research-threads/9/context" in call[1]
        for call in _client.calls
    )


def test_continue_research_missing_thread_surfaces_not_found(monkeypatch, settings):
    """A backend 404 on the context endpoint becomes a clear 'not found' error."""

    class NotFoundClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if method == "GET" and path.endswith("/context"):
                raise ToolError("Research thread not found")
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", NotFoundClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        with pytest.raises(Exception) as exc:
            asyncio.run(
                mcp.call_tool(
                    "nowing_continue_research",
                    {"research_thread_id": 999999},
                )
            )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "not found" in str(exc.value).lower()


def test_disabled_memory_tool_is_hidden(monkeypatch, settings):
    """A workspace that disables nowing_remember omits it from tools/list."""

    class DisabledRememberClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            self.calls.append((method, path, kwargs))
            if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
                return [
                    {"name": "nowing_list_workspaces", "enabled": True},
                    {"name": "nowing_select_workspace", "enabled": True},
                    {"name": "nowing_remember", "enabled": False},
                ]
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", DisabledRememberClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        tools = asyncio.run(mcp.list_tools())
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    names = {tool.name for tool in tools}
    assert "nowing_remember" not in names
