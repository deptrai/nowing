"""Connector search service: cross-source file and document search."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


"""Search methods for storage and archive connectors."""


class StorageSearchMixin:
    async def search_circleback(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Circleback meeting notes and return both the source information and langchain documents.

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
        circleback_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="CIRCLEBACK",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not circleback_docs:
            return {
                "id": 52,
                "name": "Circleback Meetings",
                "type": "CIRCLEBACK",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            meeting_name = metadata.get("meeting_name", "")
            meeting_date = metadata.get("meeting_date", "")
            title = doc_info.get("title") or meeting_name or "Circleback Meeting"
            if meeting_date:
                title += f" ({meeting_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            meeting_id = metadata.get("circleback_meeting_id", "")
            return (
                f"https://app.circleback.ai/meetings/{meeting_id}" if meeting_id else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            duration = metadata.get("duration_seconds")
            attendee_count = metadata.get("attendee_count")
            if duration:
                minutes = int(duration) // 60
                info_parts.append(f"Duration: {minutes} min")
            if attendee_count:
                info_parts.append(f"Attendees: {attendee_count}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "circleback_meeting_id": metadata.get("circleback_meeting_id", ""),
                "meeting_name": metadata.get("meeting_name", ""),
                "meeting_date": metadata.get("meeting_date", ""),
                "duration_seconds": metadata.get("duration_seconds", 0),
                "attendee_count": metadata.get("attendee_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            circleback_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 52,
            "name": "Circleback Meetings",
            "type": "CIRCLEBACK",
            "sources": sources_list,
        }

        return result_object, circleback_docs
    async def search_bookstack(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for BookStack pages and return both the source information and langchain documents.

        Uses combined chunk-level and document-level hybrid search with RRF fusion.

        Args:
            user_query: The user's query
            user_id: The user's ID
            workspace_id: The workspace ID to search in
            top_k: Maximum number of results to return
            start_date: Optional start date for filtering documents by updated_at
            end_date: Optional end date for filtering documents by updated_at

        Returns:
            tuple: (sources_info, langchain_documents)
        """
        bookstack_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="BOOKSTACK_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not bookstack_docs:
            return {
                "id": 50,
                "name": "BookStack",
                "type": "BOOKSTACK_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_name = metadata.get("page_name", "Untitled Page")
            return page_name

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_slug = metadata.get("page_slug", "")
            book_slug = metadata.get("book_slug", "")
            base_url = metadata.get("base_url", "")
            page_url = metadata.get("page_url", "")
            if page_url:
                return page_url
            if base_url and book_slug and page_slug:
                return f"{base_url}/books/{book_slug}/page/{page_slug}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            bookstack_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 50,  # Assign a unique ID for the BookStack connector
            "name": "BookStack",
            "type": "BOOKSTACK_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, bookstack_docs
    async def search_obsidian(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Obsidian vault notes and return both the source information and langchain documents.

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
        obsidian_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="OBSIDIAN_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not obsidian_docs:
            return {
                "id": 53,
                "name": "Obsidian Vault",
                "type": "OBSIDIAN_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return doc_info.get("title", "Untitled Note")

        def _url_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            # Obsidian URL format: obsidian://vault_name/path
            return doc_info.get("url", "")

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=200)
            info_parts = []
            vault_name = metadata.get("vault_name")
            tags = metadata.get("tags", [])
            if vault_name:
                info_parts.append(f"Vault: {vault_name}")
            if tags and isinstance(tags, list) and len(tags) > 0:
                info_parts.append(f"Tags: {', '.join(tags[:3])}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "vault_name": metadata.get("vault_name", ""),
                "file_path": metadata.get("file_path", ""),
                "tags": metadata.get("tags", []),
                "outgoing_links": metadata.get("outgoing_links", []),
            }

        sources_list = self._build_chunk_sources_from_documents(
            obsidian_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 53,
            "name": "Obsidian Vault",
            "type": "OBSIDIAN_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, obsidian_docs
    async def search_notes(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Notes and return both the source information and langchain documents.

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
        notes_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="NOTE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not notes_docs:
            return {
                "id": 51,
                "name": "Notes",
                "type": "NOTE",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return doc_info.get("title", "Untitled Note")

        def _url_fn(_doc_info: dict[str, Any], _metadata: dict[str, Any]) -> str:
            return ""  # Notes don't have URLs

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], _metadata: dict[str, Any]
        ) -> str:
            return self._chunk_preview(chunk.get("content", ""), limit=200)

        sources_list = self._build_chunk_sources_from_documents(
            notes_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
        )

        # Create result object
        result_object = {
            "id": 51,
            "name": "Notes",
            "type": "NOTE",
            "sources": sources_list,
        }

        return result_object, notes_docs
    async def search_elasticsearch(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Elasticsearch documents and return both the source information and langchain documents.

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
        elasticsearch_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="ELASTICSEARCH_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not elasticsearch_docs:
            return {
                "id": 34,
                "name": "Elasticsearch",
                "type": "ELASTICSEARCH_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            title = doc_info.get("title", "Elasticsearch Document")
            es_index = metadata.get("elasticsearch_index", "")
            return f"{title} (Index: {es_index})" if es_index else title

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""), limit=150)
            info_parts = []
            if metadata.get("elasticsearch_id"):
                info_parts.append(f"ID: {metadata.get('elasticsearch_id')}")
            if metadata.get("elasticsearch_score"):
                info_parts.append(f"Score: {metadata.get('elasticsearch_score')}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "elasticsearch_id": metadata.get("elasticsearch_id", ""),
                "elasticsearch_index": metadata.get("elasticsearch_index", ""),
                "elasticsearch_score": metadata.get("elasticsearch_score", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            elasticsearch_docs,
            title_fn=_title_fn,
            url_fn=lambda _doc_info, _metadata: "",
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 34,  # Assign a unique ID for the Elasticsearch connector
            "name": "Elasticsearch",
            "type": "ELASTICSEARCH_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, elasticsearch_docs
