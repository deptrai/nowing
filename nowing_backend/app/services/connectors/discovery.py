"""Connector and document-type discovery helpers."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import Document, SearchSourceConnector, SearchSourceConnectorType
from app.services.connectors.cache import (
    _get_cached_connectors,
    _get_cached_doc_types,
    _set_cached_connectors,
    _set_cached_doc_types,
)

logger = logging.getLogger(__name__)

class ConnectorDiscoveryMixin:
    """Mixin providing connector and document-type discovery."""

    # Utility Methods for Connector Discovery
    # =========================================================================

    async def get_available_connectors(
        self,
        workspace_id: int,
    ) -> list[SearchSourceConnectorType]:
        """
        Get all available (enabled) connector types for a workspace.

        Phase 1.4: results are cached per ``workspace_id`` for
        :data:`_DISCOVERY_TTL_SECONDS`. Cache key is independent of session
        identity — the cached value is plain data, safe to share across
        requests. Invalidate on connector add/update/delete via
        :func:`invalidate_connector_discovery_cache`.

        Args:
            workspace_id: The workspace ID

        Returns:
            List of SearchSourceConnectorType enums for enabled connectors
        """
        cached = _get_cached_connectors(workspace_id)
        if cached is not None:
            return list(cached)

        query = (
            select(SearchSourceConnector.connector_type)
            .filter(
                SearchSourceConnector.workspace_id == workspace_id,
            )
            .distinct()
        )

        result = await self.session.execute(query)
        connector_types = list(result.scalars().all())
        _set_cached_connectors(workspace_id, connector_types)
        return connector_types

    async def get_available_document_types(
        self,
        workspace_id: int,
    ) -> list[str]:
        """
        Get all document types that have at least one document in the workspace.

        Phase 1.4: cached per ``workspace_id`` for
        :data:`_DISCOVERY_TTL_SECONDS`. Invalidate via
        :func:`invalidate_connector_discovery_cache` when a connector
        finishes indexing new documents (or document types are otherwise
        added/removed).

        Args:
            workspace_id: The workspace ID

        Returns:
            List of document type strings that have documents indexed
        """
        cached = _get_cached_doc_types(workspace_id)
        if cached is not None:
            return list(cached)

        from sqlalchemy import distinct


        query = select(distinct(Document.document_type)).filter(
            Document.workspace_id == workspace_id,
        )

        result = await self.session.execute(query)
        doc_types = [str(dt) for dt in result.scalars().all()]
        _set_cached_doc_types(workspace_id, doc_types)
        return doc_types


# ---------------------------------------------------------------------------
