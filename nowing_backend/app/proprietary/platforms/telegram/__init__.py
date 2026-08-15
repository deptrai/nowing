"""Telegram Platform integration module (Story 22.1 / AD-1, AD-2, AD-4)."""

from __future__ import annotations

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor
from app.proprietary.platforms.telegram.models import (
    TelegramChannel,
    TelegramMedia,
    TelegramMessage,
)
from app.proprietary.platforms.telegram.preview_scraper import (
    TelegramWebPreviewScraper,
    parse_channel_info,
    parse_messages,
)
from app.proprietary.platforms.telegram.schemas import (
    ExtractedEntities,
    TelegramChannelInfo,
    TelegramMessageParsed,
    TelegramScrapeResult,
)

__all__ = [
    "ExtractedEntities",
    "TelegramChannel",
    "TelegramChannelInfo",
    "TelegramEntityExtractor",
    "TelegramMedia",
    "TelegramMessage",
    "TelegramMessageParsed",
    "TelegramScrapeResult",
    "TelegramWebPreviewScraper",
    "parse_channel_info",
    "parse_messages",
]
