"""Tests for MCP image-generation tool (Slice 1 MCP expansion)."""

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
    """Records calls and serves canned workspace/tool/generation responses."""

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
                {"name": "nowing_image_generate", "enabled": True},
            ]
        if (method, path) == ("POST", "/image-generations"):
            return {
                "id": 99,
                "prompt": kwargs.get("json", {}).get("prompt", ""),
                "model": "gpt-image-1",
                "size": "1024x1024",
                "n": 1,
                "created_at": "2026-08-05T00:00:00Z",
                "error_message": None,
                "response_data": {
                    "data": [
                        {"url": "https://cdn.nowing.test/img/99/0.png"},
                    ]
                },
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


def test_selfcheck_includes_image_generate():
    """Offline selfcheck catalog must include nowing_image_generate."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_image_generate" in EXPECTED_TOOLS


def test_image_generate_appears_in_manifest(settings):
    """nowing_image_generate must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_image_generate" in names


def test_image_generate_calls_endpoint(monkeypatch, settings):
    """nowing_image_generate calls POST /image-generations and renders URLs."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_image_generate",
                {
                    "prompt": "A cat astronaut",
                    "n": 1,
                    "size": "1024x1024",
                    "quality": "hd",
                    "model": "gpt-image-1",
                },
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "id 99" in text
    assert "https://cdn.nowing.test/img/99/0.png" in text
    assert any(
        call[0] == "POST" and call[1] == "/image-generations" for call in _client.calls
    )


def test_image_generate_renders_error_message(monkeypatch, settings):
    """A failed provider call surfaces its error_message instead of URLs."""

    class FailingClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            self.calls.append((method, path, kwargs))
            if (method, path) == ("POST", "/image-generations"):
                return {
                    "id": 100,
                    "prompt": kwargs.get("json", {}).get("prompt", ""),
                    "model": "gpt-image-1",
                    "size": "1024x1024",
                    "created_at": "2026-08-05T00:00:00Z",
                    "error_message": "provider rejected the prompt",
                    "response_data": None,
                }
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", FailingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool("nowing_image_generate", {"prompt": "banned"})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "provider rejected the prompt" in text
    assert "no image urls" not in text


def test_image_generate_out_of_credit_hint(monkeypatch, settings):
    """A backend 402 surfaces the out-of-credits hint from the client."""

    class OutOfCreditClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            self.calls.append((method, path, kwargs))
            if (method, path) == ("POST", "/image-generations"):
                raise ToolError("The workspace is out of credits for this operation.")
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", OutOfCreditClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        with pytest.raises(Exception) as exc:
            asyncio.run(mcp.call_tool("nowing_image_generate", {"prompt": "a rocket"}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    assert "out of credits" in str(exc.value).lower()


def test_image_generate_is_write_hint(monkeypatch, settings):
    """The generate tool must advertise non-readOnly so clients gate on credits."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    tool = next(t for t in tools if t.name == "nowing_image_generate")
    annotations = tool.annotations
    assert annotations is not None
    assert annotations.readOnlyHint is False
