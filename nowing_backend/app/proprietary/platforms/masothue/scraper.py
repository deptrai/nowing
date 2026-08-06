"""Orchestrator for the masothue.com company scraper."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app.config import config

from .fetch import (
    MasothueAccessBlockedError,
    MasothueDecodeError,
    MasothueRateLimitedError,
    MasothueTimeoutError,
    fetch_detail_page,
    fetch_search_page,
)
from .parsers import apply_detail, parse_search_results
from .schemas import MasothueCompany, MasothueScrapeOutput, MasothueSearchInput

logger = logging.getLogger(__name__)

SearchFetchFn = Callable[[str, str, int], Awaitable[tuple[str, int]]]
DetailFetchFn = Callable[[str], Awaitable[str]]

_MAX_RETRIES = 2


def _now_iso() -> str:
    """UTC now as an ISO-8601 millisecond string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _normalize_tax_code(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace(" ", "").replace("-", "")
    return normalized if normalized else None


def _matches_filter(company: MasothueCompany, tax_code_filter: str | None) -> bool:
    if not tax_code_filter:
        return True
    company_tax = _normalize_tax_code(company.tax_code)
    return company_tax == _normalize_tax_code(tax_code_filter)


def _degrade_reason_from_exc(exc: Exception) -> str:
    if isinstance(exc, MasothueRateLimitedError):
        return "rate_limited"
    if isinstance(exc, MasothueTimeoutError):
        return "timeout"
    if isinstance(exc, MasothueDecodeError):
        return "decode_error"
    if isinstance(exc, MasothueAccessBlockedError):
        return "access_blocked"
    return "api_error"


def _page_delay() -> float:
    return max(0.0, getattr(config, "MASOTHUE_PAGE_DELAY_S", 1.0))


def _timeout() -> float:
    return max(0.0, getattr(config, "MASOTHUE_TIMEOUT_S", 30.0))


def _outcome_to_reason(
    page_failed: bool,
    rate_limited_seen: bool,
    empty: bool,
) -> str | None:
    if empty:
        return "empty"
    if rate_limited_seen:
        return "rate_limited"
    if page_failed:
        return "api_error"
    return None


async def scrape_masothue(
    input_model: MasothueSearchInput,
    *,
    search_fetch_fn: SearchFetchFn | None = None,
    detail_fetch_fn: DetailFetchFn | None = None,
) -> MasothueScrapeOutput:
    """Collect companies across pages, with optional detail resolution."""
    search_fetch = search_fetch_fn or fetch_search_page
    detail_fetch = detail_fetch_fn or fetch_detail_page

    cap = input_model.max_items
    max_pages = input_model.max_pages

    if cap == 0 or max_pages == 0:
        return MasothueScrapeOutput(items=[], total_items=0)

    items: list[MasothueCompany] = []
    seen: set[str] = set()
    degraded = False
    degradation_reason: str | None = None
    rate_limited_seen = False
    page_failed = False

    for page in range(1, max_pages + 1):
        if len(items) >= cap:
            break

        html: str | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                html, _ = await search_fetch(
                    input_model.query,
                    input_model.search_type,
                    page,
                )
                break
            except MasothueRateLimitedError:
                rate_limited_seen = True
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_page_delay())
                    continue
                page_failed = True
                break
            except MasothueDecodeError:
                degradation_reason = "decode_error"
                page_failed = True
                break
            except (MasothueAccessBlockedError, MasothueTimeoutError, Exception) as exc:
                logger.warning(
                    "masothue search page %s failed: %s", page, exc
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_page_delay())
                    continue
                degradation_reason = _degrade_reason_from_exc(exc)
                page_failed = True
                break

        if page_failed:
            degraded = True
            break

        if html is None:
            degraded = True
            degradation_reason = degradation_reason or "api_error"
            break

        page_items = parse_search_results(html)

        if page == 1 and not page_items:
            degraded = True
            degradation_reason = "empty"
            break

        if not page_items:
            break

        for company in page_items:
            if len(items) >= cap:
                break

            if not _matches_filter(company, input_model.tax_code):
                continue

            # Resolve detail page when requested.
            if input_model.resolve_detail and company.detail_url:
                try:
                    detail_html = await detail_fetch(company.detail_url)
                    apply_detail(
                        company,
                        detail_html,
                        include_phone=input_model.include_phone,
                    )
                except (MasothueAccessBlockedError, MasothueTimeoutError) as exc:
                    logger.warning(
                        "masothue detail fetch skipped for %s: %s",
                        company.detail_url,
                        exc,
                    )
                    # Skip this item; do not bill for it.
                    continue
                except MasothueDecodeError:
                    # Detail page malformed; keep the summary from search.
                    pass
                except Exception as exc:
                    logger.warning(
                        "masothue detail fetch unexpected error for %s: %s",
                        company.detail_url,
                        exc,
                    )
                    continue

            # Re-apply the tax-code filter after detail resolution.
            if not _matches_filter(company, input_model.tax_code):
                continue

            # Deduplicate by tax code or (name + detail URL).
            key = _normalize_tax_code(company.tax_code) or f"{company.name or ''}|{company.detail_url or ''}"
            if key in seen:
                continue
            seen.add(key)

            company.scrapedAt = _now_iso()
            items.append(company)

        if len(items) >= cap:
            break

        if page < max_pages:
            await asyncio.sleep(_page_delay())

    if rate_limited_seen and not degradation_reason:
        degradation_reason = "rate_limited"

    if page_failed and not degradation_reason:
        degradation_reason = "api_error"

    return MasothueScrapeOutput(
        items=items,
        total_items=len(items),
        degraded=degraded,
        degradation_reason=degradation_reason,
    )
