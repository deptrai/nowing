"""Document process_upload Celery tasks."""

import asyncio
import logging
import os
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


@celery_app.task(name="process_file_upload", bind=True)
def process_file_upload_task(
    self, file_path: str, filename: str, workspace_id: int, user_id: str
):
    """
    Celery task to process uploaded file.

    Args:
        file_path: Path to the uploaded file
        filename: Original filename
        workspace_id: ID of the workspace
        user_id: ID of the user
    """
    import traceback

    logger.info(
        f"[process_file_upload] Task started - file: {filename}, "
        f"workspace_id: {workspace_id}, user_id: {user_id}"
    )
    logger.info(f"[process_file_upload] File path: {file_path}")

    # Check if file exists and is accessible
    if not os.path.exists(file_path):
        logger.error(
            f"[process_file_upload] File does not exist: {file_path}. "
            "File may have been removed before syncing could start."
        )
        return

    try:
        file_size = os.path.getsize(file_path)
        logger.info(f"[process_file_upload] File size: {file_size} bytes")
    except Exception as e:
        logger.warning(f"[process_file_upload] Could not get file size: {e}")

    try:
        run_async_celery_task(
            lambda: _process_file_upload(file_path, filename, workspace_id, user_id)
        )
        logger.info(
            f"[process_file_upload] Task completed successfully for: {filename}"
        )
    except Exception as e:
        logger.error(
            f"[process_file_upload] Task failed for {filename}: {e}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        raise
async def _process_file_upload(
    file_path: str, filename: str, workspace_id: int, user_id: str
):
    """Process file upload with new session."""
    from app.tasks.document_processors.file_processors import process_file_in_background

    logger.info(f"[_process_file_upload] Starting async processing for: {filename}")

    async with get_celery_session_maker()() as session:
        logger.info(f"[_process_file_upload] Database session created for: {filename}")
        task_logger = TaskLoggingService(session, workspace_id)

        # Get file size for notification metadata
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"[_process_file_upload] File size: {file_size} bytes")
        except Exception as e:
            logger.warning(f"[_process_file_upload] Could not get file size: {e}")
            file_size = None

        # Create notification for document processing
        logger.info(f"[_process_file_upload] Creating notification for: {filename}")
        notification = None
        heartbeat_task = None
        try:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="FILE",
                    document_name=filename,
                    workspace_id=workspace_id,
                    file_size=file_size,
                )
            )
            logger.info(
                f"[_process_file_upload] Notification created with ID: {notification.id}"
            )
            _start_heartbeat(notification.id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))
        except Exception:
            logger.warning(
                f"[_process_file_upload] Failed to create notification for: {filename}",
                exc_info=True,
            )

        log_entry = await task_logger.log_task_start(
            task_name="process_file_upload",
            source="document_processor",
            message=f"Starting file processing for: {filename}",
            metadata={
                "document_type": "FILE",
                "filename": filename,
                "file_path": file_path,
                "user_id": user_id,
            },
        )

        try:
            result = await process_file_in_background(
                file_path,
                filename,
                workspace_id,
                user_id,
                session,
                task_logger,
                log_entry,
                notification=notification,
            )

            # Update notification on success
            if result:
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
            else:
                # Duplicate detected
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Document already exists (duplicate)",
                    )

        except Exception as e:
            # Import here to avoid circular dependencies
            from fastapi import HTTPException

            from app.services.etl_credit_service import InsufficientCreditsError

            # Check if this is an insufficient-credit error (either direct or
            # wrapped in HTTPException)
            credit_error: InsufficientCreditsError | None = None
            if isinstance(e, InsufficientCreditsError):
                credit_error = e
            elif (
                isinstance(e, HTTPException)
                and e.__cause__
                and isinstance(e.__cause__, InsufficientCreditsError)
            ):
                # HTTPException wraps the original InsufficientCreditsError
                credit_error = e.__cause__
            elif isinstance(e, HTTPException) and "credit" in str(e.detail).lower():
                # Fallback: HTTPException with credit message but no cause
                credit_error = None  # We don't have the details

            # For insufficient-credit errors, create a dedicated notification
            if credit_error is not None:
                error_message = str(credit_error)
                # Create a dedicated insufficient credits notification
                try:
                    if notification:
                        await session.refresh(notification)
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message="Insufficient credits",
                        )

                    # Then create a separate insufficient_credits notification for better UX
                    await NotificationService.insufficient_credits.notify_insufficient_credits(
                        session=session,
                        user_id=UUID(user_id),
                        document_name=filename,
                        document_type="FILE",
                        workspace_id=workspace_id,
                        balance_micros=credit_error.balance_micros,
                        required_micros=credit_error.required_micros,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to create insufficient credits notification: {notif_error!s}"
                    )
            elif isinstance(e, HTTPException) and "credit" in str(e.detail).lower():
                # HTTPException with page limit message but no detailed cause
                error_message = str(e.detail)
                try:
                    if notification:
                        await session.refresh(notification)
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message=error_message,
                        )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )
            else:
                error_message = str(e)[:100]
                # Update notification on failure - wrapped in try-except to ensure it doesn't fail silently
                try:
                    if notification:
                        await session.refresh(notification)
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message=error_message,
                        )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to update notification on failure: {notif_error!s}"
                    )

            await task_logger.log_task_failure(
                log_entry,
                error_message,
                str(e),
                {"error_type": type(e).__name__},
            )
            logger.error(error_message)
            raise
        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification:
                _stop_heartbeat(notification.id)
@celery_app.task(name="process_file_upload_with_document", bind=True)
def process_file_upload_with_document_task(
    self,
    document_id: int,
    temp_path: str,
    filename: str,
    workspace_id: int,
    user_id: str,
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
):
    """
    Celery task to process uploaded file with existing pending document.

    This task is used by the 2-phase document upload flow:
    - Phase 1 (API): Creates pending document (visible in UI immediately)
    - Phase 2 (this task): Updates document status: pending → processing → ready/failed

    Args:
        document_id: ID of the pending document created in Phase 1
        temp_path: Path to the uploaded file
        filename: Original filename
        workspace_id: ID of the workspace
        user_id: ID of the user
    """
    import traceback

    logger.info(
        f"[process_file_upload_with_document] Task started - document_id: {document_id}, "
        f"file: {filename}, workspace_id: {workspace_id}"
    )

    # Check if file exists and is accessible
    if not os.path.exists(temp_path):
        logger.error(
            f"[process_file_upload_with_document] File does not exist: {temp_path}. "
            "File may have been removed before syncing could start."
        )
        # Mark document as failed since file is missing
        run_async_celery_task(
            lambda: _mark_document_failed(
                document_id,
                "File not found. Please re-upload the file.",
            )
        )
        return

    try:
        run_async_celery_task(
            lambda: _process_file_with_document(
                document_id,
                temp_path,
                filename,
                workspace_id,
                user_id,
                use_vision_llm=use_vision_llm,
                processing_mode=processing_mode,
            )
        )
        logger.info(
            f"[process_file_upload_with_document] Task completed successfully for: {filename}"
        )
    except Exception as e:
        logger.error(
            f"[process_file_upload_with_document] Task failed for {filename}: {e}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        raise
async def _mark_document_failed(document_id: int, reason: str):
    """Mark a document as failed when task cannot proceed."""
    from app.db import Document, DocumentStatus
    from app.tasks.document_processors.base import get_current_timestamp

    async with get_celery_session_maker()() as session:
        document = await session.get(Document, document_id)
        if document:
            document.status = DocumentStatus.failed(reason)
            document.updated_at = get_current_timestamp()
            await session.commit()
            logger.info(f"Marked document {document_id} as failed: {reason}")
async def _process_file_with_document(
    document_id: int,
    temp_path: str,
    filename: str,
    workspace_id: int,
    user_id: str,
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
):
    """
    Process file and update existing pending document status.

    This function implements Phase 2 of the 2-phase document upload:
    - Sets document status to 'processing' (shows spinner in UI)
    - Processes the file (parsing, embedding, chunking)
    - Updates document to 'ready' on success or 'failed' on error
    """
    from app.db import Document, DocumentStatus
    from app.tasks.document_processors.base import get_current_timestamp
    from app.tasks.document_processors.file_processors import (
        process_file_in_background_with_document,
    )

    logger.info(
        f"[_process_file_with_document] Starting async processing for: {filename}"
    )

    async with get_celery_session_maker()() as session:
        logger.info(
            f"[_process_file_with_document] Database session created for: {filename}"
        )
        task_logger = TaskLoggingService(session, workspace_id)

        # Get the document
        document = await session.get(Document, document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        # Get file size for notification metadata
        try:
            file_size = os.path.getsize(temp_path)
            logger.info(f"[_process_file_with_document] File size: {file_size} bytes")
        except Exception as e:
            logger.warning(
                f"[_process_file_with_document] Could not get file size: {e}"
            )
            file_size = None

        # Create notification for document processing
        logger.info(
            f"[_process_file_with_document] Creating notification for: {filename}"
        )
        notification = None
        heartbeat_task = None
        try:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="FILE",
                    document_name=filename,
                    workspace_id=workspace_id,
                    file_size=file_size,
                )
            )

            # Store document_id in notification metadata so cleanup task can find the document
            if notification.notification_metadata is not None:
                notification.notification_metadata["document_id"] = document_id
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(notification, "notification_metadata")
                await session.commit()
                await session.refresh(notification)

            _start_heartbeat(notification.id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification.id))
        except Exception:
            logger.warning(
                f"[_process_file_with_document] Failed to create notification for: {filename}",
                exc_info=True,
            )

        log_entry = await task_logger.log_task_start(
            task_name="process_file_upload_with_document",
            source="document_processor",
            message=f"Starting file processing for: {filename} (document_id: {document_id})",
            metadata={
                "document_type": "FILE",
                "document_id": document_id,
                "filename": filename,
                "file_path": temp_path,
                "user_id": user_id,
            },
        )

        try:
            # Set status to PROCESSING (shows spinner in UI via Zero)
            document.status = DocumentStatus.processing()
            await session.commit()
            logger.info(
                f"[_process_file_with_document] Document {document_id} status set to 'processing'"
            )

            # Process the file and update document
            result = await process_file_in_background_with_document(
                document=document,
                file_path=temp_path,
                filename=filename,
                workspace_id=workspace_id,
                user_id=user_id,
                session=session,
                task_logger=task_logger,
                log_entry=log_entry,
                notification=notification,
                use_vision_llm=use_vision_llm,
                processing_mode=processing_mode,
            )

            # Update notification on success
            if result:
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        document_id=result.id,
                        chunks_count=None,
                    )
                logger.info(
                    f"[_process_file_with_document] Successfully processed document {document_id}"
                )
            else:
                # Duplicate detected - mark as failed
                document.status = DocumentStatus.failed("Duplicate content detected")
                document.updated_at = get_current_timestamp()
                await session.commit()
                if notification:
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message="Document already exists (duplicate)",
                    )

        except Exception as e:
            # Import here to avoid circular dependencies
            from fastapi import HTTPException

            from app.services.etl_credit_service import InsufficientCreditsError

            # Check if this is an insufficient-credit error
            credit_error: InsufficientCreditsError | None = None
            if isinstance(e, InsufficientCreditsError):
                credit_error = e
            elif (
                isinstance(e, HTTPException)
                and e.__cause__
                and isinstance(e.__cause__, InsufficientCreditsError)
            ):
                credit_error = e.__cause__

            # Mark document as failed (shows error in UI via Zero)
            error_message = str(e)[:500]
            document.status = DocumentStatus.failed(error_message)
            document.updated_at = get_current_timestamp()
            await session.commit()
            logger.info(
                f"[_process_file_with_document] Document {document_id} marked as failed: {error_message[:100]}"
            )

            # Handle insufficient-credit errors with dedicated notification
            if credit_error is not None:
                try:
                    if notification:
                        await session.refresh(notification)
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message="Insufficient credits",
                        )
                    await NotificationService.insufficient_credits.notify_insufficient_credits(
                        session=session,
                        user_id=UUID(user_id),
                        document_name=filename,
                        document_type="FILE",
                        workspace_id=workspace_id,
                        balance_micros=credit_error.balance_micros,
                        required_micros=credit_error.required_micros,
                    )
                except Exception as notif_error:
                    logger.error(
                        f"Failed to create insufficient credits notification: {notif_error!s}"
                    )
            else:
                # Update notification on failure
                try:
                    if notification:
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

            await task_logger.log_task_failure(
                log_entry,
                error_message[:100],
                str(e),
                {"error_type": type(e).__name__, "document_id": document_id},
            )
            logger.error(f"Error processing file {filename}: {e!s}")
            raise

        finally:
            # Stop heartbeat — key deleted on success, expires on crash
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification:
                _stop_heartbeat(notification.id)

            # Clean up temp file
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.info(
                        f"[_process_file_with_document] Cleaned up temp file: {temp_path}"
                    )
                except Exception as cleanup_error:
                    logger.warning(
                        f"[_process_file_with_document] Failed to clean up temp file: {cleanup_error}"
                    )
