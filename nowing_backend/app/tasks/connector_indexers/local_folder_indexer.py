"""Backward-compatible shim for the refactored local folder indexer package.

This module re-exports the public and internal API previously defined in the
monolithic ``app.tasks.connector_indexers.local_folder_indexer`` module so that
existing imports, Celery task bindings, and test monkeypatches continue to work.
New code should import directly from ``app.tasks.connector_indexers.local_folder``.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_tasks import get_celery_session_maker
from app.tasks.connector_indexers.local_folder.constants import (
    BATCH_CONCURRENCY,
    DEFAULT_EXCLUDE_PATTERNS,
    UPLOAD_BATCH_CONCURRENCY,
    HeartbeatCallbackType,
)
from app.tasks.connector_indexers.local_folder.credits import (
    _check_credits_or_skip as _core_check_credits_or_skip,
    _compute_final_pages as _core_compute_final_pages,
    _estimate_pages_safe as _core_estimate_pages_safe,
)
from app.tasks.connector_indexers.local_folder.document import (
    _build_connector_doc as _core_build_connector_doc,
)
from app.tasks.connector_indexers.local_folder.filesystem import (
    _compute_file_content_hash as _core_compute_file_content_hash,
    _compute_raw_file_hash as _core_compute_raw_file_hash,
    _content_hash as _core_content_hash,
    _read_file_content as _core_read_file_content,
    scan_folder as _core_scan_folder,
)
from app.tasks.connector_indexers.local_folder.folders import (
    _cleanup_empty_folder_chain as _core_cleanup_empty_folder_chain,
    _cleanup_empty_folders as _core_cleanup_empty_folders,
    _clear_indexing_flag as _core_clear_indexing_flag,
    _mirror_folder_structure as _core_mirror_folder_structure,
    _mirror_folder_structure_from_paths as _core_mirror_folder_structure_from_paths,
    _resolve_folder_for_file as _core_resolve_folder_for_file,
    _set_indexing_flag as _core_set_indexing_flag,
)
from app.tasks.connector_indexers.local_folder.indexing import (
    _index_batch_files as _core_index_batch_files,
    _index_single_file as _core_index_single_file,
    index_local_folder as _core_index_local_folder,
    index_uploaded_files as _core_index_uploaded_files,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BATCH_CONCURRENCY",
    "DEFAULT_EXCLUDE_PATTERNS",
    "UPLOAD_BATCH_CONCURRENCY",
    "HeartbeatCallbackType",
    "_build_connector_doc",
    "_check_credits_or_skip",
    "_cleanup_empty_folder_chain",
    "_cleanup_empty_folders",
    "_clear_indexing_flag",
    "_compute_file_content_hash",
    "_compute_final_pages",
    "_compute_raw_file_hash",
    "_content_hash",
    "_estimate_pages_safe",
    "_index_batch_files",
    "_index_single_file",
    "_mirror_folder_structure",
    "_mirror_folder_structure_from_paths",
    "_read_file_content",
    "_resolve_folder_for_file",
    "_set_indexing_flag",
    "get_celery_session_maker",
    "index_local_folder",
    "index_uploaded_files",
    "scan_folder",
]

_estimate_pages_safe = _core_estimate_pages_safe
_check_credits_or_skip = _core_check_credits_or_skip
_compute_final_pages = _core_compute_final_pages
scan_folder = _core_scan_folder
_read_file_content = _core_read_file_content
_content_hash = _core_content_hash
_compute_raw_file_hash = _core_compute_raw_file_hash
_compute_file_content_hash = _core_compute_file_content_hash
_mirror_folder_structure = _core_mirror_folder_structure
_resolve_folder_for_file = _core_resolve_folder_for_file
_set_indexing_flag = _core_set_indexing_flag
_clear_indexing_flag = _core_clear_indexing_flag
_cleanup_empty_folder_chain = _core_cleanup_empty_folder_chain
_cleanup_empty_folders = _core_cleanup_empty_folders
_build_connector_doc = _core_build_connector_doc
_mirror_folder_structure_from_paths = _core_mirror_folder_structure_from_paths
_index_single_file = _core_index_single_file


async def _index_batch_files(
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    target_file_paths: list[str],
    root_folder_id: int | None,
    on_progress_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    return await _core_index_batch_files(
        workspace_id=workspace_id,
        user_id=user_id,
        folder_path=folder_path,
        folder_name=folder_name,
        target_file_paths=target_file_paths,
        root_folder_id=root_folder_id,
        on_progress_callback=on_progress_callback,
        get_session_maker=get_celery_session_maker,
        batch_concurrency=BATCH_CONCURRENCY,
    )


async def index_local_folder(
    session: AsyncSession,
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    exclude_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
    root_folder_id: int | None = None,
    target_file_paths: list[str] | None = None,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, int | None, str | None]:
    return await _core_index_local_folder(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
        folder_path=folder_path,
        folder_name=folder_name,
        exclude_patterns=exclude_patterns,
        file_extensions=file_extensions,
        root_folder_id=root_folder_id,
        target_file_paths=target_file_paths,
        on_heartbeat_callback=on_heartbeat_callback,
        get_session_maker=get_celery_session_maker,
        batch_concurrency=BATCH_CONCURRENCY,
    )


async def index_uploaded_files(
    session: AsyncSession,
    workspace_id: int,
    user_id: str,
    folder_name: str,
    root_folder_id: int,
    file_mappings: list[dict],
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
) -> tuple[int, int, str | None]:
    return await _core_index_uploaded_files(
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
        folder_name=folder_name,
        root_folder_id=root_folder_id,
        file_mappings=file_mappings,
        on_heartbeat_callback=on_heartbeat_callback,
        use_vision_llm=use_vision_llm,
        processing_mode=processing_mode,
        upload_batch_concurrency=UPLOAD_BATCH_CONCURRENCY,
    )
