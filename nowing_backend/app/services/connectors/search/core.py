"""Connector search service: cross-source file and document search."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    NATIVE_TO_LEGACY_DOCTYPE,
    Chunk,
    Document,
    SearchSourceConnector,
    SearchSourceConnectorType,
    async_session_maker,
)
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)


"""Core connector search primitives and generic file search."""


class ConnectorSearchCore:
    async def get_connector_by_type(
        self,
        connector_type: SearchSourceConnectorType,
        workspace_id: int,
    ) -> SearchSourceConnector | None:
        """
        Get a connector by type for a specific workspace

        Args:
            connector_type: The connector type to retrieve
            workspace_id: The workspace ID to filter by

        Returns:
            Optional[SearchSourceConnector]: The connector if found, None otherwise
        """
        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.workspace_id == workspace_id,
            SearchSourceConnector.connector_type == connector_type,
        )

        result = await self.session.execute(query)
        return result.scalars().first()
    def __init__(self, session: AsyncSession, workspace_id: int | None = None):
        self.session = session
        self.chunk_retriever = ChucksHybridSearchRetriever(session)
        self.document_retriever = DocumentHybridSearchRetriever(session)
        self.workspace_id = workspace_id
        self.source_id_counter = (
            100000  # High starting value to avoid collisions with existing IDs
        )
        self.counter_lock = (
            asyncio.Lock()
        )  # Lock to protect counter in multithreaded environments
    def _build_chunk_sources_from_documents(
        self,
        documents: list[dict[str, Any]],
        *,
        title_fn=None,
        description_fn=None,
        url_fn=None,
        extra_fields_fn=None,
    ) -> list[dict[str, Any]]:
        """
        Build a chunk-level `sources` list from document-grouped results.

        Each chunk becomes a source with `id == chunk_id` so the frontend can resolve
        citations like `[citation:<chunk_id>]`.
        """
        sources: list[dict[str, Any]] = []

        for doc in documents:
            doc_info = doc.get("document", {}) or {}
            metadata = doc_info.get("metadata", {}) or {}
            url = url_fn(doc_info, metadata) if url_fn else self._get_doc_url(metadata)
            chunks = doc.get("chunks", []) or []
            display_title = (
                title_fn(doc_info, metadata)
                if title_fn
                else doc_info.get("title", "Untitled Document")
            )
            for chunk in chunks:
                chunk_id = chunk.get("chunk_id")
                chunk_content = chunk.get("content", "")
                description = (
                    description_fn(chunk, doc_info, metadata)
                    if description_fn
                    else self._chunk_preview(chunk_content)
                )
                source = {
                    "id": chunk_id,
                    "title": display_title,
                    "description": description,
                    "url": url,
                }
                if extra_fields_fn:
                    source.update(extra_fields_fn(chunk, doc_info, metadata) or {})
                sources.append(source)
        return sources
    async def initialize_counter(self):
        """
        Initialize the source_id_counter based on the total number of chunks for the workspace.
        This ensures unique IDs across different sessions.
        """
        if self.workspace_id:
            try:
                # Count total chunks for documents belonging to this workspace

                result = await self.session.execute(
                    select(func.count(Chunk.id))
                    .join(Document)
                    .filter(Document.workspace_id == self.workspace_id)
                )
                chunk_count = result.scalar() or 0
                self.source_id_counter = chunk_count + 1
                logger.info(
                    "Initialized source_id_counter to %d for workspace %s",
                    self.source_id_counter,
                    self.workspace_id,
                )
            except SQLAlchemyError:
                logger.exception("Error initializing source_id_counter")
                # Fallback to default value when the database is unreachable or
                # the schema relationship is temporarily inconsistent.
                self.source_id_counter = 1
    async def search_files(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for files and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            workspace_id: The workspace ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        files_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="FILE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not files_docs:
            return {
                "id": 2,
                "name": "Files",
                "type": "FILE",
                "sources": [],
            }, []

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            return (
                metadata.get("og:description")
                or metadata.get("ogDescription")
                or self._chunk_preview(chunk.get("content", ""))
            )

        sources_list = self._build_chunk_sources_from_documents(
            files_docs,
            description_fn=_description_fn,
            url_fn=lambda _doc_info, metadata: metadata.get("url", "") or "",
        )

        # Create result object
        result_object = {
            "id": 2,
            "name": "Files",
            "type": "FILE",
            "sources": sources_list,
        }

        return result_object, files_docs
    def _get_doc_url(self, metadata: dict[str, Any]) -> str:
        return (
            metadata.get("url")
            or metadata.get("source")
            or metadata.get("page_url")
            or metadata.get("VisitedWebPageURL")
            or ""
        )
    async def _combined_rrf_search(
        self,
        query_text: str,
        workspace_id: int,
        document_type: str | list[str],
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform combined search using both chunk-based and document-based hybrid search,
        then merge results using Reciprocal Rank Fusion (RRF) **at the document level**.

        Returned results are **document-grouped** objects that contain a list of chunks
        with real chunk IDs (used for downstream `[citation:<chunk_id>]`).

        This method:
        1. Runs chunk-level hybrid search (vector + keyword on chunks)
        2. Runs document-level hybrid search (vector + keyword on documents, returns chunks)
        3. Combines results using RRF based on their ranks in each result set
        4. Returns top-k deduplicated results

        Args:
            query_text: The search query text
            workspace_id: The workspace ID to search within
            document_type: Document type(s) to filter (e.g., "FILE", "CRAWLED_URL",
                           or a list for multi-type queries)
            top_k: Number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            List of combined and deduplicated document results
        """
        from app.config import config

        perf = get_perf_logger()
        t0 = time.perf_counter()

        # Expand native Google types to include legacy Composio equivalents
        # so old documents remain searchable until re-indexed.
        if isinstance(document_type, str) and document_type in NATIVE_TO_LEGACY_DOCTYPE:
            resolved_type: str | list[str] = [
                document_type,
                NATIVE_TO_LEGACY_DOCTYPE[document_type],
            ]
        else:
            resolved_type = document_type

        # RRF constant
        k = 60

        # Get more results from each retriever for better fusion
        retriever_top_k = top_k * 2

        # Reuse caller-provided embedding or compute once for both retrievers.
        if query_embedding is None:
            t_embed = time.perf_counter()
            query_embedding = await asyncio.to_thread(
                config.embedding_model_instance.embed, query_text
            )
            perf.info(
                "[connector_svc] _combined_rrf embedding in %.3fs type=%s",
                time.perf_counter() - t_embed,
                document_type,
            )

        search_kwargs = {
            "query_text": query_text,
            "top_k": retriever_top_k,
            "workspace_id": workspace_id,
            "document_type": resolved_type,
            "start_date": start_date,
            "end_date": end_date,
            "query_embedding": query_embedding,
        }

        # Run chunk and document retrievers in parallel using separate DB sessions
        # so they don't contend on a shared AsyncSession connection.
        async def _run_chunk_search() -> list[dict[str, Any]]:
            async with async_session_maker() as session:
                retriever = ChucksHybridSearchRetriever(session)
                return await retriever.hybrid_search(**search_kwargs)

        async def _run_doc_search() -> list[dict[str, Any]]:
            async with async_session_maker() as session:
                retriever = DocumentHybridSearchRetriever(session)
                return await retriever.hybrid_search(**search_kwargs)

        t_parallel = time.perf_counter()
        chunk_results, doc_results = await asyncio.gather(
            _run_chunk_search(), _run_doc_search()
        )
        perf.info(
            "[connector_svc] _combined_rrf parallel retrievers in %.3fs "
            "chunk_results=%d doc_results=%d type=%s",
            time.perf_counter() - t_parallel,
            len(chunk_results),
            len(doc_results),
            document_type,
        )

        if not chunk_results and not doc_results:
            return []

        # Helper to extract document_id from our doc-grouped result
        def _doc_id(item: dict[str, Any]) -> int | None:
            doc = item.get("document", {})
            did = doc.get("id")
            return int(did) if did is not None else None

        # Build rank maps for RRF calculation (document-level)
        chunk_ranks: dict[int, int] = {}
        for rank, result in enumerate(chunk_results, start=1):
            did = _doc_id(result)
            if did is not None and did not in chunk_ranks:
                chunk_ranks[did] = rank

        doc_ranks: dict[int, int] = {}
        for rank, result in enumerate(doc_results, start=1):
            did = _doc_id(result)
            if did is not None and did not in doc_ranks:
                doc_ranks[did] = rank

        all_doc_ids = set(chunk_ranks.keys()) | set(doc_ranks.keys())

        # Calculate RRF scores for each document
        rrf_scores: dict[int, float] = {}
        for did in all_doc_ids:
            chunk_rank = chunk_ranks.get(did)
            doc_rank = doc_ranks.get(did)
            score = 0.0
            if chunk_rank is not None:
                score += 1.0 / (k + chunk_rank)
            if doc_rank is not None:
                score += 1.0 / (k + doc_rank)
            rrf_scores[did] = score

        # Prefer chunk_results data, fallback to doc_results data
        doc_data: dict[int, dict[str, Any]] = {}
        for result in chunk_results:
            did = _doc_id(result)
            if did is not None and did not in doc_data:
                doc_data[did] = result
        for result in doc_results:
            did = _doc_id(result)
            if did is not None and did not in doc_data:
                doc_data[did] = result

        sorted_doc_ids = sorted(
            all_doc_ids, key=lambda did: rrf_scores[did], reverse=True
        )[:top_k]

        combined_results: list[dict[str, Any]] = []
        for did in sorted_doc_ids:
            if did in doc_data:
                result = doc_data[did].copy()
                result["document_id"] = did
                result["score"] = rrf_scores[did]
                # Preserve chunks list if present
                if "chunks" in doc_data[did]:
                    result["chunks"] = doc_data[did]["chunks"]
                combined_results.append(result)

        perf.info(
            "[connector_svc] _combined_rrf_search TOTAL in %.3fs results=%d type=%s space=%d",
            time.perf_counter() - t0,
            len(combined_results),
            document_type,
            workspace_id,
        )
        return combined_results
    def _chunk_preview(self, text: str, limit: int = 200) -> str:
        if not text:
            return ""
        text = str(text)
        if len(text) <= limit:
            return text
        return text[:limit] + "..."
