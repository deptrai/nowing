"""Execute a ``continue_research`` automation step.

Reuses the Story 4.6 research-continuity backend **in-process** (not over HTTP):
the same ``MemoryHybridSearch`` recall scoped by ``research_thread_id`` and the
same ``collect_thread_citations`` aggregation the
``/research-threads/{id}/context`` route uses, so continuity recall never
diverges from ``nowing_continue_research``.

The thread is loaded by id AND workspace so a thread from another workspace is
unreachable, and a missing thread fails the step with a clear error — never
creating one implicitly (consistent with Story 4.6, AC-2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db import ResearchThread
from app.schemas.memory import MemorySearchHit
from app.services.memory.search import MemoryHybridSearch
from app.services.memory.thread_citations import collect_thread_citations

from ...types import ActionContext
from .params import ContinueResearchActionParams


async def continue_research(ctx: ActionContext, params: dict[str, Any]) -> dict[str, Any]:
    """Recall a research thread's memories + prior citations for the step output."""
    parsed = ContinueResearchActionParams.model_validate(params)

    thread = await ctx.session.scalar(
        select(ResearchThread).where(
            ResearchThread.id == parsed.research_thread_id,
            ResearchThread.workspace_id == ctx.workspace_id,
        )
    )
    if thread is None:
        raise ValueError(
            f"Research thread {parsed.research_thread_id} not found in workspace "
            f"{ctx.workspace_id}"
        )

    # Same recall path as the research-continuity route: an empty query recalls
    # the thread's most recent memories (recency-ordered), matching nowing_recall.
    memories = await MemoryHybridSearch(ctx.session).search(
        workspace_id=ctx.workspace_id,
        query="",
        query_embedding=None,
        top_k=parsed.top_k,
        research_thread_id=parsed.research_thread_id,
    )

    citations = await collect_thread_citations(ctx.session, thread)

    return {
        "research_thread_id": parsed.research_thread_id,
        "memories": [
            MemorySearchHit.from_memory(memory).model_dump(mode="json")
            for memory in memories
        ],
        "citations": [citation.model_dump(mode="json") for citation in citations],
    }
