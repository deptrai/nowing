"""Unit tests for ``app.services.bds_aggregator.scoring``."""

from __future__ import annotations

import pytest

from app.services.bds_aggregator.normalize import normalize_listing
from app.services.bds_aggregator.scoring import score_listing

pytestmark = pytest.mark.unit


def _listing(source: str, raw: dict):
    return normalize_listing(source, raw)


def test_single_source_confidence_components():
    raw = {
        "listing_id": 1,
        "title": "Bán nhà",
        "price": "10 Tỷ",
        "area": "75 m²",
        "post_date": "31/07/2026",
        "phone": "0901234567",
        "district": "Ba Đình",
        "detail_url": "https://bd/1",
    }
    listing = _listing("batdongsan", raw)
    scored = score_listing(listing)
    assert scored.source_trust == 0.45
    assert scored.overlap_score == pytest.approx(1 / 3, abs=0.01)
    assert 0.0 <= scored.confidence_score <= 1.0
    assert scored.confidence_score > 0.0


def test_multi_source_confidence_higher():
    a = _listing(
        "batdongsan",
        {
            "listing_id": 1,
            "title": "Bán nhà",
            "price": "10 Tỷ",
            "area": "75 m²",
            "post_date": "31/07/2026",
            "phone": "0901234567",
            "district": "Ba Đình",
            "detail_url": "https://bd/1",
        },
    )
    # Manually merge like the deduper would.
    a.source_ids = {"batdongsan": 1, "chotot_bds": 2}
    a.sources = ["batdongsan", "chotot_bds"]
    a.source_count = 2
    a.source_prices = {"batdongsan": 10_000_000_000, "chotot_bds": 10_000_000_000}
    a.price_value = 10_000_000_000
    scored = score_listing(a)
    assert scored.source_count == 2
    assert scored.overlap_score == pytest.approx(2 / 3, abs=0.01)
    assert scored.price_consistency_score == 1.0
