"""Public entry points for Google Drive indexing."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.google_drive import get_start_page_token
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    get_connector_by_id,
    update_connector_last_indexed,
)
from app.tasks.connector_indexers.google_drive.client import (
    _build_drive_client_for_connector,
)
from app.tasks.connector_indexers.google_drive.constants import (
    ACCEPTED_DRIVE_CONNECTOR_TYPES,
)
from app.tasks.connector_indexers.google_drive.indexing import (
    _index_selected_files_core,
    _process_single_file_core,
)
from app.tasks.connector_indexers.google_drive.scan import (
    _index_full_scan_core,
    _index_with_delta_sync_core,
)
from app.utils.google_credentials import COMPOSIO_GOOGLE_CONNECTOR_TYPES

logger = logging.getLogger(__name__)


async def index_google_drive_files(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    folder_id: str | None = None,
    folder_name: str | None = None,
    use_delta_sync: bool = True,
    update_last_indexed: bool = True,
    max_files: int = 500,
    include_subfolders: bool = False,
    on_heartbeat_callback: Any | None = None,
) -> tuple[int, int, str | None, int]:
    """Index Google Drive files for a specific connector.

    Returns (indexed, skipped, error_or_none, unsupported_count).
    """
    task_logger = TaskLoggingService(session, workspace_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_files_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "folder_id": folder_id,
            "use_delta_sync": use_delta_sync,
            "max_files": max_files,
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, error_msg, 0

        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google Drive client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        drive_client, client_error = _build_drive_client_for_connector(
            session, connector_id, connector, user_id
        )
        if client_error or not drive_client:
            await task_logger.log_task_failure(
                log_entry,
                client_error or "Failed to initialize Google Drive client",
                "Missing connector credentials",
                {"error_type": "ClientInitializationError"},
            )
            return 0, 0, client_error, 0

        connector_enable_vision_llm = getattr(connector, "enable_vision_llm", False)
        vision_llm = None
        if connector_enable_vision_llm:
            from app.services.llm_service import get_vision_llm

            vision_llm = await get_vision_llm(session, workspace_id)
        if not folder_id:
            error_msg = "folder_id is required for Google Drive indexing"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "MissingParameter"}
            )
            return 0, 0, error_msg, 0

        target_folder_id = folder_id
        target_folder_name = folder_name or "Selected Folder"

        folder_tokens = connector.config.get("folder_tokens", {})
        start_page_token = folder_tokens.get(target_folder_id)
        is_composio_connector = (
            connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES
        )
        can_use_delta = (
            not is_composio_connector
            and use_delta_sync
            and start_page_token
            and connector.last_indexed_at
        )

        documents_unsupported = 0

        if can_use_delta:
            logger.info(f"Using delta sync for connector {connector_id}")
            documents_indexed, documents_skipped, du = await _index_with_delta_sync_core(
                drive_client,
                session,
                connector,
                connector_id,
                workspace_id,
                user_id,
                target_folder_id,
                start_page_token,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                vision_llm=vision_llm,
            )
            documents_unsupported += du
            logger.info("Running reconciliation scan after delta sync")
            ri, rs, ru = await _index_full_scan_core(
                drive_client,
                session,
                connector,
                connector_id,
                workspace_id,
                user_id,
                target_folder_id,
                target_folder_name,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                vision_llm=vision_llm,
            )
            documents_indexed += ri
            documents_skipped += rs
            documents_unsupported += ru
        else:
            logger.info(f"Using full scan for connector {connector_id}")
            (
                documents_indexed,
                documents_skipped,
                documents_unsupported,
            ) = await _index_full_scan_core(
                drive_client,
                session,
                connector,
                connector_id,
                workspace_id,
                user_id,
                target_folder_id,
                target_folder_name,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                vision_llm=vision_llm,
            )

        if documents_indexed > 0 or can_use_delta:
            if hasattr(drive_client, "composio"):
                new_token, token_error = await drive_client.composio.get_drive_start_page_token(
                    drive_client.connected_account_id,
                    drive_client.entity_id,
                )
            else:
                new_token, token_error = await get_start_page_token(drive_client)
            if new_token and not token_error:
                await session.refresh(connector)
                if "folder_tokens" not in connector.config:
                    connector.config["folder_tokens"] = {}
                connector.config["folder_tokens"][target_folder_id] = new_token
                flag_modified(connector, "config")
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Drive indexing for connector {connector_id}",
            {
                "files_processed": documents_indexed,
                "files_skipped": documents_skipped,
                "files_unsupported": documents_unsupported,
                "sync_type": "delta" if can_use_delta else "full",
                "folder": target_folder_name,
            },
        )
        logger.info(
            f"Google Drive indexing completed: {documents_indexed} indexed, "
            f"{documents_skipped} skipped, {documents_unsupported} unsupported"
        )

        return documents_indexed, documents_skipped, None, documents_unsupported

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google Drive indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}", 0
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google Drive files for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Drive files: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Google Drive files: {e!s}", 0


async def index_google_drive_single_file(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    file_id: str,
    file_name: str | None = None,
) -> tuple[int, str | None]:
    """Index a single Google Drive file by its ID."""
    from app.connectors.google_drive import get_file_by_id

    task_logger = TaskLoggingService(session, workspace_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_single_file_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive single file indexing for file {file_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "file_id": file_id,
            "file_name": file_name,
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        drive_client, client_error = _build_drive_client_for_connector(
            session, connector_id, connector, user_id
        )
        if client_error or not drive_client:
            await task_logger.log_task_failure(
                log_entry,
                client_error or "Failed to initialize Google Drive client",
                "Missing connector credentials",
                {"error_type": "ClientInitializationError"},
            )
            return 0, client_error

        connector_enable_vision_llm = getattr(connector, "enable_vision_llm", False)
        vision_llm = None
        if connector_enable_vision_llm:
            from app.services.llm_service import get_vision_llm

            vision_llm = await get_vision_llm(session, workspace_id)
        file, error = await get_file_by_id(drive_client, file_id)
        if error or not file:
            error_msg = f"Failed to fetch file {file_id}: {error or 'File not found'}"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "FileNotFound"}
            )
            return 0, error_msg

        display_name = file_name or file.get("name", "Unknown")

        indexed, _skipped, failed = await _process_single_file_core(
            drive_client,
            session,
            file,
            connector_id,
            workspace_id,
            user_id,
            vision_llm=vision_llm,
        )
        await session.commit()

        if failed > 0:
            error_msg = f"Failed to index file {display_name}"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"file_name": display_name, "file_id": file_id}
            )
            return 0, error_msg

        if indexed > 0:
            await task_logger.log_task_success(
                log_entry,
                f"Successfully indexed file {display_name}",
                {"file_name": display_name, "file_id": file_id},
            )
            return 1, None

        return 0, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            "Database error during file indexing",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            "Failed to index Google Drive file",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Drive file: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Drive file: {e!s}"


async def index_google_drive_selected_files(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    files: list[tuple[str, str | None]],
    on_heartbeat_callback: Any | None = None,
) -> tuple[int, int, list[str]]:
    """Index multiple user-selected Google Drive files in parallel.

    Sets up the connector/credentials once, then delegates to
    _index_selected_files for the three-phase parallel pipeline.

    Returns (indexed_count, skipped_count, errors).
    """
    task_logger = TaskLoggingService(session, workspace_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_selected_files_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive batch file indexing for {len(files)} files",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "file_count": len(files),
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, [error_msg]

        drive_client, client_error = _build_drive_client_for_connector(
            session, connector_id, connector, user_id
        )
        if client_error or not drive_client:
            error_msg = client_error or "Failed to initialize Google Drive client"
            await task_logger.log_task_failure(
                log_entry,
                error_msg,
                "Missing connector credentials",
                {"error_type": "ClientInitializationError"},
            )
            return 0, 0, [error_msg]

        connector_enable_vision_llm = getattr(connector, "enable_vision_llm", False)
        vision_llm = None
        if connector_enable_vision_llm:
            from app.services.llm_service import get_vision_llm

            vision_llm = await get_vision_llm(session, workspace_id)
        indexed, skipped, unsupported, errors = await _index_selected_files_core(
            drive_client,
            session,
            files,
            connector_id=connector_id,
            workspace_id=workspace_id,
            user_id=user_id,
            on_heartbeat=on_heartbeat_callback,
            vision_llm=vision_llm,
        )

        if unsupported > 0:
            file_text = "file was" if unsupported == 1 else "files were"
            unsup_msg = f"{unsupported} {file_text} not supported"
            errors.append(unsup_msg)

        await session.commit()

        if errors:
            await task_logger.log_task_failure(
                log_entry,
                f"Batch file indexing completed with {len(errors)} error(s)",
                "; ".join(errors),
                {
                    "indexed": indexed,
                    "skipped": skipped,
                    "unsupported": unsupported,
                    "error_count": len(errors),
                },
            )
        else:
            await task_logger.log_task_success(
                log_entry,
                f"Successfully indexed {indexed} files ({skipped} skipped)",
                {"indexed": indexed, "skipped": skipped},
            )

        logger.info(
            f"Selected files indexing: {indexed} indexed, {skipped} skipped, {len(errors)} errors"
        )
        return indexed, skipped, errors

    except SQLAlchemyError as db_error:
        await session.rollback()
        error_msg = f"Database error: {db_error!s}"
        await task_logger.log_task_failure(
            log_entry, error_msg, str(db_error), {"error_type": "SQLAlchemyError"}
        )
        logger.error(error_msg, exc_info=True)
        return 0, 0, [error_msg]
    except Exception as e:
        await session.rollback()
        error_msg = f"Failed to index Google Drive files: {e!s}"
        await task_logger.log_task_failure(
            log_entry, error_msg, str(e), {"error_type": type(e).__name__}
        )
        logger.error(error_msg, exc_info=True)
        return 0, 0, [error_msg]
