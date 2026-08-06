"""Unified search across canonical entities and documents.

This module fuses vector and full-text reciprocal rank fusion (RRF) for both
canonical entities and documents, then collapses document results that are
already linked to a canonical entity in the same workspace.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.canonical.tenant_context import set_canonical_workspace_id
from app.config import config
from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalPersistOutbox,
    EmbeddingStatus,
)
from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)


# ponytail: fixed RRF constant from the product spec.  Weights are runtime
# configuration but default to 0.7 vector / 0.3 full-text.
_RRF_K = 60


def _current_embedding_model() -> str:
    return config.EMBEDDING_MODEL or "unknown"


def _rrf_score(
    rank_vector: int | None,
    rank_fts: int | None,
    *,
    w_vector: float,
    w_fts: float,
    k: int = _RRF_K,
) -> float:
    """Weighted Reciprocal Rank Fusion for two rank positions.

    Missing ranks are treated as 0 contribution, never as 0 rank (which would
    inflate the score via division by ``k``).
    """
    score = 0.0
    if rank_vector is not None:
        score += w_vector / (k + rank_vector)
    if rank_fts is not None:
        score += w_fts / (k + rank_fts)
    return score


def _is_vector_eligible(entity: CanonicalEntity, current_model: str) -> bool:
    """Return True if the entity's embedding is current and ready for vector ranking."""
    return (
        entity.embedding is not None
        and entity.embedding_model_name == current_model
        and entity.embedding_status == "ready"
    )


async def _embed_query(query_text: str) -> list[float]:
    """Compute the query embedding once, off the event loop when possible."""
    perf = get_perf_logger()
    t0 = time.perf_counter()
    embed_fn = config.embedding_model_instance.embed
    if inspect.iscoroutinefunction(embed_fn):
        query_embedding = await embed_fn(query_text)
    else:
        query_embedding = await asyncio.to_thread(embed_fn, query_text)
    perf.info(
        "[unified_search] query_embedding elapsed_ms=%.2f",
        (time.perf_counter() - t0) * 1000,
    )
    return query_embedding


class UnifiedSearchService:
    """Search both canonical entities and workspace documents in one ranked list."""

    def __init__(self, db_session: Any) -> None:
        self.db_session = db_session

    async def search(
        self,
        *,
        workspace_id: int,
        query_text: str,
        top_k: int = 10,
        entity_types: list[str] | None = None,
        document_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        embedding_status: str | None = None,
        statuses: list[str] | None = None,
        w_vector: float = 0.7,
        w_fts: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Return a single ranked list of canonical-entity and document groups.

        Document and canonical retrieval use the same workspace, date, status and
        type filters where applicable.  Documents linked to a canonical entity in
        the result set are grouped under that entity instead of appearing as a
        separate top-level hit.
        """
        perf = get_perf_logger()
        t0 = time.perf_counter()

        if w_vector < 0 or w_fts < 0:
            raise ValueError("RRF weights must be non-negative")

        # Set the canonical tenant context for RLS on canonical tables.
        await set_canonical_workspace_id(self.db_session, workspace_id)

        query_embedding = await _embed_query(query_text)

        # ponytail: document and canonical retrieval share the caller's session so
        # integration tests with uncommitted savepoint-scoped data work.  Both use
        # the same workspace, date, status and type filters, and run independently.
        # Running sequentially on one asyncpg connection is safe; the canonical
        # query still fuses vector and full-text paths within a single SQL CTE.
        t_doc = time.perf_counter()
        retriever = DocumentHybridSearchRetriever(self.db_session)
        document_results = await retriever.hybrid_search(
            query_text=query_text,
            top_k=top_k,
            workspace_id=workspace_id,
            document_type=document_types,
            start_date=start_date,
            end_date=end_date,
            query_embedding=query_embedding,
            w_vector=w_vector,
            w_fts=w_fts,
            statuses=statuses,
        )
        perf.info(
            "[unified_search] corpus=document path=hybrid workspace_id=%d "
            "elapsed_ms=%.2f result_count=%d",
            workspace_id,
            (time.perf_counter() - t_doc) * 1000,
            len(document_results),
        )

        t_can = time.perf_counter()
        canonical_results = await self._canonical_hybrid_search(
            workspace_id=workspace_id,
            query_text=query_text,
            query_embedding=query_embedding,
            top_k=top_k,
            entity_types=entity_types,
            start_date=start_date,
            end_date=end_date,
            embedding_status=embedding_status,
            w_vector=w_vector,
            w_fts=w_fts,
        )
        perf.info(
            "[unified_search] corpus=canonical path=hybrid workspace_id=%d "
            "elapsed_ms=%.2f result_count=%d",
            workspace_id,
            (time.perf_counter() - t_can) * 1000,
            len(canonical_results),
        )

        # Record low-cardinality status counters without query PII.
        await self._record_embedding_status_counts(
            workspace_id, [c["embedding_status"] for c in canonical_results]
        )
        await self._check_outbox_failure_threshold(workspace_id)

        combined = await self._collapse_and_combine(
            workspace_id,
            document_results,
            canonical_results,
        )

        perf.info(
            "[unified_search] total elapsed_ms=%.2f workspace_id=%d result_count=%d",
            (time.perf_counter() - t0) * 1000,
            workspace_id,
            len(combined),
        )
        return combined

    async def _canonical_hybrid_search(
        self,
        *,
        workspace_id: int,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
        entity_types: list[str] | None,
        start_date: datetime | None,
        end_date: datetime | None,
        embedding_status: str | None,
        w_vector: float,
        w_fts: float,
    ) -> list[dict[str, Any]]:
        """Vector + full-text RRF over ``canonical_entities``.

        Rows with a stale, NULL or non-ready embedding are excluded from the
        vector CTE but remain eligible through the full-text CTE.
        """
        perf = get_perf_logger()
        t0 = time.perf_counter()

        k = _RRF_K
        n_results = top_k * 3  # ponytail: fetch extra for better fusion quality.
        current_model = _current_embedding_model()

        # ponytail: use the 'simple' text-search configuration so short token
        # codes (e.g. "By") are not dropped as English stop words.
        tsvector = func.to_tsvector("simple", CanonicalEntity.search_text)
        tsquery = func.plainto_tsquery("simple", query_text)

        base_conditions = [CanonicalEntity.workspace_id == workspace_id]

        if entity_types:
            base_conditions.append(CanonicalEntity.entity_type.in_(entity_types))
        if start_date is not None:
            base_conditions.append(CanonicalEntity.last_seen_at >= start_date)
        if end_date is not None:
            base_conditions.append(CanonicalEntity.last_seen_at <= end_date)
        if embedding_status is not None:
            base_conditions.append(CanonicalEntity.embedding_status == embedding_status)

        # Vector CTE: only current, ready embeddings are ranked.
        vector_conditions = [
            *base_conditions,
            CanonicalEntity.embedding.is_not(None),
            CanonicalEntity.embedding_model_name == current_model,
            CanonicalEntity.embedding_status == EmbeddingStatus.READY.value,
        ]

        semantic_search_cte = (
            select(
                CanonicalEntity.id,
                func.row_number()
                .over(
                    order_by=[
                        CanonicalEntity.embedding.op("<=>")(query_embedding),
                        CanonicalEntity.id,
                    ]
                )
                .label("rank"),
            )
            .where(*vector_conditions)
            .order_by(CanonicalEntity.embedding.op("<=>")(query_embedding))
            .limit(n_results)
            .cte("semantic_search")
        )

        # Full-text CTE: any row with matching search_text is eligible.
        keyword_search_cte = (
            select(
                CanonicalEntity.id,
                func.row_number()
                .over(
                    order_by=[
                        func.ts_rank_cd(tsvector, tsquery).desc(),
                        CanonicalEntity.id,
                    ]
                )
                .label("rank"),
            )
            .where(*base_conditions)
            .where(tsvector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(tsvector, tsquery).desc())
            .limit(n_results)
            .cte("keyword_search")
        )

        vector_ranks = {
            row.id: row.rank
            for row in (
                await self.db_session.execute(
                    select(semantic_search_cte.c.id, semantic_search_cte.c.rank)
                )
            ).all()
        }
        keyword_ranks = {
            row.id: row.rank
            for row in (
                await self.db_session.execute(
                    select(keyword_search_cte.c.id, keyword_search_cte.c.rank)
                )
            ).all()
        }

        candidate_ids = set(vector_ranks) | set(keyword_ranks)
        if not candidate_ids:
            return []

        # ponytail: fuse ranks in Python to avoid a complex single-query join
        # that is hard to get right across SQLAlchemy/PostgreSQL versions.
        scores = {
            entity_id: _rrf_score(
                rank_vector=vector_ranks.get(entity_id),
                rank_fts=keyword_ranks.get(entity_id),
                w_vector=w_vector,
                w_fts=w_fts,
                k=k,
            )
            for entity_id in candidate_ids
        }
        top_ids = sorted(
            candidate_ids,
            key=lambda entity_id: (-scores[entity_id], str(entity_id)),
        )[:top_k]

        entity_map = {
            row.id: row
            for row in (
                await self.db_session.execute(
                    select(
                        CanonicalEntity.id,
                        CanonicalEntity.entity_type,
                        CanonicalEntity.canonical_title,
                        CanonicalEntity.source_count,
                        CanonicalEntity.confidence_score,
                        CanonicalEntity.conflict_flags,
                        CanonicalEntity.version,
                        CanonicalEntity.last_seen_at,
                        CanonicalEntity.embedding_status,
                    )
                    .where(*base_conditions)
                    .where(CanonicalEntity.id.in_(top_ids))
                )
            ).all()
        }

        perf.info(
            "[unified_search] corpus=canonical path=hybrid workspace_id=%d elapsed_ms=%.2f",
            workspace_id,
            (time.perf_counter() - t0) * 1000,
        )

        return [
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "canonical_title": entity.canonical_title,
                "source_count": entity.source_count,
                "confidence_score": entity.confidence_score,
                "conflict_flags": entity.conflict_flags or [],
                "version": entity.version,
                "last_seen_at": entity.last_seen_at,
                "embedding_status": entity.embedding_status,
                "score": float(scores[entity_id]),
            }
            for entity_id in top_ids
            if (entity := entity_map.get(entity_id)) is not None
        ]

    async def _collapse_and_combine(
        self,
        workspace_id: int,
        document_results: list[dict[str, Any]],
        canonical_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Group linked documents under their canonical entity and merge lists."""
        canonical_map = {
            row["id"]: {**row, "source_ids": [], "linked_documents": []}
            for row in canonical_results
        }
        canonical_ids = set(canonical_map)

        # Load source identifiers for canonical entities in the result set.
        if canonical_ids:
            source_stmt = (
                select(
                    CanonicalEntitySource.id,
                    CanonicalEntitySource.canonical_entity_id,
                    CanonicalEntitySource.source_name,
                    CanonicalEntitySource.source_record_id,
                )
                .where(
                    CanonicalEntitySource.workspace_id == workspace_id,
                    CanonicalEntitySource.canonical_entity_id.in_(canonical_ids),
                )
                .order_by(CanonicalEntitySource.last_seen_at.desc())
            )
            source_rows = (await self.db_session.execute(source_stmt)).all()

            doc_id_to_canonical: dict[int, uuid.UUID] = {}
            for row in source_rows:
                canonical_map[row.canonical_entity_id]["source_ids"].append(row.id)
                if row.source_name == "document":
                    try:
                        doc_id = int(row.source_record_id)
                    except ValueError:
                        continue
                    doc_id_to_canonical[doc_id] = row.canonical_entity_id

            # Collapse linked documents.
            remaining_documents: list[dict[str, Any]] = []
            for doc in document_results:
                doc_id = doc.get("document_id")
                canonical_id = doc_id_to_canonical.get(doc_id)
                if canonical_id and canonical_id in canonical_map:
                    canonical_map[canonical_id]["linked_documents"].append(doc_id)
                else:
                    remaining_documents.append(doc)
        else:
            remaining_documents = document_results

        # Build canonical result groups.
        canonical_groups: list[dict[str, Any]] = []
        for entity_id in canonical_results:  # preserve RRF order
            entity = canonical_map[entity_id["id"]]
            canonical_groups.append(
                {
                    "type": "canonical_entity",
                    "score": entity["score"],
                    "entity": {
                        "id": entity["id"],
                        "entity_type": entity["entity_type"],
                        "canonical_title": entity["canonical_title"],
                        "source_count": max(
                            entity["source_count"], len(entity["source_ids"])
                        ),
                        "source_ids": entity["source_ids"],
                        "confidence_score": entity["confidence_score"],
                        "conflict_flags": entity["conflict_flags"],
                        "version": entity["version"],
                        "last_seen_at": entity["last_seen_at"],
                        "embedding_status": entity["embedding_status"],
                        "view_sources": {
                            "href": f"/canonical-entities/{entity['id']}/sources",
                            "count": max(
                                entity["source_count"], len(entity["source_ids"])
                            ),
                        },
                        "linked_documents": entity["linked_documents"],
                    },
                }
            )

        # Build document result groups for unmatched documents.
        document_groups: list[dict[str, Any]] = [
            {
                "type": "document",
                "score": doc["score"],
                "document": doc,
            }
            for doc in remaining_documents
        ]

        combined = canonical_groups + document_groups
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined

    async def _record_embedding_status_counts(
        self, workspace_id: int, statuses: list[str]
    ) -> None:
        """Log low-cardinality embedding status counters without query PII."""
        counts: dict[str, int] = {}
        for status in statuses:
            counts[status] = counts.get(status, 0) + 1
        if counts:
            get_perf_logger().info(
                "[unified_search] corpus=canonical path=vector workspace_id=%d "
                "embedding_status_counts=%s",
                workspace_id,
                counts,
            )

    async def _check_outbox_failure_threshold(self, workspace_id: int) -> None:
        """Emit an alert when canonical embedding outbox failures are high."""
        threshold = getattr(config, "CANONICAL_EMBEDDING_OUTBOX_FAILURE_THRESHOLD", 5)
        since = datetime.now(UTC) - timedelta(hours=1)
        stmt = (
            select(func.count())
            .select_from(CanonicalPersistOutbox)
            .where(
                CanonicalPersistOutbox.workspace_id == workspace_id,
                CanonicalPersistOutbox.status == "failed",
                CanonicalPersistOutbox.updated_at >= since,
            )
        )
        failed_count = (await self.db_session.scalar(stmt)) or 0
        if failed_count >= threshold:
            get_perf_logger().warning(
                "[unified_search_alert] corpus=canonical path=embedding_outbox "
                "workspace_id=%d failed_count=%d threshold=%d",
                workspace_id,
                failed_count,
                threshold,
            )
