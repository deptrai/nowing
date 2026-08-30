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



async def run_composio_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Composio indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_composio_indexing(
            session, connector_id, workspace_id, user_id, start_date, end_date
        )
async def run_composio_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str | None,
    end_date: str | None,
):
    """
    Run Composio connector indexing with real-time notifications.

    This wraps the Composio indexer with the notification system so that
    Zero can sync indexing progress to the frontend in real-time.

    Args:
        session: Database session
        connector_id: ID of the Composio connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.composio_indexer import index_composio_connector

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_composio_connector,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )


__all__ = ['run_composio_indexing', 'run_composio_indexing_with_new_session']
