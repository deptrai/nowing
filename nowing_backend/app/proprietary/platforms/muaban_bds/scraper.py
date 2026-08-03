"""Muaban.net BĐS scraper: browser-backed listing extraction."""

from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
from typing import Any

from app.config import config

from .fetch import (
    AsyncStealthySession,
    MuabanBdsAccessBlockedError,
    MuabanBdsDecodeError,
    MuabanBdsRateLimitedError,
    fetch_page,
)
from .parsers import extract_listings, parse_listing
from .schemas import MuabanBdsListing, MuabanBdsScrapeInput, MuabanBdsScrapeOutput

logger = logging.getLogger(__name__)

BASE_ORIGIN = "https://muaban.net"

# Slug mapping derived from Muaban's filter/quicklink URLs.
# ``all`` is the root listing type slug; others are property subcategories.
_PROPERTY_SLUGS: dict[str, dict[str, str]] = {
    "buy": {
        "all": "ban-nha-dat-chung-cu",
        "house": "ban-nha",
        "apartment": "ban-can-ho",
        "land": "ban-dat",
        "office": "ban-nha-dat-chung-cu",
    },
    "rent": {
        "all": "cho-thue-nha-dat",
        "house": "cho-thue-nha",
        "apartment": "cho-thue-can-ho",
        "land": "cho-thue-nha-xuong-kho-dat",
        "office": "cho-thue-van-phong-mat-bang",
    },
}

_CITY_ALIASES: dict[str, str] = {
    # North
    "ha noi": "ha-noi",
    "hà nội": "ha-noi",
    "hn": "ha-noi",
    "ha-noi": "ha-noi",
    # Central
    "da nang": "da-nang",
    "đà nẵng": "da-nang",
    "dn": "da-nang",
    "hai phong": "hai-phong",
    "hải phòng": "hai-phong",
    # South
    "ho chi minh": "ho-chi-minh",
    "hồ chí minh": "ho-chi-minh",
    "hcm": "ho-chi-minh",
    "tp hcm": "ho-chi-minh",
    "tp.hcm": "ho-chi-minh",
    "tphcm": "ho-chi-minh",
    "can tho": "can-tho",
    "cần thơ": "can-tho",
}


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().strip()


def _resolve_city_slug(name: str) -> str | None:
    """Resolve a city name or slug to a Muaban city slug."""
    if all(c == "-" or c.isalnum() for c in name) and "-" in name:
        return name.strip().lower()
    return _CITY_ALIASES.get(_normalize_text(name))


def _property_slug(listing_type: str, property_type: str) -> str:
    return _PROPERTY_SLUGS.get(listing_type, {}).get(
        property_type, _PROPERTY_SLUGS["buy"]["all"]
    )


def _build_base_path(listing_type: str, property_type: str, city_slug: str) -> str:
    prop_slug = _property_slug(listing_type, property_type)
    return f"/bat-dong-san/{prop_slug}-{city_slug}"


def _matches_district(query: str, name: str) -> bool:
    """Fuzzy compare Vietnamese district names ignoring diacritics & spacing."""
    q = _normalize_text(query).replace(" ", "")
    n = _normalize_text(name).replace(" ", "")
    if q == n:
        return True
    if q.startswith("quan") and n.startswith("quận"):
        return q[4:] in n or n[4:] in q
    if q.startswith("huyen") and n.startswith("huyện"):
        return q[5:] in n or n[5:] in q
    return q in n or n in q


def _find_district_url(
    district_query: str, quicklinks: list[dict[str, Any]], default_path: str
) -> str | None:
    """Find the quicklink URL whose district name matches ``district_query``."""
    for item in quicklinks or []:
        name = item.get("name", "")
        if _matches_district(district_query, name):
            return _normalize_whitespace(item.get("url"))
    # Fallback: if the query already looks like a slug, try appending it.
    q = _normalize_text(district_query).replace(" ", "-")
    return f"{default_path}-{q}" if q else None


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _page_delay() -> float:
    return max(0.0, getattr(config, "MUABAN_BDS_PAGE_DELAY_S", 1.0))


def _item_passes_filters(
    item: MuabanBdsListing,
    input_model: MuabanBdsScrapeInput,
) -> bool:
    """Apply price/area filters after parsing."""
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


async def _open_session() -> Any:
    """Create a browser session for the Muaban scrape run."""
    from app.utils.proxy import get_proxy_url

    if AsyncStealthySession is None:
        raise MuabanBdsAccessBlockedError(
            "AsyncStealthySession not available; Muaban requires a browser"
        )

    proxy = get_proxy_url()
    session = AsyncStealthySession(
        headless=True,
        solve_cloudflare=True,
        real_chrome=True,
        proxy=proxy,
        disable_resources=True,
        extra_headers={
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.com/",
        },
    )
    await session.start()
    return session


async def _resolve_district_path(
    session: Any,
    base_url: str,
    district_query: str | None,
) -> tuple[str, bool]:
    """Return the final full URL and whether resolution succeeded."""
    if not district_query:
        return base_url, True

    page_data = await fetch_page(f"{base_url}?page=1", session=session)
    if page_data.get("notFound"):
        return base_url, False

    page_props = page_data.get("props", {}).get("pageProps", {})
    quicklinks = (
        page_props.get("quicklink", {}).get("district", {}).get("items", []) or []
    )
    base_path = base_url.removeprefix(BASE_ORIGIN)
    district_url = _find_district_url(district_query, quicklinks, base_path)
    if district_url and not district_url.startswith("http"):
        district_url = f"{BASE_ORIGIN}{district_url}"
    if not district_url or district_url == base_url:
        return base_url, False
    return district_url, True


async def scrape_muaban_bds(
    input_model: MuabanBdsScrapeInput,
    *,
    limit: int | None = None,
) -> MuabanBdsScrapeOutput:
    """Scrape Muaban.net BĐS listings for the requested city/district."""
    start = time.perf_counter()
    max_items = min(limit or input_model.max_items, input_model.max_items)
    max_pages = min(max(input_model.max_pages, 1), 20)

    city_slug = _resolve_city_slug(input_model.city)
    if not city_slug:
        return MuabanBdsScrapeOutput(
            degraded=True,
            degradation_reason=f"unknown_city:{input_model.city}",
        )

    base_path = _build_base_path(
        input_model.listing_type, input_model.property_type, city_slug
    )
    base_url = f"{BASE_ORIGIN}{base_path}"

    session = None
    try:
        session = await _open_session()
        search_url, ok = await _resolve_district_path(
            session, base_url, input_model.district
        )
        if not ok and input_model.district:
            return MuabanBdsScrapeOutput(
                degraded=True,
                degradation_reason=f"unknown_district:{input_model.district}",
            )

        listings: list[MuabanBdsListing] = []
        seen_ids: set[int] = set()

        for page_number in range(1, max_pages + 1):
            url = f"{search_url}?page={page_number}"
            try:
                page_data = await fetch_page(url, session=session)
            except MuabanBdsRateLimitedError:
                return MuabanBdsScrapeOutput(
                    items=listings,
                    total_items=len(listings),
                    degraded=True,
                    degradation_reason="rate_limited",
                )
            except (MuabanBdsAccessBlockedError, MuabanBdsDecodeError) as exc:
                logger.exception("muaban_bds page fetch failed: %s", exc)
                return MuabanBdsScrapeOutput(
                    items=listings,
                    total_items=len(listings),
                    degraded=True,
                    degradation_reason="api_error",
                )

            if page_data.get("notFound"):
                if page_number == 1:
                    return MuabanBdsScrapeOutput(
                        items=listings,
                        total_items=len(listings),
                        degraded=True,
                        degradation_reason="not_found",
                    )
                break

            raw_items = extract_listings(page_data)
            if not raw_items:
                break

            for raw in raw_items:
                if len(listings) >= max_items:
                    break
                listing_id = raw.get("id")
                if listing_id in seen_ids:
                    continue
                seen_ids.add(listing_id)
                try:
                    listing = parse_listing(raw)
                except Exception:
                    logger.exception("failed to parse Muaban item id=%s", listing_id)
                    continue
                if not _item_passes_filters(listing, input_model):
                    continue
                listings.append(listing)

            if len(listings) >= max_items:
                break
            if page_number < max_pages:
                await asyncio.sleep(_page_delay())

        logger.info(
            "[muaban_bds][perf] city=%s district=%s pages=%d items=%d elapsed_ms=%.1f",
            input_model.city,
            input_model.district,
            page_number,
            len(listings),
            (time.perf_counter() - start) * 1000,
        )
        return MuabanBdsScrapeOutput(
            items=listings,
            total_items=len(listings),
            degraded=False,
        )
    except Exception as exc:
        logger.exception("muaban_bds scraper failed: %s", exc)
        return MuabanBdsScrapeOutput(
            degraded=True,
            degradation_reason="scraper_error",
        )
    finally:
        if session is not None and hasattr(session, "close"):
            try:
                await session.close()
            except Exception as close_exc:
                logger.warning("Muaban session close failed: %s", close_exc)
