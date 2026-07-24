"""Structured REST routes for long-term memory."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Memory, Permission, get_async_session
from app.schemas.memory import (
    MemoryCreate,
    MemoryRead,
    MemorySearchHit,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryUpdate,
)
from app.services.memory.repository import MemoryRepository
from app.services.memory.search import MemoryHybridSearch
from app.users import get_auth_context
from app.utils.document_converters import embed_texts
from app.utils.rbac import check_permission

router = APIRouter()


def _to_memory_read(memory: Memory) -> MemoryRead:
    return MemoryRead.model_validate(memory)


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
):
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_CREATE.value,
        error_message="You don't have permission to create memory in this workspace",
    )

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
        created_by_id=auth.user.id,
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

    query_embedding = await asyncio.to_thread(embed_texts, [body.query])
    search = MemoryHybridSearch(session)
    results = await search.search(
        workspace_id=workspace_id,
        query=body.query,
        query_embedding=query_embedding[0],
        top_k=body.top_k,
        type=body.type,
        tags=body.tags,
        research_thread_id=body.research_thread_id,
    )

    return MemorySearchResponse(
        items=[
            MemorySearchHit(
                id=memory.id,
                content=memory.content,
                type=memory.type.value,
                tags=memory.tags or [],
                confidence=memory.confidence,
                source_type=memory.source_type.value,
                source_id=memory.source_id,
                score=0.0,
            )
            for memory in results
        ]
    )


@router.patch("/memories/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: int,
    body: MemoryUpdate,
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
            Permission.MEMORY_UPDATE.value,
            error_message="You don't have permission to update this memory",
        )

    updated = await repo.update_memory(
        memory_id=memory_id,
        corrected_content=body.corrected_content,
        corrected_by_id=auth.user.id,
        skip_version_if_unchanged=True,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _to_memory_read(updated)


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

    await repo.delete_memory(memory_id)
    return None
