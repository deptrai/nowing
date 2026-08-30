"""Document CRUD helpers: read."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
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
)
from app.services.export_service import resolve_document_markdown
from app.services.okf import document_to_concept
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Get a specific document by ID.

    ``Accept: application/json`` returns the JSON record (default).
    ``Accept: text/markdown`` returns the OKF concept.
    Requires DOCUMENTS_READ permission for the workspace.
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

        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            document.workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        # ponytail: substring match, not RFC 7231 q-values (OKF is the only non-JSON view).
        if "text/markdown" in request.headers.get("accept", ""):
            body = (
                await resolve_document_markdown(session, document)
                or document.content
                or ""
            )
            concept = document_to_concept(document, body=body)
            return PlainTextResponse(concept, media_type="text/markdown")

        raw_content = document.content or ""
        return DocumentRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata,
            content=raw_content,
            content_preview=raw_content[:300],
            content_hash=document.content_hash,
            unique_identifier_hash=document.unique_identifier_hash,
            created_at=document.created_at,
            updated_at=document.updated_at,
            archived_at=document.archived_at,
            workspace_id=document.workspace_id,
            folder_id=document.folder_id,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document: {e!s}"
        ) from e

__all__ = ['read_document']
