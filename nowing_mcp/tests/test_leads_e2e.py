"""Story 42.4 — nowing_mcp lead tools (wire-level e2e).

Khác với unit suite (FakeNowingClient ghi nhận call): suite này chạy
``mcp.call_tool`` thật → ``NowingClient`` THẬT (auth header, URL build,
params serialization, JSON parse, ``_explain_failure`` error mapping) —
chỉ stub tầng transport cuối bằng ``httpx.MockTransport`` trả response
đúng shape serializer backend thật (``BatchLeadIngestResponse``,
``LeadListResponse``, ``WorkspaceBalanceRead``).

Không chạy được cross-package e2e (backend app không import được trong
mcp venv — thiếu fastapi); backend-side coverage nằm ở
``tests/integration/lead_batch/`` bên nowing_backend.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace

import httpx
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

_API_KEY = "nw_pat_e2e_wire"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        base_url="http://testserver",
        api_key=_API_KEY,
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace="Test",
        host="127.0.0.1",
        port=8080,
    )


def _call(mcp, name: str, args: dict):
    token = mcp_request_ctx.set(SimpleNamespace())
    identity_token = identity.bind_api_key(_API_KEY)
    try:
        return asyncio.run(mcp.call_tool(name, args))
    finally:
        identity.unbind_api_key(identity_token)
        mcp_request_ctx.reset(token)


def _swap_transport(client, handler):
    """Giữ NowingClient thật, chỉ đổi httpx layer sang MockTransport."""
    client._http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=client._api_base,
        headers={"Accept": "application/json"},
    )
    return client


_LEAD_TOOL_NAMES = [
    "nowing_ingest_leads",
    "nowing_create_leads_table",
    "nowing_list_leads",
    "nowing_get_credits_balance",
]


def _resolve_shim(request: httpx.Request) -> httpx.Response | None:
    """Trả lời 2 endpoint mà ``context.resolve(workspace)`` gọi trước khi
    vào endpoint của tool — shape giống backend thật (list workspaces +
    manifest enabled-tools)."""
    if request.method == "GET" and request.url.path == "/api/v1/workspaces":
        return httpx.Response(200, json=[{"id": 1, "name": "Test"}])
    if request.method == "GET" and request.url.path.endswith("/mcp-tools"):
        return httpx.Response(
            200,
            json=[{"name": n, "enabled": True} for n in _LEAD_TOOL_NAMES],
        )
    return None


def test_e2e_ingest_leads_full_wire(settings):
    """call_tool → real client → transport: đúng method/path/auth/json body,
    response passthrough đúng BatchLeadIngestResponse shape."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        shim = _resolve_shim(request)
        if shim is not None:
            return shim
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        seen["idem"] = request.headers.get("idempotency-key")
        return httpx.Response(
            200,
            json={
                "ingested_count": 1,
                "skipped_blacklisted_count": 0,
                "failed_count": 0,
                "execution_time_ms": 7,
                "lead_ids": ["11111111-1111-1111-1111-111111111111"],
                "lead_id_mapping": {"0": "11111111-1111-1111-1111-111111111111"},
            },
        )

    mcp, client = build_server(settings)
    _swap_transport(client, handler)

    result = _call(
        mcp,
        "nowing_ingest_leads",
        {
            "workspace": "1",
            "leads": [{"company": "Acme", "email": "a@acme.io"}],
            "idempotency_key": "idem-e2e-1",
        },
    )

    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v1/workspaces/1/leads/batch-ingest"
    assert seen["auth"] == f"Bearer {_API_KEY}"
    assert seen["body"]["leads"] == [{"company": "Acme", "email": "a@acme.io"}]
    assert seen["idem"] == "idem-e2e-1"
    assert '"ingested_count": 1' in str(result)


def test_e2e_list_leads_clamps_limit_on_wire(settings):
    """limit=999 → wire nhận limit=200; markdown render từ LeadRead shape."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        shim = _resolve_shim(request)
        if shim is not None:
            return shim
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "company": "Acme",
                        "status": "new",
                        "composite_score": 80,
                        "source": "manual",
                    }
                ],
                "total": 1,
                "limit": 200,
                "offset": 0,
            },
        )

    mcp, client = build_server(settings)
    _swap_transport(client, handler)

    result = _call(
        mcp, "nowing_list_leads", {"workspace": "1", "limit": 999, "offset": -5}
    )

    assert seen["params"]["limit"] == "200"
    assert seen["params"]["offset"] == "0"
    text = str(result)
    assert "Acme" in text and "80" in text


def test_e2e_credits_balance_404_maps_no_wallet(settings):
    """404 thật từ backend → ``_explain_failure`` → ToolError('not found')
    → tool trả ``{"status":"failed","reason":"no_wallet"}`` (không raise)."""

    def handler(request: httpx.Request) -> httpx.Response:
        shim = _resolve_shim(request)
        if shim is not None:
            return shim
        return httpx.Response(404, json={"detail": "Workspace not found"})

    mcp, client = build_server(settings)
    _swap_transport(client, handler)

    result = _call(mcp, "nowing_get_credits_balance", {"workspace": "1"})

    text = str(result)
    assert "no_wallet" in text
    assert '"failed"' in text


def test_e2e_no_api_key_raises_tool_error():
    """Không Authorization context VÀ không fallback env key → real
    ``_auth_headers`` raise ToolError('No Nowing API key') trước khi chạm
    transport."""
    settings = Settings(
        base_url="http://testserver",
        api_key=None,
        api_prefix="/api/v1",
        timeout=5.0,
        default_workspace="Test",
        host="127.0.0.1",
        port=8080,
    )
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    mcp, client = build_server(settings)
    _swap_transport(client, handler)

    token = mcp_request_ctx.set(SimpleNamespace())
    try:
        # call_tool fail-closed wrap thành fastmcp ToolError — assert message.
        with pytest.raises(Exception, match="No Nowing API key"):
            asyncio.run(mcp.call_tool("nowing_get_credits_balance", {"workspace": "1"}))
    finally:
        mcp_request_ctx.reset(token)

    assert calls == []
