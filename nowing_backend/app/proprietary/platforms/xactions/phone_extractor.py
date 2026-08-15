"""Vietnamese Obfuscated Phone Number & Entity Extractor (AD-SOC-5).

3-step extraction pipeline:
1. Pre-normalization: Replace Vietnamese written numbers ('không', 'chín'...),
   homoglyphs ('o/O' -> '0', 'l/I' -> '1'), and strip punctuation delimiters.
2. Regex pattern matching: Standard 10-digit Vietnamese mobile prefixes
   (03, 05, 07, 08, 09, +84).
3. Anti-ReDoS boundary with strict time and length limits.
"""

from __future__ import annotations

import re
import time
from typing import Any

# Vietnamese word-to-digit dictionary
_WORD_TO_DIGIT_MAP = {
    "không": "0", "khong": "0",
    "một": "1", "mot": "1", "mốt": "1",
    "hai": "2",
    "ba": "3",
    "bốn": "4", "bon": "4", "tư": "4", "tu": "4",
    "năm": "5", "nam": "5", "lăm": "5", "lam": "5",
    "sáu": "6", "sau": "6",
    "bảy": "7", "bay": "7", "bẩy": "7",
    "tám": "8", "tam": "8",
    "chín": "9", "chin": "9",
}

_VN_WORDS_COMBINED_REGEX = re.compile(
    r"\b(không|khong|một|mot|mốt|hai|ba|bốn|bon|tư|tu|năm|nam|lăm|lam|sáu|sau|bảy|bay|bẩy|tám|tam|chín|chin)\b",
    re.IGNORECASE,
)

# Common letter substitutions in phone numbers
_LETTER_SUBSTITUTIONS = [
    (re.compile(r"[oOóòỏõọôốồổỗộơớờởỡợ]", re.IGNORECASE), "0"),
    (re.compile(r"[lLiI|]", re.IGNORECASE), "1"),
]

# Valid Vietnamese mobile prefixes (10 digits total: 03x, 05x, 07x, 08x, 09x)
# (?<!\d) prevents matching middle digits of long bank accounts or order IDs (EC-04)
_VN_PHONE_REGEX = re.compile(
    r"(?<!\d)(?:\+?84|0)(?:3[2-9]|5[25689]|7[06-9]|8[1-9]|9\d)\d{7}(?!\d)"
)

# Email regex
_EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Price regex (Vietnamese real estate / commerce)
_PRICE_REGEX = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:tỷ|ty|triệu|trieu|tr|k|đ|vnd|usd|củ|lít|đồng|dong))\b",
    re.IGNORECASE,
)

# Common Vietnamese key locations
_VN_PROVINCES = [
    "Hà Nội", "Hà nội", "Ha Noi", "ha nội", "ha noi", "HN",
    "TP.HCM", "TPHCM", "Hồ Chí Minh", "Ho Chi Minh", "Sài Gòn", "Sai Gon", "HCM",
    "Đà Nẵng", "Da Nang", "Hải Phòng", "Hai Phong", "Cần Thơ", "Can Tho",
    "Bình Dương", "Binh Duong", "Đồng Nai", "Dong Nai", "Bà Rịa - Vũng Tàu", "Vũng Tàu",
    "Long An", "Quảng Ninh", "Bắc Ninh", "Hải Dương", "Hưng Yên", "Vĩnh Phúc",
    "Khánh Hòa", "Nha Trang", "Lâm Đồng", "Đà Lạt", "Bình Thuận", "Phan Thiết",
    "Cầu Giấy", "Nam Từ Liêm", "Bắc Từ Liêm", "Thanh Xuân", "Đống Đa", "Ba Đình",
    "Hoàn Kiếm", "Hai Bà Trưng", "Hoàng Mai", "Long Biên", "Hà Đông", "Tây Hồ",
    "Gia Lâm", "Đông Anh", "Thanh Trì", "Hoài Đức",
    "Quận 1", "Quận 2", "Quận 3", "Quận 4", "Quận 5", "Quận 6", "Quận 7", "Quận 8",
    "Quận 9", "Quận 10", "Quận 11", "Quận 12", "Bình Thạnh", "Thủ Đức", "Gò Vấp",
    "Phú Nhuận", "Tân Bình", "Tân Phú", "Bình Tân", "Nhà Bè", "Hóc Môn", "Củ Chi", "Bình Chánh"
]


def normalize_vietnamese_text(text: str) -> str:
    """Step 1 & 2: Pre-normalize text for entity and phone extraction."""
    if not text:
        return ""

    def _sub_word(match: re.Match) -> str:
        return _WORD_TO_DIGIT_MAP.get(match.group(0).lower(), match.group(0))

    normalized = _VN_WORDS_COMBINED_REGEX.sub(_sub_word, text)

    # In contexts that look like phone numbers (digits + letters mixed),
    # replace letter substitutions and handle delimiters (/, :, (), *)
    def _sub_phone_candidate(match: re.Match) -> str:
        token = match.group(0)
        token = re.sub(r"[oOóòỏõọôốồổỗộơớờởỡợ]", "0", token)
        token = re.sub(r"[lLiI|]", "1", token)
        token = re.sub(r"[/:()*]", " ", token)
        return token

    # Match tokens with mixed letters, digits and phone punctuation
    token_pattern = re.compile(r"(?:\+?84|0|\b)[0-9oOóòỏõọôốồổỗộơớờởỡợlLiI|._\-\s/:()*]{7,25}(?:\b|(?=[^\w]))", re.IGNORECASE)
    normalized = token_pattern.sub(_sub_phone_candidate, normalized)

    return normalized


def extract_phone_numbers(text: str, timeout_sec: float = 0.05) -> list[str]:
    """Step 3: Extract valid Vietnamese phone numbers with anti-ReDoS guard."""
    if not text:
        return []

    start_time = time.perf_counter()

    # Pre-normalize
    normalized = normalize_vietnamese_text(text)

    # Clean intermediate delimiters inside potential digit clusters
    # E.g., "090.123.4567", "09 12 34 56 78", "+84 987 654 321"
    cleaned_candidates = re.findall(r"(?:\+?\d{1,4}[.\s\-_/:()*]*)?\d{2,4}(?:[.\s\-_/:()*]*\d{2,4}){2,5}", normalized)

    results: set[str] = set()

    for candidate in cleaned_candidates:
        if (time.perf_counter() - start_time) > timeout_sec:
            # ReDoS protection timeout hit
            break

        digits_only = re.sub(r"[^\d+]", "", candidate)
        if digits_only.startswith("+84"):
            digits_only = "0" + digits_only[3:]
        elif digits_only.startswith("84") and len(digits_only) == 11:
            digits_only = "0" + digits_only[2:]

        if _VN_PHONE_REGEX.fullmatch(digits_only):
            results.add(digits_only)

    # Direct search on normalized string as well
    compact_normalized = re.sub(r"(?<=\d)[.\s\-_]+(?=\d)", "", normalized)
    for match in _VN_PHONE_REGEX.finditer(compact_normalized):
        if (time.perf_counter() - start_time) > timeout_sec:
            break
        phone = match.group(0)
        if phone.startswith("+84"):
            phone = "0" + phone[3:]
        elif phone.startswith("84") and len(phone) == 11:
            phone = "0" + phone[2:]
        if len(phone) == 10 and phone.startswith("0"):
            results.add(phone)

    return sorted(results)


def classify_social_intent(text: str) -> str:
    """Classify social post intent into sell, buy, hiring, seeking, news, other."""
    if not text:
        return "other"

    lower = text.lower()

    # Hiring keywords
    hiring_keywords = [
        "tuyển", "tuyển dụng", "cần tuyển", "hiring", "job", "mức lương",
        "hoa hồng", "apply", "gửi cv", "jd", "phỏng vấn", "đãi ngộ"
    ]
    if any(k in lower for k in hiring_keywords):
        return "hiring"

    # Seeking keywords
    seeking_keywords = [
        "tìm việc", "tìm job", "ứng tuyển", "tìm thuê", "cần thuê",
        "tìm trọ", "tìm phòng", "tìm nguồn", "tìm đối tác", "cần tìm đối tác"
    ]
    if any(k in lower for k in seeking_keywords):
        return "seeking"

    # Sell keywords
    sell_keywords = [
        "bán", "cần bán", "bán gấp", "chính chủ bán", "pass", "pass lại",
        "thanh lý", "nhượng", "chuyển nhượng", "xả hàng", "giá bán",
        "bán nhà", "bán đất", "bán căn hộ", "bán xe"
    ]
    if any(k in lower for k in sell_keywords):
        return "sell"

    # Buy keywords
    buy_keywords = [
        "mua", "cần mua", "tìm mua", "mua đất", "mua nhà", "gom hàng",
        "thu mua", "mua lại", "cần tìm mua"
    ]
    if any(k in lower for k in buy_keywords):
        return "buy"

    # News / Information
    news_keywords = ["tin tức", "thông báo", "cảnh báo", "tin nóng", "cập nhật"]
    if any(k in lower for k in news_keywords):
        return "news"

    return "other"


_PROVINCES_COMBINED_REGEX = re.compile(
    r"\b(?:" + "|".join(map(re.escape, sorted(_VN_PROVINCES, key=len, reverse=True))) + r")\b",
    re.IGNORECASE,
)


class SocialEntityExtractor:
    """Extracts contact phones, emails, prices, locations and intent tags."""

    def __init__(self, timeout_sec: float = 0.05):
        self.timeout_sec = timeout_sec

    def extract_phones(self, text: str, timeout_sec: float | None = None) -> list[str]:
        return extract_phone_numbers(text, timeout_sec=timeout_sec or self.timeout_sec)

    def extract_emails(self, text: str) -> list[str]:
        if not text:
            return []
        matches = _EMAIL_REGEX.findall(text)
        return sorted(set(matches))

    def extract_prices(self, text: str) -> list[str]:
        if not text:
            return []
        matches = _PRICE_REGEX.findall(text)
        return [m.strip() for m in matches if m.strip()]

    def extract_locations(self, text: str) -> list[str]:
        if not text:
            return []
        matches = _PROVINCES_COMBINED_REGEX.findall(text)
        return sorted(set(matches))

    def classify_intent(self, text: str) -> str:
        return classify_social_intent(text)

    def extract_all(self, text: str) -> dict[str, Any]:
        """Run complete 3-step extraction pipeline."""
        phones = self.extract_phones(text)
        emails = self.extract_emails(text)
        prices = self.extract_prices(text)
        locations = self.extract_locations(text)
        intent = self.classify_intent(text)

        return {
            "phones": phones,
            "emails": emails,
            "prices": prices,
            "locations": locations,
            "intent": intent,
        }
