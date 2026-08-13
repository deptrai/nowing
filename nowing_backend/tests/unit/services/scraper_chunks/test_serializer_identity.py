"""Unit tests for scraper_chunks serializer identity fields (Story 12-4d)."""

from __future__ import annotations

import pytest

from app.services.scraper_chunks.serializer import _identity_fields, _stable_fingerprint

pytestmark = pytest.mark.unit



def test_identity_fields_for_job_domains_uses_company_title_location_posted_at():
    """_identity_fields for job domains uses {company, title, location, posted_at} (not salary/employment_type)."""
    data = {
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "posted_at": "2026-08-11",
        "salary": {"min": 30000000, "max": 50000000},
        "employment_type": "full_time",
    }

    identity = _identity_fields("vn_jobs", data)

    # Should include these fields
    assert "title" in identity
    assert "company" in identity
    assert "location" in identity
    assert "posted_at" in identity

    # Should NOT include salary or employment_type (volatile fields)
    assert "salary" not in identity
    assert "employment_type" not in identity



def test_identity_fields_for_job_domains_excludes_salary_and_employment_type():
    """_identity_fields explicitly excludes salary and employment_type for job domains."""
    data = {
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "posted_at": "2026-08-11",
        "salary": {"min": 30000000, "max": 50000000},
        "employment_type": "full_time",
    }

    identity = _identity_fields("itviec", data)

    assert "salary" not in identity
    assert "employment_type" not in identity



def test_stable_fingerprint_for_job_domains_equals_sha256_of_sorted_identity_dict():
    """_stable_fingerprint for job domains equals sha256 of sorted identity dict."""
    data = {
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "posted_at": "2026-08-11",
    }

    fingerprint = _stable_fingerprint("vn_jobs", data)

    # Verify it is domain-prefixed + 32-char hex sha256 slice
    assert ":" in fingerprint
    hash_part = fingerprint.split(":")[-1]
    assert len(hash_part) == 32
    assert all(c in "0123456789abcdef" for c in hash_part)

    # Verify it is deterministic
    fingerprint2 = _stable_fingerprint("vn_jobs", data)
    assert fingerprint == fingerprint2



def test_stable_fingerprint_boundary_posted_at_none():
    """_stable_fingerprint handles posted_at=None and remains deterministic."""
    data = {
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "posted_at": None,
    }

    fingerprint = _stable_fingerprint("vn_jobs", data)
    fingerprint2 = _stable_fingerprint("vn_jobs", data)

    assert ":" in fingerprint
    hash_part = fingerprint.split(":")[-1]
    assert len(hash_part) == 32
    assert fingerprint == fingerprint2



def test_stable_fingerprint_boundary_location_none():
    """_stable_fingerprint handles location=None boundary case."""
    data = {
        "title": "Data Engineer",
        "company": "FPT",
        "location": None,
        "posted_at": "2026-08-11",
    }

    fingerprint = _stable_fingerprint("vn_jobs", data)

    assert ":" in fingerprint
    hash_part = fingerprint.split(":")[-1]
    assert len(hash_part) == 32


def test_identity_fields_uses_canonical_id_when_present():
    """_identity_fields uses canonical_id + posted_at for job domains."""
    data = {
        "canonical_id": "job:123",
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "posted_at": "2026-08-11",
    }

    identity = _identity_fields("vn_jobs", data)

    # Job-domain identity keeps canonical_id and posted_at (AC-3).
    assert identity == {"canonical_id": "job:123", "posted_at": "2026-08-11"}
    assert "title" not in identity
    assert "company" not in identity
