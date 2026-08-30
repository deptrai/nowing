"""Extract the email address associated with a Composio connected account."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.composio.service import ComposioService

logger = logging.getLogger(__name__)


async def get_connected_account_email(
    service: ComposioService,
    connected_account_id: str,
    entity_id: str,
    toolkit_id: str,
) -> str | None:
    """Get the email address associated with a connected account.

    Uses toolkit-specific API calls:
    - Google Drive: List files and extract owner email
    - Gmail: Get user profile
    - Google Calendar: List events and extract organizer/creator email
    """
    try:
        email = await _extract_email_for_toolkit(
            service, connected_account_id, entity_id, toolkit_id
        )

        if email:
            logger.info(f"Retrieved email {email} for {toolkit_id} connector")
        else:
            logger.warning(f"Could not retrieve email for {toolkit_id} connector")

        return email

    except Exception as e:
        logger.error(f"Failed to get email for {toolkit_id} connector: {e!s}")
        return None


async def _extract_email_for_toolkit(
    service: ComposioService,
    connected_account_id: str,
    entity_id: str,
    toolkit_id: str,
) -> str | None:
    """Extract email based on toolkit type."""
    if toolkit_id == "googledrive":
        return await _get_drive_owner_email(service, connected_account_id, entity_id)
    elif toolkit_id == "gmail":
        return await _get_gmail_profile_email(service, connected_account_id, entity_id)
    elif toolkit_id == "googlecalendar":
        return await _get_calendar_user_email(service, connected_account_id, entity_id)
    return None


async def _get_drive_owner_email(
    service: ComposioService,
    connected_account_id: str,
    entity_id: str,
) -> str | None:
    """Get email from Google Drive file owner where me=True."""
    result = await service.execute_tool(
        connected_account_id=connected_account_id,
        tool_name="GOOGLEDRIVE_LIST_FILES",
        params={
            "page_size": 10,
            "fields": "files(owners)",
            "q": "'me' in owners",
        },
        entity_id=entity_id,
    )

    if not result.get("success"):
        return None

    data = result.get("data", {})
    if not isinstance(data, dict):
        return None

    files = data.get("files") or data.get("data", {}).get("files", [])
    for file in files:
        owners = file.get("owners", [])
        for owner in owners:
            if owner.get("me") and owner.get("emailAddress"):
                return owner.get("emailAddress")

    return None


async def _get_gmail_profile_email(
    service: ComposioService,
    connected_account_id: str,
    entity_id: str,
) -> str | None:
    """Get email from Gmail profile."""
    result = await service.execute_tool(
        connected_account_id=connected_account_id,
        tool_name="GMAIL_GET_PROFILE",
        params={},
        entity_id=entity_id,
    )

    if not result.get("success"):
        return None

    data = result.get("data", {})
    if not isinstance(data, dict):
        return None

    return data.get("emailAddress") or data.get("data", {}).get("emailAddress")


async def _get_calendar_user_email(
    service: ComposioService,
    connected_account_id: str,
    entity_id: str,
) -> str | None:
    """Get email from Google Calendar primary calendar or event organizer/creator."""
    result = await service.execute_tool(
        connected_account_id=connected_account_id,
        tool_name="GOOGLECALENDAR_GET_CALENDAR",
        params={"calendar_id": "primary"},
        entity_id=entity_id,
    )

    if result.get("success"):
        data = result.get("data", {})
        if isinstance(data, dict):
            calendar_data = (
                data.get("data", {}).get("calendar_data", {})
                if isinstance(data.get("data"), dict)
                else {}
            )
            summary = (
                calendar_data.get("summary")
                or calendar_data.get("id")
                or data.get("data", {}).get("summary")
                or data.get("summary")
            )
            if summary and "@" in summary:
                return summary

    result = await service.execute_tool(
        connected_account_id=connected_account_id,
        tool_name="GOOGLECALENDAR_EVENTS_LIST",
        params={"max_results": 20},
        entity_id=entity_id,
    )

    if not result.get("success"):
        return None

    data = result.get("data", {})
    if not isinstance(data, dict):
        return None

    nested_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
    summary = nested_data.get("summary") or data.get("summary")
    if summary and "@" in summary:
        return summary

    items = nested_data.get("items", []) or data.get("items", [])
    for event in items:
        organizer = event.get("organizer", {})
        if organizer.get("self"):
            return organizer.get("email")

        creator = event.get("creator", {})
        if creator.get("self"):
            return creator.get("email")

    return None
