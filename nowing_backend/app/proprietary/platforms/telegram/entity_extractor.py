"""Entity extraction and NLP intent classification for Telegram messages (Story 22.1 / AD-4)."""

from __future__ import annotations

import re
from typing import Any

from app.proprietary.platforms.telegram.schemas import ExtractedEntities

# Vietnamese phone number patterns: 03x, 05x, 07x, 08x, 09x, (+84)
# Supports spacing, dots, dashes: 0912.345.678, 0912 345 678, +84988-123-456
VN_PHONE_REGEX = re.compile(
    r"(?:\+84|84|0)(?:3[2-9]|5[25689]|7[06-9]|8[1-9]|9[0-9])(?:[.\s-]?[0-9]{1,4}){2,4}\b"
)

# Email address regex
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Vietnamese real estate & transaction prices regex
# e.g., "12.5 tỷ", "850 triệu", "15 tr/tháng", "120 triệu/m2", "$2,500/tháng", "5.2 ty"
PRICE_REGEX = re.compile(
    r"(?:\$\s*\d+(?:,\d{3})*(?:\.\d+)?(?:\s*/\s*(?:tháng|m2|m²|month|mo))?|"
    r"\b\d+(?:[.,]\d+)?\s*(?:tỷ|ty|triệu|trieu|tr|nghìn|ngàn|k|vnd|đ|d)(?:\s*/\s*(?:m2|m²|tháng|thang|th|năm|nam))?)",
    re.IGNORECASE,
)

# Hashtags regex (supports Unicode Vietnamese)
HASHTAG_REGEX = re.compile(r"#[a-zA-Z0-9_\u00C0-\u1EF9]+")

# Intent keywords
INTENT_KEYWORDS = {
    "news": [
        "tin tức", "thông báo", "bản tin", "cập nhật thị trường", "diễn biến thị trường",
        "quy hoạch", "chính sách mới", "lãi suất", "news",
    ],
    "buy": [
        "cần mua", "tìm mua", "cần tìm mua", "thu mua", "hỏi mua", "mua lại",
        "looking to buy", "want to buy",
    ],
    "seeking": [
        "cần thuê", "tìm thuê", "tìm người", "tuyển dụng", "cần tìm", "tìm kiếm",
        "looking for", "seeking", "cần đối tác", "tìm bạn", "ở ghép",
    ],
    "sell": [
        "bán gấp", "chính chủ bán", "cần bán", "bán nhà", "bán đất", "bán căn", "bán ",
        "nhượng lại", "chuyển nhượng", "sang nhượng", "pass lại", "pass ", "thanh lý",
        "cho thuê", "cho mượn", "sale", "for sale", "xả kho",
    ],
}


def clean_phone_number(raw: str) -> str:
    """Normalize phone number to standard 10-digit 09xxxxxxxx format."""
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits


def extract_phone_numbers(text: str) -> list[str]:
    """Extract and normalize unique Vietnamese phone numbers from text."""
    if not text:
        return []
    matches = VN_PHONE_REGEX.findall(text)
    phones = []
    seen = set()
    for match in matches:
        cleaned = clean_phone_number(match)
        if len(cleaned) == 10 and cleaned.startswith(("03", "05", "07", "08", "09")) and cleaned not in seen:
            seen.add(cleaned)
            phones.append(cleaned)
    return phones


def extract_emails(text: str) -> list[str]:
    """Extract unique lowercase email addresses."""
    if not text:
        return []
    matches = EMAIL_REGEX.findall(text)
    emails = []
    seen = set()
    for match in matches:
        cleaned = match.lower().strip(".,;:()")
        if cleaned not in seen:
            seen.add(cleaned)
            emails.append(cleaned)
    return emails


def extract_prices(text: str) -> list[str]:
    """Extract price and valuation expressions."""
    if not text:
        return []
    matches = PRICE_REGEX.findall(text)
    prices = []
    seen = set()
    for match in matches:
        cleaned = match.strip(".,; ")
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            prices.append(cleaned)
    return prices


def extract_hashtags(text: str) -> list[str]:
    """Extract unique hashtags."""
    if not text:
        return []
    matches = HASHTAG_REGEX.findall(text)
    hashtags = []
    seen = set()
    for match in matches:
        tag = match.strip()
        if tag.lower() not in seen:
            seen.add(tag.lower())
            hashtags.append(tag)
    return hashtags


def classify_intent(text: str) -> str:
    """Classify message intent into 'sell', 'buy', 'seeking', or 'news'."""
    if not text:
        return "news"
    lower_text = text.lower().strip()

    # Explicit news headers take highest precedence
    if lower_text.startswith(("tin tức", "thông báo", "bản tin", "tin nhanh")):
        return "news"

    for phrase in INTENT_KEYWORDS["news"]:
        if phrase in lower_text and not any(k in lower_text for k in ("bán gấp", "cần bán", "cần mua", "tìm mua", "cần thuê")):
            return "news"

    # Match buy
    for phrase in INTENT_KEYWORDS["buy"]:
        if phrase in lower_text:
            return "buy"

    # Match seeking
    for phrase in INTENT_KEYWORDS["seeking"]:
        if phrase in lower_text:
            return "seeking"

    # Match sell
    for phrase in INTENT_KEYWORDS["sell"]:
        if phrase in lower_text:
            return "sell"

    return "news"


class TelegramEntityExtractor:
    """Pipeline for extracting structured contact, financial, and semantic entities."""

    def extract(self, text: str) -> ExtractedEntities:
        """Process message text and return ExtractedEntities."""
        phone_numbers = extract_phone_numbers(text)
        emails = extract_emails(text)
        prices = extract_prices(text)
        hashtags = extract_hashtags(text)
        intent_tag = classify_intent(text)

        raw_entities: list[dict[str, Any]] = []

        for phone in phone_numbers:
            raw_entities.append({"type": "phone", "value": phone, "confidence": 0.95})
        for email in emails:
            raw_entities.append({"type": "email", "value": email, "confidence": 0.98})
        for price in prices:
            raw_entities.append({"type": "price", "value": price, "confidence": 0.90})
        for tag in hashtags:
            raw_entities.append({"type": "hashtag", "value": tag, "confidence": 1.0})

        return ExtractedEntities(
            phone_numbers=phone_numbers,
            emails=emails,
            prices=prices,
            hashtags=hashtags,
            intent_tag=intent_tag,
            raw_entities=raw_entities,
        )
