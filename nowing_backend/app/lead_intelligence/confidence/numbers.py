"""Number normalizers shared by the confidence gate and micro-extraction worker."""

from __future__ import annotations

import re
from typing import Any

from app.lead_intelligence.adapters.base import _to_float


def clean_number(raw: str) -> str:
    """Remove non-numeric chars except decimal separators."""
    return re.sub(r"[^0-9.,]", "", raw)


def normalize_number(raw: Any) -> float | None:
    """Convert a Vietnamese formatted number to float.

    Handles both comma and dot separators. When multiple separators are present,
    the rightmost one is treated as the decimal mark and the rest as thousands.
    """
    if isinstance(raw, (int, float)):
        return float(raw) if raw != 0 else None
    if raw is None:
        return None

    text = clean_number(str(raw))
    if not text:
        return None

    dot_count = text.count(".")
    comma_count = text.count(",")
    if dot_count + comma_count <= 1:
        return _to_float(text.replace(",", "."))

    last_dot = text.rfind(".")
    last_comma = text.rfind(",")
    last_sep = max(last_dot, last_comma)
    integer = text[:last_sep].replace(",", "").replace(".", "")
    decimal = text[last_sep + 1 :]
    normalized = f"{integer}.{decimal}" if decimal else integer
    return _to_float(normalized)


def price_unit_factor(unit: str) -> float | None:
    """Convert Vietnamese price unit words to multipliers."""
    unit = unit.lower()
    if unit in ("tỷ", "ty", "tỉ"):
        return 1_000_000_000
    if unit in ("triệu", "trieu", "tr"):
        return 1_000_000
    if unit in ("k", "nghìn", "ngàn", "nghin", "ngan", "củ"):
        return 1_000
    if unit in ("lít", "lit"):
        return 1_000_000
    if unit in ("đ", "dong", "vnd", "usd"):
        return 1
    return None


def is_thoa_thuan_price(price: float | None, raw: dict[str, Any]) -> bool:
    """Return True when price is 0 because the listing is negotiable (thỏa thuận)."""
    if price != 0:
        return False
    price_raw = str(raw.get("price_raw") or "").lower()
    return any(k in price_raw for k in ("thỏa thuận", "thoa thuan"))


def price_to_float(raw: Any) -> float | None:
    """Convert a Vietnamese price string to a positive float."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None

    text = str(raw).strip().lower()
    match = re.search(
        r"([\d.,]+)\s*(tỷ|ty|tỉ|triệu|trieu|tr|k|nghìn|ngàn|nghin|ngan|đ|dong|vnd|củ|lít|lit|usd)",
        text,
        re.IGNORECASE,
    )
    if not match:
        number = normalize_number(text)
        return number if number is not None and number > 0 else None

    number = normalize_number(match.group(1))
    multiplier = price_unit_factor(match.group(2))
    if number is None or multiplier is None:
        return None
    return number * multiplier if number > 0 else None
