"""Connector search service: cross-source file and document search."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


"""Search methods for communication connectors."""


class CommsSearchMixin:
    async def search_google_gmail(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Gmail messages and return both the source information and langchain documents.

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
        gmail_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="GOOGLE_GMAIL_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not gmail_docs:
            return {
                "id": 32,
                "name": "Gmail Messages",
                "type": "GOOGLE_GMAIL_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            subject = metadata.get("subject", "No Subject")
            sender = metadata.get("sender", "Unknown Sender")
            return (
                f"Email: {subject} (from {sender})" if sender else f"Email: {subject}"
            )

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            message_id = metadata.get("message_id", "")
            return (
                f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
                if message_id
                else ""
            )

        def _description_fn(
            chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> str:
            description = chunk.get("content", "")
            info_parts = []
            date_str = metadata.get("date", "")
            thread_id = metadata.get("thread_id", "")
            if date_str:
                info_parts.append(f"Date: {date_str}")
            if thread_id:
                info_parts.append(f"Thread: {thread_id}")
            if info_parts:
                description = (description + " | " + " | ".join(info_parts)).strip(" |")
            return description

        def _extra_fields_fn(
            _chunk: dict[str, Any], _doc_info: dict[str, Any], metadata: dict[str, Any]
        ) -> dict[str, Any]:
            return {
                "message_id": metadata.get("message_id", ""),
                "subject": metadata.get("subject", "No Subject"),
                "sender": metadata.get("sender", "Unknown Sender"),
                "date": metadata.get("date", ""),
                "thread_id": metadata.get("thread_id", ""),
            }

        sources_list = self._build_chunk_sources_from_documents(
            gmail_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=_description_fn,
            extra_fields_fn=_extra_fields_fn,
        )

        # Create result object
        result_object = {
            "id": 32,  # Assign a unique ID for the Gmail connector
            "name": "Gmail Messages",
            "type": "GOOGLE_GMAIL_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, gmail_docs
    async def search_slack(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for slack and return both the source information and langchain documents.

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
        slack_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="SLACK_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not slack_docs:
            return {
                "id": 4,
                "name": "Slack",
                "type": "SLACK_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = channel_name
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_id = metadata.get("channel_id", "")
            return (
                f"https://slack.com/app_redirect?channel={channel_id}"
                if channel_id
                else ""
            )

        sources_list = self._build_chunk_sources_from_documents(
            slack_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 4,
            "name": "Slack",
            "type": "SLACK_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, slack_docs
    async def search_teams(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Microsoft Teams messages and return both the source information and langchain documents.

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
        teams_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="TEAMS_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not teams_docs:
            return {
                "id": 53,
                "name": "Microsoft Teams",
                "type": "TEAMS_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            team_name = metadata.get("team_name", "Unknown Team")
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = f"{team_name} - {channel_name}"
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            team_id = metadata.get("team_id", "")
            channel_id = metadata.get("channel_id", "")
            if team_id and channel_id:
                return f"https://teams.microsoft.com/l/channel/{channel_id}/General?groupId={team_id}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            teams_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 53,
            "name": "Microsoft Teams",
            "type": "TEAMS_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, teams_docs
    async def search_discord(
        self,
        user_query: str,
        workspace_id: int,
        top_k: int = 20,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple:
        """
        Search for Discord messages and return both the source information and langchain documents.

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
        discord_docs = await self._combined_rrf_search(
            query_text=user_query,
            workspace_id=workspace_id,
            document_type="DISCORD_CONNECTOR",
            top_k=top_k,
            start_date=start_date,
            end_date=end_date,
        )

        # Early return if no results
        if not discord_docs:
            return {
                "id": 11,
                "name": "Discord",
                "type": "DISCORD_CONNECTOR",
                "sources": [],
            }, []

        def _title_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_name = metadata.get("channel_name", "Unknown Channel")
            message_date = metadata.get("start_date", "")
            title = channel_name
            if message_date:
                title += f" ({message_date})"
            return title

        def _url_fn(_doc_info: dict[str, Any], metadata: dict[str, Any]) -> str:
            channel_id = metadata.get("channel_id", "")
            guild_id = metadata.get("guild_id", "")
            if guild_id and channel_id:
                return f"https://discord.com/channels/{guild_id}/{channel_id}"
            if channel_id:
                return f"https://discord.com/channels/@me/{channel_id}"
            return ""

        sources_list = self._build_chunk_sources_from_documents(
            discord_docs,
            title_fn=_title_fn,
            url_fn=_url_fn,
            description_fn=lambda chunk, _doc_info, _metadata: chunk.get("content", ""),
        )

        # Create result object
        result_object = {
            "id": 11,
            "name": "Discord",
            "type": "DISCORD_CONNECTOR",
            "sources": sources_list,
        }

        return result_object, discord_docs
