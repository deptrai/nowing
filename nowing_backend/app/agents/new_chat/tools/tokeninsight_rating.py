"""TokenInsight rating tools for Nowing deep agent.

Provides 2 tools for TokenInsight third-party ratings:
- get_tokeninsight_rating: Overall letter grade (A/B/C/D/F) + category scores
- get_tokeninsight_research_snippet: Latest analyst research note excerpt

All tools return {"source_domain": "tokeninsight.com", ...} so
SourceAttributionMiddleware emits citation events (AC4, Story 9-UX-1).

TokenInsight offers a free public API tier (100 req/min) for basic data.
A paid tier is available for research snippets and deeper analysis.

Environment variables:
    TOKENINSIGHT_API_KEY — Optional for free tier; required for research snippets.

Rate limits (AC14):
    Free: 100 req/min.
    Paid: custom.
"""

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import tool

from ._rate_limiter import _ApiRateLimiter

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_TI_BASE = "https://api.tokeninsight.com/api/v1"

# AC14: TokenInsight free tier = 100 req/min
_ti_rate_limit = int(os.getenv("TOKENINSIGHT_RATE_LIMIT", "100"))
_ti_rl = _ApiRateLimiter(max_calls=_ti_rate_limit, window_seconds=60.0, name="tokeninsight")

# Rating → numeric score for badge coloring
_RATING_SCORE: dict[str, int] = {"A+": 98, "A": 93, "A-": 88, "B+": 83, "B": 78, "B-": 73, "C+": 68, "C": 63, "C-": 58, "D": 40, "F": 10}


def _api_key() -> str | None:
    return os.getenv("TOKENINSIGHT_API_KEY", "").strip() or None


def _auth_headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    return {"TI_API_KEY": key}


def _unavailable_error(status: int) -> dict[str, Any]:
    messages = {
        401: "TokenInsight API key missing or invalid. Add TOKENINSIGHT_API_KEY to .env.",
        403: "TokenInsight endpoint requires paid tier.",
        429: "TokenInsight rate limit exceeded (100 req/min free). Retry later.",
    }
    return {
        "error": messages.get(status, f"TokenInsight API returned HTTP {status}"),
        "status": status,
        "source_domain": "tokeninsight.com",
    }


def create_tokeninsight_rating_tool():
    """Factory: get_tokeninsight_rating — letter grade + category scores."""

    @tool
    async def get_tokeninsight_rating(token_symbol: str) -> dict[str, Any]:
        """Get the TokenInsight third-party rating for a cryptocurrency.

        Returns an overall letter grade (A+/A/B/C/D/F), a numeric score
        (0-100), and breakdown across technology, team, ecosystem, and
        tokenomics dimensions.

        Use when user asks for a third-party rating, investment grade,
        or wants to benchmark a token against analyst standards.

        The rating badge is shown next to the Risk Badge in TokenHeroCard
        (AC11, Story 9-UX-4).

        Args:
            token_symbol: Token ticker symbol (e.g. "BTC", "ETH", "UNI").
                Case-insensitive.

        Returns:
            Dict with overall_rating (str), overall_score (int 0-100),
            categories (dict), last_updated (str),
            source_domain "tokeninsight.com", or {"error": ..., "status": ...}.
        """
        if not token_symbol or not token_symbol.strip():
            return {"error": "token_symbol is required", "source_domain": "tokeninsight.com"}

        symbol = token_symbol.strip().upper()
        await _ti_rl.acquire()

        url = f"{_TI_BASE}/coins/{symbol.lower()}/rating"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=_auth_headers())

            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            if resp.status_code == 404:
                return {
                    "error": f"Token '{symbol}' not found in TokenInsight database",
                    "status": 404,
                    "source_domain": "tokeninsight.com",
                }
            resp.raise_for_status()
            data = resp.json().get("data", {})

            overall_rating = data.get("rating", data.get("grade", "N/A"))
            overall_score = data.get("score", _RATING_SCORE.get(overall_rating, 0))

            categories = {
                "technology": data.get("technologyScore", None),
                "team": data.get("teamScore", None),
                "ecosystem": data.get("ecosystemScore", None),
                "tokenomics": data.get("tokenomicsScore", None),
            }
            categories = {k: v for k, v in categories.items() if v is not None}

            return {
                "source_domain": "tokeninsight.com",
                "symbol": symbol,
                "overall_rating": overall_rating,
                "overall_score": int(overall_score),
                "categories": categories,
                "last_updated": data.get("updatedAt", data.get("lastUpdated", "")),
                "tokeninsight_url": f"https://tokeninsight.com/en/coins/{symbol.lower()}",
            }
        except httpx.TimeoutException:
            logger.warning("tokeninsight rating timeout for %s", symbol)
            return {"error": "TokenInsight API timeout", "source_domain": "tokeninsight.com"}
        except httpx.HTTPStatusError as exc:
            logger.warning("tokeninsight rating HTTP error %s for %s", exc.response.status_code, symbol)
            return {"error": f"TokenInsight API error: {exc.response.status_code}", "source_domain": "tokeninsight.com"}
        except Exception as exc:
            logger.exception("tokeninsight rating unexpected error for %s", symbol)
            return {"error": f"Unexpected error: {exc}", "source_domain": "tokeninsight.com"}

    return get_tokeninsight_rating


def create_tokeninsight_research_snippet_tool():
    """Factory: get_tokeninsight_research_snippet — latest analyst note excerpt."""

    @tool
    async def get_tokeninsight_research_snippet(token_symbol: str) -> dict[str, Any]:
        """Get the latest TokenInsight research note excerpt for a token.

        Returns a short excerpt (≤ 500 chars) from the most recent analyst
        research note, publication date, and a link to the full report.

        Use when user asks for analyst opinion, research note, or wants
        a third-party investment thesis on a token.

        Args:
            token_symbol: Token ticker symbol (e.g. "BTC", "ETH", "UNI").

        Returns:
            Dict with excerpt (str), published_at (str), report_url (str),
            source_domain "tokeninsight.com", or {"error": ..., "status": ...}.
        """
        if not token_symbol or not token_symbol.strip():
            return {"error": "token_symbol is required", "source_domain": "tokeninsight.com"}

        symbol = token_symbol.strip().upper()

        # Research snippets require API key (paid tier)
        if not _api_key():
            return _unavailable_error(401)

        await _ti_rl.acquire()
        url = f"{_TI_BASE}/coins/{symbol.lower()}/research/latest"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=_auth_headers())

            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            if resp.status_code == 404:
                return {
                    "error": f"No research notes found for '{symbol}' on TokenInsight",
                    "status": 404,
                    "source_domain": "tokeninsight.com",
                }
            resp.raise_for_status()
            data = resp.json().get("data", {})

            full_text = data.get("content", data.get("body", ""))
            excerpt = full_text[:500].rstrip() + ("..." if len(full_text) > 500 else "")

            return {
                "source_domain": "tokeninsight.com",
                "symbol": symbol,
                "excerpt": excerpt,
                "published_at": data.get("publishedAt", data.get("createdAt", "")),
                "title": data.get("title", ""),
                "report_url": data.get("url", f"https://tokeninsight.com/en/research/{symbol.lower()}"),
            }
        except httpx.TimeoutException:
            logger.warning("tokeninsight research timeout for %s", symbol)
            return {"error": "TokenInsight API timeout", "source_domain": "tokeninsight.com"}
        except httpx.HTTPStatusError as exc:
            logger.warning("tokeninsight research HTTP error %s for %s", exc.response.status_code, symbol)
            return {"error": f"TokenInsight API error: {exc.response.status_code}", "source_domain": "tokeninsight.com"}
        except Exception as exc:
            logger.exception("tokeninsight research unexpected error for %s", symbol)
            return {"error": f"Unexpected error: {exc}", "source_domain": "tokeninsight.com"}

    return get_tokeninsight_research_snippet
