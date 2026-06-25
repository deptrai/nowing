"""Unit tests for crypto sentiment tools (Story 0-1)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.new_chat.tools.crypto_sentiment import (
    create_cmc_sentiment_tool,
    create_reddit_crypto_sentiment_tool,
)


def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return m


# ── get_cmc_sentiment ───────────────────────────────────────────────────────


@pytest.fixture
def fng_tool():
    return create_cmc_sentiment_tool()


_FNG_PAYLOAD = {
    "data": [
        {"value": "22", "value_classification": "Extreme Fear", "timestamp": "1714000000"},
        {"value": "30", "value_classification": "Fear", "timestamp": "1713913600"},
    ]
}


@pytest.mark.asyncio
async def test_fng_extreme_fear(fng_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_FNG_PAYLOAD)

        result = await fng_tool.ainvoke({"symbol": "BTC"})

    assert result["fear_greed_value"] == 22
    assert "Extreme Fear" in result["sentiment"]
    assert result["symbol_context"] == "BTC"
    assert len(result["historical_7d"]) == 2


@pytest.mark.asyncio
async def test_fng_extreme_greed(fng_tool):
    payload = {"data": [{"value": "85", "value_classification": "Extreme Greed", "timestamp": "1714000000"}]}
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await fng_tool.ainvoke({"symbol": "ETH"})

    assert "Extreme Greed" in result["sentiment"]


@pytest.mark.asyncio
async def test_fng_empty_data_returns_error(fng_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({"data": []})

        result = await fng_tool.ainvoke({"symbol": "BTC"})

    assert "error" in result


@pytest.mark.asyncio
async def test_fng_exception_returns_error(fng_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = Exception("timeout")

        result = await fng_tool.ainvoke({"symbol": "BTC"})

    assert "error" in result


# ── get_reddit_crypto_sentiment ─────────────────────────────────────────────


@pytest.fixture
def reddit_tool():
    return create_reddit_crypto_sentiment_tool()


_REDDIT_PAYLOAD = {
    "data": {
        "children": [
            {"data": {"title": "BTC to the moon", "score": 150, "upvote_ratio": 0.92, "num_comments": 30, "created_utc": 1714000000, "permalink": "/r/CryptoCurrency/comments/abc", "link_flair_text": "Discussion"}},
            {"data": {"title": "BTC concerns", "score": 20, "upvote_ratio": 0.55, "num_comments": 5, "created_utc": 1713990000, "permalink": "/r/CryptoCurrency/comments/def", "link_flair_text": None}},
        ]
    }
}


@pytest.mark.asyncio
async def test_reddit_positive_sentiment(reddit_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_REDDIT_PAYLOAD)

        result = await reddit_tool.ainvoke({"symbol": "BTC"})

    assert result["posts_found"] == 2
    assert result["symbol"] == "BTC"
    # avg ratio = (0.92 + 0.55) / 2 = 0.735 → Mixed/Neutral
    assert "Mixed" in result["sentiment_signal"] or "Positive" in result["sentiment_signal"]


@pytest.mark.asyncio
async def test_reddit_empty_posts(reddit_tool):
    payload = {"data": {"children": []}}
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await reddit_tool.ainvoke({"symbol": "BTC"})

    assert result["posts_found"] == 0
    assert result["posts"] == []


@pytest.mark.asyncio
async def test_reddit_429_returns_error(reddit_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=429)

        result = await reddit_tool.ainvoke({"symbol": "BTC"})

    assert "error" in result
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_reddit_403_private_subreddit(reddit_tool):
    with patch("app.agents.new_chat.tools.crypto_sentiment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=403)

        result = await reddit_tool.ainvoke({"symbol": "BTC", "subreddit": "private_sub"})

    assert "error" in result
    assert "private" in result["error"].lower()
