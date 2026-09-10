"""Hermetic integration tests for XActionsMcpClient (Story 26-7).

Uses the shared E2E fake MCP runtime so no network calls are made.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
)
from tests.e2e.fakes import mcp_runtime

pytestmark = pytest.mark.integration

_XACTIONS_MCP_URL = "http://xactions:3001/mcp"
_XACTIONS_API_KEY = "test-xactions-api-key"
_XACTIONS_CONSUMER_ID = "test-consumer"
_XACTIONS_ADMIN_TOKEN = "super-secret-admin-token"


def _make_tool(name: str, description: str, schema: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema=schema,
    )


def _make_text_response(text: str, is_error: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        isError=is_error,
    )


@pytest.fixture
def xactions_mcp_server():
    """Install the fake MCP runtime and register a fake XActions server."""
    active_patches: list[Any] = []
    mcp_runtime.install(active_patches)
    mcp_runtime.reset()

    last_call: dict[str, Any] = {}

    def _list_tools() -> SimpleNamespace:
        return SimpleNamespace(
            tools=[
                _make_tool(
                    "x_facebook_group_posts",
                    "Fetch posts from a Facebook group.",
                    {
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["group_id"],
                    },
                ),
                _make_tool(
                    "x_admin_purge",
                    "Admin-only purge operation.",
                    {
                        "type": "object",
                        "properties": {
                            "target_id": {"type": "string"},
                            "token": {"type": "string"},
                        },
                        "required": ["target_id"],
                    },
                ),
            ]
        )

    def _call_tool(tool_name: str, arguments: dict[str, Any]) -> SimpleNamespace:
        last_call["tool_name"] = tool_name
        last_call["arguments"] = arguments

        if tool_name == "x_facebook_group_posts":
            envelope = {
                "success": True,
                "data": [{"id": "post-1", "message": "hello"}],
                "meta": {"total": 1, "page": 1},
                "summary": {"fetched": 1},
            }
            return _make_text_response(json.dumps(envelope))

        if tool_name == "x_governor_status":
            return _make_text_response(json.dumps({"success": True, "data": {}}))

        if tool_name == "x_admin_purge":
            return _make_text_response(
                json.dumps({"success": True, "data": {"purged": True}})
            )

        if tool_name == "x_rate_limited_tool":
            envelope = {
                "success": False,
                "error": {
                    "message": "Rate limit exceeded",
                    "code": "RATE_LIMITED",
                    "retryAfter": 30,
                    "suggestedAction": "retry",
                },
            }
            return _make_text_response(json.dumps(envelope), is_error=True)

        raise NotImplementedError(f"Unexpected XActions tool call: {tool_name!r}")

    mcp_runtime.register(
        url=_XACTIONS_MCP_URL,
        expected_bearer=_XACTIONS_API_KEY,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )

    yield {"last_call": last_call}

    for p in active_patches:
        p.stop()
    mcp_runtime.reset()


@pytest.fixture
async def xactions_client(xactions_mcp_server):
    """Yield a configured XActionsMcpClient inside a fake transport session."""
    client = XActionsMcpClient(
        url=_XACTIONS_MCP_URL,
        api_key=_XACTIONS_API_KEY,
        consumer_id=_XACTIONS_CONSUMER_ID,
    )
    client.admin_token = _XACTIONS_ADMIN_TOKEN
    async with client as c:
        yield c


class TestHermeticXActionsMcpClient:
    """Hermetic tests for XActions MCP client list/call without network."""

    @pytest.mark.asyncio
    async def test_hermetic_list_tools(self, xactions_client: XActionsMcpClient) -> None:
        """list_tools returns tool names, descriptions, and input schemas."""
        tools = await xactions_client.list_tools()
        names = {tool["name"] for tool in tools}
        assert names == {"x_facebook_group_posts", "x_admin_purge"}

        fb_tool = next(t for t in tools if t["name"] == "x_facebook_group_posts")
        assert fb_tool["description"] == "Fetch posts from a Facebook group."
        assert fb_tool["input_schema"]["required"] == ["group_id"]

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_success(
        self, xactions_client: XActionsMcpClient, xactions_mcp_server: dict[str, Any]
    ) -> None:
        """call_tool parses the 3-layer envelope and returns data, meta, summary."""
        result = await xactions_client.call_tool(
            "x_facebook_group_posts",
            {"group_id": "12345", "limit": 10},
        )

        assert result["success"] is True
        assert result["data"] == [{"id": "post-1", "message": "hello"}]
        assert result["meta"] == {"total": 1, "page": 1}
        assert result["summary"] == {"fetched": 1}

        last_call = xactions_mcp_server["last_call"]
        assert last_call["tool_name"] == "x_facebook_group_posts"
        assert last_call["arguments"]["group_id"] == "12345"

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_structured_error(
        self, xactions_client: XActionsMcpClient
    ) -> None:
        """Structured error envelope raises XActionsMcpError with retry_after."""
        with pytest.raises(XActionsMcpError) as exc_info:
            await xactions_client.call_tool(
                "x_rate_limited_tool",
                {"group_id": "12345"},
            )

        err = exc_info.value
        assert err.message == "Rate limit exceeded"
        assert err.code == "RATE_LIMITED"
        assert err.retry_after == 30
        assert err.suggested_action == "retry"

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_admin_token_injection(
        self, xactions_client: XActionsMcpClient, xactions_mcp_server: dict[str, Any]
    ) -> None:
        """Admin token is injected for x_admin_* tools when token not provided."""
        await xactions_client.call_tool(
            "x_admin_purge",
            {"target_id": "queue-42"},
        )

        last_call = xactions_mcp_server["last_call"]
        assert last_call["tool_name"] == "x_admin_purge"
        assert last_call["arguments"]["target_id"] == "queue-42"
        assert last_call["arguments"]["token"] == _XACTIONS_ADMIN_TOKEN

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_admin_token_preserved_when_explicit(
        self, xactions_client: XActionsMcpClient, xactions_mcp_server: dict[str, Any]
    ) -> None:
        """Caller-provided token is not overwritten by the admin token helper."""
        await xactions_client.call_tool(
            "x_admin_purge",
            {"target_id": "queue-42", "token": "caller-token"},
        )

        last_call = xactions_mcp_server["last_call"]
        assert last_call["arguments"]["token"] == "caller-token"
