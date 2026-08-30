"""Google Drive ConnectorDocument construction and placeholder creation."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)


def _build_connector_doc(
    file: dict,
    markdown: str,
    drive_metadata: dict,
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
) -> ConnectorDocument:
    """Build a ConnectorDocument from Drive file metadata + extracted markdown."""
    file_id = file.get("id", "")
    file_name = file.get("name", "Unknown")

    metadata = {
        **drive_metadata,
        "connector_id": connector_id,
        "document_type": "Google Drive File",
        "connector_type": "Google Drive",
    }

    return ConnectorDocument(
        title=file_name,
        source_markdown=markdown,
        unique_id=file_id,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        workspace_id=workspace_id,
        connector_id=connector_id,
        created_by_id=user_id,
        metadata=metadata,
    )


async def _create_drive_placeholders(
    session: AsyncSession,
    files: list[dict],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
) -> None:
    """Create placeholder document rows for discovered Drive files.

    Called immediately after file discovery (Phase 1) so documents appear
    in the UI via Zero sync before the slow download/ETL phase begins.
    """
    if not files:
        return

    placeholders = []
    for file in files:
        file_id = file.get("id")
        file_name = file.get("name", "Unknown")
        if not file_id:
            continue
        placeholders.append(
            PlaceholderInfo(
                title=file_name,
                document_type=DocumentType.GOOGLE_DRIVE_FILE,
                unique_id=file_id,
                workspace_id=workspace_id,
                connector_id=connector_id,
                created_by_id=user_id,
                metadata={
                    "google_drive_file_id": file_id,
                    "FILE_NAME": file_name,
                    "connector_id": connector_id,
                    "connector_type": "Google Drive",
                },
            )
        )

    if placeholders:
        pipeline = IndexingPipelineService(session)
        await pipeline.create_placeholder_documents(placeholders)
