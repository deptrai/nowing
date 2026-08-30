"""Document process_extension Celery tasks."""

import logging
from uuid import UUID

from app.celery_app import celery_app
from app.notifications.service import NotificationService
from app.services.task_logging_service import TaskLoggingService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.document_processors import (
    add_extension_received_document,
)

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


@celery_app.task(name="process_extension_document", bind=True)
def process_extension_document_task(
    self, individual_document_dict, workspace_id: int, user_id: str
):
    """
    Celery task to process extension document.

    Args:
        individual_document_dict: Document data as dictionary
        workspace_id: ID of the workspace
        user_id: ID of the user
    """
    return run_async_celery_task(
        lambda: _process_extension_document(
            individual_document_dict, workspace_id, user_id
        )
    )
async def _process_extension_document(
    individual_document_dict, workspace_id: int, user_id: str
):
    """Process extension document with new session."""
    from pydantic import BaseModel, ConfigDict, Field

    # Reconstruct the document object from dict
    # You'll need to define the proper model for this
    class DocumentMetadata(BaseModel):
        VisitedWebPageTitle: str
        VisitedWebPageURL: str
        BrowsingSessionId: str
        VisitedWebPageDateWithTimeInISOString: str
        VisitedWebPageReffererURL: str
        VisitedWebPageVisitDurationInMilliseconds: str

    class IndividualDocument(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        metadata: DocumentMetadata
        page_content: str = Field(alias="pageContent")

    individual_document = IndividualDocument(**individual_document_dict)

    async with get_celery_session_maker()() as session:
        task_logger = TaskLoggingService(session, workspace_id)

        # Truncate title for notification display
        page_title = individual_document.metadata.VisitedWebPageTitle[:50]
        if len(individual_document.metadata.VisitedWebPageTitle) > 50:
            page_title += "..."

        # Create notification for document processing
        notification = (
            await NotificationService.document_processing.notify_processing_started(
                session=session,
                user_id=UUID(user_id),
                document_type="EXTENSION",
                document_name=page_title,
                workspace_id=workspace_id,
            )
        )

        log_entry = await task_logger.log_task_start(
            task_name="process_extension_document",
            source="document_processor",
            message=f"Starting processing of extension document from {individual_document.metadata.VisitedWebPageTitle}",
            metadata={
                "document_type": "EXTENSION",
                "url": individual_document.metadata.VisitedWebPageURL,
                "title": individual_document.metadata.VisitedWebPageTitle,
                "user_id": user_id,
            },
        )

        try:
            # Update notification: parsing stage
            await NotificationService.document_processing.notify_processing_progress(
                session,
                notification,
                stage="parsing",
                stage_message="Reading page content",
            )

            result = await add_extension_received_document(
                session, individual_document, workspace_id, user_id
            )

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed extension document: {individual_document.metadata.VisitedWebPageTitle}",
                    {"document_id": result.id, "content_hash": result.content_hash},
                )

                # Update notification on success
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                )
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Extension document already exists (duplicate): {individual_document.metadata.VisitedWebPageTitle}",
                    {"duplicate_detected": True},
                )

                # Update notification for duplicate
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Page already saved (duplicate)",
                    )
                )
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to process extension document: {individual_document.metadata.VisitedWebPageTitle}",
                str(e),
                {"error_type": type(e).__name__},
            )

            # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
            try:
                # Refresh notification to ensure it's not stale after any rollback
                await session.refresh(notification)
                await (
                    NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:100],
                    )
                )
            except Exception as notif_error:
                logger.error(
                    f"Failed to update notification on failure: {notif_error!s}"
                )

            logger.error(f"Error processing extension document: {e!s}")
            raise
