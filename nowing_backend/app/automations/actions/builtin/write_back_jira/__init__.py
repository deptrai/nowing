"""``write_back_jira`` action: create or update a Jira issue."""

from __future__ import annotations

from .factory import build_handler
from .params import JiraActionParams

__all__ = ["JiraActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
