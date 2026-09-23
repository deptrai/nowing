"""Compatibility re-export for app.tasks.celery_tasks.document_tasks."""

from .documents import (
    delete_document_task,
    delete_folder_documents_task,
    delete_workspace_task,
    index_local_folder_task,
    index_uploaded_folder_files_task,
    process_circleback_meeting_task,
    process_extension_document_task,
    process_file_upload_task,
    process_file_upload_with_document_task,
)
from .documents.heartbeat import (
    _run_heartbeat_loop,
    _start_heartbeat,
    _stop_heartbeat,
)
from .documents.process_upload import _process_file_with_document  # noqa: F401

__all__ = [
    "_run_heartbeat_loop",
    "_start_heartbeat",
    "_stop_heartbeat",
    "delete_document_task",
    "delete_folder_documents_task",
    "delete_workspace_task",
    "index_local_folder_task",
    "index_uploaded_folder_files_task",
    "process_circleback_meeting_task",
    "process_extension_document_task",
    "process_file_upload_task",
    "process_file_upload_with_document_task",
]
