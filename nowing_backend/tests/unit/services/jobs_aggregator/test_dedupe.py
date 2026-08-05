"""Deduplicate cross-source job listings."""

from __future__ import annotations

import pytest

from app.services.jobs_aggregator.dedupe import deduplicate
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = pytest.mark.unit


def test_dedupe_same_job_across_sources():
    listings = [
        VnJobAggregatedListing(
            id="vw:123",
            title="Data Engineer",
            company="FPT",
            location="Hà Nội",
            source="vietnamworks",
            source_urls=["https://vietnamworks.com/123"],
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="it:456",
            title="Data Engineer",
            company="FPT",
            location="Hà Nội",
            source="itviec",
            source_urls=["https://itviec.com/456"],
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)

    assert len(merged) == 1
    assert merged[0].source == "multiple"
    assert set(merged[0].source_urls) == {
        "https://vietnamworks.com/123",
        "https://itviec.com/456",
    }
