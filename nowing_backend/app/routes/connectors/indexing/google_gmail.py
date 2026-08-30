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



async def run_google_gmail_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Create a new session and run the Google Gmail indexing task.
    This prevents session leaks by creating a dedicated session for the background task.
    """
    async with async_session_maker() as session:
        await run_google_gmail_indexing(
            session, connector_id, workspace_id, user_id, start_date, end_date
        )
async def run_google_gmail_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
):
    """
    Background task to run Google Gmail indexing.

    Args:
        session: Database session
        connector_id: ID of the Google Gmail connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
    """
    from app.tasks.connector_indexers import index_google_gmail_messages

    # Create a wrapper function that calls index_google_gmail_messages with max_messages
    async def gmail_indexing_wrapper(
        session: AsyncSession,
        connector_id: int,
        workspace_id: int,
        user_id: str,
        start_date: str | None,
        end_date: str | None,
        update_last_indexed: bool,
        on_heartbeat_callback=None,
    ) -> tuple[int, int, str | None]:
        max_messages = 1000
        indexed_count, skipped_count, error_message = await index_google_gmail_messages(
            session=session,
            connector_id=connector_id,
            workspace_id=workspace_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            update_last_indexed=update_last_indexed,
            max_messages=max_messages,
            on_heartbeat_callback=on_heartbeat_callback,
        )
        return indexed_count, skipped_count, error_message if error_message else None

    await _run_indexing_with_notifications(
        session=session,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        indexing_function=gmail_indexing_wrapper,
        update_timestamp_func=_update_connector_timestamp_by_id,
        supports_heartbeat_callback=True,
    )

__all__ = ['run_google_gmail_indexing', 'run_google_gmail_indexing_with_new_session']
