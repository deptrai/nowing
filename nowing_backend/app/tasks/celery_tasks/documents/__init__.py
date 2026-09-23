"""Document Celery tasks package."""

from .circleback import process_circleback_meeting_task
from .delete import (
    delete_document_task,
    delete_folder_documents_task,
    delete_workspace_task,
)
from .index_local import (
    index_local_folder_task,
    index_uploaded_folder_files_task,
)
from .process_extension import process_extension_document_task
from .process_upload import (
    process_file_upload_task,
    process_file_upload_with_document_task,
)

__all__ = [
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
