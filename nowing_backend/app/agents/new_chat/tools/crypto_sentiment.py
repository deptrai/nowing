"""Crypto sentiment tools for Nowing deep agent.

Provides 2 tools for fetching crypto market sentiment:
- get_cmc_sentiment: Fear & Greed Index from alternative.me
- get_reddit_crypto_sentiment: Reddit post sentiment for a subreddit/symbol

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
_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")


def create_cmc_sentiment_tool():
    """Factory: get_cmc_sentiment — Crypto Fear & Greed Index."""

    @tool
    @crypto_tool_decorator("alternative_me")
    async def get_cmc_sentiment(symbol: str) -> dict[str, Any]:
        """Get the Crypto Fear & Greed Index for general market sentiment.

        Use when the user asks about overall crypto market mood, fear/greed,
        or sentiment indicators (e.g. "is the market fearful?").

        Note: The Fear & Greed Index is a market-wide indicator, not
        symbol-specific. The symbol param is recorded for context.

        Args:
            symbol: Crypto symbol for context (e.g. "BTC", "ETH").

        Returns:
            Dict with value (0-100), value_classification, and historical data,
            or {"error": ...}.
        """
        url = "https://api.alternative.me/fng/?limit=7&format=json"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        entries: list[dict] = data.get("data", [])

        if not entries:
            return {"error": "No Fear & Greed data returned"}

        latest = entries[0]
        current_value = int(latest.get("value") or 0)

        # Classify sentiment
        if current_value <= 25:
            sentiment = "Extreme Fear 😱"
        elif current_value <= 45:
            sentiment = "Fear 😰"
        elif current_value <= 55:
            sentiment = "Neutral 😐"
        elif current_value <= 75:
            sentiment = "Greed 😄"
        else:
            sentiment = "Extreme Greed 🤑"

        return {
            "symbol_context": symbol,
            "fear_greed_value": current_value,
            "value_classification": latest.get("value_classification"),
            "sentiment": sentiment,
            "timestamp": latest.get("timestamp"),
            "historical_7d": [
                {
                    "value": int(e.get("value", 0)),
                    "classification": e.get("value_classification"),
                    "timestamp": e.get("timestamp"),
                }
                for e in entries[:7]
            ],
            "source": "alternative.me Fear & Greed Index",
        }

    return get_cmc_sentiment


def create_reddit_crypto_sentiment_tool():
    """Factory: get_reddit_crypto_sentiment — Reddit post sentiment."""

    @tool
    @crypto_tool_decorator("reddit")
    async def get_reddit_crypto_sentiment(
        symbol: str,
        subreddit: str = "CryptoCurrency",
        limit: int = 25,
    ) -> dict[str, Any]:
        """Get Reddit community sentiment for a crypto symbol.

        Use when the user asks about Reddit community opinion, social buzz,
        or sentiment around a specific token or topic.

        Args:
            symbol: Crypto symbol to search for (e.g. "BTC", "ETH", "SOL").
            subreddit: Subreddit to search in (default: "CryptoCurrency").
            limit: Number of posts to analyze (default 25, max 100).

        Returns:
            Dict with posts list, upvote stats, and sentiment_summary,
            or {"error": ...}.
        """
        limit = max(1, min(limit, 100))
        # Validate subreddit to prevent URL path injection
        if not _SUBREDDIT_RE.match(subreddit):
            return {"error": f"Invalid subreddit name: {subreddit!r}"}
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": symbol,
            "sort": "new",
            "limit": limit,
            "restrict_sr": 1,
        }
        headers = {"User-Agent": "nowing-crypto-agent/1.0"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code == 429:
            return {"error": "Reddit rate limit reached, try again later"}
        if resp.status_code == 403:
            return {"error": f"Reddit subreddit r/{subreddit} is private or banned"}
        resp.raise_for_status()
        data = resp.json()

        posts_raw: list[dict] = [
            child.get("data", {})
            for child in (data.get("data", {}).get("children") or [])
        ]

        if not posts_raw:
            return {
                "symbol": symbol,
                "subreddit": subreddit,
                "posts_found": 0,
                "sentiment_summary": "No posts found",
                "posts": [],
            }

        posts = [
            {
                "title": p.get("title"),
                "score": p.get("score") or 0,
                "upvote_ratio": p.get("upvote_ratio") or 0,
                "num_comments": p.get("num_comments") or 0,
                "created_utc": p.get("created_utc"),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "flair": p.get("link_flair_text"),
            }
            for p in posts_raw
        ]

        # Basic sentiment signal from upvote ratios
        avg_upvote_ratio = sum(p["upvote_ratio"] for p in posts) / len(posts)
        avg_score = sum(p["score"] for p in posts) / len(posts)

        if avg_upvote_ratio >= 0.80:
            sentiment_signal = "Positive 🟢"
        elif avg_upvote_ratio >= 0.60:
            sentiment_signal = "Mixed/Neutral 🟡"
        else:
            sentiment_signal = "Negative 🔴"

        return {
            "symbol": symbol,
            "subreddit": subreddit,
            "posts_found": len(posts),
            "avg_upvote_ratio": round(avg_upvote_ratio, 3),
            "avg_score": round(avg_score, 1),
            "sentiment_signal": sentiment_signal,
            "posts": posts,
        }

    return get_reddit_crypto_sentiment
