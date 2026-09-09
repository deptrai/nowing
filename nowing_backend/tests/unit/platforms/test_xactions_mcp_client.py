"""Unit tests for XActionsMcpClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
)


class TestXActionsMcpClient:
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        client = XActionsMcpClient(
            url="http://xactions:3001/mcp",
            api_key="test-key",
            consumer_id="test-consumer",
        )
        assert client.url == "http://xactions:3001/mcp"
        assert client.api_key == "test-key"
        assert client.consumer_id == "test-consumer"

    @pytest.mark.asyncio
    async def test_headers_include_auth_and_consumer_id(self):
        client = XActionsMcpClient(api_key="key", consumer_id="cid")
        headers = client._headers
        assert headers["Authorization"] == "Bearer key"
        assert headers["X-Consumer-Id"] == "cid"

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        client = XActionsMcpClient()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = '{"success": true, "data": [], "meta": {}}'
        mock_result.content = [mock_content]
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(return_value=mock_result)
        result = await client.call_tool("x_facebook_group_posts", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_tool_error_envelope(self):
        client = XActionsMcpClient()
        mock_result = MagicMock()
        mock_result.isError = True
        mock_content = MagicMock()
        mock_content.text = '{"success": false, "error": {"code": "XACT_4291", "message": "rate limited", "retryAfterMs": 5000}}'
        mock_result.content = [mock_content]
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(return_value=mock_result)
        with pytest.raises(XActionsMcpError) as exc:
            await client.call_tool("x_facebook_group_posts", {})
        assert exc.value.code == "XACT_4291"
        assert exc.value.retry_after == 5000

    @pytest.mark.asyncio
    async def test_call_tool_non_json_error(self):
        client = XActionsMcpClient()
        mock_result = MagicMock()
        mock_result.isError = True
        mock_content = MagicMock()
        mock_content.text = "Internal Server Error"
        mock_result.content = [mock_content]
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(return_value=mock_result)
        with pytest.raises(RuntimeError, match="Non-JSON XActions response"):
            await client.call_tool("x_facebook_group_posts", {})

    @pytest.mark.asyncio
    async def test_health_check(self):
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = '{"success": true, "data": {"healthyProxyCount": 5}, "meta": {}}'
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)
        result = await client.health_check()
        assert result["status"] == "healthy"
        assert result["data"]["healthyProxyCount"] == 5


class TestXActionsMcpError:
    def test_error_fields(self):
        err = XActionsMcpError(
            message="test",
            code="XACT_4010",
            retry_after=30,
            suggested_action="halt",
        )
        assert err.code == "XACT_4010"
        assert err.retry_after == 30
        assert err.suggested_action == "halt"
