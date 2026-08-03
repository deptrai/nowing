"""Pure, I/O-free parsing of Muaban.net BĐS listing data."""

from __future__ import annotations

import json
import re
from typing import Any

from .schemas import MuabanBdsListing


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _extract_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    raw = match.group(1).replace(",", ".")
    return _to_float(raw)


def _format_price(
    price_value: Any, price_display: str | None
) -> tuple[str | None, str | None, int | None]:
    raw = _normalize_whitespace(price_display)
    if raw is None:
        return None, None, None
    value = _to_int(price_value)
    return raw, raw, value


def _parse_locations_json(raw: dict[str, Any]) -> dict[str, str]:
    """Parse the ``locations`` JSON string to ward/district/city names."""
    loc = raw.get("locations")
    if not isinstance(loc, str):
        return {}
    try:
        parsed = json.loads(loc)
    except json.JSONDecodeError:
        return {}
    result: dict[str, str] = {}
    for key, label in (("w", "ward"), ("d", "district"), ("c", "city")):
        obj = parsed.get(key)
        if isinstance(obj, dict):
            name = _normalize_whitespace(obj.get("n"))
            if name:
                result[label] = name
    return result


def _extract_attributes(attributes: Any) -> dict[str, Any]:
    """Return ``{area, rooms, toilets}`` from the attribute badges."""
    result: dict[str, Any] = {
        "area": None,
        "rooms": None,
        "toilets": None,
        "area_value": None,
    }
    if not isinstance(attributes, list):
        return result
    for attr in attributes:
        if not isinstance(attr, dict):
            continue
        value = _normalize_whitespace(attr.get("value"))
        if not value:
            continue
        if result["area"] is None and (
            "m²" in value or "m2" in value or "m" in value.lower()
        ):
            result["area"] = value
            result["area_value"] = _extract_number(value)
        if result["rooms"] is None and ("PN" in value or "phòng ngủ" in value.lower()):
            result["rooms"] = _to_int(_extract_number(value))
        if result["toilets"] is None and (
            "WC" in value
            or "phòng tắm" in value.lower()
            or "phòng vệ sinh" in value.lower()
        ):
            result["toilets"] = _to_int(_extract_number(value))
    return result


def _extract_locations_display(raw: dict[str, Any]) -> dict[str, str]:
    """Fallback: derive ward/district/city from the ``locations_display`` list."""
    result: dict[str, str] = {}
    items = raw.get("locations_display") or []
    if not isinstance(items, list) or not items:
        return result
    # Heuristic: list is ordered from most-specific to least-specific.
    mapping = {0: "ward", -2: "district", -1: "city"}
    for idx, label in mapping.items():
        try:
            item = items[idx]
        except IndexError:
            continue
        name = _normalize_whitespace(item.get("name"))
        if name:
            result[label] = name
    return result


def _listing_type(raw: dict[str, Any]) -> str | None:
    """Map ``subcategory_id`` to buy/rent."""
    sub = raw.get("subcategory_id")
    if sub == 169:
        return "buy"
    if sub == 46:
        return "rent"
    return None


def _property_type(raw: dict[str, Any]) -> str | None:
    """Map Muaban category name to a normalized property type."""
    name = _normalize_whitespace(raw.get("category_name")) or ""
    lower = name.lower()
    if "căn hộ" in lower or "chung cư" in lower:
        return "apartment"
    if "đất" in lower and "nhà" not in lower:
        return "land"
    if "văn phòng" in lower or "mặt bằng" in lower or "văn phòng" in lower:
        return "office"
    if "nhà" in lower or "biệt thự" in lower or "villa" in lower:
        return "house"
    return _normalize_whitespace(raw.get("category_name"))


def _seller_type(raw: dict[str, Any]) -> str | None:
    if raw.get("is_company") is True:
        return "company"
    return "individual"


def _build_detail_url(url: str | None) -> str | None:
    if not url:
        return None
    return f"https://muaban.net{url}"


def _first_image(covers: Any) -> str | None:
    if isinstance(covers, list) and covers:
        return _normalize_whitespace(covers[0])
    return None


def parse_listing(raw: dict[str, Any]) -> MuabanBdsListing:
    """Map a single raw Muaban item to a typed listing."""
    price, price_raw, price_value = _format_price(
        raw.get("price"), raw.get("price_display")
    )
    attr = _extract_attributes(raw.get("attributes"))
    loc_json = _parse_locations_json(raw)
    loc_display = _extract_locations_display(raw)
    loc = {**loc_display, **loc_json}  # JSON takes priority

    return MuabanBdsListing(
        dataType="muaban_bds_listing",
        listing_id=_to_int(raw.get("id")),
        user_id=_to_int(raw.get("user_id")),
        title=_normalize_whitespace(raw.get("title")),
        price=price,
        price_raw=price_raw,
        price_value=price_value,
        area=attr["area"],
        area_raw=attr["area"],
        area_value=attr["area_value"],
        location=_normalize_whitespace(raw.get("location")),
        district=loc.get("district"),
        city=loc.get("city"),
        ward=loc.get("ward"),
        post_date=_normalize_whitespace(raw.get("publish_display")),
        thumbnail_url=_first_image(raw.get("covers")),
        detail_url=_build_detail_url(_normalize_whitespace(raw.get("url"))),
        listing_type=_listing_type(raw),
        property_type=_property_type(raw),
        seller_type=_seller_type(raw),
        rooms=attr["rooms"],
        toilets=attr["toilets"],
        phone=_normalize_whitespace(raw.get("phone")),
    )


def extract_listings(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the raw item list out of a Muaban Next.js payload."""
    page_props = next_data.get("props", {}).get("pageProps", {})
    for key in ("classified", "estateSell", "estateRent"):
        container = page_props.get(key)
        if isinstance(container, dict):
            items = container.get("items")
            if isinstance(items, list):
                return items
    return []


def parse_listings(raw_items: list[dict[str, Any]]) -> list[MuabanBdsListing]:
    """Map a list of raw Muaban items to typed listings."""
    if not raw_items:
        return []
    return [parse_listing(item) for item in raw_items if isinstance(item, dict)]
