"""Connector service package."""

from __future__ import annotations

from app.services.connectors.cache import invalidate_connector_discovery_cache
from app.services.connectors.discovery import ConnectorDiscoveryMixin
from app.services.connectors.search import ConnectorSearchService

__all__ = ["ConnectorService", "invalidate_connector_discovery_cache"]

class ConnectorService(ConnectorSearchService, ConnectorDiscoveryMixin):
    """Facade combining connector search and discovery."""
