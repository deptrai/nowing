"""Shared Composio constants and registry mappings."""

from __future__ import annotations

# Mapping of toolkit IDs to their display names
COMPOSIO_TOOLKIT_NAMES = {
    "googledrive": "Google Drive",
    "gmail": "Gmail",
    "googlecalendar": "Google Calendar",
    "slack": "Slack",
    "notion": "Notion",
    "github": "GitHub",
}

# Toolkits that support indexing (Phase 1: Google services only)
INDEXABLE_TOOLKITS = {"googledrive"}

# Mapping of toolkit IDs to connector types
TOOLKIT_TO_CONNECTOR_TYPE = {
    "googledrive": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "gmail": "COMPOSIO_GMAIL_CONNECTOR",
    "googlecalendar": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}

# Mapping of toolkit IDs to document types
# Google Drive, Gmail, Calendar use unified native indexers - not in this registry
TOOLKIT_TO_DOCUMENT_TYPE: dict[str, str] = {}

# Mapping of toolkit IDs to their indexer functions
# Format: toolkit_id -> (module_path, function_name, supports_date_filter)
# supports_date_filter: True if the indexer accepts start_date/end_date params
# Google Drive, Gmail, Calendar use unified native indexers - not in this registry
TOOLKIT_TO_INDEXER: dict[str, tuple[str, str, bool]] = {}
