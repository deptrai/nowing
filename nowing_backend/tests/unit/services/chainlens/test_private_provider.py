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

    # Connector not in DB: session.scalar returns None.
    fake_session.scalar = AsyncMock(return_value=None)
    fake_session.execute = AsyncMock(return_value=None)

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
        request_connector_id=None,
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
        request_connector_id=42,
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
        request_connector_id=None,
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
        request_connector_id=None,
        doc_meta=doc_meta,
    )

    assert len(response) == 1


@pytest.mark.asyncio
async def test_resolve_document_type_from_sources(fake_session, fake_workspace):
    """``sources`` are mapped to ``DocumentType`` values."""
    service = PrivateProviderService(fake_session)

    request = _make_request(sources=["FILE"])
    document_type = await service._resolve_document_type(request, fake_workspace.id)
    assert document_type == ["FILE"]

    request = _make_request(sources=["FILE", "NOTION_CONNECTOR"])
    document_type = await service._resolve_document_type(request, fake_workspace.id)
    assert document_type == ["FILE", "NOTION_CONNECTOR"]


def test_format_ts_uses_created_at_fallback():
    """Missing updated_at falls back to created_at before current time."""
    from datetime import UTC, datetime

    created = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)
    assert (
        PrivateProviderService._format_ts(None, fallback=created) == created.isoformat()
    )


def test_build_chunks_skips_memory_with_none_content(fake_session, fake_workspace):
    """A memory with ``None`` content does not crash the builder."""
    service = PrivateProviderService(fake_session)

    class _Mem:
        id = 99
        content = None
        updated_at = None
        created_at = None
        type = None

    class _Scored:
        memory = _Mem()

    chunks = service._build_chunks(
        request=_make_request(topK=10),
        chunk_results=[],
        doc_results=[],
        memory_results=[_Scored()],
        workspace=fake_workspace,
        request_connector_id=None,
        doc_meta={},
    )
    assert chunks == []


@pytest.mark.asyncio
async def test_search_sets_tenant_context_for_owner_and_records_usage(
    fake_session, fake_workspace, monkeypatch
):
    """Service sets tenant context and records TokenUsage for workspace owner."""
    service = PrivateProviderService(fake_session)
    tenant_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.chainlens.private_provider.set_request_tenant_context",
        tenant_spy,
    )

    monkeypatch.setattr(service, "_is_workspace_member", AsyncMock(return_value=False))
    monkeypatch.setattr(service, "_resolve_document_type", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service,
        "_run_retrievers",
        AsyncMock(return_value=([], [])),
    )
    monkeypatch.setattr(service, "_search_memory", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service,
        "_load_document_meta",
        AsyncMock(return_value={}),
    )

    fake_embed = AsyncMock(return_value=[0.1] * 384)
    monkeypatch.setattr(
        "app.services.chainlens.private_provider.config.embedding_model_instance.embed",
        fake_embed,
    )

    record_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.chainlens.private_provider.record_token_usage",
        record_spy,
    )

    await service.search(_make_request(), fake_workspace)

    assert tenant_spy.await_count == 2
    # First and last set_request_tenant_context calls use workspace + owner.
    first_call = tenant_spy.await_args_list[0].kwargs
    assert first_call["workspace_id"] == fake_workspace.id
    assert first_call["user_id"] == str(fake_workspace.user_id)
    assert record_spy.await_count == 1
    assert record_spy.await_args.kwargs["workspace_id"] == fake_workspace.id
    assert record_spy.await_args.kwargs["user_id"] == fake_workspace.user_id


@pytest.mark.asyncio
async def test_resolve_document_type_from_connector(
    fake_session, fake_workspace, monkeypatch
):
    """``connectorId`` maps to the connector's type value."""
    service = PrivateProviderService(fake_session)

    fake_connector = SimpleNamespace(
        connector_type=SimpleNamespace(value="SLACK_CONNECTOR")
    )
    fake_session.scalar = AsyncMock(return_value=fake_connector.connector_type)

    request = _make_request(connectorId=42)
    document_type = await service._resolve_document_type(request, fake_workspace.id)
    assert document_type == ["SLACK_CONNECTOR"]
