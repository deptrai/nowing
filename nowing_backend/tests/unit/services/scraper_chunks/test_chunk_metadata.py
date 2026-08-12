"""Unit tests for scraper_chunks ChunkMetadata salary fields (Story 12-4d)."""

from __future__ import annotations

import pytest

from app.services.scraper_chunks.schemas import ChunkMetadata
from app.services.scraper_chunks.serializer import to_chunks

pytestmark = pytest.mark.unit



def test_chunk_metadata_has_salary_field():
    """ChunkMetadata has salary field."""
    metadata = ChunkMetadata(
        source="nowing_scraper",
        sourceId="test:123",
        domain="vn_jobs",
        fetchedAt="2026-08-11T00:00:00+00:00",
        contentType="job",
        salary={"min": 30000000, "max": 50000000, "currency": "VND"},
    )

    assert hasattr(metadata, "salary")
    assert metadata.salary is not None
    assert metadata.salary["min"] == 30000000
    assert metadata.salary["max"] == 50000000



def test_chunk_metadata_has_salary_consistency_score_field():
    """ChunkMetadata has salary_consistency_score field."""
    metadata = ChunkMetadata(
        source="nowing_scraper",
        sourceId="test:123",
        domain="vn_jobs",
        fetchedAt="2026-08-11T00:00:00+00:00",
        contentType="job",
        salary_consistency_score=0.85,
    )

    assert hasattr(metadata, "salary_consistency_score")
    assert metadata.salary_consistency_score == 0.85



def test_to_chunks_populates_salary_from_vn_job_aggregated_listing():
    """to_chunks populates salary field from VnJobAggregatedListing."""
    data = {
        "id": "job:1",
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "salary": {"min": 30000000, "max": 50000000, "currency": "VND", "period": "month"},
        "posted_at": "2026-08-11",
        "job_description": "Build data pipelines.",
    }

    chunks = to_chunks(
        domain="vn_jobs",
        data=data,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="job_posting",
    )

    assert len(chunks) > 0
    assert hasattr(chunks[0].metadata, "salary")
    assert chunks[0].metadata.salary is not None
    assert chunks[0].metadata.salary["min"] == 30000000
    assert chunks[0].metadata.salary["max"] == 50000000



def test_to_chunks_populates_salary_consistency_score_from_vn_job_aggregated_listing():
    """to_chunks populates salary_consistency_score from VnJobAggregatedListing."""
    data = {
        "id": "job:1",
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "salary": {"min": 30000000, "max": 50000000, "currency": "VND"},
        "salary_consistency_score": 0.9,
        "posted_at": "2026-08-11",
        "job_description": "Build data pipelines.",
    }

    chunks = to_chunks(
        domain="vn_jobs",
        data=data,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="job_posting",
    )

    assert len(chunks) > 0
    assert hasattr(chunks[0].metadata, "salary_consistency_score")
    assert chunks[0].metadata.salary_consistency_score == 0.9



def test_to_chunks_salary_none_negotiable_results_in_metadata_salary_none():
    """salary None (negotiable/hidden) results in salary=None metadata."""
    data = {
        "id": "job:1",
        "title": "Data Engineer",
        "company": "FPT",
        "location": "Hà Nội",
        "salary": None,
        "posted_at": "2026-08-11",
        "job_description": "Build data pipelines.",
    }

    chunks = to_chunks(
        domain="vn_jobs",
        data=data,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="job_posting",
    )

    assert len(chunks) > 0
    assert hasattr(chunks[0].metadata, "salary")
    assert chunks[0].metadata.salary is None
