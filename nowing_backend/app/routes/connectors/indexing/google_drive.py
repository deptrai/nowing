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
from app.schemas import GoogleDriveIndexRequest

from .._shared import (
    _is_auth_error,
    _persist_auth_expired,
    _update_connector_timestamp_by_id,
)

logger = logging.getLogger(__name__)


async def run_google_drive_indexing(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    items_dict: dict,  # Dictionary with 'folders', 'files', and 'indexing_options'
):
    """Runs the Google Drive indexing task for folders and files with notifications."""
    from uuid import UUID

    notification = None
    try:
        from app.tasks.connector_indexers.google_drive_indexer import (
            index_google_drive_files,
            index_google_drive_selected_files,
        )

        # Parse the structured data
        items = GoogleDriveIndexRequest(**items_dict)
        indexing_options = items.indexing_options
        total_indexed = 0
        total_skipped = 0
        errors = []

        # Get connector info for notification
        connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()

        if connector:
            # Create notification when indexing starts
            notification = await NotificationService.connector_indexing.notify_google_drive_indexing_started(
                session=session,
                user_id=UUID(user_id),
                connector_id=connector_id,
                connector_name=connector.name,
                connector_type=connector.connector_type.value,
                workspace_id=workspace_id,
                folder_count=len(items.folders),
                file_count=len(items.files),
                folder_names=items.get_folder_names() if items.folders else None,
                file_names=items.get_file_names() if items.files else None,
            )

        # Update notification to fetching stage
        if notification:
            await NotificationService.connector_indexing.notify_indexing_progress(
                session=session,
                notification=notification,
                indexed_count=0,
                stage="fetching",
            )

        total_unsupported = 0

        # Index each folder with indexing options
        for folder in items.folders:
            try:
                (
                    indexed_count,
                    skipped_count,
                    error_message,
                    unsupported_count,
                ) = await index_google_drive_files(
                    session,
                    connector_id,
                    workspace_id,
                    user_id,
                    folder_id=folder.id,
                    folder_name=folder.name,
                    use_delta_sync=indexing_options.incremental_sync,
                    update_last_indexed=False,
                    max_files=indexing_options.max_files_per_folder,
                    include_subfolders=indexing_options.include_subfolders,
                )
                total_skipped += skipped_count
                total_unsupported += unsupported_count
                if error_message:
                    errors.append(f"Folder '{folder.name}': {error_message}")
                else:
                    total_indexed += indexed_count
            except (OSError, RuntimeError, TypeError, ValueError) as e:
                errors.append(f"Folder '{folder.name}': {e!s}")
                logger.error(
                    f"Error indexing folder {folder.name} ({folder.id}): {e}",
                    exc_info=True,
                )

        # Index all selected files together via the parallel pipeline
        if items.files:
            try:
                file_tuples = [(f.id, f.name) for f in items.files]
                (
                    indexed_count,
                    _skipped,
                    file_errors,
                ) = await index_google_drive_selected_files(
                    session,
                    connector_id,
                    workspace_id,
                    user_id,
                    files=file_tuples,
                )
                total_indexed += indexed_count
                errors.extend(file_errors)
            except (OSError, RuntimeError, TypeError, ValueError) as e:
                errors.append(f"File batch indexing: {e!s}")
                logger.error(
                    f"Error batch indexing files: {e}",
                    exc_info=True,
                )

        # Prepare error message for notification
        error_message = None
        if errors:
            error_message = "; ".join(errors)
            logger.error(
                f"Google Drive indexing completed with errors for connector {connector_id}: {error_message}"
            )
            if _is_auth_error(error_message):
                await _persist_auth_expired(session, connector_id)
                error_message = (
                    "Google Drive authentication expired. Please re-authenticate."
                )
        else:
            # Update notification to storing stage
            if notification:
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=total_indexed,
                    stage="storing",
                )

            logger.info(
                f"Google Drive indexing successful for connector {connector_id}. Indexed {total_indexed} documents from {len(items.folders)} folder(s) and {len(items.files)} file(s)."
            )
            # Update the last indexed timestamp only on full success
            await _update_connector_timestamp_by_id(session, connector_id)
            await session.commit()  # Commit timestamp update

        # Update notification on completion
        if notification:
            # Refresh notification to reload attributes that may have been expired by earlier commits
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
            f"Critical error in run_google_drive_indexing for connector {connector_id}: {e}",
            exc_info=True,
        )

        # Update notification on exception
        if notification:
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=0,
                    error_message=str(e),
                )
            except (SQLAlchemyError, OSError, TypeError, ValueError) as notif_error:
                logger.error(f"Failed to update notification: {notif_error!s}")


async def run_google_drive_indexing_with_new_session(
    connector_id: int,
    workspace_id: int,
    user_id: str,
    items_dict: dict,
):
    """Wrapper to run Google Drive indexing with its own database session."""
    logger.info(
        f"Background task started: Indexing Google Drive connector {connector_id} into space {workspace_id}"
    )
    async with async_session_maker() as session:
        await run_google_drive_indexing(
            session, connector_id, workspace_id, user_id, items_dict
        )
    logger.info(
        f"Background task finished: Indexing Google Drive connector {connector_id}"
    )


__all__ = ['run_google_drive_indexing', 'run_google_drive_indexing_with_new_session']
