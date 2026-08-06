"""Serialize Nowing knowledge into Open Knowledge Format (OKF v0.2).

Pure functions with no HTTP / MCP / framework dependencies. Given an ORM row
(:class:`~app.db.Document`, :class:`~app.db.Memory`, :class:`~app.db.Chunk`, or
:class:`~app.db.MemoryRelation`) they return OKF-conformant markdown. Every
consumer (ZIP export, REST, MCP, agents) calls these rather than re-implementing
frontmatter.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yaml

from app.db import Chunk, Document, Memory, MemoryRelation, MemorySourceType
from app.services.okf.redaction import redact_secrets
from app.services.okf.type_mapping import (
    okf_chunk_type,
    okf_citation_type,
    okf_memory_type,
    okf_relation_type,
    okf_resource,
    okf_type,
)

# Reserved OKF filenames; never used for concept documents.
INDEX_FILENAME = "index.md"
LOG_FILENAME = "log.md"

_FRONTMATTER_DELIMITER = "---"


def _timestamp(model: Document | Memory | Chunk | MemoryRelation) -> str | None:
    when = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
    if when is None:
        return None
    # ISO 8601, matching Google's sample bundles (e.g. 2026-05-28T22:49:59+00:00).
    return when.isoformat()


def _tags_from_metadata(metadata: dict[str, Any] | None) -> list[str] | None:
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("tags")
    if isinstance(raw, list):
        tags = [str(t).strip() for t in raw if str(t).strip()]
        return tags or None
    return None


def _memory_title(memory: Memory) -> str:
    content = (memory.content or "").replace("\n", " ").strip()
    if not content:
        return "Memory"
    if len(content) <= 80:
        return content
    return content[:80].rstrip() + "..."


def _citation_label(memory: Memory) -> str | None:
    if memory.source_run_id is not None:
        return f"run_{memory.source_run_id}"
    if memory.source_type == MemorySourceType.CHAT_MESSAGE and memory.source_id:
        return f"chat_{memory.source_id}"
    return None


def _memory_body(memory: Memory) -> str:
    """Memory body is its content; optional source recipe is kept in the citation."""
    return memory.content or ""


def _citation_body(memory: Memory) -> str:
    lines: list[str] = []
    if memory.source_capability:
        lines.append(f"**Capability:** {memory.source_capability}")
    if memory.source_input is not None:
        redacted = redact_secrets(memory.source_input)
        try:
            payload = json.dumps(redacted, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            payload = str(redacted)
        lines.append(f"**Input:**\n```json\n{payload}\n```")
    return "\n\n".join(lines)


def _memory_resource(memory: Memory, source_path: str | None = None) -> str | None:
    if source_path:
        return source_path
    return _citation_label(memory)


def build_frontmatter(
    model: Document | Memory | Chunk | MemoryRelation,
    *,
    redacted_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ordered OKF frontmatter mapping for a model.

    Only ``type`` is required; recommended keys are included only when we have a
    value. Insertion order is preserved in the emitted YAML.

    For :class:`~app.db.Document`, ``redacted_metadata`` is the already-redacted
    ``document_metadata`` dict; when omitted, it is redacted here.
    """
    frontmatter: dict[str, Any]

    if isinstance(model, Document):
        metadata = (
            redacted_metadata
            if redacted_metadata is not None
            else redact_secrets(model.document_metadata or {})
        )

        frontmatter = {"type": okf_type(model.document_type)}

        resource = okf_resource(model.document_type, metadata)
        if resource:
            frontmatter["resource"] = resource

        title = (model.title or "").strip()
        if title:
            frontmatter["title"] = title

        description = metadata.get("description")
        if isinstance(description, str) and description.strip():
            frontmatter["description"] = description.strip()

        tags = _tags_from_metadata(metadata)
        if tags:
            frontmatter["tags"] = tags

        timestamp = _timestamp(model)
        if timestamp:
            frontmatter["timestamp"] = timestamp

    elif isinstance(model, Memory):
        frontmatter = {"type": okf_memory_type(model)}

        title = _memory_title(model)
        if title:
            frontmatter["title"] = title

        tags = [str(t).strip() for t in (model.tags or []) if str(t).strip()] or None
        if tags:
            frontmatter["tags"] = tags

        timestamp = _timestamp(model)
        if timestamp:
            frontmatter["timestamp"] = timestamp

    elif isinstance(model, Chunk):
        frontmatter = {
            "type": okf_chunk_type(),
            "title": f"Chunk {model.position}",
        }

        timestamp = _timestamp(model)
        if timestamp:
            frontmatter["timestamp"] = timestamp

    elif isinstance(model, MemoryRelation):
        frontmatter = {
            "type": okf_relation_type(model),
            "title": f"{okf_relation_type(model)} Relation",
        }

        timestamp = _timestamp(model)
        if timestamp:
            frontmatter["timestamp"] = timestamp

    else:
        raise TypeError(f"Unsupported OKF model type: {type(model)}")

    return frontmatter


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Render a frontmatter mapping as a YAML block delimited by ``---``."""
    body = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return f"{_FRONTMATTER_DELIMITER}\n{body}{_FRONTMATTER_DELIMITER}\n"


def concept_to_markdown(frontmatter: dict[str, Any], body: str) -> str:
    """Serialize an OKF concept from a frontmatter mapping and a markdown body."""
    rendered = render_frontmatter(frontmatter)
    body_text = (body or "").strip("\n")
    return f"{rendered}\n{body_text}\n"


def document_to_concept(document: Document, *, body: str) -> str:
    """Serialize a document as an OKF concept."""
    redacted_metadata = redact_secrets(document.document_metadata or {})
    frontmatter = build_frontmatter(document, redacted_metadata=redacted_metadata)
    return concept_to_markdown(frontmatter, body)


def memory_to_concept(memory: Memory, *, source_path: str | None = None) -> str:
    """Serialize a memory fact as an OKF concept.

    ``source_path`` is the bundle-relative path to the source document, when the
    memory was derived from a document in the same bundle. Run and chat sources
    are rendered as ``run_<uuid>`` and ``chat_<id>`` resources automatically.
    """
    frontmatter = build_frontmatter(memory)
    resource = _memory_resource(memory, source_path=source_path)
    if resource:
        frontmatter["resource"] = resource
    return concept_to_markdown(frontmatter, _memory_body(memory))


def chunk_to_concept(chunk: Chunk, *, document_path: str | None = None) -> str:
    """Serialize a document chunk as an OKF concept."""
    frontmatter = build_frontmatter(chunk)
    if document_path:
        frontmatter["resource"] = document_path
    return concept_to_markdown(frontmatter, chunk.content or "")


def relation_to_concept(
    relation: MemoryRelation,
    *,
    from_path: str | None = None,
    to_path: str | None = None,
) -> str:
    """Serialize a memory relation as an OKF concept."""
    frontmatter = build_frontmatter(relation)
    from_ref = from_path or f".okf/memories/{relation.from_memory_id}.md"
    to_ref = to_path or f".okf/memories/{relation.to_memory_id}.md"
    body = (
        f"**From:** {from_ref}\n"
        f"**To:** {to_ref}\n"
        f"**Type:** {relation.relation_type.value}"
    )
    return concept_to_markdown(frontmatter, body)


def citation_to_concept(
    memory: Memory,
    *,
    source_path: str | None = None,
) -> str:
    """Serialize a memory's provenance as an OKF citation concept."""
    title = source_path or _citation_label(memory) or "Citation"
    frontmatter: dict[str, Any] = {
        "type": okf_citation_type(),
        "title": title,
    }
    if title:
        frontmatter["resource"] = title
    timestamp = _timestamp(memory)
    if timestamp:
        frontmatter["timestamp"] = timestamp
    return concept_to_markdown(frontmatter, _citation_body(memory))


@dataclass(frozen=True)
class ConceptRef:
    """One concept entry for an ``index.md`` listing."""

    title: str
    filename: str  # relative to the directory, e.g. "orders.md"
    type: str  # OKF type, used as the grouping heading
    description: str | None = None


@dataclass(frozen=True)
class SubdirRef:
    """One subdirectory entry for an ``index.md`` listing."""

    name: str  # directory name, e.g. "tables"
    description: str | None = None


@dataclass(frozen=True)
class LogEntry:
    """One line of an OKF ``log.md``: a concept and when it last changed."""

    title: str
    timestamp: str | None = None  # ISO-8601, or None when unknown


def folder_to_log(entries: list[LogEntry]) -> str:
    """Build a minimal OKF ``log.md`` body for one directory.

    Lists each concept newest-first with the time it last changed; undated
    entries sort last. Returns an empty string when there is nothing to log.
    """
    if not entries:
        return ""
    ordered = sorted(
        entries,
        key=lambda e: (e.timestamp is not None, e.timestamp or "", e.title),
        reverse=True,
    )
    lines = ["# Change Log", ""]
    for entry in ordered:
        when = f" - {entry.timestamp}" if entry.timestamp else ""
        lines.append(f"* {entry.title}{when}")
    return "\n".join(lines) + "\n"


def _index_bullet(title: str, link: str, description: str | None) -> str:
    bullet = f"* [{title}]({link})"
    if description:
        # Keep index descriptions to a single line.
        bullet += f" - {' '.join(description.split())}"
    return bullet


def folder_to_index(
    *,
    concepts: list[ConceptRef] | None = None,
    subdirectories: list[SubdirRef] | None = None,
) -> str:
    """Build an OKF ``index.md`` body (no frontmatter) for one directory.

    Subdirectories are listed under a ``# Subdirectories`` heading and concepts
    are grouped under their ``type`` heading, mirroring Google's sample bundles.
    Returns an empty string when there is nothing to list.
    """
    concepts = concepts or []
    subdirectories = subdirectories or []
    sections: list[str] = []

    if subdirectories:
        lines = ["# Subdirectories", ""]
        for sub in sorted(subdirectories, key=lambda s: s.name.lower()):
            lines.append(
                _index_bullet(sub.name, f"{sub.name}/{INDEX_FILENAME}", sub.description)
            )
        sections.append("\n".join(lines))

    by_type: dict[str, list[ConceptRef]] = {}
    for concept in concepts:
        by_type.setdefault(concept.type, []).append(concept)
    for type_heading in sorted(by_type):
        lines = [f"# {type_heading}", ""]
        for concept in sorted(by_type[type_heading], key=lambda c: c.title.lower()):
            lines.append(
                _index_bullet(concept.title, concept.filename, concept.description)
            )
        sections.append("\n".join(lines))

    return ("\n\n".join(sections) + "\n") if sections else ""
