"""Composio integration package.

This package wraps the Composio SDK for OAuth, toolkit execution,
and Google Workspace (Drive, Gmail, Calendar) read/write operations.
"""

from __future__ import annotations

from composio import Composio

from .base import ComposioClientMixin
from .calendar import ComposioCalendarMixin
from .constants import (
    COMPOSIO_TOOLKIT_NAMES,
    INDEXABLE_TOOLKITS,
    TOOLKIT_TO_CONNECTOR_TYPE,
    TOOLKIT_TO_DOCUMENT_TYPE,
    TOOLKIT_TO_INDEXER,
)
from .drive import ComposioDriveMixin
from .email import get_connected_account_email
from .gmail import ComposioGmailMixin
from .service import ComposioService, get_composio_service

__all__ = [
    "COMPOSIO_TOOLKIT_NAMES",
    "INDEXABLE_TOOLKITS",
    "TOOLKIT_TO_CONNECTOR_TYPE",
    "TOOLKIT_TO_DOCUMENT_TYPE",
    "TOOLKIT_TO_INDEXER",
    "Composio",
    "ComposioCalendarMixin",
    "ComposioClientMixin",
    "ComposioDriveMixin",
    "ComposioGmailMixin",
    "ComposioService",
    "get_composio_service",
    "get_connected_account_email",
]
