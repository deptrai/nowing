"""Unit tests for ``app.services.bds_aggregator.normalize``."""

from __future__ import annotations

import pytest

from app.services.bds_aggregator.normalize import (
    _parse_area,
    _parse_price,
    make_canonical_id,
    normalize_listing,
    to_batdongsan_city_code,
)

pytestmark = pytest.mark.unit


def test_city_code_resolves_known_aliases():
    assert to_batdongsan_city_code("Hà Nội") == "HN"
    assert to_batdongsan_city_code("hanoi") == "HN"
    assert to_batdongsan_city_code("hn") == "HN"
    assert to_batdongsan_city_code("Hồ Chí Minh") == "SG"
    assert to_batdongsan_city_code("ho chi minh") == "SG"
    assert to_batdongsan_city_code("tp hcm") == "SG"
    assert to_batdongsan_city_code("Da Nang") == "DN"
    assert to_batdongsan_city_code("Đà Nẵng") == "DN"


def test_city_code_passes_through_existing_code():
    assert to_batdongsan_city_code("HN") == "HN"
    assert to_batdongsan_city_code("SG") == "SG"


def test_city_code_returns_none_for_unknown():
    assert to_batdongsan_city_code("Atlantis") is None


@pytest.mark.parametrize(
    ("text", "price_value", "price_per_m2", "is_per_m2"),
    [
        ("19.8 Tỷ", 19_800_000_000, None, False),
        ("850 triệu", 850_000_000, None, False),
        ("2,5 tỷ/m²", None, 2_500_000_000.0, True),
        ("Thỏa thuận", None, None, False),
        ("Giá thỏa thuận", None, None, False),
    ],
)
def test_parse_price_variants(text, price_value, price_per_m2, is_per_m2):
    pv, ppm, flag = _parse_price(text)
    assert pv == price_value
    assert ppm == price_per_m2
    assert flag is is_per_m2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("75 m²", 75.0),
        ("100m2", 100.0),
        ("5x20m", 100.0),
        ("1.2 ha", 12_000.0),
        ("", None),
    ],
)
def test_parse_area_variants(text, expected):
    assert _parse_area(text) == expected


def test_normalize_listing_maps_fields():
    raw = {
        "listing_id": 123,
        "title": "Bán nhà Ba Đình",
        "price": "19.8 Tỷ",
        "area": "75 m²",
        "location": "Phố Nguyễn Thái Học",
        "district": "Ba Đình",
        "ward": "Vĩnh Phúc",
        "city": "Hà Nội",
        "post_date": "31/07/2026",
        "phone": "0901234567",
        "thumbnail_url": "https://example.com/img.jpg",
        "detail_url": "https://batdongsan.com.vn/123",
    }
    listing = normalize_listing("batdongsan", raw)
    assert listing.title == "Bán nhà Ba Đình"
    assert listing.price_value == 19_800_000_000
    assert listing.area_value == 75.0
    assert listing.price_per_m2 == 19_800_000_000 / 75.0
    assert listing.district == "Ba Đình"
    assert listing.city == "Hà Nội"
    assert listing.phone_key == "901234567"
    assert listing.contact == "0901xxx67"
    assert listing.source_ids == {"batdongsan": 123}


def test_canonical_id_is_deterministic():
    a = make_canonical_id({"batdongsan": 1, "chotot_bds": 2})
    b = make_canonical_id({"chotot_bds": 2, "batdongsan": 1})
    assert a == b
