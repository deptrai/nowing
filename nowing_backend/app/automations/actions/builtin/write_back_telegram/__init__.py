"""``write_back_telegram`` action: send a Telegram message."""

from __future__ import annotations

from .factory import build_handler
from .params import TelegramActionParams

__all__ = ["TelegramActionParams", "build_handler"]

# Side-effect: register on the actions store.
from . import definition  # noqa: F401
