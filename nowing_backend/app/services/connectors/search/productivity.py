"""Connector search service: cross-source file and document search."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


"""Search methods for productivity connectors."""


class ProductivitySearchMixin:
    async def search_notion(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Notion pages and return both the source information and langchain documents.

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
        notion_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="NOTION_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not notion_docs:
            return {
                "id": 5,
                "name": "Notion",
                "type": "NOTION_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_title = metadata.get("page_title", "Untitled Page")
            indexed_at = metadata.get("indexed_at", "")
            title = page_title
            if indexed_at:
                title += f" (indexed: {indexed_at})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_id = metadata.get("page_id", "")
            return f"https://notion.so/{page_id.replace('-', '')}" if page_id else ""

        sources_list = self._build_chunk_sources_from_documents(
            notion_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 5,
            "name": "Notion",
            "type": "NOTION_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, notion_docs
    async def search_jira(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Jira issues and comments and return both the source information and langchain documents.

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
        jira_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="JIRA_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not jira_docs:
            return {
                "id": 30,
                "name": "Jira Issues",
                "type": "JIRA_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_key = metadata.get("issue_key", "")
            issue_title = metadata.get("issue_title", "Untitled Issue")
            status = metadata.get("status", "")
            title = f"{issue_key} - {issue_title}" if issue_key else issue_title
            if status:
                title += f" ({status})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_key = metadata.get("issue_key", "")
            base_url = metadata.get("base_url")
            return f"{base_url}/browse/{issue_key}" if issue_key and base_url else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            priority = metadata.get("priority", "")
            issue_type = metadata.get("issue_type", "")
            comment_count = metadata.get("comment_count", 0)
            if priority:
                info_parts.append(f"Priority: {priority}")
            if issue_type:
                info_parts.append(f"Type: {issue_type}")
            if comment_count:
                info_parts.append(f"Comments: {comment_count}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "issue_key": metadata.get("issue_key", ""),
                "status": metadata.get("status", ""),
                "priority": metadata.get("priority", ""),
                "issue_type": metadata.get("issue_type", ""),
                "comment_count": metadata.get("comment_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            jira_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 10,  # Assign a unique ID for the Jira connector
            "name": "Jira Issues",
            "type": "JIRA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, jira_docs
    async def search_clickup(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for ClickUp tasks and return both the source information and langchain documents.

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
        clickup_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="CLICKUP_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not clickup_docs:
            return {
                "id": 31,
                "name": "ClickUp Tasks",
                "type": "CLICKUP_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("task_name", "ClickUp Task")

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("task_url", "") or ""

        def _description_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            parts = []
            if metadata.get("task_status"):
                parts.append(f"Status: {metadata.get('task_status')}")
            if metadata.get("task_priority"):
                parts.append(f"Priority: {metadata.get('task_priority')}")
            if metadata.get("task_due_date"):
                parts.append(f"Due: {metadata.get('task_due_date')}")
            if metadata.get("task_list_name"):
                parts.append(f"List: {metadata.get('task_list_name')}")
            if metadata.get("task_space_name"):
                parts.append(f"Space: {metadata.get('task_space_name')}")
            return " | ".join(parts) if parts else "ClickUp Task"

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "task_id": metadata.get("task_id", ""),
                "status": metadata.get("task_status", ""),
                "priority": metadata.get("task_priority", ""),
                "assignees": metadata.get("task_assignees", []),
                "due_date": metadata.get("task_due_date", ""),
                "list_name": metadata.get("task_list_name", ""),
                "space_name": metadata.get("task_space_name", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            clickup_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the ClickUp connector
            "name": "ClickUp Tasks",
            "type": "CLICKUP_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, clickup_docs
    async def search_linear(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Linear issues and comments and return both the source information and langchain documents.

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
        linear_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="LINEAR_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not linear_docs:
            return {
                "id": 9,
                "name": "Linear Issues",
                "type": "LINEAR_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_identifier = metadata.get("issue_identifier", "")
            issue_title = metadata.get("issue_title", "Untitled Issue")
            issue_state = metadata.get("state", "")
            title = (
                f"{issue_identifier} - {issue_title}"
                if issue_identifier
                else issue_title
            )
            if issue_state:
                title += f" ({issue_state})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            issue_identifier = metadata.get("issue_identifier", "")
            return (
                f"https://linear.app/issue/{issue_identifier}"
                if issue_identifier
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            comment_count = metadata.get("comment_count", 0)
            if comment_count:
                description = (description + f" | Comments: {comment_count}").strip(
                    " |"
                )
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "issue_identifier": metadata.get("issue_identifier", ""),
                "state": metadata.get("state", ""),
                "comment_count": metadata.get("comment_count", 0),
            }

        sources_list = self._build_chunk_sources_from_documents(
            linear_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 9,  # Assign a unique ID for the Linear connector
            "name": "Linear Issues",
            "type": "LINEAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, linear_docs
    async def search_confluence(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Confluence pages and return both the source information and langchain documents.

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
        confluence_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="CONFLUENCE_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not confluence_docs:
            return {
                "id": 40,
                "name": "Confluence",
                "type": "CONFLUENCE_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_title = metadata.get("page_title", "Untitled Page")
            space_key = metadata.get("space_key", "")
            title = page_title
            if space_key:
                title += f" ({space_key})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            page_id = metadata.get("page_id", "")
            base_url = metadata.get("base_url", "")
            return f"{base_url}/pages/{page_id}" if base_url and page_id else ""

        sources_list = self._build_chunk_sources_from_documents(
            confluence_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 40,
            "name": "Confluence",
            "type": "CONFLUENCE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, confluence_docs
    async def search_luma(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Luma events and return both the source information and langchain documents.

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
        luma_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="LUMA_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not luma_docs:
            return {
                "id": 33,
                "name": "Luma Events",
                "type": "LUMA_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_name = metadata.get("event_name", "Untitled Event")
            start_time = metadata.get("start_time", "")
            return f"{event_name} ({start_time})" if start_time else event_name

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return metadata.get("event_url", "") or ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            if metadata.get("location_name"):
                info_parts.append(f"Venue: {metadata.get('location_name')}")
            elif metadata.get("location_address"):
                info_parts.append(f"Location: {metadata.get('location_address')}")
            if metadata.get("meeting_url"):
                info_parts.append("Online Event")
            if metadata.get("end_time"):
                info_parts.append(f"Ends: {metadata.get('end_time')}")
            if metadata.get("timezone"):
                info_parts.append(f"TZ: {metadata.get('timezone')}")
            if metadata.get("visibility"):
                info_parts.append(
                    f"Visibility: {str(metadata.get('visibility')).title()}"
                )
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "event_id": metadata.get("event_id", ""),
                "event_name": metadata.get("event_name", "Untitled Event"),
                "start_time": metadata.get("start_time", ""),
                "end_time": metadata.get("end_time", ""),
                "location_name": metadata.get("location_name", ""),
                "location_address": metadata.get("location_address", ""),
                "meeting_url": metadata.get("meeting_url", ""),
                "timezone": metadata.get("timezone", ""),
                "visibility": metadata.get("visibility", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            luma_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 33,  # Assign a unique ID for the Luma connector
            "name": "Luma Events",
            "type": "LUMA_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, luma_docs
    async def search_airtable(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Airtable records and return both the source information and langchain documents.

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
        airtable_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="AIRTABLE_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not airtable_docs:
            return {
                "id": 32,
                "name": "Airtable Records",
                "type": "AIRTABLE_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            record_id = metadata.get("record_id", "")
            return record_id if record_id else "Airtable Record"

        def _description_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            created_time = metadata.get("created_time", "")
            return f"Created: {created_time}" if created_time else ""

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "record_id": metadata.get("record_id", ""),
                "created_time": metadata.get("created_time", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            airtable_docs,
            title_fn=_title_fn,
            url_fn=lambda _doc_info, _metadata: "",
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        result_object = {
            "id": 32,
            "name": "Airtable Records",
            "type": "AIRTABLE_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, airtable_docs
