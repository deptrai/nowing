from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument


@pytest.fixture
def make_connector_document():
    """Factory fixture: returns a callable that builds a ConnectorDocument with sensible defaults."""

    def _factory(
        *,
        title: str = "Test Document",
        source_markdown: str = "# Test content",
        unique_id: str = "test-unique-id",
        document_type: DocumentType = DocumentType.FILE,
        search_space_id: int = 1,
        created_by_id: str = "user-001",
        **kwargs,
    ) -> ConnectorDocument:
        return ConnectorDocument(
            title=title,
            source_markdown=source_markdown,
            unique_id=unique_id,
            document_type=document_type,
            search_space_id=search_space_id,
            created_by_id=created_by_id,
            **kwargs,
        )

    return _factory


@pytest.fixture
def patched_summarizer_chain(monkeypatch):
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=MagicMock(content="The summary."))

    template = MagicMock()
    template.__or__ = MagicMock(return_value=chain)

    monkeypatch.setattr(
        "app.indexing_pipeline.document_summarizer.SUMMARY_PROMPT_TEMPLATE",
        template,
    )
    return chain


@pytest.fixture
def patched_chunker_instance(monkeypatch):
    mock = MagicMock()
    mock.chunk.return_value = [MagicMock(text="prose chunk")]
    monkeypatch.setattr(
        "app.indexing_pipeline.document_chunker.config.chunker_instance", mock
    )
    return mock


@pytest.fixture
def patched_code_chunker_instance(monkeypatch):
    mock = MagicMock()
    mock.chunk.return_value = [MagicMock(text="code chunk")]
    monkeypatch.setattr(
        "app.indexing_pipeline.document_chunker.config.code_chunker_instance", mock
    )
    return mock
