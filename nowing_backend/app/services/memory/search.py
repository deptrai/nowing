"""Hybrid full-text + vector search for memory rows (Story 3.14, D1/D5/D6)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import Float, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Memory, MemoryType
from app.services.memory.vector import VectorValidationError, validate_embedding_vector

logger = logging.getLogger(__name__)

#: D6: at most 15 SQL candidates are ever materialized, regardless of top_k.
_MAX_CANDIDATES = 15
#: D6: at most 5 valid results are ever returned, regardless of top_k.
_MAX_RESULTS = 5


@dataclass(frozen=True)
class ScoredMemory:
    """A single search hit paired with its ranking metadata (D1).

    ``score``/``similarity`` are both finite floats for a ranked (query-driven)
    hit, and both ``None`` for a recency (query-less) hit — never a fake
    ``0.0`` placeholder.
    """

    memory: Memory
    score: float | None
    similarity: float | None


class MemoryHybridSearch:
    """RRF fusion of vector similarity and full-text search over Memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _scope_conditions(
        *,
        workspace_id: int | None,
        user_id: UUID | None,
        research_thread_id: int | None,
    ) -> list[Any]:
        """Canonical scope per D5: exactly one of workspace/user, never both.

        Raises ``ValueError`` before any SQL is built on a missing or
        ambiguous scope — never a broad ``OR`` across scopes.
        """
        has_workspace = workspace_id is not None
        has_user = user_id is not None
        if has_workspace == has_user:
            raise ValueError(
                "memory search scope must be exactly one of workspace_id or user_id"
            )
        if research_thread_id is not None and not has_workspace:
            raise ValueError("research_thread_id requires workspace scope")
        if has_workspace:
            return [Memory.workspace_id == workspace_id]
        return [Memory.workspace_id.is_(None), Memory.created_by_id == user_id]

    async def search(
        self,
        *,
        workspace_id: int | None = None,
        user_id: UUID | None = None,
        query: str,
        query_embedding: list[float] | np.ndarray | None = None,
        top_k: int = 5,
        type: str | None = None,
        tags: list[str] | None = None,
        research_thread_id: int | None = None,
    ) -> list[ScoredMemory]:
        base_conditions = self._scope_conditions(
            workspace_id=workspace_id,
            user_id=user_id,
            research_thread_id=research_thread_id,
        )
        if type is not None:
            base_conditions.append(Memory.type == MemoryType(type))
        if research_thread_id is not None:
            base_conditions.append(Memory.research_thread_id == research_thread_id)
        if tags:
            base_conditions.append(Memory.tags.op("&&")(tags))

        query_blank = not str(query).strip()
        query_embedding_missing = query_embedding is None

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, (int, np.integer))
            or top_k < 1
            or top_k > _MAX_RESULTS
        ):
            raise ValueError(
                f"top_k must be a positive integer between 1 and {_MAX_RESULTS}, got {top_k!r}"
            )
        output_limit = top_k

        if query_blank and query_embedding_missing:
            # D6: recency = blank query + no embedding + a concrete thread id.
            if research_thread_id is None:
                raise ValueError(
                    "recency recall requires a research_thread_id; "
                    "ranked recall requires a nonblank query and a valid embedding"
                )
            stmt = (
                select(Memory)
                .where(*base_conditions)
                .order_by(Memory.created_at.desc(), Memory.id.desc())
                .limit(output_limit)
            )
            result = await self.session.execute(stmt)
            return [
                ScoredMemory(memory=memory, score=None, similarity=None)
                for memory in result.scalars().all()
            ]
        elif not query_blank and not query_embedding_missing:
            # D6: ranked = nonblank query + valid embedding.
            pass
        else:
            raise ValueError(
                "query and query_embedding must both be provided for ranked recall, "
                "or both absent for recency recall"
            )

        embedding = validate_embedding_vector(
            query_embedding, dimension=config.embedding_model_instance.dimension
        )
        candidate_limit = min(top_k * 3, _MAX_CANDIDATES)

        tsvector = func.to_tsvector("english", Memory.content)
        tsquery = func.plainto_tsquery("english", query)
        distance = Memory.embedding.op("<=>", return_type=Float)(embedding)

        semantic = (
            select(
                Memory.id,
                func.row_number()
                .over(order_by=(distance.asc(), Memory.id.asc()))
                .label("rank"),
            )
            .where(*base_conditions)
            .order_by(distance.asc(), Memory.id.asc())
            .limit(candidate_limit)
            .cte("semantic_memory")
        )

        keyword_rank = func.ts_rank_cd(tsvector, tsquery)
        keyword = (
            select(
                Memory.id,
                func.row_number()
                .over(order_by=(keyword_rank.desc(), Memory.id.asc()))
                .label("rank"),
            )
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
            .order_by(keyword_rank.desc(), Memory.id.asc())
            .limit(candidate_limit)
            .cte("keyword_memory")
        )

        k = 60
        final = (
            select(
                Memory,
                (
                    func.coalesce(1.0 / (k + semantic.c.rank), 0.0)
                    + func.coalesce(1.0 / (k + keyword.c.rank), 0.0)
                ).label("score"),
                (1.0 - distance).label("similarity"),
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
            .order_by(
                text("score DESC"),
                text("similarity DESC"),
                Memory.created_at.desc(),
                Memory.id.asc(),
            )
            .limit(_MAX_CANDIDATES)
        )

        result = await self.session.execute(final)
        candidates = result.all()

        valid: list[ScoredMemory] = []
        for memory, score, similarity in candidates:
            if len(valid) >= output_limit:
                break
            try:
                validate_embedding_vector(
                    memory.embedding,
                    dimension=config.embedding_model_instance.dimension,
                )
            except VectorValidationError as exc:
                logger.warning(
                    "skipping memory %s with invalid stored embedding: %s",
                    memory.id,
                    exc.reason,
                )
                continue
            if score is None or similarity is None:
                logger.warning(
                    "skipping memory %s with non-finite score/similarity", memory.id
                )
                continue
            score = float(score)
            similarity = float(similarity)
            if not (np.isfinite(score) and np.isfinite(similarity)):
                logger.warning(
                    "skipping memory %s with non-finite score/similarity", memory.id
                )
                continue
            valid.append(
                ScoredMemory(memory=memory, score=score, similarity=similarity)
            )

        return valid
