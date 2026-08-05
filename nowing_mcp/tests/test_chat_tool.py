"""Tests for the ``nowing_chat`` MCP tool (Slice 4, SSE buffered)."""

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

_FAKE_TOOLS = [
    {"name": "nowing_list_workspaces", "enabled": True},
    {"name": "nowing_select_workspace", "enabled": True},
    {"name": "nowing_chat", "enabled": True},
]


class FakeNowingClient:
    """Records calls and serves canned workspace/tool/chat responses."""

    def __init__(
        self, *, api_base: str, timeout: float, fallback_api_key: str | None
    ) -> None:
        self.api_base = api_base
        self.timeout = timeout
        self.fallback_api_key = fallback_api_key
        self.calls: list[tuple[str, str, dict | None]] = []
        self.sse_events: list[dict | str] | None = None
        self.busy_then_ok = 0

    async def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/workspaces"):
            return [{"id": 1, "name": "Test"}]
        if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
            return _FAKE_TOOLS
        if (method, path) == ("POST", "/threads"):
            return {"id": 42}
        return []

    async def stream_sse(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        events = self.sse_events or [
            {"type": "start", "messageId": "m1"},
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "Hello "},
            {"type": "text-delta", "id": "t1", "delta": "world."},
            {"type": "text-end", "id": "t1"},
            {"type": "data-turn-info", "data": {"chat_turn_id": "turn-1"}},
            {"type": "finish"},
            "[DONE]",
        ]
        for payload in events:
            if isinstance(payload, str):
                yield SimpleNamespace(data=payload)
            else:
                import json

                yield SimpleNamespace(data=json.dumps(payload))


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


def _build(monkeypatch, settings):
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    return mcp, client


def test_selfcheck_includes_chat_tool():
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_chat" in EXPECTED_TOOLS


def test_chat_tool_appears_in_manifest(settings):
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    assert "nowing_chat" in {t.name for t in tools}


def test_chat_buffers_sse_into_answer(monkeypatch, settings):
    """Tool returns the concatenated text-delta text, not raw SSE events."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_chat",
                {
                    "user_query": "Summarize RAG",
                    "chat_id": 5,
                    "mode": "quality",
                },
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "Hello world." in text
    assert "[DONE]" not in text
    assert "text-delta" not in text
    assert "turn-1" in text
    assert any(
        call
        == (
            "POST",
            "/new_chat",
            {
                "json": {
                    "chat_id": 5,
                    "workspace_id": 1,
                    "user_query": "Summarize RAG",
                    "mode": "quality",
                }
            },
        )
        for call in client.calls
    )


def test_chat_creates_thread_when_no_chat_id(monkeypatch, settings):
    """Omitting chat_id creates a thread first, then asks on it."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        result = asyncio.run(
            mcp.call_tool("nowing_chat", {"user_query": "Hello there"})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "Hello world." in text
    thread_call = next(c for c in client.calls if c[0] == "POST" and c[1] == "/threads")
    assert thread_call[2]["json"]["workspace_id"] == 1
    assert any(
        c[0] == "POST" and c[1] == "/new_chat" and c[2]["json"]["chat_id"] == 42
        for c in client.calls
    )


def test_chat_mode_none_omits_key(monkeypatch, settings):
    """When mode is None, the request body must not contain a mode key."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        asyncio.run(mcp.call_tool("nowing_chat", {"user_query": "Hi", "chat_id": 5}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    new_chat_calls = [c for c in client.calls if c[1] == "/new_chat"]
    assert new_chat_calls
    assert "mode" not in new_chat_calls[0][2]["json"]


def test_chat_retries_on_thread_busy(monkeypatch, settings):
    """409 THREAD_BUSY during stream raises ThreadBusyError handled with retry."""
    from mcp_server.core.errors import ThreadBusyError

    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)

    original = FakeNowingClient.stream_sse

    async def flaky_stream(self, method: str, path: str, **kwargs):
        if (method, path) == ("POST", "/new_chat") and not getattr(
            self, "_retried", False
        ):
            self._retried = True
            raise ThreadBusyError("THREAD_BUSY", "Thread is busy")
        async for ev in original(self, method, path, **kwargs):
            yield ev

    monkeypatch.setattr(FakeNowingClient, "stream_sse", flaky_stream)

    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        result = asyncio.run(
            mcp.call_tool("nowing_chat", {"user_query": "Hi", "chat_id": 5})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "Hello world." in str(result)


def test_chat_rejects_empty_query(monkeypatch, settings):
    """Empty/whitespace user_query fails validation before any API call."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        with pytest.raises(Exception) as exc:
            asyncio.run(mcp.call_tool("nowing_chat", {"user_query": "   "}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "empty" in str(exc.value).lower()
    assert not any(c[1] == "/new_chat" for c in client.calls)


def test_chat_skips_non_json_sse_and_handles_empty(monkeypatch, settings):
    """Non-JSON SSE lines are skipped; a stream with no text returns a clear message."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    client.sse_events = ["bogus-not-json", "[DONE]"]
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        result = asyncio.run(
            mcp.call_tool("nowing_chat", {"user_query": "Hi", "chat_id": 5})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "No content" in str(result)


def test_chat_json_format_returns_chat_id_and_text(monkeypatch, settings):
    """response_format=json returns chat_id + text in JSON."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)
    mcp, client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_chat",
                {"user_query": "Hi", "chat_id": 5, "response_format": "json"},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    import json as _json

    payload = _json.loads(result[0].text)
    assert payload["chat_id"] == 5
    assert "Hello world." in payload["text"]
