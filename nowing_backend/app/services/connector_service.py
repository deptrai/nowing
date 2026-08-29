"""Compatibility re-export for `app.services.connector_service`."""

from __future__ import annotations

from app.services.connectors import (
    ConnectorService,
    invalidate_connector_discovery_cache,
)

__all__ = ["ConnectorService", "invalidate_connector_discovery_cache"]
