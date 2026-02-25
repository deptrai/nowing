import pytest
from pydantic import ValidationError

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument


def test_valid_document_created_with_required_fields():
    doc = ConnectorDocument(
        title="Task",
        source_markdown="## Task\n\nSome content.",
        unique_id="task-1",
        document_type=DocumentType.CLICKUP_CONNECTOR,
        search_space_id=1,
        connector_id=42,
        created_by_id="00000000-0000-0000-0000-000000000001",
    )
    assert doc.should_summarize is True
    assert doc.should_use_code_chunker is False
    assert doc.metadata == {}
    assert doc.connector_id == 42
    assert doc.created_by_id == "00000000-0000-0000-0000-000000000001"


def test_omitting_connector_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
            created_by_id="00000000-0000-0000-0000-000000000001",
        )


def test_omitting_created_by_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
            connector_id=42,
        )


def test_empty_source_markdown_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
        )


def test_whitespace_only_source_markdown_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="   \n\t  ",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
        )


def test_empty_title_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
        )


def test_empty_created_by_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
            connector_id=42,
            created_by_id="",
        )


def test_zero_connector_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
            connector_id=0,
            created_by_id="00000000-0000-0000-0000-000000000001",
        )


def test_zero_search_space_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=0,
            connector_id=42,
            created_by_id="00000000-0000-0000-0000-000000000001",
        )


def test_empty_unique_id_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="Task",
            source_markdown="## Content",
            unique_id="",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
        )
