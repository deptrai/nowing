"""Unit tests for the Muaban BĐS parsers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.proprietary.platforms.muaban_bds.parsers import (
    extract_listings,
    parse_listing,
    parse_listings,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"


def _load_next_data(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_extract_listings_from_city_page():
    data = _load_next_data("hcm_city.json")
    items = extract_listings(data)
    assert len(items) == 20
    assert items[0]["id"] > 0


def test_extract_listings_from_landing_page():
    data = _load_next_data("landing.json")
    items = extract_listings(data)
    assert len(items) > 0


def test_parse_listing_maps_fields():
    data = _load_next_data("hcm_city.json")
    raw = extract_listings(data)[0]
    listing = parse_listing(raw)

    assert listing.dataType == "muaban_bds_listing"
    assert listing.listing_id == raw["id"]
    assert listing.title
    assert listing.price
    assert listing.location
    assert listing.city
    assert listing.district
    assert listing.detail_url.startswith("https://muaban.net")
    assert listing.thumbnail_url.startswith("https://")


def test_parse_listings_preserves_count():
    data = _load_next_data("hcm_city.json")
    raw_items = extract_listings(data)[:3]
    listings = parse_listings(raw_items)
    assert len(listings) == 3
    for listing in listings:
        assert listing.dataType == "muaban_bds_listing"
