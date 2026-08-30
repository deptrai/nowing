"""Google Drive connector indexer package."""

from __future__ import annotations

from app.tasks.connector_indexers.google_drive.client import (
    ComposioDriveClient,
    _build_drive_client_for_connector,
)
from app.tasks.connector_indexers.google_drive.constants import (
    ACCEPTED_DRIVE_CONNECTOR_TYPES,
    HEARTBEAT_INTERVAL_SECONDS,
    HeartbeatCallbackType,
)
from app.tasks.connector_indexers.google_drive.document import (
    _build_connector_doc,
    _create_drive_placeholders,
)
from app.tasks.connector_indexers.google_drive.download import (
    _download_and_index_core,
    _download_files_parallel_core,
)
from app.tasks.connector_indexers.google_drive.entrypoints import (
    index_google_drive_files,
    index_google_drive_selected_files,
    index_google_drive_single_file,
)
from app.tasks.connector_indexers.google_drive.file_filter import (
    _remove_document,
    _should_skip_file,
)
from app.tasks.connector_indexers.google_drive.indexing import (
    _index_selected_files_core,
    _process_single_file_core,
)
from app.tasks.connector_indexers.google_drive.scan import (
    _index_full_scan_core,
    _index_with_delta_sync_core,
)

__all__ = [
    "ACCEPTED_DRIVE_CONNECTOR_TYPES",
    "HEARTBEAT_INTERVAL_SECONDS",
    "ComposioDriveClient",
    "HeartbeatCallbackType",
    "_build_connector_doc",
    "_build_drive_client_for_connector",
    "_create_drive_placeholders",
    "_download_and_index_core",
    "_download_files_parallel_core",
    "_index_full_scan_core",
    "_index_selected_files_core",
    "_index_with_delta_sync_core",
    "_process_single_file_core",
    "_remove_document",
    "_should_skip_file",
    "index_google_drive_files",
    "index_google_drive_selected_files",
    "index_google_drive_single_file",
]
