"""Telegram alert listener module alias."""

from __future__ import annotations

from app.proprietary.platforms.telegram.stream_daemon import (
    TelegramStreamDaemon,
    process_telegram_stream_event,
)

__all__ = ["TelegramStreamDaemon", "process_telegram_stream_event"]
