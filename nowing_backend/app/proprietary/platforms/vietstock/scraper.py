"""Orchestrator for the Vietstock stock/financials scraper."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from .fetch import (
    VietstockAccessBlockedError,
    VietstockAuthRefreshError,
    VietstockDecodeError,
    VietstockRateLimitedError,
    fetch_financials,
    fetch_quote,
)
from .parsers import parse_financials, parse_quote
from .schemas import VietstockScrapeInput, VietstockScrapeOutput

logger = logging.getLogger(__name__)

QuoteFn = Callable[[str], Awaitable[dict[str, Any]]]
FinancialsFn = Callable[[str], Awaitable[dict[str, Any]]]


_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}$")


def _is_valid_symbol(symbol: str | None) -> bool:
    """Validate a Vietnamese stock ticker: 1-10 uppercase letters/digits."""
    if not symbol:
        return False
    return bool(_SYMBOL_RE.match(symbol.strip().upper()))


async def scrape_vietstock(
    input_model: VietstockScrapeInput,
    *,
    quote_fn: QuoteFn | None = None,
    financials_fn: FinancialsFn | None = None,
) -> VietstockScrapeOutput:
    """Fetch and parse Vietstock data for a stock symbol.

    ``*_fn`` are test seams. Production uses the public :func:`fetch_quote`
    and :func:`fetch_financials` helpers, which include process-local rate
    limiting and cookie auth.
    """
    _quote: QuoteFn = quote_fn or fetch_quote
    _financials: FinancialsFn = financials_fn or fetch_financials

    quote: Any = None
    financials: Any = None
    degraded = False
    degradation_reason: str | None = None

    if not _is_valid_symbol(input_model.symbol):
        return VietstockScrapeOutput(
            degraded=True,
            degradation_reason="invalid symbol",
        )

    try:
        quote_raw = await _quote(input_model.symbol)
        quote = parse_quote(quote_raw, input_model.symbol)
    except VietstockRateLimitedError:
        degraded = True
        degradation_reason = "rate_limited"
    except VietstockAuthRefreshError as exc:
        logger.warning("vietstock quote auth refresh failed", exc_info=exc)
        degraded = True
        degradation_reason = str(exc)
    except VietstockDecodeError as exc:
        logger.warning("vietstock quote decode failed", exc_info=exc)
        degraded = True
        degradation_reason = "decode_error"
    except VietstockAccessBlockedError as exc:
        logger.warning("vietstock quote fetch blocked", exc_info=exc)
        degraded = True
        degradation_reason = "api_error"
    except Exception as exc:
        logger.exception("vietstock quote unexpected error: %s", exc)
        degraded = True
        degradation_reason = "api_error"

    if not degraded and input_model.include_financials:
        try:
            financials_raw = await _financials(input_model.symbol)
            financials = parse_financials(financials_raw, input_model.symbol)
        except VietstockRateLimitedError:
            degraded = True
            degradation_reason = "rate_limited"
        except VietstockAuthRefreshError as exc:
            logger.warning("vietstock financials auth refresh failed", exc_info=exc)
            degraded = True
            degradation_reason = str(exc)
        except VietstockDecodeError as exc:
            logger.warning("vietstock financials decode failed", exc_info=exc)
            degraded = True
            degradation_reason = "decode_error"
        except VietstockAccessBlockedError as exc:
            logger.warning("vietstock financials fetch blocked", exc_info=exc)
            degraded = True
            degradation_reason = "api_error"
        except Exception as exc:
            logger.exception("vietstock financials unexpected error: %s", exc)
            degraded = True
            degradation_reason = "api_error"

    if quote is None and not degraded:
        # No usable quote but no error was raised.
        degraded = True
        degradation_reason = "empty"

    return VietstockScrapeOutput(
        quote=quote,
        financials=financials,
        degraded=degraded,
        degradation_reason=degradation_reason,
    )
