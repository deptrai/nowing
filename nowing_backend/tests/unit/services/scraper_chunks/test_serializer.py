"""Unit tests for ``app.services.scraper_chunks.serializer``."""

from __future__ import annotations

from copy import deepcopy

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def sample_bds_listing() -> dict[str, object]:
    return {
        "canonical_id": "bds:hn:bd-1",
        "title": "Bán nhà Ba Đình",
        "price": "19.8 Tỷ",
        "area": "75 m²",
        "district": "Ba Đình",
        "ward": "Phúc Xá",
        "city": "Hà Nội",
        "detail_urls": {"batdongsan": "https://bd/1"},
        "sources": ["batdongsan"],
        "source_count": 1,
        "confidence_score": 0.9,
    }


@pytest.fixture
def sample_job_entity() -> dict[str, object]:
    return {
        "id": "job:1",
        "title": "Senior Data Engineer",
        "company": "ACB",
        "location": "Hà Nội",
        "employment_type": "full_time",
        "salary": {"min": 30000000, "currency": "VND", "period": "month"},
        "posted_at": "2026-08-11",
        "job_description": "Build data pipelines.",
        "job_requirement": "Python, SQL.",
        "source": "multiple",
        "confidence_score": 0.85,
    }


def test_to_chunks_returns_chunks_with_metadata(sample_bds_listing):
    """to_chunks returns Chunk objects with the canonical scraper metadata."""
    from app.services.scraper_chunks.serializer import to_chunks

    chunks = to_chunks(
        domain="bds",
        data=sample_bds_listing,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="listing",
    )

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.metadata.source == "nowing_scraper"
        assert chunk.metadata.domain == "bds"
        assert chunk.metadata.fetchedAt is not None
        assert chunk.metadata.contentType == "text/markdown"
        assert chunk.metadata.category == "listing"
        assert chunk.metadata.title == sample_bds_listing["title"]
        assert chunk.metadata.url == sample_bds_listing["detail_urls"]["batdongsan"]
        assert chunk.metadata.sourceId
        assert chunk.content


def test_to_chunks_includes_canonical_entity_id(sample_bds_listing):
    """If the raw data carries a canonical id, it is exposed as canonicalEntityId."""
    from app.services.scraper_chunks.serializer import to_chunks

    chunks = to_chunks(
        domain="bds",
        data=sample_bds_listing,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="listing",
    )

    assert all(
        chunk.metadata.canonicalEntityId == sample_bds_listing["canonical_id"]
        for chunk in chunks
    )


def test_to_chunks_source_id_is_stable_and_deterministic(sample_bds_listing):
    """sourceId is deterministic: identical input yields identical id."""
    from app.services.scraper_chunks.serializer import to_chunks

    kwargs = {
        "domain": "bds",
        "data": sample_bds_listing,
        "fetched_at": "2026-08-11T00:00:00+00:00",
        "content_type": "text/markdown",
        "category": "listing",
    }
    first = to_chunks(**kwargs)
    second = to_chunks(**kwargs)

    assert first[0].metadata.sourceId == second[0].metadata.sourceId


def test_to_chunks_source_id_is_stable_across_volatile_fields(
    sample_bds_listing,
):
    """sourceId does not change when volatile/display-only fields vary."""
    from app.services.scraper_chunks.serializer import to_chunks

    base = deepcopy(sample_bds_listing)
    variant = deepcopy(sample_bds_listing)
    variant["thumbnail_url"] = "https://different.example/img.jpg"
    variant["contact"] = "0909999999"

    base_chunks = to_chunks(
        domain="bds",
        data=base,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="listing",
    )
    variant_chunks = to_chunks(
        domain="bds",
        data=variant,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="listing",
    )

    assert base_chunks[0].metadata.sourceId == variant_chunks[0].metadata.sourceId


def test_to_chunks_splits_oversized_content():
    """Content larger than 8,000 tokens is split with chunkIndex/chunkTotal and stable suffixes."""
    from app.services.scraper_chunks.serializer import to_chunks

    oversized = "word " * 9000
    data = {
        "title": "Big listing",
        "description": oversized,
        "canonical_id": "bds:big:1",
        "city": "Hà Nội",
        "district": "Ba Đình",
        "price": "10 tỷ",
        "sources": ["batdongsan"],
    }

    chunks = to_chunks(
        domain="bds",
        data=data,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="listing",
    )

    assert len(chunks) > 1
    base_source_id = chunks[0].metadata.sourceId.rsplit(":", 1)[0]
    for index, chunk in enumerate(chunks):
        assert chunk.metadata.chunkIndex == index
        assert chunk.metadata.chunkTotal == len(chunks)
        assert len(chunk.content.split()) <= 8000
        assert chunk.metadata.sourceId.startswith(base_source_id)


def test_to_chunks_raises_validation_error_for_missing_bds_fields():
    """BĐS listings missing required fields raise ChunkValidationError."""
    from app.services.scraper_chunks.schemas import ChunkValidationError
    from app.services.scraper_chunks.serializer import to_chunks

    bad = {
        "city": "Hà Nội",
        "district": "Ba Đình",
        "price": "10 tỷ",
        # missing title
    }

    with pytest.raises(ChunkValidationError) as exc_info:
        to_chunks(
            domain="bds",
            data=bad,
            fetched_at="2026-08-11T00:00:00+00:00",
            content_type="text/markdown",
            category="listing",
        )

    assert "title" in str(exc_info.value)


def test_to_chunks_raises_validation_error_for_missing_job_fields():
    """Job entities missing required fields raise ChunkValidationError."""
    from app.services.scraper_chunks.schemas import ChunkValidationError
    from app.services.scraper_chunks.serializer import to_chunks

    bad = {
        "company": "ACB",
        "location": "Hà Nội",
        # missing title
    }

    with pytest.raises(ChunkValidationError) as exc_info:
        to_chunks(
            domain="vn_jobs",
            data=bad,
            fetched_at="2026-08-11T00:00:00+00:00",
            content_type="text/markdown",
            category="job_posting",
        )

    assert "title" in str(exc_info.value)


def test_to_chunks_redacts_pii_before_chunking(sample_job_entity):
    """Sensitive contact data is masked before it becomes Chunk content."""
    from app.services.scraper_chunks.serializer import to_chunks

    data = dict(sample_job_entity)
    data["job_description"] = "Liên hệ 0901234567 hoặc hr@example.com để apply."

    chunks = to_chunks(
        domain="vn_jobs",
        data=data,
        fetched_at="2026-08-11T00:00:00+00:00",
        content_type="text/markdown",
        category="job_posting",
    )

    full = " ".join(chunk.content for chunk in chunks)
    assert "0901234567" not in full
    assert "hr@example.com" not in full
    assert "<PHONE>" in full
    assert "<EMAIL>" in full
