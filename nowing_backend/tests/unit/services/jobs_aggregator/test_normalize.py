"""Red-phase ATDD tests for jobs_aggregator normalize (AC-2).

Tests are SKIPPED until ``_normalize_experience()`` and
``location_normalize`` integration are implemented.
Existing passing tests are kept (not skipped) — only NEW tests are skipped.
"""

from __future__ import annotations

import datetime

import pytest

from app.services.jobs_aggregator.normalize import normalize_listing
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Existing passing test (keep green)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: salary parsing for 0/0 negotiable")
def test_normalize_salary_zero_zero_is_negotiable():
    """should resolve salary_min=0, salary_max=0 → period='negotiable', confidence=0.5."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_min": 0, "salary_max": 0}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.period == "negotiable"
    assert listing.salary.confidence == 0.5


@pytest.mark.skip(reason="red-phase: salary parsing for min>0, max=0")
def test_normalize_salary_min_only():
    """should resolve salary_min>0, salary_max=0 → min=min_v, max=None, confidence=0.7."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_min": 30000000, "salary_max": 0}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.min == 30000000
    assert listing.salary.max is None
    assert listing.salary.confidence == 0.7


@pytest.mark.skip(reason="red-phase: salary parsing for both present")
def test_normalize_salary_both_present():
    """should resolve salary_min>0, salary_max>0 → confidence=0.8."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_min": 20000000, "salary_max": 40000000}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.min == 20000000
    assert listing.salary.max == 40000000
    assert listing.salary.confidence == 0.8


@pytest.mark.skip(reason="red-phase: salary hidden when no raw")
def test_normalize_salary_hidden():
    """should resolve no salary_raw → period='hidden', confidence=0.0."""
    raw = {"id": "1", "title": "Dev", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.salary.period == "hidden"
    assert listing.salary.confidence == 0.0


@pytest.mark.skip(reason="red-phase: salary negotiable text")
def test_normalize_salary_negotiable_text():
    """should resolve 'thương lượng' → period='negotiable', confidence=0.5."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_raw": "Thương lượng"}
    listing = normalize_listing("topcv", raw)
    assert listing.salary.period == "negotiable"
    assert listing.salary.confidence == 0.5


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: posted_at parsing
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: posted_at Vietnamese relative text")
def test_normalize_posted_at_hom_nay():
    """should resolve 'hôm nay' → today's date."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "hôm nay"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today()


@pytest.mark.skip(reason="red-phase: posted_at Vietnamese relative text")
def test_normalize_posted_at_hom_qua():
    """should resolve 'hôm qua' → yesterday's date."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "hôm qua"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today() - datetime.timedelta(days=1)


@pytest.mark.skip(reason="red-phase: posted_at Vietnamese relative text")
def test_normalize_posted_at_n_ngay_truoc():
    """should resolve '3 ngày trước' → 3 days ago."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "3 ngày trước"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today() - datetime.timedelta(days=3)


@pytest.mark.skip(reason="red-phase: posted_at dd/mm/yyyy format")
def test_normalize_posted_at_dd_mm_yyyy():
    """should resolve '05/08/2026' → date(2026, 8, 5)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "05/08/2026"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date(2026, 8, 5)


@pytest.mark.skip(reason="red-phase: posted_at None")
def test_normalize_posted_at_none():
    """should handle posted_at=None → None (not crash)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": None}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at is None


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: experience_years (NEW _normalize_experience)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: _normalize_experience not implemented")
def test_normalize_experience_years_text_3_plus():
    """should resolve '3+ years' → 3."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": "3+ years"}
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years == 3


@pytest.mark.skip(reason="red-phase: _normalize_experience not implemented")
def test_normalize_experience_years_text_khong_yeu_cau():
    """should resolve 'Không yêu cầu' → 0 or None."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": "Không yêu cầu"}
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years in (0, None)


@pytest.mark.skip(reason="red-phase: _normalize_experience not implemented")
def test_normalize_experience_years_int_passthrough():
    """should resolve int 5 → 5 (passthrough)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": 5}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.experience_years == 5


@pytest.mark.skip(reason="red-phase: _normalize_experience not implemented")
def test_normalize_experience_years_none():
    """should handle experience_years=None → None."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": None}
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years is None


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: skills None handling")
def test_normalize_skills_none_returns_empty_list():
    """should handle raw.get('skills')=None → skills=[] (not crash)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "skills": None}
    listing = normalize_listing("itviec", raw)
    assert listing.skills == []


@pytest.mark.skip(reason="red-phase: source_url None handling")
def test_normalize_source_url_none():
    """should handle source_url=None → source_urls=[''] (not [])."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "source_url": None}
    listing = normalize_listing("itviec", raw)
    assert listing.source_urls == [""]


@pytest.mark.skip(reason="red-phase: id None → derived source_record_id")
def test_normalize_id_none_derives_stable_id():
    """should handle id=None → derive stable source_record_id via SHA-256."""
    raw_a = {"title": "Dev", "company": "Co", "location": "HN", "posted_at": "2026-08-05"}
    raw_b = {"title": "Dev", "company": "Co", "location": "HN", "posted_at": "2026-08-05"}
    listing_a = normalize_listing("itviec", raw_a)
    listing_b = normalize_listing("itviec", raw_b)
    assert listing_a.id == listing_b.id  # deterministic
    assert listing_a.id.startswith("itviec:")  # prefixed with source


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: empty title → confidence 0.3")
def test_normalize_empty_title_confidence_03():
    """should compute confidence_score=0.3 when title is empty."""
    raw = {"id": "1", "title": "", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == 0.3


@pytest.mark.skip(reason="red-phase: empty company → confidence 0.3")
def test_normalize_empty_company_confidence_03():
    """should compute confidence_score=0.3 when company is empty."""
    raw = {"id": "1", "title": "Dev", "company": ""}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == 0.3


@pytest.mark.skip(reason="red-phase: both title+company present → confidence 0.6")
def test_normalize_both_present_confidence_06():
    """should compute confidence_score=0.6 when both title and company are non-empty."""
    raw = {"id": "1", "title": "Dev", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == 0.6


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: salary confidence exact values")
def test_normalize_salary_confidence_exact_values():
    """should compute salary.confidence as exactly 0.5 for negotiable, 0.7 for min-only, 0.8 for both."""
    # negotiable
    listing_n = normalize_listing("vw", {"id": "1", "title": "D", "company": "C", "salary_raw": "Thương lượng"})
    assert listing_n.salary.confidence == 0.5
    # min only
    listing_m = normalize_listing("vw", {"id": "2", "title": "D", "company": "C", "salary_min": 10, "salary_max": 0})
    assert listing_m.salary.confidence == 0.7
    # both
    listing_b = normalize_listing("vw", {"id": "3", "title": "D", "company": "C", "salary_min": 10, "salary_max": 20})
    assert listing_b.salary.confidence == 0.8


# ---------------------------------------------------------------------------
# Pattern 5 — Error message
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: normalize_listing is total (no raise)")
def test_normalize_does_not_raise_on_any_input():
    """should NOT raise on any raw input — normalize_listing is total."""
    # Empty dict
    listing = normalize_listing("itviec", {})
    assert isinstance(listing, VnJobAggregatedListing)
    # All None values
    listing = normalize_listing("itviec", {"title": None, "company": None, "location": None})
    assert isinstance(listing, VnJobAggregatedListing)


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: PrivateAttrs excluded
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="red-phase: PrivateAttrs should not serialize")
def test_normalize_private_attrs_not_in_dump():
    """should NOT return _source_record_ids or _source_url_map in serialized output."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "source_url": "https://example.com"}
    listing = normalize_listing("itviec", raw)
    dumped = listing.model_dump()
    assert "_source_record_ids" not in dumped
    assert "_source_url_map" not in dumped
