"""Orchestrator for the CafeF stock/financials/news scraper."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .fetch import (
    CafeFAccessBlockedError,
    CafeFDecodeError,
    CafeFRateLimitedError,
    fetch_financials,
    fetch_news,
    fetch_quote,
)
from .parsers import parse_financials, parse_news, parse_quote
from .schemas import CafeFScrapeInput, CafeFScrapeOutput

logger = logging.getLogger(__name__)

QuoteFn = Callable[[str], Awaitable[dict[str, Any]]]
FinancialsFn = Callable[[str], Awaitable[dict[str, Any]]]
NewsFn = Callable[[str, int], Awaitable[list[dict[str, Any]]]]


async def scrape_cafef(
    input_model: CafeFScrapeInput,
    *,
    quote_fn: QuoteFn | None = None,
    financials_fn: FinancialsFn | None = None,
    news_fn: NewsFn | None = None,
) -> CafeFScrapeOutput:
    """Fetch and parse CafeF data for a stock symbol.

    ``*_fn`` are test seams. Production uses the public :func:`fetch_*`
    helpers, which include process-local rate limiting.
    """
    _quote: QuoteFn = quote_fn or fetch_quote
    _financials: FinancialsFn = financials_fn or fetch_financials
    _news: NewsFn = news_fn or fetch_news

    quote: Any = None
    financials: Any = None
    news: list[Any] = []
    degraded = False
    degradation_reason: str | None = None

    try:
        quote_raw = await _quote(input_model.symbol)
        quote = parse_quote(quote_raw, input_model.symbol)
    except CafeFRateLimitedError:
        degraded = True
        degradation_reason = "rate_limited"
    except CafeFDecodeError as exc:
        logger.warning("cafef quote decode failed", exc_info=exc)
        degraded = True
        degradation_reason = "decode_error"
    except CafeFAccessBlockedError as exc:
        logger.warning("cafef quote fetch failed", exc_info=exc)
        degraded = True
        degradation_reason = "api_error"
    except Exception as exc:
        logger.exception("cafef quote unexpected error: %s", exc)
        degraded = True
        degradation_reason = "api_error"

    if not degraded and input_model.include_financials:
        try:
            financials_raw = await _financials(input_model.symbol)
            financials = parse_financials(financials_raw, input_model.symbol)
        except CafeFRateLimitedError:
            degraded = True
            degradation_reason = "rate_limited"
        except CafeFDecodeError as exc:
            logger.warning("cafef financials decode failed", exc_info=exc)
            degraded = True
            degradation_reason = "decode_error"
        except CafeFAccessBlockedError as exc:
            logger.warning("cafef financials fetch failed", exc_info=exc)
            degraded = True
            degradation_reason = "api_error"
        except Exception as exc:
            logger.exception("cafef financials unexpected error: %s", exc)
            degraded = True
            degradation_reason = "api_error"

    if not degraded and input_model.include_news:
        try:
            news_raw = await _news(
                input_model.symbol, max_news=input_model.max_news
            )
            news = parse_news(
                news_raw, input_model.symbol, max_news=input_model.max_news
            )
        except CafeFRateLimitedError:
            # News is optional; do not fail the whole scrape for missing news.
            logger.warning("cafef news rate limited")
        except CafeFDecodeError as exc:
            logger.warning("cafef news decode failed", exc_info=exc)
        except CafeFAccessBlockedError as exc:
            logger.warning("cafef news fetch failed", exc_info=exc)
        except Exception as exc:
            logger.exception("cafef news unexpected error: %s", exc)

    if quote is None and not degraded:
        # No usable quote but no error was raised.
        degraded = True
        degradation_reason = "empty"

    return CafeFScrapeOutput(
        quote=quote,
        financials=financials,
        news=news,
        degraded=degraded,
        degradation_reason=degradation_reason,
    )
