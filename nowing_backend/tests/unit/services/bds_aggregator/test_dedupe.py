"""Unit tests for ``app.services.bds_aggregator.dedupe``."""

from __future__ import annotations

import pytest

from app.services.bds_aggregator.dedupe import deduplicate
from app.services.bds_aggregator.normalize import normalize_listing

pytestmark = pytest.mark.unit


def _listing(source: str, raw: dict) -> any:  # type: ignore[no-redef]
    return normalize_listing(source, raw)


def test_phone_dedupe_merges_same_phone():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán nhà Ba Đình",
            "price": "19.8 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "phone": "0901234567",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Bán nhà Ba Đình",
            "price": "19.5 tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "phone": "0901 234.567",
            "detail_url": "https://ct/2",
        },
    )
    merged = deduplicate([a, b])
    assert len(merged) == 1
    assert sorted(merged[0].sources) == ["batdongsan", "chotot_bds"]
    assert merged[0].source_count == 2
    assert merged[0].source_ids == {"batdongsan": 1, "chotot_bds": 2}
    assert "chotot_bds" in merged[0].detail_urls


def test_address_dedupe_merges_same_district_ward():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán nhà Quận 1",
            "price": "8.5 Tỷ",
            "area": "50 m²",
            "district": "Quận 1",
            "ward": "Phường Bến Nghé",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "muaban_bds",
        {
            "listing_id": 3,
            "title": "Nhà Quận 1",
            "price": "8.7 Tỷ",
            "area": "52 m²",
            "district": "Quận 1",
            "ward": "Phường Bến Nghé",
            "detail_url": "https://mb/3",
        },
    )
    merged = deduplicate([a, b])
    assert len(merged) == 1


def test_transitive_dedupe_merges_linked_group():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "A",
            "price": "10 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "phone": "0901234567",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "B",
            "price": "10.2 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "ward": "Vĩnh Phúc",
            "location": "Phố Nguyễn Thái Học",
            "phone": "0901234567",
            "detail_url": "https://ct/2",
        },
    )
    c = _listing(
        "muaban_bds",
        {
            "listing_id": 3,
            "title": "C",
            "price": "10.1 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "ward": "Vĩnh Phúc",
            "location": "Phố Nguyễn Thái Học",
            "detail_url": "https://mb/3",
        },
    )
    merged = deduplicate([a, b, c])
    assert len(merged) == 1
    assert sorted(merged[0].sources) == ["batdongsan", "chotot_bds", "muaban_bds"]


def test_image_dedupe_merges_same_image():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "A",
            "price": "10 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "thumbnail_url": "https://example.com/img.jpg",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "B",
            "price": "10.2 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "thumbnail_url": "https://example.com/img.jpg",
            "detail_url": "https://ct/2",
        },
    )
    merged = deduplicate([a, b])
    assert len(merged) == 1
    assert sorted(merged[0].sources) == ["batdongsan", "chotot_bds"]


def test_price_conflict_flag():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán nhà Ba Đình",
            "price": "10 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "phone": "0901234567",
            "detail_url": "https://bd/1",
        },
    )
    b = _listing(
        "chotot_bds",
        {
            "listing_id": 2,
            "title": "Bán nhà Ba Đình",
            "price": "14 Tỷ",
            "area": "75 m²",
            "district": "Ba Đình",
            "phone": "0901234567",
            "detail_url": "https://ct/2",
        },
    )
    merged = deduplicate([a, b])
    assert len(merged) == 1
    assert len(merged[0].conflict_flags) == 1
    assert merged[0].conflict_flags[0].type == "price_conflict"
    assert merged[0].conflict_flags[0].price_range["min"] == 10_000_000_000
    assert merged[0].conflict_flags[0].price_range["max"] == 14_000_000_000
