"""Composio service class and singleton factory."""

from __future__ import annotations

from app.services.composio.calendar import ComposioCalendarMixin
from app.services.composio.drive import ComposioDriveMixin
from app.services.composio.email import (
    get_connected_account_email as _get_connected_account_email,
)
from app.services.composio.gmail import ComposioGmailMixin


class ComposioService(
    ComposioDriveMixin,
    ComposioGmailMixin,
    ComposioCalendarMixin,
):
    """Service for interacting with the Composio API.

    Composition of client initialization, Google Drive, Gmail, and Calendar
    toolkit mixins. Public constants are re-exported from ``constants.py`` for
    backward compatibility.
    """

    async def get_connected_account_email(
        self,
        connected_account_id: str,
        entity_id: str,
        toolkit_id: str,
    ) -> str | None:
        """Get the email address associated with a connected account."""
        return await _get_connected_account_email(
            self, connected_account_id, entity_id, toolkit_id
        )


_composio_service: ComposioService | None = None


def get_composio_service() -> ComposioService:
    """Get or create the Composio service singleton.

    Raises:
        ValueError: If Composio is not properly configured.
    """
    global _composio_service
    if _composio_service is None:
        _composio_service = ComposioService()
    return _composio_service
