"""End-to-end envelope contract tests — Story 42.2.

Exercises the real agent boundary: ``StructuredTool.ainvoke`` →
``_handle_medirus_*`` → ``_execute_medirus_tool`` → ``_format_result`` →
JSON string the agent receives. Only the external ``MedirusMcpClient``
(the Medirus daemon) is mocked — everything else is production code.

ACs covered (epics.md Story 42.2):
- Unified ``{status, reason, recovery_hint, items}`` contract for every
  Medirus tool result (success / empty_result / failed / degraded /
  preview).
- Failures carry a recovery_hint (seeded map + generic fallback);
  Medirus ``suggestedAction`` forwarded marked ``untrusted``.
- dryRun stubs never look like success.
- Early argument validation fails as an envelope (no "Error: ..." string).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.chat.multi_agent_chat.shared.tools.mcp.medirus_gateway import (
    create_medirus_meta_tools,
)
from app.proprietary.platforms.medirus.mcp_client import MedirusMcpError

GATEWAY = "app.agents.chat.multi_agent_chat.shared.tools.mcp.medirus_gateway"
ENVELOPE_KEYS = {"status", "reason", "recovery_hint", "items"}


def _tools():
    return {
        t.name: t
        for t in create_medirus_meta_tools(
            connector_id=10,
            connector_name="Medirus",
            server_config={"url": "http://test:3001/mcp"},
        )
    }


def _mock_client(call_tool):
    mock_client = AsyncMock()
    mock_client.call_tool = call_tool
    mock_client.__aenter__.return_value = mock_client
    return patch(
        f"{GATEWAY}.MedirusMcpClient", autospec=True, return_value=mock_client
    )


@pytest.mark.asyncio
async def test_e2e_success_envelope_contract():
    """Agent receives the 4-key envelope with status=success on happy path."""
    tool = _tools()["medirus_search"]
    call_tool = AsyncMock(
        return_value={
            "success": True,
            "data": [{"id": "1", "text": "hello twitter"}],
            "summary": "1 tweet",
            "meta": {"cost_micros": 10},
        }
    )
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"query": "ai agent", "platform": "twitter"})

    env = json.loads(raw)
    assert set(env.keys()) == ENVELOPE_KEYS
    assert env["status"] == "success"
    assert env["reason"] is None
    assert env["recovery_hint"] is None
    assert env["items"] == [{"id": "1", "text": "hello twitter"}]


@pytest.mark.asyncio
async def test_e2e_exception_maps_to_failed_with_hint():
    """MedirusMcpError 4010 → failed envelope + seeded hint + untrusted action."""
    tool = _tools()["medirus_search"]
    call_tool = AsyncMock(
        side_effect=MedirusMcpError(
            "auth expired",
            code="MEDIRUS_4010",
            suggested_action="set c_user/xs",
        )
    )
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"query": "ai agent", "platform": "twitter"})

    env = json.loads(raw)
    assert set(env.keys()) == ENVELOPE_KEYS
    assert env["status"] == "failed"
    assert env["reason"] == "auth expired"
    assert env["recovery_hint"]
    assert "authCookie" in env["recovery_hint"] or "Medirus/.env" in env["recovery_hint"]
    assert "(untrusted suggestedAction: set c_user/xs)" in env["recovery_hint"]
    assert env["items"] == []


@pytest.mark.asyncio
async def test_e2e_in_band_failure_maps_to_failed():
    """In-band {success: false} dict → failed envelope (not silent empty)."""
    tool = _tools()["medirus_scrape"]
    call_tool = AsyncMock(
        return_value={
            "success": False,
            "error": {
                "message": "bot challenge",
                "code": "MEDIRUS_4030",
                "suggestedAction": "residential proxy",
            },
        }
    )
    with _mock_client(call_tool):
        raw = await tool.ainvoke(
            {
                "platform": "facebook",
                "action": "marketplace",
                "query": "xe máy",
            }
        )

    env = json.loads(raw)
    assert env["status"] == "failed"
    assert env["reason"] == "bot challenge"
    assert "PROXY" in env["recovery_hint"]
    assert "(untrusted suggestedAction: residential proxy)" in env["recovery_hint"]


@pytest.mark.asyncio
async def test_e2e_empty_result_status():
    """Empty channel ≠ failed channel: empty data → empty_result."""
    tool = _tools()["medirus_search"]
    call_tool = AsyncMock(return_value={"success": True, "data": []})
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"query": "nothing here", "platform": "twitter"})

    env = json.loads(raw)
    assert env["status"] == "empty_result"
    assert env["items"] == []


@pytest.mark.asyncio
async def test_e2e_degraded_status_passthrough():
    """Medirus meta.degraded surfaces as status=degraded + reason."""
    tool = _tools()["medirus_crawl_post"]
    call_tool = AsyncMock(
        return_value={
            "success": True,
            "data": [{"id": "post_1"}],
            "meta": {"degraded": True, "degradation_reason": "comments truncated"},
        }
    )
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"url": "https://facebook.com/post/1"})

    env = json.loads(raw)
    assert env["status"] == "degraded"
    assert env["reason"] == "comments truncated"
    assert env["items"] == [{"id": "post_1"}]


@pytest.mark.asyncio
async def test_e2e_dry_run_stub_is_preview_not_success():
    """Daemon dryRun echo → preview: stub must never look like success."""
    tool = _tools()["medirus_search"]
    call_tool = AsyncMock(
        return_value={"success": True, "preview": True, "data": [{"id": "stub"}]}
    )
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"query": "ai agent", "platform": "twitter"})

    env = json.loads(raw)
    assert env["status"] == "preview"
    assert env["items"] == [{"id": "stub"}]


@pytest.mark.asyncio
async def test_e2e_early_validation_failed_envelope_no_hint():
    """Missing url/post_id → failed envelope with recovery_hint=None."""
    tool = _tools()["medirus_crawl_post"]
    call_tool = AsyncMock()  # must not be called
    with _mock_client(call_tool):
        raw = await tool.ainvoke({})

    env = json.loads(raw)
    assert env["status"] == "failed"
    assert "url or post_id" in env["reason"]
    assert env["recovery_hint"] is None
    call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_e2e_generic_exception_generic_hint():
    """Uncoded exception → failed envelope + generic hint."""
    tool = _tools()["medirus_search"]
    call_tool = AsyncMock(side_effect=RuntimeError("socket boom"))
    with _mock_client(call_tool):
        raw = await tool.ainvoke({"query": "ai", "platform": "twitter"})

    env = json.loads(raw)
    assert env["status"] == "failed"
    assert "socket boom" in env["reason"]
    assert env["recovery_hint"] == "generic: check logs, retry"
