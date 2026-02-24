import pytest
from pydantic import ValidationError

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument


def test_valid_document_created_with_defaults():
    doc = ConnectorDocument(
        title="Task",
        source_markdown="## Task\n\nSome content.",
        unique_id="task-1",
        document_type=DocumentType.CLICKUP_CONNECTOR,
        search_space_id=1,
    )
    assert doc.should_summarize is True
    assert doc.should_use_code_chunker is False
    assert doc.metadata == {}
    assert doc.connector_id is None
    assert doc.created_by_id is None


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


def test_should_summarize_false_accepted():
    doc = ConnectorDocument(
        title="Message",
        source_markdown="Hello world.",
        unique_id="msg-1",
        document_type=DocumentType.SLACK_CONNECTOR,
        search_space_id=1,
        should_summarize=False,
    )
    assert doc.should_summarize is False


def test_should_use_code_chunker_accepted():
    doc = ConnectorDocument(
        title="Repository",
        source_markdown="def hello():\n    pass",
        unique_id="repo-1",
        document_type=DocumentType.GITHUB_CONNECTOR,
        search_space_id=1,
        should_use_code_chunker=True,
    )
    assert doc.should_use_code_chunker is True


def test_empty_title_raises():
    with pytest.raises(ValidationError):
        ConnectorDocument(
            title="",
            source_markdown="## Content",
            unique_id="task-1",
            document_type=DocumentType.CLICKUP_CONNECTOR,
            search_space_id=1,
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
