"""Hermetic integration tests for MedirusMcpClient (Story 26-7).

Uses the shared E2E fake MCP runtime so no network calls are made.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.proprietary.platforms.medirus.mcp_client import (
    MedirusMcpClient,
    MedirusMcpError,
)
from tests.e2e.fakes import mcp_runtime

pytestmark = pytest.mark.integration

_MEDIRUS_MCP_URL = "http://medirus:3001/mcp"
_MEDIRUS_API_KEY = "test-medirus-api-key"
_MEDIRUS_CONSUMER_ID = "test-consumer"
_MEDIRUS_ADMIN_TOKEN = "super-secret-admin-token"


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
def medirus_mcp_server():
    """Install the fake MCP runtime and register a fake Medirus server."""
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

        raise NotImplementedError(f"Unexpected Medirus tool call: {tool_name!r}")

    mcp_runtime.register(
        url=_MEDIRUS_MCP_URL,
        expected_bearer=_MEDIRUS_API_KEY,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )

    yield {"last_call": last_call}

    for p in active_patches:
        p.stop()
    mcp_runtime.reset()


@pytest.fixture
async def medirus_client(medirus_mcp_server):
    """Yield a configured MedirusMcpClient inside a fake transport session."""
    client = MedirusMcpClient(
        url=_MEDIRUS_MCP_URL,
        api_key=_MEDIRUS_API_KEY,
        consumer_id=_MEDIRUS_CONSUMER_ID,
    )
    client.admin_token = _MEDIRUS_ADMIN_TOKEN
    async with client as c:
        yield c


class TestHermeticMedirusMcpClient:
    """Hermetic tests for Medirus MCP client list/call without network."""

    @pytest.mark.asyncio
    async def test_hermetic_list_tools(self, medirus_client: MedirusMcpClient) -> None:
        """list_tools returns tool names, descriptions, and input schemas."""
        tools = await medirus_client.list_tools()
        names = {tool["name"] for tool in tools}
        assert names == {"x_facebook_group_posts", "x_admin_purge"}

        fb_tool = next(t for t in tools if t["name"] == "x_facebook_group_posts")
        assert fb_tool["description"] == "Fetch posts from a Facebook group."
        assert fb_tool["input_schema"]["required"] == ["group_id"]

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_success(
        self, medirus_client: MedirusMcpClient, medirus_mcp_server: dict[str, Any]
    ) -> None:
        """call_tool parses the 3-layer envelope and returns data, meta, summary."""
        result = await medirus_client.call_tool(
            "x_facebook_group_posts",
            {"group_id": "12345", "limit": 10},
        )

        assert result["success"] is True
        assert result["data"] == [{"id": "post-1", "message": "hello"}]
        assert result["meta"] == {"total": 1, "page": 1}
        assert result["summary"] == {"fetched": 1}

        last_call = medirus_mcp_server["last_call"]
        assert last_call["tool_name"] == "x_facebook_group_posts"
        assert last_call["arguments"]["group_id"] == "12345"

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_structured_error(
        self, medirus_client: MedirusMcpClient
    ) -> None:
        """Structured error envelope raises MedirusMcpError with retry_after."""
        with pytest.raises(MedirusMcpError) as exc_info:
            await medirus_client.call_tool(
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
        self, medirus_client: MedirusMcpClient, medirus_mcp_server: dict[str, Any]
    ) -> None:
        """Admin token is injected for x_admin_* tools when token not provided."""
        await medirus_client.call_tool(
            "x_admin_purge",
            {"target_id": "queue-42"},
        )

        last_call = medirus_mcp_server["last_call"]
        assert last_call["tool_name"] == "x_admin_purge"
        assert last_call["arguments"]["target_id"] == "queue-42"
        assert last_call["arguments"]["token"] == _MEDIRUS_ADMIN_TOKEN

    @pytest.mark.asyncio
    async def test_hermetic_call_tool_admin_token_preserved_when_explicit(
        self, medirus_client: MedirusMcpClient, medirus_mcp_server: dict[str, Any]
    ) -> None:
        """Caller-provided token is not overwritten by the admin token helper."""
        await medirus_client.call_tool(
            "x_admin_purge",
            {"target_id": "queue-42", "token": "caller-token"},
        )

        last_call = medirus_mcp_server["last_call"]
        assert last_call["arguments"]["token"] == "caller-token"
