"""Tests for MCP lead workspace tools (Story 42.4)."""

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
from mcp_server.core.errors import ToolError  # noqa: E402
from mcp_server.server import build_server  # noqa: E402

_FAKE_TOOLS = [
    {"name": "nowing_list_workspaces", "enabled": True},
    {"name": "nowing_select_workspace", "enabled": True},
    {"name": "nowing_ingest_leads", "enabled": True},
    {"name": "nowing_create_leads_table", "enabled": True},
    {"name": "nowing_list_leads", "enabled": True},
    {"name": "nowing_get_credits_balance", "enabled": True},
]


class FakeNowingClient:
    """Records calls and serves canned workspace/tool/lead responses."""

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
        if (method, path) == ("POST", "/workspaces/1/leads/batch-ingest"):
            leads = kwargs.get("json", {}).get("leads", [])
            return {
                "ingested_count": len(leads),
                "skipped_blacklisted_count": 0,
                "failed_count": 0,
                "execution_time_ms": 5,
                "lead_ids": [],
                "lead_id_mapping": {},
            }
        if (method, path) == ("POST", "/workspaces/1/tables"):
            return {"id": "abc-123", "name": kwargs["json"]["name"], "icon": "table"}
        if (method, path) == ("GET", "/workspaces/1/leads"):
            params = kwargs.get("params", {})
            return {
                "items": [
                    {
                        "company": "Acme",
                        "status": "new",
                        "composite_score": 80,
                        "source": "manual",
                    }
                ],
                "total": 1,
                "limit": params.get("limit"),
                "offset": params.get("offset"),
            }
        if (method, path) == ("GET", "/workspaces/1/credits/balance"):
            return {"workspace_id": 1, "credit_micros_balance": 1500000}
        return []

    async def request_bytes(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
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


def _call(mcp, name: str, args: dict):
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")
    try:
        return asyncio.run(mcp.call_tool(name, args))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)


def test_leads_tools_in_selfcheck():
    """Offline selfcheck catalog must include the four lead workspace tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_ingest_leads" in EXPECTED_TOOLS
    assert "nowing_create_leads_table" in EXPECTED_TOOLS
    assert "nowing_list_leads" in EXPECTED_TOOLS
    assert "nowing_get_credits_balance" in EXPECTED_TOOLS


def test_leads_tools_appear_in_manifest(settings):
    """All four lead workspace tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "nowing_ingest_leads" in names
    assert "nowing_create_leads_table" in names
    assert "nowing_list_leads" in names
    assert "nowing_get_credits_balance" in names


def test_ingest_leads_posts_batch(monkeypatch, settings):
    """nowing_ingest_leads POSTs the leads payload to the batch-ingest endpoint."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    leads = [{"company": "Acme", "email": "a@acme.io"}]
    result = _call(mcp, "nowing_ingest_leads", {"leads": leads})

    assert '"ingested_count": 1' in str(result)
    assert any(
        call[0] == "POST" and call[1] == "/workspaces/1/leads/batch-ingest"
        and call[2]["json"] == {"leads": leads}
        for call in _client.calls
    )


def test_ingest_leads_forwards_idempotency_key(monkeypatch, settings):
    """An idempotency_key argument is forwarded as the Idempotency-Key header."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    _call(
        mcp,
        "nowing_ingest_leads",
        {"leads": [{"company": "Acme"}], "idempotency_key": "k1"},
    )

    call = next(c for c in _client.calls if c[1] == "/workspaces/1/leads/batch-ingest")
    assert call[2]["headers"] == {"Idempotency-Key": "k1"}


def test_ingest_leads_no_header_without_key(monkeypatch, settings):
    """Without an idempotency key, no headers are sent."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    _call(mcp, "nowing_ingest_leads", {"leads": [{"company": "Acme"}]})

    call = next(c for c in _client.calls if c[1] == "/workspaces/1/leads/batch-ingest")
    assert "headers" not in call[2] or not call[2]["headers"]


def test_ingest_leads_422_raises_tool_error(monkeypatch, settings):
    """A 422 reject-all from the backend surfaces as a ToolError (real client behavior)."""

    class RejectingClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if (method, path) == ("POST", "/workspaces/1/leads/batch-ingest"):
                self.calls.append((method, path, kwargs))
                raise ToolError("Nowing returned 422: batch rejected (invalid email)")
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", RejectingClient)

    mcp, _client = build_server(settings)
    with pytest.raises(Exception) as exc:
        _call(mcp, "nowing_ingest_leads", {"leads": [{"company": "A"}, {"company": "B"}]})

    assert "422" in str(exc.value) or "rejected" in str(exc.value).lower()


def test_ingest_leads_reports_skipped_and_failed(monkeypatch, settings):
    """Skipped/failed counts from the batch response are reported."""

    class PartialClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if (method, path) == ("POST", "/workspaces/1/leads/batch-ingest"):
                self.calls.append((method, path, kwargs))
                return {
                    "ingested_count": 1,
                    "skipped_blacklisted_count": 1,
                    "failed_count": 0,
                    "execution_time_ms": 5,
                    "lead_ids": [],
                    "lead_id_mapping": {},
                }
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", PartialClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_ingest_leads", {"leads": [{"company": "A"}, {"company": "B"}]})

    text = str(result)
    assert '"ingested_count": 1' in text
    assert '"skipped_blacklisted_count": 1' in text


def test_create_leads_table_posts_table(monkeypatch, settings):
    """nowing_create_leads_table POSTs {name, icon='table'} to /tables."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_create_leads_table", {"name": "Hot leads"})

    text = str(result)
    assert "Hot leads" in text
    assert any(
        call
        == (
            "POST",
            "/workspaces/1/tables",
            {"json": {"name": "Hot leads", "icon": "table"}},
        )
        for call in _client.calls
    )


def test_list_leads_clamps_limit_and_offset(monkeypatch, settings):
    """limit is clamped to [1, 200] with default 50; offset is clamped to >= 0."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    _call(mcp, "nowing_list_leads", {"limit": 500, "offset": -3})
    _call(mcp, "nowing_list_leads", {"limit": 0})
    _call(mcp, "nowing_list_leads", {})

    list_calls = [c for c in _client.calls if c[1] == "/workspaces/1/leads"]
    assert list_calls[0][2]["params"] == {"limit": 200, "offset": 0}
    assert list_calls[1][2]["params"] == {"limit": 1, "offset": 0}
    assert list_calls[2][2]["params"] == {"limit": 50, "offset": 0}


def test_list_leads_renders_table(monkeypatch, settings):
    """The listing renders a markdown table with company/status/score/source."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_list_leads", {})

    text = str(result)
    assert "Acme" in text
    assert "new" in text
    assert "80" in text
    assert "manual" in text
    assert "Total: 1" in text


def test_list_leads_empty_renders_no_error(monkeypatch, settings):
    """An empty lead list renders a total line without raising."""

    class EmptyClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if (method, path) == ("GET", "/workspaces/1/leads"):
                self.calls.append((method, path, kwargs))
                return {"items": [], "total": 0, "limit": 50, "offset": 0}
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", EmptyClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_list_leads", {})

    text = str(result)
    assert "No leads" in text
    assert "total: 0" in text.lower()


def test_list_leads_forwards_filters(monkeypatch, settings):
    """client_id and source arguments are forwarded as query params."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    _call(mcp, "nowing_list_leads", {"client_id": "c1", "source": "manual"})

    call = next(c for c in _client.calls if c[1] == "/workspaces/1/leads")
    assert call[2]["params"]["client_id"] == "c1"
    assert call[2]["params"]["source"] == "manual"


def test_create_leads_table_custom_icon(monkeypatch, settings):
    """An optional icon argument overrides the default 'table'."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    _call(mcp, "nowing_create_leads_table", {"name": "T", "icon": "fire"})

    call = next(c for c in _client.calls if c[1] == "/workspaces/1/tables")
    assert call[2]["json"]["icon"] == "fire"


def test_get_credits_balance_returns_balance(monkeypatch, settings):
    """nowing_get_credits_balance calls GET /workspaces/1/credits/balance."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_get_credits_balance", {})

    text = str(result)
    assert "1500000" in text
    assert any(
        call[0] == "GET" and call[1] == "/workspaces/1/credits/balance"
        for call in _client.calls
    )


def test_get_credits_balance_404_maps_to_no_wallet(monkeypatch, settings):
    """A 404 from the balance endpoint returns {status: failed, reason: no_wallet}."""

    class NotFoundClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if (method, path) == ("GET", "/workspaces/1/credits/balance"):
                self.calls.append((method, path, kwargs))
                raise ToolError(
                    "The requested resource was not found. (server said: "
                    "Wallet not found)"
                )
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", NotFoundClient)

    mcp, _client = build_server(settings)
    result = _call(mcp, "nowing_get_credits_balance", {})

    text = str(result)
    assert "failed" in text
    assert "no_wallet" in text


def test_leads_tools_fail_without_api_key(monkeypatch, settings):
    """Without a bound API key the tools raise a readable error."""

    class NoKeyClient(FakeNowingClient):
        async def request(self, method: str, path: str, **kwargs):
            if (method, path) == ("GET", "/workspaces/1/credits/balance"):
                self.calls.append((method, path, kwargs))
                raise ToolError("No Nowing API key configured.")
            return await super().request(method, path, **kwargs)

    monkeypatch.setattr("mcp_server.server.NowingClient", NoKeyClient)

    mcp, _client = build_server(settings)
    with pytest.raises(Exception) as exc:
        _call(mcp, "nowing_get_credits_balance", {})

    assert "api key" in str(exc.value).lower()
