import pytest

from app.db import DocumentType
from app.indexing_pipeline.document_hashing import compute_content_hash, compute_unique_identifier_hash

pytestmark = pytest.mark.unit


def test_different_unique_id_produces_different_hash(make_connector_document):
    doc_a = make_connector_document(unique_id="id-001")
    doc_b = make_connector_document(unique_id="id-002")
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(doc_b)


def test_different_search_space_produces_different_identifier_hash(make_connector_document):
    doc_a = make_connector_document(search_space_id=1)
    doc_b = make_connector_document(search_space_id=2)
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(doc_b)


def test_different_document_type_produces_different_identifier_hash(make_connector_document):
    doc_a = make_connector_document(document_type=DocumentType.CLICKUP_CONNECTOR)
    doc_b = make_connector_document(document_type=DocumentType.NOTION_CONNECTOR)
    assert compute_unique_identifier_hash(doc_a) != compute_unique_identifier_hash(doc_b)


def test_same_content_same_space_produces_same_content_hash(make_connector_document):
    doc_a = make_connector_document(source_markdown="Hello world", search_space_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", search_space_id=1)
    assert compute_content_hash(doc_a) == compute_content_hash(doc_b)


def test_same_content_different_space_produces_different_content_hash(make_connector_document):
    doc_a = make_connector_document(source_markdown="Hello world", search_space_id=1)
    doc_b = make_connector_document(source_markdown="Hello world", search_space_id=2)
    assert compute_content_hash(doc_a) != compute_content_hash(doc_b)


def test_different_content_produces_different_content_hash(make_connector_document):
    doc_a = make_connector_document(source_markdown="Original content")
    doc_b = make_connector_document(source_markdown="Updated content")
    assert compute_content_hash(doc_a) != compute_content_hash(doc_b)
