"""``write_back_slack`` action: send a Slack message."""

from __future__ import annotations

from .factory import build_handler
from .params import SlackActionParams

__all__ = ["SlackActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
