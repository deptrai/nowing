"""Orchestrator for the Chợ Tốt Nhà BĐS scraper."""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.config import config

from .fetch import (
    ChototBdsAccessBlockedError,
    ChototBdsBotDetectedError,
    ChototBdsDecodeError,
    ChototBdsRateLimitedError,
    fetch_listings,
    fetch_phone,
    load_regions,
)
from .parsers import parse_listings
from .schemas import ChototBdsListing, ChototBdsScrapeInput, ChototBdsScrapeOutput

logger = logging.getLogger(__name__)

FetchFn = Callable[..., Awaitable[dict[str, Any]]]
RegionsFn = Callable[[], Awaitable[dict[str, Any]]]

_MAX_RETRIES = 2
_PAGE_SIZE = 20

_PROPERTY_TYPE_TO_CG: dict[str, int] = {
    "all": 1000,
    "apartment": 1010,
    "house": 1020,
    "office": 1030,
    "land": 1040,
}

_CITY_ALIASES: dict[str, str] = {
    "hn": "hà nội",
    "hanoi": "hà nội",
    "ha noi": "hà nội",
    "sg": "hồ chí minh",
    "hcm": "hồ chí minh",
    "ho chi minh": "hồ chí minh",
    "tp hcm": "hồ chí minh",
    "tp ho chi minh": "hồ chí minh",
    "dn": "đà nẵng",
    "da nang": "đà nẵng",
    "hp": "hải phòng",
    "hai phong": "hải phòng",
    "ct": "cần thơ",
    "can tho": "cần thơ",
}


def _now_iso() -> str:
    """UTC now as an ISO-8601 millisecond string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _normalize_text(value: str) -> str:
    """Lowercase, strip and remove diacritics for fuzzy matching."""
    text = value.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Strip common prefixes so "TP Ho Chi Minh" matches "Ho Chi Minh".
    for prefix in ("tp ", "tinh ", "thanh pho ", "quan ", "huyen ", "phuong ", "xa "):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    return text


def _extract_entities(regions_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the ``regions`` dict from a ``loadRegions`` response."""
    return (
        regions_payload.get("regionFollowId", {}).get("entities", {}).get("regions", {})
    )


def _resolve_region_v2(city: str, regions: dict[str, Any]) -> int:
    """Resolve a city name/alias to a ``region_v2`` code."""
    city_norm = _normalize_text(city)
    alias = _CITY_ALIASES.get(city_norm)
    if alias:
        city_norm = _normalize_text(alias)

    # Try direct numeric first.
    try:
        return int(city)
    except (ValueError, OverflowError):
        pass

    for region_id, region in regions.items():
        name = region.get("name", "")
        if not isinstance(name, str) or not name:
            continue
        if _normalize_text(name) == city_norm:
            try:
                return int(region_id)
            except (ValueError, OverflowError):
                continue

    raise ValueError(f"Unknown Chotot city: {city}")


def _resolve_area_v2(
    district_query: str | None,
    district_id: int | None,
    region_id: int,
    regions: dict[str, Any],
) -> int | None:
    """Resolve a district name or numeric id to an ``area_v2`` code."""
    if district_id is not None:
        if district_id < 0:
            raise ValueError(f"Invalid negative district_id: {district_id}")
        return district_id
    if not district_query:
        return None

    try:
        parsed = int(district_query)
        if parsed < 0:
            raise ValueError(f"Invalid negative district query: {district_query}")
        return parsed
    except (ValueError, OverflowError):
        pass

    region = regions.get(str(region_id), {})
    areas = region.get("area", {})
    if not isinstance(areas, dict):
        areas = {}
    query_norm = _normalize_text(district_query)

    # Exact match only; substring fallback removed to avoid false positives.
    for area_id, area in areas.items():
        name = area.get("name", "")
        if not isinstance(name, str) or not name:
            continue
        if _normalize_text(name) == query_norm:
            try:
                parsed = int(area_id)
                if parsed < 0:
                    continue
                return parsed
            except (ValueError, OverflowError):
                continue

    raise ValueError(f"Unknown Chotot district: {district_query}")


def _page_delay() -> float:
    """Pacing between page requests."""
    return max(0.0, getattr(config, "CHOTOT_BDS_PAGE_DELAY_S", 0.5))


def _build_page_payload(
    input_model: ChototBdsScrapeInput,
    *,
    page: int,
    region_v2: int,
    area_v2: int | None,
) -> dict[str, Any]:
    cg = _PROPERTY_TYPE_TO_CG.get(input_model.property_type, 1000)
    return {
        "region_v2": region_v2,
        "area_v2": area_v2,
        "cg": cg,
        "listing_type": input_model.listing_type,
        "page": page,
        "page_size": _PAGE_SIZE,
        "min_price": input_model.min_price,
        "max_price": input_model.max_price,
        "min_area": input_model.min_area,
        "max_area": input_model.max_area,
    }


async def scrape_chotot_bds(
    input_model: ChototBdsScrapeInput,
    *,
    limit: int | None = None,
    fetch_fn: FetchFn | None = None,
    regions_fn: RegionsFn | None = None,
) -> ChototBdsScrapeOutput:
    """Collect BĐS listings across pages, honoring caps and degradation."""
    fetch = fetch_fn or fetch_listings
    load = regions_fn or load_regions

    try:
        regions_payload = await load()
    except (
        ChototBdsAccessBlockedError,
        ChototBdsRateLimitedError,
        ChototBdsDecodeError,
    ):
        raise
    except Exception:
        return ChototBdsScrapeOutput(
            items=[],
            total_items=0,
            degraded=True,
            degradation_reason="api_error",
        )

    regions = _extract_entities(regions_payload)
    try:
        region_v2 = _resolve_region_v2(input_model.city, regions)
        area_v2 = _resolve_area_v2(
            getattr(input_model, "district", None),
            input_model.district_id,
            region_v2,
            regions,
        )
    except ValueError as exc:
        return ChototBdsScrapeOutput(
            items=[],
            total_items=0,
            degraded=True,
            degradation_reason=f"invalid_input: {exc}",
        )

    cap = max(0, limit if limit is not None else input_model.max_items)
    max_pages = input_model.max_pages

    items: list[ChototBdsListing] = []
    seen_ids: set[int] = set()
    degraded = False
    degradation_reason: str | None = None

    for page in range(1, max_pages + 1):
        if len(items) >= cap:
            break

        payload = _build_page_payload(
            input_model,
            page=page,
            region_v2=region_v2,
            area_v2=area_v2,
        )
        page_data: list[dict[str, Any]] = []
        page_total = 0
        page_failed = False

        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await fetch(**payload)
                ads = result.get("ads") or []
                # ``total`` may be missing or 0; trust ``len(ads)`` for pagination.
                page_total = int(result.get("total") or len(ads))
                if not isinstance(ads, list):
                    degradation_reason = "layout_changed"
                    page_failed = True
                    break
                # If the response has no ``ads`` key at all, the layout likely changed.
                if "ads" not in result:
                    degradation_reason = "layout_changed"
                    page_failed = True
                    break
                page_data = ads
                break
            except ChototBdsRateLimitedError:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_page_delay())
                    continue
                page_failed = True
                degradation_reason = "rate_limited"
                break
            except ChototBdsDecodeError:
                degradation_reason = "decode_error"
                page_failed = True
                break
            except ChototBdsBotDetectedError:
                page_failed = True
                degradation_reason = "bot_detected"
                break
            except (ChototBdsAccessBlockedError, Exception):
                page_failed = True
                break

        if page_failed:
            if degradation_reason is None:
                degradation_reason = "api_error"
            degraded = True
            break

        # An empty first page means the constraints matched nothing.
        if page == 1 and not page_data:
            degraded = True
            degradation_reason = "empty"
            break

        for listing in parse_listings(page_data):
            if len(items) >= cap:
                break
            if listing.listing_id is not None:
                if listing.listing_id in seen_ids:
                    continue
                seen_ids.add(listing.listing_id)
            items.append(listing)

        # Stop when we have seen the whole result set.
        offset = page * _PAGE_SIZE
        if not page_data or (page_total and offset >= page_total):
            break

        if page < max_pages and len(items) < cap:
            await asyncio.sleep(_page_delay())

    for item in items:
        item.scrapedAt = _now_iso()

    # Attempt to resolve the public phone number for each listing.
    # This is a best-effort call: if the phone API blocks us we keep the
    # listing and leave ``phone`` as ``None``.
    if items:
        _phone_semaphore = asyncio.Semaphore(3)

        async def _resolve_phone(item: ChototBdsListing) -> None:
            if not item.listing_id:
                return
            try:
                async with _phone_semaphore:
                    item.phone = await fetch_phone(item.listing_id)
                    await asyncio.sleep(_page_delay())
            except Exception:
                logger.exception("failed to resolve phone for list_id=%s", item.listing_id)

        await asyncio.gather(*(_resolve_phone(item) for item in items))

    return ChototBdsScrapeOutput(
        items=items,
        total_items=len(items),
        degraded=degraded,
        degradation_reason=degradation_reason,
    )
