"""Pure, I/O-free parsing of Chợ Tốt listing data across categories."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from .fetch import CategoryConfigError, get_category_config
from .schemas import ChototBdsListing, ChototListing

logger = logging.getLogger(__name__)


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None


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


def _build_detail_url(list_id: Any, category: str = "bds") -> str | None:
    """Canonical public detail URL for a Chợ Tốt listing."""
    try:
        list_id_int = int(list_id)
    except (TypeError, ValueError, OverflowError):
        return None
    if list_id_int <= 0 or list_id_int > 10**15:
        return None
    try:
        cfg = get_category_config(category)
        origin = cfg.get("detail_origin", "https://www.chotot.com")
    except CategoryConfigError:
        origin = "https://www.chotot.com"
    return f"{origin}/{list_id_int}.htm"


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
        return "sell"
    if t == "u":
        return "rent"
    if t == "k":
        return "want_to_buy"
    return _normalize_whitespace(t)


def _listing_type_bds(raw: dict[str, Any]) -> str | None:
    """Legacy BĐS output values for backward compatibility."""
    t = raw.get("type")
    if t == "s":
        return "buy"
    if t == "u":
        return "rent"
    return _normalize_whitespace(t)


def _build_address(raw: dict[str, Any]) -> str | None:
    """Assemble a readable street-level address when parts are present."""
    parts = [
        _normalize_whitespace(raw.get("street_number")),
        _normalize_whitespace(raw.get("street_name")),
        _normalize_whitespace(raw.get("ward_name")),
        _normalize_whitespace(raw.get("area_name")),
        _normalize_whitespace(raw.get("region_name")),
    ]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def _extract_common(raw: dict[str, Any], category: str) -> dict[str, Any]:
    """Build the common fields shared by every ``ChototListing``."""
    price, price_raw, price_value = _format_price(
        raw.get("price"), raw.get("price_string")
    )
    address = _build_address(raw)
    detail_url = _build_detail_url(raw.get("list_id"), category)

    return {
        "listing_id": _as_int(raw.get("list_id")),
        "ad_id": _as_int(raw.get("ad_id")),
        "title": _normalize_whitespace(raw.get("subject")),
        "price": price,
        "price_raw": price_raw,
        "price_value": price_value,
        "location": address,
        "district": _normalize_whitespace(raw.get("area_name")),
        "city": _normalize_whitespace(raw.get("region_name")),
        "ward": _normalize_whitespace(raw.get("ward_name")),
        "post_date": _normalize_whitespace(raw.get("date")),
        "thumbnail_url": _first_image(raw),
        "detail_url": detail_url,
        "latitude": _as_float(raw.get("latitude")),
        "longitude": _as_float(raw.get("longitude")),
        "seller_type": _seller_type(raw),
        "listing_type": _listing_type(raw),
    }


_COMMON_SCALAR_KEYS: frozenset[str] = frozenset({
    "account_id",
    "account_name",
    "account_oid",
    "ad_features",
    "ad_id",
    "ad_labels",
    "area",
    "area_name",
    "area_v2",
    "avatar",
    "body",
    "business_days",
    "category",
    "category_name",
    "company_ad",
    "contain_videos",
    "cta_buttons",
    "date",
    "fee_type",
    "full_name",
    "image",
    "image_thumbnails",
    "images",
    "inspection_images",
    "is_shop_verified",
    "is_sticky",
    "is_zalo_show",
    "job_tier",
    "label_campaigns",
    "latitude",
    "list_id",
    "list_time",
    "location",
    "longitude",
    "number_of_images",
    "params",
    "price",
    "price_string",
    "protection_entitlement",
    "pty_characteristics",
    "region",
    "region_name",
    "region_name_v3",
    "region_v2",
    "seller_info",
    "special_display",
    "special_display_images",
    "specific_service_offered",
    "state",
    "status",
    "sticky_ad_platinum",
    "subject",
    "thumbnail_image",
    "type",
    "videos",
    "ward",
    "ward_name",
    "ward_name_v3",
    "webp_image",
})


def _extract_attributes(
    raw: dict[str, Any], category: str, known_fields: set[str]
) -> dict[str, Any]:
    """Copy category-specific scalar fields into the ``attributes`` bag."""
    skip = _COMMON_SCALAR_KEYS | known_fields
    attrs: dict[str, Any] = {}
    for key, value in raw.items():
        if key in skip or value is None:
            continue
        if isinstance(value, (str, int, float, bool)) and not isinstance(value, bool):
            # bool is an int subclass; keep useful booleans like company_ad.
            attrs[key] = value
        elif isinstance(value, bool) or (isinstance(value, list) and value and all(
            isinstance(v, (str, int, float, bool)) for v in value
        )):
            attrs[key] = value
        elif isinstance(value, dict) and value:
            # Shallow dict for things like seller_info / shop.
            attrs[key] = value
    return attrs


def _vehicle_attrs(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract vehicle-specific fields for both cars and motorbikes."""
    attrs: dict[str, Any] = {}
    for key in (
        "carbrand",
        "carbrand_name",
        "carmodel",
        "carorigin",
        "carfuel",
        "cartransmission",
        "car_mileage",
        "car_mileage_v2",
        "carcondition",
        "car_year",
        "motorbikebrand",
        "motorbikebrand_name",
        "motorbikemodel",
        "motorbikeorigin",
        "motorbiketype",
        "motorbikefuel",
        "motorbiketransmission",
        "mileage",
        "mileage_v2",
        "regdate",
        "condition_ad",
        "condition_ad_name",
        "vehicleguarantee",
        "veh_inspected",
        "veh_ecom_can_buy_now",
        "veh_ecom_product_id",
        "veh_ecom_shop_id",
    ):
        if key in raw and raw[key] is not None:
            attrs[key] = raw[key]
    # Normalise make/model/year/mileage to common keys when present.
    if "carbrand" in attrs or "carbrand_name" in attrs:
        attrs["make"] = attrs.get("carbrand_name") or attrs.get("carbrand")
    if "carmodel" in attrs:
        attrs["model"] = attrs["carmodel"]
    if "car_year" in attrs:
        attrs["year"] = attrs["car_year"]
    elif "regdate" in attrs:
        attrs["year"] = attrs["regdate"]
    if "mileage_v2" in attrs:
        attrs["mileage"] = attrs["mileage_v2"]
    elif "car_mileage_v2" in attrs:
        attrs["mileage"] = attrs["car_mileage_v2"]
    elif "mileage" in attrs:
        attrs["mileage"] = attrs["mileage"]
    if "carfuel" in attrs:
        attrs["fuel_type"] = attrs["carfuel"]
    if "cartransmission" in attrs:
        attrs["transmission"] = attrs["cartransmission"]
    if "condition_ad_name" in attrs:
        attrs["condition"] = attrs["condition_ad_name"]
    if "motorbikebrand" in attrs or "motorbikebrand_name" in attrs:
        attrs["make"] = attrs.get("motorbikebrand_name") or attrs.get("motorbikebrand")
    if "motorbikemodel" in attrs:
        attrs["model"] = attrs["motorbikemodel"]
    if "motorbikeorigin" in attrs:
        attrs["vehicle_type"] = attrs["motorbikeorigin"]
    return attrs


def _electronics_attrs(raw: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key in (
        "mobile_brand",
        "mobile_brand_name",
        "mobile_model",
        "mobile_capacity",
        "mobile_color",
        "mobile_color_name",
        "elt_condition",
        "condition_ad",
        "condition_ad_name",
        "official_store",
        "gds_inspected",
        "giveaway",
    ):
        if key in raw and raw[key] is not None:
            attrs[key] = raw[key]
    if "mobile_brand" in attrs:
        attrs["brand"] = attrs.get("mobile_brand_name") or attrs.get("mobile_brand")
    if "mobile_model" in attrs:
        attrs["model"] = attrs["mobile_model"]
    if "mobile_capacity" in attrs:
        attrs["capacity"] = attrs["mobile_capacity"]
    if "mobile_color_name" in attrs or "mobile_color" in attrs:
        attrs["color"] = attrs.get("mobile_color_name") or attrs.get("mobile_color")
    if "condition_ad_name" in attrs:
        attrs["condition"] = attrs["condition_ad_name"]
    elif "elt_condition" in attrs:
        attrs["condition"] = attrs["elt_condition"]
    return attrs


def _job_attrs(raw: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key in (
        "company_name",
        "job_type",
        "contract_type",
        "min_salary",
        "max_salary",
        "salary_type",
        "preferred_education",
        "preferred_gender",
        "preferred_working_experience",
        "min_age",
        "max_age",
        "vacancies",
        "skills",
        "candidate_academic_level",
        "candidate_applied",
        "candidate_birthday",
        "candidate_cert",
        "candidate_gender",
        "candidate_working_exp",
        "require_portrait_photo",
        "job_urgent_recruit_enabled",
    ):
        if key in raw and raw[key] is not None:
            attrs[key] = raw[key]
    if "min_salary" in attrs or "max_salary" in attrs:
        attrs["salary_min"] = attrs.get("min_salary")
        attrs["salary_max"] = attrs.get("max_salary")
        attrs["salary_string"] = _normalize_whitespace(raw.get("price_string"))
    if "company_name" in attrs:
        attrs["company_name"] = _normalize_whitespace(attrs["company_name"])
    return attrs


def _bds_attrs(raw: dict[str, Any]) -> dict[str, Any]:
    """BĐS-specific fields for the legacy ``ChototBdsListing``."""
    attrs: dict[str, Any] = {}
    for key in (
        "area",
        "rooms",
        "floors",
        "toilets",
        "size",
        "size_unit_string",
        "property_legal_document",
        "apartment_type",
        "apartment_feature",
        "balconydirection",
        "direction",
        "pty_characteristics",
        "pty_project_name",
    ):
        if key in raw and raw[key] is not None:
            attrs[key] = raw[key]
    return attrs


def _property_type(raw: dict[str, Any]) -> str | None:
    """Map BĐS leaf category code to a normalized property type."""
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


def parse_generic(raw: dict[str, Any], category: str = "unknown") -> ChototListing:
    """Parse an unknown or unmapped category, preserving as much data as possible."""
    common = _extract_common(raw, category)
    listing = ChototListing(category=category, **common)
    listing.attributes = _extract_attributes(raw, category, set())
    return listing


def parse_bds(raw: dict[str, Any]) -> ChototBdsListing:
    """Parse a BĐS listing, preserving the legacy typed schema."""
    price, price_raw, price_value = _format_price(
        raw.get("price"), raw.get("price_string")
    )
    area, area_raw, area_value = _format_area(
        raw.get("size"), raw.get("size_unit_string")
    )
    address = _build_address(raw)
    detail_url = _build_detail_url(raw.get("list_id"), "bds")

    return ChototBdsListing(
        dataType="chotot_bds_listing",
        listing_id=_as_int(raw.get("list_id")),
        ad_id=_as_int(raw.get("ad_id")),
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
        latitude=_as_float(raw.get("latitude")),
        longitude=_as_float(raw.get("longitude")),
        listing_type=_listing_type_bds(raw),
        property_type=_property_type(raw),
        seller_type=_seller_type(raw),
        rooms=_as_int(raw.get("rooms")),
        floors=_as_int(raw.get("floors")),
        toilets=_as_int(raw.get("toilets")),
        attributes=_bds_attrs(raw),
    )


def _vehicle_listing(raw: dict[str, Any], category: str) -> ChototListing:
    common = _extract_common(raw, category)
    listing = ChototListing(category=category, **common)
    listing.attributes = _vehicle_attrs(raw)
    # Keep price string as display value if price_value is None.
    return listing


def _electronics_listing(raw: dict[str, Any], category: str) -> ChototListing:
    common = _extract_common(raw, category)
    listing = ChototListing(category=category, **common)
    listing.attributes = _electronics_attrs(raw)
    return listing


def _job_listing(raw: dict[str, Any], category: str) -> ChototListing:
    common = _extract_common(raw, category)
    # Company name belongs in the title/location area if missing.
    if not common.get("location") and raw.get("company_name"):
        common["location"] = _normalize_whitespace(raw.get("company_name"))
    listing = ChototListing(category=category, **common)
    listing.attributes = _job_attrs(raw)
    return listing


def _general_goods_listing(raw: dict[str, Any], category: str) -> ChototListing:
    """Furniture, fashion, pets, hobbies, home goods, services, etc."""
    common = _extract_common(raw, category)
    listing = ChototListing(category=category, **common)
    known = {
        "condition_ad",
        "condition_ad_name",
        "itemconsumer",
        "pet_breed",
        "pet_breed_name",
        "pet_age",
        "pet_size",
        "food_type",
        "official_store",
        "gds_inspected",
        "giveaway",
    }
    listing.attributes = _extract_attributes(raw, category, known)
    if "condition_ad_name" in raw and raw["condition_ad_name"] is not None:
        listing.attributes.setdefault("condition", raw["condition_ad_name"])
    if "pet_breed_name" in raw and raw["pet_breed_name"] is not None:
        listing.attributes.setdefault("breed", raw["pet_breed_name"])
    elif "pet_breed" in raw and raw["pet_breed"] is not None:
        listing.attributes.setdefault("breed", raw["pet_breed"])
    return listing


# Dispatch based on the *requested* category slug, not the leaf ``category`` code.
# This keeps the parser contract simple and avoids needing a full category tree.
_CATEGORY_PARSERS: dict[str, Callable[[dict[str, Any]], ChototListing]] = {
    "bds": parse_bds,
    "cars": lambda raw: _vehicle_listing(raw, "cars"),
    "motorbikes": lambda raw: _vehicle_listing(raw, "motorbikes"),
    "electronics": lambda raw: _electronics_listing(raw, "electronics"),
    "jobs": lambda raw: _job_listing(raw, "jobs"),
    "pets": lambda raw: _general_goods_listing(raw, "pets"),
    "fashion": lambda raw: _general_goods_listing(raw, "fashion"),
    "home_goods": lambda raw: _general_goods_listing(raw, "home_goods"),
    "home_appliances": lambda raw: _general_goods_listing(raw, "home_appliances"),
    "kitchen": lambda raw: _general_goods_listing(raw, "kitchen"),
    "services": lambda raw: _general_goods_listing(raw, "services"),
    "home_services": lambda raw: _general_goods_listing(raw, "home_services"),
}


def parse_listing(raw: dict[str, Any], category: str = "bds") -> ChototListing:
    """Map a single raw ad dict to a typed ``ChototListing``."""
    if not isinstance(raw, dict):
        raise ValueError("raw listing must be a dict")

    try:
        get_category_config(category)
    except CategoryConfigError:
        return parse_generic(raw, "unknown")

    parser = _CATEGORY_PARSERS.get(category)
    if parser is None:
        # Allow raw numeric cg categories to fall back to generic parsing.
        if category.isdigit():
            return parse_generic(raw, category)
        return parse_generic(raw, "unknown")
    return parser(raw)


def parse_listings(
    raw_items: list[dict[str, Any]], category: str = "bds"
) -> list[ChototListing]:
    """Map a list of raw Chotot ad dicts to typed listings."""
    if not raw_items:
        return []
    listings: list[ChototListing] = []
    for item in raw_items:
        if isinstance(item, dict):
            listings.append(parse_listing(item, category))
        else:
            logger.warning("skipping non-dict ad item in category=%r: %s", category, type(item))
    return listings
