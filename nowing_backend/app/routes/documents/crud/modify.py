"""Document CRUD helpers: modify."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Document,
    Permission,
    get_async_session,
)
from app.routes.documents.crud.router import router
from app.schemas import (
    DocumentRead,
    DocumentUpdate,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


@router.put("/documents/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Update a document.
    Requires DOCUMENTS_UPDATE permission for the workspace.
    """
    try:
        result = await session.execute(
            select(Document).filter(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
        db_document = result.scalars().first()

        if not db_document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            db_document.workspace_id,
            Permission.DOCUMENTS_UPDATE.value,
            "You don't have permission to update documents in this workspace",
        )

        update_data = document_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_document, key, value)
        await session.commit()
        await session.refresh(db_document)

        # Convert to DocumentRead for response
        return DocumentRead(
            id=db_document.id,
            title=db_document.title,
            document_type=db_document.document_type,
            document_metadata=db_document.document_metadata,
            content=db_document.content,
            content_hash=db_document.content_hash,
            unique_identifier_hash=db_document.unique_identifier_hash,
            created_at=db_document.created_at,
            updated_at=db_document.updated_at,
            workspace_id=db_document.workspace_id,
            folder_id=db_document.folder_id,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update document: {e!s}"
        ) from e


@router.delete("/documents/{document_id}", response_model=dict)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Delete a document.
    Requires DOCUMENTS_DELETE permission for the workspace.
    Documents in "processing" state cannot be deleted.

    Heavy cascade deletion runs asynchronously via Celery so the API
    response is fast and the deletion remains durable across API restarts.
    """
    try:
        result = await session.execute(
            select(Document).filter(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with id {document_id} not found"
            )

        doc_state = document.status.get("state") if document.status else None
        if doc_state in ("pending", "processing"):
            raise HTTPException(
                status_code=409,
                detail="Cannot delete document while it is pending or being processed. Please wait for processing to complete.",
            )
        if doc_state == "deleting":
            raise HTTPException(
                status_code=409,
                detail="Document is already being deleted.",
            )

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            document.workspace_id,
            Permission.DOCUMENTS_DELETE.value,
            "You don't have permission to delete documents in this workspace",
        )

        # Mark the document as "deleting" so it's excluded from searches,
        # then commit immediately so the user gets a fast response.
        document.status = {"state": "deleting"}
        await session.commit()

        # Dispatch durable background deletion via Celery.
        # If queue dispatch fails, revert status to avoid a stuck "deleting" document.
        try:
            from app.tasks.celery_tasks.document_tasks import delete_document_task

            delete_document_task.delay(document_id)
        except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as dispatch_error:
            document.status = {"state": "ready"}
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail="Failed to queue background deletion. Please try again.",
            ) from dispatch_error

        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document: {e!s}"
        ) from e

__all__ = ['delete_document', 'update_document']
