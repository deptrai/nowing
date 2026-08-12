"""ATDD tests for jobs_aggregator normalize (AC-2).

Covers salary, location, employment_type, posted_at, experience_years,
and source_url normalization.
"""

from __future__ import annotations

import datetime

import pytest

from app.services.jobs_aggregator.normalize import (
    _normalize_experience,
    _normalize_location,
    _normalize_salary_period,
    _normalize_text,
    _parse_post_date,
    _parse_salary,
    normalize_listing,
)
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
    assert listing.location == "HN"  # now resolves to city code
    assert listing.salary.raw == "Từ 30 triệu"
    assert listing.source == "vietnamworks"


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


def test_normalize_salary_zero_zero_is_negotiable():
    """should resolve salary_min=0, salary_max=0 → period='negotiable', confidence=0.5."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_min": 0, "salary_max": 0}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.period == "negotiable"
    assert listing.salary.confidence == 0.5


def test_normalize_salary_min_only():
    """should resolve salary_min>0, salary_max=0 → min=min_v, max=None, confidence=0.7."""
    raw = {
        "id": "1",
        "title": "Dev",
        "company": "Co",
        "salary_min": 30000000,
        "salary_max": 0,
    }
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.min == 30000000
    assert listing.salary.max is None
    assert listing.salary.confidence == 0.7


def test_normalize_salary_both_present():
    """should resolve salary_min>0, salary_max>0 → confidence=0.8."""
    raw = {
        "id": "1",
        "title": "Dev",
        "company": "Co",
        "salary_min": 20000000,
        "salary_max": 40000000,
    }
    listing = normalize_listing("vietnamworks", raw)
    assert listing.salary.min == 20000000
    assert listing.salary.max == 40000000
    assert listing.salary.confidence == 0.8


def test_normalize_salary_hidden():
    """should resolve no salary_raw → period='hidden', confidence=0.0."""
    raw = {"id": "1", "title": "Dev", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.salary.period == "hidden"
    assert listing.salary.confidence == 0.0


def test_normalize_salary_negotiable_text():
    """should resolve 'thương lượng' → period='negotiable', confidence=0.5."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "salary_raw": "Thương lượng"}
    listing = normalize_listing("topcv", raw)
    assert listing.salary.period == "negotiable"
    assert listing.salary.confidence == 0.5


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: posted_at parsing
# ---------------------------------------------------------------------------


def test_normalize_posted_at_hom_nay():
    """should resolve 'hôm nay' → today's date."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "hôm nay"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today()


def test_normalize_posted_at_hom_qua():
    """should resolve 'hôm qua' → yesterday's date."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "hôm qua"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today() - datetime.timedelta(days=1)


def test_normalize_posted_at_n_ngay_truoc():
    """should resolve '3 ngày trước' → 3 days ago."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "3 ngày trước"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date.today() - datetime.timedelta(days=3)


def test_normalize_posted_at_dd_mm_yyyy():
    """should resolve '05/08/2026' → date(2026, 8, 5)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": "05/08/2026"}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at == datetime.date(2026, 8, 5)


def test_normalize_posted_at_none():
    """should handle posted_at=None → None (not crash)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "posted_at": None}
    listing = normalize_listing("topcv", raw)
    assert listing.posted_at is None


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: experience_years (NEW _normalize_experience)
# ---------------------------------------------------------------------------


def test_normalize_experience_years_text_3_plus():
    """should resolve '3+ years' → 3."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": "3+ years"}
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years == 3


def test_normalize_experience_years_text_khong_yeu_cau():
    """should resolve 'Không yêu cầu' → 0 or None."""
    raw = {
        "id": "1",
        "title": "Dev",
        "company": "Co",
        "experience_years": "Không yêu cầu",
    }
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years in (0, None)


def test_normalize_experience_years_int_passthrough():
    """should resolve int 5 → 5 (passthrough)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": 5}
    listing = normalize_listing("vietnamworks", raw)
    assert listing.experience_years == 5


def test_normalize_experience_years_none():
    """should handle experience_years=None → None."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "experience_years": None}
    listing = normalize_listing("itviec", raw)
    assert listing.experience_years is None


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking
# ---------------------------------------------------------------------------


def test_normalize_skills_none_returns_empty_list():
    """should handle raw.get('skills')=None → skills=[] (not crash)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "skills": None}
    listing = normalize_listing("itviec", raw)
    assert listing.skills == []


def test_normalize_source_url_none():
    """should handle source_url=None → source_urls=[] (no empty string)."""
    raw = {"id": "1", "title": "Dev", "company": "Co", "source_url": None}
    listing = normalize_listing("itviec", raw)
    assert listing.source_urls == []


def test_normalize_id_none_derives_stable_id():
    """should handle id=None → derive stable source_record_id via SHA-256."""
    raw_a = {
        "title": "Dev",
        "company": "Co",
        "location": "HN",
        "posted_at": "2026-08-05",
    }
    raw_b = {
        "title": "Dev",
        "company": "Co",
        "location": "HN",
        "posted_at": "2026-08-05",
    }
    listing_a = normalize_listing("itviec", raw_a)
    listing_b = normalize_listing("itviec", raw_b)
    assert listing_a.id == listing_b.id  # deterministic
    assert listing_a.id.startswith("itviec:")  # prefixed with source


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases
# ---------------------------------------------------------------------------


def test_normalize_empty_title_confidence_03():
    """should compute confidence_score=0.3 when title is empty."""
    raw = {"id": "1", "title": "", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == pytest.approx(0.3)


def test_normalize_empty_company_confidence_03():
    """should compute confidence_score=0.3 when company is empty."""
    raw = {"id": "1", "title": "Dev", "company": ""}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == pytest.approx(0.3)


def test_normalize_both_present_confidence_06():
    """should compute confidence_score=0.6 when both title and company are non-empty."""
    raw = {"id": "1", "title": "Dev", "company": "Co"}
    listing = normalize_listing("itviec", raw)
    assert listing.confidence_score == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic
# ---------------------------------------------------------------------------


def test_normalize_salary_confidence_exact_values():
    """should compute salary.confidence as exactly 0.5 for negotiable, 0.7 for min-only, 0.8 for both."""
    # negotiable
    listing_n = normalize_listing(
        "vietnamworks",
        {"id": "1", "title": "D", "company": "C", "salary_raw": "Thương lượng"},
    )
    assert listing_n.salary.confidence == pytest.approx(0.5)
    # min only
    listing_m = normalize_listing(
        "vietnamworks",
        {"id": "2", "title": "D", "company": "C", "salary_min": 10, "salary_max": 0},
    )
    assert listing_m.salary.confidence == pytest.approx(0.7)
    # both
    listing_b = normalize_listing(
        "vietnamworks",
        {"id": "3", "title": "D", "company": "C", "salary_min": 10, "salary_max": 20},
    )
    assert listing_b.salary.confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Pattern 5 — Error message
# ---------------------------------------------------------------------------


def test_normalize_does_not_raise_on_any_input():
    """should NOT raise on any raw input — normalize_listing is total."""
    # Empty dict
    listing = normalize_listing("itviec", {})
    assert isinstance(listing, VnJobAggregatedListing)
    # All None values
    listing = normalize_listing(
        "itviec", {"title": None, "company": None, "location": None}
    )
    assert isinstance(listing, VnJobAggregatedListing)


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror: PrivateAttrs excluded
# ---------------------------------------------------------------------------


def test_normalize_private_attrs_not_in_dump():
    """should NOT return _source_record_ids or _source_url_map in serialized output."""
    raw = {
        "id": "1",
        "title": "Dev",
        "company": "Co",
        "source_url": "https://example.com",
    }
    listing = normalize_listing("itviec", raw)
    dumped = listing.model_dump()
    assert "_source_record_ids" not in dumped
    assert "_source_url_map" not in dumped


# ===========================================================================
# Mutation-killing boundary tests
# ===========================================================================


def test_parse_post_date_relative_phrases():
    """Vietnamese relative posted_at phrases parse to deterministic offsets."""
    today = datetime.date.today()
    assert _parse_post_date("hôm nay") == today
    assert _parse_post_date("hôm qua") == today - datetime.timedelta(days=1)
    assert _parse_post_date("5 ngày trước") == today - datetime.timedelta(days=5)


def test_parse_post_date_iso_and_dmy():
    """Absolute date formats parse correctly."""
    assert _parse_post_date("2026-08-05") == datetime.date(2026, 8, 5)
    assert _parse_post_date("05/08/2026") == datetime.date(2026, 8, 5)
    assert _parse_post_date("05-08-2026") == datetime.date(2026, 8, 5)


def test_parse_post_date_unparseable_returns_none():
    """Invalid date text returns None, not today."""
    assert _parse_post_date("unknown posted date") is None


def test_normalize_salary_period_mapping():
    """Period identifiers map to canonical schema values."""
    assert _normalize_salary_period(1) == "hour"
    assert _normalize_salary_period(2) == "month"
    assert _normalize_salary_period(3) == "year"
    assert _normalize_salary_period("year") == "year"
    assert _normalize_salary_period("negotiable") == "negotiable"


def test_normalize_salary_period_unknown_defaults_month():
    """Unknown period id defaults to month."""
    assert _normalize_salary_period("quarter") == "month"
    assert _normalize_salary_period(None) == "month"


def test_parse_salary_both_values_present():
    """Both min and max present gives min/max and highest confidence."""
    salary = _parse_salary(
        {
            "salary_raw": "10-20 triệu",
            "salary_min": 10_000_000,
            "salary_max": 20_000_000,
            "salary_period_id": 2,
        }
    )
    assert salary.min == 10_000_000
    assert salary.max == 20_000_000
    assert salary.confidence == 0.8
    assert salary.period == "month"


def test_parse_salary_min_only():
    """Only min present gives min and 0.7 confidence."""
    salary = _parse_salary(
        {
            "salary_raw": "Từ 15 triệu",
            "salary_min": 15_000_000,
            "salary_max": 0,
        }
    )
    assert salary.min == 15_000_000
    assert salary.max is None
    assert salary.confidence == 0.7


def test_parse_salary_zero_zero():
    """0/0 with raw text becomes negotiable."""
    salary = _parse_salary(
        {
            "salary_raw": "thương lượng",
            "salary_min": 0,
            "salary_max": 0,
        }
    )
    assert salary.min == 0
    assert salary.max == 0
    assert salary.period == "negotiable"
    assert salary.confidence == 0.5


def test_parse_salary_hidden_no_data():
    """No salary text and no numeric fields is hidden."""
    salary = _parse_salary({})
    assert salary.min == 0
    assert salary.max == 0
    assert salary.period == "hidden"
    assert salary.confidence == 0.0


def test_parse_salary_numeric_no_text():
    """Numeric fields without raw text gives period from mapping and 0.8 confidence."""
    salary = _parse_salary({"salary_min": 30_000_000, "salary_max": 50_000_000})
    assert salary.min == 30_000_000
    assert salary.max == 50_000_000
    assert salary.confidence == 0.8
    assert salary.period == "month"


def test_normalize_location_resolves_city_code():
    """Known city names resolve to canonical code."""
    assert _normalize_location("Hà Nội") == "HN"
    assert _normalize_location("Hồ Chí Minh") == "SG"


def test_normalize_location_unknown_returns_raw():
    """Unknown locations fall back to the raw text."""
    assert _normalize_location("Some Village") == "Some Village"


def test_normalize_location_empty_returns_none():
    """Empty/None location returns None."""
    assert _normalize_location(None) is None
    assert _normalize_location("   ") is None


def test_normalize_experience_passthrough():
    """Integer and float experience pass through."""
    assert _normalize_experience(5) == 5
    assert _normalize_experience(2.5) == 2


def test_normalize_experience_text():
    """Text with numbers parses correctly."""
    assert _normalize_experience("3+ years") == 3
    assert _normalize_experience("Không yêu cầu") == 0


def test_normalize_experience_unparseable_returns_none():
    """Unparseable text and empty values return None."""
    assert _normalize_experience("  ") is None
    assert _normalize_experience(None) is None


def test_normalize_text_strips_and_empty():
    """Text strips whitespace and converts emptiness to None."""
    assert _normalize_text("  hello  ") == "hello"
    assert _normalize_text("   ") is None
    assert _normalize_text(None) is None
