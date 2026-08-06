"""Unit tests for BDS and Jobs canonical conventions (AD-27)."""

from __future__ import annotations

import pytest

from app.services.bds_aggregator import fingerprint, merge, search_text
from app.services.bds_aggregator.schemas import VnBdsAggregatedListing
from app.services.jobs_aggregator import (
    fingerprint as job_fingerprint,
    merge as job_merge,
    search_text as job_search_text,
)
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = [pytest.mark.unit]


class TestBdsConvention:
    """BDS exposes stable ``fingerprint``, ``merge`` and ``search_text`` exports."""

    def test_fingerprint_signature_and_stability(self):
        raw = {
            "listing_id": "123",
            "title": "Nhà phố Quận 7",
            "district": "Quận 7",
            "location": "Hồ Chí Minh",
        }
        fp1 = fingerprint(raw)
        fp2 = fingerprint(raw)
        assert isinstance(fp1, str)
        assert fp1 == fp2
        assert len(fp1) >= 16

    def test_fingerprint_changes_with_identity(self):
        raw1 = {"listing_id": "123", "title": "A"}
        raw2 = {"listing_id": "124", "title": "A"}
        assert fingerprint(raw1) != fingerprint(raw2)

    def test_merge_signature_and_behavior(self):
        canonical = {
            "source": "batdongsan",
            "title": "Nhà phố",
            "price_value": 1_000_000_000,
            "area_value": 50.0,
            "district": "Quận 7",
        }
        new_raw = {
            "source": "muaban",
            "title": "Nhà phố Quận 7",
            "price_value": 1_100_000_000,
            "area_value": 50.0,
            "district": "Quận 7",
            "ward": "Tân Phong",
        }
        merged = merge(canonical, new_raw)
        assert isinstance(merged, VnBdsAggregatedListing)
        # The merged listing should pick up the longer title and ward from the new raw.
        assert merged.title == "Nhà phố Quận 7"
        assert merged.ward == "Tân Phong"
        assert "batdongsan" in merged.sources and "muaban" in merged.sources

    def test_search_text_signature(self):
        canonical = VnBdsAggregatedListing(
            canonical_id="c1",
            title="Nhà phố Quận 7",
            location="Hồ Chí Minh",
            district="Quận 7",
            ward="Tân Phong",
            city="Hồ Chí Minh",
            project="Sunrise City",
            price="5 tỷ",
            area="100 m2",
            sources=["batdongsan"],
            confidence_score=0.8,
        )
        text = search_text(canonical)
        assert isinstance(text, str)
        for token in ["Nhà phố Quận 7", "Quận 7", "Tân Phong", "Sunrise City", "5 tỷ"]:
            assert token in text


class TestJobsConvention:
    """Jobs exposes stable ``fingerprint``, ``merge`` and ``search_text`` exports."""

    def test_fingerprint_signature_and_stability(self):
        raw = {
            "id": "job-123",
            "title": "Senior Python Engineer",
            "company": "ACME",
            "location": "Hồ Chí Minh",
            "posted_at": "2026-08-01",
        }
        fp1 = job_fingerprint(raw)
        fp2 = job_fingerprint(raw)
        assert isinstance(fp1, str)
        assert fp1 == fp2
        assert len(fp1) >= 16

    def test_fingerprint_changes_with_identity(self):
        raw1 = {"id": "job-123", "title": "Engineer", "company": "A", "location": "HCM"}
        raw2 = {
            "id": "job-124",
            "title": "Engineer",
            "company": "A",
            "location": "HN",
        }
        assert job_fingerprint(raw1) != job_fingerprint(raw2)

    def test_merge_signature_and_behavior(self):
        canonical = VnJobAggregatedListing(
            id="job-1",
            title="Engineer",
            company="ACME",
            location="Hồ Chí Minh",
            skills=["python"],
            source="topcv",
        )
        new_raw = {
            "source": "vietnamworks",
            "title": "Engineer",
            "company": "ACME",
            "location": "Hồ Chí Minh",
            "skills": ["python", "django"],
        }
        merged = job_merge(canonical, new_raw)
        assert isinstance(merged, VnJobAggregatedListing)
        assert merged.source == "multiple"
        assert "django" in merged.skills

    def test_search_text_signature(self):
        listing = VnJobAggregatedListing(
            id="job-1",
            title="Senior Python Engineer",
            company="ACME",
            location="Hồ Chí Minh",
            skills=["python", "django"],
            employment_type="full_time",
            source="topcv",
        )
        text = job_search_text(listing)
        assert isinstance(text, str)
        for token in [
            "Senior Python Engineer",
            "ACME",
            "python",
            "django",
            "full_time",
        ]:
            assert token in text
