"""Nowing private data provider for chainlens-research (Story 20.3).

This service searches the workspace's own ``Document``/``Chunk``/``Memory`` KB
and returns typed ``PrivateProviderChunk`` results. It never calls live
connector APIs and never exposes OAuth credentials.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.canonical.tenant_context import set_request_tenant_context
from app.config import config
from app.db import Document, SearchSourceConnector, Workspace
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
    PrivateProviderChunk,
    PrivateProviderChunkMetadata,
)
from app.services.memory.search import MemoryHybridSearch

logger = logging.getLogger(__name__)

# Small, fixed fallback top-k so private search stays cheap and bounded.
_MAX_DOC_RESULTS = 5
_MAX_CHUNK_RESULTS_PER_DOC = 3
_MAX_MEMORY_RESULTS = 3


class PrivateProviderService:
    """Search a workspace's private knowledge base for chainlens-research."""

    def __init__(self, session):
        self.session = session
        self._chunk_retriever = ChucksHybridSearchRetriever(session)
        self._document_retriever = DocumentHybridSearchRetriever(session)

    async def search(
        self,
        request: PrivateDataSearchRequest,
        workspace: Workspace,
    ) -> PrivateDataSearchResponse:
        """Run a private search and return a typed, cost-attributed response."""
        workspace_id = workspace.id

        # Resolve a requested userId if the user is a member of the workspace;
        # otherwise keep it as audit-only metadata and use the workspace owner.
        effective_user_id = (
            request.userId
            if await self._is_workspace_member(request.userId, workspace_id)
            else workspace.user_id
        )

        # Set tenant GUCs for all downstream queries.
        await set_request_tenant_context(
            self.session,
            workspace_id=workspace_id,
            client_id=None,
            user_id=str(effective_user_id) if effective_user_id else None,
        )

        # Resolve document type filter from ``sources``/``connectorId``.
        document_type = await self._resolve_document_type(request)

        # Compute a shared query embedding once for both retrievers.
        query_embedding = await asyncio.to_thread(
            config.embedding_model_instance.embed, request.query
        )

        # Search documents and chunks in parallel, both scoped by workspace.
        chunk_results, doc_results = await self._run_retrievers(
            query_text=request.query,
            top_k=_MAX_DOC_RESULTS,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
        )

        # Search workspace memory as a secondary source.
        memory_results = await self._search_memory(
            query=request.query,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
        )

        # Retrievers don't return connector_id or updated_at, so load them
        # in one batched query for the documents we will surface.
        doc_meta = await self._load_document_meta(chunk_results, doc_results)

        # Merge, deduplicate by chunk id, and build typed chunks.
        chunks = self._build_chunks(
            request=request,
            chunk_results=chunk_results,
            doc_results=doc_results,
            memory_results=memory_results,
            workspace=workspace,
            connector_id=request.connectorId,
            doc_meta=doc_meta,
        )

        # Respect caller's topK while guaranteeing a stable shape.
        if len(chunks) > request.topK:
            chunks = chunks[: request.topK]

        return PrivateDataSearchResponse(chunks=chunks, costDollars=0.0)

    async def _is_workspace_member(
        self, user_id: UUID | None, workspace_id: int
    ) -> bool:
        """Return ``True`` if ``user_id`` is an explicit member of the workspace."""
        if user_id is None:
            return False
        from app.db import WorkspaceMembership

        result = await self.session.execute(
            select(WorkspaceMembership.id).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        return result.scalar() is not None

    async def _resolve_document_type(
        self, request: PrivateDataSearchRequest
    ) -> str | list[str] | None:
        """Map ``sources`` or ``connectorId`` to a ``DocumentType`` filter."""
        if request.connectorId is not None:
            connector = await self.session.execute(
                select(SearchSourceConnector).where(
                    SearchSourceConnector.id == request.connectorId,
                    SearchSourceConnector.workspace_id == request.workspaceId,
                )
            )
            connector = connector.scalars().first()
            if connector is not None:
                return connector.connector_type.value
            # Connector requested but not found: empty result is the safe default.
            logger.warning(
                "connector_id=%d not found in workspace %d; private search will return empty",
                request.connectorId,
                request.workspaceId,
            )
            return []

        if request.sources:
            # Treat source names as connector type values or document types.
            from app.db import DocumentType

            mapped: list[str] = []
            for source in request.sources:
                source = source.strip().upper()
                if not source:
                    continue
                try:
                    mapped.append(DocumentType[source].value)
                except KeyError:
                    # Unknown source names are ignored rather than failing hard.
                    logger.debug("unknown source filter: %r", source)
            if not mapped:
                return None
            return mapped if len(mapped) > 1 else mapped[0]

        return None

    async def _run_retrievers(
        self,
        *,
        query_text: str,
        top_k: int,
        workspace_id: int,
        document_type: str | list[str] | None,
        query_embedding: list[float],
    ) -> tuple[list[dict], list[dict]]:
        """Run chunk and document hybrid searches in parallel."""
        chunk_task = self._chunk_retriever.hybrid_search(
            query_text=query_text,
            top_k=top_k,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
        )
        doc_task = self._document_retriever.hybrid_search(
            query_text=query_text,
            top_k=top_k,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
        )
        return await asyncio.gather(chunk_task, doc_task)

    async def _search_memory(
        self,
        *,
        query: str,
        workspace_id: int,
        query_embedding: list[float],
    ) -> list:
        """Search workspace-scoped memory."""
        search = MemoryHybridSearch(self.session)
        try:
            return await search.search(
                workspace_id=workspace_id,
                user_id=None,
                query=query,
                query_embedding=query_embedding,
                top_k=_MAX_MEMORY_RESULTS,
            )
        except Exception:
            logger.warning(
                "Memory search failed for workspace %d", workspace_id, exc_info=True
            )
            return []

    async def _load_document_meta(
        self,
        chunk_results: list[dict],
        doc_results: list[dict],
    ) -> dict[int, dict]:
        """Load connector_id and updated_at for all candidate documents."""
        doc_ids: set[int] = set()
        for doc_group in chunk_results + doc_results:
            doc_info = doc_group.get("document") or {}
            doc_id = doc_info.get("id")
            if doc_id is not None:
                doc_ids.add(doc_id)

        if not doc_ids:
            return {}

        rows = await self.session.execute(
            select(Document.id, Document.connector_id, Document.updated_at).where(
                Document.id.in_(doc_ids)
            )
        )
        return {
            row.id: {"connector_id": row.connector_id, "updated_at": row.updated_at}
            for row in rows
        }

    def _build_chunks(
        self,
        *,
        request: PrivateDataSearchRequest,
        chunk_results: list[dict],
        doc_results: list[dict],
        memory_results: list,
        workspace: Workspace,
        connector_id: int | None,
        doc_meta: dict[int, dict],
    ) -> list[PrivateProviderChunk]:
        """Merge retriever outputs and map them to the response chunk schema."""
        seen: set[int] = set()
        chunks: list[PrivateProviderChunk] = []

        def add_doc_chunks(doc_group: dict) -> None:
            doc_info = doc_group.get("document") or {}
            doc_id = doc_info.get("id")
            if doc_id is None:
                return

            # Connector-scoped search: exact connector_id match wins.
            if (
                connector_id is not None
                and doc_meta.get(doc_id, {}).get("connector_id") != connector_id
            ):
                return

            doc_title = doc_info.get("title") or "Untitled Document"
            doc_type = doc_info.get("document_type") or "private_provider"
            extra_meta = doc_meta.get(doc_id, {})
            fetched_at = self._format_ts(extra_meta.get("updated_at"))

            for chunk in (doc_group.get("chunks") or [])[:_MAX_CHUNK_RESULTS_PER_DOC]:
                if len(chunks) >= request.topK:
                    return
                chunk_id = chunk.get("chunk_id")
                if chunk_id is None or chunk_id in seen:
                    continue
                seen.add(chunk_id)
                content = chunk.get("content", "")
                if not content.strip():
                    continue
                chunks.append(
                    self._make_chunk(
                        content=content,
                        doc_id=doc_id,
                        chunk_id=chunk_id,
                        doc_title=doc_title,
                        doc_type=doc_type,
                        fetched_at=fetched_at,
                        workspace_id=workspace.id,
                        connector_id=connector_id,
                    )
                )

        # Process chunk-level results first (more precise citations).
        for doc_group in chunk_results:
            if len(chunks) >= request.topK:
                break
            add_doc_chunks(doc_group)

        # Then document-level results for any additional doc hits.
        for doc_group in doc_results:
            if len(chunks) >= request.topK:
                break
            add_doc_chunks(doc_group)

        # Finally add memory results if still under topK.
        for scored in memory_results:
            if len(chunks) >= request.topK:
                break
            memory = scored.memory
            if not memory.content.strip():
                continue
            memory_id = memory.id
            if memory_id in seen:
                continue
            seen.add(memory_id)
            source_id = f"nowing://workspaces/{workspace.id}/memories/{memory.id}"
            chunks.append(
                PrivateProviderChunk(
                    content=memory.content,
                    metadata=PrivateProviderChunkMetadata(
                        source="private_provider",
                        sourceId=source_id,
                        domain="nowing",
                        fetchedAt=self._format_ts(
                            memory.updated_at or memory.created_at
                        ),
                        contentType=memory.type.value if memory.type else "memory",
                        title="Memory",
                        url=source_id,
                        document_id=None,
                        chunk_id=memory.id,
                        connector_id=None,
                        workspace_id=workspace.id,
                    ),
                )
            )

        return chunks

    def _make_chunk(
        self,
        *,
        content: str,
        doc_id: int,
        chunk_id: int,
        doc_title: str,
        doc_type: str,
        fetched_at: str,
        workspace_id: int,
        connector_id: int | None,
    ) -> PrivateProviderChunk:
        """Build a single ``PrivateProviderChunk`` from a chunk and its document."""
        if connector_id is not None:
            source_id = f"nowing://connectors/{connector_id}/documents/{doc_id}/chunks/{chunk_id}"
        else:
            source_id = f"nowing://documents/{doc_id}/chunks/{chunk_id}"

        return PrivateProviderChunk(
            content=content,
            metadata=PrivateProviderChunkMetadata(
                source="private_provider",
                sourceId=source_id,
                domain="nowing",
                fetchedAt=fetched_at,
                contentType=doc_type,
                title=doc_title,
                url=source_id,
                document_id=doc_id,
                chunk_id=chunk_id,
                connector_id=connector_id,
                workspace_id=workspace_id,
            ),
        )

    @staticmethod
    def _format_ts(value) -> str:
        """Return an ISO 8601 string for a datetime value."""
        if value is None:
            return datetime.now(UTC).isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
