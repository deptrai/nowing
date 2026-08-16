"""Executor for telegram.search capability (Story 22.1 / AD-1, AD-6)."""

from __future__ import annotations

import logging
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.capabilities.telegram.search.schemas import (
    TelegramSearchInput,
    TelegramSearchOutput,
)
from app.proprietary.platforms.telegram.preview_scraper import (
    TelegramWebPreviewScraper,
)
from app.proprietary.platforms.telegram.schemas import TelegramScrapeResult

logger = logging.getLogger(__name__)


async def scrape_telegram_channel(channel_username: str) -> TelegramScrapeResult:
    """Fetch public channel messages using the web preview engine."""
    scraper = TelegramWebPreviewScraper()
    return await scraper.scrape_channel(channel_username)


def _filter_and_paginate(
    result: TelegramScrapeResult,
    payload: TelegramSearchInput,
) -> TelegramSearchOutput:
    """Filter scraped messages by intent and keyword, then paginate."""
    filtered_messages = result.messages

    if payload.intent:
        target_intent = payload.intent.strip().lower()
        filtered_messages = [
            m for m in filtered_messages if m.intent_tag.lower() == target_intent
        ]

    if payload.keyword:
        kw = payload.keyword.strip().lower()
        filtered_messages = [m for m in filtered_messages if kw in m.text.lower()]

    total_found = len(filtered_messages)
    matched_messages = filtered_messages[: payload.limit]

    return TelegramSearchOutput(
        channel_info=result.channel_info,
        messages=matched_messages,
        total_found=total_found,
    )


async def search_telegram_messages(
    payload: TelegramSearchInput,
    ctx: CapabilityContext | None = None,
) -> TelegramSearchOutput:
    """Execute telegram search using scrape_telegram_channel."""
    result: TelegramScrapeResult = await scrape_telegram_channel(
        payload.channel_username
    )
    return _filter_and_paginate(result, payload)


def build_telegram_search_executor(scraper_fn: Any = None):
    """Factory creating an executor for searching Telegram messages."""
    if scraper_fn is None:
        return search_telegram_messages

    async def _execute(
        payload: TelegramSearchInput,
        ctx: CapabilityContext | None = None,
    ) -> TelegramSearchOutput:
        result: TelegramScrapeResult = await scraper_fn(payload.channel_username)
        return _filter_and_paginate(result, payload)

    return _execute
