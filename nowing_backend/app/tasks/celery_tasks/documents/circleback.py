"""Document circleback Celery tasks."""

import asyncio
import logging
from uuid import UUID

from app.celery_app import celery_app
from app.notifications.service import NotificationService
from app.services.task_logging_service import TaskLoggingService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .heartbeat import _run_heartbeat_loop, _start_heartbeat, _stop_heartbeat

logger = logging.getLogger(__name__)

# ===== Redis heartbeat for document processing tasks =====
# Same mechanism as connector indexing heartbeats (app/routes/connectors/_shared.py).
# A background coroutine refreshes a Redis key every 60s with a 2-min TTL.
# If the Celery worker crashes, the coroutine dies, the key expires, and the
# stale_notification_cleanup_task detects the missing key and marks the
# notification + document as failed.
_doc_heartbeat_redis = None
HEARTBEAT_TTL_SECONDS = 120  # 2 minutes — same as connector indexing
HEARTBEAT_REFRESH_INTERVAL = 60  # Refresh every 60 seconds


@celery_app.task(name="process_circleback_meeting", bind=True)
def process_circleback_meeting_task(
    self,
    meeting_id: int,
    meeting_name: str,
    markdown_content: str,
    metadata: dict,
    workspace_id: int,
    connector_id: int | None = None,
):
    """
    Celery task to process Circleback meeting webhook data.

    Args:
        meeting_id: Circleback meeting ID
        meeting_name: Name of the meeting
        markdown_content: Meeting content formatted as markdown
        metadata: Meeting metadata dictionary
        workspace_id: ID of the workspace
        connector_id: ID of the Circleback connector (for deletion support)
    """
    return run_async_celery_task(
        lambda: _process_circleback_meeting(
            meeting_id,
            meeting_name,
            markdown_content,
            metadata,
            workspace_id,
            connector_id,
        )
    )
async def _process_circleback_meeting(
    meeting_id: int,
    meeting_name: str,
    markdown_content: str,
    metadata: dict,
    workspace_id: int,
    connector_id: int | None = None,
):
    """Process Circleback meeting with new session."""
    from app.tasks.document_processors.circleback_processor import (
        add_circleback_meeting_document,
    )

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, workspace_id)

        # Get user_id from metadata if available
        user_id = metadata.get("user_id")

        # Create notification if user_id is available
        notification = None
        heartbeat_task = None
        if user_id:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="CIRCLEBACK",
                    document_name=f"Meeting: {meeting_name[:40]}",
                    workspace_id=workspace_id,
                )
            )

            # Start Redis heartbeat for stale task detection
            _start_heartbeat(notification.id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))

        log_entry = await task_logger.log_task_start(
            task_name="process_circleback_meeting",
            source="circleback_webhook",
            message=f"Starting Circleback meeting processing: {meeting_name}",
            metadata={
                "document_type": "CIRCLEBACK",
                "meeting_id": meeting_id,
                "meeting_name": meeting_name,
                **metadata,
            },
        )

        try:
            # Update notification: parsing stage
            if notification:
                await (
                    NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Reading meeting notes",
                    )
                )

            result = await add_circleback_meeting_document(
                session=session,
                meeting_id=meeting_id,
                meeting_name=meeting_name,
                markdown_content=markdown_content,
                metadata=metadata,
                workspace_id=workspace_id,
                connector_id=connector_id,
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed Circleback meeting: {meeting_name}",
                    {
                        "document_id": result.id,
                        "meeting_id": meeting_id,
                        "content_hash": result.content_hash,
                    },
                )

                # Update notification on success
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Circleback meeting document already exists (duplicate): {meeting_name}",
                    {"duplicate_detected": True, "meeting_id": meeting_id},
                )

                # Update notification for duplicate
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Meeting already saved (duplicate)",
                    )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process Circleback meeting: {meeting_name}",
                str(e),
                {"error_type": type(e).__name__, "meeting_id": meeting_id},
            )

            # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
            if notification:
                try:
                    # Refresh notification to ensure it's not stale after any rollback
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )

            logger.error(f"Error processing Circleback meeting: {e!s}")
            raise
        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification:
                _stop_heartbeat(notification.id)
