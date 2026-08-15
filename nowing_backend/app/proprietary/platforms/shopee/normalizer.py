"""Price and entity normalization for Shopee Vietnam (Story 17.2 / AD-EC-2)."""

from __future__ import annotations

import math
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import parse_qs, unquote, urlparse

# Shopee encodes VND prices scaled by 100,000 in raw JSON payloads.
SHOPEE_PRICE_SCALE = Decimal("100000")
_PRECISION_CENTS = Decimal("0.01")


def normalize_price(raw_price: int | float | str | Decimal | None) -> Decimal | None:
    """Normalize raw Shopee integer price (scaled by 100,000) to precise NUMERIC(18, 2) Decimal.

    Applies Decimal(raw_price) / Decimal("100000") with ROUND_HALF_UP rounding.
    Zero and negative inputs clamp to Decimal("0.00").
    Non-finite (NaN, Infinity) or invalid inputs return None.
    """
    if raw_price is None:
        return None

    if isinstance(raw_price, str):
        clean_str = raw_price.strip()
        if not clean_str:
            return None
        try:
            val = Decimal(clean_str)
        except InvalidOperation:
            return None
    elif isinstance(raw_price, (int, float, Decimal)):
        try:
            val = Decimal(str(raw_price))
        except (InvalidOperation, ValueError):
            return None
    else:
        return None

    if not val.is_finite():
        return None

    if val <= Decimal("0"):
        return Decimal("0.00")

    normalized = val / SHOPEE_PRICE_SCALE
    return normalized.quantize(_PRECISION_CENTS, rounding=ROUND_HALF_UP)


def normalize_rating(raw_rating: float | int | str | None) -> float:
    """Normalize Shopee rating star into a clamped float in range [0.0, 5.0] with 2 decimals."""
    if raw_rating is None:
        return 0.0

    try:
        val = float(raw_rating)
    except (ValueError, TypeError):
        return 0.0

    if math.isnan(val) or math.isinf(val):
        return 0.0

    if val < 0.0:
        return 0.0
    if val > 5.0:
        return 5.0

    return round(val, 2)


def normalize_discount(
    current_price: Decimal | None,
    original_price: Decimal | None,
    raw_discount: int | str | None = None,
) -> int:
    """Determine discount percentage (0-100) from raw percentage or calculated price difference."""
    if raw_discount is not None:
        try:
            cleaned_discount = str(raw_discount).strip().rstrip("%").lstrip("-")
            d_val = int(cleaned_discount)
            if 0 <= d_val <= 100:
                return d_val
        except (ValueError, TypeError):
            pass

    if (
        current_price is not None
        and original_price is not None
        and original_price > Decimal("0")
        and current_price < original_price
    ):
        diff = original_price - current_price
        pct = (diff / original_price) * Decimal("100")
        rounded = int(pct.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return max(0, min(100, rounded))

    return 0


def _slugify(text: str) -> str:
    """Convert Vietnamese text to ASCII URL-friendly slug."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


def normalize_product_url(
    shop_id: int | str, item_id: int | str, name: str | None = None
) -> str:
    """Build canonical Shopee Vietnam product URL."""
    if name:
        slug = _slugify(name)
        if slug:
            return f"https://shopee.vn/{slug}-i.{shop_id}.{item_id}"
    return f"https://shopee.vn/product/{shop_id}/{item_id}"


_URL_PATTERNS = [
    # https://shopee.vn/product/{shop_id}/{item_id}
    re.compile(r"/product/(\d+)/(\d+)"),
    # https://shopee.vn/slug-name-i.{shop_id}.{item_id}
    re.compile(r"-i\.(\d+)\.(\d+)"),
    # https://shopee.vn/universal-link/product/{shop_id}/{item_id}
    re.compile(r"/universal-link/product/(\d+)/(\d+)"),
]


def extract_ids_from_url(url: str) -> tuple[int | None, int | None]:
    """Extract (shop_id, item_id) tuple from a Shopee Vietnam URL.

    Returns (None, None) if the URL is not a recognized Shopee product format.
    """
    if not url or not isinstance(url, str):
        return None, None

    unquoted = unquote(url.strip())
    parsed = urlparse(unquoted)

    # Check query params for itemid & shopid (or snake_case item_id & shop_id)
    if parsed.query:
        qs = parse_qs(parsed.query)
        s_val = qs.get("shopid") or qs.get("shop_id")
        i_val = qs.get("itemid") or qs.get("item_id")
        if s_val and i_val:
            try:
                return int(s_val[0]), int(i_val[0])
            except (ValueError, IndexError):
                pass

    # Check path against known patterns
    path = parsed.path
    for pattern in _URL_PATTERNS:
        match = pattern.search(path)
        if match:
            try:
                shop_id = int(match.group(1))
                item_id = int(match.group(2))
                return shop_id, item_id
            except (ValueError, IndexError):
                continue

    return None, None


class ShopeePriceNormalizer:
    """Facade for Shopee Vietnam price and product data normalizations."""

    @staticmethod
    def normalize_price(raw_price: int | float | str | Decimal | None) -> Decimal | None:
        return normalize_price(raw_price)

    @staticmethod
    def normalize_rating(raw_rating: float | int | str | None) -> float:
        return normalize_rating(raw_rating)

    @staticmethod
    def normalize_discount(
        current_price: Decimal | None,
        original_price: Decimal | None,
        raw_discount: int | str | None = None,
    ) -> int:
        return normalize_discount(current_price, original_price, raw_discount)

    @staticmethod
    def normalize_product_url(
        shop_id: int | str, item_id: int | str, name: str | None = None
    ) -> str:
        return normalize_product_url(shop_id, item_id, name)

    @staticmethod
    def extract_ids_from_url(url: str) -> tuple[int | None, int | None]:
        return extract_ids_from_url(url)
