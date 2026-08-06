"""OKF serializer self-checks: emitted concepts stay conformant and the
frontmatter fields consumers rely on (type/title/timestamp) round-trip.
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.db import (
    Chunk,
    Document,
    DocumentType,
    Memory,
    MemoryRelation,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
)
from app.services.okf import (
    ConceptRef,
    LogEntry,
    SubdirRef,
    chunk_to_concept,
    citation_to_concept,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    is_conformant_concept,
    memory_to_concept,
    parse_frontmatter,
    relation_to_concept,
    validate_concept,
)


def _make_document() -> Document:
    return Document(
        title="Weekly Sync Notes",
        document_type=DocumentType.NOTE,
        document_metadata={"tags": ["team", "meeting"], "url": "https://example.com/n"},
        updated_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )


def test_concept_is_conformant_and_roundtrips() -> None:
    concept = document_to_concept(_make_document(), body="# Agenda\n\nShip OKF.")

    assert is_conformant_concept(concept)

    frontmatter, error = parse_frontmatter(concept)
    assert error is None
    assert frontmatter["type"] == "Note"
    assert frontmatter["title"] == "Weekly Sync Notes"
    assert frontmatter["tags"] == ["team", "meeting"]
    assert frontmatter["resource"] == "https://example.com/n"
    assert frontmatter["timestamp"] == "2026-05-28T22:49:59+00:00"
    assert "# Agenda" in concept


def test_type_is_always_present_even_without_metadata() -> None:
    doc = Document(title="Raw", document_type=DocumentType.CRAWLED_URL)
    concept = document_to_concept(doc, body="body")
    frontmatter, error = parse_frontmatter(concept)
    assert error is None
    assert frontmatter["type"] == "Web Page"
    assert "resource" not in frontmatter
    assert "tags" not in frontmatter


def test_validator_rejects_non_conformant_documents() -> None:
    assert validate_concept("no frontmatter here")
    assert validate_concept("---\ntitle: Missing type\n---\nbody")


def test_folder_index_groups_by_type_and_lists_subdirs() -> None:
    index = folder_to_index(
        concepts=[
            ConceptRef(
                title="Orders", filename="orders.md", type="Note", description="x"
            ),
        ],
        subdirectories=[SubdirRef(name="tables", description="Table docs")],
    )
    assert "# Subdirectories" in index
    assert "* [tables](tables/index.md) - Table docs" in index
    assert "# Note" in index
    assert "* [Orders](orders.md) - x" in index


def test_folder_log_lists_concepts_newest_first() -> None:
    log = folder_to_log(
        [
            LogEntry(title="Older", timestamp="2026-01-01T00:00:00+00:00"),
            LogEntry(title="Newer", timestamp="2026-06-01T00:00:00+00:00"),
            LogEntry(title="Undated", timestamp=None),
        ]
    )
    assert "# Change Log" in log
    assert log.index("Newer") < log.index("Older") < log.index("Undated")
    assert "* Newer - 2026-06-01T00:00:00+00:00" in log


def test_folder_log_is_empty_when_no_entries() -> None:
    assert folder_to_log([]) == ""


def test_export_log_files_synthesized_only_where_docs_live() -> None:
    from app.services.export_service import _build_log_files

    files = dict(
        _build_log_files(
            {
                "": [LogEntry(title="Root Doc", timestamp="2026-05-01T00:00:00+00:00")],
                "Research/AI": [LogEntry(title="Nested", timestamp=None)],
            }
        )
    )
    assert "# Change Log" in files["log.md"]
    assert "Root Doc" in files["log.md"]
    assert "Nested" in files["Research/AI/log.md"]
    assert "Research/log.md" not in files


def test_export_index_files_include_root_version_and_ancestors() -> None:
    from app.services.export_service import _build_index_files

    files = dict(
        _build_index_files(
            {"Research/AI": [ConceptRef(title="Note", filename="note.md", type="Note")]}
        )
    )

    assert files["index.md"].startswith('---\nokf_version: "0.2"\n---')
    assert "* [Research](Research/index.md)" in files["index.md"]
    assert "* [AI](AI/index.md)" in files["Research/index.md"]
    assert "* [Note](note.md)" in files["Research/AI/index.md"]


def test_memory_to_concept_is_conformant() -> None:
    memory = Memory(
        content="Important fact",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=["project"],
        updated_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )
    concept = memory_to_concept(memory)
    assert is_conformant_concept(concept)
    frontmatter, error = parse_frontmatter(concept)
    assert error is None
    assert frontmatter["type"] == "Semantic"
    assert frontmatter["title"] == "Important fact"
    assert frontmatter["tags"] == ["project"]


def test_memory_to_concept_run_citation() -> None:
    run_id = uuid4()
    memory = Memory(
        content="Run fact",
        type=MemoryType.EPISODIC,
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=run_id,
        updated_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )
    concept = memory_to_concept(memory)
    frontmatter, _ = parse_frontmatter(concept)
    assert frontmatter["resource"] == f"run_{run_id}"


def test_chunk_to_concept_is_conformant() -> None:
    chunk = Chunk(
        content="chunk body",
        position=3,
        document_id=1,
        created_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )
    concept = chunk_to_concept(chunk, document_path="Research/Note.md")
    assert is_conformant_concept(concept)
    frontmatter, _ = parse_frontmatter(concept)
    assert frontmatter["type"] == "Chunk"
    assert frontmatter["title"] == "Chunk 3"
    assert frontmatter["resource"] == "Research/Note.md"
    assert "chunk body" in concept


def test_relation_to_concept_is_conformant() -> None:
    relation = MemoryRelation(
        workspace_id=1,
        from_memory_id=1,
        to_memory_id=2,
        relation_type=MemoryRelationType.DERIVED_FROM,
    )
    concept = relation_to_concept(
        relation,
        from_path=".okf/memories/memory_1.md",
        to_path=".okf/memories/memory_2.md",
    )
    assert is_conformant_concept(concept)
    frontmatter, _ = parse_frontmatter(concept)
    assert frontmatter["type"] == "Derived From"
    assert ".okf/memories/memory_1.md" in concept


def test_citation_to_concept_redacts_source_input() -> None:
    memory = Memory(
        content="Cited fact",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.SCRAPER_RUN,
        source_run_id=uuid4(),
        source_capability="search",
        source_input={"api_key": "sk-secret123", "query": "okf"},
        updated_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )
    concept = citation_to_concept(memory)
    assert is_conformant_concept(concept)
    assert "[REDACTED]" in concept
    assert "sk-secret123" not in concept


def test_document_to_concept_redacts_metadata_secrets() -> None:
    doc = Document(
        title="Connector doc",
        document_type=DocumentType.GITHUB_CONNECTOR,
        document_metadata={
            "url": "https://example.com/repo",
            "token": "ghp_supersecret",
        },
    )
    concept = document_to_concept(doc, body="body")
    # The raw secret must not leak anywhere in the emitted concept.
    assert "ghp_supersecret" not in concept
    # Resource is extracted from the URL before redaction.
    assert "https://example.com/repo" in concept
