"""Normalize raw job listings."""

from __future__ import annotations

import pytest

from app.services.jobs_aggregator.normalize import normalize_listing
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = pytest.mark.unit


def test_normalize_vietnamworks_listing():
    raw = {
        "id": "123",
        "title": "Senior Data Engineer",
        "company": "ACB",
        "location": "Hà Nội",
        "salary_raw": "Từ 30 triệu",
        "posted_at": "2026-08-05",
        "employment_type": "full_time",
    }
    listing = normalize_listing("vietnamworks", raw)

    assert isinstance(listing, VnJobAggregatedListing)
    assert listing.title == "Senior Data Engineer"
    assert listing.company == "ACB"
    assert listing.location == "Hà Nội"
    assert listing.salary.raw == "Từ 30 triệu"
    assert listing.source == "vietnamworks"
