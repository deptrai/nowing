"""Compatibility re-export for `app.services.connector_service`."""

from __future__ import annotations

from app.db import async_session_maker
from app.services.connectors import (
    ConnectorService,
    invalidate_connector_discovery_cache,
)

__all__ = ["ConnectorService", "async_session_maker", "invalidate_connector_discovery_cache"]
