"""Unit tests for DeFiLlama tools (Story 0-1)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


from app.agents.new_chat.tools.defillama import (
    create_defillama_protocol_tool,
    create_defillama_tvl_overview_tool,
    create_defillama_yields_tool,
    create_defillama_stablecoins_tool,
    create_defillama_bridges_tool,
)


def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return m


# ── get_defillama_protocol ──────────────────────────────────────────────────


@pytest.fixture
def protocol_tool():
    return create_defillama_protocol_tool()


@pytest.mark.asyncio
async def test_protocol_success(protocol_tool):
    payload = {
        "name": "Uniswap",
        "symbol": "UNI",
        "category": "DEX",
        "tvl": 5_000_000_000,
        "chainTvls": {"Ethereum": {"tvl": 4_000_000_000}, "Arbitrum": {"tvl": 1_000_000_000}},
        "change_1d": 2.5,
        "change_7d": -1.2,
        "mcap": 8_000_000_000,
        "fdv": 10_000_000_000,
        "audit_links": ["https://audit.example.com"],
        "description": "AMM DEX",
        "url": "https://uniswap.org",
        "twitter": "Uniswap",
    }
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await protocol_tool.ainvoke({"protocol_slug": "uniswap"})

    assert result["name"] == "Uniswap"
    assert result["tvl"] == 5_000_000_000
    assert len(result["chains"]) == 2
    assert result["mcap"] == 8_000_000_000


@pytest.mark.asyncio
async def test_protocol_404_returns_error(protocol_tool):
    resp = _mock_response({}, status_code=404)
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = resp

        result = await protocol_tool.ainvoke({"protocol_slug": "nonexistent"})

    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_protocol_exception_returns_error(protocol_tool):
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = Exception("network timeout")

        result = await protocol_tool.ainvoke({"protocol_slug": "uniswap"})

    assert "error" in result


# ── get_defillama_tvl_overview ──────────────────────────────────────────────


@pytest.fixture
def tvl_overview_tool():
    return create_defillama_tvl_overview_tool()


_PROTOCOLS_PAYLOAD = [
    {"name": "Alpha", "slug": "alpha", "category": "DEX", "chains": ["Ethereum"], "tvl": 3e9, "change_1d": 1.0, "change_7d": 2.0, "mcap": None},
    {"name": "Beta", "slug": "beta", "category": "Lending", "chains": ["BSC"], "tvl": 1e9, "change_1d": -0.5, "change_7d": 3.0, "mcap": None},
    {"name": "Gamma", "slug": "gamma", "category": "DEX", "chains": ["Ethereum", "BSC"], "tvl": 2e9, "change_1d": 0.0, "change_7d": 0.0, "mcap": None},
]


@pytest.mark.asyncio
async def test_tvl_overview_no_filter(tvl_overview_tool):
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_PROTOCOLS_PAYLOAD)

        result = await tvl_overview_tool.ainvoke({"limit": 10})

    assert result["total_protocols"] == 3
    assert result["protocols"][0]["name"] == "Alpha"  # highest TVL first


@pytest.mark.asyncio
async def test_tvl_overview_chain_filter(tvl_overview_tool):
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_PROTOCOLS_PAYLOAD)

        result = await tvl_overview_tool.ainvoke({"chain": "BSC", "limit": 10})

    # Beta (BSC) + Gamma (Ethereum+BSC) pass filter
    names = [p["name"] for p in result["protocols"]]
    assert "Alpha" not in names
    assert "Beta" in names
    assert "Gamma" in names


# ── get_defillama_yields ────────────────────────────────────────────────────


@pytest.fixture
def yields_tool():
    return create_defillama_yields_tool()


_YIELDS_PAYLOAD = {
    "data": [
        {"pool": "p1", "project": "aave", "chain": "Ethereum", "symbol": "USDC", "tvlUsd": 1e8, "apy": 5.5, "apyBase": 5.5, "apyReward": 0, "ilRisk": "no", "stablecoin": True},
        {"pool": "p2", "project": "curve", "chain": "Ethereum", "symbol": "ETH-USDC", "tvlUsd": 5e7, "apy": 12.0, "apyBase": 3.0, "apyReward": 9.0, "ilRisk": "yes", "stablecoin": False},
    ]
}


@pytest.mark.asyncio
async def test_yields_returns_sorted_by_apy(yields_tool):
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_YIELDS_PAYLOAD)

        result = await yields_tool.ainvoke({"limit": 20})

    assert result["pools"][0]["apy"] == 12.0  # highest first


@pytest.mark.asyncio
async def test_yields_symbol_filter(yields_tool):
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_YIELDS_PAYLOAD)

        result = await yields_tool.ainvoke({"symbol": "USDC", "limit": 20})

    # Both "USDC" and "ETH-USDC" contain "USDC" → 2 matches
    assert result["total_pools"] == 2
    assert all("USDC" in p["symbol"] for p in result["pools"])


# ── get_defillama_stablecoins ───────────────────────────────────────────────


@pytest.fixture
def stablecoins_tool():
    return create_defillama_stablecoins_tool()


@pytest.mark.asyncio
async def test_stablecoins_returns_sorted(stablecoins_tool):
    payload = {
        "peggedAssets": [
            {"name": "Tether", "symbol": "USDT", "pegType": "peggedUSD", "pegMechanism": "fiat-backed", "circulating": {"peggedUSD": 100e9}, "price": 1.0, "chainCirculating": {"Ethereum": {}, "BSC": {}}},
            {"name": "USD Coin", "symbol": "USDC", "pegType": "peggedUSD", "pegMechanism": "fiat-backed", "circulating": {"peggedUSD": 40e9}, "price": 1.0, "chainCirculating": {"Ethereum": {}}},
        ]
    }
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await stablecoins_tool.ainvoke({"limit": 20})

    assert result["stablecoins"][0]["symbol"] == "USDT"
    assert result["total_stablecoins"] == 2


# ── get_defillama_bridges ───────────────────────────────────────────────────


@pytest.fixture
def bridges_tool():
    return create_defillama_bridges_tool()


@pytest.mark.asyncio
async def test_bridges_sorted_by_volume(bridges_tool):
    payload = {
        "bridges": [
            {"id": 1, "displayName": "Stargate", "chains": ["Ethereum", "BSC"], "lastDailyVolume": 5e8, "weeklyVolume": 3e9, "monthlyVolume": 10e9, "currentDayVolume": 4e8},
            {"id": 2, "displayName": "Hop", "chains": ["Ethereum", "Arbitrum"], "lastDailyVolume": 1e8, "weeklyVolume": 7e8, "monthlyVolume": 3e9, "currentDayVolume": 9e7},
        ]
    }
    with patch("app.agents.new_chat.tools.defillama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await bridges_tool.ainvoke({"limit": 20})

    assert result["bridges"][0]["name"] == "Stargate"
    assert result["total_bridges"] == 2
