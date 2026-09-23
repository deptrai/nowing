"""Local folder connector document builder."""

from __future__ import annotations

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument


def _build_connector_doc(
    title: str,
    content: str,
    relative_path: str,
    folder_name: str,
    *,
    workspace_id: int,
    user_id: str,
) -> ConnectorDocument:
    """Build a ConnectorDocument from a local file's extracted content."""
    unique_id = f"{folder_name}:{relative_path}"
    metadata = {
        "folder_name": folder_name,
        "file_path": relative_path,
        "document_type": "Local Folder File",
        "connector_type": "Local Folder",
    }

    return ConnectorDocument(
        title=title,
        source_markdown=content,
        unique_id=unique_id,
        document_type=DocumentType.LOCAL_FOLDER_FILE,
        workspace_id=workspace_id,
        connector_id=None,
        created_by_id=user_id,
        metadata=metadata,
    )
