"""Crypto news tools for Nowing deep agent.

Provides 2 tools:
- get_crypto_news: Latest crypto news from CryptoPanic public API
- get_coingecko_token_info: Token info, market data, and links from CoinGecko free tier

All tools are stateless (NFR-CS4) and use httpx.AsyncClient for non-blocking I/O.
Leverages @crypto_tool_decorator for global resilience (Circuit Breaker, Pacing, Error Handling).
"""

import logging
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from .utils import crypto_tool_decorator

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_COIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-_.]{0,63}$", re.IGNORECASE)


def create_crypto_news_tool():
    """Factory: get_crypto_news — latest news from CryptoPanic."""

    @tool
    @crypto_tool_decorator("cryptopanic")
    async def get_crypto_news(
        currencies: str = "BTC",
        kind: str = "news",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get latest cryptocurrency news and media from CryptoPanic.

        Use when the user asks for recent crypto news, market updates,
        or wants to know what's happening in the crypto space.

        Args:
            currencies: Comma-separated crypto symbols (e.g. "BTC", "ETH,SOL").
            kind: Type of content — "news" or "media" (default "news").
            limit: Number of articles to return (default 20, max 50).

        Returns:
            Dict with articles list and sentiment_signal, or {"error": ...}.
        """
        limit = max(1, min(int(limit), 50))
        params: dict[str, Any] = {
            "public": "true",
            "currencies": currencies.upper(),
            "kind": kind,
            "limit": limit,
        }
        url = "https://cryptopanic.com/api/v1/posts/"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 429:
            return {"error": "CryptoPanic rate limit reached, try again later"}
        resp.raise_for_status()
        data = resp.json()

        raw_results: list[dict] = data.get("results", [])

        if not raw_results:
            return {
                "currencies": currencies,
                "articles_found": 0,
                "articles": [],
                "sentiment_signal": {"positive": 0, "negative": 0, "important": 0},
            }

        articles = []
        positive_count = 0
        negative_count = 0
        important_count = 0

        for item in raw_results:
            votes: dict = item.get("votes") or {}
            positive = int(votes.get("positive") or 0)
            negative = int(votes.get("negative") or 0)
            important = int(votes.get("important") or 0)
            positive_count += positive
            negative_count += negative
            important_count += important

            source: dict = item.get("source") or {}
            articles.append(
                {
                    "title": item.get("title"),
                    "published_at": item.get("published_at"),
                    "url": item.get("url"),
                    "source": source.get("title"),
                    "source_domain": source.get("domain"),
                    "votes": {
                        "positive": positive,
                        "negative": negative,
                        "important": important,
                        "saved": int(votes.get("saved") or 0),
                    },
                    "currencies": [
                        c.get("code") for c in (item.get("currencies") or [])
                    ],
                }
            )

        total_votes = positive_count + negative_count
        positive_ratio = positive_count / total_votes if total_votes > 0 else 0.5

        return {
            "currencies": currencies,
            "articles_found": len(articles),
            "articles": articles,
            "sentiment_signal": {
                "positive": positive_count,
                "negative": negative_count,
                "important": important_count,
                "positive_ratio": round(positive_ratio, 3),
            },
        }

    return get_crypto_news


def create_coingecko_token_info_tool():
    """Factory: get_coingecko_token_info — detailed token info from CoinGecko free tier."""

    @tool
    @crypto_tool_decorator("coingecko")
    async def get_coingecko_token_info(coin_id: str) -> dict[str, Any]:
        """Get detailed token information, market data, and links from CoinGecko.

        Use when the user asks about token fundamentals, market cap, supply,
        social links, developer activity, or community stats.

        Critical for Tokenomics Analyst (Story 9.1).

        Args:
            coin_id: CoinGecko coin ID (e.g. "bitcoin", "ethereum", "solana").
                     Find IDs at https://api.coingecko.com/api/v3/coins/list

        Returns:
            Dict with market data, links, community stats, or {"error": ...}.
        """
        if not _COIN_ID_RE.match(coin_id or ""):
            return {"error": f"Invalid coin_id: {coin_id!r}"}
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)

        if resp.status_code == 429:
            return {"error": "CoinGecko rate limit reached, try again in 1 minute"}
        if resp.status_code == 404:
            return {"error": f"CoinGecko coin ID '{coin_id}' not found"}
        resp.raise_for_status()
        data = resp.json()

        market_data: dict = data.get("market_data") or {}
        current_price: dict = market_data.get("current_price") or {}
        community_data: dict = data.get("community_data") or {}
        links: dict = data.get("links") or {}

        return {
            "id": data.get("id"),
            "symbol": (data.get("symbol") or "").upper(),
            "name": data.get("name"),
            "description": (data.get("description") or {}).get("en", "")[:500],
            "categories": data.get("categories", []),
            # Market data
            "current_price_usd": current_price.get("usd", 0),
            "market_cap": (market_data.get("market_cap") or {}).get("usd", 0),
            "fully_diluted_valuation": (market_data.get("fully_diluted_valuation") or {}).get("usd", 0),
            "total_volume": (market_data.get("total_volume") or {}).get("usd", 0),
            "price_change_24h_pct": market_data.get("price_change_percentage_24h"),
            "price_change_7d_pct": market_data.get("price_change_percentage_7d"),
            "circulating_supply": market_data.get("circulating_supply"),
            "total_supply": market_data.get("total_supply"),
            "max_supply": market_data.get("max_supply"),
            "ath": (market_data.get("ath") or {}).get("usd"),
            "atl": (market_data.get("atl") or {}).get("usd"),
            # Links
            "links": {
                "homepage": (links.get("homepage") or [""])[0],
                "twitter": links.get("twitter_screen_name"),
                "github": (links.get("repos_url") or {}).get("github", []),
                "reddit": links.get("subreddit_url"),
                "coingecko_url": f"https://www.coingecko.com/en/coins/{coin_id}",
            },
            # Community
            "community_data": {
                "twitter_followers": community_data.get("twitter_followers"),
                "reddit_subscribers": community_data.get("reddit_subscribers"),
                "reddit_active_accounts_48h": community_data.get("reddit_accounts_active_48h"),
                "telegram_channel_user_count": community_data.get("telegram_channel_user_count"),
            },
            "last_updated": data.get("last_updated"),
        }

    return get_coingecko_token_info
