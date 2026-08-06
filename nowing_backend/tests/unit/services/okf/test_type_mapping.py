"""OKF type and resource mapping coverage."""

from __future__ import annotations

import pytest

from app.db import DocumentType, MemoryRelationType, MemoryType
from app.services.okf.type_mapping import (
    OKF_TYPE_BY_DOCUMENT_TYPE,
    okf_chunk_type,
    okf_citation_type,
    okf_memory_type,
    okf_relation_type,
    okf_resource,
    okf_type,
)


def test_every_document_type_maps_to_nonempty_okf_type() -> None:
    for document_type in DocumentType:
        okf = okf_type(document_type)
        expected = OKF_TYPE_BY_DOCUMENT_TYPE.get(
            document_type, document_type.value.replace("_", " ").title()
        )
        assert okf == expected
        assert okf.strip() == okf


def test_unknown_or_none_document_type_falls_back_gracefully() -> None:
    assert okf_type("WEIRD_CONNECTOR") == "Weird Connector"
    assert okf_type(None) == "Document"


@pytest.mark.parametrize(
    ("document_type", "metadata", "expected"),
    [
        (
            DocumentType.GITHUB_CONNECTOR,
            {"html_url": "https://github.com/x/repo"},
            "https://github.com/x/repo",
        ),
        (
            DocumentType.SLACK_CONNECTOR,
            {"permalink": "https://workspace.slack.com/x"},
            "https://workspace.slack.com/x",
        ),
        (
            DocumentType.NOTION_CONNECTOR,
            {"url": "https://notion.so/page"},
            "https://notion.so/page",
        ),
        (
            DocumentType.GOOGLE_DRIVE_FILE,
            {"webViewLink": "https://drive.google.com/file/d/1"},
            "https://drive.google.com/file/d/1",
        ),
        (
            DocumentType.YOUTUBE_VIDEO,
            {"video_url": "https://youtube.com/watch?v=1"},
            "https://youtube.com/watch?v=1",
        ),
        (
            DocumentType.CRAWLED_URL,
            {"source_url": "https://example.com"},
            "https://example.com",
        ),
        (
            DocumentType.EXTENSION,
            {"VisitedWebPageURL": "https://example.com/page"},
            "https://example.com/page",
        ),
        (DocumentType.NOTE, {"url": "https://example.com/n"}, "https://example.com/n"),
        (DocumentType.FILE, {"file_name": "x.pdf"}, None),
    ],
)
def test_okf_resource_extracts_canonical_url(document_type, metadata, expected) -> None:
    assert okf_resource(document_type, metadata) == expected


def test_okf_resource_rejects_non_http_uris_and_internal_ids() -> None:
    assert okf_resource(DocumentType.NOTE, {"url": "s3://bucket/file"}) is None
    assert okf_resource(DocumentType.NOTE, {"url": 12345}) is None
    assert okf_resource(DocumentType.NOTE, {"url": "/internal/123"}) is None


def test_okf_memory_types() -> None:
    assert okf_memory_type(MemoryType.SEMANTIC) == "Semantic"
    assert okf_memory_type("episodic") == "Episodic"
    assert okf_memory_type(None) == "Memory"


def test_okf_relation_types() -> None:
    assert okf_relation_type(MemoryRelationType.RELATED) == "Related"
    assert okf_relation_type("derived_from") == "Derived From"
    assert okf_relation_type(None) == "Relation"


def test_okf_chunk_and_citation_types() -> None:
    assert okf_chunk_type() == "Chunk"
    assert okf_citation_type() == "Citation"
