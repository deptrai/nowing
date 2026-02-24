import pytest
from sqlalchemy import select

from app.db import Document, DocumentStatus
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService

pytestmark = pytest.mark.integration


async def test_sets_status_ready(
    db_session, db_search_space, make_connector_document,
    mock_llm, patched_generate_summary, patched_create_chunks,
):
    connector_doc = make_connector_document(search_space_id=db_search_space.id)
    service = IndexingPipelineService(session=db_session)

    prepared = await service.prepare_for_indexing([connector_doc])
    document = prepared[0]
    document_id = document.id

    await service.index(document, connector_doc, mock_llm)

    result = await db_session.execute(select(Document).filter(Document.id == document_id))
    reloaded = result.scalars().first()

    assert DocumentStatus.is_state(reloaded.status, DocumentStatus.READY)
