"""ATDD tests for location_normalize shared module (AC-2, AC-4, Q1 resolved decision).

Covers diacritics stripping, slug generation, city-code resolution,
and alias mapping for Vietnamese provinces.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


def test_remove_diacritics_strips_vietnamese_diacritics():
    """should resolve 'Hà Nội' → 'ha noi' (diacritics stripped, đ→d)."""
    from app.services.location_normalize import remove_diacritics

    assert remove_diacritics("Hà Nội") == "ha noi"
    assert remove_diacritics("Đà Nẵng") == "da nang"


def test_remove_diacritics_handles_none_and_empty():
    """should resolve None → '' and '' → ''."""
    from app.services.location_normalize import remove_diacritics

    assert remove_diacritics(None) == ""
    assert remove_diacritics("") == ""


def test_to_slug_produces_hyphenated_slug():
    """should resolve 'Hà Nội' → 'ha-noi' (slugified)."""
    from app.services.location_normalize import to_slug

    assert to_slug("Hà Nội") == "ha-noi"
    assert to_slug("Tp. Hồ Chí Minh") == "tp-ho-chi-minh"


def test_resolve_city_code_hanoi_alias():
    """should resolve 'Hà Nội' → 'HN' (diacritics-stripped alias match)."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code("Hà Nội") == "HN"
    assert resolve_city_code("hanoi") == "HN"
    assert resolve_city_code("HN") == "HN"


def test_resolve_city_code_hcm_alias():
    """should resolve 'Tp.HCM' → 'SG' (alias)."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code("Tp.HCM") == "SG"
    assert resolve_city_code("Hồ Chí Minh") == "SG"
    assert resolve_city_code("Saigon") == "SG"
    assert resolve_city_code("tphcm") == "SG"


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking
# ---------------------------------------------------------------------------


def test_resolve_city_code_unknown_returns_none():
    """should handle unknown city 'Mars Colony' → None (no crash)."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code("Mars Colony") is None


def test_resolve_city_code_none_input_returns_none():
    """should handle None input → None."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code(None) is None


def test_remove_diacritics_on_english_text():
    """should handle non-Vietnamese text safely (unicodedata works on all Unicode)."""
    from app.services.location_normalize import remove_diacritics

    assert remove_diacritics("New York") == "new york"
    assert remove_diacritics("Tokyo") == "tokyo"


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases
# ---------------------------------------------------------------------------


def test_resolve_city_code_prefix_stripped():
    """should resolve 'thanh-pho-ha-noi' → 'HN' (prefix-stripped)."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code("Thành phố Hà Nội") == "HN"
    assert resolve_city_code("Tỉnh Bình Dương") == "BD"


def test_resolve_city_code_whitespace_only():
    """should handle whitespace-only input → None."""
    from app.services.location_normalize import resolve_city_code

    assert resolve_city_code("   ") is None


def test_city_aliases_covers_63_provinces():
    """should have 64 city codes covering all 63 Vietnamese provinces (63 provinces + Long Bien district)."""
    from app.services.location_normalize import CITY_CODES

    assert len(CITY_CODES) == 64
    assert "HN" in CITY_CODES
    assert "SG" in CITY_CODES
