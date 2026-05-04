import pytest
from app.agents.new_chat.tools.crypto_smart_money_flow import create_smart_money_flow_tool
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_smart_money_flow_returns_sankey_shape():
    mock_nansen_output = {
        "source_domain": "nansen.ai",
        "token_address": "0x123",
        "smart_money_wallets": [
            {"label": "Whale A", "net_flow_usd": 1000.0},
            {"label": "Whale B", "net_flow_usd": -500.0},
        ],
        "net_flow_24h_usd": 500.0,
    }
    
    # We patch the factory used inside create_smart_money_flow_tool
    with patch("app.agents.new_chat.tools.crypto_smart_money_flow.create_nansen_smart_money_tool") as mock_factory:
        mock_tool = AsyncMock()
        mock_tool.ainvoke.return_value = mock_nansen_output
        mock_factory.return_value = mock_tool
        
        # Tool creation triggers the factory call
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x123"})
        
        assert res["source_domain"] == "nansen.ai"
        assert len(res["nodes"]) == 3  # Market, Whale A, Whale B
        assert any(n["id"] == "Market" for n in res["nodes"])
        assert any(n["id"] == "Whale A" for n in res["nodes"])
        assert any(n["id"] == "Whale B" for n in res["nodes"])
        
        assert len(res["links"]) == 2
        assert res["net_flow_amount"] == 500.0
        
        # Check link directions
        inflow = next(l for l in res["links"] if l["target"] == "Whale A")
        assert inflow["source"] == "Market"
        assert inflow["value"] == 1000.0
        
        outflow = next(l for l in res["links"] if l["source"] == "Whale B")
        assert outflow["target"] == "Market"
        assert outflow["value"] == 500.0

@pytest.mark.asyncio
async def test_get_smart_money_flow_propagates_nansen_error():
    mock_error = {"error": "Rate limit", "status": 429}
    
    with patch("app.agents.new_chat.tools.crypto_smart_money_flow.create_nansen_smart_money_tool") as mock_factory:
        mock_tool = AsyncMock()
        mock_tool.ainvoke.return_value = mock_error
        mock_factory.return_value = mock_tool
        
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x123"})
        
        assert "error" in res
        assert res["status"] == 429
        assert res["source_domain"] == "nansen.ai"
