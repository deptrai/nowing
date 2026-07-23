"""``write_back_notion`` action: create or update a Notion page."""

from __future__ import annotations

from .factory import build_handler
from .params import NotionActionParams

__all__ = ["NotionActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
