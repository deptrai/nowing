"""Integration tests for crypto tools — calls real external APIs.

Run with:
    uv run pytest -m integration tests/integration/tools/test_crypto_tools_live.py -v -p no:xdist

All tests assert on response shape and data sanity, not exact values.
All tools return {"error": ...} on failure — tests accept graceful degradation
(rate limits, network issues) but fail on wrong response shape.
"""

import pytest

from app.agents.new_chat.tools.contract_analysis import (
    create_check_token_security_tool,
    create_contract_info_tool,
)
from app.agents.new_chat.tools.crypto_news import (
    create_coingecko_token_info_tool,
    create_crypto_news_tool,
)
from app.agents.new_chat.tools.crypto_sentiment import (
    create_cmc_sentiment_tool,
    create_reddit_crypto_sentiment_tool,
)
from app.agents.new_chat.tools.defillama import (
    create_defillama_bridges_tool,
    create_defillama_protocol_tool,
    create_defillama_stablecoins_tool,
    create_defillama_tvl_overview_tool,
    create_defillama_yields_tool,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _is_graceful_error(result: dict) -> bool:
    """True when the tool returned a graceful error dict (rate limit, network, etc.)."""
    return "error" in result


# ──────────────────────────────────────────────
# AC1 — DeFiLlama TVL Overview
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_defillama_tvl_overview_returns_protocols():
    """AC1: TVL overview returns list of protocols with required fields."""
    tool = create_defillama_tvl_overview_tool()
    result = await tool.ainvoke({"limit": 5})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "protocols" in result, f"Missing 'protocols' key: {result}"
    assert "total_protocols" in result
    assert isinstance(result["protocols"], list)
    assert len(result["protocols"]) > 0

    proto = result["protocols"][0]
    assert "name" in proto
    assert "tvl" in proto
    assert isinstance(proto["tvl"], (int, float))


# ──────────────────────────────────────────────
# AC2 — DeFiLlama Protocol Detail
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_defillama_protocol_returns_tvl_and_chains():
    """AC2: Protocol detail returns TVL and chain breakdown."""
    tool = create_defillama_protocol_tool()
    result = await tool.ainvoke({"protocol_slug": "uniswap"})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "tvl" in result, f"Missing 'tvl' key: {result}"
    assert "chains" in result
    assert result["tvl"] is not None
    assert isinstance(result["chains"], list)


@pytest.mark.integration
async def test_defillama_protocol_404_returns_error():
    """AC2: Non-existent protocol returns graceful error dict."""
    tool = create_defillama_protocol_tool()
    result = await tool.ainvoke({"protocol_slug": "this-protocol-does-not-exist-xyz"})

    assert "error" in result, f"Expected error for unknown slug, got: {result}"


# ──────────────────────────────────────────────
# AC3 — DeFiLlama Yields
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_defillama_yields_returns_pools():
    """AC3: Yields returns pool list with APY and TVL."""
    tool = create_defillama_yields_tool()
    result = await tool.ainvoke({"symbol": "USDC", "min_tvl": 1_000_000, "limit": 10})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "pools" in result, f"Missing 'pools' key: {result}"
    assert "total_pools" in result
    assert isinstance(result["pools"], list)

    if result["pools"]:
        pool = result["pools"][0]
        assert "apy" in pool
        assert "tvl_usd" in pool
        assert "project" in pool


# ──────────────────────────────────────────────
# AC4 — DeFiLlama Stablecoins
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_defillama_stablecoins_returns_list():
    """AC4: Stablecoins returns ranked list with circulating supply."""
    tool = create_defillama_stablecoins_tool()
    result = await tool.ainvoke({"limit": 10})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "stablecoins" in result, f"Missing 'stablecoins' key: {result}"
    assert "total_stablecoins" in result
    assert isinstance(result["stablecoins"], list)
    assert len(result["stablecoins"]) > 0

    stable = result["stablecoins"][0]
    assert "name" in stable
    assert "symbol" in stable
    assert "circulating_usd" in stable


# ──────────────────────────────────────────────
# AC5 — CoinGecko Token Info
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_coingecko_token_info_returns_market_data():
    """AC5: CoinGecko returns token info with market_cap and supply fields."""
    tool = create_coingecko_token_info_tool()
    result = await tool.ainvoke({"coin_id": "bitcoin"})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "market_cap" in result, f"Missing 'market_cap' key: {result}"
    assert "circulating_supply" in result
    assert "max_supply" in result
    assert "symbol" in result
    assert result["symbol"] == "BTC"
    assert isinstance(result["market_cap"], (int, float))
    assert result["market_cap"] > 0


@pytest.mark.integration
async def test_coingecko_token_info_404_returns_error():
    """AC5: Non-existent coin ID returns graceful error."""
    tool = create_coingecko_token_info_tool()
    result = await tool.ainvoke({"coin_id": "this-coin-does-not-exist-xyz"})

    assert "error" in result, f"Expected error for unknown coin, got: {result}"


# ──────────────────────────────────────────────
# AC6 — DeFiLlama Bridges
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_defillama_bridges_returns_volume_data():
    """AC6: Bridges returns list with 24h volume."""
    tool = create_defillama_bridges_tool()
    result = await tool.ainvoke({"limit": 5})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "bridges" in result, f"Missing 'bridges' key: {result}"
    assert "total_bridges" in result
    assert isinstance(result["bridges"], list)

    if result["bridges"]:
        bridge = result["bridges"][0]
        assert "name" in bridge
        assert "volume_24h" in bridge


# ──────────────────────────────────────────────
# AC7 — GoPlus Token Security
# ──────────────────────────────────────────────

# USDC on Ethereum — stable well-known contract for smoke testing
_USDC_ETH = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


@pytest.mark.integration
async def test_check_token_security_returns_risk_level():
    """AC7: GoPlus returns risk assessment with risk_level field."""
    tool = create_check_token_security_tool()
    result = await tool.ainvoke({"contract_address": _USDC_ETH, "chain_id": "ethereum"})

    if _is_graceful_error(result):
        pytest.skip(f"GoPlus unavailable: {result['error']}")

    assert "risk_level" in result, f"Missing 'risk_level': {result}"
    assert result["risk_level"] in ("SAFE", "LOW", "MEDIUM", "HIGH")
    assert "risk_score" in result
    assert "risks_detected" in result


@pytest.mark.integration
async def test_check_token_security_invalid_address_returns_error():
    """AC7: Invalid EVM address returns graceful error."""
    tool = create_check_token_security_tool()
    result = await tool.ainvoke({"contract_address": "not-an-address", "chain_id": "ethereum"})

    assert "error" in result, f"Expected error for invalid address, got: {result}"


# ──────────────────────────────────────────────
# AC8 — Etherscan Contract Info
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_get_contract_info_missing_api_key_returns_error():
    """AC8: Missing ETHERSCAN_API_KEY returns graceful error (not exception)."""
    import os
    saved = os.environ.pop("ETHERSCAN_API_KEY", None)
    try:
        tool = create_contract_info_tool()
        result = await tool.ainvoke({"contract_address": _USDC_ETH, "chain": "ethereum"})
        assert "error" in result, f"Expected error when API key missing, got: {result}"
    finally:
        if saved is not None:
            os.environ["ETHERSCAN_API_KEY"] = saved


# ──────────────────────────────────────────────
# AC9 — Fear & Greed Index
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_cmc_sentiment_returns_fear_greed():
    """AC9: Fear & Greed Index returns value 0-100 and classification."""
    tool = create_cmc_sentiment_tool()
    result = await tool.ainvoke({"symbol": "BTC"})

    if _is_graceful_error(result):
        pytest.skip(f"API unavailable: {result['error']}")

    assert "fear_greed_value" in result, f"Missing 'fear_greed_value': {result}"
    assert "value_classification" in result
    assert "historical_7d" in result
    assert 0 <= result["fear_greed_value"] <= 100
    assert isinstance(result["historical_7d"], list)
    assert len(result["historical_7d"]) > 0


# ──────────────────────────────────────────────
# AC10 — Reddit Crypto Sentiment
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_reddit_crypto_sentiment_returns_posts():
    """AC10: Reddit sentiment returns posts and avg_upvote_ratio."""
    tool = create_reddit_crypto_sentiment_tool()
    result = await tool.ainvoke({"symbol": "BTC", "subreddit": "CryptoCurrency", "limit": 10})

    if _is_graceful_error(result):
        pytest.skip(f"Reddit unavailable: {result['error']}")

    assert "avg_upvote_ratio" in result, f"Missing 'avg_upvote_ratio': {result}"
    assert "posts_found" in result
    assert "sentiment_signal" in result
    assert 0.0 <= result["avg_upvote_ratio"] <= 1.0


@pytest.mark.integration
async def test_reddit_crypto_sentiment_invalid_subreddit_returns_error():
    """AC10: Invalid subreddit name returns graceful error."""
    tool = create_reddit_crypto_sentiment_tool()
    result = await tool.ainvoke({"symbol": "BTC", "subreddit": "!!invalid!!", "limit": 5})

    assert "error" in result, f"Expected error for invalid subreddit, got: {result}"


# ──────────────────────────────────────────────
# AC11 — CryptoPanic News
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_crypto_news_returns_articles():
    """AC11: CryptoPanic returns articles list with sentiment_signal."""
    tool = create_crypto_news_tool()
    result = await tool.ainvoke({"currencies": "BTC", "kind": "news", "limit": 10})

    if _is_graceful_error(result):
        pytest.skip(f"CryptoPanic unavailable: {result['error']}")

    assert "articles" in result, f"Missing 'articles': {result}"
    assert "sentiment_signal" in result
    assert "articles_found" in result
    assert isinstance(result["articles"], list)

    if result["articles"]:
        article = result["articles"][0]
        assert "title" in article
        assert "url" in article
        assert "published_at" in article


# ──────────────────────────────────────────────
# AC12 — Registry Smoke Test
# ──────────────────────────────────────────────

@pytest.mark.integration
async def test_registry_all_crypto_tools_instantiable():
    """AC12: All 11 crypto tools can be instantiated via their factories."""
    factories = [
        create_defillama_tvl_overview_tool,
        create_defillama_protocol_tool,
        create_defillama_yields_tool,
        create_defillama_stablecoins_tool,
        create_defillama_bridges_tool,
        create_cmc_sentiment_tool,
        create_reddit_crypto_sentiment_tool,
        create_crypto_news_tool,
        create_coingecko_token_info_tool,
        create_contract_info_tool,
        create_check_token_security_tool,
    ]

    tools = []
    for factory in factories:
        t = factory()
        assert t is not None, f"{factory.__name__} returned None"
        assert hasattr(t, "ainvoke"), f"{factory.__name__} tool missing ainvoke"
        tools.append(t)

    assert len(tools) == 11, f"Expected 11 tools, got {len(tools)}"

    tool_names = {t.name for t in tools}
    expected_names = {
        "get_defillama_tvl_overview",
        "get_defillama_protocol",
        "get_defillama_yields",
        "get_defillama_stablecoins",
        "get_defillama_bridges",
        "get_cmc_sentiment",
        "get_reddit_crypto_sentiment",
        "get_crypto_news",
        "get_coingecko_token_info",
        "get_contract_info",
        "check_token_security",
    }
    assert tool_names == expected_names, f"Tool name mismatch: {tool_names ^ expected_names}"
