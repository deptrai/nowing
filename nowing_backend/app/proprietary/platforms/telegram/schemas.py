"""Pydantic schemas for Telegram Scraper subsystem (Story 22.1 / AD-2, AD-4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """Structured entities extracted from Telegram message content."""

    phone_numbers: list[str] = Field(
        default_factory=list, description="Extracted Vietnamese phone numbers"
    )
    emails: list[str] = Field(
        default_factory=list, description="Extracted email addresses"
    )
    prices: list[str] = Field(
        default_factory=list, description="Extracted prices and currency values"
    )
    hashtags: list[str] = Field(default_factory=list, description="Extracted hashtags")
    intent_tag: str = Field(
        default="news",
        description="Intent classification: 'sell', 'buy', 'seeking', 'news'",
    )
    raw_entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of typed entities for JSONB storage: [{'type': '...', 'value': '...', 'confidence': 0.9}]",
    )


class TelegramChannelInfo(BaseModel):
    """Metadata of a public Telegram channel or supergroup."""

    id: int | None = Field(default=None, description="Telegram peer ID (if known)")
    username: str = Field(..., description="Canonical channel username without @")
    title: str = Field(..., description="Channel display title")
    description: str = Field(default="", description="Channel about/bio description")
    avatar_url: str | None = Field(default=None, description="Channel avatar photo URL")
    subscribers_count: int = Field(default=0, description="Subscriber or member count")
    is_megagroup: bool = Field(
        default=False, description="Whether channel is a megagroup/forum"
    )
    is_public: bool = Field(default=True, description="Whether channel is public")


class TelegramMessageParsed(BaseModel):
    """A message parsed from Telegram public preview or MTProto ingress."""

    message_id: int = Field(..., description="External Telegram message ID")
    channel_username: str = Field(..., description="Channel username")
    text: str = Field(default="", description="Clean text content")
    published_at: datetime = Field(..., description="Publish timestamp in UTC")
    views: int = Field(default=0, description="View count")
    forwards: int = Field(default=0, description="Forward count")
    replies_count: int = Field(default=0, description="Discussion reply count")
    has_media: bool = Field(
        default=False, description="Whether message contains photo/video/doc"
    )
    media_urls: list[str] = Field(
        default_factory=list, description="Preview media URLs"
    )
    author_name: str | None = Field(default=None, description="Author display name")
    intent_tag: str = Field(default="news", description="Classified intent tag")
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities, description="Extracted entities"
    )


class TelegramScrapeResult(BaseModel):
    """Result returned by TelegramWebPreviewScraper."""

    channel_info: TelegramChannelInfo
    messages: list[TelegramMessageParsed] = Field(default_factory=list)
