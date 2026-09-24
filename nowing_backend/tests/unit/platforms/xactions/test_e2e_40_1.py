"""E2E integration test for Story 40.1 - XActions circuit breaker.

Tests that exercise the real code path (not mocked):
- call_tool goes through circuit breaker
- After 3 failures → circuit opens
- Subsequent calls fail fast with XACT_4001
- After recovery timeout → circuit half-opens and probes
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpClient,
    XActionsMcpError,
    XACTIONS_CONNECTIVITY_TIMEOUT_SECONDS,
)
from app.proprietary.platforms.xactions.circuit_breaker import (
    XACTIONS_CIRCUIT_BREAKER,
    XActionsCircuitBreaker,
    CircuitState,
)


@pytest.fixture(autouse=True)
async def reset_breaker():
    await XACTIONS_CIRCUIT_BREAKER.reset()
    yield
    await XACTIONS_CIRCUIT_BREAKER.reset()


class TestE2E401CircuitBreaker:
    """E2E tests for Story 40.1."""

    @pytest.mark.asyncio
    async def test_e2e_circuit_breaker_happy_path(self):
        """Successful call goes through circuit breaker."""
        client = XActionsMcpClient(
            url="http://test:3001/mcp",
            api_key="test-key",
            consumer_id="e2e-test",
        )

        async def fake_call(name, args):
            return {
                "success": True,
                "data": [{"id": 1}],
                "meta": {},
                "summary": {},
                "artifact_path": None,
            }

        with patch.object(client, "_call_tool_inner", side_effect=fake_call):
            result = await client.call_tool("x_scrape", {
                "platform": "topcv",
                "action": "scrape",
                "args": {"keyword": "test"},
                "context": {"targetId": "t1", "workspaceId": "w1"},
            })

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert XACTIONS_CIRCUIT_BREAKER.is_closed
        assert XACTIONS_CIRCUIT_BREAKER.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_e2e_circuit_opens_after_threshold(self):
        """Circuit opens after 3 consecutive failures → fail-fast XACT_4001."""
        client = XActionsMcpClient(
            url="http://test:3001/mcp",
            api_key="test-key",
            consumer_id="e2e-test",
        )

        async def fail_call(name, args):
            raise ConnectionError("XActions unreachable")

        with patch.object(client, "_call_tool_inner", side_effect=fail_call):
            for i in range(3):
                with pytest.raises(ConnectionError):
                    await client.call_tool("x_scrape", {})

        assert XACTIONS_CIRCUIT_BREAKER.is_open
        assert XACTIONS_CIRCUIT_BREAKER.stats.state == CircuitState.OPEN

        # 4th call fails fast with XACT_4001
        with pytest.raises(XActionsMcpError) as exc_info:
            await client.call_tool("x_scrape", {})

        assert exc_info.value.code == "XACT_4001"
        assert "scraper_temporarily_unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_e2e_circuit_recovery(self):
        """Circuit recovers after timeout via half-open probe."""
        fast_breaker = XActionsCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            expected_exceptions=(ConnectionError,),
        )

        async def fail():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await fast_breaker.call(fail)
        assert fast_breaker.is_open

        await asyncio.sleep(0.15)

        async def success():
            return {"ok": True}

        result = await fast_breaker.call(success)
        assert result == {"ok": True}
        assert fast_breaker.is_closed
        assert fast_breaker.stats.failure_count == 0
