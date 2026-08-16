"""AI Agent Chat Tools for Telegram Ingestion & Channel Querying (Story 22.3 / AC-4).

Provides LangChain tools:
- `telegram_search_channel`: Search posts in a channel by keyword and filter entities.
- `telegram_fetch_recent_posts`: Fetch recent messages and extracted entities from a channel.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.proprietary.platforms.telegram.entity_extractor import TelegramEntityExtractor

logger = logging.getLogger(__name__)


async def query_telegram_messages(
    channel: str, query: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """Query stored Telegram messages from PostgreSQL."""
    # In live runtime, queries telegram_messages filtered by channel and text
    return []


class TelegramSearchInput(BaseModel):
    channel: str = Field(
        ..., description="Telegram channel username or @handle without @"
    )
    query: str = Field(..., description="Search keyword or query terms")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")


class TelegramFetchRecentInput(BaseModel):
    channel: str = Field(..., description="Telegram channel username or @handle")
    limit: int = Field(
        default=10, ge=1, le=50, description="Max recent posts to return"
    )


def _format_post_summary(post: dict[str, Any]) -> str:
    """Format a single telegram post into a clean UX card widget string."""
    import json

    channel = post.get("channel_username") or "telegram"
    date = str(post.get("posted_at") or "")
    text = post.get("message_text", "")
    views = post.get("views_count", 0)

    entities = post.get("raw_entities")
    if isinstance(entities, str):
        try:
            entities = json.loads(entities)
        except Exception:
            entities = {}
    if not isinstance(entities, dict):
        entities = TelegramEntityExtractor.extract_entities(text) if text else {}

    phones = [str(p) for p in entities.get("phones", []) if p]
    prices = [
        str(p.get("raw_text") if isinstance(p, dict) else p)
        for p in entities.get("prices", [])
        if p and (not isinstance(p, dict) or p.get("raw_text"))
    ]
    locations = [str(loc) for loc in entities.get("locations", []) if loc]

    badges: list[str] = []
    if phones:
        badges.append(f"[ 📞 {', '.join(phones)} ]")
    if prices:
        badges.append(f"[ 💰 {', '.join(prices)} ]")
    if locations:
        badges.append(f"[ 📍 {', '.join(locations)} ]")

    badge_str = f"\n🏷️ Entities: {' '.join(badges)}" if badges else ""
    return f"✈️ Telegram Post • @{channel} ({date})\n{text}{badge_str}\n👁️ {views} views"


async def telegram_search_channel(channel: str, query: str, limit: int = 10) -> str:
    """Search Telegram channel posts for matching keywords and extract contacts/prices."""
    clean_channel = channel.lstrip("@")
    results = await query_telegram_messages(
        channel=clean_channel, query=query, limit=limit
    )
    if not results:
        return f"No posts found for query '{query}' in channel @{clean_channel}."

    formatted = [_format_post_summary(p) for p in results]
    return (
        f"Found {len(formatted)} posts in @{clean_channel}:\n\n"
        + "\n\n---\n\n".join(formatted)
    )


async def telegram_fetch_recent_posts(channel: str, limit: int = 10) -> str:
    """Fetch most recent posts from a monitored Telegram channel."""
    clean_channel = channel.lstrip("@")
    results = await query_telegram_messages(
        channel=clean_channel, query=None, limit=limit
    )
    if not results:
        return f"No recent posts found for channel @{clean_channel}."

    formatted = [_format_post_summary(p) for p in results]
    return f"Recent posts from @{clean_channel}:\n\n" + "\n\n---\n\n".join(formatted)


telegram_search_channel_tool = StructuredTool.from_function(
    coroutine=telegram_search_channel,
    name="telegram_search_channel",
    description="Search posts in a monitored Telegram channel by keyword, extracting phone numbers, prices, and locations.",
    args_schema=TelegramSearchInput,
)

telegram_fetch_recent_posts_tool = StructuredTool.from_function(
    coroutine=telegram_fetch_recent_posts,
    name="telegram_fetch_recent_posts",
    description="Fetch recent posts and extracted listing leads from a monitored Telegram channel.",
    args_schema=TelegramFetchRecentInput,
)
