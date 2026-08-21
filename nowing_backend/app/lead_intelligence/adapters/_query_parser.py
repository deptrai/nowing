"""Lightweight query parser for multi-source real-estate adapters.

Extracts city, price range, listing type and property type from free-form
Vietnamese queries. Designed for Batdongsan and Chợ Tốt adapters only.

ponytail: this is a heuristic parser, not an NLU model. It handles the most
common Vietnamese price/city patterns and falls back to defaults/safe values
when the input is ambiguous.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.proprietary.platforms.batdongsan.city_codes import (
    CITY_CODES as BDS_CITY_CODES,
)
from app.services.location_normalize import (
    _CITY_SLUGS,
    CITY_ALIASES,
    remove_diacritics,
    resolve_city_code,
    to_slug,
)

_BDS_DEFAULT_CITY = "HN"
_CHOTOT_DEFAULT_CITY = "Hà Nội"

_PRICE_UNITS = {
    "tỷ": 1_000_000_000,
    "ty": 1_000_000_000,
    "tỉ": 1_000_000_000,
    "triệu": 1_000_000,
    "trieu": 1_000_000,
    "tr": 1_000_000,
    "ti": 1_000_000_000,
}

_PRICE_RANGE_RE = re.compile(
    r"(?:từ)?\s*(\d+[\.,]?\d*)\s*(tỷ|ty|tỉ|ti|triệu|trieu|tr)?\s*"
    r"(?:đến|den|tới|toi|-|->)\s*"
    r"(\d+[\.,]?\d*)\s*(tỷ|ty|tỉ|ti|triệu|trieu|tr)",
    re.IGNORECASE,
)
_PRICE_BELOW_RE = re.compile(
    r"(?:dưới|duoi|đến|den|tới|toi)\s+(\d+[\.,]?\d*)\s*(tỷ|ty|tỉ|ti|triệu|trieu|tr)",
    re.IGNORECASE,
)
_PRICE_ABOVE_RE = re.compile(
    r"(?:trên|từ)\s+(\d+[\.,]?\d*)\s*(tỷ|ty|tỉ|ti|triệu|trieu|tr)",
    re.IGNORECASE,
)
_PRICE_ALONE_RE = re.compile(
    r"(?:giá\s+)?(\d+[\.,]?\d*)\s*(tỷ|ty|tỉ|ti|triệu|trieu|tr)",
    re.IGNORECASE,
)

_RENT_RE = re.compile(r"\b(thuê|cho thuê|thue|cho thue)\b", re.IGNORECASE)

_PROPERTY_TYPE_RE = re.compile(
    r"\b(chung cư|chung cu|căn hộ|can ho|biệt thự|biet thu|"
    r"nhà phố|nha pho|nhà\b|nha\b|đất nền|dat nen|đất\b|dat\b|"
    r"văn phòng|van phong|mặt bằng|mat bang|nhà xưởng|nha xuong|kho|"
    r"cửa hàng|cua hang|shop)\b",
    re.IGNORECASE,
)

_PROPERTY_TYPE_MAP: dict[str, str] = {
    "chung cư": "apartment",
    "chung cu": "apartment",
    "căn hộ": "apartment",
    "can ho": "apartment",
    "biệt thự": "house",
    "biet thu": "house",
    "nhà phố": "house",
    "nha pho": "house",
    "nhà": "house",
    "nha": "house",
    "đất nền": "land",
    "dat nen": "land",
    "đất": "land",
    "dat": "land",
    "văn phòng": "office",
    "van phong": "office",
    "mặt bằng": "office",
    "mat bang": "office",
    "nhà xưởng": "land",
    "nha xuong": "land",
    "kho": "land",
    "cửa hàng": "office",
    "cua hang": "office",
    "shop": "office",
}


def _parse_amount(num_str: str, unit: str | None) -> int | None:
    """Convert a Vietnamese price string + unit to an integer VND amount."""
    if not unit:
        return None
    try:
        num_str = num_str.replace(",", ".")
        amount = Decimal(num_str)
    except (InvalidOperation, ValueError):
        return None
    multiplier = _PRICE_UNITS.get(unit.lower())
    if not multiplier:
        return None
    return int(amount * multiplier)


def _strip_price_phrases(text: str) -> str:
    """Remove common price keywords so they don't collide with city parsing."""
    return re.sub(r"(giá|gia|khoảng|tầm|tuần)\s+", " ", text, flags=re.IGNORECASE)


def _normalize_city_input(value: str) -> str:
    """Return a diacritics-free, space-separated city string for Chotot."""
    text = remove_diacritics(value or "")
    text = re.sub(r"[.,;:-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    lowered = text.lower()
    for prefix in ("tp ", "tinh ", "thanh pho ", "quan ", "huyen ", "phuong ", "xa "):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    return text


def _query_slug(text: str) -> str:
    """Make a hyphenated slug from the full query."""
    return to_slug(_strip_price_phrases(text))


def _first_location(locations: Any) -> str | None:
    if not locations:
        return None
    if isinstance(locations, str):
        locations = [locations]
    for loc in locations:
        if loc and str(loc).strip():
            return str(loc).strip()
    return None


def _resolve_city_from_query(query: str) -> tuple[str | None, str | None]:
    """Find the first known city in ``query`` and return (code, slug-or-name)."""
    if not query:
        return None, None

    slug = _query_slug(query)
    if not slug:
        return None, None

    best_code: str | None = None
    best_slug: str | None = None
    best_len = 0

    for alias, code in CITY_ALIASES.items():
        if not alias:
            continue
        pattern = r"(?:^|-)" + re.escape(alias) + r"(?:$|-)"
        if re.search(pattern, slug) and len(alias) > best_len:
            best_len = len(alias)
            best_code = code
            best_slug = _CITY_SLUGS.get(code)

    return best_code, best_slug


def resolve_batdongsan_city(query: str, filters: dict[str, Any] | None) -> str:
    """Return a Batdongsan city code, falling back to the default."""
    loc = _first_location(filters.get("locations") if filters else None)
    if loc:
        code = resolve_city_code(loc)
        if code and code in BDS_CITY_CODES:
            return code

    code, _ = _resolve_city_from_query(query)
    if code and code in BDS_CITY_CODES:
        return code

    return _BDS_DEFAULT_CITY


def resolve_chotot_city(
    query: str, filters: dict[str, Any] | None, default: str | None = _CHOTOT_DEFAULT_CITY
) -> str | None:
    """Return a Chotot-resolvable city string, falling back to the default."""
    loc = _first_location(filters.get("locations") if filters else None)
    if loc:
        normalized = _normalize_city_input(loc)
        if normalized:
            return normalized

    code, slug = _resolve_city_from_query(query)
    if slug:
        return slug.replace("-", " ")
    if code and code in _CITY_SLUGS:
        return _CITY_SLUGS[code].replace("-", " ")

    return default


def extract_price_range(query: str) -> tuple[int | None, int | None]:
    """Return ``(min_price, max_price)`` in VND from a Vietnamese query."""
    if not query:
        return None, None

    text = remove_diacritics(query)

    range_match = _PRICE_RANGE_RE.search(text)
    if range_match:
        # Shorthand ranges like "3-5 tỷ" omit the first unit; reuse the second.
        min_unit = range_match.group(2) or range_match.group(4)
        min_price = _parse_amount(range_match.group(1), min_unit)
        max_price = _parse_amount(range_match.group(3), range_match.group(4))
        if min_price is not None and max_price is not None and min_price > max_price:
            min_price, max_price = max_price, min_price
        return min_price, max_price

    max_price: int | None = None
    min_price: int | None = None

    below_match = _PRICE_BELOW_RE.search(text)
    if below_match:
        max_price = _parse_amount(below_match.group(1), below_match.group(2))

    above_match = _PRICE_ABOVE_RE.search(text)
    if above_match:
        min_price = _parse_amount(above_match.group(1), above_match.group(2))

    if min_price is None and max_price is None:
        alone_match = _PRICE_ALONE_RE.search(text)
        if alone_match:
            max_price = _parse_amount(alone_match.group(1), alone_match.group(2))

    return min_price, max_price


def extract_listing_type_bds(query: str) -> str:
    """Return 'rent' or 'buy' for Batdongsan."""
    return "rent" if _RENT_RE.search(query or "") else "buy"


def extract_listing_type_chotot(query: str) -> str:
    """Return 'rent' or 'sell' for Chợ Tốt."""
    return "rent" if _RENT_RE.search(query or "") else "sell"


def extract_property_type_chotot(query: str) -> str | None:
    """Return a Chotot property_type string or None to keep the default 'all'."""
    text = remove_diacritics(query or "")
    match = _PROPERTY_TYPE_RE.search(text)
    if not match:
        return None
    return _PROPERTY_TYPE_MAP.get(match.group(1).lower().strip(), "all")


# Muaban.net reuses the same city resolution and property type mapping as Chotot.
resolve_muaban_bds_city = resolve_chotot_city
