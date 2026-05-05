"""Unit tests for crypto_smart_money_flow.get_smart_money_flow.

Story 10.1.1 AC1: tool wrapper that transforms raw Nansen smart-money output
into a Sankey-ready visualization shape.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.new_chat.tools.crypto_smart_money_flow import create_smart_money_flow_tool


def _patched_nansen(return_value):
    """Helper: patch the inner Nansen factory to return a mock with `ainvoke`."""
    mock_tool = AsyncMock()
    mock_tool.ainvoke = AsyncMock(return_value=return_value)
    return patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow.create_nansen_smart_money_tool",
        return_value=mock_tool,
    )


@pytest.mark.asyncio
async def test_get_smart_money_flow_returns_sankey_shape():
    mock_nansen_output = {
        "source_domain": "nansen.ai",
        "token_address": "0x" + "1" * 40,
        "smart_money_wallets": [
            {"address": "0xaaaa", "label": "Whale A", "net_flow_usd": 1000.0},
            {"address": "0xbbbb", "label": "Whale B", "net_flow_usd": -500.0},
        ],
        "net_flow_24h_usd": 500.0,
    }
    with _patched_nansen(mock_nansen_output):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x" + "1" * 40})

    assert res["source_domain"] == "nansen.ai"
    assert any(n["id"] == "Market" for n in res["nodes"])
    assert len(res["links"]) == 2
    assert res["net_flow_amount"] == 500.0

    market_to_whale_a = next(
        link for link in res["links"] if link["source"] == "Market" and link["target"].startswith("Whale A")
    )
    assert market_to_whale_a["value"] == 1000.0

    whale_b_to_market = next(
        link for link in res["links"] if link["target"] == "Market" and link["source"].startswith("Whale B")
    )
    assert whale_b_to_market["value"] == 500.0


@pytest.mark.asyncio
async def test_get_smart_money_flow_nansen_error_returns_empty_sankey():
    """When Nansen errors and no fallback keys, tool returns empty valid Sankey (not error dict)."""
    mock_error = {"error": "Rate limit", "status": 429, "source_domain": "nansen.ai"}
    with _patched_nansen(mock_error):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x" + "1" * 40})

    # Empty Sankey is intentional — avoids breaking the visualization UI.
    # source_domain stays "nansen.ai" (the primary provider tried) so the FE
    # citation badge has a valid favicon URL.
    assert "nodes" in res
    assert "links" in res
    assert res["links"] == []
    assert res["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_get_smart_money_flow_in_smart_money_allowed_tools():
    """get_smart_money_flow must be registered for smart_money_analyst sub-agent."""
    from app.agents.new_chat.subagents.crypto.smart_money_spec import SMART_MONEY_ALLOWED_TOOLS

    assert "get_smart_money_flow" in SMART_MONEY_ALLOWED_TOOLS


@pytest.mark.asyncio
async def test_get_smart_money_flow_rejects_empty_address():
    with _patched_nansen({}):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": ""})
    assert "error" in res
    assert "required" in res["error"]


@pytest.mark.asyncio
async def test_get_smart_money_flow_rejects_unsupported_chain():
    with _patched_nansen({}):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x" + "1" * 40, "chain": "solana"})
    assert "error" in res
    assert "solana" in res["error"]


@pytest.mark.asyncio
async def test_get_smart_money_flow_handles_empty_wallets():
    """Spec edge case: Nansen returns 200 but no wallets — still return valid Sankey."""
    mock_output = {
        "source_domain": "nansen.ai",
        "smart_money_wallets": [],
        "net_flow_24h_usd": 0.0,
    }
    with _patched_nansen(mock_output):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x" + "1" * 40})

    assert res["nodes"] == [{"id": "Market"}]
    assert res["links"] == []
    assert res["net_flow_amount"] == 0.0


@pytest.mark.asyncio
async def test_get_smart_money_flow_caps_wallet_count():
    """30+ wallets should be capped to keep Sankey readable."""
    wallets = [
        {"address": f"0x{i:040x}", "label": f"W{i}", "net_flow_usd": 1000.0 + i}
        for i in range(50)
    ]
    mock_output = {
        "source_domain": "nansen.ai",
        "smart_money_wallets": wallets,
        "net_flow_24h_usd": 50000.0,
    }
    with _patched_nansen(mock_output):
        tool = create_smart_money_flow_tool()
        res = await tool.ainvoke({"token_address": "0x" + "1" * 40})

    # Market + at most 30 wallet nodes (cap enforced by _MAX_WALLETS_IN_SANKEY)
    assert len(res["nodes"]) <= 31
