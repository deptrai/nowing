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
from app.db import (
    NATIVE_TO_LEGACY_DOCTYPE,
    Document,
    SearchSourceConnector,
    Workspace,
)
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.retriever.documents_hybrid_search import DocumentHybridSearchRetriever
from app.services.chainlens.schemas import (
    PrivateDataSearchRequest,
    PrivateDataSearchResponse,
    PrivateProviderChunk,
    PrivateProviderChunkMetadata,
)
from app.services.memory.search import MemoryHybridSearch, ScoredMemory
from app.services.token_tracking_service import UsageType, record_token_usage
from app.utils.document_converters import embed_text

logger = logging.getLogger(__name__)

# Maps ``SearchSourceConnectorType`` enum values to the primary searchable
# ``DocumentType`` that retrievers understand.  ``None`` means the connector does
# not have a single matching document type (e.g. generic MCP) and should not be
# pre-filtered by document type.  Legacy equivalents are added by
# ``_expand_document_type`` at resolution time.
_CONNECTOR_TYPE_TO_DOC_TYPE: dict[str, str | None] = {
    "SLACK_CONNECTOR": "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR": "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR": "NOTION_CONNECTOR",
    "GITHUB_CONNECTOR": "GITHUB_CONNECTOR",
    "LINEAR_CONNECTOR": "LINEAR_CONNECTOR",
    "DISCORD_CONNECTOR": "DISCORD_CONNECTOR",
    "JIRA_CONNECTOR": "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR": "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR": "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "AIRTABLE_CONNECTOR": "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR": "LUMA_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR": "ELASTICSEARCH_CONNECTOR",
    "WEBCRAWLER_CONNECTOR": "CRAWLED_URL",
    "BOOKSTACK_CONNECTOR": "BOOKSTACK_CONNECTOR",
    "CIRCLEBACK_CONNECTOR": "CIRCLEBACK",
    "OBSIDIAN_CONNECTOR": "OBSIDIAN_CONNECTOR",
    "DROPBOX_CONNECTOR": "DROPBOX_FILE",
    "ONEDRIVE_CONNECTOR": "ONEDRIVE_FILE",
    "MCP_CONNECTOR": None,
    "EXA_MCP_CONNECTOR": None,
    "RSS_FEED": "NEWS_CONNECTOR",
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "COMPOSIO_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
}


def _expand_document_type(doc_type: str) -> list[str]:
    """Return ``doc_type`` plus its legacy Composio equivalent, if any."""
    expanded: set[str] = {doc_type}
    if doc_type in NATIVE_TO_LEGACY_DOCTYPE:
        expanded.add(NATIVE_TO_LEGACY_DOCTYPE[doc_type])
    for native, legacy in NATIVE_TO_LEGACY_DOCTYPE.items():
        if legacy == doc_type:
            expanded.add(native)
    return list(expanded)


def _map_source_to_document_types(source: str) -> list[str] | None:
    """Map a connector-type or document-type name to searchable document types.

    If ``source`` is a known ``SearchSourceConnectorType`` enum value, translate
    it to the matching ``DocumentType`` and expand to legacy equivalents.
    If ``source`` is itself a ``DocumentType`` name, expand to its legacy/native
    equivalent.  Return ``None`` for values that do not map to a known document
    type (e.g. generic MCP connectors when used as a ``sources`` filter).
    """
    from app.db import DocumentType

    if source in _CONNECTOR_TYPE_TO_DOC_TYPE:
        doc_type = _CONNECTOR_TYPE_TO_DOC_TYPE[source]
        if doc_type is None:
            return None
        return _expand_document_type(doc_type)

    try:
        _ = DocumentType[source]
    except KeyError:
        logger.debug("unknown source filter: %r", source)
        return None
    return _expand_document_type(source)


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
        *,
        correlation_id: str | None = None,
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
        document_type = await self._resolve_document_type(request, workspace_id)

        # Any requested filter that resolves to an empty set should return empty.
        if document_type == []:
            await self._record_usage(
                workspace_id=workspace_id,
                user_id=effective_user_id,
                request=request,
                correlation_id=correlation_id,
            )
            return PrivateDataSearchResponse(chunks=[], costDollars=0.0)

        # Compute a shared query embedding once for both retrievers.
        # Use the helper that truncates to the model's context window and holds
        # the embedding lock for non-thread-safe local models.
        raw_embedding = await asyncio.to_thread(embed_text, request.query)
        query_embedding = (
            raw_embedding.tolist()
            if hasattr(raw_embedding, "tolist")
            else raw_embedding
        )

        # Search documents and chunks sequentially on the same session.
        chunk_results, doc_results = await self._run_retrievers(
            query_text=request.query,
            top_k=request.topK,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
        )

        # Search workspace memory as a primary source; optionally add the
        # requested user's personal memory if the user is a workspace member.
        # Memory is not connector-scoped, so skip it when a connectorId is given.
        memory_results: list[ScoredMemory] = []
        if request.connectorId is None:
            memory_results = await self._search_memory(
                query=request.query,
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                user_id=effective_user_id
                if request.userId == effective_user_id
                else None,
                top_k=request.topK,
            )

        # Ensure tenant context is restored for batched document metadata load.
        await set_request_tenant_context(
            self.session,
            workspace_id=workspace_id,
            client_id=None,
            user_id=str(effective_user_id) if effective_user_id else None,
        )

        # Retrievers don't return connector_id or updated_at, so load them
        # in one batched query for the documents we will surface.
        doc_meta = await self._load_document_meta(
            chunk_results, doc_results, workspace_id=workspace_id
        )

        # Merge, deduplicate by chunk id, and build typed chunks.
        chunks = self._build_chunks(
            request=request,
            chunk_results=chunk_results,
            doc_results=doc_results,
            memory_results=memory_results,
            workspace=workspace,
            request_connector_id=request.connectorId,
            doc_meta=doc_meta,
        )

        # Respect caller's topK while guaranteeing a stable shape.
        if len(chunks) > request.topK:
            chunks = chunks[: request.topK]

        await self._record_usage(
            workspace_id=workspace_id,
            user_id=effective_user_id,
            request=request,
            correlation_id=correlation_id,
        )

        return PrivateDataSearchResponse(chunks=chunks, costDollars=0.0)

    async def _record_usage(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        request: PrivateDataSearchRequest,
        correlation_id: str | None,
    ) -> None:
        """Persist a zero-cost ``TokenUsage`` row for the search."""
        await record_token_usage(
            self.session,
            usage_type=UsageType.CHAINLENS_PRIVATE_SEARCH,
            workspace_id=workspace_id,
            user_id=user_id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=0,
            call_details={
                "correlation_id": correlation_id,
                "query": request.query,
                "connector_id": request.connectorId,
                "sources": request.sources,
                "requested_user_id": str(request.userId) if request.userId else None,
            },
        )

    async def _is_workspace_member(
        self, user_id: UUID | None, workspace_id: int
    ) -> bool:
        """Return ``True`` if ``user_id`` is an active, explicit member."""
        if user_id is None:
            return False
        from app.db import User, WorkspaceMembership

        result = await self.session.execute(
            select(WorkspaceMembership.id)
            .join(User, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
                User.is_active.is_(True),
            )
        )
        return result.scalar() is not None

    async def _resolve_document_type(
        self,
        request: PrivateDataSearchRequest,
        workspace_id: int,
    ) -> list[str] | None:
        """Map ``sources`` and/or ``connectorId`` to a ``DocumentType`` filter.

        Returns ``None`` when no filter is requested; ``[]`` when the requested
        filter cannot be resolved (so the search safely returns empty); or a
        list of one or more ``DocumentType`` values to pass to the retrievers.
        When both ``connectorId`` and ``sources`` are supplied, the result is
        the intersection of the connector's type and the explicit sources, with
        the connector_id filter in ``_build_chunks`` still applied.
        """
        connector_doc_types = await self._resolve_connector_document_types(
            request, workspace_id
        )
        source_doc_types = self._resolve_source_document_types(request)

        if connector_doc_types == [] or source_doc_types == []:
            return []
        if connector_doc_types is None and source_doc_types is None:
            return None
        if connector_doc_types is None:
            return source_doc_types
        if source_doc_types is None:
            return connector_doc_types

        # Both supplied: restrict the search to the overlap, if any.
        intersection = [
            dt for dt in connector_doc_types if dt in source_doc_types
        ]
        if not intersection:
            return []
        return intersection

    async def _resolve_connector_document_types(
        self,
        request: PrivateDataSearchRequest,
        workspace_id: int,
    ) -> list[str] | None:
        """Resolve the document types for a connector-scoped search.

        ``None`` means no connector was requested (or the connector has no
        matching document type and should not be pre-filtered by type).
        ``[]`` means the connector was requested but does not exist.
        """
        if request.connectorId is None:
            return None

        connector_type = await self.session.scalar(
            select(SearchSourceConnector.connector_type).where(
                SearchSourceConnector.id == request.connectorId,
                SearchSourceConnector.workspace_id == workspace_id,
            )
        )
        if connector_type is None:
            logger.warning(
                "connector_id=%d not found in workspace %d; private search will return empty",
                request.connectorId,
                workspace_id,
            )
            return []

        connector_value = (
            connector_type.value
            if hasattr(connector_type, "value")
            else str(connector_type)
        )
        return _map_source_to_document_types(connector_value)

    def _resolve_source_document_types(
        self,
        request: PrivateDataSearchRequest,
    ) -> list[str] | None:
        """Resolve the document types for an explicit ``sources`` list.

        ``None`` means no sources were requested; ``[]`` means all supplied
        sources were unknown.
        """
        if not request.sources:
            return None

        mapped: list[str] = []
        seen: set[str] = set()
        for source in request.sources:
            source = source.strip().upper()
            if not source:
                continue
            doc_types = _map_source_to_document_types(source)
            if doc_types:
                for dt in doc_types:
                    if dt not in seen:
                        seen.add(dt)
                        mapped.append(dt)
        if not mapped:
            return []
        return mapped

    async def _run_retrievers(
        self,
        *,
        query_text: str,
        top_k: int,
        workspace_id: int,
        document_type: list[str] | None,
        query_embedding: list[float],
    ) -> tuple[list[dict], list[dict]]:
        """Run chunk and document hybrid searches sequentially on one session.

        ``AsyncSession`` cannot execute statements concurrently on a single
        connection, so we await the retrievers one at a time.
        """
        chunk_results = await self._chunk_retriever.hybrid_search(
            query_text=query_text,
            top_k=top_k,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
            statuses=["ready"],
        )
        doc_results = await self._document_retriever.hybrid_search(
            query_text=query_text,
            top_k=top_k,
            workspace_id=workspace_id,
            document_type=document_type,
            query_embedding=query_embedding,
            statuses=["ready"],
        )
        return chunk_results, doc_results

    async def _search_memory(
        self,
        *,
        query: str,
        workspace_id: int,
        query_embedding: list[float],
        user_id: UUID | None,
        top_k: int,
    ) -> list[ScoredMemory]:
        """Search workspace memory and, for a valid member, their personal memory."""
        # MemoryHybridSearch enforces top_k <= 5 internally.
        search = MemoryHybridSearch(self.session)
        memory_top_k = min(top_k, 5)
        try:
            results: list[ScoredMemory] = await search.search(
                workspace_id=workspace_id,
                user_id=None,
                query=query,
                query_embedding=query_embedding,
                top_k=memory_top_k,
            )
        except Exception:
            logger.warning(
                "Memory search failed for workspace %d", workspace_id, exc_info=True
            )
            results = []

        if user_id is not None:
            try:
                user_results = await search.search(
                    workspace_id=None,
                    user_id=user_id,
                    query=query,
                    query_embedding=query_embedding,
                    top_k=memory_top_k,
                )
            except Exception:
                logger.warning(
                    "User-scoped memory search failed for user %s in workspace %d",
                    user_id,
                    workspace_id,
                    exc_info=True,
                )
                user_results = []

            results.extend(
                scored
                for scored in user_results
                if scored.memory.id not in {m.memory.id for m in results}
            )

            # Sort by relevance so higher-scored memories are kept when slicing.
            results = sorted(
                results, key=lambda scored: scored.score or 0.0, reverse=True
            )[:top_k]

        return results

    async def _load_document_meta(
        self,
        chunk_results: list[dict],
        doc_results: list[dict],
        workspace_id: int,
    ) -> dict[int, dict]:
        """Load connector_id and timestamps for all candidate documents."""
        doc_ids: set[int] = set()
        for doc_group in chunk_results + doc_results:
            doc_info = doc_group.get("document") or {}
            doc_id = doc_info.get("id")
            if doc_id is not None:
                doc_ids.add(doc_id)

        if not doc_ids:
            return {}

        rows = await self.session.execute(
            select(
                Document.id,
                Document.connector_id,
                Document.updated_at,
                Document.created_at,
            ).where(
                Document.id.in_(doc_ids),
                Document.workspace_id == workspace_id,
            )
        )
        return {
            row.id: {
                "connector_id": row.connector_id,
                "updated_at": row.updated_at,
                "created_at": row.created_at,
            }
            for row in rows
        }

    def _build_chunks(
        self,
        *,
        request: PrivateDataSearchRequest,
        chunk_results: list[dict],
        doc_results: list[dict],
        memory_results: list[ScoredMemory],
        workspace: Workspace,
        request_connector_id: int | None,
        doc_meta: dict[int, dict],
    ) -> list[PrivateProviderChunk]:
        """Merge retriever outputs and map them to the response chunk schema."""
        seen: set[tuple[str, int]] = set()
        chunks: list[PrivateProviderChunk] = []

        def add_doc_chunks(doc_group: dict) -> None:
            doc_info = doc_group.get("document") or {}
            doc_id = doc_info.get("id")
            if doc_id is None:
                return

            extra_meta = doc_meta.get(doc_id, {})
            doc_connector_id = extra_meta.get("connector_id")

            # Connector-scoped search: exact connector_id match wins.
            if (
                request_connector_id is not None
                and doc_connector_id != request_connector_id
            ):
                return

            doc_title = doc_info.get("title") or "Untitled Document"
            doc_type = doc_info.get("document_type") or "private_provider"
            fetched_at = self._format_ts(
                extra_meta.get("updated_at"), extra_meta.get("created_at")
            )

            for chunk in (doc_group.get("chunks") or [])[: request.topK]:
                if len(chunks) >= request.topK:
                    return
                chunk_id = chunk.get("chunk_id")
                if chunk_id is None or ("chunk", chunk_id) in seen:
                    continue
                seen.add(("chunk", chunk_id))
                content = chunk.get("content") or ""
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
                        connector_id=doc_connector_id,
                    )
                )

        # Merge chunk- and document-level hits into one ranked list by the
        # retriever's document score, then build chunks in that order.
        all_doc_groups = sorted(
            chunk_results + doc_results,
            key=lambda group: float(group.get("score") or 0.0),
            reverse=True,
        )
        for doc_group in all_doc_groups:
            if len(chunks) >= request.topK:
                break
            add_doc_chunks(doc_group)

        # Finally add memory results if still under topK.
        # Memory is not a connector-backed document, so skip when connectorId is set.
        if request_connector_id is None:
            for scored in memory_results:
                if len(chunks) >= request.topK:
                    break
                memory = scored.memory
                if not (memory.content or "").strip():
                    continue
                memory_id = memory.id
                if ("memory", memory_id) in seen:
                    continue
                seen.add(("memory", memory_id))
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
        document_url = f"nowing://documents/{doc_id}/chunks/{chunk_id}"
        if connector_id is not None:
            source_id = f"nowing://connectors/{connector_id}/documents/{doc_id}/chunks/{chunk_id}"
        else:
            source_id = document_url

        return PrivateProviderChunk(
            content=content,
            metadata=PrivateProviderChunkMetadata(
                source="private_provider",
                sourceId=source_id,
                domain="nowing",
                fetchedAt=fetched_at,
                contentType=doc_type,
                title=doc_title,
                url=document_url,
                document_id=doc_id,
                chunk_id=chunk_id,
                connector_id=connector_id,
                workspace_id=workspace_id,
            ),
        )

    @staticmethod
    def _format_ts(value, fallback=None) -> str:
        """Return an ISO 8601 string for a datetime value.

        If ``value`` is missing and a ``fallback`` is provided, use it;
        otherwise use the current UTC time as a last-resort default.
        """
        if value is None:
            value = fallback
        if value is None:
            return datetime.now(UTC).isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
