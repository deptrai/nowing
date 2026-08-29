"""Orchestrator for the Batdongsan scraper."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.config import config
from app.db import async_session_maker
from app.services.scraper_platform_account_service import (
    RateLimit,
    ScraperPlatformAccountRotator,
    ScraperPlatformAccountService,
)
from app.services.scraper_rule_metrics import record_failure, record_success

from .fetch import (
    AsyncStealthySession,
    BatdongsanAccessBlockedError,
    BatdongsanAccountRestrictedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
    _access_token_expires_at,
    fetch_detail_phone,
    fetch_listings,
    resolve_detail_urls,
)
from .parsers import (
    build_detail_url,
    extract_phone_from_title,
    parse_listings,
)
from .schemas import BatdongsanListing, BatdongsanScrapeInput, BatdongsanScrapeOutput

logger = logging.getLogger(__name__)

FetchFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Phone detail fetches are slow and expensive; bound concurrency and per-call
# wall time so a run does not wait on many sequential browser sessions.
_MAX_PHONE_CONCURRENCY = 2
_PHONE_RESOLVE_TIMEOUT_S = 60.0


def now_iso() -> str:
    """UTC now as an ISO-8601 millisecond string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _build_page_payload(
    input_model: BatdongsanScrapeInput, page: int
) -> dict[str, Any]:
    payload = {
        "ptype": 38 if input_model.listing_type == "buy" else 49,
        "cate": 0,
        "city": input_model.city,
        "dist": input_model.district_id if input_model.district_id is not None else -1,
        "ward": -1,
        "street": -1,
        "room": -1,
        "direct": -1,
        "minprice": 0,
        "maxprice": 0,
        "minarea": 0,
        "maxarea": 0,
        "projectid": -1,
        "sort": 0,
        "page": page,
        "searchType": 0,
        "client": "android",
        "m": "list",
        "pagesize": 20,
    }
    return payload


def _item_passes_filters(
    item: BatdongsanListing, input_model: BatdongsanScrapeInput
) -> bool:
    """Apply price/area filters client-side after parsing."""
    if input_model.min_price is not None and (
        item.price_value is None or item.price_value < input_model.min_price
    ):
        return False
    if input_model.max_price is not None and (
        item.price_value is None or item.price_value > input_model.max_price
    ):
        return False
    if input_model.min_area is not None and (
        item.area_value is None or item.area_value < input_model.min_area
    ):
        return False
    return not (
        input_model.max_area is not None
        and (item.area_value is None or item.area_value > input_model.max_area)
    )


def _web_fallback_applicable(input_model: BatdongsanScrapeInput) -> bool:
    """Web fallback only for city-level queries without price/area bounds.

    The SSR URL cannot express district or numeric filters, so falling back
    for filtered queries would return results that violate the user's
    constraints.
    """
    return (
        input_model.district_id is None
        and input_model.min_price is None
        and input_model.max_price is None
        and input_model.min_area is None
        and input_model.max_area is None
    )


async def scrape_batdongsan(
    input_model: BatdongsanScrapeInput,
    *,
    limit: int | None = None,
    fetch_fn: FetchFn | None = None,
    web_fetch_fn: FetchFn | None = None,
    resolve_phones: bool = False,
) -> BatdongsanScrapeOutput:
    """Collect listings across pages, honoring caps and degradation.

    ``fetch_fn`` is a seam for tests; production uses :func:`fetch_listings`.
    ``web_fetch_fn`` is an optional SSR web fallback used when the mobile API
    returns an empty first page for a city-level query (e.g. provinces not
    indexed by the mobile API).
    """
    fetch = fetch_fn or fetch_listings
    cap = limit if limit is not None else input_model.max_items
    max_pages = input_model.max_pages

    items: list[BatdongsanListing] = []
    seen_ids: set[int] = set()
    degraded = False
    degradation_reason: str | None = None
    rate_limited_seen = False
    using_web = False

    for page in range(1, max_pages + 1):
        if len(items) >= cap:
            break

        payload = _build_page_payload(input_model, page)
        page_data: list[dict[str, Any]] = []
        page_meta: Any = None
        page_failed = False

        active_fetch = web_fetch_fn if using_web else fetch
        try:
            result = await active_fetch(payload)
            page_data = result.get("data") or []
            page_meta = result.get("m")
            await record_success("batdongsan")
        except BatdongsanDecodeError:
            degraded = True
            degradation_reason = "decode_error"
            page_failed = True
            await record_failure("batdongsan")
        except BatdongsanRateLimitedError:
            rate_limited_seen = True
            page_failed = True
            await record_failure("batdongsan")
        except (BatdongsanAccessBlockedError, Exception):
            page_failed = True
            await record_failure("batdongsan")

        # Web fallback: only on page 1 when mobile gave nothing, the
        # query is city-level, and a web fetcher is wired.
        if (
            page == 1
            and not page_data
            and not page_failed
            and web_fetch_fn is not None
            and _web_fallback_applicable(input_model)
        ):
            try:
                web_result = await web_fetch_fn(payload)
                web_data = web_result.get("data") or []
                if web_data:
                    page_data = web_data
                    page_meta = web_result.get("m")
                    using_web = True
                    logger.info(
                        "[batdongsan] web fallback engaged for city=%s "
                        "page=%s (%d items)",
                        input_model.city,
                        page,
                        len(web_data),
                    )
            except BatdongsanRateLimitedError:
                rate_limited_seen = True
            except (BatdongsanAccessBlockedError, BatdongsanDecodeError, Exception):
                pass

        if page_failed:
            if degradation_reason is None:
                degradation_reason = (
                    "rate_limited" if rate_limited_seen else "api_error"
                )
            degraded = True
            break

        if not isinstance(page_data, list):
            degraded = True
            degradation_reason = "api_error"
            break

        # An empty first page means the district/constraints matched nothing —
        # a user mistake or an invalid ``dist``, not a normal end of results.
        if page == 1 and not page_data:
            degraded = True
            degradation_reason = "empty"
            break

        for listing in parse_listings(page_data):
            if len(items) >= cap:
                break
            if not _item_passes_filters(listing, input_model):
                continue
            # Promoted listings can repeat across pages; dedupe so the same
            # listing is never returned (or billed) twice.
            if listing.listing_id is not None:
                if listing.listing_id in seen_ids:
                    continue
                seen_ids.add(listing.listing_id)
            items.append(listing)

        # ``m`` (more flag) is ``None`` at end of list; also stop on empty page.
        if not page_data or page_meta is None:
            break

        # Inter-page pacing is handled inside fetch_listings / fetch_web_listings
        # via ``delays.request_ms`` from the active scraper rule.

    # Best-effort: resolve detail URLs and then fetch phone numbers.  The
    # mobile ``p_sync`` API no longer reliably includes ``url``, so we
    # construct a canonical detail URL from the listing id, city and title
    # before falling back to the slower web-listing resolver.
    # Full phone numbers are usually gated by login/OTP, so we also keep a
    # masked ``phone_display`` and fall back to extracting a number from the
    # title (e.g. ``LH: 0916754123``) when the detail page cannot unmask it.
    if resolve_phones:
        try:
            for item in items:
                if not item.detail_url and item.listing_id is not None:
                    item.detail_url = build_detail_url(
                        item.listing_id,
                        item.title,
                        input_model.city,
                        listing_type=input_model.listing_type,
                    )

            if AsyncStealthySession is not None:
                async with async_session_maker() as session:
                    service = ScraperPlatformAccountService(session)
                    limit = RateLimit(
                        requests_per_minute=config.BATDONGSAN_PHONE_RPM,
                        burst=config.BATDONGSAN_PHONE_BURST,
                        cooldown_seconds=config.BATDONGSAN_PHONE_COOLDOWN_S,
                        max_consecutive_failures=config.BATDONGSAN_PHONE_MAX_CONSECUTIVE_FAILURES,
                    )
                    rotator = ScraperPlatformAccountRotator(
                        service, "batdongsan", limit
                    )

                    # Grab one account for the (rare) web-listing resolver.
                    _web_account, web_credentials = await rotator.get_credentials(
                        wait=False, timeout=5.0
                    )

                    # Only page-scan if construction left gaps (unknown city, etc.).
                    if any(item.detail_url is None for item in items):
                        await resolve_detail_urls(
                            input_model,
                            items,
                            credentials=web_credentials,
                            web_fetch_fn=web_fetch_fn,
                        )

                    semaphore = asyncio.Semaphore(_MAX_PHONE_CONCURRENCY)

                    async def _resolve_phone(item: BatdongsanListing) -> None:
                        if not item.detail_url:
                            return

                        phone: str | None = None
                        phone_display: str | None = None

                        account, credentials = await rotator.get_credentials(
                            wait=True, timeout=60.0
                        )
                        if not credentials:
                            logger.warning(
                                "No batdongsan account available for phone resolve; "
                                "falling back to title extraction"
                            )
                        else:
                            token_exp = _access_token_expires_at(credentials)
                            token_fresh = (
                                token_exp is not None and token_exp - time.time() > 60
                            )
                            if token_exp is not None and not token_fresh:
                                logger.warning(
                                    "Batdongsan access token expired; phone unmasking skipped"
                                )

                            if token_fresh:
                                async with semaphore:
                                    try:
                                        async with asyncio.timeout(
                                            _PHONE_RESOLVE_TIMEOUT_S
                                        ):
                                            (
                                                phone,
                                                phone_display,
                                            ) = await fetch_detail_phone(
                                                item.detail_url, credentials=credentials
                                            )
                                        await rotator.record_use(account, success=True)
                                    except TimeoutError:
                                        logger.warning(
                                            "Batdongsan phone resolve timed out for %s",
                                            item.detail_url,
                                        )
                                        await rotator.record_use(account, success=False)
                                    except BatdongsanAccountRestrictedError as exc:
                                        logger.warning(
                                            "Batdongsan account restricted for %s: %s",
                                            item.detail_url,
                                            exc,
                                        )
                                        await rotator.record_use(
                                            account,
                                            success=False,
                                            error_type="restricted",
                                        )
                                    except BatdongsanRateLimitedError:
                                        logger.warning(
                                            "Batdongsan rate limited for %s",
                                            item.detail_url,
                                        )
                                        await rotator.record_use(
                                            account,
                                            success=False,
                                            error_type="rate_limited",
                                        )
                                    except Exception:
                                        logger.exception(
                                            "Batdongsan phone resolve failed for %s",
                                            item.detail_url,
                                        )
                                        await rotator.record_use(account, success=False)

                        if phone:
                            item.phone = phone
                            item.phone_display = phone
                        elif phone_display:
                            item.phone_display = phone_display
                        if not item.phone and item.title:
                            title_phone = extract_phone_from_title(item.title)
                            if title_phone:
                                item.phone = title_phone
                                item.phone_display = title_phone

                    await asyncio.gather(*(_resolve_phone(item) for item in items))
        except Exception:
            logger.exception("batdongsan detail/phone resolution failed")

    for item in items:
        item.scrapedAt = now_iso()

    if rate_limited_seen:
        degraded = True
        degradation_reason = "rate_limited"

    return BatdongsanScrapeOutput(
        items=items,
        total_items=len(items),
        degraded=degraded,
        degradation_reason=degradation_reason,
    )
