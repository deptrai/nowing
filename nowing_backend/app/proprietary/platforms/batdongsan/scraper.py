"""Orchestrator for the Batdongsan scraper."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from .fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanRateLimitedError,
    fetch_listings,
)
from .parsers import parse_listings
from .schemas import BatdongsanListing, BatdongsanScrapeInput, BatdongsanScrapeOutput

FetchFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Retry a single page this many times before giving up on that page.
_MAX_RETRIES = 2


def now_iso() -> str:
    """UTC now as an ISO-8601 millisecond string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _build_page_payload(input_model: BatdongsanScrapeInput, page: int) -> dict[str, Any]:
    payload = {
        "ptype": 38 if input_model.listing_type == "buy" else 49,
        "cate": 0,
        "city": input_model.city,
        "dist": input_model.district_id if input_model.district_id is not None else -1,
        "ward": -1,
        "street": -1,
        "room": -1,
        "direct": -1,
        "minprice": input_model.min_price if input_model.min_price is not None else 0,
        "maxprice": input_model.max_price if input_model.max_price is not None else 0,
        "minarea": input_model.min_area if input_model.min_area is not None else 0,
        "maxarea": input_model.max_area if input_model.max_area is not None else 0,
        "projectid": -1,
        "sort": 0,
        "page": page,
        "searchType": 0,
        "client": "android",
        "m": "list",
        "pagesize": 20,
    }
    return payload


async def scrape_batdongsan(
    input_model: BatdongsanScrapeInput,
    *,
    limit: int | None = None,
    fetch_fn: FetchFn | None = None,
) -> BatdongsanScrapeOutput:
    """Collect listings across pages, honoring caps and degradation.

    ``fetch_fn`` is a seam for tests; production uses :func:`fetch_listings`.
    """
    fetch = fetch_fn or fetch_listings
    cap = limit if limit is not None else input_model.max_items
    max_pages = input_model.max_pages

    items: list[BatdongsanListing] = []
    degraded = False
    degradation_reason: str | None = None
    rate_limited_seen = False

    for page in range(1, max_pages + 1):
        if len(items) >= cap:
            break

        payload = _build_page_payload(input_model, page)
        page_data: list[dict[str, Any]] = []
        page_meta: Any = None
        page_failed = False

        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await fetch(payload)
                page_data = result.get("data") or []
                page_meta = result.get("m")
                break
            except BatdongsanRateLimitedError:
                rate_limited_seen = True
                if attempt < _MAX_RETRIES:
                    continue
                page_failed = True
                break
            except (BatdongsanAccessBlockedError, Exception):
                page_failed = True
                break

        if page_failed:
            degraded = True
            degradation_reason = "rate_limited" if rate_limited_seen else "api_error"
            break

        if not isinstance(page_data, list):
            page_data = []

        parsed = parse_listings(page_data)
        for listing in parsed:
            if len(items) >= cap:
                break
            items.append(listing)

        # ``m`` (more flag) is ``None`` at end of list; also stop on empty page.
        if not page_data or page_meta is None:
            break

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
