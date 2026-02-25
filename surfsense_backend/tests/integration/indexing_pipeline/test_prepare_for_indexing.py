import pytest
from sqlalchemy import select

from app.db import Document, DocumentStatus
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration


async def test_new_document_is_persisted_with_pending_status(
    db_session, db_search_space, make_connector_document
):
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc])

    assert len(results) == 1
    document_id = results[0].id

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    reloaded = result.scalars().first()

    assert reloaded is not None
    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.PENDING)


async def test_unchanged_document_is_skipped(
    db_session, db_search_space, make_connector_document
):
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    await service.prepare_for_indexing([doc])
    results = await service.prepare_for_indexing([doc])

    assert results == []


async def test_title_only_change_updates_title_in_db(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(search_space_id=db_search_space.id, title="Original Title")
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    renamed = make_connector_document(search_space_id=db_search_space.id, title="Updated Title")
    results = await service.prepare_for_indexing([renamed])

    assert results == []

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    reloaded = result.scalars().first()

    assert reloaded.title == "Updated Title"


async def test_changed_content_is_returned_for_reprocessing(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(search_space_id=db_search_space.id, source_markdown="## v1")
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    original_id = first[0].id

    updated = make_connector_document(search_space_id=db_search_space.id, source_markdown="## v2")
    results = await service.prepare_for_indexing([updated])

    assert len(results) == 1
    assert results[0].id == original_id

    result = await db_session.execute(select(Document).filter(Document.id == original_id))
    reloaded = result.scalars().first()

    assert reloaded.source_markdown == "## v2"
    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.PENDING)


async def test_all_documents_in_batch_are_persisted(
    db_session, db_search_space, make_connector_document
):
    docs = [
        make_connector_document(search_space_id=db_search_space.id, unique_id="id-1", title="Doc 1", source_markdown="## Content 1"),
        make_connector_document(search_space_id=db_search_space.id, unique_id="id-2", title="Doc 2", source_markdown="## Content 2"),
        make_connector_document(search_space_id=db_search_space.id, unique_id="id-3", title="Doc 3", source_markdown="## Content 3"),
    ]
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing(docs)

    assert len(results) == 3

    result = await db_session.execute(select(Document).filter(Document.search_space_id == db_search_space.id))
    rows = result.scalars().all()

    assert len(rows) == 3


async def test_duplicate_in_batch_is_persisted_once(
    db_session, db_search_space, make_connector_document
):
    doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc, doc])

    assert len(results) == 1

    result = await db_session.execute(select(Document).filter(Document.search_space_id == db_search_space.id))
    rows = result.scalars().all()

    assert len(rows) == 1


async def test_created_by_id_is_persisted(
    db_session, db_user, db_search_space, make_connector_document
):
    doc = make_connector_document(
        search_space_id=db_search_space.id,
        created_by_id=str(db_user.id),
    )
    service = IndexingPipelineService(session=db_session)

    results = await service.prepare_for_indexing([doc])
    document_id = results[0].id

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    reloaded = result.scalars().first()

    assert str(reloaded.created_by_id) == str(db_user.id)


async def test_metadata_is_updated_when_content_changes(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v1",
        metadata={"status": "in_progress"},
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    updated = make_connector_document(
        search_space_id=db_search_space.id,
        source_markdown="## v2",
        metadata={"status": "done"},
    )
    await service.prepare_for_indexing([updated])

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    reloaded = result.scalars().first()

    assert reloaded.document_metadata == {"status": "done"}


async def test_updated_at_advances_when_title_only_changes(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(search_space_id=db_search_space.id, title="Old Title")
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    updated_at_v1 = result.scalars().first().updated_at

    renamed = make_connector_document(search_space_id=db_search_space.id, title="New Title")
    await service.prepare_for_indexing([renamed])

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    updated_at_v2 = result.scalars().first().updated_at

    assert updated_at_v2 > updated_at_v1


async def test_updated_at_advances_when_content_changes(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(search_space_id=db_search_space.id, source_markdown="## v1")
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    document_id = first[0].id

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    updated_at_v1 = result.scalars().first().updated_at

    updated = make_connector_document(search_space_id=db_search_space.id, source_markdown="## v2")
    await service.prepare_for_indexing([updated])

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    updated_at_v2 = result.scalars().first().updated_at

    assert updated_at_v2 > updated_at_v1


async def test_same_content_from_different_source_is_skipped(
    db_session, db_search_space, make_connector_document
):
    first = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-a",
        source_markdown="## Shared content",
    )
    second = make_connector_document(
        search_space_id=db_search_space.id,
        unique_id="source-b",
        source_markdown="## Shared content",
    )
    service = IndexingPipelineService(session=db_session)

    await service.prepare_for_indexing([first])
    results = await service.prepare_for_indexing([second])

    assert results == []

    result = await db_session.execute(
        select(Document).filter(Document.search_space_id == db_search_space.id)
    )
    assert len(result.scalars().all()) == 1


async def test_title_and_content_change_updates_both_and_returns_document(
    db_session, db_search_space, make_connector_document
):
    original = make_connector_document(
        search_space_id=db_search_space.id,
        title="Original Title",
        source_markdown="## v1",
    )
    service = IndexingPipelineService(session=db_session)

    first = await service.prepare_for_indexing([original])
    original_id = first[0].id

    updated = make_connector_document(
        search_space_id=db_search_space.id,
        title="Updated Title",
        source_markdown="## v2",
    )
    results = await service.prepare_for_indexing([updated])

    assert len(results) == 1
    assert results[0].id == original_id

    result = await db_session.execute(select(Document).filter(Document.id == original_id))
    reloaded = result.scalars().first()

    assert reloaded.title == "Updated Title"
    assert reloaded.source_markdown == "## v2"
