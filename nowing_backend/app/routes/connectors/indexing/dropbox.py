"""Connector indexing routes and helpers."""

from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    SearchSourceConnector,
    async_session_maker,
)
from app.notifications.service import NotificationService

from .._shared import (
    _is_auth_error,
    _persist_auth_expired,
    _update_connector_timestamp_by_id,
)

logger = logging.getLogger(__name__)


async def run_dropbox_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    items_dict: dict,
):
    """Runs the Dropbox indexing task for folders and files with notifications."""
    from uuid import UUID

    notification = None
    try:
        from app.tasks.connector_indexers.dropbox_indexer import index_dropbox_files

        connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()

        if connector:
            notification = await NotificationService.connector_indexing.notify_google_drive_indexing_started(
                session=session,
                user_id=UUID(user_id),
                connector_id=connector_id,
                connector_name=connector.name,
                connector_type=connector.connector_type.value,
                workspace_id=workspace_id,
                folder_count=len(items_dict.get("folders", [])),
                file_count=len(items_dict.get("files", [])),
                folder_names=[
                    f.get("name", "Unknown") for f in items_dict.get("folders", [])
                ],
                file_names=[
                    f.get("name", "Unknown") for f in items_dict.get("files", [])
                ],
            )

        if notification:
            await NotificationService.connector_indexing.notify_indexing_progress(
                session=session,
                notification=notification,
                indexed_count=0,
                stage="fetching",
            )

        (
            total_indexed,
            total_skipped,
            error_message,
            total_unsupported,
        ) = await index_dropbox_files(
            session,
            connector_id,
            workspace_id,
            user_id,
            items_dict,
        )

        if error_message:
            logger.error(
                f"Dropbox indexing completed with errors for connector {connector_id}: {error_message}"
            )
            if _is_auth_error(error_message):
                await _persist_auth_expired(session, connector_id)
                error_message = (
                    "Dropbox authentication expired. Please re-authenticate."
                )
        else:
            if notification:
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=total_indexed,
                    stage="storing",
                )

            logger.info(
                f"Dropbox indexing successful for connector {connector_id}. Indexed {total_indexed} documents."
            )
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()

        if notification:
            await session.refresh(notification)
            await NotificationService.connector_indexing.notify_indexing_completed(
                session=session,
                notification=notification,
                indexed_count=total_indexed,
                error_message=error_message,
                skipped_count=total_skipped,
                unsupported_count=total_unsupported,
            )

    except Exception as e:  # Celery task boundary: catch all unhandled indexing failures to release resources and update notifications.
        logger.error(
            f"Critical error in run_dropbox_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        if notification:
            try:
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=0,
                    error_message=str(e),
                )
            except (SQLAlchemyError, OSError, TypeError, ValueError) as notif_error:
                logger.error(f"Failed to update notification: {notif_error!s}")


async def run_dropbox_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    items_dict: dict,
):
    """Wrapper to run Dropbox indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Dropbox connector {connector_id} into space {workspace_id}"
    )
    async with async_session_maker() as session:
        await run_dropbox_indexing(
            session, connector_id, workspace_id, user_id, items_dict
        )
    logger.info(
        f"Background task finished: Indexing Dropbox connector {connector_id}"
    )


__all__ = ['run_dropbox_indexing', 'run_dropbox_indexing_with_new_session']
