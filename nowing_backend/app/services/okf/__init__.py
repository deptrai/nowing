"""Open Knowledge Format (OKF v0.2) serialization for the Nowing KB.

Single source of truth for turning documents, memories, chunks, and relations
into OKF concepts, ``index.md`` listings and ``log.md`` logs. Pure KB-layer
functions; every consumer (ZIP export, REST, MCP, agents) calls in.

The OKF-native model: database rows are canonical, and frontmatter is *derived*
from their columns on read (never stored), so rows are conformant by
construction. Chunks and embeddings are a *derived*, rebuildable search
projection - never a source of truth.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from app.services.okf.redaction import redact_secrets
from app.services.okf.serializer import (
    INDEX_FILENAME,
    LOG_FILENAME,
    ConceptRef,
    LogEntry,
    SubdirRef,
    build_frontmatter,
    chunk_to_concept,
    citation_to_concept,
    concept_to_markdown,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    memory_to_concept,
    relation_to_concept,
    render_frontmatter,
)
from app.services.okf.type_mapping import (
    OKF_TYPE_BY_DOCUMENT_TYPE,
    okf_chunk_type,
    okf_citation_type,
    okf_memory_type,
    okf_relation_type,
    okf_resource,
    okf_type,
)
from app.services.okf.validator import (
    is_conformant_concept,
    parse_frontmatter,
    validate_bundle,
    validate_concept,
)

__all__ = [
    "INDEX_FILENAME",
    "LOG_FILENAME",
    "OKF_TYPE_BY_DOCUMENT_TYPE",
    "ConceptRef",
    "LogEntry",
    "SubdirRef",
    "build_frontmatter",
    "chunk_to_concept",
    "citation_to_concept",
    "concept_to_markdown",
    "document_to_concept",
    "folder_to_index",
    "folder_to_log",
    "is_conformant_concept",
    "memory_to_concept",
    "okf_chunk_type",
    "okf_citation_type",
    "okf_memory_type",
    "okf_relation_type",
    "okf_resource",
    "okf_type",
    "parse_frontmatter",
    "redact_secrets",
    "relation_to_concept",
    "render_frontmatter",
    "validate_bundle",
    "validate_concept",
]
