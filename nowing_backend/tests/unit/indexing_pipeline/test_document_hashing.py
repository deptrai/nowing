import pytest

from app.db import DocumentType
from app.indexing_pipeline.document_hashing import (
    compute_content_hash,
    compute_identifier_hash,
    compute_unique_identifier_hash,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "kwargs_a,kwargs_b",
    [
        ({"unique_id": "id-001"}, {"unique_id": "id-002"}),
        ({"search_space_id": 1}, {"search_space_id": 2}),
        (
            {"document_type": DocumentType.CLICKUP_CONNECTOR},
            {"document_type": DocumentType.NOTION_CONNECTOR},
        ),
    ],
    ids=["unique_id", "search_space_id", "document_type"],
)
def test_different_inputs_produce_different_identifier_hash(
    make_connector_document, kwargs_a, kwargs_b
):
    """Changing unique_id, search_space_id, or document_type produces different identifier hashes."""
    doc_a = make_connector_document(**kwargs_a)
    doc_b = make_connector_document(**kwargs_b)
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(doc_b)


@pytest.mark.parametrize(
    "kwargs_a,kwargs_b,equal",
    [
        (
            {"source_markdown": "Hello world", "search_space_id": 1},
            {"source_markdown": "Hello world", "search_space_id": 1},
            True,
        ),
        (
            {"source_markdown": "Hello world", "search_space_id": 1},
            {"source_markdown": "Hello world", "search_space_id": 2},
            False,
        ),
        (
            {"source_markdown": "Original content"},
            {"source_markdown": "Updated content"},
            False,
        ),
    ],
    ids=["same_content_same_space", "same_content_different_space", "different_content"],
)
def test_content_hash_equality(make_connector_document, kwargs_a, kwargs_b, equal):
    """Content hash equality depends on both source_markdown and search_space_id."""
    doc_a = make_connector_document(**kwargs_a)
    doc_b = make_connector_document(**kwargs_b)
    if equal:
        assert compute_content_hash(doc_a) == compute_content_hash(doc_b)
    else:
        assert compute_content_hash(doc_a) != compute_content_hash(doc_b)


def test_compute_identifier_hash_matches_connector_doc_hash(make_connector_document):
    """Raw-args hash equals ConnectorDocument hash for equivalent inputs."""
    doc = make_connector_document(
        document_type=DocumentType.GOOGLE_GMAIL_CONNECTOR,
        unique_id="msg-123",
        search_space_id=5,
    )
    raw_hash = compute_identifier_hash("GOOGLE_GMAIL_CONNECTOR", "msg-123", 5)
    assert raw_hash == compute_unique_identifier_hash(doc)


def test_compute_identifier_hash_differs_for_different_inputs():
    """Different arguments produce different hashes."""
    h1 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 1)
    h2 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-2", 1)
    h3 = compute_identifier_hash("GOOGLE_DRIVE_FILE", "file-1", 2)
    h4 = compute_identifier_hash("COMPOSIO_GOOGLE_DRIVE_CONNECTOR", "file-1", 1)
    assert len({h1, h2, h3, h4}) == 4
