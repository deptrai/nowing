"""Backward-compatible shim for the refactored Google Drive indexer package.

This module re-exports the public and internal API previously defined in the
monolithic ``app.tasks.connector_indexers.google_drive_indexer`` module so that
existing imports, Celery task bindings, and test monkeypatches continue to work.
New code should import directly from ``app.tasks.connector_indexers.google_drive``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_drive import (
    categorize_change,
    download_and_extract_content,
    fetch_all_changes,
    get_file_by_id,
    get_files_in_folder,
)
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
)
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    mark_connector_documents_failed,
)
from app.tasks.connector_indexers.google_drive.client import (
    ComposioDriveClient,
    _build_drive_client_for_connector as _core_build_drive_client_for_connector,
)
from app.tasks.connector_indexers.google_drive.constants import (
    ACCEPTED_DRIVE_CONNECTOR_TYPES,
    HEARTBEAT_INTERVAL_SECONDS,
    HeartbeatCallbackType,
)
from app.tasks.connector_indexers.google_drive.document import (
    _build_connector_doc as _core_build_connector_doc,
    _create_drive_placeholders as _core_create_drive_placeholders,
)
from app.tasks.connector_indexers.google_drive.download import (
    _download_and_index_core,
    _download_files_parallel_core,
)
from app.tasks.connector_indexers.google_drive.entrypoints import (
    index_google_drive_files as _core_index_google_drive_files,
    index_google_drive_selected_files as _core_index_google_drive_selected_files,
    index_google_drive_single_file as _core_index_google_drive_single_file,
)
from app.tasks.connector_indexers.google_drive.file_filter import (
    _remove_document as _core_remove_document,
    _should_skip_file as _core_should_skip_file,
)
from app.tasks.connector_indexers.google_drive.indexing import (
    _index_selected_files_core,
    _process_single_file_core,
)
from app.tasks.connector_indexers.google_drive.scan import (
    _index_full_scan_core,
    _index_with_delta_sync_core,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ACCEPTED_DRIVE_CONNECTOR_TYPES",
    "HEARTBEAT_INTERVAL_SECONDS",
    "ComposioDriveClient",
    "HeartbeatCallbackType",
    "_build_connector_doc",
    "_build_drive_client_for_connector",
    "_create_drive_placeholders",
    "_download_and_index",
    "_download_files_parallel",
    "_index_full_scan",
    "_index_selected_files",
    "_index_with_delta_sync",
    "_process_single_file",
    "_remove_document",
    "_should_skip_file",
    "index_google_drive_files",
    "index_google_drive_selected_files",
    "index_google_drive_single_file",
]


# ---------------------------------------------------------------------------
# Bound public helpers kept at the legacy module for monkeypatch compatibility
# ---------------------------------------------------------------------------


_build_drive_client_for_connector = _core_build_drive_client_for_connector
_build_connector_doc = _core_build_connector_doc
_create_drive_placeholders = _core_create_drive_placeholders
_should_skip_file = _core_should_skip_file
_remove_document = _core_remove_document


async def _download_files_parallel(
    drive_client: Any,
    files: list[dict],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    max_concurrency: int = 3,
    on_heartbeat: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
) -> tuple[list[ConnectorDocument], list[tuple[str, str]]]:
    return await _download_files_parallel_core(
        drive_client,
        files,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        extract_fn=download_and_extract_content,
        build_connector_doc_fn=_build_connector_doc,
        max_concurrency=max_concurrency,
        on_heartbeat=on_heartbeat,
        vision_llm=vision_llm,
        heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
    )


async def _download_and_index(
    drive_client: Any,
    session: AsyncSession,
    files: list[dict],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    on_heartbeat: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int]:
    return await _download_and_index_core(
        drive_client,
        session,
        files,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        download_files_parallel_fn=_download_files_parallel,
        on_heartbeat=on_heartbeat,
        extract_fn=download_and_extract_content,
        vision_llm=vision_llm,
        pipeline_cls=IndexingPipelineService,
    )


async def _process_single_file(
    drive_client: Any,
    session: AsyncSession,
    file: dict,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    return await _process_single_file_core(
        drive_client,
        session,
        file,
        connector_id,
        workspace_id,
        user_id,
        skip_fn=_should_skip_file,
        extract_fn=download_and_extract_content,
        pipeline_cls=IndexingPipelineService,
        mark_failed_fn=mark_connector_documents_failed,
        vision_llm=vision_llm,
    )


async def _index_selected_files(
    drive_client: Any,
    session: AsyncSession,
    file_ids: list[tuple[str, str | None]],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    on_heartbeat: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int, list[str]]:
    return await _index_selected_files_core(
        drive_client,
        session,
        file_ids,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        get_file_fn=get_file_by_id,
        skip_fn=_should_skip_file,
        download_and_index_fn=_download_and_index,
        create_placeholders_fn=_create_drive_placeholders,
        on_heartbeat=on_heartbeat,
        extract_fn=download_and_extract_content,
        vision_llm=vision_llm,
    )


async def _index_full_scan(
    drive_client: Any,
    session: AsyncSession,
    connector: object,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    folder_id: str | None,
    folder_name: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    return await _index_full_scan_core(
        drive_client,
        session,
        connector,
        connector_id,
        workspace_id,
        user_id,
        folder_id,
        folder_name,
        task_logger,
        log_entry,
        max_files,
        skip_fn=_should_skip_file,
        get_files_fn=get_files_in_folder,
        create_placeholders_fn=_create_drive_placeholders,
        download_and_index_fn=_download_and_index,
        include_subfolders=include_subfolders,
        on_heartbeat_callback=on_heartbeat_callback,
        vision_llm=vision_llm,
    )


async def _index_with_delta_sync(
    drive_client: Any,
    session: AsyncSession,
    connector: object,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    folder_id: str | None,
    start_page_token: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    return await _index_with_delta_sync_core(
        drive_client,
        session,
        connector,
        connector_id,
        workspace_id,
        user_id,
        folder_id,
        start_page_token,
        task_logger,
        log_entry,
        max_files,
        skip_fn=_should_skip_file,
        fetch_changes_fn=fetch_all_changes,
        categorize_fn=categorize_change,
        remove_document_fn=_remove_document,
        create_placeholders_fn=_create_drive_placeholders,
        download_and_index_fn=_download_and_index,
        include_subfolders=include_subfolders,
        on_heartbeat_callback=on_heartbeat_callback,
        vision_llm=vision_llm,
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


index_google_drive_files = _core_index_google_drive_files
index_google_drive_single_file = _core_index_google_drive_single_file
index_google_drive_selected_files = _core_index_google_drive_selected_files
