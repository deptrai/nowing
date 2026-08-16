"""Vietnamese Entity Extractor for Telegram Messages (Story 22.3 / AC-1).

Extracts and normalizes:
- Vietnamese phone numbers (with homoglyphs, written words, and standard prefixes)
- Prices (tỷ, triệu, k, rental rates) normalized to numeric VND
- Emails
- Administrative locations (provinces, districts)
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.proprietary.platforms.telegram.schemas import ExtractedEntities

# Vietnamese word-to-digit dictionary
_WORD_TO_DIGIT_MAP = {
    "không": "0",
    "khong": "0",
    "một": "1",
    "mot": "1",
    "mốt": "1",
    "hai": "2",
    "ba": "3",
    "bốn": "4",
    "bon": "4",
    "tư": "4",
    "tu": "4",
    "năm": "5",
    "nam": "5",
    "lăm": "5",
    "lam": "5",
    "sáu": "6",
    "sau": "6",
    "bảy": "7",
    "bay": "7",
    "bẩy": "7",
    "tám": "8",
    "tam": "8",
    "chín": "9",
    "chin": "9",
}

_VN_WORDS_COMBINED_REGEX = re.compile(
    r"\b(không|khong|một|mot|mốt|hai|ba|bốn|bon|tư|tu|năm|nam|lăm|lam|sáu|sau|bảy|bay|bẩy|tám|tam|chín|chin)\b",
    re.IGNORECASE,
)

# Valid Vietnamese mobile prefixes (10 digits total: 03x, 05x, 07x, 08x, 09x)
_VN_PHONE_REGEX = re.compile(
    r"(?<!\w)(?:\+?84|0)(?:3[2-9]|5[25689]|7[06-9]|8[1-9]|9\d)\d{7}(?!\w)"
)

# Email regex
_EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}"
)

# Complex Vietnamese real estate price patterns
_PRICE_COMPOUND_REGEX = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(tỷ|ty)\s*(\d+(?:[.,]\d+)*)\s*(triệu|trieu|tr|k)?",
    re.IGNORECASE,
)

_PRICE_SIMPLE_REGEX = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(tỷ|ty|triệu|trieu|tr|k|đ|vnd|đồng|dong)(?:\s*(?:/|\s+mỗi\s+|\s+trên\s*|\s*cho\s*)?\s*(tháng|thang|m2|m²|năm|nam))?",
    re.IGNORECASE,
)


# Common Vietnamese key locations (Provinces & Major Districts)
_VN_LOCATIONS = [
    "Hà Nội",
    "Hà nội",
    "Ha Noi",
    "HN",
    "TP.HCM",
    "TPHCM",
    "Hồ Chí Minh",
    "Ho Chi Minh",
    "Sài Gòn",
    "Sai Gon",
    "HCM",
    "Đà Nẵng",
    "Da Nang",
    "Hải Phòng",
    "Hai Phong",
    "Cần Thơ",
    "Can Tho",
    "Bình Dương",
    "Binh Duong",
    "Đồng Nai",
    "Dong Nai",
    "Bà Rịa - Vũng Tàu",
    "Vũng Tàu",
    "Long An",
    "Quảng Ninh",
    "Bắc Ninh",
    "Hải Dương",
    "Hưng Yên",
    "Vĩnh Phúc",
    "Khánh Hòa",
    "Nha Trang",
    "Lâm Đồng",
    "Đà Lạt",
    "Bình Thuận",
    "Phan Thiết",
    "Cầu Giấy",
    "Nam Từ Liêm",
    "Bắc Từ Liêm",
    "Thanh Xuân",
    "Đống Đa",
    "Ba Đình",
    "Hoàn Kiếm",
    "Hai Bà Trưng",
    "Hoàng Mai",
    "Long Biên",
    "Hà Đông",
    "Tây Hồ",
    "Gia Lâm",
    "Đông Anh",
    "Thanh Trì",
    "Hoài Đức",
    "Quận 1",
    "Quận 2",
    "Quận 3",
    "Quận 4",
    "Quận 5",
    "Quận 6",
    "Quận 7",
    "Quận 8",
    "Quận 9",
    "Quận 10",
    "Quận 11",
    "Quận 12",
    "Bình Thạnh",
    "Thủ Đức",
    "Gò Vấp",
    "Phú Nhuận",
    "Tân Bình",
    "Tân Phú",
    "Bình Tân",
    "Nhà Bè",
    "Hóc Môn",
    "Củ Chi",
    "Bình Chánh",
]

_LOCATIONS_COMBINED_REGEX = re.compile(
    r"\b(?:"
    + "|".join(map(re.escape, sorted(_VN_LOCATIONS, key=len, reverse=True)))
    + r")\b",
    re.IGNORECASE,
)


def _pre_normalize_phone_text(text: str) -> str:
    """Pre-normalize homoglyphs and word numbers in potential phone contexts."""
    if not text:
        return ""

    def _sub_word(match: re.Match) -> str:
        return _WORD_TO_DIGIT_MAP.get(match.group(0).lower(), match.group(0))

    normalized = _VN_WORDS_COMBINED_REGEX.sub(_sub_word, text)

    def _sub_phone_candidate(match: re.Match) -> str:
        token = match.group(0)
        token = re.sub(r"[oOóòỏõọôốồổỗộơớờởỡợ]", "0", token)
        token = re.sub(r"[lLiI|]", "1", token)
        token = re.sub(r"[/:()*]", " ", token)
        return token

    token_pattern = re.compile(
        r"(?:\+?84|0|\b)[0-9oOóòỏõọôốồổỗộơớờởỡợlLiI|._\-\s/:()*]{7,25}(?:\b|(?=[^\w]))",
        re.IGNORECASE,
    )
    return token_pattern.sub(_sub_phone_candidate, normalized)


def _extract_phones(text: str, timeout_sec: float = 0.05) -> list[str]:
    """Extract valid Vietnamese phone numbers with ReDoS protection."""
    if not text:
        return []

    if len(text) > 200000:
        text = text[:200000]

    start_time = time.perf_counter()
    normalized = _pre_normalize_phone_text(text)
    if (time.perf_counter() - start_time) > timeout_sec:
        return []

    cleaned_candidates = re.findall(
        r"(?<!\w)(?:\+?\d{1,4}[.\s\-_/:()*]*)?\d{2,4}(?:[.\s\-_/:()*]*\d{2,4}){2,5}(?!\w)",
        normalized,
    )

    results: set[str] = set()

    for candidate in cleaned_candidates:
        if (time.perf_counter() - start_time) > timeout_sec:
            break

        digits_only = re.sub(r"[^\d+]", "", candidate)
        if digits_only.startswith("+84"):
            digits_only = "0" + digits_only[3:]
        elif digits_only.startswith("84") and len(digits_only) == 11:
            digits_only = "0" + digits_only[2:]

        if _VN_PHONE_REGEX.fullmatch(digits_only):
            results.add(digits_only)

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


def _extract_prices(text: str) -> list[dict[str, Any]]:
    """Extract and normalize Vietnamese prices into numeric VND amounts."""
    if not text:
        return []

    results: list[dict[str, Any]] = []
    seen_raw: set[str] = set()

    # 1. Compound prices: e.g. "18 tỷ 500tr", "18 tỷ 5", "2 tỷ 500k"
    for match in _PRICE_COMPOUND_REGEX.finditer(text):
        raw_text = match.group(0).strip()
        if raw_text in seen_raw:
            continue
        seen_raw.add(raw_text)

        ty_val = float(match.group(1).replace(",", "."))
        second_str = match.group(3).strip()
        second_unit = (
            (match.group(4) or "").lower().strip() if len(match.groups()) >= 4 else ""
        )

        # Check if second part has a 'k' unit or is a single digit
        if "k" in second_unit or second_str.lower().endswith("k"):
            k_val = float(second_str.lower().rstrip("k").replace(",", "."))
            amount_vnd = int(ty_val * 1_000_000_000 + k_val * 1_000)
        else:
            trieu_val = float(second_str.replace(",", "."))
            if trieu_val < 10:  # e.g. "18 tỷ 5" -> 18.5 tỷ
                amount_vnd = int(ty_val * 1_000_000_000 + trieu_val * 100_000_000)
            elif trieu_val < 1000:
                amount_vnd = int(ty_val * 1_000_000_000 + trieu_val * 1_000_000)
            else:
                amount_vnd = int(ty_val * 1_000_000_000 + trieu_val)

        results.append(
            {
                "raw_text": raw_text,
                "amount_vnd": amount_vnd,
                "unit": "tỷ",
                "is_rental": False,
            }
        )

    # 2. Simple prices: e.g. "25.5 tỷ", "8.5 triệu/tháng", "500k/tháng", "500.000 đ"
    for match in _PRICE_SIMPLE_REGEX.finditer(text):
        raw_text = match.group(0).strip()
        if any(raw_text in r for r in seen_raw):
            continue
        seen_raw.add(raw_text)

        raw_num = match.group(1).strip()
        unit = match.group(2).lower()
        period = (match.group(3) or "").lower()
        is_rental = (
            "tháng" in period
            or "thang" in period
            or "/tháng" in raw_text
            or "/thang" in raw_text
        )

        clean_num = raw_num
        if clean_num.count(".") > 1 or (
            clean_num.count(".") == 1
            and len(clean_num.split(".")[1]) == 3
            and unit in ("đ", "vnd", "đồng", "dong")
        ):
            clean_num = clean_num.replace(".", "")
        elif (
            clean_num.count(",") == 1
            and len(clean_num.split(",")[1]) == 3
            and unit in ("đ", "vnd", "đồng", "dong")
        ):
            clean_num = clean_num.replace(",", "")
        else:
            clean_num = clean_num.replace(",", ".")

        try:
            num = float(clean_num)
        except ValueError:
            continue

        if unit in ("tỷ", "ty"):
            amount_vnd = int(num * 1_000_000_000)
            canonical_unit = "tỷ"
        elif unit in ("triệu", "trieu", "tr"):
            amount_vnd = int(num * 1_000_000)
            canonical_unit = "triệu"
        elif unit == "k":
            amount_vnd = int(num * 1_000)
            canonical_unit = "k"
        elif unit in ("đ", "vnd", "đồng", "dong"):
            amount_vnd = int(num)
            canonical_unit = "VND"
        else:
            amount_vnd = int(num)
            canonical_unit = unit

        results.append(
            {
                "raw_text": raw_text,
                "amount_vnd": amount_vnd,
                "unit": canonical_unit,
                "is_rental": is_rental,
            }
        )

    return results


def extract_phone_numbers(text: str) -> list[str]:
    return _extract_phones(text)


def extract_emails(text: str) -> list[str]:
    return sorted(set(_EMAIL_REGEX.findall(text))) if text else []


def extract_prices(text: str) -> list[str]:
    prices = _extract_prices(text)
    return [p["raw_text"] for p in prices]


def extract_hashtags(text: str) -> list[str]:
    return re.findall(r"#\w+", text) if text else []


def classify_intent(text: str) -> str:
    if not text:
        return "news"
    lower = text.lower()
    if any(w in lower for w in ["bán", "cho thuê", "nhượng", "pass", "bán gấp"]):
        return "sell"
    if any(w in lower for w in ["cần mua", "tìm mua", "mua đất", "mua căn"]):
        return "buy"
    if any(w in lower for w in ["cần tìm", "tìm thuê", "ở ghép", "cần thuê"]):
        return "seeking"
    return "news"


class TelegramEntityExtractor:
    """Production entity extraction for Telegram messages and posts."""

    @classmethod
    def extract(cls, text: str | None) -> ExtractedEntities:
        """Extract structured ExtractedEntities model from raw text."""
        if not text or not isinstance(text, str):
            return ExtractedEntities()

        raw_dict = cls.extract_entities(text)
        intent = classify_intent(text)

        prices_list = []
        for p in raw_dict.get("prices", []):
            if isinstance(p, dict) and "raw_text" in p:
                prices_list.append(p["raw_text"])
            elif isinstance(p, str):
                prices_list.append(p)

        raw_entities = []
        for ph in raw_dict.get("phones", []):
            raw_entities.append({"type": "phone", "value": ph})
        for em in raw_dict.get("emails", []):
            raw_entities.append({"type": "email", "value": em})
        for pr in prices_list:
            raw_entities.append({"type": "price", "value": pr})
        for ht in re.findall(r"#\w+", text):
            raw_entities.append({"type": "hashtag", "value": ht})

        return ExtractedEntities(
            phone_numbers=raw_dict.get("phones", []),
            emails=raw_dict.get("emails", []),
            prices=prices_list,
            hashtags=re.findall(r"#\w+", text),
            intent_tag=intent,
            raw_entities=raw_entities,
        )

    @classmethod
    def extract_entities(cls, text: str | None) -> dict[str, Any]:
        """Extract structured entities (phones, prices, emails, locations) from raw text."""
        if not text or not isinstance(text, str):
            return {
                "phones": [],
                "prices": [],
                "emails": [],
                "locations": [],
            }

        phones = _extract_phones(text)

        # Extract emails
        emails = sorted(set(_EMAIL_REGEX.findall(text)))

        # Extract locations
        locations = sorted(set(_LOCATIONS_COMBINED_REGEX.findall(text)))

        # Extract prices
        prices = _extract_prices(text)

        return {
            "phones": phones,
            "prices": prices,
            "emails": emails,
            "locations": locations,
        }

