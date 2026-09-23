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



async def run_notion_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Notion indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    from app.tasks.connector_indexers import index_notion_pages

    async with async_session_maker() as session:
        await _run_indexing_with_notifications(
            session=session,
            connector_id=connector_id,
            workspace_id=workspace_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            indexing_function=index_notion_pages,
            update_timestamp_func=_update_connector_timestamp_by_id,
            supports_retry_callback=True,  # Notion connector supports retry notifications
            supports_heartbeat_callback=True,  # Notion connector supports heartbeat notifications
        )
async def run_notion_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Notion indexing.

    Args:
        session: Database session
        connector_id: ID of the Notion connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_notion_pages

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_notion_pages,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_retry_callback=True,  # Notion connector supports retry notifications
        supports_heartbeat_callback=True,  # Notion connector supports heartbeat notifications
    )

__all__ = ['run_notion_indexing', 'run_notion_indexing_with_new_session']
