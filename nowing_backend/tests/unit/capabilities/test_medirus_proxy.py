"""Unit tests for Medirus thin-proxy executor (Story 40.2)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.capabilities.core.medirus_proxy import (
    _map_medirus_error,
    make_medirus_executor,
)
from app.exceptions import ExternalServiceError
from app.proprietary.platforms.medirus.mcp_client import MedirusMcpError


class TestMedirusProxyExecutor:
    """Test Medirus thin-proxy executor."""

    @pytest.fixture
    def mock_client(self):
        """Mock the shared MCP client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_executor_calls_x_scrape(self, mock_client):
        """Test that executor calls medirus_scrape with correct envelope."""
        mock_client.call_tool = AsyncMock(
            return_value={
                "success": True,
                "data": [{"id": "job1", "title": "Developer"}],
                "meta": {"cost_micros": 5500, "degraded": False},
            }
        )

        with patch(
            "app.capabilities.core.medirus_proxy.get_shared_client",
            return_value=mock_client,
        ):
            executor = make_medirus_executor(
                platform="topcv",
                action="scrape",
                args_mapper=lambda i: {"keyword": i.keyword},
            )

            mock_input = MagicMock()
            mock_input.keyword = "data engineer"
            mock_input.target_id = "target-123"
            mock_input.model_dump.return_value = {"keyword": "data engineer"}

            ctx = MagicMock()
            ctx.workspace_id = 42

            result = await executor(mock_input, ctx)

            # Verify medirus_scrape was called with correct envelope
            mock_client.call_tool.assert_called_once_with(
                "medirus_scrape",
                {
                    "platform": "topcv",
                    "action": "scrape",
                    "args": {"keyword": "data engineer"},
                    "context": {
                        "targetId": "target-123",
                        "workspaceId": "42",
                    },
                },
            )

            assert result["items"] == [{"id": "job1", "title": "Developer"}]
            assert result["cost_micros"] == 5500

    @pytest.mark.asyncio
    async def test_executor_maps_xact_4001_to_503(self, mock_client):
        """Test that MEDIRUS_4001 circuit-open maps to ExternalServiceError."""
        mock_client.call_tool = AsyncMock(
            side_effect=MedirusMcpError(
                message="scraper_temporarily_unavailable",
                code="MEDIRUS_4001",
            )
        )

        with patch(
            "app.capabilities.core.medirus_proxy.get_shared_client",
            return_value=mock_client,
        ):
            executor = make_medirus_executor(platform="topcv")

            mock_input = MagicMock()
            mock_input.model_dump.return_value = {}

            with pytest.raises(ExternalServiceError) as exc_info:
                await executor(mock_input, None)

            assert exc_info.value.code == "MEDIRUS_4001"

    @pytest.mark.asyncio
    async def test_executor_handles_degraded_response(self, mock_client):
        """Test that degraded response passes through."""
        mock_client.call_tool = AsyncMock(
            return_value={
                "success": True,
                "data": [{"id": "partial"}],
                "meta": {
                    "cost_micros": 2750,
                    "degraded": True,
                    "degradation_reason": "bot_detected",
                },
            }
        )

        with patch(
            "app.capabilities.core.medirus_proxy.get_shared_client",
            return_value=mock_client,
        ):
            executor = make_medirus_executor(platform="topcv")

            mock_input = MagicMock()
            mock_input.model_dump.return_value = {}

            result = await executor(mock_input, None)

            assert result["degraded"] is True
            assert result["degradation_reason"] == "bot_detected"
            assert result["cost_micros"] == 2750

    @pytest.mark.asyncio
    async def test_executor_handles_error_envelope(self, mock_client):
        """Test that error envelope raises mapped exception."""
        mock_client.call_tool = AsyncMock(
            return_value={
                "success": False,
                "error": {
                    "message": "Invalid platform",
                    "code": "VALIDATION_ERROR",
                },
            }
        )

        with patch(
            "app.capabilities.core.medirus_proxy.get_shared_client",
            return_value=mock_client,
        ):
            executor = make_medirus_executor(platform="topcv")

            mock_input = MagicMock()
            mock_input.model_dump.return_value = {}

            with pytest.raises(ExternalServiceError) as exc_info:
                await executor(mock_input, None)

            assert exc_info.value.code == "MEDIRUS_4002"

    @pytest.mark.asyncio
    async def test_executor_wraps_generic_error(self, mock_client):
        """Test that generic exceptions are wrapped."""
        mock_client.call_tool = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )

        with patch(
            "app.capabilities.core.medirus_proxy.get_shared_client",
            return_value=mock_client,
        ):
            executor = make_medirus_executor(platform="topcv")

            mock_input = MagicMock()
            mock_input.model_dump.return_value = {}

            with pytest.raises(ExternalServiceError) as exc_info:
                await executor(mock_input, None)

            assert exc_info.value.code == "MEDIRUS_UPSTREAM_ERROR"


class TestMedirusErrorMapping:
    """Test error mapping functions."""

    def test_map_xact_4001(self):
        exc = MedirusMcpError("test", code="MEDIRUS_4001")
        result = _map_medirus_error(exc)
        assert isinstance(result, ExternalServiceError)
        assert result.code == "MEDIRUS_4001"

    def test_map_xact_4002(self):
        exc = MedirusMcpError("bad args", code="MEDIRUS_4002")
        result = _map_medirus_error(exc)
        assert isinstance(result, ExternalServiceError)
        assert result.code == "MEDIRUS_4002"

    def test_map_validation_error(self):
        exc = MedirusMcpError("invalid", code="VALIDATION_ERROR")
        result = _map_medirus_error(exc)
        assert isinstance(result, ExternalServiceError)
        assert result.code == "MEDIRUS_4002"
