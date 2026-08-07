"""REST endpoints for canonical entity merge history, conflict resolution and revert."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.canonical.services.canonical_persist_service import (
    ConcurrentUpdateError,
    RevertNotPossibleError,
    resolve_canonical_conflict,
    revert_canonical_entity,
)
from app.canonical.services.unified_search_service import UnifiedSearchService
from app.canonical.tenant_context import set_canonical_workspace_id
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalMergeHistory,
    DocumentType,
    Permission,
    get_async_session,
)
from app.schemas.documents import PaginatedResponse
from app.users import require_session_context
from app.utils.rbac import check_permission

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CanonicalEntitySourceRead(BaseModel):
    id: uuid.UUID
    source_name: str
    source_record_id: str
    source_url: str | None
    source_snapshot: dict[str, Any] | None = None
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CanonicalMergeHistoryRead(BaseModel):
    id: uuid.UUID
    previous_version: int
    new_version: int
    previous_data: dict[str, Any]
    new_data: dict[str, Any]
    previous_source_ids: list[dict[str, Any]]
    new_source_ids: list[dict[str, Any]]
    operation: str
    actor: str | None
    conflicts: list[dict[str, Any]]
    method: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CanonicalEntityRead(BaseModel):
    id: uuid.UUID
    workspace_id: int
    entity_type: str
    canonical_title: str | None
    canonical_data: dict[str, Any]
    fingerprint: str
    search_text: str | None
    source_count: int
    confidence_score: float
    conflict_flags: list[dict[str, Any]]
    version: int
    first_seen_at: datetime
    last_seen_at: datetime
    embedding_status: str
    sources: list[CanonicalEntitySourceRead] = []
    latest_history: CanonicalMergeHistoryRead | None = None

    model_config = ConfigDict(from_attributes=True)


class CanonicalEntityListItem(BaseModel):
    id: uuid.UUID
    workspace_id: int
    entity_type: str
    canonical_title: str | None
    source_count: int
    confidence_score: float
    conflict_flags: list[dict[str, Any]]
    version: int
    last_seen_at: datetime
    embedding_status: str

    model_config = ConfigDict(from_attributes=True)


class RevertRequest(BaseModel):
    history_id: uuid.UUID


class ResolveConflictRequest(BaseModel):
    field: str
    value: Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_history(history: CanonicalMergeHistory) -> CanonicalMergeHistoryRead:
    return CanonicalMergeHistoryRead.model_validate(history)


def _map_source(source: CanonicalEntitySource) -> CanonicalEntitySourceRead:
    return CanonicalEntitySourceRead.model_validate(source)


def _build_entity_read(
    entity: CanonicalEntity, latest: CanonicalMergeHistory | None
) -> CanonicalEntityRead:
    """ponytail: explicit construction is smaller than fighting Pydantic
    to ignore the loaded ORM relationships while still overriding them."""
    return CanonicalEntityRead(
        id=entity.id,
        workspace_id=entity.workspace_id,
        entity_type=entity.entity_type,
        canonical_title=entity.canonical_title,
        canonical_data=entity.canonical_data,
        fingerprint=entity.fingerprint,
        search_text=entity.search_text,
        source_count=entity.source_count,
        confidence_score=entity.confidence_score,
        conflict_flags=entity.conflict_flags,
        version=entity.version,
        first_seen_at=entity.first_seen_at,
        last_seen_at=entity.last_seen_at,
        embedding_status=entity.embedding_status,
        sources=[_map_source(s) for s in entity.sources],
        latest_history=_map_history(latest) if latest else None,
    )


async def _load_entity_with_sources_and_history(
    session: AsyncSession,
    entity_id: uuid.UUID,
    workspace_id: int | None = None,
) -> CanonicalEntity:
    stmt = (
        select(CanonicalEntity)
        .options(
            selectinload(CanonicalEntity.sources),
            selectinload(CanonicalEntity.merge_history),
        )
        .where(CanonicalEntity.id == entity_id)
    )
    if workspace_id is not None:
        stmt = stmt.where(CanonicalEntity.workspace_id == workspace_id)
    entity = await session.scalar(stmt)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical entity not found",
        )
    return entity


async def _load_entity_for_permission(
    session: AsyncSession, entity_id: uuid.UUID
) -> CanonicalEntity:
    entity = await session.get(CanonicalEntity, entity_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical entity not found",
        )
    return entity


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/canonical-entities", response_model=PaginatedResponse[CanonicalEntityListItem]
)
async def list_canonical_entities(
    workspace_id: int,
    entity_type: str | None = None,
    conflict: bool | None = None,
    status: str | None = Query(None, description="Filter by embedding_status"),
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """List canonical entities for a workspace. Minimal fields only; full snapshots via GET."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to view canonical entities in this workspace",
    )
    await set_canonical_workspace_id(session, workspace_id)

    count_stmt = select(func.count()).select_from(CanonicalEntity)
    stmt = select(CanonicalEntity).order_by(CanonicalEntity.last_seen_at.desc())

    filters = [
        CanonicalEntity.workspace_id == workspace_id,
    ]
    if entity_type:
        filters.append(CanonicalEntity.entity_type == entity_type)
    if status:
        filters.append(CanonicalEntity.embedding_status == status)
    if conflict is True:
        filters.append(CanonicalEntity.conflict_flags != [])
    elif conflict is False:
        filters.append(CanonicalEntity.conflict_flags == [])

    count_stmt = count_stmt.where(*filters)
    stmt = stmt.where(*filters).offset(skip).limit(limit)

    total = (await session.scalar(count_stmt)) or 0
    rows = (await session.scalars(stmt)).all()

    return PaginatedResponse(
        items=[CanonicalEntityListItem.model_validate(r) for r in rows],
        total=total,
        page=(skip // limit + 1) if limit > 0 else 1,
        page_size=limit,
        has_more=skip + len(rows) < total,
    )


@router.get("/canonical-entities/{entity_id}", response_model=CanonicalEntityRead)
async def get_canonical_entity(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Get a canonical entity with source links and its latest merge history."""
    entity = await _load_entity_with_sources_and_history(session, entity_id)
    await check_permission(
        session,
        auth,
        entity.workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to view this canonical entity",
    )
    await set_canonical_workspace_id(session, entity.workspace_id)

    latest = entity.merge_history[0] if entity.merge_history else None
    return _build_entity_read(entity, latest)


@router.get(
    "/canonical-entities/{entity_id}/sources", response_model=list[CanonicalEntitySourceRead]
)
async def get_canonical_entity_sources(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Get the source links for a canonical entity."""
    entity = await _load_entity_with_sources_and_history(session, entity_id)
    await check_permission(
        session,
        auth,
        entity.workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to view this canonical entity's sources",
    )
    await set_canonical_workspace_id(session, entity.workspace_id)

    return [_map_source(s) for s in entity.sources]


@router.get(
    "/canonical-entities/{entity_id}/history",
    response_model=list[CanonicalMergeHistoryRead],
)
async def get_canonical_entity_history(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Full merge/revert/resolve history for a canonical entity."""
    entity = await _load_entity_with_sources_and_history(session, entity_id)
    await check_permission(
        session,
        auth,
        entity.workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to view this canonical entity's history",
    )
    await set_canonical_workspace_id(session, entity.workspace_id)

    return [_map_history(h) for h in entity.merge_history]


@router.post(
    "/canonical-entities/{entity_id}/revert", response_model=CanonicalEntityRead
)
async def revert_canonical_entity_route(
    entity_id: uuid.UUID,
    body: RevertRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Revert an entity to a selected merge history entry."""
    entity = await _load_entity_for_permission(session, entity_id)
    await check_permission(
        session,
        auth,
        entity.workspace_id,
        Permission.CANONICAL_ENTITIES_WRITE.value,
        "You don't have permission to revert this canonical entity",
    )

    try:
        await revert_canonical_entity(
            session,
            workspace_id=entity.workspace_id,
            entity_id=entity_id,
            target_history_id=body.history_id,
            actor=str(auth.user.id),
        )
    except RevertNotPossibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ConcurrentUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await session.flush()
    entity = await _load_entity_with_sources_and_history(
        session, entity_id, workspace_id=entity.workspace_id
    )
    latest = entity.merge_history[0] if entity.merge_history else None
    return _build_entity_read(entity, latest)


@router.post(
    "/canonical-entities/{entity_id}/resolve-conflict",
    response_model=CanonicalEntityRead,
)
async def resolve_canonical_conflict_route(
    entity_id: uuid.UUID,
    body: ResolveConflictRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Manually resolve a conflict by writing a field value."""
    entity = await _load_entity_for_permission(session, entity_id)
    await check_permission(
        session,
        auth,
        entity.workspace_id,
        Permission.CANONICAL_ENTITIES_WRITE.value,
        "You don't have permission to resolve conflicts for this canonical entity",
    )

    try:
        await resolve_canonical_conflict(
            session,
            workspace_id=entity.workspace_id,
            entity_id=entity_id,
            field=body.field,
            value=body.value,
            actor=str(auth.user.id),
        )
    except RevertNotPossibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ConcurrentUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await session.flush()
    entity = await _load_entity_with_sources_and_history(
        session, entity_id, workspace_id=entity.workspace_id
    )
    latest = entity.merge_history[0] if entity.merge_history else None
    return _build_entity_read(entity, latest)


# ---------------------------------------------------------------------------
# Unified search (Story 13.3)
# ---------------------------------------------------------------------------


class ViewSourcesContract(BaseModel):
    href: str
    count: int


class UnifiedSearchEntity(BaseModel):
    id: uuid.UUID
    entity_type: str
    canonical_title: str | None
    source_count: int
    source_ids: list[uuid.UUID]
    confidence_score: float
    conflict_flags: list[Any]
    version: int
    last_seen_at: datetime
    embedding_status: str
    view_sources: ViewSourcesContract
    linked_documents: list[int]


class UnifiedSearchDocument(BaseModel):
    document_id: int
    document: dict[str, Any]
    chunks: list[dict[str, Any]]
    score: float
    content: str = ""
    matched_chunk_ids: list[int] = []
    source: str | None = None

    model_config = ConfigDict(extra="allow")


class UnifiedSearchResult(BaseModel):
    type: str
    score: float
    entity: UnifiedSearchEntity | None = None
    document: UnifiedSearchDocument | None = None


class UnifiedSearchResponse(BaseModel):
    items: list[UnifiedSearchResult]
    total: int


class UnifiedSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    workspace_id: int
    top_k: int = Field(default=10, ge=1, le=50)
    entity_types: list[str] | None = None
    document_types: list[str] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    embedding_status: str | None = None
    statuses: list[str] | None = None
    w_vector: float = Field(default=0.7, ge=0.0)
    w_fts: float = Field(default=0.3, ge=0.0)


@router.post("/canonical-search", response_model=UnifiedSearchResponse)
async def search_canonical_and_documents(
    body: UnifiedSearchRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Search canonical entities and documents, collapsing linked sources.

    Requires both ``documents:read`` and ``canonical_entities:read`` permissions
    because the result set spans both corpora.
    """
    await check_permission(
        session,
        auth,
        body.workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )
    await check_permission(
        session,
        auth,
        body.workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to read canonical entities in this workspace",
    )
    await set_canonical_workspace_id(session, body.workspace_id)

    service = UnifiedSearchService(session)
    try:
        items = await service.search(
            workspace_id=body.workspace_id,
            query_text=body.query,
            top_k=body.top_k,
            entity_types=body.entity_types,
            document_types=body.document_types,
            start_date=body.start_date,
            end_date=body.end_date,
            embedding_status=body.embedding_status,
            statuses=body.statuses,
            w_vector=body.w_vector,
            w_fts=body.w_fts,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return UnifiedSearchResponse(items=items, total=len(items))


@router.get("/canonical-search/supported-filters")
async def supported_canonical_search_filters(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Return the supported canonical entity and document type filters."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.CANONICAL_ENTITIES_READ.value,
        "You don't have permission to read canonical entities in this workspace",
    )
    await set_canonical_workspace_id(session, workspace_id)

    entity_types = (
        await session.scalars(
            select(func.distinct(CanonicalEntity.entity_type)).where(
                CanonicalEntity.workspace_id == workspace_id
            )
        )
    ).all()

    return {
        "entity_types": sorted(entity_types),
        "document_types": sorted([dt.value for dt in DocumentType]),
    }
