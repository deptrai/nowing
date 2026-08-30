"""Connector search service: cross-source file and document search."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


"""Search methods for web and code sources."""


class WebSearchMixin:
    async def search_github(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for GitHub documents and return both the source information and langchain documents.

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
        github_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="GITHUB_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not github_docs:
            return {
                "id": 8,
                "name": "GitHub",
                "type": "GITHUB_CONNECTOR",
                "sources": [],
            }, []

        sources_list = self._build_chunk_sources_from_documents(
            github_docs,
            description_fn=lambda chunk, _doc_info, metadata: (
                metadata.get("description") or chunk.get("content", "")
            ),
            url_fn=lambda _doc_info, metadata: metadata.get("url", "") or "",
        )

        # Create result object
        result_object = {
            "id": 8,
            "name": "GitHub",
            "type": "GITHUB_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, github_docs
    async def search_youtube(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for YouTube videos and return both the source information and langchain documents.

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
        youtube_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="YOUTUBE_VIDEO",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not youtube_docs:
            return {
                "id": 7,
                "name": "YouTube Videos",
                "type": "YOUTUBE_VIDEO",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            video_title = metadata.get("video_title", "Untitled Video")
            channel_name = metadata.get("channel_name", "")
            return f"{video_title} - {channel_name}" if channel_name else video_title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            video_id = metadata.get("video_id", "")
            return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            return metadata.get("description") or chunk.get("content", "")

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "video_id": metadata.get("video_id", ""),
                "channel_name": metadata.get("channel_name", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            youtube_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 7,  # Assign a unique ID for the YouTube connector
            "name": "YouTube Videos",
            "type": "YOUTUBE_VIDEO",
            "sources": sources_list,
        }

        return result_object, youtube_docs
    async def search_extension(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for extension data and return both the source information and langchain documents.

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
        extension_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="EXTENSION",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not extension_docs:
            return {
                "id": 6,
                "name": "Extension",
                "type": "EXTENSION",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            webpage_title = metadata.get("VisitedWebPageTitle", "Untitled Page")
            visit_date = metadata.get("VisitedWebPageDateWithTimeInISOString", "")
            title = webpage_title
            if visit_date:
                if "T" in visit_date:
                    formatted_date = visit_date.split("T")[0]
                    title += f" (visited: {formatted_date})"
                else:
                    title += f" (visited: {visit_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("VisitedWebPageURL", "") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            visit_duration = metadata.get(
                "VisitedWebPageVisitDurationInMilliseconds", ""
            )
            if visit_duration:
                try:
                    duration_seconds = int(visit_duration) / 1000
                except (ValueError, TypeError):
                    duration_seconds = None
                if duration_seconds is not None:
                    duration_text = (
                        f"{duration_seconds:.1f} seconds"
                        if duration_seconds < 60
                        else f"{duration_seconds / 60:.1f} minutes"
                    )
                    description = (description + f" | Duration: {duration_text}").strip(
                        " |"
                    )
            return description

        sources_list = self._build_chunk_sources_from_documents(
            extension_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
        )

        # Create result object
        result_object = {
            "id": 6,
            "name": "Extension",
            "type": "EXTENSION",
            "sources": sources_list,
        }

        return result_object, extension_docs
