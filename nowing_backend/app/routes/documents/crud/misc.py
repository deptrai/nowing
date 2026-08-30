"""Document CRUD helpers: misc."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.chat.runtime.path_resolver import virtual_path_to_doc
from app.auth.context import AuthContext
from app.db import (
    Chunk,
    Document,
    Permission,
    get_async_session,
)
from app.routes.documents.crud.router import router
from app.schemas import (
    ChunkRead,
    DocumentTitleRead,
    DocumentWithChunksRead,
    PaginatedResponse,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


@router.get("/documents/by-virtual-path", response_model=DocumentTitleRead)
async def get_document_by_virtual_path(
    workspace_id: int,
    virtual_path: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Resolve a knowledge-base document by its agent-facing virtual path.

    The agent renders every document under ``/documents/...`` with a
    ``.xml`` extension appended via ``safe_filename`` (so a PDF titled
    ``2025-W2.pdf`` becomes ``/documents/2025-W2.pdf.xml``). When the user
    clicks that path in an answer, this endpoint must round-trip back to
    the underlying ``Document`` row regardless of its type — agent-created
    NOTE docs (which carry ``virtual_path`` in metadata), uploaded PDFs,
    and connector docs all flow through here.

    Resolution is delegated to :func:`virtual_path_to_doc`, the single
    source of truth that handles:

    * ``unique_identifier_hash`` lookup (agent NOTE fast path)
    * ``" (<doc_id>).xml"`` disambiguation suffixes
    * ``.xml`` extension stripping for title-based fallback
    * ``safe_filename`` round-trip for connector titles with lossy chars
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        document = await virtual_path_to_doc(
            session,
            workspace_id=workspace_id,
            virtual_path=virtual_path,
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentTitleRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            folder_id=document.folder_id,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve document by virtual path: {e!s}",
        ) from e


@router.get("/documents/by-chunk/{chunk_id}", response_model=DocumentWithChunksRead)
async def get_document_by_chunk_id(
    chunk_id: int,
    chunk_window: int = Query(
        5, ge=0, description="Number of chunks before/after the cited chunk to include"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Retrieves a document based on a chunk ID, including a window of chunks around the cited one.
    Uses SQL-level pagination to avoid loading all chunks into memory.
    """
    try:
        from sqlalchemy import and_, func, or_

        chunk_result = await session.execute(select(Chunk).filter(Chunk.id == chunk_id))
        chunk = chunk_result.scalars().first()

        if not chunk:
            raise HTTPException(
                status_code=404, detail=f"Chunk with id {chunk_id} not found"
            )

        document_result = await session.execute(
            select(Document).filter(
                Document.id == chunk.document_id,
                Document.archived_at.is_(None),
            )
        )
        document = document_result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        await check_permission(
            session,
            auth,
            document.workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        total_result = await session.execute(
            select(func.count())
            .select_from(Chunk)
            .filter(Chunk.document_id == document.id)
        )
        total_chunks = total_result.scalar() or 0

        cited_idx_result = await session.execute(
            select(func.count())
            .select_from(Chunk)
            .filter(
                Chunk.document_id == document.id,
                or_(
                    Chunk.position < chunk.position,
                    and_(Chunk.position == chunk.position, Chunk.id < chunk.id),
                ),
            )
        )
        cited_idx = cited_idx_result.scalar() or 0

        start = max(0, cited_idx - chunk_window)
        end = min(total_chunks, cited_idx + chunk_window + 1)

        windowed_result = await session.execute(
            select(Chunk)
            .filter(Chunk.document_id == document.id)
            .order_by(Chunk.position, Chunk.id)
            .offset(start)
            .limit(end - start)
        )
        windowed_chunks = windowed_result.scalars().all()

        return DocumentWithChunksRead(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            document_metadata=document.document_metadata or {},
            content=document.content,
            content_hash=document.content_hash,
            unique_identifier_hash=document.unique_identifier_hash,
            created_at=document.created_at,
            updated_at=document.updated_at,
            archived_at=document.archived_at,
            workspace_id=document.workspace_id,
            chunks=windowed_chunks,
            total_chunks=total_chunks,
            chunk_start_index=start,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document: {e!s}"
        ) from e


@router.get(
    "/documents/{document_id}/chunks",
    response_model=PaginatedResponse[ChunkRead],
)
async def get_document_chunks_paginated(
    document_id: int,
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    start_offset: int | None = Query(
        None, ge=0, description="Direct offset; overrides page * page_size"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Paginated chunk loading for a document.
    Supports both page-based and offset-based access.
    """
    try:
        from sqlalchemy import func

        doc_result = await session.execute(
            select(Document).filter(
                Document.id == document_id,
                Document.archived_at.is_(None),
            )
        )
        document = doc_result.scalars().first()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        await check_permission(
            session,
            auth,
            document.workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        total_result = await session.execute(
            select(func.count())
            .select_from(Chunk)
            .filter(Chunk.document_id == document_id)
        )
        total = total_result.scalar() or 0

        offset = start_offset if start_offset is not None else page * page_size
        chunks_result = await session.execute(
            select(Chunk)
            .filter(Chunk.document_id == document_id)
            .order_by(Chunk.position, Chunk.id)
            .offset(offset)
            .limit(page_size)
        )
        chunks = chunks_result.scalars().all()

        return PaginatedResponse(
            items=chunks,
            total=total,
            page=offset // page_size if page_size else page,
            page_size=page_size,
            has_more=(offset + len(chunks)) < total,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch chunks: {e!s}"
        ) from e

__all__ = ['get_document_by_chunk_id', 'get_document_by_virtual_path', 'get_document_chunks_paginated']
