"""Structured REST routes for long-term memory."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Memory, MemoryType, Permission, get_async_session
from app.schemas.memory import (
    MemoryCreate,
    MemoryRead,
    MemorySearchHit,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryUpdate,
)
from app.services.memory.repository import MemoryRepository
from app.services.memory.revalidation_service import (
    RevalidationError,
    RevalidationService,
)
from app.services.memory.search import MemoryHybridSearch
from app.services.memory.vector import (
    VectorValidationError,
    validate_single_embedding_result,
)
from app.users import get_auth_context
from app.utils.document_converters import embed_texts
from app.utils.rbac import check_permission

router = APIRouter()


def _to_memory_read(memory: Memory) -> MemoryRead:
    return MemoryRead.model_validate(memory)


def _pat_client_id(auth: AuthContext) -> str | None:
    """Return the client_id bound to the authenticated PAT, if any."""
    return getattr(auth.pat, "client_id", None) if auth.pat else None


def _pat_agent_id(auth: AuthContext) -> str | None:
    """Return the agent_id bound to the authenticated PAT, if any."""
    return getattr(auth.pat, "agent_id", None) if auth.pat else None


def _resolved_tenant_ids(
    auth: AuthContext,
    requested_client_id: str | None = None,
    requested_agent_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Intersect an optional request body/query client_id/agent_id with the auth scope.

    Session and system principals have no client scope, so any non-None
    request values are rejected. PAT principals default to their bound scope.
    This mirrors the fail-closed pattern in agent_chat_routes.py.
    """
    client_id = _pat_client_id(auth)
    agent_id = _pat_agent_id(auth)

    if requested_client_id is not None and requested_client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="client_id outside authorization scope",
        )
    if requested_agent_id is not None and requested_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="agent_id outside authorization scope",
        )
    return client_id, agent_id


def _require_memory_tenant_match(auth: AuthContext, memory: Memory) -> None:
    """Fail closed when a memory belongs to a different client/agent scope."""
    client_id, agent_id = _pat_client_id(auth), _pat_agent_id(auth)
    if memory.client_id != client_id or memory.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="memory outside authorization scope",
        )


@router.post(
    "/workspaces/{workspace_id}/memories",
    response_model=MemoryRead,
    status_code=201,
)
async def create_memory(
    workspace_id: int,
    body: MemoryCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    x_automation_run_id: int | None = Header(default=None),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_CREATE.value,
        error_message="You don't have permission to create memory in this workspace",
    )

    # AC-18.6: client_id/agent_id must come from the auth scope. Intersect the
    # request body with the PAT scope so callers cannot widen beyond their tenant.
    client_id, agent_id = _resolved_tenant_ids(auth, body.client_id, body.agent_id)

    repo = MemoryRepository(session)
    memory = await repo.create_memory(
        workspace_id=workspace_id,
        content=body.content,
        type=body.type,
        source_type=body.source_type,
        source_id=body.source_id,
        tags=body.tags,
        confidence=body.confidence,
        research_thread_id=body.research_thread_id,
        client_id=client_id,
        agent_id=agent_id,
        created_by_id=auth.user.id,
        # Loop guard (Story 6.5, AC-5): a cross-process automation write (an
        # external MCP server calling this endpoint) threads its origin via the
        # ``X-Automation-Run-Id`` header, since a Python contextvar cannot cross
        # the HTTP boundary. The repository skips ``memory.changed`` emission for
        # an automation-origin write so it cannot re-fire its own trigger.
        automation_run_id=x_automation_run_id,
    )
    return _to_memory_read(memory)


@router.post(
    "/workspaces/{workspace_id}/memories/search",
    response_model=MemorySearchResponse,
)
async def search_memory(
    workspace_id: int,
    body: MemorySearchRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
        error_message="You don't have permission to search memory in this workspace",
    )

    # AC-18.6: recall must stay within the caller's tenant scope.
    client_id, _ = _resolved_tenant_ids(auth, body.client_id)

    query_embedding = None
    if body.query.strip():
        try:
            embeddings = await asyncio.to_thread(embed_texts, [body.query])
        except Exception as exc:
            raise VectorValidationError("provider_error") from exc
        query_embedding = validate_single_embedding_result(embeddings)

    search = MemoryHybridSearch(session)
    try:
        results = await search.search(
            workspace_id=workspace_id,
            query=body.query,
            query_embedding=query_embedding,
            top_k=body.top_k,
            type=body.type,
            tags=body.tags,
            research_thread_id=body.research_thread_id,
            client_id=client_id,
        )
    except VectorValidationError as exc:
        status = 500 if exc.reason == "provider_error" else 422
        raise HTTPException(
            status_code=status,
            detail={
                "code": exc.reason,
                "message": f"embedding validation failed: {exc.reason}",
            },
        ) from exc

    return MemorySearchResponse(
        items=[
            MemorySearchHit.from_memory(
                hit.memory, score=hit.score, similarity=hit.similarity
            )
            for hit in results
        ]
    )


@router.get(
    "/workspaces/{workspace_id}/memories",
    response_model=list[MemoryRead],
)
async def list_memories(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    limit: int = Query(default=20, ge=1, le=100),
    type: MemoryType | None = Query(default=None),
    tags: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
        error_message="You don't have permission to read memory in this workspace",
    )

    # AC-18.6: list must stay within the caller's tenant scope.
    client_id, _ = _resolved_tenant_ids(auth, client_id)

    repo = MemoryRepository(session)
    memories = await repo.list_memories(
        workspace_id=workspace_id,
        limit=limit,
        type=type,
        tags=tags.split(",") if tags else None,
        client_id=client_id,
    )
    return [_to_memory_read(memory) for memory in memories]


@router.patch("/memories/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: int,
    body: MemoryUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    x_automation_run_id: int | None = Header(default=None),
):
    repo = MemoryRepository(session)
    memory = await repo.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.workspace_id is not None:
        await check_permission(
            session,
            auth,
            memory.workspace_id,
            Permission.MEMORY_UPDATE.value,
            error_message="You don't have permission to update this memory",
        )
    elif memory.created_by_id is None or str(memory.created_by_id) != str(auth.user.id):
        # Workspace-less (personal) memory: only its owner may update it.
        # Fail closed when the memory has no owner or the caller is unknown.
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to update this memory",
        )

    # AC-18.6: tenant scope on the memory must match the caller's scope.
    _require_memory_tenant_match(auth, memory)

    updated = await repo.update_memory(
        memory_id=memory_id,
        corrected_content=body.corrected_content,
        corrected_by_id=auth.user.id,
        skip_version_if_unchanged=True,
        # See create_memory: cross-process automation origin via header (AC-5).
        automation_run_id=x_automation_run_id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_memory_read(updated)


@router.post(
    "/workspaces/{workspace_id}/memories/{memory_id}/revalidate",
    response_model=MemoryRead,
)
async def revalidate_memory(
    workspace_id: int,
    memory_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    x_automation_run_id: int | None = Header(default=None),
):
    repo = MemoryRepository(session)
    memory = await repo.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.workspace_id is not None and memory.workspace_id != workspace_id:
        raise HTTPException(
            status_code=403,
            detail="Memory does not belong to the specified workspace",
        )

    if memory.workspace_id is not None:
        await check_permission(
            session,
            auth,
            memory.workspace_id,
            Permission.MEMORY_UPDATE.value,
            error_message="You don't have permission to revalidate this memory",
        )
    elif memory.created_by_id is None or str(memory.created_by_id) != str(auth.user.id):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to revalidate this memory",
        )

    # AC-18.6: tenant scope on the memory must match the caller's scope.
    _require_memory_tenant_match(auth, memory)

    service = RevalidationService(session)
    try:
        result = await service.revalidate(
            memory_id,
            workspace_id=workspace_id,
            actor_id=auth.user.id,
        )
    except RevalidationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        ) from exc

    return _to_memory_read(result.memory)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    repo = MemoryRepository(session)
    memory = await repo.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.workspace_id is not None:
        await check_permission(
            session,
            auth,
            memory.workspace_id,
            Permission.MEMORY_DELETE.value,
            error_message="You don't have permission to delete this memory",
        )
    elif memory.created_by_id is None or str(memory.created_by_id) != str(auth.user.id):
        # Workspace-less (personal) memory: only its owner may delete it.
        # Fail closed when the memory has no owner or the caller is unknown.
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to delete this memory",
        )

    # AC-18.6: tenant scope on the memory must match the caller's scope.
    _require_memory_tenant_match(auth, memory)

    await repo.delete_memory(memory_id)
    return None


class MemoryBulkDeleteRequest(BaseModel):
    source_type: str | None = None
    source_id: int | None = None
    source_entity_type: str | None = None
    dry_run: bool = False


@router.delete("/workspaces/{workspace_id}/memories/{memory_id}", status_code=204)
async def right_to_delete_memory(
    workspace_id: int,
    memory_id: int,
    reason: str | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Right-to-Delete single memory erasure with audit trail logging (Story 28.5, AC-8)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_DELETE.value,
        error_message="You don't have permission to delete this memory",
    )
    from app.services.memory.erasure_service import MemoryErasureService

    service = MemoryErasureService(session)
    deleted = await service.delete_memory(
        workspace_id=workspace_id,
        memory_id=memory_id,
        actor=auth.user,
        reason=reason,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return None


@router.post("/workspaces/{workspace_id}/memories/bulk-delete")
async def bulk_delete_memories(
    workspace_id: int,
    body: MemoryBulkDeleteRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Chunked bulk memory deletion with dry-run and audit trail logging (Story 28.5, AC-9)."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_DELETE.value,
        error_message="You don't have permission to delete memories in bulk",
    )
    from app.services.memory.erasure_service import MemoryErasureService

    service = MemoryErasureService(session)
    result = await service.bulk_delete_memories(
        workspace_id=workspace_id,
        source_type=body.source_type,
        source_id=body.source_id,
        source_entity_type=body.source_entity_type,
        actor=auth.user,
        dry_run=body.dry_run,
    )
    return result
