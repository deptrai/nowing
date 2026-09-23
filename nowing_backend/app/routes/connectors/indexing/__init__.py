"""Connector indexing package.

This package exposes the public indexing API used by Celery tasks and tests.
The FastAPI endpoint and shared helper live in ``core.py``; each connector
has its own runner module.
"""

from __future__ import annotations

from app.utils.rbac import check_permission

from .._shared import _update_connector_timestamp_by_id
from .bookstack import (
    run_bookstack_indexing,
    run_bookstack_indexing_with_new_session,
)
from .composio import (
    run_composio_indexing,
    run_composio_indexing_with_new_session,
)
from .confluence import (
    run_confluence_indexing,
    run_confluence_indexing_with_new_session,
)
from .core import (
    _run_indexing_with_notifications,
    index_connector_content,
    router,
)
from .dropbox import (
    run_dropbox_indexing,
    run_dropbox_indexing_with_new_session,
)
from .elasticsearch import (
    run_elasticsearch_indexing,
    run_elasticsearch_indexing_with_new_session,
)
from .github import (
    run_github_indexing,
    run_github_indexing_with_new_session,
)
from .google_calendar import (
    run_google_calendar_indexing,
    run_google_calendar_indexing_with_new_session,
)
from .google_drive import (
    run_google_drive_indexing,
    run_google_drive_indexing_with_new_session,
)
from .google_gmail import (
    run_google_gmail_indexing,
    run_google_gmail_indexing_with_new_session,
)
from .notion import (
    run_notion_indexing,
    run_notion_indexing_with_new_session,
)
from .onedrive import (
    run_onedrive_indexing,
    run_onedrive_indexing_with_new_session,
)

__all__ = [
    "_run_indexing_with_notifications",
    "_update_connector_timestamp_by_id",
    "check_permission",
    "index_connector_content",
    "router",
    "run_bookstack_indexing",
    "run_bookstack_indexing_with_new_session",
    "run_composio_indexing",
    "run_composio_indexing_with_new_session",
    "run_confluence_indexing",
    "run_confluence_indexing_with_new_session",
    "run_dropbox_indexing",
    "run_dropbox_indexing_with_new_session",
    "run_elasticsearch_indexing",
    "run_elasticsearch_indexing_with_new_session",
    "run_github_indexing",
    "run_github_indexing_with_new_session",
    "run_google_calendar_indexing",
    "run_google_calendar_indexing_with_new_session",
    "run_google_drive_indexing",
    "run_google_drive_indexing_with_new_session",
    "run_google_gmail_indexing",
    "run_google_gmail_indexing_with_new_session",
    "run_notion_indexing",
    "run_notion_indexing_with_new_session",
    "run_onedrive_indexing",
    "run_onedrive_indexing_with_new_session",
]
