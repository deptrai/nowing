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


def _format_price(
    price_value: Any, price_string: str | None
) -> tuple[str | None, str | None, int | None]:
    """Return ``(price, price_raw, price_value)`` from a Chotot price."""
    raw = _normalize_whitespace(price_string)
    if raw is None:
        return None, None, None
    if isinstance(price_value, (int, float)):
        return raw, raw, int(price_value)
    # Non-numeric strings like "Thỏa thuận" are kept in price_raw only.
    if not re.search(r"[\d.,]+", raw):
        return None, raw, None
    return raw, raw, None


def _format_area(
    size_value: Any, size_unit: str | None
) -> tuple[str | None, str | None, float | None]:
    """Return ``(area, area_raw, area_value)`` from size fields."""
    if isinstance(size_value, (int, float)):
        unit = _normalize_whitespace(size_unit) or "m²"
        raw = f"{size_value} {unit}"
        return raw, raw, float(size_value)
    return None, None, None


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
    except (TypeError, ValueError):
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
