"""Offline parser tests for the Chotot BĐS scraper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.chotot.parsers import parse_listing, parse_listings
from app.proprietary.platforms.chotot.schemas import ChototBdsListing

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> list[dict]:
    decoded = json.loads(
        (_FIXTURE_DIR / "sample_ad_listing.json").read_text(encoding="utf-8")
    )
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
