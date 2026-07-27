"""REST route for research-thread continuity context (Story 4.6, FR-33).

Exposes ``GET /workspaces/{workspace_id}/research-threads/{thread_id}/context``,
the backend half of ``nowing_continue_research``: it returns a thread's ranked
related memories together with its prior citations, and fails clearly (404) when
the thread does not exist in the workspace — never creating one implicitly.

The memory half reuses the exact recall path of ``memories/search``
(``MemoryHybridSearch`` scoped by ``research_thread_id``) so continuity recall
matches ``nowing_recall`` (AC-3, no divergent ranking). The citations half is
delegated to ``collect_thread_citations`` (AC-1b / AC-4).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, ResearchThread, get_async_session
from app.schemas.memory import MemorySearchHit, ResearchThreadContext
from app.services.memory.search import MemoryHybridSearch
from app.services.memory.thread_citations import collect_thread_citations
from app.users import get_auth_context
from app.utils.document_converters import embed_texts
from app.utils.rbac import check_permission

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/research-threads/{thread_id}/context",
    response_model=ResearchThreadContext,
)
async def get_research_thread_context(
    workspace_id: int,
    thread_id: int,
    query: str = Query(
        default="",
        description=(
            "Optional query to rank the thread's memories; empty returns the "
            "most recent (recency-ordered) recall, matching nowing_recall."
        ),
    ),
    top_k: int = Query(default=5, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ResearchThreadContext:
    # Continuity is a read of the thread's memory/context — reuse memory:read.
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.MEMORY_READ.value,
        error_message="You don't have permission to read memory in this workspace",
    )

    # Load by id AND workspace_id so a thread from another workspace is not
    # reachable (AC-4 isolation). No implicit creation on miss (AC-2).
    thread = await session.scalar(
        select(ResearchThread).where(
            ResearchThread.id == thread_id,
            ResearchThread.workspace_id == workspace_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Research thread not found")

    # Same recall path as POST /memories/search (AC-3): embed only a non-empty
    # query; an empty query falls back to recency ordering inside the search.
    query_embedding = None
    if query.strip():
        embeddings = await asyncio.to_thread(embed_texts, [query])
        query_embedding = embeddings[0]

    search = MemoryHybridSearch(session)
    memories = await search.search(
        workspace_id=workspace_id,
        query=query,
        query_embedding=query_embedding,
        top_k=top_k,
        research_thread_id=thread_id,
    )

    citations = await collect_thread_citations(session, thread)

    return ResearchThreadContext(
        thread_id=thread.id,
        title=thread.title,
        memories=[
            MemorySearchHit.from_memory(memory)
            for memory in memories
        ],
        citations=citations,
    )
