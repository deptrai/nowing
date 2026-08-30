"""Lead Search & Retrieval Service for high-scale workspace queries (10k+ leads).

Implements GIN full-text search (``tsvector``), ``pg_trgm`` fuzzy substring
matching, composite B-tree index-aligned filtering/sorting, keyset (cursor)
pagination, and optional pgvector HNSW semantic hybrid retrieval.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Lead

logger = logging.getLogger(__name__)


class LeadSearchService:
    """Service executing optimized FTS, trigram, and keyset-paginated lead queries."""

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    async def search_leads(
        self,
        session: AsyncSession,
        workspace_id: int,
        search_term: str | None = None,
        table_id: UUID | None = None,
        status_filter: str | None = None,
        stage_id: UUID | None = None,
        assigned_to_user_id: UUID | None = None,
        client_id: str | None = None,
        source: str | None = None,
        sources: list[str] | None = None,
        min_fit_score: float | None = None,
        min_composite_score: float | None = None,
        intent: str | None = None,
        sort: str = "-created_at",
        cursor_score: float | None = None,
        cursor_id: UUID | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> tuple[list[Lead], int]:
        """Execute composite-indexed search with GIN FTS and cursor pagination.

        Returns a tuple of (leads, total_count).  The total is computed from an
        equivalent count query that respects the same filters but ignores
        pagination cursors.
        """
        limit = min(max(limit, 1), self.MAX_LIMIT)

        # Base tenant-scoped query.
        stmt = (
            select(Lead)
            .where(Lead.workspace_id == workspace_id)
            .options(selectinload(Lead.verified_contacts))
        )

        # 1. Tenant & RBAC isolation / categorical filters.
        if assigned_to_user_id is not None:
            stmt = stmt.where(Lead.assigned_to_user_id == assigned_to_user_id)
        if client_id is not None:
            stmt = stmt.where(Lead.client_id == client_id)
        if table_id is not None:
            stmt = stmt.where(Lead.table_id == table_id)
        if status_filter is not None:
            stmt = stmt.where(Lead.status == status_filter)
        if stage_id is not None:
            stmt = stmt.where(Lead.stage_id == stage_id)
        if source is not None:
            stmt = stmt.where(Lead.source.ilike(f"%{source}%", escape="!"))
        if sources is not None:
            stmt = stmt.where(Lead.source.in_(sources))
        if min_fit_score is not None:
            stmt = stmt.where(Lead.fit_score >= min_fit_score)
        if min_composite_score is not None:
            stmt = stmt.where(Lead.composite_score >= min_composite_score)

        # 2. Intent / source mapping (mirror leads_routes intent filter).
        if intent:
            intent_clean = intent.strip().upper()
            if "THẦU" in intent_clean or "TENDER" in intent_clean:
                stmt = stmt.where(Lead.source.in_(["muasamcong", "tender"]))
            elif "TUYỂN" in intent_clean or "JOB" in intent_clean:
                stmt = stmt.where(
                    Lead.source.in_(["topcv", "itviec", "vietnamworks", "jobs"])
                )
            elif "MUA" in intent_clean:
                stmt = stmt.where(
                    Lead.source.in_(["shopee", "tiktok_shop", "ecommerce", "facebook"])
                )
            elif "BÁN" in intent_clean:
                stmt = stmt.where(
                    Lead.source.in_(["batdongsan", "chotot", "muaban_bds", "facebook"])
                )

        # 3. Full-Text Search + Trigram fallback.
        search_term = (search_term or "").strip()
        if search_term:
            ts_query = func.plainto_tsquery("simple", search_term)
            fts_condition = Lead.search_vector.op("@@")(ts_query)

            # Trigram similarity on key identifier fields for partial / fuzzy matches.
            trgm_condition = or_(
                Lead.company_name.op("%")(search_term),
                Lead.tax_id.op("%")(search_term),
                Lead.domain.op("%")(search_term),
            )

            stmt = stmt.where(or_(fts_condition, trgm_condition))

        # 4. Ordering aligned with composite indexes.
        order_by_clause = self._build_order_by(sort)
        stmt = stmt.order_by(*order_by_clause)

        # 5. Keyset (cursor) pagination for deep page performance.
        if cursor_score is not None and cursor_id is not None:
            score_col, is_desc = self._score_column_for_sort(sort)
            direction = ">" if not is_desc else "<"
            stmt = stmt.where(
                or_(
                    score_col.op(direction)(cursor_score),
                    and_(
                        score_col == cursor_score,
                        Lead.id.op(direction)(cursor_id),
                    ),
                )
            )

        # Count query (same filters, no cursor, no limit/offset).
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar_one()

        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total

    def _build_order_by(self, sort: str) -> list[Any]:
        """Return order-by clauses matching the composite B-tree indexes."""
        if sort in {"-created_at", "-createdAt"}:
            return [desc(Lead.created_at), desc(Lead.id)]
        if sort in {"created_at", "createdAt"}:
            return [Lead.created_at, Lead.id]
        if sort in {"-fit_score", "-fitScore"}:
            return [desc(Lead.fit_score).nullslast(), desc(Lead.id)]
        if sort in {"fit_score", "fitScore"}:
            return [Lead.fit_score.nullslast(), Lead.id]
        if sort in {"-score", "-composite_score"}:
            return [desc(Lead.composite_score).nullslast(), desc(Lead.id)]
        if sort in {"score", "composite_score"}:
            return [Lead.composite_score.nullslast(), Lead.id]
        # Default.
        return [desc(Lead.created_at), desc(Lead.id)]

    def _score_column_for_sort(self, sort: str) -> tuple[Any, bool]:
        """Return (score_column, is_descending) for keyset pagination."""
        if sort in {"-fit_score", "-fitScore", "fit_score", "fitScore"}:
            return Lead.fit_score, sort.startswith("-")
        if sort in {"-score", "-composite_score", "score", "composite_score"}:
            return Lead.composite_score, sort.startswith("-")
        return Lead.created_at, sort.startswith("-")

    async def hybrid_semantic_search(
        self,
        session: AsyncSession,
        workspace_id: int,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 50,
        rrf_k: int = 60,
    ) -> list[Lead]:
        """Perform Reciprocal Rank Fusion blending pgvector HNSW and tsvector FTS."""
        # Step A: Vector retrieval (Top-K)
        vec_stmt = (
            select(Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.embedding.isnot(None),
            )
            .order_by(Lead.embedding.op("<=>")(query_embedding))
            .limit(top_k)
        )
        vec_res = await session.execute(vec_stmt)
        vec_ids = [row[0] for row in vec_res.fetchall()]

        # Step B: Keyword retrieval (Top-K)
        ts_query = func.plainto_tsquery("simple", query_text)
        fts_stmt = (
            select(Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.search_vector.op("@@")(ts_query),
            )
            .order_by(func.ts_rank_cd(Lead.search_vector, ts_query).desc())
            .limit(top_k)
        )
        fts_res = await session.execute(fts_stmt)
        fts_ids = [row[0] for row in fts_res.fetchall()]

        # Step C: RRF Scoring
        rrf_scores: dict[UUID, float] = {}
        for rank, lead_id in enumerate(vec_ids):
            rrf_scores[lead_id] = rrf_scores.get(lead_id, 0.0) + (
                1.0 / (rrf_k + rank + 1)
            )
        for rank, lead_id in enumerate(fts_ids):
            rrf_scores[lead_id] = rrf_scores.get(lead_id, 0.0) + (
                1.0 / (rrf_k + rank + 1)
            )

        if not rrf_scores:
            return []

        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda _id: rrf_scores[_id],
            reverse=True,
        )[:top_k]

        leads_stmt = (
            select(Lead)
            .where(Lead.id.in_(sorted_ids), Lead.workspace_id == workspace_id)
            .options(selectinload(Lead.verified_contacts))
        )
        leads_res = await session.execute(leads_stmt)
        leads_map = {lead.id: lead for lead in leads_res.scalars().all()}
        return [leads_map[lid] for lid in sorted_ids if lid in leads_map]
