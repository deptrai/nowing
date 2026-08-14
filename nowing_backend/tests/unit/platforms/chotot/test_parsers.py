"""Offline parser tests for the Chotot BĐS scraper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.chotot.parsers import parse_listing, parse_listings
from app.proprietary.platforms.chotot.schemas import ChototBdsListing, ChototListing

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> list[dict]:
    decoded = json.loads(
        (_FIXTURE_DIR / "sample_ad_listing.json").read_text(encoding="utf-8")
    )
    return decoded["ads"]


def _load_fixture(name: str) -> list[dict]:
    decoded = json.loads((_FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return decoded["ads"]


def test_parse_listings_maps_all_fields():
    raw_items = _load_sample()

    listings = parse_listings(raw_items)

    assert len(listings) == 2
    first = listings[0]
    assert isinstance(first, ChototBdsListing)
    assert first.listing_id == 133886560
    assert first.ad_id == 177832062
    assert first.title == "Nha Dep hem xe hoi 891/18 hl2"
    assert first.price == "6,3 tỷ"
    assert first.price_raw == "6,3 tỷ"
    assert first.price_value == 6_300_000_000
    assert first.area == "56.7 m²"
    assert first.area_raw == "56.7 m²"
    assert first.district == "Quận Bình Tân"
    assert first.city == "Tp Hồ Chí Minh"
    assert first.ward == "Phường Bình Trị Đông"
    assert first.post_date == "2 giờ trước"
    assert first.thumbnail_url is not None
    assert first.detail_url == "https://www.nhatot.com/133886560.htm"
    assert first.latitude == 10.763908
    assert first.longitude == 106.614395
    assert first.rooms == 2
    assert first.floors == 3
    assert first.toilets == 3
    assert first.listing_type == "buy"
    assert first.property_type == "house"
    assert first.seller_type == "individual"


def test_parse_listing_returns_none_fields_for_missing_optional():
    raw = {
        "list_id": 999,
        "subject": "Sample",
        "price_string": "Thỏa thuận",
        "size": None,
        "thumbnail_image": None,
    }

    listing = parse_listing(raw)

    assert listing.listing_id == 999
    assert listing.price_raw == "Thỏa thuận"
    assert listing.price is None
    assert listing.area is None
    assert listing.area_raw is None
    assert listing.thumbnail_url is None


def test_parse_listings_returns_empty_for_empty_input():
    assert parse_listings([]) == []


def test_parse_price_string_handles_vietnamese_units():
    from app.proprietary.platforms.chotot.parsers import _parse_price_string

    assert _parse_price_string("6,3 tỷ") == 6_300_000_000
    assert _parse_price_string("5 triệu") == 5_000_000
    assert _parse_price_string("3 tr.") == 3_000_000
    assert _parse_price_string("500 nghìn") == 500_000
    assert _parse_price_string("Thỏa thuận") is None
    # Per-square-meter prices must not be converted to a total.
    assert _parse_price_string("5 triệu/m²") is None
    assert _parse_price_string("3 tr/m2") is None
    # Overflowing prices should degrade gracefully.
    assert _parse_price_string("999999999999999999999 tỷ") is None


def test_parse_detail_url_rejects_invalid_list_id():
    from app.proprietary.platforms.chotot.parsers import _build_detail_url

    assert _build_detail_url("abc") is None
    assert _build_detail_url(-1) is None
    assert _build_detail_url("999999999999999999999999") is None
    assert _build_detail_url(133886560) == "https://www.nhatot.com/133886560.htm"


def test_parse_area_rejects_extreme_values():
    from app.proprietary.platforms.chotot.parsers import _format_area

    assert _format_area(float("inf"), None) == (None, None, None)
    assert _format_area(float("nan"), None) == (None, None, None)
    assert _format_area(-5, None) == (None, None, None)
    assert _format_area(1_000_000, None) == (None, None, None)
    assert _format_area(56.7, None) == ("56.7 m²", "56.7 m²", 56.7)


def test_parse_vehicle_listing():
    raw_items = _load_fixture("vehicles")

    listings = parse_listings(raw_items, category="cars")

    assert len(listings) == 1
    first = listings[0]
    assert isinstance(first, ChototListing)
    assert first.category == "cars"
    assert first.listing_id == 177832100
    assert first.title == "Toyota Camry 2.5G 2020 màu đen"
    assert first.price_value == 820_000_000
    assert first.detail_url == "https://xe.chotot.com/177832100.htm"
    assert first.attributes["make"] == "Toyota"
    assert first.attributes["model"] == "Camry"
    assert first.attributes["year"] == 2020
    assert first.attributes["mileage"] == 45000
    assert first.attributes["fuel_type"] == "Xăng"
    assert first.attributes["transmission"] == "Tự động"


def test_parse_motorbike_listing():
    raw_items = _load_fixture("motorbikes")

    listings = parse_listings(raw_items, category="motorbikes")

    assert len(listings) == 1
    first = listings[0]
    assert first.category == "motorbikes"
    assert first.listing_id == 177832101
    assert first.detail_url == "https://xe.chotot.com/177832101.htm"
    assert first.attributes["make"] == "Honda"
    assert first.attributes["model"] == "SH"
    assert first.attributes["year"] == 2019


def test_parse_job_listing():
    raw_items = _load_fixture("jobs")

    listings = parse_listings(raw_items, category="jobs")

    assert len(listings) == 1
    first = listings[0]
    assert isinstance(first, ChototListing)
    assert first.category == "jobs"
    assert first.listing_id == 177832200
    assert first.title == "Tuyển lập trình viên Python"
    assert first.detail_url == "https://vieclamtot.com/177832200.htm"
    assert first.attributes["salary_min"] == 20000000
    assert first.attributes["salary_max"] == 30000000
    assert first.attributes["company_name"] == "TechVN"
    assert first.attributes["job_type"] == "Toàn thời gian"


def test_parse_electronics_listing():
    raw_items = _load_fixture("electronics")

    listings = parse_listings(raw_items, category="electronics")

    assert len(listings) == 1
    first = listings[0]
    assert isinstance(first, ChototListing)
    assert first.category == "electronics"
    assert first.listing_id == 177832300
    assert first.title == "iPhone 14 Pro Max 128GB tím"
    assert first.detail_url == "https://www.chotot.com/177832300.htm"
    assert first.attributes["brand"] == "Apple"
    assert first.attributes["model"] == "iPhone 14 Pro Max"
    assert first.attributes["capacity"] == "128GB"
    assert first.attributes["color"] == "Tím"


def test_parse_unknown_category_is_not_billed():
    raw = {
        "list_id": 177832999,
        "subject": "Unknown item",
        "price_string": "1 triệu",
        "region_name": "Hà Nội",
        "area_name": "Quận Ba Đình",
        "category": 99999,
        "category_name": "Không xác định",
    }

    listing = parse_listing(raw, category="unknown")

    assert isinstance(listing, ChototListing)
    assert listing.category == "unknown"
    assert listing.listing_id == 177832999
