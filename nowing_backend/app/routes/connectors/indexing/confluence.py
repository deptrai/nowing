"""Connector indexing routes and helpers."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    async_session_maker,
)

from .._shared import (
    _update_connector_timestamp_by_id,
)
from .core import _run_indexing_with_notifications

logger = logging.getLogger(__name__)



async def run_confluence_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run Confluence indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Confluence connector {connector_id} into space {workspace_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_confluence_indexing(
            session, connector_id, workspace_id, user_id, start_date, end_date
        )
    logger.info(
        f"Background task finished: Indexing Confluence connector {connector_id}"
    )
async def run_confluence_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Confluence indexing.

    Args:
        session: Database session
        connector_id: ID of the Confluence connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_confluence_pages

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_confluence_pages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )

__all__ = ['run_confluence_indexing', 'run_confluence_indexing_with_new_session']
