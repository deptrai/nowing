"""The notification types the API recognizes."""

from __future__ import annotations

from typing import Literal

NotificationType = Literal[
    "connector_indexing",
    "connector_deletion",
    "document_processing",
    "new_mention",
    "comment_reply",
    "insufficient_credits",
    "auto_reload_failed",
    "deep_research_complete",
    "automation_run_complete",
    "alert_run_complete",
    "signal_detected",
]

NotificationCategory = Literal["comments", "status"]
