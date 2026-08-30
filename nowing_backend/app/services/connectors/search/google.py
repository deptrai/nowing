"""Connector search service: cross-source file and document search."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


"""Search methods for Google workspace connectors."""


class GoogleSearchMixin:
    async def search_google_calendar(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Google Calendar events and return both the source information and langchain documents.

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
        calendar_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="GOOGLE_CALENDAR_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not calendar_docs:
            return {
                "id": 31,
                "name": "Google Calendar Events",
                "type": "GOOGLE_CALENDAR_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_summary = metadata.get("event_summary", "Untitled Event")
            start_time = metadata.get("start_time", "")
            title = event_summary
            if start_time:
                title += f" ({start_time})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            event_id = metadata.get("event_id", "")
            calendar_id = metadata.get("calendar_id", "")
            return (
                f"https://calendar.google.com/calendar/event?eid={event_id}"
                if event_id and calendar_id
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            location = metadata.get("location", "")
            calendar_id = metadata.get("calendar_id", "")
            end_time = metadata.get("end_time", "")
            if location:
                info_parts.append(f"Location: {location}")
            if calendar_id and calendar_id != "primary":
                info_parts.append(f"Calendar: {calendar_id}")
            if end_time:
                info_parts.append(f"End: {end_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "event_id": metadata.get("event_id", ""),
                "event_summary": metadata.get("event_summary", "Untitled Event"),
                "calendar_id": metadata.get("calendar_id", ""),
                "start_time": metadata.get("start_time", ""),
                "end_time": metadata.get("end_time", ""),
                "location": metadata.get("location", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            calendar_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 31,  # Assign a unique ID for the Google Calendar connector
            "name": "Google Calendar Events",
            "type": "GOOGLE_CALENDAR_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, calendar_docs
    async def search_google_drive(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Google Drive files and return both the source information and langchain documents.

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
        drive_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="GOOGLE_DRIVE_FILE",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not drive_docs:
            return {
                "id": 33,
                "name": "Google Drive Files",
                "type": "GOOGLE_DRIVE_FILE",
                "sources": [],
            }, []

        def _title_fn(doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            return (
                doc_info.get("title")
                or metadata.get("google_drive_file_name")
                or metadata.get("FILE_NAME")
                or "Untitled File"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            file_id = metadata.get("google_drive_file_id", "")
            return f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = self._chunk_preview(chunk.get("content", ""))
            info_parts = []
            mime_type = metadata.get("google_drive_mime_type", "")
            modified_time = metadata.get("modified_time", "")
            if mime_type:
                # Simplify mime type for display
                if "google-apps" in mime_type:
                    file_type = mime_type.split(".")[-1].title()
                else:
                    file_type = mime_type.split("/")[-1].upper()
                info_parts.append(f"Type: {file_type}")
            if modified_time:
                info_parts.append(f"Modified: {modified_time}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "google_drive_file_id": metadata.get("google_drive_file_id", ""),
                "google_drive_mime_type": metadata.get("google_drive_mime_type", ""),
                "modified_time": metadata.get("modified_time", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            drive_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 33,  # Assign a unique ID for the Google Drive connector
            "name": "Google Drive Files",
            "type": "GOOGLE_DRIVE_FILE",
            "sources": sources_list,
        }

        return result_object, drive_docs
