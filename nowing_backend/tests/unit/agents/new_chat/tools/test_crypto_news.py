"""Unit tests for crypto news tools (Story 0-1)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.new_chat.tools.crypto_news import (
    create_crypto_news_tool,
    create_coingecko_token_info_tool,
)


def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return m


# ── get_crypto_news ─────────────────────────────────────────────────────────


@pytest.fixture
def news_tool():
    return create_crypto_news_tool()


_NEWS_PAYLOAD = {
    "results": [
        {
            "title": "BTC hits new high",
            "published_at": "2026-04-23T10:00:00Z",
            "url": "https://example.com/1",
            "source": {"title": "CoinDesk", "domain": "coindesk.com"},
            "votes": {"positive": 10, "negative": 2, "important": 5, "saved": 1},
            "currencies": [{"code": "BTC"}],
        },
        {
            "title": "ETH upgrade successful",
            "published_at": "2026-04-23T09:00:00Z",
            "url": "https://example.com/2",
            "source": {"title": "The Block", "domain": "theblock.co"},
            "votes": {"positive": 8, "negative": 1, "important": 3, "saved": 0},
            "currencies": [{"code": "ETH"}],
        },
    ]
}


@pytest.mark.asyncio
async def test_news_success(news_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_NEWS_PAYLOAD)

        result = await news_tool.ainvoke({"currencies": "BTC"})

    assert result["articles_found"] == 2
    assert result["articles"][0]["title"] == "BTC hits new high"
    assert result["sentiment_signal"]["positive"] == 18  # 10 + 8
    assert result["sentiment_signal"]["negative"] == 3   # 2 + 1


@pytest.mark.asyncio
async def test_news_empty_results(news_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({"results": []})

        result = await news_tool.ainvoke({"currencies": "BTC"})

    assert result["articles_found"] == 0
    assert result["articles"] == []


@pytest.mark.asyncio
async def test_news_429_returns_error(news_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=429)

        result = await news_tool.ainvoke({"currencies": "BTC"})

    assert "error" in result
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_news_exception_returns_error(news_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = Exception("network error")

        result = await news_tool.ainvoke({"currencies": "BTC"})

    assert "error" in result


# ── get_coingecko_token_info ────────────────────────────────────────────────


@pytest.fixture
def cg_tool():
    return create_coingecko_token_info_tool()


_CG_PAYLOAD = {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin",
    "description": {"en": "Peer-to-peer digital currency."},
    "categories": ["Cryptocurrency"],
    "market_data": {
        "current_price": {"usd": 65000},
        "market_cap": {"usd": 1.3e12},
        "fully_diluted_valuation": {"usd": 1.4e12},
        "total_volume": {"usd": 3e10},
        "price_change_percentage_24h": 1.5,
        "price_change_percentage_7d": -2.3,
        "circulating_supply": 19_700_000,
        "total_supply": 21_000_000,
        "max_supply": 21_000_000,
        "ath": {"usd": 73_000},
        "atl": {"usd": 67},
    },
    "links": {
        "homepage": ["https://bitcoin.org"],
        "twitter_screen_name": "Bitcoin",
        "repos_url": {"github": ["https://github.com/bitcoin/bitcoin"]},
        "subreddit_url": "https://www.reddit.com/r/Bitcoin/",
    },
    "community_data": {
        "twitter_followers": 6_000_000,
        "reddit_subscribers": 5_000_000,
        "reddit_accounts_active_48h": 10_000,
        "telegram_channel_user_count": None,
    },
    "last_updated": "2026-04-23T10:00:00Z",
}


@pytest.mark.asyncio
async def test_coingecko_success(cg_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_CG_PAYLOAD)

        result = await cg_tool.ainvoke({"coin_id": "bitcoin"})

    assert result["id"] == "bitcoin"
    assert result["symbol"] == "BTC"
    assert result["current_price_usd"] == 65000
    assert result["links"]["twitter"] == "Bitcoin"
    assert result["community_data"]["twitter_followers"] == 6_000_000


@pytest.mark.asyncio
async def test_coingecko_404_returns_error(cg_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=404)

        result = await cg_tool.ainvoke({"coin_id": "notarealcoin"})

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_coingecko_429_returns_error(cg_tool):
    with patch("app.agents.new_chat.tools.crypto_news.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=429)

        result = await cg_tool.ainvoke({"coin_id": "bitcoin"})

    assert "error" in result
    assert "rate limit" in result["error"].lower()
