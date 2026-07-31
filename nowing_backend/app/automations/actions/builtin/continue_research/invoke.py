"""Execute a ``continue_research`` automation step.

Reuses the Story 4.6 research-continuity backend **in-process** (not over HTTP):
the same ``MemoryHybridSearch`` recall scoped by ``research_thread_id`` and the
same ``collect_thread_citations`` aggregation the
``/research-threads/{id}/context`` route uses, so continuity recall never
diverges from ``nowing_continue_research``.

The thread is loaded by id AND workspace so a thread from another workspace is
unreachable, and a missing thread fails the step with a clear error — never
creating one implicitly (consistent with Story 4.6, AC-2).

Story 3.14 (D9) pins new (``schema_version 1.1``) writes to ``top_k`` 1..5. A
persisted ``schema_version 1.0`` run instead validates against the wider legacy
1..100 ceiling, then a still-valid 6..100 value is clamped to 5 with a one-time
warning logged before the recall runs.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.db import ResearchThread
from app.schemas.memory import MemorySearchHit
from app.services.memory.search import MemoryHybridSearch
from app.services.memory.thread_citations import collect_thread_citations

from ...types import ActionContext
from .params import ContinueResearchActionParams, _LegacyContinueResearchActionParams

logger = logging.getLogger(__name__)

_LEGACY_SCHEMA_VERSION = "1.0"
_STRICT_TOP_K_CEILING = 5


async def continue_research(
    ctx: ActionContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Recall a research thread's memories + prior citations for the step output."""
    if ctx.schema_version == _LEGACY_SCHEMA_VERSION:
        parsed = _LegacyContinueResearchActionParams.model_validate(params)
        top_k = parsed.top_k
        if top_k > _STRICT_TOP_K_CEILING:
            logger.warning(
                "continue_research: schema_version %s requested top_k=%d, "
                "clamping to %d",
                ctx.schema_version,
                top_k,
                _STRICT_TOP_K_CEILING,
                extra={
                    "action": "continue_research",
                    "schema_version": ctx.schema_version,
                    "reason": "top_k_above_5",
                },
            )
            top_k = _STRICT_TOP_K_CEILING
    else:
        parsed = ContinueResearchActionParams.model_validate(params)
        top_k = parsed.top_k

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
    hits = await MemoryHybridSearch(ctx.session).search(
        workspace_id=ctx.workspace_id,
        query="",
        query_embedding=None,
        top_k=top_k,
        research_thread_id=parsed.research_thread_id,
    )

    citations = await collect_thread_citations(ctx.session, thread)

    return {
        "research_thread_id": parsed.research_thread_id,
        "memories": [
            MemorySearchHit.from_memory(
                hit.memory, score=hit.score, similarity=hit.similarity
            ).model_dump(mode="json")
            for hit in hits
        ],
        "citations": [citation.model_dump(mode="json") for citation in citations],
    }
