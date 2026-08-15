"""Tests for MCP contact-enrichment tools (Story 21.3, Task 7)."""

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
    {"name": "nowing_enrich_lead", "enabled": True},
    {"name": "nowing_list_contacts", "enabled": True},
]


class FakeNowingClient:
    """Records calls and serves canned workspace/tool/enrichment responses."""

    calls: list[tuple[str, str, dict | None]] = []

    def __init__(
        self, *, api_base: str, timeout: float, fallback_api_key: str | None
    ) -> None:
        self.api_base = api_base
        self.timeout = timeout
        self.fallback_api_key = fallback_api_key

    async def request(self, method: str, path: str, **kwargs):
        type(self).calls.append((method, path, kwargs))
        if (method, path) == ("GET", "/workspaces"):
            return [{"id": 1, "name": "Test"}]
        if (method, path) == ("GET", "/workspaces/1/mcp-tools"):
            return _FAKE_TOOLS
        if (method, path) == (
            "POST",
            "/workspaces/1/leads/lead-1/enrich",
        ):
            return {
                "enrichment_request_id": "req-1",
                "lead_id": "lead-1",
                "contact_count": 2,
                "cost_micros": 100,
                "degraded": False,
                "degradation_reasons": [],
                "verified_contact_ids": ["c1", "c2"],
            }
        if (method, path) == ("GET", "/workspaces/1/leads/lead-1/contacts"):
            return [
                {
                    "id": "c1",
                    "name": "Alice Nguyen",
                    "title": "CTO",
                    "email": "alice@fpt.com",
                    "phone": "+84123456789",
                    "verification_status": "verified",
                    "confidence": 0.95,
                    "source_provider": "cleanlist",
                }
            ]
        return []

    async def request_bytes(self, method: str, path: str, **kwargs):
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


def test_selfcheck_includes_enrichment_tools():
    """Offline selfcheck catalog must include the enrichment tools."""
    from mcp_server.selfcheck import EXPECTED_TOOLS

    assert "nowing_enrich_lead" in EXPECTED_TOOLS
    assert "nowing_list_contacts" in EXPECTED_TOOLS


def test_enrichment_tools_appear_in_manifest(settings):
    """Both enrichment tools must appear in the offline tool manifest."""
    mcp, _client = build_server(settings)
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert "nowing_enrich_lead" in names
    assert "nowing_list_contacts" in names


def test_enrich_lead_calls_backend(monkeypatch, settings):
    """nowing_enrich_lead POSTs to the enrich route and renders the output."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_enrich_lead",
                {"lead_id": "lead-1", "requested_count": 2},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = result[0].text
    assert "Enrichment request req-1" in text
    assert "Found 2 verified contacts" in text
    assert any(
        call == ("POST", "/workspaces/1/leads/lead-1/enrich", {"json": {"requested_count": 2}})
        for call in FakeNowingClient.calls
    )


def test_list_verified_contacts_renders_table(monkeypatch, settings):
    """nowing_list_contacts GETs contacts with pagination and renders a table."""
    monkeypatch.setattr("mcp_server.server.NowingClient", FakeNowingClient)

    mcp, _client = build_server(settings)
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key("nw_pat_test")

    try:
        result = asyncio.run(
            mcp.call_tool(
                "nowing_list_contacts",
                {"lead_id": "lead-1", "limit": 20, "offset": 0},
            )
        )
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)

    text = result[0].text
    assert "Alice Nguyen" in text
    assert "alice@fpt.com" in text
    assert "cleanlist" in text
    assert any(
        call == (
            "GET",
            "/workspaces/1/leads/lead-1/contacts",
            {"params": {"limit": 20, "offset": 0}},
        )
        for call in FakeNowingClient.calls
    )