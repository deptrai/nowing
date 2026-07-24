"""Hybrid full-text + vector search for memory rows."""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import Float, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Memory, MemoryType


def _as_np(embedding: Any) -> np.ndarray:
    return np.asarray(embedding, dtype=np.float32)


class MemoryHybridSearch:
    """RRF fusion of vector similarity and full-text search over Memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        *,
        workspace_id: int,
        query: str,
        query_embedding: list[float] | np.ndarray | None = None,
        top_k: int = 5,
        type: str | None = None,
        tags: list[str] | None = None,
        research_thread_id: int | None = None,
    ) -> list[Memory]:
        k = 60
        n_results = top_k * 3

        base_conditions = [Memory.workspace_id == workspace_id]
        if type is not None:
            base_conditions.append(Memory.type == MemoryType(type))
        if research_thread_id is not None:
            base_conditions.append(Memory.research_thread_id == research_thread_id)
        if tags:
            base_conditions.append(Memory.tags.op("&&")(tags))

        # Query-less thread recall: when no query text/embedding is supplied
        # (e.g. nowing_continue_research scoping by thread), return the most
        # recent matching memories instead of ranking by relevance.
        if query_embedding is None or not str(query).strip():
            stmt = (
                select(Memory)
                .where(*base_conditions)
                .order_by(Memory.created_at.desc())
                .limit(top_k)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        tsvector = func.to_tsvector("english", Memory.content)
        tsquery = func.plainto_tsquery("english", query)

        embedding = _as_np(query_embedding)

        semantic = (
            select(
                Memory.id,
                func.rank()
                .over(order_by=Memory.embedding.op("<=>", return_type=Float)(embedding))
                .label("rank"),
            )
            .where(*base_conditions)
            .order_by(Memory.embedding.op("<=>", return_type=Float)(embedding))
            .limit(n_results)
            .cte("semantic_memory")
        )

        keyword = (
            select(
                Memory.id,
                func.rank()
                .over(order_by=func.ts_rank_cd(tsvector, tsquery).desc())
                .label("rank"),
            )
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(n_results)
            .cte("keyword_memory")
        )

        final = (
            select(
                Memory,
                (
                    func.coalesce(1.0 / (k + semantic.c.rank), 0.0)
                    + func.coalesce(1.0 / (k + keyword.c.rank), 0.0)
                ).label("score"),
            )
            .select_from(
                semantic.outerjoin(
                    keyword,
                    semantic.c.id == keyword.c.id,
                    full=True,
                )
            )
            .join(
                Memory,
                Memory.id == func.coalesce(semantic.c.id, keyword.c.id),
            )
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        result = await self.session.execute(final)
        rows = result.all()
        return [row[0] for row in rows]
