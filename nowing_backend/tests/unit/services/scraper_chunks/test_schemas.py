"""Unit tests for ``app.services.scraper_chunks.schemas``."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _valid_metadata_kwargs() -> dict[str, object]:
    return {
        "source": "nowing_scraper",
        "sourceId": "bds:sha256:abc123",
        "domain": "bds",
        "fetchedAt": "2026-08-11T00:00:00+00:00",
        "contentType": "listing",
    }


def test_chunk_metadata_enforces_required_fields():
    """ChunkMetadata rejects a record missing a required metadata field."""
    from pydantic import ValidationError

    from app.services.scraper_chunks.schemas import ChunkMetadata

    with pytest.raises(ValidationError):
        ChunkMetadata(
            sourceId="bds:1",
            domain="bds",
            fetchedAt="2026-08-11T00:00:00+00:00",
            contentType="listing",
        )


def test_chunk_accepts_valid_source_and_optional_fields():
    """Chunk accepts the canonical ``nowing_scraper`` source and all optional metadata."""
    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    metadata = ChunkMetadata(
        **_valid_metadata_kwargs(),
        confidence_score=0.9,
        source_count=2,
        conflict_flags=[],
        chunkIndex=0,
        chunkTotal=1,
        canonicalEntityId="canon-1",
    )
    chunk = Chunk(content="Bán nhà Ba Đình 75 m²", metadata=metadata)

    assert chunk.metadata.source == "nowing_scraper"
    assert chunk.metadata.confidence_score == 0.9
    assert chunk.metadata.chunkIndex == 0
    assert chunk.metadata.chunkTotal == 1
    assert chunk.metadata.canonicalEntityId == "canon-1"


def test_chunk_rejects_invalid_source():
    """The ``source`` metadata field is limited to the chainlens-owned enum."""
    from pydantic import ValidationError

    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    with pytest.raises(ValidationError):
        Chunk(
            content="x",
            metadata=ChunkMetadata(
                source="invalid_source",
                sourceId="bds:1",
                domain="bds",
                fetchedAt="2026-08-11T00:00:00+00:00",
                contentType="listing",
            ),
        )


def test_chunk_enforces_content_present():
    """A Chunk requires non-empty content."""
    from pydantic import ValidationError

    from app.services.scraper_chunks.schemas import Chunk, ChunkMetadata

    with pytest.raises(ValidationError):
        Chunk(content="", metadata=ChunkMetadata(**_valid_metadata_kwargs()))


def test_chunk_validation_error_carries_field_details():
    """ChunkValidationError carries the domain and the missing field names."""
    from app.services.scraper_chunks.schemas import ChunkValidationError

    exc = ChunkValidationError(domain="vn_jobs", missing=["title", "company"])

    assert exc.domain == "vn_jobs"
    assert "title" in exc.missing
    assert "company" in exc.missing
