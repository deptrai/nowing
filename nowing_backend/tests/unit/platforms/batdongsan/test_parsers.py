"""Offline parser tests for the Batdongsan scraper.

No network. Uses a captured fixture plus synthetic edge cases to exercise the
raw ``p_sync`` data → ``BatdongsanListing`` mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.batdongsan.parsers import (
    build_detail_url,
    extract_phone_from_title,
    parse_listing,
    parse_listings,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanListing

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_sample() -> list[dict]:
    decoded = json.loads(
        (_FIXTURE_DIR / "sample_p_sync.json").read_text(encoding="utf-8")
    )
    return decoded["data"]


def test_parse_listings_maps_all_fields():
    raw_items = _load_sample()

    listings = parse_listings(raw_items)

    assert len(listings) == 2
    first = listings[0]
    assert isinstance(first, BatdongsanListing)
    assert first.listing_id == 46122640
    assert first.title == "Bán nhà riêng tại Ba Đình"
    assert first.price == "19.8 Tỷ"
    assert first.price_raw == "19.8 Tỷ"
    assert first.area == "75 m²"
    assert first.area_raw == "75 m²"
    assert first.location == "Phường Quán Thánh, Quận Ba Đình, Hà Nội"
    assert first.city == "Hà Nội"
    assert first.district == "Ba Đình"
    assert first.post_date == "31/07/2026"
    assert (
        first.thumbnail_url == "https://file4.batdongsan.com.vn/crop/200x200/some.jpg"
    )
    assert (
        first.detail_url
        == "https://batdongsan.com.vn/nha-dat-ban-ba-dinh/some-pr46122640"
    )
    assert first.latitude == 21.0286146035022
    assert first.longitude == 105.812719675434
    assert first.rooms == 18


def test_parse_listing_returns_none_fields_for_missing_optional():
    raw = {
        "id": 999,
        "title": "Sample",
        "price": "Thỏa thuận",
        "area": None,
        "avatar": None,
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


def test_parse_listings_parses_rent_listing():
    raw_items = _load_sample()
    rent = raw_items[1]

    listings = parse_listings([rent])

    assert len(listings) == 1
    assert listings[0].listing_id == 46122641
    assert listings[0].title == "Cho thuê căn hộ Quận 1"


def test_parse_listing_keeps_area_range_token():
    listing = parse_listing({"id": 1, "area": "72-75 m²"})

    assert listing.area == "72-75 m²"
    assert listing.area_raw == "72-75 m²"


def test_parse_web_listings_extracts_cards():
    from app.proprietary.platforms.batdongsan.parsers import parse_web_listings

    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
    items = parse_web_listings(html)

    assert len(items) == 2
    first = items[0]
    assert first["id"] == 45972873
    assert (
        first["title"]
        == "Bán nhà hẻm 222/20 Thủ Khoa Huân, phường Phú Thủy, DT 102.7m2"
    )
    assert first["price"] == "3,4 tỷ"
    assert first["area"] == "102,7 m²"
    assert first["address"] == "TP. Phan Thiết (P. Phú Thủy mới)"
    assert (
        first["avatar"]
        == "https://file4.batdongsan.com.vn/crop/200x140/2026/06/28/img1_wm.jpg"
    )
    assert (
        first["url"]
        == "https://batdongsan.com.vn/ban-nha-rieng-duong-thu-khoa-huan-phuong-phu-thuy-1-181/ban-hem-222-20-pr45972873"
    )
    assert first["room"] == 2

    second = items[1]
    assert second["id"] == 45972874
    assert second["room"] == 3


def test_parse_web_listings_empty_html():
    from app.proprietary.platforms.batdongsan.parsers import parse_web_listings

    assert parse_web_listings("<html><body></body></html>") == []


def test_parse_web_listings_feeds_into_parse_listing():
    from app.proprietary.platforms.batdongsan.parsers import (
        parse_listing,
        parse_web_listings,
    )

    html = (_FIXTURE_DIR / "web_page.html").read_text(encoding="utf-8")
    items = parse_web_listings(html)
    listing = parse_listing(items[0])

    assert listing.listing_id == 45972873
    assert listing.price == "3,4 tỷ"
    assert listing.area == "102,7 m²"
    assert listing.rooms == 2
    assert listing.thumbnail_url is not None
    assert listing.detail_url is not None


def test_build_detail_url_buy_and_rent():
    assert build_detail_url(
        12345, "Bán nhà riêng tại Ba Đình", "HN", listing_type="buy"
    ) == "https://batdongsan.com.vn/ban-nha-dat-ha-noi/ban-nha-rieng-tai-ba-dinh-pr12345"
    assert build_detail_url(
        12345, "Cho thuê căn hộ Quận 1", "SG", listing_type="rent"
    ) == "https://batdongsan.com.vn/nha-dat-cho-thue-tp-hcm/cho-thue-can-ho-quan-1-pr12345"


def test_build_detail_url_unknown_city_returns_none():
    assert build_detail_url(12345, "Bán nhà", "XX", listing_type="buy") is None


def test_build_detail_url_missing_id_returns_none():
    assert build_detail_url(None, "Bán nhà", "HN", listing_type="buy") is None


def test_extract_phone_from_title_variants():
    assert extract_phone_from_title("LH: 0916754123") == "0916754123"
    assert extract_phone_from_title("LH 0916 754 123") == "0916754123"
    assert extract_phone_from_title("Call 0916.754.123") == "0916754123"
    assert extract_phone_from_title("Bán nhà giá 6.8 tỷ") is None
