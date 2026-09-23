"""Local folder connector indexer package."""

from __future__ import annotations

from app.tasks.connector_indexers.local_folder.constants import (
    BATCH_CONCURRENCY,
    DEFAULT_EXCLUDE_PATTERNS,
    UPLOAD_BATCH_CONCURRENCY,
    HeartbeatCallbackType,
)
from app.tasks.connector_indexers.local_folder.credits import (
    _check_credits_or_skip,
    _compute_final_pages,
    _estimate_pages_safe,
)
from app.tasks.connector_indexers.local_folder.document import _build_connector_doc
from app.tasks.connector_indexers.local_folder.filesystem import (
    _compute_file_content_hash,
    _compute_raw_file_hash,
    _content_hash,
    _read_file_content,
    scan_folder,
)
from app.tasks.connector_indexers.local_folder.folders import (
    _cleanup_empty_folder_chain,
    _cleanup_empty_folders,
    _clear_indexing_flag,
    _mirror_folder_structure,
    _mirror_folder_structure_from_paths,
    _resolve_folder_for_file,
    _set_indexing_flag,
)
from app.tasks.connector_indexers.local_folder.indexing import (
    _index_batch_files,
    _index_single_file,
    index_local_folder,
    index_uploaded_files,
)

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
    "index_local_folder",
    "index_uploaded_files",
    "scan_folder",
]
