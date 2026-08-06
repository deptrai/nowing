"""Map Nowing document and memory types to OKF concept ``type`` strings and ``resource`` URIs.

OKF (Open Knowledge Format) requires a non-empty, human-friendly ``type`` on
every concept and recommends a ``resource`` URI pointing at the underlying asset.
Nowing stores document types as a :class:`~app.db.DocumentType` enum, memory types
as :class:`~app.db.MemoryType`, relation types as :class:`~app.db.MemoryRelationType`,
and the source URL (when one exists) inside free-form ``document_metadata`` JSON.
This module is the single place that knows those mappings.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.db import DocumentType, MemoryRelationType, MemoryType

if TYPE_CHECKING:
    pass


OKF_TYPE_BY_DOCUMENT_TYPE: dict[DocumentType, str] = {
    DocumentType.EXTENSION: "Web Page",
    DocumentType.CRAWLED_URL: "Web Page",
    DocumentType.FILE: "File",
    DocumentType.SLACK_CONNECTOR: "Slack Message",
    DocumentType.TEAMS_CONNECTOR: "Teams Message",
    DocumentType.ONEDRIVE_FILE: "OneDrive File",
    DocumentType.NOTION_CONNECTOR: "Notion Page",
    DocumentType.YOUTUBE_VIDEO: "YouTube Video",
    DocumentType.GITHUB_CONNECTOR: "GitHub Document",
    DocumentType.LINEAR_CONNECTOR: "Linear Issue",
    DocumentType.DISCORD_CONNECTOR: "Discord Message",
    DocumentType.JIRA_CONNECTOR: "Jira Issue",
    DocumentType.CONFLUENCE_CONNECTOR: "Confluence Page",
    DocumentType.CLICKUP_CONNECTOR: "ClickUp Task",
    DocumentType.GOOGLE_CALENDAR_CONNECTOR: "Google Calendar Event",
    DocumentType.GOOGLE_GMAIL_CONNECTOR: "Gmail Message",
    DocumentType.GOOGLE_DRIVE_FILE: "Google Drive File",
    DocumentType.AIRTABLE_CONNECTOR: "Airtable Record",
    DocumentType.LUMA_CONNECTOR: "Luma Event",
    DocumentType.ELASTICSEARCH_CONNECTOR: "Elasticsearch Document",
    DocumentType.BOOKSTACK_CONNECTOR: "BookStack Page",
    DocumentType.CIRCLEBACK: "Circleback Meeting",
    DocumentType.OBSIDIAN_CONNECTOR: "Obsidian Note",
    DocumentType.NOTE: "Note",
    DocumentType.DROPBOX_FILE: "Dropbox File",
    DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Google Drive File",
    DocumentType.COMPOSIO_GMAIL_CONNECTOR: "Gmail Message",
    DocumentType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Google Calendar Event",
    DocumentType.LOCAL_FOLDER_FILE: "File",
}


def _coerce_document_type(
    document_type: DocumentType | str | None,
) -> DocumentType | None:
    if document_type is None:
        return None
    try:
        return DocumentType(document_type)
    except ValueError:
        return None


def okf_type(document_type: DocumentType | str | None) -> str:
    """Return the OKF ``type`` string for a Nowing document type.

    Falls back to a Title-Cased version of the enum value so the required
    ``type`` field is never empty, even for types added after this map.
    """
    dt = _coerce_document_type(document_type)
    if dt is None:
        if document_type is None:
            return "Document"
        return str(document_type).replace("_", " ").title() or "Document"
    return OKF_TYPE_BY_DOCUMENT_TYPE.get(dt) or dt.value.replace("_", " ").title()


# Per-type metadata keys that hold the canonical source URL, checked first.
_RESOURCE_KEYS_BY_TYPE: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.GOOGLE_DRIVE_FILE: ("webViewLink", "web_view_link"),
    DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: ("webViewLink", "web_view_link"),
    DocumentType.GITHUB_CONNECTOR: ("html_url", "url"),
    DocumentType.NOTION_CONNECTOR: ("url",),
    DocumentType.LINEAR_CONNECTOR: ("url",),
    DocumentType.JIRA_CONNECTOR: ("url",),
    DocumentType.CONFLUENCE_CONNECTOR: ("url",),
    DocumentType.SLACK_CONNECTOR: ("permalink", "url"),
    DocumentType.DISCORD_CONNECTOR: ("url",),
    DocumentType.CLICKUP_CONNECTOR: ("url",),
    DocumentType.YOUTUBE_VIDEO: ("url", "video_url"),
    DocumentType.LUMA_CONNECTOR: ("url",),
    DocumentType.BOOKSTACK_CONNECTOR: ("url",),
    DocumentType.OBSIDIAN_CONNECTOR: ("url",),
    DocumentType.CRAWLED_URL: ("url",),
    DocumentType.EXTENSION: ("VisitedWebPageURL", "url"),
}

# Generic URL-bearing keys checked for any type as a fallback.
_GENERIC_RESOURCE_KEYS: tuple[str, ...] = (
    "url",
    "URL",
    "source_url",
    "sourceUrl",
    "source",
    "link",
    "permalink",
    "web_url",
    "webViewLink",
    "html_url",
)


def okf_resource(
    document_type: DocumentType | str | None, metadata: dict[str, Any] | None
) -> str | None:
    """Return the canonical source URI for a document, or ``None`` if it has none."""
    if not isinstance(metadata, dict) or not metadata:
        return None

    dt = _coerce_document_type(document_type)
    type_keys = _RESOURCE_KEYS_BY_TYPE.get(dt, ()) if dt is not None else ()

    for key in (*type_keys, *_GENERIC_RESOURCE_KEYS):
        value = metadata.get(key)
        if isinstance(value, str):
            candidate = value.strip()
            if candidate.startswith(("http://", "https://")):
                return candidate
    return None


def _title_case(value: str | None) -> str:
    return str(value).replace("_", " ").title() if value else ""


def okf_memory_type(memory_type: MemoryType | str | None) -> str:
    """Return the OKF ``type`` string for a memory fact."""
    if isinstance(memory_type, MemoryType):
        return _title_case(memory_type.value) or "Memory"
    if isinstance(memory_type, str):
        try:
            return _title_case(MemoryType(memory_type).value) or "Memory"
        except ValueError:
            return memory_type.replace("_", " ").title() or "Memory"
    if memory_type is None:
        return "Memory"
    # Memory instance
    return okf_memory_type(memory_type.type)


def okf_relation_type(relation_type: MemoryRelationType | str | None) -> str:
    """Return the OKF ``type`` string for a memory relation."""
    if isinstance(relation_type, MemoryRelationType):
        return _title_case(relation_type.value) or "Relation"
    if isinstance(relation_type, str):
        try:
            return _title_case(MemoryRelationType(relation_type).value) or "Relation"
        except ValueError:
            return relation_type.replace("_", " ").title() or "Relation"
    if relation_type is None:
        return "Relation"
    # MemoryRelation instance
    return okf_relation_type(relation_type.relation_type)


def okf_chunk_type() -> str:
    """Return the OKF ``type`` string for a document chunk."""
    return "Chunk"


def okf_citation_type() -> str:
    """Return the OKF ``type`` string for a provenance citation."""
    return "Citation"
