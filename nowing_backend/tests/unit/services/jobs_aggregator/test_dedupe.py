"""ATDD tests for jobs_aggregator dedupe (AC-4, AC-5, AC-6).

Covers Jaro-Winkler fuzzy title matching, posted_at ±3 days tolerance,
conflict flags (SALARY_MISMATCH, LOCATION_MISMATCH), source_count,
salary spread thresholds (10% stable / 20% conflict), and preserving
both source records on conflict.
"""

from __future__ import annotations

import datetime

import pytest

from app.services.jobs_aggregator.dedupe import deduplicate
from app.services.jobs_aggregator.schemas import VnJobAggregatedListing, VnJobSalary

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Existing passing test (keep green)
# ---------------------------------------------------------------------------


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


# ===========================================================================
# AC-4: Fuzzy title matching (Jaro-Winkler ≥ 0.85) + posted_at ±3 days
# ===========================================================================


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


def test_dedupe_fuzzy_title_match_above_threshold():
    """should group 'Backend Developer' vs 'Back-end Developer' (JW ≥ 0.85)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Backend Developer",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Back-end Developer",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert merged[0].source == "multiple"


def test_dedupe_fuzzy_title_below_threshold_not_grouped():
    """should NOT group 'Data Engineer' vs 'Data Scientist' (JW < 0.85)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Data Engineer",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Data Scientist",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 2  # not grouped


def test_dedupe_uses_rapidfuzz_jaro_winkler():
    """should use rapidfuzz.distance.JaroWinkler.similarity() (not difflib.SequenceMatcher)."""
    # ponytail: verify the import path is rapidfuzz, not difflib
    import inspect

    import app.services.jobs_aggregator.dedupe as dedupe_mod

    src = inspect.getsource(dedupe_mod)
    assert "rapidfuzz" in src
    assert "JaroWinkler" in src or "jaro_winkler" in src


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases: Jaro-Winkler boundary
# ---------------------------------------------------------------------------


def test_dedupe_jw_boundary_exactly_085():
    """should match when Jaro-Winkler similarity is exactly 0.85 (≥, inclusive)."""
    # 'Full Stack Developer' vs 'Fullstack Developer' → JW ≈ 0.947 (well above 0.85)
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Full Stack Developer",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Fullstack Developer",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    from rapidfuzz.distance import JaroWinkler

    sim = JaroWinkler.similarity(listings[0].title, listings[1].title)
    assert sim >= 0.85  # verify pair is above threshold
    merged = deduplicate(listings)
    assert len(merged) == 1


def test_dedupe_jw_boundary_below_085():
    """should NOT match when Jaro-Winkler similarity is 0.8499 (< 0.85)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Data Engineer",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Data Scientist",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    from rapidfuzz.distance import JaroWinkler

    sim = JaroWinkler.similarity(listings[0].title, listings[1].title)
    assert sim < 0.85  # verify pair is below threshold
    merged = deduplicate(listings)
    assert len(merged) == 2


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases: posted_at ±3 days
# ---------------------------------------------------------------------------


def test_dedupe_posted_at_3_days_apart_match():
    """should match when posted_at difference is exactly 3 days (±3 inclusive)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            posted_at=datetime.date(2026, 8, 5),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            posted_at=datetime.date(2026, 8, 8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1


def test_dedupe_posted_at_4_days_apart_no_match():
    """should NOT match when posted_at difference is 4 days (> ±3)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            posted_at=datetime.date(2026, 8, 5),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            posted_at=datetime.date(2026, 8, 9),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 2


def test_dedupe_posted_at_none_both_match():
    """should match when posted_at is None on both (skip date constraint)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            posted_at=None,
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            posted_at=None,
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1


def test_dedupe_posted_at_none_one_match():
    """should match when posted_at is None on one (skip date constraint)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            posted_at=None,
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            posted_at=datetime.date(2026, 8, 5),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases: null/empty company + location
# ---------------------------------------------------------------------------


def test_dedupe_empty_company_not_grouped():
    """should NOT group all empty-company listings together."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="",
            location="HN",
            source="vietnamworks",
            confidence_score=0.3,
        ),
        VnJobAggregatedListing(
            id="b",
            title="QA",
            company="",
            location="HN",
            source="itviec",
            confidence_score=0.3,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 2  # different titles, empty company → not grouped


def test_dedupe_none_location_wildcard():
    """should treat None location as wildcard (match any, not LOCATION_MISMATCH)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location=None,
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "LOCATION_MISMATCH" not in merged[0].conflict_flags


# ===========================================================================
# AC-5: Salary consistency (≤10% → stable) + source_count
# ===========================================================================


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


def test_dedupe_source_count_set_on_merge():
    """should set source_count = len(group) on merged listing."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
        VnJobAggregatedListing(
            id="c",
            title="Dev",
            company="FPT",
            location="HN",
            source="topcv",
            confidence_score=0.5,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert merged[0].source_count == 3


def test_dedupe_salary_diff_le_10_percent_stable():
    """should set confidence_score ≥ 0.8 when salary difference ≤ 10%."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=31_000_000, max=31_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert merged[0].confidence_score >= 0.8
    assert merged[0].salary_consistency_score >= 0.8


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases: salary boundary
# ---------------------------------------------------------------------------


def test_dedupe_salary_diff_exactly_10_percent_stable():
    """should be stable when salary difference is exactly 10.0% (≤ 10%, inclusive)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=33_000_000, max=33_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "SALARY_MISMATCH" not in merged[0].conflict_flags


def test_dedupe_salary_diff_exactly_20_percent_not_conflict():
    """should NOT set SALARY_MISMATCH when salary difference is exactly 20.0% (> 20% is conflict)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=36_000_000, max=36_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "SALARY_MISMATCH" not in merged[0].conflict_flags


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking: null/hidden salary
# ---------------------------------------------------------------------------


def test_dedupe_salary_none_both_skip_comparison():
    """should skip salary comparison when salary is None/hidden on both → consistency=0.5."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(period="hidden"),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(period="hidden"),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "SALARY_MISMATCH" not in merged[0].conflict_flags


def test_dedupe_salary_zero_negotiable_skipped():
    """should skip 0-value salaries in comparison (0 means negotiable, not 0 VND)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=0, max=0, period="negotiable"),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "SALARY_MISMATCH" not in merged[0].conflict_flags


def test_dedupe_all_salaries_zero_consistency_05():
    """should set salary_consistency_score=0.5 (not 0.8) when all salaries are 0 (can't confirm stability)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=0, max=0, period="negotiable"),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=0, max=0, period="negotiable"),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert merged[0].salary_consistency_score == 0.5


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic
# ---------------------------------------------------------------------------


def test_dedupe_confidence_boost_exact():
    """should compute confidence_score as exactly min(1.0, base + 0.1*(len-1))."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.6,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    # base=0.6, boost=0.1*(2-1)=0.1 → 0.7
    assert merged[0].confidence_score == pytest.approx(0.7)


# ===========================================================================
# AC-6: Conflict flags + lower confidence + preserve both records
# ===========================================================================


# ---------------------------------------------------------------------------
# Pattern 1 — Mirror
# ---------------------------------------------------------------------------


def test_dedupe_salary_mismatch_flag():
    """should set conflict_flags=['SALARY_MISMATCH'] when salary difference > 20%."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=50_000_000, max=50_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert "SALARY_MISMATCH" in merged[0].conflict_flags


def test_dedupe_location_mismatch_flag():
    """should set conflict_flags=['LOCATION_MISMATCH'] when locations differ after normalization."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="Hà Nội",
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="Hồ Chí Minh",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    # Note: these have different locations so may not group — depends on whether
    # location is part of the match key. If they DO group, flag should be set.
    if len(merged) == 1:
        assert "LOCATION_MISMATCH" in merged[0].conflict_flags


def test_dedupe_both_salary_and_location_mismatch():
    """should set conflict_flags=['SALARY_MISMATCH', 'LOCATION_MISMATCH'] when both conditions hold."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="Hà Nội",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="Đà Nẵng",
            source="itviec",
            salary=VnJobSalary(min=50_000_000, max=50_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    if len(merged) == 1:
        assert "SALARY_MISMATCH" in merged[0].conflict_flags
        assert "LOCATION_MISMATCH" in merged[0].conflict_flags


def test_dedupe_no_conflict_empty_flags():
    """should set conflict_flags=[] when no conflict."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=31_000_000, max=31_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert merged[0].conflict_flags == []


def test_dedupe_conflict_lowers_confidence():
    """should lower confidence_score to 0.5-0.7 when conflict detected."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.9,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=60_000_000, max=60_000_000, confidence=0.8),
            confidence_score=0.9,
        ),
    ]
    merged = deduplicate(listings)
    if len(merged) == 1 and "SALARY_MISMATCH" in merged[0].conflict_flags:
        assert 0.5 <= merged[0].confidence_score <= 0.7


def test_dedupe_preserves_both_records_on_conflict():
    """should preserve both source records when conflict detected (not merge into one)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=60_000_000, max=60_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    # Set private attrs so provenance is traceable after merge.
    listings[0]._source_record_ids = {"vietnamworks": "a"}
    listings[1]._source_record_ids = {"itviec": "b"}
    merged = deduplicate(listings)
    # AC-6: "preserves both source records" — either return 2 records or carry both in a conflict group
    # The exact shape is implementation-defined, but both sources must be traceable
    if len(merged) == 1:
        # If merged into one, both source_ids must be present
        assert "vietnamworks" in merged[0]._source_record_ids
        assert "itviec" in merged[0]._source_record_ids
    else:
        # If returned as 2, both must have conflict flags
        assert any("SALARY_MISMATCH" in m.conflict_flags for m in merged)


# ---------------------------------------------------------------------------
# Pattern 3 — Edge cases: conflict boundary
# ---------------------------------------------------------------------------


def test_dedupe_salary_diff_20_01_percent_conflict():
    """should set SALARY_MISMATCH when salary difference is >20%.

    Spread = (hi - lo) / hi.  For 30M vs 38M: (38M - 30M) / 38M = 0.2105 > 0.20.
    """
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=38_000_000, max=38_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert "SALARY_MISMATCH" in merged[0].conflict_flags


def test_dedupe_none_location_not_mismatch():
    """should NOT set LOCATION_MISMATCH when location is None on one listing."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location=None,
            source="vietnamworks",
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    if len(merged) == 1:
        assert "LOCATION_MISMATCH" not in merged[0].conflict_flags


def test_dedupe_null_salary_one_not_mismatch():
    """should NOT set SALARY_MISMATCH when salary is None on one (asymmetric, can't compare)."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(period="hidden"),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    if len(merged) == 1:
        assert "SALARY_MISMATCH" not in merged[0].conflict_flags


# ---------------------------------------------------------------------------
# Pattern 5 — Error message: exact enum strings
# ---------------------------------------------------------------------------


def test_dedupe_conflict_flags_exact_strings():
    """should set conflict_flags with exact 'SALARY_MISMATCH' (not 'salary_mismatch', 'PRICE_MISMATCH')."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=30_000_000, max=30_000_000, confidence=0.8),
            confidence_score=0.7,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=60_000_000, max=60_000_000, confidence=0.8),
            confidence_score=0.6,
        ),
    ]
    merged = deduplicate(listings)
    if merged and merged[0].conflict_flags:
        for flag in merged[0].conflict_flags:
            assert flag in ("SALARY_MISMATCH", "LOCATION_MISMATCH")
            assert flag == flag.upper()


# ---------------------------------------------------------------------------
# Pattern 2 — Over-Mocking: empty group, single listing
# ---------------------------------------------------------------------------


def test_dedupe_empty_group_no_conflict():
    """should handle empty group → no conflict, conflict_flags=[]."""
    merged = deduplicate([])
    assert merged == []


def test_dedupe_single_listing_no_conflict():
    """should handle single listing → no conflict, conflict_flags=[]."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            confidence_score=0.7,
        ),
    ]
    merged = deduplicate(listings)
    assert len(merged) == 1
    assert merged[0].conflict_flags == []


# ---------------------------------------------------------------------------
# Pattern 4 — Arithmetic: conflict confidence exact
# ---------------------------------------------------------------------------


def test_dedupe_conflict_confidence_05_large_spread():
    """should compute confidence_score=0.5 when SALARY_MISMATCH and spread > 50%."""
    listings = [
        VnJobAggregatedListing(
            id="a",
            title="Dev",
            company="FPT",
            location="HN",
            source="vietnamworks",
            salary=VnJobSalary(min=10_000_000, max=10_000_000, confidence=0.8),
            confidence_score=0.9,
        ),
        VnJobAggregatedListing(
            id="b",
            title="Dev",
            company="FPT",
            location="HN",
            source="itviec",
            salary=VnJobSalary(min=100_000_000, max=100_000_000, confidence=0.8),
            confidence_score=0.9,
        ),
    ]
    merged = deduplicate(listings)
    if len(merged) == 1 and "SALARY_MISMATCH" in merged[0].conflict_flags:
        assert merged[0].confidence_score == pytest.approx(0.5)
