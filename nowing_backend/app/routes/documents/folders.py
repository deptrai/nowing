"""Local folder sync endpoints (desktop app)."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import Document, DocumentType, Permission, get_async_session
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.routes.documents._shared import (
    FolderSyncFinalizeRequest,
    FolderUnlinkRequest,
)
from app.services.folder_service import get_folder_subtree_ids
from app.tasks.connector_indexers.local_folder_indexer import (
    _cleanup_empty_folder_chain,
    _cleanup_empty_folders,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/documents/folder-unlink")
async def folder_unlink(
    request: FolderUnlinkRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Handle file deletion events from the desktop watcher.

    For each relative path, find the matching document and delete it.
    """

    await check_permission(
        session,
        auth,
        request.workspace_id,
        Permission.DOCUMENTS_DELETE.value,
        "You don't have permission to delete documents in this workspace",
    )

    deleted_count = 0

    for rel_path in request.relative_paths:
        unique_id = f"{request.folder_name}:{rel_path}"
        uid_hash = compute_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE.value,
            unique_id,
            request.workspace_id,
        )

        existing = (
            await session.execute(
                select(Document).where(Document.unique_identifier_hash == uid_hash)
            )
        ).scalar_one_or_none()

        if existing:
            deleted_folder_id = existing.folder_id
            await session.delete(existing)
            await session.flush()

            if deleted_folder_id and request.root_folder_id:
                await _cleanup_empty_folder_chain(
                    session, deleted_folder_id, request.root_folder_id
                )
            deleted_count += 1

    await session.commit()
    return {"deleted_count": deleted_count}


@router.post("/documents/folder-sync-finalize")
async def folder_sync_finalize(
    request: FolderSyncFinalizeRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Finalize a full folder scan by deleting orphaned documents.

    The client sends the complete list of relative paths currently in the
    folder. Any document in the DB for this folder that is NOT in the list
    gets deleted.
    """

    await check_permission(
        session,
        auth,
        request.workspace_id,
        Permission.DOCUMENTS_DELETE.value,
        "You don't have permission to delete documents in this workspace",
    )

    if not request.root_folder_id:
        return {"deleted_count": 0}

    subtree_ids = await get_folder_subtree_ids(session, request.root_folder_id)

    seen_hashes: set[str] = set()
    for rel_path in request.all_relative_paths:
        unique_id = f"{request.folder_name}:{rel_path}"
        uid_hash = compute_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE.value,
            unique_id,
            request.workspace_id,
        )
        seen_hashes.add(uid_hash)

    all_folder_docs = (
        (
            await session.execute(
                select(Document).where(
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.workspace_id == request.workspace_id,
                    Document.folder_id.in_(subtree_ids),
                )
            )
        )
        .scalars()
        .all()
    )

    deleted_count = 0
    for doc in all_folder_docs:
        if doc.unique_identifier_hash not in seen_hashes:
            await session.delete(doc)
            deleted_count += 1

    await session.flush()

    existing_dirs: set[str] = set()
    for rel_path in request.all_relative_paths:
        parent = str(os.path.dirname(rel_path))
        if parent and parent != ".":
            existing_dirs.add(parent)

    folder_mapping: dict[str, int] = {"": request.root_folder_id}

    await _cleanup_empty_folders(
        session,
        request.root_folder_id,
        request.workspace_id,
        existing_dirs,
        folder_mapping,
        subtree_ids=subtree_ids,
    )

    await session.commit()
    return {"deleted_count": deleted_count}
