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



async def run_github_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """Wrapper to run GitHub indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing GitHub connector {connector_id} into space {workspace_id} from {start_date} to {end_date}"
    )
    async with async_session_maker() as session:
        await run_github_indexing(
            session, connector_id, workspace_id, user_id, start_date, end_date
        )
    logger.info(f"Background task finished: Indexing GitHub connector {connector_id}")
async def run_github_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run GitHub indexing.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_github_repos

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=index_github_repos,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )

__all__ = ['run_github_indexing', 'run_github_indexing_with_new_session']
