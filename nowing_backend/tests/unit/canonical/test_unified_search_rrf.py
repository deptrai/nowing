"""Unit tests for the UnifiedSearchService RRF and collapse helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.canonical.services.unified_search_service import (
    UnifiedSearchService,
    _is_vector_eligible,
    _rrf_score,
)


class _FakeCanonicalEntity:
    def __init__(
        self,
        *,
        embedding,
        embedding_model_name,
        embedding_status,
    ):
        self.embedding = embedding
        self.embedding_model_name = embedding_model_name
        self.embedding_status = embedding_status


def test_rrf_score_with_both_ranks():
    """Weighted RRF with vector and full-text ranks."""
    score = _rrf_score(
        rank_vector=1,
        rank_fts=2,
        w_vector=0.7,
        w_fts=0.3,
        k=60,
    )
    expected = 0.7 / (60 + 1) + 0.3 / (60 + 2)
    assert score == pytest.approx(expected)


def test_rrf_score_missing_vector_rank():
    """A full-text-only result still contributes the FTS component."""
    score = _rrf_score(
        rank_vector=None,
        rank_fts=1,
        w_vector=0.7,
        w_fts=0.3,
        k=60,
    )
    assert score == pytest.approx(0.3 / 61)


def test_rrf_score_missing_fts_rank():
    """A vector-only result still contributes the vector component."""
    score = _rrf_score(
        rank_vector=1,
        rank_fts=None,
        w_vector=0.7,
        w_fts=0.3,
        k=60,
    )
    assert score == pytest.approx(0.7 / 61)


def test_vector_eligible_only_for_ready_current_embedding():
    """Null, stale model or non-ready status excludes the entity from vector ranking."""
    dim = 384
    entity = _FakeCanonicalEntity(
        embedding=[0.1] * dim,
        embedding_model_name="current-model",
        embedding_status="ready",
    )
    assert _is_vector_eligible(entity, "current-model") is True

    entity.embedding = None
    assert _is_vector_eligible(entity, "current-model") is False

    entity.embedding = [0.1] * dim
    entity.embedding_model_name = "old-model"
    assert _is_vector_eligible(entity, "current-model") is False

    entity.embedding_model_name = "current-model"
    entity.embedding_status = "pending"
    assert _is_vector_eligible(entity, "current-model") is False


@pytest.mark.asyncio
async def test_collapse_linked_documents():
    """Documents linked to a canonical entity in the result set are grouped."""
    entity_id = uuid.uuid4()
    canonical_results = [
        {
            "id": entity_id,
            "entity_type": "vn_bds.listing",
            "canonical_title": "Bán nhà Quận 1",
            "source_count": 1,
            "confidence_score": 0.9,
            "conflict_flags": [],
            "version": 1,
            "last_seen_at": None,
            "embedding_status": "ready",
            "score": 1.5,
        }
    ]
    document_results = [
        {"document_id": 1, "score": 1.0, "document": {"id": 1, "title": "doc"}},
        {"document_id": 2, "score": 0.9, "document": {"id": 2, "title": "linked"}},
    ]

    source_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            id=source_id,
            canonical_entity_id=entity_id,
            source_name="document",
            source_record_id="2",
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = UnifiedSearchService(mock_session)
    combined = await service._collapse_and_combine(
        workspace_id=1,
        document_results=document_results,
        canonical_results=canonical_results,
    )

    assert len(combined) == 2  # one canonical group, one unmatched document
    canonical_group = next(g for g in combined if g["type"] == "canonical_entity")
    assert canonical_group["entity"]["linked_documents"] == [2]
    assert source_id in canonical_group["entity"]["source_ids"]

    doc_group = next(g for g in combined if g["type"] == "document")
    assert doc_group["document"]["document_id"] == 1


@pytest.mark.asyncio
async def test_collapse_only_when_entity_present():
    """A linked document whose canonical entity is not in results stays top-level."""
    document_results = [
        {"document_id": 1, "score": 1.0, "document": {"id": 1, "title": "linked"}},
    ]

    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = UnifiedSearchService(mock_session)
    combined = await service._collapse_and_combine(
        workspace_id=1,
        document_results=document_results,
        canonical_results=[],  # no canonical results
    )

    assert len(combined) == 1
    assert combined[0]["type"] == "document"
    assert combined[0]["document"]["document_id"] == 1
