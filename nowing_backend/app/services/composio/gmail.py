"""Composio Gmail toolkit operations."""

from __future__ import annotations

import logging
from typing import Any

from app.services.composio.base import ComposioClientMixin

logger = logging.getLogger(__name__)


class ComposioGmailMixin(ComposioClientMixin):
    """Gmail operations via Composio tools."""

    async def get_gmail_messages(
        self,
        connected_account_id: str,
        entity_id: str,
        query: str = "",
        max_results: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int | None, str | None]:
        """List Gmail messages via Composio with pagination support."""
        try:
            params = {"max_results": min(max_results, 50)}
            if query:
                params["query"] = query
            if page_token:
                params["page_token"] = page_token

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_FETCH_EMAILS",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], None, None, result.get("error", "Unknown error")

            data = result.get("data", {})

            messages = []
            next_token = None
            result_size_estimate = None
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                response_data = (
                    inner_data.get("response_data", {})
                    if isinstance(inner_data, dict)
                    else {}
                )
                messages = (
                    data.get("messages", [])
                    or (
                        inner_data.get("messages", [])
                        if isinstance(inner_data, dict)
                        else []
                    )
                    or response_data.get("messages", [])
                    or data.get("emails", [])
                    or (
                        inner_data.get("emails", [])
                        if isinstance(inner_data, dict)
                        else []
                    )
                    or response_data.get("emails", [])
                )
                next_token = (
                    data.get("nextPageToken")
                    or data.get("next_page_token")
                    or (
                        inner_data.get("nextPageToken")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or (
                        inner_data.get("next_page_token")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or response_data.get("nextPageToken")
                    or response_data.get("next_page_token")
                )
                result_size_estimate = (
                    data.get("resultSizeEstimate")
                    or data.get("result_size_estimate")
                    or (
                        inner_data.get("resultSizeEstimate")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or (
                        inner_data.get("result_size_estimate")
                        if isinstance(inner_data, dict)
                        else None
                    )
                    or response_data.get("resultSizeEstimate")
                    or response_data.get("result_size_estimate")
                )
            elif isinstance(data, list):
                messages = data

            return messages, next_token, result_size_estimate, None

        except Exception as e:
            logger.error(f"Failed to list Gmail messages: {e!s}")
            return [], None, None, str(e)

    async def get_gmail_message_detail(
        self, connected_account_id: str, entity_id: str, message_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Get full details of a Gmail message via Composio."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
                params={"message_id": message_id},
                entity_id=entity_id,
            )

            if not result.get("success"):
                return None, result.get("error", "Unknown error")

            data = result.get("data")
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                if isinstance(inner_data, dict):
                    return inner_data.get("response_data", inner_data), None

            return data, None

        except Exception as e:
            logger.error(f"Failed to get Gmail message detail: {e!s}")
            return None, str(e)

    @staticmethod
    def _split_email_csv(value: str | None) -> list[str] | None:
        """Tools accept comma-separated cc/bcc strings; Composio expects an array."""
        if not value:
            return None
        addrs = [e.strip() for e in value.split(",") if e.strip()]
        return addrs or None

    async def send_gmail_email(
        self,
        connected_account_id: str,
        entity_id: str,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
        is_html: bool = False,
    ) -> tuple[str | None, str | None, str | None]:
        """Send a Gmail message via the Composio GMAIL_SEND_EMAIL toolkit."""
        try:
            params: dict[str, Any] = {
                "recipient_email": to,
                "subject": subject,
                "body": body,
                "is_html": is_html,
            }
            if cc:
                cc_list = self._split_email_csv(cc)
                if cc_list:
                    params["cc"] = cc_list
            if bcc:
                bcc_list = self._split_email_csv(bcc)
                if bcc_list:
                    params["bcc"] = bcc_list

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_SEND_EMAIL",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            message_id = None
            thread_id = None
            if isinstance(payload, dict):
                message_id = (
                    payload.get("id")
                    or payload.get("message_id")
                    or payload.get("messageId")
                )
                thread_id = payload.get("threadId") or payload.get("thread_id")
            return message_id, thread_id, None
        except Exception as e:
            logger.error(f"Failed to send Gmail email: {e!s}")
            return None, None, str(e)

    async def create_gmail_draft(
        self,
        connected_account_id: str,
        entity_id: str,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
        is_html: bool = False,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Create a Gmail draft via the Composio GMAIL_CREATE_EMAIL_DRAFT toolkit."""
        try:
            params: dict[str, Any] = {
                "recipient_email": to,
                "subject": subject,
                "body": body,
                "is_html": is_html,
            }
            cc_list = self._split_email_csv(cc)
            if cc_list:
                params["cc"] = cc_list
            bcc_list = self._split_email_csv(bcc)
            if bcc_list:
                params["bcc"] = bcc_list

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_CREATE_EMAIL_DRAFT",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, None, None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            draft_id = None
            message_id = None
            thread_id = None
            if isinstance(payload, dict):
                draft_id = payload.get("id") or payload.get("draft_id")
                draft_message = payload.get("message") or {}
                if isinstance(draft_message, dict):
                    message_id = draft_message.get("id") or draft_message.get(
                        "message_id"
                    )
                    thread_id = draft_message.get("threadId") or draft_message.get(
                        "thread_id"
                    )
                if message_id is None:
                    message_id = payload.get("message_id") or payload.get("messageId")
                if thread_id is None:
                    thread_id = payload.get("thread_id") or payload.get("threadId")
            return draft_id, message_id, thread_id, None
        except Exception as e:
            logger.error(f"Failed to create Gmail draft: {e!s}")
            return None, None, None, str(e)

    async def update_gmail_draft(
        self,
        connected_account_id: str,
        entity_id: str,
        draft_id: str,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        is_html: bool = False,
    ) -> tuple[str | None, str | None, str | None]:
        """Update an existing Gmail draft via GMAIL_UPDATE_DRAFT."""
        try:
            params: dict[str, Any] = {
                "draft_id": draft_id,
                "is_html": is_html,
            }
            if to:
                params["recipient_email"] = to
            if subject is not None:
                params["subject"] = subject
            if body is not None:
                params["body"] = body
            cc_list = self._split_email_csv(cc)
            if cc_list:
                params["cc"] = cc_list
            bcc_list = self._split_email_csv(bcc)
            if bcc_list:
                params["bcc"] = bcc_list

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_UPDATE_DRAFT",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            new_draft_id = draft_id
            message_id = None
            if isinstance(payload, dict):
                new_draft_id = payload.get("id") or payload.get("draft_id") or draft_id
                draft_message = payload.get("message") or {}
                if isinstance(draft_message, dict):
                    message_id = draft_message.get("id") or draft_message.get(
                        "message_id"
                    )
                if message_id is None:
                    message_id = payload.get("message_id") or payload.get("messageId")
            return new_draft_id, message_id, None
        except Exception as e:
            logger.error(f"Failed to update Gmail draft: {e!s}")
            return None, None, str(e)

    async def trash_gmail_message(
        self,
        connected_account_id: str,
        entity_id: str,
        message_id: str,
    ) -> str | None:
        """Move a Gmail message to trash via GMAIL_MOVE_TO_TRASH."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GMAIL_MOVE_TO_TRASH",
                params={"message_id": message_id},
                entity_id=entity_id,
            )
            if not result.get("success"):
                return result.get("error", "Unknown error")
            return None
        except Exception as e:
            logger.error(f"Failed to trash Gmail message: {e!s}")
            return str(e)
