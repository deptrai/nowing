"""Pure, I/O-free parsing of Batdongsan ``p_sync`` listing data."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup

from .city_codes import CITY_SLUGS
from .schemas import BatdongsanListing

# District/city prefixes seen in Vietnamese addresses. Quận = urban district,
# Huyện = rural district, Thị xã = town, TP = city.
_DISTRICT_PREFIXES = ("Quận", "Huyện", "Thị xã", "TX.", "H.")
_CITY_PREFIXES = ("TP.", "Tỉnh", "Thành phố")


def _normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _extract_number_and_unit(text: str | None) -> str | None:
    """Pull the leading ``number unit`` token out of strings like ``75 m²``.

    Handles ranges (``72-75 m²``) by keeping the dash inside the number group
    so it is never mistaken for a unit separator.
    """
    if not text:
        return None
    match = re.search(r"([\d.,]+(?:-[\d.,]+)?)\s*([^\d.,\s-]+)", text)
    if match:
        return f"{match.group(1)} {match.group(2)}".strip()
    return text.strip() or None


def _parse_price(raw: Any) -> tuple[str | None, str | None]:
    """Return ``(price, price_raw)`` from a Batdongsan price string.

    ``Thỏa thuận`` and non-price strings are kept in ``price_raw`` only.
    """
    raw_str = _normalize_whitespace(raw)
    if raw_str is None:
        return None, None

    if re.search(r"[\d.,]+", raw_str):
        normalized = _extract_number_and_unit(raw_str) or raw_str
        return normalized, raw_str
    return None, raw_str


def _parse_area(raw: Any) -> tuple[str | None, str | None]:
    """Return ``(area, area_raw)`` from an area string like ``75 m²``."""
    raw_str = _normalize_whitespace(raw)
    if raw_str is None:
        return None, None
    if re.search(r"[\d.,]+", raw_str):
        normalized = _extract_number_and_unit(raw_str) or raw_str
        return normalized, raw_str
    return None, raw_str


def _strip_prefixes(text: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip(" .")
    return text.strip() or text


def _split_address(address: str | None) -> tuple[str | None, str | None]:
    """Best-effort split ``location`` into ``(district, city)``.

    Addresses are usually comma-delimited: ``Ward, District, City`` or
    ``Street, Ward, District, City``. The last segment is city, the one before
    it is district. Only prefixes are stripped, no translation.
    """
    if not address:
        return None, None
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return None, None
    city = _strip_prefixes(parts[-1], _CITY_PREFIXES)
    district = (
        _strip_prefixes(parts[-2], _DISTRICT_PREFIXES) if len(parts) >= 2 else None
    )
    return district, city


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


_WEB_ORIGIN = "https://batdongsan.com.vn"


_TITLE_PHONE_RE = re.compile(
    r"(?:LH|ĐT|SDT|sdt|đt|liên hệ|phone|call)?\s*[:\-]?\s*(\d[\d\s\.\-]{8,}\d)",
    re.IGNORECASE,
)


def _normalize_phone_text(text: str) -> str | None:
    """Extract a clean 10+ digit Vietnamese phone number from free text."""
    text = text.strip()
    # Remove separators and keep spacing every 3-4 digits for readability.
    digits = re.sub(r"[^\d]", "", text)
    if len(digits) >= 9 and digits.startswith("0"):
        return digits
    # Some titles include numbers like '0916 754 123' separated by spaces.
    parts = re.split(r"[\.\s\-]+", text.strip())
    if len(parts) >= 3 and all(p.isdigit() for p in parts):
        return "".join(parts)
    return None


def extract_phone_from_title(title: str | None) -> str | None:
    """Best-effort phone extraction from listing title (e.g. ``LH: 0916754123``)."""
    if not title:
        return None
    m = _TITLE_PHONE_RE.search(title)
    if not m:
        return None
    phone = _normalize_phone_text(m.group(1))
    return phone


def _slugify_title(title: str | None) -> str:
    """Create a URL-safe slug from a listing title.

    The slug is not authoritative on batdongsan.com.vn; the canonical
    ``pr<listing_id>`` suffix determines the page.  We keep the title for
    readability but aggressively strip non-ASCII diacritics.
    """
    if not title:
        return "tin-dang"
    # Pre-map a couple of Vietnamese consonants before NFKD so the result
    # contains the right ASCII base letter (đ/Đ → d/D).
    text = title.replace("\u0110", "D").replace("\u0111", "d")
    # Decompose and drop combining marks, then keep alphanumerics and spaces.
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug or "tin-dang"


def build_detail_url(
    listing_id: int | None,
    title: str | None,
    city_code: str,
    listing_type: str = "buy",
) -> str | None:
    """Construct a batdongsan.com.vn detail URL from known listing fields.

    The site accepts an arbitrary last-segment slug as long as the canonical
    ``pr<listing_id>`` suffix is present and the parent category/city path
    exists, so we can avoid scanning web listing pages for a match.
    """
    if not listing_id or not city_code:
        return None
    city_slug = CITY_SLUGS.get(city_code)
    if not city_slug:
        return None
    prefix = "ban-nha-dat" if listing_type == "buy" else "nha-dat-cho-thue"
    slug = _slugify_title(title)
    return f"{_WEB_ORIGIN}/{prefix}-{city_slug}/{slug}-pr{listing_id}"


def parse_listing(raw: dict[str, Any]) -> BatdongsanListing:
    """Map a single raw data dict to a typed listing."""
    address = _normalize_whitespace(raw.get("address"))
    district, city = _split_address(address) if address else (None, None)
    price, price_raw = _parse_price(raw.get("price"))
    area, area_raw = _parse_area(raw.get("area"))

    # If the city is still empty after stripping prefixes, fall back to the
    # last segment untouched.
    if not city:
        parts = [p.strip() for p in (address or "").split(",") if p.strip()]
        city = parts[-1] if parts else None

    return BatdongsanListing(
        dataType="batdongsan_listing",
        listing_id=_to_int(raw.get("id")),
        title=_normalize_whitespace(raw.get("title")),
        price=price,
        price_raw=price_raw,
        area=area,
        area_raw=area_raw,
        location=address,
        district=district,
        city=city,
        post_date=_normalize_whitespace(raw.get("date")),
        thumbnail_url=_normalize_whitespace(raw.get("avatar")),
        detail_url=_normalize_whitespace(raw.get("url")),
        latitude=_to_float(raw.get("lat")),
        longitude=_to_float(raw.get("lon")),
        category=_normalize_whitespace(raw.get("cat")),
        rooms=_to_int(raw.get("room")),
    )


def parse_listings(raw_items: list[dict[str, Any]]) -> list[BatdongsanListing]:
    """Map a list of raw Batdongsan data dicts to typed listings."""
    if not raw_items:
        return []
    return [parse_listing(item) for item in raw_items if isinstance(item, dict)]


def parse_web_listings(html: str) -> list[dict[str, Any]]:
    """Parse SSR listing cards from a batdongsan.com.vn web page.

    Returns raw dicts shaped like mobile ``p_sync`` items so
    :func:`parse_listings` can consume them uniformly.
    """
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.js__card-listing")
    items: list[dict[str, Any]] = []
    for card in cards:
        prid = card.get("prid")
        if not prid:
            continue
        try:
            listing_id = int(prid)
        except (TypeError, ValueError):
            continue

        link = card.select_one("a.js__product-link-for-product-id")
        href = (link.get("href") or "") if link else ""
        detail_url = f"{_WEB_ORIGIN}{href}" if href else None

        title_el = card.select_one("span.js__card-title")
        title = title_el.get_text(strip=True) if title_el else None

        price_el = card.select_one("span.re__card-config-price")
        price = price_el.get_text(strip=True) if price_el else None

        area_el = card.select_one("span.re__card-config-area")
        area = area_el.get_text(strip=True) if area_el else None

        loc_el = card.select_one("div.re__card-location")
        location = loc_el.get_text(strip=True) if loc_el else None

        avatar = card.get("prav")

        bedroom_el = card.select_one("span.re__card-config-bedroom")
        room: int | None = None
        if bedroom_el:
            aria = bedroom_el.get("aria-label") or ""
            m = re.search(r"\d+", aria)
            if m:
                room = int(m.group(0))

        items.append(
            {
                "id": listing_id,
                "title": title,
                "price": price,
                "area": area,
                "address": location,
                "avatar": avatar,
                "url": detail_url,
                "room": room,
            }
        )
    return items


def parse_detail_phone(html: str) -> tuple[str | None, str | None]:
    """Extract the best-effort phone info from a Batdongsan detail page.

    The public page shows a masked number (e.g. ``0906 782 ***``) behind a
    ``Hiện số`` button.  Full numbers require a logged-in session and often
    an SMS OTP, so we return the masked display as ``phone_display`` and only
    set ``phone`` when the button already contains a fully numeric string.
    """
    soup = BeautifulSoup(html, "lxml")

    # Primary: the contact button on the listing detail page.
    phone_btn = (
        soup.select_one("div.js__phone-event")
        or soup.select_one("div.re__btn-phone-icon")
        or soup.select_one("a.re__link-phone")
        or soup.select_one(".js__phone")
    )
    if phone_btn:
        text = phone_btn.get_text(strip=True)
        # Text is typically "0906 782 *** · Hiện số" or a full number.
        if "·" in text:
            text = text.split("·")[0].strip()
        if re.search(r"\d", text):
            digits_only = re.sub(r"[^\d\s]", "", text).strip()
            phone_display = text
            # Consider it a full phone if it has at least 10 digits and no mask.
            phone = (
                phone_display
                if len(digits_only) >= 10 and "*" not in phone_display
                else None
            )
            return phone, phone_display

    # Fallback: a plain phone text span (often a support hotline, not the agent).
    fallback = soup.select_one("span.re__text-phone")
    if fallback:
        text = fallback.get_text(strip=True)
        if re.search(r"\d", text):
            # Accept only a single mobile-style number (not support/landline/multi-number).
            digits = re.sub(r"[^\d]", "", text)
            if (
                len(digits) in (10, 11)
                and digits.startswith(("09", "08", "07", "05", "03"))
                and "(" not in text
                and "-" not in text
            ):
                return text, text

    return None, None
