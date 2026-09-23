"""Backward-compatible shim for the refactored Composio package.

This module re-exports the public API previously defined in the monolithic
``app.services.composio_service`` module so that existing imports continue to
work. New code should import directly from ``app.services.composio``.
"""

from __future__ import annotations

from app.services.composio import (
    COMPOSIO_TOOLKIT_NAMES,
    INDEXABLE_TOOLKITS,
    TOOLKIT_TO_CONNECTOR_TYPE,
    TOOLKIT_TO_DOCUMENT_TYPE,
    TOOLKIT_TO_INDEXER,
    Composio,
    ComposioCalendarMixin,
    ComposioClientMixin,
    ComposioDriveMixin,
    ComposioGmailMixin,
    ComposioService,
    get_composio_service,
)

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
]
