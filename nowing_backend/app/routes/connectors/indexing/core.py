"""Connector indexing routes and helpers."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import pytz
import redis
from dateutil.parser import isoparse
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Permission,
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.notifications.service import NotificationService
from app.observability import metrics as ot_metrics, otel as ot
from app.schemas import GoogleDriveIndexRequest
from app.users import get_auth_context
from app.utils.indexing_locks import (
    acquire_connector_indexing_lock,
    release_connector_indexing_lock,
)

from .._shared import (
    HEARTBEAT_TTL_SECONDS,
    _get_heartbeat_key,
    _is_auth_error,
    _persist_auth_expired,
    _run_indexing_heartbeat_loop,
    get_heartbeat_redis_client,
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/search-source-connectors/{connector_id}/index", response_model=dict[str, Any]
)
async def index_connector_content(
    connector_id: int,
    workspace_id: int = Query(
        ..., description="ID of the workspace to store indexed content"
    ),
    start_date: str = Query(
        None,
        description="Start date for indexing (YYYY-MM-DD format). If not provided, uses last_indexed_at or defaults to 365 days ago",
    ),
    end_date: str = Query(
        None,
        description="End date for indexing (YYYY-MM-DD format). If not provided, uses today's date. For calendar connectors (Google Calendar, Luma), future dates can be selected to index upcoming events.",
    ),
    drive_items: GoogleDriveIndexRequest | None = Body(
        None,
        description="[Google Drive only] Structured request with folders and files to index",
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Index content from a KB connector to a workspace.

    Live connectors (Slack, Teams, Linear, Jira, ClickUp, Calendar, Airtable,
    Gmail, Discord, Luma, Notion, Confluence, Exa MCP) use real-time agent tools instead.
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Ensure the connector actually belongs to the requested workspace.
        # Without this, the permission check below would authorize against the
        # caller-supplied workspace_id (their own space) while the connector
        # lives in another user's space, allowing cross-tenant indexing of a
        # foreign connector (and use of its stored credentials). Returning 404
        # (rather than 403) on a mismatch also avoids disclosing the existence of
        # connectors in other workspaces.
        if connector.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check if user has permission to update connectors (indexing is an update
        # operation). Authorize against the connector's OWN workspace — matching
        # the read/update/delete handlers — not the client-supplied query param.
        from . import check_permission

        await check_permission(
            session,
            auth,
            connector.workspace_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to index content in this workspace",
        )

        # Handle different connector types
        response_message = ""
        indexing_started = True
        # Use UTC for consistency with last_indexed_at storage
        today_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Determine the actual date range to use
        if start_date is None:
            # Use last_indexed_at or default to 365 days ago
            if connector.last_indexed_at:
                # Convert last_indexed_at to timezone-naive for comparison (like calculate_date_range does)
                last_indexed_naive = (
                    connector.last_indexed_at.replace(tzinfo=None)
                    if connector.last_indexed_at.tzinfo
                    else connector.last_indexed_at
                )
                # Use UTC for "today" to match how last_indexed_at is stored
                today_utc = datetime.now(UTC).replace(tzinfo=None).date()
                last_indexed_date = last_indexed_naive.date()

                if last_indexed_date == today_utc:
                    # If last indexed today, go back 1 day to ensure we don't miss anything
                    indexing_from = (today_utc - timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    indexing_from = last_indexed_naive.strftime("%Y-%m-%d")
            else:
                indexing_from = (
                    datetime.now(UTC).replace(tzinfo=None) - timedelta(days=365)
                ).strftime("%Y-%m-%d")
        else:
            indexing_from = start_date

        # For calendar connectors, default to today but allow future dates if explicitly provided
        if connector.connector_type in [
            SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        ]:
            # Default to today if no end_date provided (users can manually select future dates)
            indexing_to = today_str if end_date is None else end_date

            # If start_date and end_date are the same, adjust end_date to be one day later
            # to ensure valid date range (start_date must be strictly before end_date)
            if indexing_from == indexing_to:
                dt = isoparse(indexing_to)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=pytz.UTC)
                else:
                    dt = dt.astimezone(pytz.UTC)
                # Add one day to end_date to make it strictly after start_date
                dt_end = dt + timedelta(days=1)
                indexing_to = dt_end.strftime("%Y-%m-%d")
                logger.info(
                    f"Adjusted end_date from {end_date} to {indexing_to} "
                    f"to ensure valid date range (start_date must be strictly before end_date)"
                )
        else:
            # For non-calendar connectors, cap at today
            indexing_to = end_date if end_date else today_str

        from app.services.mcp_oauth.registry import (
            DEPRECATED_INDEXING_CONNECTOR_TYPES,
            LIVE_CONNECTOR_TYPES,
        )

        if connector.connector_type in LIVE_CONNECTOR_TYPES:
            return {
                "message": (
                    f"{connector.connector_type.value} uses real-time agent tools; "
                    "background indexing is disabled."
                ),
                "indexing_started": False,
                "connector_id": connector_id,
                "workspace_id": workspace_id,
                "indexing_from": indexing_from,
                "indexing_to": indexing_to,
            }

        if connector.connector_type in DEPRECATED_INDEXING_CONNECTOR_TYPES:
            return {
                "message": (
                    f"Indexing for {connector.connector_type.value} has been "
                    "deprecated. The knowledge base now stores files, notes, and "
                    "uploads only."
                ),
                "indexing_started": False,
                "connector_id": connector_id,
                "workspace_id": workspace_id,
                "indexing_from": indexing_from,
                "indexing_to": indexing_to,
            }

        if connector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_notion_pages_task

            logger.info(
                f"Triggering Notion indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_notion_pages_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Notion indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.GITHUB_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import index_github_repos_task

            logger.info(
                f"Triggering GitHub indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_github_repos_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "GitHub indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.CONFLUENCE_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_confluence_pages_task,
            )

            logger.info(
                f"Triggering Confluence indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_confluence_pages_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Confluence indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.BOOKSTACK_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_bookstack_pages_task,
            )

            logger.info(
                f"Triggering BookStack indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_bookstack_pages_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "BookStack indexing started in the background."

        elif (
            connector.connector_type == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_drive_files_task,
            )

            if drive_items and drive_items.has_items():
                logger.info(
                    f"Triggering Google Drive indexing for connector {connector_id} into workspace {workspace_id}, "
                    f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
                )
                items_dict = drive_items.model_dump()
            else:
                # Quick Index / periodic sync: fall back to stored config
                config = connector.config or {}
                selected_folders = config.get("selected_folders", [])
                selected_files = config.get("selected_files", [])
                if not selected_folders and not selected_files:
                    raise HTTPException(
                        status_code=400,
                        detail="Google Drive indexing requires folders or files to be configured. "
                        "Please select folders/files to index.",
                    )
                indexing_options = config.get(
                    "indexing_options",
                    {
                        "max_files_per_folder": 100,
                        "incremental_sync": True,
                        "include_subfolders": True,
                    },
                )
                items_dict = {
                    "folders": selected_folders,
                    "files": selected_files,
                    "indexing_options": indexing_options,
                }
                logger.info(
                    f"Triggering Google Drive indexing for connector {connector_id} into workspace {workspace_id} "
                    f"using existing config"
                )

            index_google_drive_files_task.delay(
                connector_id,
                workspace_id,
                str(user.id),
                items_dict,
            )
            response_message = "Google Drive indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.ONEDRIVE_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_onedrive_files_task,
            )

            if drive_items and drive_items.has_items():
                logger.info(
                    f"Triggering OneDrive indexing for connector {connector_id} into workspace {workspace_id}, "
                    f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
                )
                items_dict = drive_items.model_dump()
            else:
                config = connector.config or {}
                selected_folders = config.get("selected_folders", [])
                selected_files = config.get("selected_files", [])
                if not selected_folders and not selected_files:
                    raise HTTPException(
                        status_code=400,
                        detail="OneDrive indexing requires folders or files to be configured. "
                        "Please select folders/files to index.",
                    )
                indexing_options = config.get(
                    "indexing_options",
                    {
                        "max_files_per_folder": 100,
                        "incremental_sync": True,
                        "include_subfolders": True,
                    },
                )
                items_dict = {
                    "folders": selected_folders,
                    "files": selected_files,
                    "indexing_options": indexing_options,
                }
                logger.info(
                    f"Triggering OneDrive indexing for connector {connector_id} into workspace {workspace_id} "
                    f"using existing config"
                )

            index_onedrive_files_task.delay(
                connector_id,
                workspace_id,
                str(user.id),
                items_dict,
            )
            response_message = "OneDrive indexing started in the background."

        elif connector.connector_type == SearchSourceConnectorType.DROPBOX_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_dropbox_files_task,
            )

            if drive_items and drive_items.has_items():
                logger.info(
                    f"Triggering Dropbox indexing for connector {connector_id} into workspace {workspace_id}, "
                    f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
                )
                items_dict = drive_items.model_dump()
            else:
                config = connector.config or {}
                selected_folders = config.get("selected_folders", [])
                selected_files = config.get("selected_files", [])
                if not selected_folders and not selected_files:
                    raise HTTPException(
                        status_code=400,
                        detail="Dropbox indexing requires folders or files to be configured. "
                        "Please select folders/files to index.",
                    )
                indexing_options = config.get(
                    "indexing_options",
                    {
                        "max_files_per_folder": 100,
                        "incremental_sync": True,
                        "include_subfolders": True,
                    },
                )
                items_dict = {
                    "folders": selected_folders,
                    "files": selected_files,
                    "indexing_options": indexing_options,
                }
                logger.info(
                    f"Triggering Dropbox indexing for connector {connector_id} into workspace {workspace_id} "
                    f"using existing config"
                )

            index_dropbox_files_task.delay(
                connector_id,
                workspace_id,
                str(user.id),
                items_dict,
            )
            response_message = "Dropbox indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.ELASTICSEARCH_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_elasticsearch_documents_task,
            )

            logger.info(
                f"Triggering Elasticsearch indexing for connector {connector_id} into workspace {workspace_id}"
            )
            index_elasticsearch_documents_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Elasticsearch indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_drive_files_task,
            )

            # For Composio Google Drive, if drive_items is provided, update connector config
            # This allows the UI to pass folder/file selection like the regular Google Drive connector
            if drive_items and drive_items.has_items():
                # Update connector config with the selected folders/files
                config = connector.config or {}
                config["selected_folders"] = [
                    {"id": f.id, "name": f.name} for f in drive_items.folders
                ]
                config["selected_files"] = [
                    {"id": f.id, "name": f.name} for f in drive_items.files
                ]
                if drive_items.indexing_options:
                    config["indexing_options"] = {
                        "max_files_per_folder": drive_items.indexing_options.max_files_per_folder,
                        "incremental_sync": drive_items.indexing_options.incremental_sync,
                        "include_subfolders": drive_items.indexing_options.include_subfolders,
                    }
                connector.config = config
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(connector, "config")
                await session.commit()
                await session.refresh(connector)

                logger.info(
                    f"Triggering Composio Google Drive indexing for connector {connector_id} into workspace {workspace_id}, "
                    f"folders: {len(drive_items.folders)}, files: {len(drive_items.files)}"
                )
            else:
                logger.info(
                    f"Triggering Composio Google Drive indexing for connector {connector_id} into workspace {workspace_id} "
                    f"using existing config"
                )

            # Extract config and build items_dict for index_google_drive_files_task
            config = connector.config or {}
            selected_folders = config.get("selected_folders", [])
            selected_files = config.get("selected_files", [])
            if not selected_folders and not selected_files:
                raise HTTPException(
                    status_code=400,
                    detail="Composio Google Drive indexing requires folders or files to be configured. "
                    "Please select folders/files to index.",
                )
            indexing_options = config.get(
                "indexing_options",
                {
                    "max_files_per_folder": 100,
                    "incremental_sync": True,
                    "include_subfolders": True,
                },
            )
            items_dict = {
                "folders": selected_folders,
                "files": selected_files,
                "indexing_options": indexing_options,
            }
            index_google_drive_files_task.delay(
                connector_id, workspace_id, str(user.id), items_dict
            )
            response_message = (
                "Composio Google Drive indexing started in the background."
            )

        elif (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_gmail_messages_task,
            )

            logger.info(
                f"Triggering Composio Gmail indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_google_gmail_messages_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Composio Gmail indexing started in the background."

        elif (
            connector.connector_type
            == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_google_calendar_events_task,
            )

            logger.info(
                f"Triggering Composio Google Calendar indexing for connector {connector_id} into workspace {workspace_id} from {indexing_from} to {indexing_to}"
            )
            index_google_calendar_events_task.delay(
                connector_id, workspace_id, str(user.id), indexing_from, indexing_to
            )
            response_message = (
                "Composio Google Calendar indexing started in the background."
            )

        elif connector.connector_type == SearchSourceConnectorType.RSS_FEED:
            from app.tasks.celery_tasks.rss_tasks import index_rss_feeds_task

            logger.info(
                f"Triggering RSS feed indexing for connector {connector_id} into workspace {workspace_id}"
            )
            index_rss_feeds_task.delay(
                connector_id, workspace_id, str(user.id), None, None
            )
            response_message = "RSS feed indexing started in the background."

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Indexing not supported for connector type: {connector.connector_type}",
            )

        return {
            "message": response_message,
            "indexing_started": indexing_started,
            "connector_id": connector_id,
            "workspace_id": workspace_id,
            "indexing_from": indexing_from,
            "indexing_to": indexing_to,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to initiate indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate indexing: {e!s}"
        ) from e


async def _run_indexing_with_notifications(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
    indexing_function,
    update_timestamp_func=None,
    supports_retry_callback: bool = False,
    supports_heartbeat_callback: bool = False,
):
    """
    Generic helper to run indexing with real-time notifications.

    Args:
        session: Database session
        connector_id: ID of the connector
        workspace_id: ID of the workspace
        user_id: ID of the user
        start_date: Start date for indexing
        end_date: End date for indexing
        indexing_function: Async function that performs the indexing
        update_timestamp_func: Optional function to update connector timestamp
        supports_retry_callback: Whether the indexing function supports on_retry_callback
        supports_heartbeat_callback: Whether the indexing function supports on_heartbeat_callback
    """
    from uuid import UUID

    from celery.exceptions import SoftTimeLimitExceeded

    notification = None
    connector_lock_acquired = False
    heartbeat_task: asyncio.Task | None = None
    # Track indexed count for retry notifications and heartbeat
    current_indexed_count = 0

    try:
        connector_lock_acquired = acquire_connector_indexing_lock(connector_id)
        if not connector_lock_acquired:
            ot.add_event(
                "connector.sync.skipped",
                {
                    "skip.reason": "lock_contention",
                    "error.category": "lock_contention",
                },
            )
            logger.info(
                f"Skipping indexing for connector {connector_id} "
                "(another worker already holds Redis connector lock)"
            )
            return

        # Get connector info for notification
        connector_result = await session.execute(
            select(SearchSourceConnector).where(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = connector_result.scalar_one_or_none()

        if connector:
            # Create notification when indexing starts
            notification = (
                await NotificationService.connector_indexing.notify_indexing_started(
                    session=session,
                    user_id=UUID(user_id),
                    connector_id=connector_id,
                    connector_name=connector.name,
                    connector_type=connector.connector_type.value,
                    workspace_id=workspace_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

            # Set initial Redis heartbeat for stale detection
            if notification:
                try:
                    heartbeat_key = _get_heartbeat_key(notification.id)
                    get_heartbeat_redis_client().setex(
                        heartbeat_key, HEARTBEAT_TTL_SECONDS, "0"
                    )
                    ot_metrics.record_celery_heartbeat_refresh(
                        heartbeat_type="connector"
                    )
                except (redis.RedisError, OSError, TypeError, ValueError) as e:
                    ot_metrics.record_celery_heartbeat_failure(
                        heartbeat_type="connector"
                    )
                    logger.warning(f"Failed to set initial Redis heartbeat: {e}")

                # Start a background coroutine that refreshes the
                # heartbeat every HEARTBEAT_REFRESH_INTERVAL seconds.
                # Without this the cleanup_stale_indexing_notifications
                # task can mark the doc failed when on_heartbeat_callback
                # doesn't fire — for example during the GitHub
                # connector's Phase 1 gitingest blocking call (#1295).
                heartbeat_task = asyncio.create_task(
                    _run_indexing_heartbeat_loop(notification.id)
                )

        # Update notification to fetching stage
        if notification:
            await NotificationService.connector_indexing.notify_indexing_progress(
                session=session,
                notification=notification,
                indexed_count=0,
                stage="fetching",
            )

        # Create retry callback for connectors that support it
        async def on_retry_callback(
            retry_reason: str, attempt: int, max_attempts: int, wait_seconds: float
        ) -> None:
            """Callback to update notification during API retries (rate limits, etc.)"""
            nonlocal notification
            ot.add_event(
                "connector.retry.scheduled",
                {
                    "retry.reason": retry_reason,
                    "retry.attempt": attempt,
                    "retry.max": max_attempts,
                    "retry.delay_ms": int(wait_seconds * 1000),
                },
            )
            if notification:
                try:
                    await session.refresh(notification)
                    await NotificationService.connector_indexing.notify_retry_progress(
                        session=session,
                        notification=notification,
                        indexed_count=current_indexed_count,
                        retry_reason=retry_reason,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        wait_seconds=wait_seconds,
                    )
                    await session.commit()
                except (redis.RedisError, OSError, TypeError, ValueError) as e:
                    # Don't let notification errors break the indexing
                    logger.warning(f"Failed to update retry notification: {e}")

        # Create heartbeat callback for connectors that support it
        # This updates the notification periodically during long-running indexing loops
        # to prevent the task from appearing stuck if the worker crashes
        async def on_heartbeat_callback(indexed_count: int) -> None:
            """Callback to update notification during indexing (heartbeat)."""
            nonlocal notification, current_indexed_count
            current_indexed_count = indexed_count
            if notification:
                try:
                    # Set Redis heartbeat key with TTL (fast, for stale detection)
                    heartbeat_key = _get_heartbeat_key(notification.id)
                    get_heartbeat_redis_client().setex(
                        heartbeat_key, HEARTBEAT_TTL_SECONDS, str(indexed_count)
                    )
                    ot_metrics.record_celery_heartbeat_refresh(
                        heartbeat_type="connector"
                    )
                except (redis.RedisError, OSError, TypeError, ValueError) as e:
                    # Don't let Redis errors break the indexing
                    ot_metrics.record_celery_heartbeat_failure(
                        heartbeat_type="connector"
                    )
                    logger.warning(f"Failed to set Redis heartbeat: {e}")

                try:
                    # Still update DB notification for progress display
                    await session.refresh(notification)
                    await (
                        NotificationService.connector_indexing.notify_indexing_progress(
                            session=session,
                            notification=notification,
                            indexed_count=indexed_count,
                            stage="processing",
                        )
                    )
                    await session.commit()
                except (redis.RedisError, OSError, TypeError, ValueError) as e:
                    # Don't let notification errors break the indexing
                    logger.warning(f"Failed to update heartbeat notification: {e}")

        # Build kwargs for indexing function
        indexing_kwargs = {
            "session": session,
            "connector_id": connector_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
            "update_last_indexed": False,
        }

        # Add retry callback for connectors that support it
        if supports_retry_callback:
            indexing_kwargs["on_retry_callback"] = on_retry_callback

        # Add heartbeat callback for connectors that support it
        if supports_heartbeat_callback:
            indexing_kwargs["on_heartbeat_callback"] = on_heartbeat_callback

        # Run the indexing function
        # Some indexers return (indexed, error), others return (indexed, skipped, error)
        result = await indexing_function(**indexing_kwargs)

        # Handle both 2-tuple and 3-tuple returns for backwards compatibility
        if len(result) == 3:
            documents_processed, documents_skipped, error_or_warning = result
        else:
            documents_processed, error_or_warning = result
            documents_skipped = None

        # Update connector timestamp if function provided and indexing was successful
        if documents_processed > 0 and update_timestamp_func:
            # Update notification to storing stage
            if notification:
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    stage="storing",
                )

            await update_timestamp_func(session, connector_id)
            await session.commit()  # Commit timestamp update
            logger.info(
                f"Indexing completed successfully: {documents_processed} documents processed"
            )

            # Update notification on success (or partial success with errors)
            if notification:
                # Refresh notification to ensure it's not stale after timestamp update commit
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    error_message=error_or_warning,  # Show errors even if some documents were indexed
                    skipped_count=documents_skipped,
                )
                await (
                    session.commit()
                )  # Commit to ensure Zero syncs the notification update
        elif documents_processed > 0:
            # Update notification to storing stage
            if notification:
                await NotificationService.connector_indexing.notify_indexing_progress(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    stage="storing",
                )

            # Success but no timestamp update function
            logger.info(
                f"Indexing completed successfully: {documents_processed} documents processed"
            )
            if notification:
                # Refresh notification to ensure it's not stale after indexing function commits
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=documents_processed,
                    error_message=error_or_warning,  # Show errors even if some documents were indexed
                    skipped_count=documents_skipped,
                )
                await (
                    session.commit()
                )  # Commit to ensure Zero syncs the notification update
        else:
            # No new documents processed - check if this is an error or just no changes
            if error_or_warning:
                # Check if this is a duplicate warning or empty result (success cases) or an actual error
                # Handle both normal and Composio calendar connectors
                error_or_warning_lower = (
                    str(error_or_warning).lower() if error_or_warning else ""
                )
                is_duplicate_warning = "skipped (duplicate)" in error_or_warning_lower
                # "No X found" messages are success cases - sync worked, just found nothing in date range
                is_empty_result = (
                    "no " in error_or_warning_lower
                    and "found" in error_or_warning_lower
                )
                # Informational warnings - sync succeeded but some content couldn't be synced
                # These are NOT errors, just notifications about API limitations or recommendations
                is_info_warning = (
                    "couldn't be synced" in error_or_warning_lower
                    or "using legacy token" in error_or_warning_lower
                    or "(api limitation)" in error_or_warning_lower
                )

                if is_duplicate_warning or is_empty_result or is_info_warning:
                    # These are success cases - sync worked, just found nothing new
                    logger.info(f"Indexing completed successfully: {error_or_warning}")
                    # Still update timestamp so Zero syncs and clears "Syncing" UI
                    if update_timestamp_func:
                        await update_timestamp_func(session, connector_id)
                        await session.commit()  # Commit timestamp update
                    if notification:
                        # Refresh notification to ensure it's not stale after timestamp update commit
                        await session.refresh(notification)
                        # For empty results, use a cleaner message
                        notification_message = (
                            "No new items found in date range"
                            if is_empty_result
                            else error_or_warning
                        )
                        await NotificationService.connector_indexing.notify_indexing_completed(
                            session=session,
                            notification=notification,
                            indexed_count=0,
                            error_message=notification_message,  # Pass as warning, not error
                            is_warning=True,  # Flag to indicate this is a warning, not an error
                            skipped_count=documents_skipped,
                        )
                        await (
                            session.commit()
                        )  # Commit to ensure Zero syncs the notification update
                else:
                    # Actual failure
                    logger.error(f"Indexing failed: {error_or_warning}")
                    if _is_auth_error(str(error_or_warning)):
                        await _persist_auth_expired(session, connector_id)
                    if notification:
                        # Refresh notification to ensure it's not stale after indexing function commits
                        await session.refresh(notification)
                        await NotificationService.connector_indexing.notify_indexing_completed(
                            session=session,
                            notification=notification,
                            indexed_count=0,
                            error_message=error_or_warning,
                            skipped_count=documents_skipped,
                        )
                        await (
                            session.commit()
                        )  # Commit to ensure Zero syncs the notification update
            else:
                # Success - just no new documents to index (all skipped/unchanged)
                logger.info(
                    "Indexing completed: No new documents to process (all up to date)"
                )
                # Still update timestamp so Zero syncs and clears "Syncing" UI
                if update_timestamp_func:
                    await update_timestamp_func(session, connector_id)
                    await session.commit()  # Commit timestamp update
                if notification:
                    # Refresh notification to ensure it's not stale after timestamp update commit
                    await session.refresh(notification)
                    await NotificationService.connector_indexing.notify_indexing_completed(
                        session=session,
                        notification=notification,
                        indexed_count=0,
                        error_message=None,  # No error - sync succeeded
                        skipped_count=documents_skipped,
                    )
                    await (
                        session.commit()
                    )  # Commit to ensure Zero syncs the notification update
    except SoftTimeLimitExceeded:
        # Celery soft time limit was reached - task is about to be killed
        # Gracefully save progress and mark as interrupted
        logger.warning(
            f"Soft time limit reached for connector {connector_id}. "
            f"Saving partial progress: {current_indexed_count} items indexed."
        )

        if notification:
            try:
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=current_indexed_count,
                    error_message="Time limit reached. Partial sync completed. Please run again for remaining items.",
                    is_warning=True,  # Mark as warning since partial data was indexed
                )
                await session.commit()
            except (SQLAlchemyError, OSError, TypeError, ValueError) as notif_error:
                logger.error(
                    f"Failed to update notification on soft timeout: {notif_error!s}"
                )

        # Re-raise so Celery knows the task was terminated
        raise
    except Exception as e:  # Celery task boundary: catch all unhandled indexing failures to release resources and update notifications.
        logger.error(f"Error in indexing task: {e!s}", exc_info=True)

        if _is_auth_error(str(e)):
            await _persist_auth_expired(session, connector_id)

        # Update notification on exception
        if notification:
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await NotificationService.connector_indexing.notify_indexing_completed(
                    session=session,
                    notification=notification,
                    indexed_count=current_indexed_count,  # Use tracked count, not 0
                    error_message=str(e),
                    skipped_count=None,  # Unknown on exception
                )
            except (redis.RedisError, OSError, TypeError, ValueError) as notif_error:
                logger.error(f"Failed to update notification: {notif_error!s}")
    finally:
        # Stop the background heartbeat refresher BEFORE deleting the
        # Redis key, so the loop cannot race and re-create the key
        # after we delete it.
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(Exception):
                await asyncio.gather(heartbeat_task, return_exceptions=True)
        # Clean up Redis heartbeat key when task completes (success or failure)
        if notification:
            try:
                heartbeat_key = _get_heartbeat_key(notification.id)
                get_heartbeat_redis_client().delete(heartbeat_key)
            except Exception:  # defensive: ignore cleanup failures
                pass  # Ignore cleanup errors - key will expire anyway
        if connector_lock_acquired:
            with suppress(Exception):
                release_connector_indexing_lock(connector_id)
