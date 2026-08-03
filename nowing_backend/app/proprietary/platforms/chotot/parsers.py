"""Pure, I/O-free parsing of Chợ Tốt Nhà BĐS listing data."""

from __future__ import annotations

import re
from typing import Any

from .schemas import ChototBdsListing


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _parse_price_string(raw: str) -> int | None:
    """Parse Vietnamese price strings such as \"6,3 tỷ\" or \"5 triệu\" into VND."""
    lowered = raw.lower()
    if re.search(r"/[mм]\s*²?|m²|m2|/m", lowered):
        # Per-square-meter prices cannot be converted to a total without area.
        return None

    # Extract the first numeric token, accepting comma or dot as decimal separator.
    match = re.search(r"[\d.,]+", raw)
    if not match:
        return None

    num_str = match.group(0).replace(",", ".")
    try:
        value = float(num_str)
    except ValueError:
        return None

    multiplier = 1
    if re.search(r"(tỷ|tỉ|ty)\b", lowered):
        multiplier = 1_000_000_000
    elif re.search(r"\btriệu\b|(^|\s|\d)tr(\b|\.)", lowered):
        multiplier = 1_000_000
    elif re.search(r"\b(nghìn|ngàn)\b|\bk\b", lowered):
        multiplier = 1_000

    result = value * multiplier
    if result > 1e15:
        return None
    try:
        return int(result)
    except (OverflowError, ValueError):
        return None


def _format_price(
    price_value: Any, price_string: str | None
) -> tuple[str | None, str | None, int | None]:
    """Return ``(price, price_raw, price_value)`` from a Chotot price."""
    raw = _normalize_whitespace(price_string)
    if raw is None:
        return None, None, None
    if isinstance(price_value, (int, float)) and not isinstance(price_value, bool):
        return raw, raw, int(price_value)
    parsed = _parse_price_string(raw)
    if parsed is not None:
        return raw, raw, parsed
    # Non-numeric strings like "Thỏa thuận" are kept in price_raw only.
    return None, raw, None


def _format_area(
    size_value: Any, size_unit: str | None
) -> tuple[str | None, str | None, float | None]:
    """Return ``(area, area_raw, area_value)`` from size fields."""
    if not isinstance(size_value, (int, float)) or isinstance(size_value, bool):
        return None, None, None
    try:
        size_float = float(size_value)
    except (ValueError, OverflowError):
        return None, None, None
    if not (0 < size_float < 1_000_000) or size_float != size_float:  # reject NaN/inf
        return None, None, None
    unit = _normalize_whitespace(size_unit) or "m²"
    raw = f"{size_value} {unit}"
    return raw, raw, size_float


def _first_image(raw: dict[str, Any]) -> str | None:
    """Prefer the listing thumbnail; fall back to the first full image."""
    thumb = _normalize_whitespace(raw.get("thumbnail_image"))
    if thumb:
        return thumb
    image = _normalize_whitespace(raw.get("image"))
    if image:
        return image
    images = raw.get("images") or []
    if isinstance(images, list) and images:
        return _normalize_whitespace(images[0])
    return None


def _build_detail_url(list_id: Any) -> str | None:
    """Canonical public detail URL for a Nhà Tốt listing."""
    try:
        list_id_int = int(list_id)
    except (TypeError, ValueError, OverflowError):
        return None
    if list_id_int <= 0 or list_id_int > 10**15:
        return None
    return f"https://www.nhatot.com/{list_id_int}.htm"


def _seller_type(raw: dict[str, Any]) -> str | None:
    """Classify seller as ``company`` / ``individual`` / ``shop``."""
    if raw.get("company_ad") is True:
        return "company"
    if raw.get("shop") or raw.get("is_shop_verified") is True:
        return "shop"
    return "individual"


def _listing_type(raw: dict[str, Any]) -> str | None:
    """Map the ``type`` flag to a human purpose."""
    t = raw.get("type")
    if t == "s":
        return "buy"
    if t == "u":
        return "rent"
    return _normalize_whitespace(t)


def _property_type(raw: dict[str, Any]) -> str | None:
    """Map category code to a normalized property type."""
    category = raw.get("category")
    mapping = {
        1010: "apartment",
        1020: "house",
        1030: "office",
        1040: "land",
    }
    if isinstance(category, int) and category in mapping:
        return mapping[category]
    return _normalize_whitespace(raw.get("category_name"))


def _build_address(raw: dict[str, Any]) -> str | None:
    """Assemble a readable street-level address when parts are present."""
    parts = [
        _normalize_whitespace(raw.get("street_number")),
        _normalize_whitespace(raw.get("street_name")),
        _normalize_whitespace(raw.get("ward_name")),
    ]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def parse_listing(raw: dict[str, Any]) -> ChototBdsListing:
    """Map a single raw ad dict to a typed listing."""
    price, price_raw, price_value = _format_price(
        raw.get("price"), raw.get("price_string")
    )
    area, area_raw, area_value = _format_area(
        raw.get("size"), raw.get("size_unit_string")
    )
    address = _build_address(raw)
    detail_url = _build_detail_url(raw.get("list_id"))

    return ChototBdsListing(
        dataType="chotot_bds_listing",
        listing_id=raw.get("list_id"),
        ad_id=raw.get("ad_id"),
        title=_normalize_whitespace(raw.get("subject")),
        price=price,
        price_raw=price_raw,
        price_value=price_value,
        area=area,
        area_raw=area_raw,
        area_value=area_value,
        location=address,
        district=_normalize_whitespace(raw.get("area_name")),
        city=_normalize_whitespace(raw.get("region_name")),
        ward=_normalize_whitespace(raw.get("ward_name")),
        post_date=_normalize_whitespace(raw.get("date")),
        thumbnail_url=_first_image(raw),
        detail_url=detail_url,
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        listing_type=_listing_type(raw),
        property_type=_property_type(raw),
        seller_type=_seller_type(raw),
        rooms=raw.get("rooms"),
        floors=raw.get("floors"),
        toilets=raw.get("toilets"),
    )


def parse_listings(raw_items: list[dict[str, Any]]) -> list[ChototBdsListing]:
    """Map a list of raw Chotot ad dicts to typed listings."""
    if not raw_items:
        return []
    return [parse_listing(item) for item in raw_items if isinstance(item, dict)]
