"""telegram.search capability module."""

from __future__ import annotations

from app.capabilities.telegram.search.definition import TELEGRAM_SEARCH
from app.capabilities.telegram.search.schemas import (
    TelegramSearchInput,
    TelegramSearchOutput,
)

__all__ = [
    "TELEGRAM_SEARCH",
    "TelegramSearchInput",
    "TelegramSearchOutput",
]
