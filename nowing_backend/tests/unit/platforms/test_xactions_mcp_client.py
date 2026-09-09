"""Unit tests for XActionsMcpClient."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        assert exc.value.retry_after == 5.0  # 5000 ms → 5 s

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

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = '{"success": false, "data": {"healthyProxyCount": 0}, "meta": {}}'
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)
        result = await client.health_check()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_unavailable(self):
        client = XActionsMcpClient()
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(side_effect=RuntimeError("MCP down"))
        result = await client.health_check()
        assert result["status"] == "unavailable"
        assert "MCP down" in result["error"]

    @pytest.mark.asyncio
    async def test_call_tool_url_default_fallthrough(self, monkeypatch):
        """Kill line 62 ReplaceOrWithAnd: url or config or default."""
        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_MCP_URL",
            "http://from-config:3001/mcp",
        )
        client = XActionsMcpClient()
        assert client.url == "http://from-config:3001/mcp"

        client2 = XActionsMcpClient(url="http://explicit:3001/mcp")
        assert client2.url == "http://explicit:3001/mcp"

        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_MCP_URL",
            "",
        )
        client3 = XActionsMcpClient()
        assert client3.url == "http://xactions:3001/mcp"

    @pytest.mark.asyncio
    async def test_call_tool_uses_default_success(self):
        """Kill line 150, 181 ReplaceTrueWithFalse and line 178 AddNot."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = '{"data": [], "meta": {}}'
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)
        result = await client.call_tool("x_facebook_group_posts", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_tool_empty_response_defaults(self):
        """Kill line 150 ReplaceTrueWithFalse: empty result_text returns success=True."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = "   "
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)
        result = await client.call_tool("x_facebook_group_posts", {})
        assert result["success"] is True
        assert result["data"] == []
        assert result["meta"] == {}

    @pytest.mark.asyncio
    async def test_call_tool_data_with_artifact_appends(self):
        """Kill line 178: data + artifact_data appends; non-list falls back."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "data": [{"post_id": "1"}],
            "meta": {"datasetArtifactPath": "http://xactions/artifact"},
        })
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)

        with patch.object(
            client, "_fetch_artifact", new=AsyncMock(return_value=[{"post_id": "2"}])
        ):
            result = await client.call_tool("x_facebook_group_posts", {})
        assert result["data"] == [{"post_id": "1"}, {"post_id": "2"}]

        # Non-list data should be replaced by artifact data
        mock_content.text = json.dumps({
            "data": {"count": 5},
            "meta": {"datasetArtifactPath": "http://xactions/artifact"},
        })
        with patch.object(
            client, "_fetch_artifact", new=AsyncMock(return_value=[{"post_id": "3"}])
        ):
            result = await client.call_tool("x_facebook_group_posts", {})
        assert result["data"] == [{"post_id": "3"}]

    @pytest.mark.asyncio
    async def test_call_tool_retry_after_seconds_not_ms(self):
        """Kill line 167 ReplaceAndWithOr: only convert ms when retry_after is None."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = True
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "success": False,
            "error": {
                "code": "XACT_4291",
                "message": "rate limited",
                "retryAfter": 120,
                "retryAfterMs": 5000,
            },
        })
        mock_result.content = [mock_content]
        client._session.call_tool = AsyncMock(return_value=mock_result)
        with pytest.raises(XActionsMcpError) as exc:
            await client.call_tool("x_facebook_group_posts", {})
        assert exc.value.retry_after == 120  # seconds wins

    @pytest.mark.asyncio
    async def test_resolve_artifact_path_rejects_traversal(self):
        """Kill line 102, 106 AddNot / path traversal guard."""
        root = "/tmp/xactions_artifacts"
        with pytest.raises(ValueError):
            XActionsMcpClient._resolve_artifact_path(root, "../etc/passwd")
        with pytest.raises(ValueError):
            XActionsMcpClient._resolve_artifact_path(root, "/etc/passwd")

    @pytest.mark.asyncio
    async def test_resolve_artifact_path_accepts_relative(self):
        root = "/tmp/xactions_artifacts"
        result = XActionsMcpClient._resolve_artifact_path(root, "fb/group_1.json")
        assert result == str(Path(root).resolve() / "fb" / "group_1.json")

    @pytest.mark.asyncio
    async def test_list_tools_requires_session(self):
        """Kill line 114 AddNot: session guard."""
        client = XActionsMcpClient()
        with pytest.raises(RuntimeError, match="MCP session not initialized"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_list_tools_input_schema(self):
        """Kill line 122 AddNot: hasattr guard for inputSchema."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        tool_with_schema = MagicMock()
        tool_with_schema.name = "x_tool"
        tool_with_schema.description = "desc"
        tool_with_schema.inputSchema = {"type": "object"}
        tool_without_schema = MagicMock()
        tool_without_schema.name = "x_old"
        tool_without_schema.description = None
        del tool_without_schema.inputSchema
        client._session.list_tools = AsyncMock(return_value=MagicMock(tools=[tool_with_schema, tool_without_schema]))
        result = await client.list_tools()
        assert result[0]["input_schema"] == {"type": "object"}
        assert result[1]["input_schema"] == {}

    @pytest.mark.asyncio
    async def test_list_tools_description_fallback(self):
        """Kill line 121 ReplaceOrWithAnd: None description falls back to empty string."""
        client = XActionsMcpClient()
        client._session = AsyncMock()
        tool = MagicMock()
        tool.name = "x_tool"
        tool.description = None
        tool.inputSchema = {}
        client._session.list_tools = AsyncMock(return_value=MagicMock(tools=[tool]))
        result = await client.list_tools()
        assert result[0]["description"] == ""

    @pytest.mark.asyncio
    async def test_aexit_handles_none_session_transport(self):
        """Kill line 87, 90 ReplaceComparisonOperator / AddNot."""
        client = XActionsMcpClient()
        client._session = None
        client._transport_cm = None
        # should not raise
        await client.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_aexit_closes_session_and_transport(self):
        client = XActionsMcpClient()
        client._session = AsyncMock()
        client._transport_cm = AsyncMock()
        await client.__aexit__(None, None, None)
        assert client._session is None
        assert client._transport_cm is None

    @pytest.mark.asyncio
    async def test_fetch_artifact_http_bad_json(self):
        """Kill line 197 ExceptionReplacer."""
        client = XActionsMcpClient()
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(side_effect=json.JSONDecodeError("bad", "", 0)),
        ))):
            result = await client._fetch_artifact("http://xactions/artifact.json")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_artifact_local_no_root(self, monkeypatch):
        """Kill line 203 AddNot: missing XACTIONS_ARTIFACT_ROOT."""
        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_ARTIFACT_ROOT",
            None,
        )
        client = XActionsMcpClient()
        result = await client._fetch_artifact("group_1.json")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_artifact_local_unsafe_path(self, monkeypatch):
        """Kill line 212 ExceptionReplacer."""
        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_ARTIFACT_ROOT",
            "/tmp/xactions_artifacts",
        )
        client = XActionsMcpClient()
        result = await client._fetch_artifact("../etc/passwd")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_artifact_local_read_error(self, monkeypatch, tmp_path):
        """Kill line 220 ExceptionReplacer."""
        root = tmp_path / "artifacts"
        root.mkdir()
        (root / "bad.json").write_text("not json")
        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_ARTIFACT_ROOT",
            str(root),
        )
        client = XActionsMcpClient()
        result = await client._fetch_artifact("bad.json")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_artifact_local_success(self, monkeypatch, tmp_path):
        root = tmp_path / "artifacts"
        root.mkdir()
        (root / "good.json").write_text(json.dumps([{"post_id": "p1"}]))
        monkeypatch.setattr(
            "app.proprietary.platforms.xactions.mcp_client.config.XACTIONS_ARTIFACT_ROOT",
            str(root),
        )
        client = XActionsMcpClient()
        result = await client._fetch_artifact("good.json")
        assert result == [{"post_id": "p1"}]


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
