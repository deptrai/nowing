"""Document index_local Celery tasks."""

import asyncio
import contextlib
import logging
from uuid import UUID

from app.celery_app import celery_app
from app.notifications.service import NotificationService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.connector_indexers.local_folder_indexer import (
    index_local_folder,
    index_uploaded_files,
)

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


@celery_app.task(name="index_local_folder", bind=True)
def index_local_folder_task(
    self,
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    exclude_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
    root_folder_id: int | None = None,
    target_file_paths: list[str] | None = None,
):
    """Celery task to index a local folder. Config is passed directly — no connector row."""
    return run_async_celery_task(
        lambda: _index_local_folder_async(
            workspace_id=workspace_id,
            user_id=user_id,
            folder_path=folder_path,
            folder_name=folder_name,
            exclude_patterns=exclude_patterns,
            file_extensions=file_extensions,
            root_folder_id=root_folder_id,
            target_file_paths=target_file_paths,
        )
    )
async def _index_local_folder_async(
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    exclude_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
    root_folder_id: int | None = None,
    target_file_paths: list[str] | None = None,
):
    """Run local folder indexing with notification + heartbeat."""
    is_batch = bool(target_file_paths)
    is_full_scan = not target_file_paths
    file_count = len(target_file_paths) if target_file_paths else None

    if is_batch:
        doc_name = f"{folder_name} ({file_count} file{'s' if file_count != 1 else ''})"
    else:
        doc_name = folder_name

    notification = None
    notification_id: int | None = None
    heartbeat_task = None

    async with get_celery_session_maker()() as session:
        try:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="LOCAL_FOLDER_FILE",
                    document_name=doc_name,
                    workspace_id=workspace_id,
                )
            )
            notification_id = notification.id
            _start_heartbeat(notification_id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification_id))
        except Exception:
            logger.warning(
                "Failed to create notification for local folder indexing",
                exc_info=True,
            )

        async def _heartbeat_progress(completed_count: int) -> None:
            """Refresh heartbeat and optionally update notification progress."""
            if notification:
                with contextlib.suppress(Exception):
                    await NotificationService.document_processing.notify_processing_progress(
                        session=session,
                        notification=notification,
                        stage="indexing",
                        stage_message=f"Syncing files ({completed_count}/{file_count or '?'})",
                    )

        try:
            _indexed, _skipped_or_failed, _rfid, err = await index_local_folder(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                folder_path=folder_path,
                folder_name=folder_name,
                exclude_patterns=exclude_patterns,
                file_extensions=file_extensions,
                root_folder_id=root_folder_id,
                target_file_paths=target_file_paths,
                on_heartbeat_callback=_heartbeat_progress
                if (is_batch or is_full_scan)
                else None,
            )

            if notification:
                try:
                    await session.refresh(notification)
                    if err:
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message=err,
                        )
                    else:
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                        )
                except Exception:
                    logger.warning(
                        "Failed to update notification after local folder indexing",
                        exc_info=True,
                    )

        except Exception as e:
            logger.exception(f"Local folder indexing failed: {e}")
            if notification:
                try:
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:200],
                    )
                except Exception:
                    pass
            raise
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification_id is not None:
                _stop_heartbeat(notification_id)
@celery_app.task(name="index_uploaded_folder_files", bind=True)
def index_uploaded_folder_files_task(
    self,
    workspace_id: int,
    user_id: str,
    folder_name: str,
    root_folder_id: int,
    file_mappings: list[dict],
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
):
    """Celery task to index files uploaded from the desktop app."""
    return run_async_celery_task(
        lambda: _index_uploaded_folder_files_async(
            workspace_id=workspace_id,
            user_id=user_id,
            folder_name=folder_name,
            root_folder_id=root_folder_id,
            file_mappings=file_mappings,
            use_vision_llm=use_vision_llm,
            processing_mode=processing_mode,
        )
    )
async def _index_uploaded_folder_files_async(
    workspace_id: int,
    user_id: str,
    folder_name: str,
    root_folder_id: int,
    file_mappings: list[dict],
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
):
    """Run upload-based folder indexing with notification + heartbeat."""
    file_count = len(file_mappings)
    doc_name = f"{folder_name} ({file_count} file{'s' if file_count != 1 else ''})"

    notification = None
    notification_id: int | None = None
    heartbeat_task = None

    async with get_celery_session_maker()() as session:
        try:
            notification = (
                await NotificationService.document_processing.notify_processing_started(
                    session=session,
                    user_id=UUID(user_id),
                    document_type="LOCAL_FOLDER_FILE",
                    document_name=doc_name,
                    workspace_id=workspace_id,
                )
            )
            notification_id = notification.id
            _start_heartbeat(notification_id)
            heartbeat_task = asyncio.create_task(_run_heartbeat_loop(notification_id))
        except Exception:
            logger.warning(
                "Failed to create notification for uploaded folder indexing",
                exc_info=True,
            )

        async def _heartbeat_progress(completed_count: int) -> None:
            if notification:
                with contextlib.suppress(Exception):
                    await NotificationService.document_processing.notify_processing_progress(
                        session=session,
                        notification=notification,
                        stage="indexing",
                        stage_message=f"Syncing files ({completed_count}/{file_count})",
                    )

        try:
            _indexed, _failed, err = await index_uploaded_files(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                folder_name=folder_name,
                root_folder_id=root_folder_id,
                file_mappings=file_mappings,
                on_heartbeat_callback=_heartbeat_progress,
                use_vision_llm=use_vision_llm,
                processing_mode=processing_mode,
            )

            if notification:
                try:
                    await session.refresh(notification)
                    if err:
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                            error_message=err,
                        )
                    else:
                        await NotificationService.document_processing.notify_processing_completed(
                            session=session,
                            notification=notification,
                        )
                except Exception:
                    logger.warning(
                        "Failed to update notification after uploaded folder indexing",
                        exc_info=True,
                    )

        except Exception as e:
            logger.exception(f"Uploaded folder indexing failed: {e}")
            if notification:
                try:
                    await session.refresh(notification)
                    await NotificationService.document_processing.notify_processing_completed(
                        session=session,
                        notification=notification,
                        error_message=str(e)[:200],
                    )
                except Exception:
                    pass
            raise
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            if notification_id is not None:
                _stop_heartbeat(notification_id)
