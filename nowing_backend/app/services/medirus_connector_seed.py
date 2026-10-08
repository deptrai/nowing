"""Auto-seeder for Medirus MCP connector.

Ensures every active workspace has an `MEDIRUS_MCP_CONNECTOR` record pointing to
the configured Medirus daemon so chat agents have immediate access to the 3
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


def build_medirus_connector_config() -> dict:
    """Build standard server_config and trusted_tools for Medirus."""
    mcp_url = getattr(config, "MEDIRUS_MCP_URL", "http://localhost:3333/mcp")
    consumer_id = getattr(config, "MEDIRUS_CONSUMER_ID", "nowing")
    api_key = getattr(config, "MEDIRUS_MCP_API_KEY", "")

    headers = {"X-Consumer-Id": consumer_id}
    if api_key:
        # pi-lens-ignore: ast-grep:no-secret-in-env-var-name -- runtime credential value, not hardcoded
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


async def ensure_workspace_medirus_connector(
    session: AsyncSession,
    workspace_id: int,
    user_id: UUID,
) -> SearchSourceConnector | None:
    """Ensure a specific workspace has the Medirus connector. Returns the connector."""
    try:
        existing = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.workspace_id == workspace_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MEDIRUS_MCP_CONNECTOR,
            )
        )
        connector = existing.scalars().first()
        if connector is not None:
            return connector

        # Skip workspaces that are marked for deletion so we do not re-seed a
        # connector on rows that are about to be dropped.
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None or workspace.name.startswith("[DELETING] "):
            return None

        connector = SearchSourceConnector(
            name="Medirus",
            connector_type=SearchSourceConnectorType.MEDIRUS_MCP_CONNECTOR,
            is_indexable=False,
            config=build_medirus_connector_config(),
            periodic_indexing_enabled=False,
            indexing_frequency_minutes=None,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        session.add(connector)
        await session.flush()
        logger.info(
            "Auto-provisioned Medirus connector for workspace %d",
            workspace_id,
        )
        return connector
    except Exception as exc:  # seed failure → rollback so session stays clean; connector absent
        await session.rollback()
        logger.warning(
            "Failed to ensure Medirus connector for workspace %d: %s",
            workspace_id,
            exc,
            exc_info=True,
        )
        return None


async def seed_medirus_connectors(session: AsyncSession) -> int:
    """Scan all active workspaces and create Medirus connector where missing.

    Uses a single set-lookup to avoid the N+1 query pattern when checking
    whether each workspace already has an Medirus connector.

    Returns the count of newly created connectors.
    """
    created_count = 0
    try:
        active_workspace_stmt = (
            select(Workspace.id, Workspace.user_id)
            .filter(~Workspace.name.startswith("[DELETING] "))
            .order_by(Workspace.id)
        )

        existing_stmt = select(SearchSourceConnector.workspace_id).filter(
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.MEDIRUS_MCP_CONNECTOR,
        )
        existing_result = await session.execute(existing_stmt)
        existing_ids = set(existing_result.scalars().all())

        result = await session.execute(active_workspace_stmt)
        workspaces = result.all()

        for ws in workspaces:
            if ws.id in existing_ids:
                continue

            connector = SearchSourceConnector(
                name="Medirus",
                connector_type=SearchSourceConnectorType.MEDIRUS_MCP_CONNECTOR,
                is_indexable=False,
                config=build_medirus_connector_config(),
                periodic_indexing_enabled=False,
                indexing_frequency_minutes=None,
                workspace_id=ws.id,
                user_id=ws.user_id,
            )
            session.add(connector)
            created_count += 1

        if created_count > 0:
            await session.commit()
            logger.info("Seeded Medirus connector for %d workspaces", created_count)
    except Exception as exc:  # seeding best-effort at boot; rollback keeps session usable
        logger.warning("seed_medirus_connectors failed: %s", exc, exc_info=True)
        await session.rollback()

    return created_count
