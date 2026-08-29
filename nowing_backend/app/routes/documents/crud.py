"""Document CRUD, search, and status endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.chat.multi_agent_chat.shared.retrieval.hybrid_search import (
    search_chunks,
)
from app.agents.chat.multi_agent_chat.shared.retrieval.models import SearchScope
from app.agents.chat.runtime.path_resolver import virtual_path_to_doc
from app.auth.context import AuthContext
from app.db import (
    Chunk,
    Document,
    Folder,
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
from app.schemas import (
    ChunkRead,
    DocumentRead,
    DocumentStatusBatchResponse,
    DocumentStatusItemRead,
    DocumentStatusSchema,
    DocumentTitleRead,
    DocumentTitleSearchResponse,
    DocumentUpdate,
    DocumentWithChunksRead,
    FolderRead,
    PaginatedResponse,
)
from app.services.export_service import resolve_document_markdown
from app.services.okf import document_to_concept
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

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


# ====================================================================
