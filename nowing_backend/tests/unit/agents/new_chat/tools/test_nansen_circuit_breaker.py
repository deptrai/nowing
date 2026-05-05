import time
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from app.agents.new_chat.middleware.circuit_breaker import (
    FAILURE_THRESHOLD,
    circuit_breaker,
)
from app.agents.new_chat.tools.nansen_smart_money import create_nansen_smart_money_tool


@pytest.mark.asyncio
@respx.mock
async def test_nansen_circuit_opens_after_3_consecutive_5xx():
    """AC3: Circuit opens once 3 consecutive 5xx errors land within 60s window."""
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40
        url = "https://api.nansen.ai/api/v1/tgm/who-bought-sold"

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # circuit closed initially
        mock_redis.incr.return_value = FAILURE_THRESHOLD  # threshold reached on this call

        with patch.object(circuit_breaker, "_redis", mock_redis):
            respx.post(url).mock(return_value=Response(500))

            res = await tool.ainvoke({"token_address": token})
            assert res.get("status") == 500
            mock_redis.incr.assert_called_with("cb:fail_count:nansen")
            # State must transition to "open" once threshold reached
            mock_redis.set.assert_any_call("cb:state:nansen", "open", ex=120)


@pytest.mark.asyncio
@respx.mock
async def test_nansen_circuit_returns_503_when_open():
    """AC3: When circuit is open, tool returns 503 without hitting Nansen."""
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40

        mock_redis = AsyncMock()
        # Sequence: state=open, open_until=future
        mock_redis.get.side_effect = [b"open", str(time.time() + 60).encode()]

        with patch.object(circuit_breaker, "_redis", mock_redis):
            res = await tool.ainvoke({"token_address": token})
            assert res.get("status") == 503


@pytest.mark.asyncio
@respx.mock
async def test_nansen_404_returns_empty_wallets_not_error():
    """404 = token not indexed by Nansen — must return empty wallets, NOT an error dict."""
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40
        url = "https://api.nansen.ai/api/v1/tgm/who-bought-sold"

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # circuit closed

        with patch.object(circuit_breaker, "_redis", mock_redis):
            respx.post(url).mock(return_value=Response(404))

            res = await tool.ainvoke({"token_address": token})
            assert "error" not in res
            assert res.get("smart_money_wallets") == []
            assert res.get("signal") == "neutral"
            # 404 must not count as a failure
            mock_redis.incr.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_nansen_circuit_half_open_probe_succeeds():
    """AC3: After cooldown expires, one probe is allowed; success closes the circuit."""
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40
        url = "https://api.nansen.ai/api/v1/tgm/who-bought-sold"

        mock_redis = AsyncMock()
        # Sequence on is_open():
        #   state=open, open_until=past (cooldown expired)
        # then SET NX creates the probe slot, DECR returns 0 (allowed=0, NOT blocked)
        mock_redis.get.side_effect = [b"open", str(time.time() - 1).encode(), b"half_open"]
        mock_redis.set.return_value = True  # SET NX succeeded
        mock_redis.decr.return_value = 0  # probe allowed

        with patch.object(circuit_breaker, "_redis", mock_redis):
            respx.post(url).mock(
                return_value=Response(200, json={"data": [], "pagination": {"page": 1, "per_page": 30, "is_last_page": True}})
            )

            res = await tool.ainvoke({"token_address": token})
            assert "error" not in res
            # Probe success → circuit closed → state keys deleted
            mock_redis.delete.assert_any_call(
                "cb:fail_count:nansen",
                "cb:open_until:nansen",
                "cb:state:nansen",
                "cb:probe_allowed:nansen",
            )
