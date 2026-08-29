"""Document version history endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import Document, DocumentVersion, Permission, get_async_session
from app.tasks.celery_tasks.document_reindex_tasks import reindex_document_task
from app.users import get_auth_context
from app.utils.document_versioning import create_version_snapshot
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

# Version History Endpoints
# ====================================================================


@router.get("/documents/{document_id}/versions")
async def list_document_versions(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """List all versions for a document, ordered by version_number descending."""
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    await check_permission(
        session, user, document.workspace_id, Permission.DOCUMENTS_READ.value
    )

    versions = (
        (
            await session.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version_number.desc())
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "version_number": v.version_number,
            "title": v.title,
            "content_hash": v.content_hash,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/documents/{document_id}/versions/{version_number}")
async def get_document_version(
    document_id: int,
    version_number: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Get full version content including source_markdown."""
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    await check_permission(
        session, user, document.workspace_id, Permission.DOCUMENTS_READ.value
    )

    version = (
        await session.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number,
            )
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "version_number": version.version_number,
        "title": version.title,
        "content_hash": version.content_hash,
        "source_markdown": version.source_markdown,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


@router.post("/documents/{document_id}/versions/{version_number}/restore")
async def restore_document_version(
    document_id: int,
    version_number: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Restore a previous version: snapshot current state, then overwrite document content."""
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    await check_permission(
        session, user, document.workspace_id, Permission.DOCUMENTS_UPDATE.value
    )

    version = (
        await session.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number,
            )
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Snapshot current state before restoring

    await create_version_snapshot(session, document)

    # Restore the version's content onto the document
    document.source_markdown = version.source_markdown
    document.title = version.title or document.title
    document.content_needs_reindexing = True
    await session.commit()


    reindex_document_task.delay(document_id, str(user.id))

    return {
        "message": f"Restored version {version_number}",
        "document_id": document_id,
        "restored_version": version_number,
    }


