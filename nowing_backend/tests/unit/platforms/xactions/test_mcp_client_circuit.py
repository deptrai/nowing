"""Unit tests for XActions MCP Client with Circuit Breaker (Story 40.1)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
    XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS,
    XACTIONS_CONNECTIVITY_TIMEOUT_SECONDS,
)
from app.proprietary.platforms.xactions.circuit_breaker import (
    XACTIONS_CIRCUIT_BREAKER,
    CircuitState,
)


@pytest.fixture(autouse=True)
async def reset_circuit_breaker():
    """Reset circuit breaker state before each test."""
    await XACTIONS_CIRCUIT_BREAKER.reset()
    yield
    await XACTIONS_CIRCUIT_BREAKER.reset()


class TestXActionsMcpClientCircuitBreaker:
    """Test suite for XActions MCP Client circuit breaker integration."""

    @pytest.fixture
    def client(self):
        return XActionsMcpClient(
            url="http://test:3001/mcp",
            api_key="test-key",
            consumer_id="test",
        )

    def test_connectivity_timeout_default(self):
        """Connectivity timeout defaults to 4.0s."""
        assert XACTIONS_CONNECTIVITY_TIMEOUT_SECONDS == 4.0

    def test_mcp_timeout_default(self):
        """MCP timeout defaults to 60.0s."""
        assert XACTIONS_MCP_DEFAULT_TIMEOUT_SECONDS == 60.0

    @pytest.mark.asyncio
    async def test_call_tool_uses_circuit_breaker(self, client):
        """Successful call_tool goes through circuit breaker."""
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            return_value=MagicMock(
                content=[MagicMock(text='{"success": true, "data": []}')],
                isError=False,
            )
        )

        result = await client.call_tool("x_test_tool", {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_call_tool_circuit_open_raises_xact_4001(self, client):
        """Open circuit raises XACT_4001 error."""
        # Force circuit open via failures
        async def fail():
            raise ConnectionError("down")

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await XACTIONS_CIRCUIT_BREAKER.call(fail)

        assert XACTIONS_CIRCUIT_BREAKER.is_open

        client._session = AsyncMock()

        with pytest.raises(XActionsMcpError) as exc_info:
            await client.call_tool("x_test_tool", {})

        assert exc_info.value.code == "XACT_4001"
        assert "scraper_temporarily_unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_success_resets_circuit(self, client):
        """Successful call resets circuit breaker failure count."""
        # Inject prior failures
        async def fail():
            raise ConnectionError("down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await XACTIONS_CIRCUIT_BREAKER.call(fail)

        assert XACTIONS_CIRCUIT_BREAKER.stats.failure_count == 2

        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            return_value=MagicMock(
                content=[MagicMock(text='{"success": true, "data": []}')],
                isError=False,
            )
        )

        await client.call_tool("x_test_tool", {})
        assert XACTIONS_CIRCUIT_BREAKER.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_tool_failure_increments_circuit(self, client):
        """Failed call increments circuit breaker failure count."""
        initial_count = XACTIONS_CIRCUIT_BREAKER.stats.failure_count

        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            side_effect=ConnectionError("Connection failed")
        )
        client._tainted = False

        with pytest.raises(ConnectionError):
            await client.call_tool("x_test_tool", {})

        assert (
            XACTIONS_CIRCUIT_BREAKER.stats.failure_count == initial_count + 1
        )


class TestXActionsMcpClientEnvelope:
    """Test suite for envelope parsing."""

    @pytest.fixture
    def client(self):
        return XActionsMcpClient(
            url="http://test:3001/mcp",
            api_key="test-key",
            consumer_id="test",
        )

    @pytest.mark.asyncio
    async def test_empty_response_returns_success(self, client):
        """Empty response returns success envelope."""
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            return_value=MagicMock(content=[], isError=False)
        )

        result = await client.call_tool("x_test_tool", {})
        assert result == {"success": True, "data": [], "meta": {}}

    @pytest.mark.asyncio
    async def test_error_envelope_raises_mcp_error(self, client):
        """Error envelope raises XActionsMcpError."""
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            return_value=MagicMock(
                content=[
                    MagicMock(
                        text='{"success": false, "error": {"message": "Tool failed", "code": "TOOL_ERROR"}}'
                    )
                ],
                isError=True,
            )
        )

        with pytest.raises(XActionsMcpError) as exc_info:
            await client.call_tool("x_test_tool", {})

        assert exc_info.value.code == "TOOL_ERROR"
        assert "Tool failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_json_response_raises_runtime_error(self, client):
        """Non-JSON response raises RuntimeError."""
        client._session = AsyncMock()
        client._session.call_tool = AsyncMock(
            return_value=MagicMock(
                content=[MagicMock(text="not json")],
                isError=False,
            )
        )

        with pytest.raises(RuntimeError) as exc_info:
            await client.call_tool("x_test_tool", {})

        assert "Non-JSON" in str(exc_info.value)
