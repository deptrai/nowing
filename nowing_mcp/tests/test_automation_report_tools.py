"""Tests for MCP automation list + report list/export tools (Slice 3 read-only)."""

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
    {"name": "nowing_automation_list", "enabled": True},
    {"name": "nowing_automation_run", "enabled": True},
    {"name": "nowing_report_list", "enabled": True},
    {"name": "nowing_report_export", "enabled": True},
]


class FakeNowingClient:
    """Records calls and serves canned workspace/tool/automation/report responses."""

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
            return _FAKE_TOOLS
        if (method, path) == ("GET", "/automations"):
            return {
                "total": 2,
                "items": [
                    {
                        "id": 11,
                        "workspace_id": 1,
                        "name": "Daily digest",
                        "description": "Sends a digest every morning.",
                        "status": "active",
                        "version": 3,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-02T00:00:00Z",
                    },
                    {
                        "id": 12,
                        "workspace_id": 1,
                        "name": "Price alert",
                        "description": None,
                        "status": "paused",
                        "version": 1,
                        "created_at": "2026-01-03T00:00:00Z",
                        "updated_at": "2026-01-03T00:00:00Z",
                    },
                ],
            }
        if (method, path) == ("GET", "/reports"):
            return [
                {
                    "id": 5,
                    "title": "Q1 market review",
                    "report_style": "professional",
                    "content_type": "markdown",
                    "created_at": "2026-02-01T00:00:00Z",
                },
                {
                    "id": 6,
                    "title": "Competitor deep dive",
                    "report_style": None,
                    "content_type": "markdown",
                    "created_at": "2026-02-02T00:00:00Z",
                },
            ]
        if method == "POST" and path.startswith("/automations/"):
            return {
                "id": 999,
                "automation_id": 11,
                "trigger_id": None,
                "status": "pending",
                "started_at": None,
                "finished_at": None,
                "created_at": "2026-03-01T00:00:00Z",
            }
        return []

    async def request_bytes(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/reports/5/export"):
            payload = kwargs.get("params", {}).get("format", "pdf")
            if payload == "plain":
                return b"# Exported plain report", "text/plain; charset=utf-8"
            return b"%PDF-1.4 fake-pdf-bytes", "application/pdf"
        return b"", None


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


def test_selfcheck_includes_slice3_tools():
    """Offline selfcheck catalog must include the three Slice 3 tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_automation_list" in EXPECTED_TOOLS
    assert "nowing_report_list" in EXPECTED_TOOLS
    assert "nowing_report_export" in EXPECTED_TOOLS


def test_slice3_tools_appear_in_manifest(settings):
    """All three Slice 3 tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_automation_list" in names
    assert "nowing_report_list" in names
    assert "nowing_report_export" in names


def test_automation_list_calls_endpoint(monkeypatch, settings):
    """nowing_automation_list calls GET /automations with workspace + pagination."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool("nowing_automation_list", {"limit": 10, "offset": 5})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "Daily digest" in text
    assert "active" in text
    assert "Price alert" in text
    assert "paused" in text
    assert any(
        call
        == (
            "GET",
            "/automations",
            {"params": {"workspace_id": 1, "limit": 10, "offset": 5}},
        )
        for call in _client.calls
    )


def test_report_list_calls_endpoint(monkeypatch, settings):
    """nowing_report_list calls GET /reports with workspace scope."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(mcp.call_tool("nowing_report_list", {"limit": 10}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "Q1 market review" in text
    assert "Competitor deep dive" in text
    assert any(
        call == ("GET", "/reports", {"params": {"workspace_id": 1, "limit": 10}})
        for call in _client.calls
    )


def test_report_export_text_format_returns_text(monkeypatch, settings):
    """plain export returns the decoded text directly."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool("nowing_report_export", {"report_id": 5, "format": "plain"})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "Exported plain report" in text
    assert any(
        call == ("GET", "/reports/5/export", {"params": {"format": "plain"}})
        for call in _client.calls
    )


def test_report_export_binary_format_returns_base64(monkeypatch, settings):
    """pdf export returns a base64-encoded payload with a decode hint."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(mcp.call_tool("nowing_report_export", {"report_id": 5}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    import base64
    import re

    text = str(result)
    assert "base64" in text.lower()
    assert "pdf" in text
    assert any(
        call == ("GET", "/reports/5/export", {"params": {"format": "pdf"}})
        for call in _client.calls
    )

    match = re.search(r"JVBER[A-Za-z0-9+/=]+", text)
    assert match, "expected a base64-encoded PDF payload in the output"
    assert b"%PDF-1.4 fake-pdf-bytes" in base64.b64decode(match.group(0))


def test_slice3_tools_are_read_only(monkeypatch, settings):
    """All three Slice 3 tools must be read-only (no destructive hint)."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    for name in (
        "nowing_automation_list",
        "nowing_report_list",
        "nowing_report_export",
    ):
        tool = next(t for t in tools if t.name == name)
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.readOnlyHint is True
        assert annotations.destructiveHint is False
        assert annotations.idempotentHint is True


def test_selfcheck_includes_run_tool():
    """Offline selfcheck catalog must include nowing_automation_run."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_automation_run" in EXPECTED_TOOLS


def test_run_tool_appears_in_manifest(settings):
    """nowing_automation_run must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_automation_run" in names


def test_automation_run_calls_endpoint(monkeypatch, settings):
    """nowing_automation_run POSTs /automations/{id}/run and returns run id/status."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool("nowing_automation_run", {"automation_id": 11})
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = str(result)
    assert "#999" in text
    assert "pending" in text
    assert any(
        call
        == (
            "POST",
            "/automations/11/run",
            {"json": {"workspace_id": 1}},
        )
        for call in _client.calls
    )


def test_automation_run_json_format(monkeypatch, settings):
    """response_format=json returns exactly {run_id, status}."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_automation_run",
                {"automation_id": 11, "response_format": "json"},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    import json

    payload = json.loads(result[0].text)
    assert payload == {"run_id": 999, "status": "pending"}


def test_automation_run_errors_are_readable(monkeypatch, settings):
    """Backend rejections surface as readable messages, not raw exceptions."""
    from mcp_server.core.errors import ToolError

    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    class FailingClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if method == "POST" and path.startswith("/automations/"):
                raise ToolError(
                    "Access denied — the token lacks permission, or API access "
                    "is disabled for this workspace. (server said: forbidden)"
                )
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", FailingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        with pytest.raises(Exception) as exc:
            asyncio.run(mcp.call_tool("nowing_automation_run", {"automation_id": 11}))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    message = str(exc.value).lower()
    assert "automation" in message
    assert "permission" in message
