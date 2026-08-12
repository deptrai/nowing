"""Shared Vietnamese location normalization helpers.

Extracted from ``bds_aggregator/normalize.py`` so both BĐS and jobs aggregators
reuse the same diacritics stripping, slug generation, and city-code resolution.

Ponytail: 62-province table is a V1 snapshot — covers all 63 Vietnamese
provinces/municipalities as of 2026.  If Vietnam adds a new province, append
the code+slug here and both aggregators pick it up.
"""

from __future__ import annotations

import re
import unicodedata

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
    "DNA": "dong-nai",
    "GL": "gia-lai",
    "HAN": "ha-nam",
    "HD": "hai-duong",
    "HG": "ha-giang",
    "HN": "ha-noi",
    "HOB": "hoa-binh",
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
    "QNA": "quang-nam",
    "QN": "quang-ninh",
    "QNG": "quang-ngai",
    "QT": "quang-tri",
    "SG": "tp-hcm",
    "SL": "son-la",
    "ST": "soc-trang",
    "TB": "thai-binh",
    "TG": "tien-giang",
    "TH": "thanh-hoa",
    "TNI": "tay-ninh",
    "TN": "thai-nguyen",
    "TQ": "tuyen-quang",
    "TV": "tra-vinh",
    "TTH": "hue",
    "VL": "vinh-long",
    "VP": "vinh-phuc",
    "VT": "ba-ria-vung-tau",
    "YB": "yen-bai",
}

CITY_CODES: frozenset[str] = frozenset(_CITY_SLUGS)

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
CITY_ALIASES: dict[str, str] = {}
for _code, _slug in _CITY_SLUGS.items():
    CITY_ALIASES[_slug] = _code
    CITY_ALIASES[_slug.replace("-", "")] = _code
    CITY_ALIASES[_code.lower()] = _code
CITY_ALIASES.update(_CITY_OVERRIDES)


def remove_diacritics(value: str | None) -> str:
    """Return an ASCII-ish lowercased copy of ``value``."""
    if not value:
        return ""
    text = unicodedata.normalize("NFD", value)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("\u0111", "d").replace("\u0110", "d")
    return text.lower()


def to_slug(value: str | None) -> str:
    """Make a lowercase, no-diacritic, hyphenated slug."""
    text = remove_diacritics(value or "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def resolve_city_code(user_city: str | None) -> str | None:
    """Resolve free-form Vietnamese city input to a canonical code (e.g. ``HN``).

    Returns ``None`` for unknown cities — callers treat that as "no filter".
    """
    if not user_city:
        return None
    raw = user_city.strip()
    if not raw:
        return None
    # Accept any known city code case-insensitively.
    if raw.upper() in CITY_CODES:
        return raw.upper()

    normalized = to_slug(raw)
    if normalized in CITY_ALIASES:
        return CITY_ALIASES[normalized]

    # Try a few common prefix-stripped forms.
    for prefix in ("tp-", "tinh-", "thanh-pho-", "quan-", "huyen-", "phuong-", "xa-"):
        if normalized.startswith(prefix):
            stripped = normalized[len(prefix) :]
            if stripped in CITY_ALIASES:
                return CITY_ALIASES[stripped]

    return None
