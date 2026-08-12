"""Normalize heterogeneous BĐS listings into the common schema."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.location_normalize import (
    remove_diacritics as _remove_diacritics,
    resolve_city_code,
)

from .schemas import VnBdsAggregatedListing, VnBdsProvenance

logger = logging.getLogger(__name__)

# Ponytail: ``to_batdongsan_city_code`` kept as a thin alias so the BĐS
# orchestrator import path stays stable.  The shared module is the source
# of truth.
to_batdongsan_city_code = resolve_city_code

_ADDRESS_STOP_WORDS = frozenset(
    {
        "ban",
        "cho thue",
        "m2",
        "m²",
        "m",
        "met",
        "met vuong",
        "duong",
        "pho",
        "tai",
        "can",
        "nha",
        "dat",
        "phuong",
        "quan",
        "huyen",
        "xa",
        "du an",
        "project",
        "so",
    }
)


def _normalize_phone(phone: str | None) -> str | None:
    """Return a comparable Vietnamese mobile/landline core (drop +84/0)."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    if digits.startswith("0"):
        digits = digits[1:]
    elif digits.startswith("84"):
        digits = digits[2:]
    if len(digits) >= 7:
        return digits
    return None


def _mask_phone(phone: str | None) -> str | None:
    """Mask a full phone number to avoid leaking PII in output."""
    if not phone:
        return None
    core = _normalize_phone(phone)
    if core and len(core) >= 7:
        return f"0{core[:3]}xxx{core[-2:]}"
    return None


def _parse_price(text: str | None) -> tuple[int | None, float | None, bool]:
    """Return (total_price, price_per_m2, is_per_m2) from a price string."""
    if not text:
        return None, None, False

    lower = text.lower()
    if any(w in lower for w in ("thoa thuan", "thuong luong", "giá tỷ", "gia ty")):
        # Negotiable / no numeric price.
        return None, None, False

    # Detect per-m² denominator before we start extracting numbers.
    is_per_m2 = bool(
        re.search(r"[/]\s*(m²|m2|m\b|mét\s*vuông| mét)", text, re.IGNORECASE)
    )

    m = re.search(r"([0-9]+(?:[.,]\d+)?)", text.replace(",", "."))
    if not m:
        return None, None, False

    try:
        number = float(m.group(1))
    except ValueError:
        return None, None, False

    # Unit multiplier.
    multiplier = 1.0
    unit_match = re.search(
        r"(tỷ|tỉ|tỷ\s*/|tỉ\s*/|triệu|tr\b|tr\s*/|nghìn|ng\b)",
        text,
        re.IGNORECASE,
    )
    if unit_match:
        unit = unit_match.group(1).lower().strip()
        if unit.startswith("tỷ") or unit.startswith("tỉ"):
            multiplier = 1_000_000_000
        elif unit.startswith("triệu") or unit == "tr":
            multiplier = 1_000_000
        elif unit.startswith("nghìn") or unit == "ng":
            multiplier = 1_000

    value = number * multiplier

    if is_per_m2:
        return None, value, True
    return int(value), None, False


def _parse_area(text: str | None) -> float | None:
    """Return area in m² from a free-form area string."""
    if not text:
        return None

    # Handle "5x20m" / "5 x 20 m" as a rough product.
    dim_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[xX*]\s*(\d+(?:[.,]\d+)?)", text)
    if dim_match:
        try:
            return float(dim_match.group(1).replace(",", ".")) * float(
                dim_match.group(2).replace(",", ".")
            )
        except ValueError:
            pass

    m = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(m²|m2|mét\s*vuông|m\b|ha|hecta|héc\s*ta|hectare)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    try:
        number = float(m.group(1).replace(",", "."))
    except ValueError:
        return None

    unit = m.group(2).lower()
    if unit.startswith("ha") or unit.startswith("hec"):
        return number * 10_000
    return number


def _parse_post_date(text: str | None) -> tuple[str | None, datetime | None]:
    """Return the raw post_date and a parsed datetime (date only) if possible."""
    if not text:
        return None, None

    raw = str(text).strip()
    today = datetime.now(UTC).date()

    # Relative Vietnamese phrases.
    relative = re.match(
        r"(\d+)\s*(ngày|gio|giờ|tuan|tuần|thang|tháng)\s*trước", raw, re.IGNORECASE
    )
    if relative:
        n = int(relative.group(1))
        unit = relative.group(2).lower()
        if unit in ("ngày", "ngay"):
            dt = today - timedelta(days=n)
        elif unit in ("giờ", "gio"):
            dt = today - timedelta(hours=n)
        elif unit in ("tuần", "tuan"):
            dt = today - timedelta(weeks=n)
        else:  # tháng
            dt = today - timedelta(days=n * 30)
        return raw, datetime(dt.year, dt.month, dt.day, tzinfo=UTC)

    if re.search(r"hôm\s*nay", raw, re.IGNORECASE):
        return raw, datetime(today.year, today.month, today.day, tzinfo=UTC)
    if re.search(r"hôm\s*qua", raw, re.IGNORECASE):
        dt = today - timedelta(days=1)
        return raw, datetime(dt.year, dt.month, dt.day, tzinfo=UTC)

    # Common absolute formats.
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            return raw, parsed
        except ValueError:
            continue

    return raw, None


def _normalize_address(
    district: str | None,
    ward: str | None,
    location: str | None,
) -> str | None:
    """Create a comparable address key from whatever location parts we have."""
    parts: list[str] = []
    for part in (district, ward, location):
        if not part:
            continue
        text = _remove_diacritics(part)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        tokens = [
            t
            for t in text.split()
            if t and t not in _ADDRESS_STOP_WORDS and not t.isdigit()
        ]
        if tokens:
            parts.append(" ".join(tokens))

    if not parts:
        return None
    return " ".join(parts)


def _extract_id(raw: dict[str, Any]) -> Any:
    """Pick the most stable id available from a raw source listing."""
    for key in ("listing_id", "ad_id", "user_id", "id"):
        if raw.get(key) is not None:
            return raw[key]
    return None


def _source_title(raw: dict[str, Any], source: str) -> str | None:
    return raw.get("title") or raw.get("subject") or raw.get("name")


def _source_phone(raw: dict[str, Any]) -> str | None:
    return raw.get("phone") or raw.get("phone_display") or raw.get("phone_enc")


def _source_detail_url(raw: dict[str, Any]) -> str | None:
    return raw.get("detail_url") or raw.get("url") or raw.get("link")


def _image_key(raw: dict[str, Any]) -> str | None:
    """Return a comparable key for an image based on its URL.

    Uses a truncated SHA-256 so the same image across sources matches even when
    query parameters differ; ``None`` when no image is present.
    """
    url = raw.get("thumbnail_url") or raw.get("image_url") or raw.get("image")
    if not url:
        return None
    # Normalize protocol, trailing path noise and query params.
    text = re.sub(r"^https?://", "", str(url).strip().lower())
    text = text.split("?")[0]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def make_canonical_id(source_ids: dict[str, Any]) -> str:
    """Stable canonical id from sorted source key/values."""
    payload = json.dumps(
        {k: str(v) for k, v in sorted(source_ids.items())},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize_listing(source: str, raw: dict[str, Any]) -> VnBdsAggregatedListing:
    """Map one raw source listing to the common schema."""
    raw = dict(raw) if raw else {}

    price_text = raw.get("price") or raw.get("price_raw")
    price_value, price_per_m2, is_per_m2 = _parse_price(price_text)

    area_text = raw.get("area") or raw.get("area_raw")
    area_value = _parse_area(area_text)

    if is_per_m2 and price_per_m2 is not None and area_value:
        price_value = int(price_per_m2 * area_value)
    elif price_value is not None and area_value and area_value > 0:
        price_per_m2 = price_value / area_value

    raw_post_date, _ = _parse_post_date(raw.get("post_date"))

    phone = _source_phone(raw)
    phone_key = _normalize_phone(phone)
    contact = _mask_phone(phone)

    district = raw.get("district")
    ward = raw.get("ward")
    location = raw.get("location")
    address_key = _normalize_address(district, ward, location)

    source_id = _extract_id(raw)
    source_ids = {source: source_id} if source_id is not None else {source: None}
    detail_urls: dict[str, str | None] = {source: _source_detail_url(raw)}
    source_prices: dict[str, int | None] = {source: price_value}

    listing = VnBdsAggregatedListing(
        canonical_id=make_canonical_id(source_ids),
        source_ids=source_ids,
        title=_source_title(raw, source),
        price=price_text,
        price_value=price_value,
        price_per_m2=price_per_m2,
        area=area_text,
        area_value=area_value,
        location=location,
        district=district,
        ward=ward,
        city=raw.get("city"),
        project=raw.get("project") or raw.get("estate_project"),
        legal=raw.get("legal") or raw.get("legal_status"),
        post_date=raw_post_date,
        contact=contact,
        phone_key=phone_key,
        address_key=address_key,
        image_key=_image_key(raw),
        thumbnail_url=raw.get("thumbnail_url") or raw.get("image_url"),
        detail_urls=detail_urls,
        sources=[source],
        source_count=1,
        source_prices=source_prices,
        confidence_score=0.0,
        provenance=VnBdsProvenance(),
    )
    # Confidence will be filled in after deduplication.
    return listing
