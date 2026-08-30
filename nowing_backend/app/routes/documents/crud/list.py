"""Document CRUD helpers: list."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    Document,
    Folder,
    Permission,
    Workspace,
    WorkspaceMembership,
    get_async_session,
)
from app.routes.documents.crud.router import router
from app.schemas import (
    DocumentRead,
    DocumentStatusBatchResponse,
    DocumentStatusItemRead,
    DocumentStatusSchema,
    FolderRead,
    PaginatedResponse,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


@router.get("/documents", response_model=PaginatedResponse[DocumentRead])
async def read_documents(
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    workspace_id: int | None = None,
    document_types: str | None = None,
    folder_id: int | str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    List documents the user has access to, with optional filtering and pagination.
    Requires DOCUMENTS_READ permission for the workspace(s).

    Args:
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'.
        page: Zero-based page index used when 'skip' is not provided.
        page_size: Number of items per page (default: 50). Use -1 to return all remaining items after the offset.
        workspace_id: If provided, restrict results to a specific workspace.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents visible to the user.

    Notes:
        - If both 'skip' and 'page' are provided, 'skip' is used.
        - Results are scoped to documents in workspaces the user has membership in.
    """
    try:
        from sqlalchemy import func

        # If specific workspace_id, check permission
        if workspace_id is not None:
            await check_permission(
                session,
                auth,
                workspace_id,
                Permission.DOCUMENTS_READ.value,
                "You don't have permission to read documents in this workspace",
            )
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .filter(
                    Document.workspace_id == workspace_id,
                    Document.archived_at.is_(None),
                )
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .filter(
                    Document.workspace_id == workspace_id,
                    Document.archived_at.is_(None),
                )
            )
        else:
            # Get documents from all workspaces user has membership in
            query = (
                select(Document)
                .options(selectinload(Document.created_by))
                .join(Workspace)
                .join(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.user_id == user.id,
                    Document.archived_at.is_(None),
                )
            )
            count_query = (
                select(func.count())
                .select_from(Document)
                .join(Workspace)
                .join(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.user_id == user.id,
                    Document.archived_at.is_(None),
                )
            )

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))
                count_query = count_query.filter(Document.document_type.in_(type_list))

        # Filter by folder_id: "root" or "null" => root level (folder_id IS NULL),
        # integer => specific folder, omitted => all documents
        if folder_id is not None:
            if str(folder_id).lower() in ("root", "null"):
                query = query.filter(Document.folder_id.is_(None))
                count_query = count_query.filter(Document.folder_id.is_(None))
            else:
                fid = int(folder_id)
                query = query.filter(Document.folder_id == fid)
                count_query = count_query.filter(Document.folder_id == fid)

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        from sqlalchemy import asc as sa_asc, desc as sa_desc

        sort_column_map = {
            "created_at": Document.created_at,
            "title": Document.title,
            "document_type": Document.document_type,
        }
        sort_col = sort_column_map.get(sort_by, Document.created_at)
        query = query.order_by(
            sa_desc(sort_col) if sort_order == "desc" else sa_asc(sort_col)
        )

        # Calculate offset
        offset = 0
        if skip is not None:
            offset = skip
        elif page is not None:
            offset = page * page_size

        # Get paginated results
        if page_size == -1:
            result = await session.execute(query.offset(offset))
        else:
            result = await session.execute(query.offset(offset).limit(page_size))

        db_documents = result.scalars().all()

        # Convert database objects to API-friendly format
        api_documents = []
        for doc in db_documents:
            created_by_name = None
            created_by_email = None
            if doc.created_by:
                created_by_name = doc.created_by.display_name
                created_by_email = doc.created_by.email

            # Parse status from JSONB
            status_data = None
            if hasattr(doc, "status") and doc.status:
                status_data = DocumentStatusSchema(
                    state=doc.status.get("state", "ready"),
                    reason=doc.status.get("reason"),
                )

            raw_content = doc.content or ""
            api_documents.append(
                DocumentRead(
                    id=doc.id,
                    title=doc.title,
                    document_type=doc.document_type,
                    document_metadata=doc.document_metadata,
                    content="",
                    content_preview=raw_content[:300],
                    content_hash=doc.content_hash,
                    unique_identifier_hash=doc.unique_identifier_hash,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                    archived_at=doc.archived_at,
                    workspace_id=doc.workspace_id,
                    folder_id=doc.folder_id,
                    created_by_id=doc.created_by_id,
                    created_by_name=created_by_name,
                    created_by_email=created_by_email,
                    status=status_data,
                )
            )

        # Calculate pagination info
        actual_page = (
            page if page is not None else (offset // page_size if page_size > 0 else 0)
        )
        has_more = (offset + len(api_documents)) < total if page_size > 0 else False

        return PaginatedResponse(
            items=api_documents,
            total=total,
            page=actual_page,
            page_size=page_size,
            has_more=has_more,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch documents: {e!s}"
        ) from e


@router.get("/documents/status", response_model=DocumentStatusBatchResponse)
async def get_documents_status(
    workspace_id: int,
    document_ids: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Batch status endpoint for documents in a workspace.

    Returns lightweight status info for the provided document IDs, intended for
    polling async ETL progress in chat upload flows.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        # Parse comma-separated IDs (e.g. "1,2,3")
        parsed_ids = []
        for raw_id in document_ids.split(","):
            value = raw_id.strip()
            if not value:
                continue
            try:
                parsed_ids.append(int(value))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid document id: {value}",
                ) from None

        if not parsed_ids:
            return DocumentStatusBatchResponse(items=[])

        result = await session.execute(
            select(Document).filter(
                Document.workspace_id == workspace_id,
                Document.id.in_(parsed_ids),
            )
        )
        docs = result.scalars().all()

        items = [
            DocumentStatusItemRead(
                id=doc.id,
                title=doc.title,
                document_type=doc.document_type,
                status=DocumentStatusSchema(
                    state=(doc.status or {}).get("state", "ready"),
                    reason=(doc.status or {}).get("reason"),
                ),
            )
            for doc in docs
        ]
        return DocumentStatusBatchResponse(items=items)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document status: {e!s}"
        ) from e


@router.get("/documents/type-counts")
async def get_document_type_counts(
    workspace_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Get counts of documents by type for workspaces the user has access to.
    Requires DOCUMENTS_READ permission for the workspace(s).

    Args:
        workspace_id: If provided, restrict counts to a specific workspace.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        Dict mapping document types to their counts.
    """
    try:
        from sqlalchemy import func

        if workspace_id is not None:
            # Check permission for specific workspace
            await check_permission(
                session,
                auth,
                workspace_id,
                Permission.DOCUMENTS_READ.value,
                "You don't have permission to read documents in this workspace",
            )
            query = (
                select(Document.document_type, func.count(Document.id))
                .filter(
                    Document.workspace_id == workspace_id,
                    Document.archived_at.is_(None),
                )
                .group_by(Document.document_type)
            )
        else:
            # Get counts from all workspaces user has membership in
            query = (
                select(Document.document_type, func.count(Document.id))
                .join(Workspace)
                .join(WorkspaceMembership)
                .filter(
                    WorkspaceMembership.user_id == user.id,
                    Document.archived_at.is_(None),
                )
                .group_by(Document.document_type)
            )

        result = await session.execute(query)
        type_counts = dict(result.all())

        return type_counts
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document type counts: {e!s}"
        ) from e


@router.get("/documents/watched-folders", response_model=list[FolderRead])
async def get_watched_folders(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Return root folders that are marked as watched (metadata->>'watched' = 'true')."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )

    folders = (
        (
            await session.execute(
                select(Folder).where(
                    Folder.workspace_id == workspace_id,
                    Folder.parent_id.is_(None),
                    Folder.folder_metadata.isnot(None),
                    Folder.folder_metadata["watched"].astext == "true",
                )
            )
        )
        .scalars()
        .all()
    )

    return folders

__all__ = ['get_document_type_counts', 'get_documents_status', 'get_watched_folders', 'read_documents']
