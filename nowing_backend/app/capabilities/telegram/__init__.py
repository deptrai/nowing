"""Telegram capabilities package."""

from __future__ import annotations

from app.capabilities.telegram import search as _search  # noqa: F401
from app.capabilities.telegram.search.definition import TELEGRAM_SEARCH

__all__ = [
    "TELEGRAM_SEARCH",
]
