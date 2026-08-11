"""Unit tests for ``app.services.chainlens.private_provider``."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chainlens.private_provider import PrivateProviderService
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
    PrivateProviderChunk,
    PrivateProviderChunkMetadata,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_workspace():
    """Return a lightweight workspace stand-in."""
    return SimpleNamespace(
        id=7,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000042"),
    )


@pytest.fixture
def fake_session():
    return MagicMock()


def _make_request(**overrides) -> PrivateDataSearchRequest:
    defaults = {
        "query": "private search query",
        "workspaceId": 7,
        "userId": None,
        "connectorId": None,
        "sources": None,
        "topK": 20,
    }
    defaults.update(overrides)
    return PrivateDataSearchRequest(**defaults)


def test_request_strips_query_and_validates():
    req = _make_request(query="  spaced  ")
    assert req.query == "spaced"

    with pytest.raises(ValueError):
        _make_request(query="")

    with pytest.raises(ValueError):
        _make_request(workspaceId=0)

    with pytest.raises(ValueError):
        _make_request(topK=0)

    with pytest.raises(ValueError):
        _make_request(topK=101)


def test_chunk_source_is_private_provider():
    chunk = PrivateProviderChunk(
        content="hello",
        metadata=PrivateProviderChunkMetadata(
            source="private_provider",
            sourceId="nowing://documents/1/chunks/2",
            domain="nowing",
            fetchedAt="2026-08-11T00:00:00+00:00",
            contentType="FILE",
        ),
    )
    assert chunk.metadata.source == "private_provider"


def test_response_defaults_to_empty_and_zero_cost():
    response = PrivateDataSearchResponse()
    assert response.chunks == []
    assert response.costDollars == 0.0


@pytest.mark.asyncio
async def test_search_returns_empty_when_connector_not_found(
    fake_session, fake_workspace, monkeypatch
):
    """Requesting an unknown connector yields an empty, zero-cost response."""
    service = PrivateProviderService(fake_session)

    # Mock workspace membership lookup: requested user is not a member.
    monkeypatch.setattr(service, "_is_workspace_member", AsyncMock(return_value=False))

    # Mock retrievers to return hits so we can verify the connector filter empties them.
    chunk_results = [
        {
            "document": {"id": 1, "title": "Doc", "document_type": "FILE"},
            "chunks": [{"chunk_id": 10, "content": "content"}],
        }
    ]
    monkeypatch.setattr(
        service._chunk_retriever,
        "hybrid_search",
        AsyncMock(return_value=chunk_results),
    )
    monkeypatch.setattr(
        service._document_retriever,
        "hybrid_search",
        AsyncMock(return_value=[]),
    )

    # Connector not in DB: session returns None.
    result = MagicMock()
    result.scalars.return_value.first = MagicMock(return_value=None)
    fake_session.execute = AsyncMock(return_value=result)

    # Patch embedding and memory search.
    fake_embed = AsyncMock(return_value=[0.1] * 384)
    monkeypatch.setattr(
        "app.services.chainlens.private_provider.config.embedding_model_instance.embed",
        fake_embed,
    )
    monkeypatch.setattr(
        service,
        "_search_memory",
        AsyncMock(return_value=[]),
    )

    request = _make_request(connectorId=999)
    response = await service.search(request, fake_workspace)

    assert response.chunks == []
    assert response.costDollars == 0.0


@pytest.mark.asyncio
async def test_build_chunks_maps_retriever_results(fake_session, fake_workspace):
    """Document/Chunk retriever results are mapped to PrivateProviderChunk."""
    service = PrivateProviderService(fake_session)

    chunk_results = [
        {
            "document": {
                "id": 1,
                "title": "My Document",
                "document_type": "FILE",
            },
            "chunks": [
                {"chunk_id": 10, "content": "first chunk"},
                {"chunk_id": 11, "content": "second chunk"},
            ],
        }
    ]
    doc_results = [
        {
            "document": {
                "id": 2,
                "title": "Other Doc",
                "document_type": "NOTE",
            },
            "chunks": [
                {"chunk_id": 20, "content": "other chunk"},
            ],
        }
    ]

    doc_meta = {
        1: {"connector_id": None, "updated_at": None},
        2: {"connector_id": None, "updated_at": None},
    }

    request = _make_request(topK=10)
    response = service._build_chunks(
        request=request,
        chunk_results=chunk_results,
        doc_results=doc_results,
        memory_results=[],
        workspace=fake_workspace,
        connector_id=None,
        doc_meta=doc_meta,
    )

    assert len(response) == 3
    assert response[0].metadata.source == "private_provider"
    assert response[0].metadata.document_id == 1
    assert response[0].metadata.chunk_id == 10
    assert response[0].metadata.url == "nowing://documents/1/chunks/10"
    assert response[2].metadata.document_id == 2


@pytest.mark.asyncio
async def test_build_chunks_filters_by_connector_id(fake_session, fake_workspace):
    """Only documents whose connector_id matches the request are returned."""
    service = PrivateProviderService(fake_session)

    chunk_results = [
        {
            "document": {
                "id": 1,
                "title": "Connector Doc",
                "document_type": "SLACK_CONNECTOR",
            },
            "chunks": [{"chunk_id": 10, "content": "slack chunk"}],
        },
        {
            "document": {
                "id": 2,
                "title": "Other Doc",
                "document_type": "FILE",
            },
            "chunks": [{"chunk_id": 20, "content": "other chunk"}],
        },
    ]

    doc_meta = {
        1: {"connector_id": 42, "updated_at": None},
        2: {"connector_id": None, "updated_at": None},
    }

    response = service._build_chunks(
        request=_make_request(topK=10),
        chunk_results=chunk_results,
        doc_results=[],
        memory_results=[],
        workspace=fake_workspace,
        connector_id=42,
        doc_meta=doc_meta,
    )

    assert len(response) == 1
    assert response[0].metadata.connector_id == 42
    assert "connectors/42" in response[0].metadata.sourceId


@pytest.mark.asyncio
async def test_build_chunks_respects_top_k(fake_session, fake_workspace):
    """The merged chunk list is truncated to the request's ``topK``."""
    service = PrivateProviderService(fake_session)

    chunk_results = [
        {
            "document": {"id": 1, "title": "Doc", "document_type": "FILE"},
            "chunks": [{"chunk_id": i, "content": f"chunk {i}"} for i in range(10)],
        }
    ]
    doc_meta = {1: {"connector_id": None, "updated_at": None}}

    response = service._build_chunks(
        request=_make_request(topK=3),
        chunk_results=chunk_results,
        doc_results=[],
        memory_results=[],
        workspace=fake_workspace,
        connector_id=None,
        doc_meta=doc_meta,
    )

    assert len(response) == 3
    assert response[0].metadata.chunk_id == 0


@pytest.mark.asyncio
async def test_build_chunks_deduplicates_by_chunk_id(fake_session, fake_workspace):
    """The same chunk returned by both retrievers appears only once."""
    service = PrivateProviderService(fake_session)

    shared_doc = {"id": 1, "title": "Doc", "document_type": "FILE"}
    chunk = {"chunk_id": 10, "content": "shared chunk"}
    chunk_results = [{"document": shared_doc, "chunks": [chunk]}]
    doc_results = [{"document": shared_doc, "chunks": [chunk]}]
    doc_meta = {1: {"connector_id": None, "updated_at": None}}

    response = service._build_chunks(
        request=_make_request(topK=10),
        chunk_results=chunk_results,
        doc_results=doc_results,
        memory_results=[],
        workspace=fake_workspace,
        connector_id=None,
        doc_meta=doc_meta,
    )

    assert len(response) == 1


@pytest.mark.asyncio
async def test_resolve_document_type_from_sources(fake_session, fake_workspace):
    """``sources`` are mapped to ``DocumentType`` values."""
    service = PrivateProviderService(fake_session)

    request = _make_request(sources=["FILE"])
    document_type = await service._resolve_document_type(request)
    assert document_type == "FILE"

    request = _make_request(sources=["FILE", "NOTION_CONNECTOR"])
    document_type = await service._resolve_document_type(request)
    assert document_type == ["FILE", "NOTION_CONNECTOR"]


@pytest.mark.asyncio
async def test_resolve_document_type_from_connector(
    fake_session, fake_workspace, monkeypatch
):
    """``connectorId`` maps to the connector's type value."""
    service = PrivateProviderService(fake_session)

    fake_connector = SimpleNamespace(
        connector_type=SimpleNamespace(value="SLACK_CONNECTOR")
    )
    result = MagicMock()
    result.scalars.return_value.first = MagicMock(return_value=fake_connector)
    fake_session.execute = AsyncMock(return_value=result)

    request = _make_request(connectorId=42)
    document_type = await service._resolve_document_type(request)
    assert document_type == "SLACK_CONNECTOR"
