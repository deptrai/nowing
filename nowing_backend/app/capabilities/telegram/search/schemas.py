"""Input/output Pydantic schemas for telegram.search capability (Story 22.1 / AD-1, AD-6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.proprietary.platforms.telegram.schemas import (
    TelegramChannelInfo,
    TelegramMessageParsed,
)


class TelegramSearchInput(BaseModel):
    """Input payload for searching Telegram messages in a public channel."""

    channel_username: str = Field(
        ...,
        description="Target public Telegram channel username without @ (e.g. batdongsanhanoi)",
    )
    keyword: str | None = Field(
        default=None,
        description="Optional text keyword or phrase to filter messages (case-insensitive)",
    )
    intent: str | None = Field(
        default=None,
        description="Optional intent filter: 'sell', 'buy', 'seeking', or 'news'",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of matched messages to return",
    )

    @property
    def estimated_units(self) -> int:
        return self.limit


class TelegramSearchOutput(BaseModel):
    """Output payload returning matched Telegram messages and channel metadata."""

    channel_info: TelegramChannelInfo | None = Field(
        default=None,
        description="Channel metadata (title, description, subscribers)",
    )
    messages: list[TelegramMessageParsed] = Field(
        default_factory=list,
        description="List of matched messages with extracted entities",
    )
    total_found: int = Field(
        default=0,
        description="Total number of messages matching the criteria",
    )

    @property
    def billable_units(self) -> int:
        return len(self.messages) or 1
