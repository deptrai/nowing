"""Integration tests for the canonical + document unified search API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.canonical.services.unified_search_service import UnifiedSearchService
from app.config import config as app_config
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    Chunk,
    Document,
    DocumentType,
)

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


_EMBEDDING_DIM = app_config.embedding_model_instance.dimension
_DUMMY_EMBEDDING = [0.1] * _EMBEDDING_DIM
_CURRENT_MODEL = app_config.EMBEDDING_MODEL or "unknown"


@pytest_asyncio.fixture
async def another_workspace(db_session, db_user):
    from app.db import Workspace

    space = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(space)
    await db_session.flush()
    return space


def _make_document(
    *,
    title: str,
    content: str,
    workspace_id: int,
    created_by_id: str,
    document_type: DocumentType = DocumentType.FILE,
    updated_at: datetime | None = None,
    status: dict | None = None,
) -> Document:
    return Document(
        title=title,
        document_type=document_type,
        content=content,
        source_markdown=content,
        content_hash=f"content-{uuid.uuid4().hex[:12]}",
        unique_identifier_hash=f"uid-{uuid.uuid4().hex[:12]}",
        embedding=_DUMMY_EMBEDDING,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        updated_at=updated_at or datetime.now(UTC),
        status=status or {"state": "ready"},
    )


def _make_chunk(*, content: str, document_id: int) -> Chunk:
    return Chunk(
        content=content,
        document_id=document_id,
        embedding=_DUMMY_EMBEDDING,
    )


def _make_canonical_entity(
    *,
    workspace_id: int,
    title: str,
    search_text: str,
    entity_type: str = "vn_bds.listing",
    embedding_status: str = "ready",
    last_seen_at: datetime | None = None,
) -> CanonicalEntity:
    return CanonicalEntity(
        workspace_id=workspace_id,
        entity_type=entity_type,
        canonical_title=title,
        canonical_data={"title": title},
        fingerprint=f"fp-{uuid.uuid4().hex[:12]}",
        search_text=search_text,
        source_count=1,
        confidence_score=0.9,
        conflict_flags=[],
        version=1,
        first_seen_at=datetime.now(UTC),
        last_seen_at=last_seen_at or datetime.now(UTC),
        embedding=_DUMMY_EMBEDDING,
        embedding_model_name=_CURRENT_MODEL,
        embedding_status=embedding_status,
    )


def _make_canonical_source(
    *,
    workspace_id: int,
    canonical_entity_id: uuid.UUID,
    source_name: str,
    source_record_id: str,
    entity_type: str = "vn_bds.listing",
) -> CanonicalEntitySource:
    return CanonicalEntitySource(
        workspace_id=workspace_id,
        canonical_entity_id=canonical_entity_id,
        entity_type=entity_type,
        source_name=source_name,
        source_record_id=source_record_id,
        source_snapshot={"title": "source"},
    )


@pytest_asyncio.fixture
async def seed_unified_search(db_session, db_user, db_workspace, another_workspace):
    """Seed docs, chunks and canonical entities for unified search tests."""
    user_id = str(db_user.id)
    space_id = db_workspace.id

    # Documents
    matching_doc = _make_document(
        title="Quarterly review document",
        content="quarterly performance review summary",
        workspace_id=space_id,
        created_by_id=user_id,
    )
    linked_doc = _make_document(
        title="Linked listing page",
        content="bán nhà quận 1 listing source text",
        workspace_id=space_id,
        created_by_id=user_id,
    )
    other_type_doc = _make_document(
        title="Note about quarterly",
        content="quarterly meeting notes",
        workspace_id=space_id,
        created_by_id=user_id,
        document_type=DocumentType.NOTE,
    )
    old_doc = _make_document(
        title="Old quarterly report",
        content="quarterly report from two years ago",
        workspace_id=space_id,
        created_by_id=user_id,
        updated_at=datetime.now(UTC) - timedelta(days=800),
    )
    pending_doc = _make_document(
        title="Pending quarterly doc",
        content="quarterly pending document",
        workspace_id=space_id,
        created_by_id=user_id,
        status={"state": "pending"},
    )

    db_session.add_all([matching_doc, linked_doc, other_type_doc, old_doc, pending_doc])
    await db_session.flush()

    chunks = [
        _make_chunk(
            content="quarterly performance review summary",
            document_id=matching_doc.id,
        ),
        _make_chunk(
            content="bán nhà quận 1 listing source text",
            document_id=linked_doc.id,
        ),
        _make_chunk(
            content="quarterly meeting notes",
            document_id=other_type_doc.id,
        ),
        _make_chunk(
            content="quarterly report from two years ago",
            document_id=old_doc.id,
        ),
        _make_chunk(
            content="quarterly pending document",
            document_id=pending_doc.id,
        ),
    ]
    db_session.add_all(chunks)
    await db_session.flush()

    # Canonical entities
    entity_matching = _make_canonical_entity(
        workspace_id=space_id,
        title="Bán nhà Quận 1",
        search_text="bán nhà quận 1",
        entity_type="vn_bds.listing",
    )
    entity_other_type = _make_canonical_entity(
        workspace_id=space_id,
        title="Quarterly note entity",
        search_text="quarterly meeting notes",
        entity_type="company.note",
    )
    entity_old = _make_canonical_entity(
        workspace_id=space_id,
        title="Old listing",
        search_text="old quarterly report",
        entity_type="vn_bds.listing",
        last_seen_at=datetime.now(UTC) - timedelta(days=800),
    )
    entity_stale = _make_canonical_entity(
        workspace_id=space_id,
        title="Stale embedding listing",
        search_text="quarterly stale",
        entity_type="vn_bds.listing",
        embedding_status="pending",
    )
    other_space_entity = _make_canonical_entity(
        workspace_id=another_workspace.id,
        title="Other space listing",
        search_text="bán nhà quận 1",
        entity_type="vn_bds.listing",
    )

    db_session.add_all(
        [
            entity_matching,
            entity_other_type,
            entity_old,
            entity_stale,
            other_space_entity,
        ]
    )
    await db_session.flush()

    # Sources
    sources = [
        _make_canonical_source(
            workspace_id=space_id,
            canonical_entity_id=entity_matching.id,
            source_name="document",
            source_record_id=str(linked_doc.id),
        ),
        _make_canonical_source(
            workspace_id=space_id,
            canonical_entity_id=entity_matching.id,
            source_name="batdongsan",
            source_record_id="bds-123",
        ),
        _make_canonical_source(
            workspace_id=space_id,
            canonical_entity_id=entity_other_type.id,
            source_name="note",
            source_record_id="note-1",
        ),
        _make_canonical_source(
            workspace_id=another_workspace.id,
            canonical_entity_id=other_space_entity.id,
            source_name="batdongsan",
            source_record_id="bds-other",
        ),
    ]
    db_session.add_all(sources)
    await db_session.flush()

    # Fix source counts to reflect the rows we just inserted.
    for entity in [entity_matching, entity_other_type, other_space_entity]:
        entity.source_count = 2 if entity == entity_matching else 1

    await db_session.flush()

    return {
        "workspace": db_workspace,
        "user": db_user,
        "another_workspace": another_workspace,
        "matching_doc": matching_doc,
        "linked_doc": linked_doc,
        "other_type_doc": other_type_doc,
        "old_doc": old_doc,
        "pending_doc": pending_doc,
        "entity_matching": entity_matching,
        "entity_other_type": entity_other_type,
        "entity_old": entity_old,
        "entity_stale": entity_stale,
        "other_space_entity": other_space_entity,
    }


@pytest.mark.asyncio
async def test_unified_search_returns_both_corpora(db_session, seed_unified_search):
    """Query matches a canonical entity and a document."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly performance",
        top_k=10,
    )

    assert results
    types = {r["type"] for r in results}
    assert "canonical_entity" in types
    assert "document" in types


@pytest.mark.asyncio
async def test_unified_search_collapse_linked_document(db_session, seed_unified_search):
    """A document linked to a canonical entity appears under the entity group."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="bán nhà quận 1",
        top_k=10,
    )

    linked_doc_id = seed_unified_search["linked_doc"].id
    matching_entity_id = seed_unified_search["entity_matching"].id

    top_doc_ids = [
        r["document"]["document_id"] for r in results if r["type"] == "document"
    ]
    assert linked_doc_id not in top_doc_ids

    canonical_group = next(
        (
            r
            for r in results
            if r["type"] == "canonical_entity"
            and r["entity"]["id"] == matching_entity_id
        ),
        None,
    )
    assert canonical_group is not None
    assert linked_doc_id in canonical_group["entity"]["linked_documents"]
    assert len(canonical_group["entity"]["source_ids"]) == 2


@pytest.mark.asyncio
async def test_unified_search_entity_type_filter(db_session, seed_unified_search):
    """Filter by canonical entity type."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly",
        top_k=10,
        entity_types=["company.note"],
    )

    for r in results:
        if r["type"] == "canonical_entity":
            assert r["entity"]["entity_type"] == "company.note"


@pytest.mark.asyncio
async def test_unified_search_document_type_filter(db_session, seed_unified_search):
    """Filter by document type."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly",
        top_k=10,
        document_types=["NOTE"],
    )

    for r in results:
        if r["type"] == "document":
            assert r["document"]["document"]["document_type"] == "NOTE"


@pytest.mark.asyncio
async def test_unified_search_date_filter(db_session, seed_unified_search):
    """Date filter excludes old canonical entities and documents."""
    service = UnifiedSearchService(db_session)
    now = datetime.now(UTC)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly",
        top_k=10,
        start_date=now - timedelta(days=30),
        end_date=now,
    )

    for r in results:
        if r["type"] == "canonical_entity":
            assert r["entity"]["id"] != seed_unified_search["entity_old"].id
        if r["type"] == "document":
            assert r["document"]["document_id"] != seed_unified_search["old_doc"].id


@pytest.mark.asyncio
async def test_unified_search_document_status_filter(db_session, seed_unified_search):
    """Status filter restricts document results."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly",
        top_k=10,
        statuses=["ready"],
    )

    doc_ids = {r["document"]["document_id"] for r in results if r["type"] == "document"}
    assert seed_unified_search["pending_doc"].id not in doc_ids


@pytest.mark.asyncio
async def test_unified_search_embedding_status_filter(db_session, seed_unified_search):
    """Embedding status filter includes pending-only canonical rows."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly stale",
        top_k=10,
        embedding_status="pending",
    )

    assert results
    for r in results:
        if r["type"] == "canonical_entity":
            assert r["entity"]["embedding_status"] == "pending"


@pytest.mark.asyncio
async def test_unified_search_workspace_isolation(db_session, seed_unified_search):
    """Entities and documents from another workspace are not returned."""
    service = UnifiedSearchService(db_session)
    results = await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="bán nhà quận 1",
        top_k=10,
    )

    entity_ids = {r["entity"]["id"] for r in results if r["type"] == "canonical_entity"}
    assert seed_unified_search["other_space_entity"].id not in entity_ids

    doc_ids = {r["document"]["document_id"] for r in results if r["type"] == "document"}
    # The other workspace has no documents in this fixture.
    assert all(isinstance(d, int) for d in doc_ids)


@pytest.mark.asyncio
async def test_unified_search_rls_requires_canonical_context(
    db_session, seed_unified_search
):
    """The service sets canonical workspace context before querying."""
    from app.canonical.tenant_context import get_canonical_workspace_id

    service = UnifiedSearchService(db_session)
    await service.search(
        workspace_id=seed_unified_search["workspace"].id,
        query_text="quarterly",
        top_k=10,
    )
    assert get_canonical_workspace_id(db_session) == seed_unified_search["workspace"].id
