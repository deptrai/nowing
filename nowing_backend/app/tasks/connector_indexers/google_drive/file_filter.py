"""Google Drive file filtering and legacy document removal."""

from __future__ import annotations

import logging

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.google_drive.file_types import (
    is_google_workspace_file,
    should_skip_by_extension,
    should_skip_file as skip_mime,
)
from app.db import Document, DocumentStatus, DocumentType
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.tasks.connector_indexers.base import check_document_by_unique_identifier

logger = logging.getLogger(__name__)


async def _should_skip_file(
    session: AsyncSession,
    file: dict,
    workspace_id: int,
) -> tuple[bool, str | None]:
    """Pre-filter: detect unchanged / rename-only files.

    Returns (should_skip, message).
    Side-effects: migrates legacy Composio hashes, updates renames in-place.
    """
    file_id = file.get("id")
    file_name = file.get("name", "Unknown")
    mime_type = file.get("mimeType", "")

    if skip_mime(mime_type):
        return True, "folder/shortcut"
    if not is_google_workspace_file(mime_type):
        ext_skip, unsup_ext = should_skip_by_extension(file_name)
        if ext_skip:
            return True, f"unsupported:{unsup_ext}"
    if not file_id:
        return True, "missing file_id"

    # --- locate existing document ---
    primary_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, workspace_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        legacy_hash = compute_identifier_hash(
            DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR.value, file_id, workspace_id
        )
        existing = await check_document_by_unique_identifier(session, legacy_hash)
        if existing:
            existing.unique_identifier_hash = primary_hash
            if existing.document_type == DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR:
                existing.document_type = DocumentType.GOOGLE_DRIVE_FILE
            logger.info(f"Migrated legacy Composio Drive document: {file_id}")

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.document_type.in_(
                    [
                        DocumentType.GOOGLE_DRIVE_FILE,
                        DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
                    ]
                ),
                cast(Document.document_metadata["google_drive_file_id"], String)
                == file_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.unique_identifier_hash = primary_hash
            if existing.document_type == DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR:
                existing.document_type = DocumentType.GOOGLE_DRIVE_FILE
            logger.debug(f"Found legacy doc by metadata for file_id: {file_id}")

    if not existing:
        return False, None

    # --- content-change check via md5 / modifiedTime ---
    incoming_md5 = file.get("md5Checksum")
    incoming_mtime = file.get("modifiedTime")
    meta = existing.document_metadata or {}
    stored_md5 = meta.get("md5_checksum")
    stored_mtime = meta.get("modified_time")

    content_unchanged = False
    if incoming_md5 and stored_md5:
        content_unchanged = incoming_md5 == stored_md5
    elif incoming_md5 and not stored_md5:
        return False, None
    elif not incoming_md5 and incoming_mtime and stored_mtime:
        content_unchanged = incoming_mtime == stored_mtime
    elif not incoming_md5:
        return False, None

    if not content_unchanged:
        return False, None

    # --- rename-only detection ---
    old_name = meta.get("FILE_NAME") or meta.get("google_drive_file_name")
    if old_name and old_name != file_name:
        existing.title = file_name
        if not existing.document_metadata:
            existing.document_metadata = {}
        existing.document_metadata["FILE_NAME"] = file_name
        existing.document_metadata["google_drive_file_name"] = file_name
        if incoming_mtime:
            existing.document_metadata["modified_time"] = incoming_mtime
        flag_modified(existing, "document_metadata")
        await session.commit()
        logger.info(f"Rename-only update: '{old_name}' → '{file_name}'")
        return True, f"File renamed: '{old_name}' → '{file_name}'"

    state = DocumentStatus.get_state(existing.status)
    if state in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        # Stuck placeholder/in-progress doc (e.g. worker died mid-index): re-index
        # instead of skipping, otherwise it never recovers.
        return False, None
    if state != DocumentStatus.READY:
        return True, "skipped (previously failed)"
    return True, "unchanged"


async def _remove_document(session: AsyncSession, file_id: str, workspace_id: int):
    """Remove a document that was deleted in Drive."""
    primary_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, workspace_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        legacy_hash = compute_identifier_hash(
            DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR.value, file_id, workspace_id
        )
        existing = await check_document_by_unique_identifier(session, legacy_hash)

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.document_type.in_(
                    [
                        DocumentType.GOOGLE_DRIVE_FILE,
                        DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
                    ]
                ),
                cast(Document.document_metadata["google_drive_file_id"], String)
                == file_id,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        await session.delete(existing)
        logger.info(f"Removed deleted file document: {file_id}")
