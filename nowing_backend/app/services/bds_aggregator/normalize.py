"""Normalize heterogeneous BĐS listings into the common schema."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any

from .schemas import VnBdsAggregatedListing, VnBdsProvenance

logger = logging.getLogger(__name__)

# Batdongsan city code → URL slug mapping.  This is a V1 snapshot of the
# proprietary ``app.proprietary.platforms.batdongsan.city_codes`` table, kept
# local so the aggregator can resolve free-form city input without triggering
# heavy platform imports.
_CITY_SLUGS: dict[str, str] = {
    "AG": "an-giang",
    "BD": "binh-duong",
    "BDI": "binh-dinh",
    "BG": "bac-giang",
    "BK": "bac-kan",
    "BL": "bac-lieu",
    "BN": "bac-ninh",
    "BP": "binh-phuoc",
    "BT": "ben-tre",
    "BTH": "binh-thuan",
    "CB": "cao-bang",
    "CM": "ca-mau",
    "CT": "can-tho",
    "DI": "dien-bien",
    "DKL": "dak-lak",
    "DN": "da-nang",
    "DNO": "dak-nong",
    "DT": "dong-thap",
    "GL": "gia-lai",
    "HD": "hai-duong",
    "HG": "ha-giang",
    "HN": "ha-noi",
    "HP": "hai-phong",
    "HT": "ha-tinh",
    "HUG": "hau-giang",
    "HY": "hung-yen",
    "KH": "khanh-hoa",
    "KG": "kien-giang",
    "KT": "kon-tum",
    "LA": "long-an",
    "LB": "long-bien",
    "LC": "lao-cai",
    "LCH": "lai-chau",
    "LD": "lam-dong",
    "LS": "lang-son",
    "NA": "nghe-an",
    "NB": "ninh-binh",
    "ND": "nam-dinh",
    "NT": "ninh-thuan",
    "PT": "phu-tho",
    "PY": "phu-yen",
    "QB": "quang-binh",
    "QN": "quang-ninh",
    "QNG": "quang-ngai",
    "QT": "quang-tri",
    "SG": "tp-hcm",
    "SL": "son-la",
    "ST": "soc-trang",
    "TB": "thai-binh",
    "TG": "tien-giang",
    "TH": "thanh-hoa",
    "TN": "thai-nguyen",
    "TQ": "tuyen-quang",
    "TV": "tra-vinh",
    "TTH": "hue",
    "VL": "vinh-long",
    "VT": "ba-ria-vung-tau",
    "YB": "yen-bai",
}

_CITY_CODES: frozenset[str] = frozenset(_CITY_SLUGS)

# Extra common aliases for free-form Vietnamese input.  The generated aliases
# below (slugs, unhyphenated slugs and lower-case codes) cover the standard
# names; this table covers typos, abbreviations and colloquial forms.
_CITY_OVERRIDES: dict[str, str] = {
    "ha-noi": "HN",
    "hanoi": "HN",
    "ho-chi-minh": "SG",
    "hcm": "SG",
    "tp-hcm": "SG",
    "tphcm": "SG",
    "sai-gon": "SG",
    "saigon": "SG",
    "hue": "TTH",
    "ba-ria-vung-tau": "VT",
    "ba-ria": "VT",
    "vung-tau": "VT",
    "binh-dinh": "BDI",
    "lai-chau": "LCH",
}

# Generate the full alias table from slugs, codes and manual overrides so any
# of {slug, unhyphenated-slug, lowercase-code, common-name} resolve correctly.
_CITY_ALIASES: dict[str, str] = {}
for _code, _slug in _CITY_SLUGS.items():
    _CITY_ALIASES[_slug] = _code
    _CITY_ALIASES[_slug.replace("-", "")] = _code
    _CITY_ALIASES[_code.lower()] = _code
_CITY_ALIASES.update(_CITY_OVERRIDES)

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


def _remove_diacritics(value: str | None) -> str:
    """Return an ASCII-ish lowercased copy of ``value``."""
    if not value:
        return ""
    text = unicodedata.normalize("NFD", value)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("\u0111", "d").replace("\u0110", "d")
    return text.lower()


def _to_slug(value: str | None) -> str:
    """Make a lowercase, no-diacritic, hyphenated slug."""
    text = _remove_diacritics(value or "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def to_batdongsan_city_code(user_city: str | None) -> str | None:
    """Resolve free-form Vietnamese city input to a Batdongsan code."""
    if not user_city:
        return None
    raw = user_city.strip()
    # Accept any known city code case-insensitively.
    if raw.upper() in _CITY_CODES:
        return raw.upper()

    normalized = _to_slug(raw)
    if normalized in _CITY_ALIASES:
        return _CITY_ALIASES[normalized]

    # Try a few common prefix-stripped forms.
    for prefix in ("tp-", "tinh-", "thanh-pho-", "quan-", "huyen-", "phuong-", "xa-"):
        if normalized.startswith(prefix):
            stripped = normalized[len(prefix) :]
            if stripped in _CITY_ALIASES:
                return _CITY_ALIASES[stripped]

    return None


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
