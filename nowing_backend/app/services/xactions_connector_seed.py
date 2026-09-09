"""Auto-seeder for XActions MCP connector.

Ensures every active workspace has an `XACTIONS_MCP_CONNECTOR` record pointing to
the configured XActions daemon so chat agents have immediate access to the 3
meta-tools (`x_scrape`, `x_search`, `x_crawl_post`) without requiring manual setup.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import SearchSourceConnectorType
from app.models.connectors import SearchSourceConnector
from app.models.workspaces import Workspace

logger = logging.getLogger(__name__)


def build_xactions_connector_config() -> dict:
    """Build standard server_config and trusted_tools for XActions."""
    mcp_url = getattr(config, "XACTIONS_MCP_URL", "http://localhost:3001/mcp")
    consumer_id = getattr(config, "XACTIONS_CONSUMER_ID", "nowing")
    api_key = getattr(config, "XACTIONS_MCP_API_KEY", "")

    headers = {"X-Consumer-Id": consumer_id}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return {
        "consumer_id": consumer_id,
        "server_config": {
            "url": mcp_url,
            "transport": "streamable-http",
            "headers": headers,
        },
        "trusted_tools": ["x_scrape", "x_search", "x_crawl_post"],
    }


async def ensure_workspace_xactions_connector(
    session: AsyncSession,
    workspace_id: int,
    user_id: UUID,
) -> SearchSourceConnector | None:
    """Ensure a specific workspace has the XActions connector. Returns the connector."""
    try:
        existing = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.workspace_id == workspace_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR,
            )
        )
        connector = existing.scalars().first()
        if connector is not None:
            return connector

        connector = SearchSourceConnector(
            name="XActions",
            connector_type=SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR,
            is_indexable=False,
            config=build_xactions_connector_config(),
            periodic_indexing_enabled=False,
            indexing_frequency_minutes=None,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        session.add(connector)
        await session.flush()
        logger.info(
            "Auto-provisioned XActions connector for workspace %d",
            workspace_id,
        )
        return connector
    except Exception as exc:
        await session.rollback()
        logger.warning(
            "Failed to ensure XActions connector for workspace %d: %s",
            workspace_id,
            exc,
            exc_info=True,
        )
        return None


async def seed_xactions_connectors(session: AsyncSession) -> int:
    """Scan all active workspaces and create XActions connector where missing.

    Returns the count of newly created connectors.
    """
    created_count = 0
    try:
        stmt = select(Workspace).filter(~Workspace.name.startswith("[DELETING] "))
        result = await session.execute(stmt)
        workspaces = result.scalars().all()

        for ws in workspaces:
            existing = await session.execute(
                select(SearchSourceConnector.id).filter(
                    SearchSourceConnector.workspace_id == ws.id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR,
                )
            )
            if existing.scalars().first() is None:
                connector = SearchSourceConnector(
                    name="XActions",
                    connector_type=SearchSourceConnectorType.XACTIONS_MCP_CONNECTOR,
                    is_indexable=False,
                    config=build_xactions_connector_config(),
                    periodic_indexing_enabled=False,
                    indexing_frequency_minutes=None,
                    workspace_id=ws.id,
                    user_id=ws.user_id,
                )
                session.add(connector)
                created_count += 1

        if created_count > 0:
            await session.commit()
            logger.info("Seeded XActions connector for %d workspaces", created_count)
    except Exception as exc:
        logger.warning("seed_xactions_connectors failed: %s", exc, exc_info=True)
        await session.rollback()

    return created_count
