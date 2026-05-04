import pytest
import respx
from httpx import Response
from unittest.mock import AsyncMock, patch, ANY
from app.agents.new_chat.tools.nansen_smart_money import create_nansen_smart_money_tool
from app.agents.new_chat.middleware.circuit_breaker import circuit_breaker
import time

@pytest.mark.asyncio
@respx.mock
async def test_nansen_circuit_breaker_opens_on_failures():
    # Mock API Key
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40
        url = "https://api.nansen.ai/v1/token/smart-money"
        
        mock_redis = AsyncMock()
        # Mocking initial state: closed, but will record failure
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 5 # Reach threshold immediately
        
        with patch.object(circuit_breaker, "_redis", mock_redis):
            # Trigger 5xx error
            respx.get(url).mock(return_value=Response(500))
            
            # This call should record failure and open circuit
            res = await tool.ainvoke({"token_address": token})
            assert res.get("status") == 500
            
            # Check if record_failure was effectively called
            mock_redis.incr.assert_called_with("cb:fail_count:nansen")
            
            # Now mock it as OPEN
            mock_redis.get.side_effect = [b"open", str(time.time() + 60).encode()]
            
            # Next call should be blocked
            res = await tool.ainvoke({"token_address": token})
            assert res.get("status") == 503

@pytest.mark.asyncio
@respx.mock
async def test_nansen_circuit_breaker_resets_on_success():
    with patch("app.agents.new_chat.tools.nansen_smart_money._api_key", return_value="fake-key"):
        tool = create_nansen_smart_money_tool()
        token = "0x" + "a" * 40
        url = "https://api.nansen.ai/v1/token/smart-money"
        
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"closed"
        
        with patch.object(circuit_breaker, "_redis", mock_redis):
            # Trigger success
            respx.get(url).mock(return_value=Response(200, json={"data": {"wallets": [], "netFlow24hUsd": 0}}))
            
            await tool.ainvoke({"token_address": token})
            
            # Should record success
            mock_redis.delete.assert_any_call("cb:fail_count:nansen", "cb:open_until:nansen", "cb:state:nansen", "cb:probe_allowed:nansen")
