"""Document CRUD helpers: search."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope
from app.auth.context import AuthContext
from app.db import (
    Document,
    Permission,
    Workspace,
    WorkspaceMembership,
    get_async_session,
)
from app.routes.documents._shared import (
    SemanticSearchChunk,
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.routes.documents.crud.router import router
from app.schemas import (
    DocumentRead,
    DocumentStatusSchema,
    DocumentTitleRead,
    DocumentTitleSearchResponse,
    PaginatedResponse,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)


@router.get("/documents/search", response_model=PaginatedResponse[DocumentRead])
async def search_documents(
    title: str,
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    workspace_id: int | None = None,
    document_types: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Search documents by title substring, optionally filtered by workspace_id and document_types.
    Requires DOCUMENTS_READ permission for the workspace(s).

    Args:
        title: Case-insensitive substring to match against document titles. Required.
        skip: Absolute number of items to skip from the beginning. If provided, it takes precedence over 'page'. Default: None.
        page: Zero-based page index used when 'skip' is not provided. Default: None.
        page_size: Number of items per page. Use -1 to return all remaining items after the offset. Default: 50.
        workspace_id: Filter results to a specific workspace. Default: None.
        document_types: Comma-separated list of document types to filter by (e.g., "EXTENSION,FILE,SLACK_CONNECTOR").
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        PaginatedResponse[DocumentRead]: Paginated list of documents matching the query and filter.

    Notes:
        - Title matching uses ILIKE (case-insensitive).
        - If both 'skip' and 'page' are provided, 'skip' is used.
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

        # Only search by title (case-insensitive)
        query = query.filter(Document.title.ilike(f"%{title}%"))
        count_query = count_query.filter(Document.title.ilike(f"%{title}%"))

        # Filter by document_types if provided
        if document_types is not None and document_types.strip():
            type_list = [t.strip() for t in document_types.split(",") if t.strip()]
            if type_list:
                query = query.filter(Document.document_type.in_(type_list))
                count_query = count_query.filter(Document.document_type.in_(type_list))

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

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
            status_code=500, detail=f"Failed to search documents: {e!s}"
        ) from e


@router.post("/documents/search-semantic", response_model=SemanticSearchResponse)
async def search_documents_semantic(
    request: SemanticSearchRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Hybrid semantic + keyword search over a workspace's knowledge base.

    Thin REST door onto the same retriever the chat agent uses: returns the most
    relevant documents with their matching passages, ranked by relevance.
    Requires DOCUMENTS_READ permission for the workspace.
    """
    # Local import: the retriever pulls in the embedding model + agent stack,
    # so keep it out of module import (mirrors the celery-task imports here).

    await check_permission(
        session,
        auth,
        request.workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )

    scope = SearchScope(
        document_types=tuple(request.document_types)
        if request.document_types
        else None,
    )
    try:
        hits = await search_chunks(
            session,
            workspace_id=request.workspace_id,
            query=request.query,
            scope=scope,
            top_k=request.top_k,
        )
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Semantic search failed: {e!s}"
        ) from e

    return SemanticSearchResponse(
        items=[
            SemanticSearchHit(
                document_id=hit.document_id,
                title=hit.title,
                document_type=hit.document_type,
                score=hit.score,
                chunks=[
                    SemanticSearchChunk(
                        content=chunk.content,
                        position=chunk.position,
                        score=chunk.score,
                    )
                    for chunk in hit.chunks
                ],
            )
            for hit in hits
        ]
    )


@router.get("/documents/search/titles", response_model=DocumentTitleSearchResponse)
async def search_document_titles(
    workspace_id: int,
    title: str = "",
    page: int = 0,
    page_size: int = 20,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """
    Lightweight document title search optimized for mention picker (@mentions).

    Returns only id, title, and document_type - no content or metadata.
    Uses pg_trgm fuzzy search with similarity scoring for typo tolerance.
    Results are ordered by relevance using trigram similarity scores.

    Args:
        workspace_id: The workspace to search in. Required.
        title: Search query (case-insensitive). If empty or < 2 chars, returns recent documents.
        page: Zero-based page index. Default: 0.
        page_size: Number of items per page. Default: 20.
        session: Database session (injected).
        user: Current authenticated user (injected).

    Returns:
        DocumentTitleSearchResponse: Lightweight list with has_more flag (no total count).
    """
    from sqlalchemy import desc, or_

    try:
        # Check permission for the workspace
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.DOCUMENTS_READ.value,
            "You don't have permission to read documents in this workspace",
        )

        # Base query - only select lightweight fields
        query = select(
            Document.id,
            Document.title,
            Document.document_type,
        ).filter(
            Document.workspace_id == workspace_id,
            Document.archived_at.is_(None),
        )

        # If query is too short, return recent documents ordered by updated_at
        if len(title.strip()) < 2:
            query = query.order_by(Document.updated_at.desc().nullslast())
        else:
            # Fuzzy search using pg_trgm similarity + ILIKE fallback
            search_term = title.strip()

            # Similarity threshold for fuzzy matching (0.3 = ~30% trigram overlap)
            # Lower values = more fuzzy, higher values = stricter matching
            similarity_threshold = 0.3

            # Match documents that either:
            # 1. Have high trigram similarity (fuzzy match - handles typos)
            # 2. Contain the exact substring (ILIKE - handles partial matches)
            query = query.filter(
                or_(
                    func.similarity(Document.title, search_term) > similarity_threshold,
                    Document.title.ilike(f"%{search_term}%"),
                )
            )

            # Order by similarity score (descending) for best relevance ranking
            # Higher similarity = better match = appears first
            query = query.order_by(
                desc(func.similarity(Document.title, search_term)),
                Document.title,  # Alphabetical tiebreaker
            )

        # Fetch page_size + 1 to determine has_more without COUNT query
        offset = page * page_size
        result = await session.execute(query.offset(offset).limit(page_size + 1))
        rows = result.all()

        # Check if there are more results
        has_more = len(rows) > page_size
        items = rows[:page_size]  # Only return requested page_size

        # Convert to response format
        api_documents = [
            DocumentTitleRead(
                id=row.id,
                title=row.title,
                document_type=row.document_type,
            )
            for row in items
        ]

        return DocumentTitleSearchResponse(
            items=api_documents,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to search document titles: {e!s}"
        ) from e

__all__ = ['search_document_titles', 'search_documents', 'search_documents_semantic']
