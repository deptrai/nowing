"""``TelegramActionParams`` — params for the ``write_back_telegram`` action."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TelegramActionParams(BaseModel):
    """Send a Telegram message from an automation step."""

    model_config = ConfigDict(extra="forbid")

    chat_id: str | None = Field(
        default=None,
        min_length=1,
        description="Telegram chat id or @channelusername. Falls back to the creator's binding.",
    )
    text: str = Field(..., min_length=1)
    parse_mode: str | None = Field(default="Markdown")
    reply_to_message_id: str | None = Field(default=None)
    reply_markup: dict | None = Field(default=None)
    account_id: int | None = Field(
        default=None, description="Explicit ExternalChatAccount id."
    )
    use_system_bot: bool = Field(
        default=True,
        description="Use the workspace/system shared Telegram bot instead of a BYO account.",
    )
    connector_name: str | None = Field(
        default=None,
        description="Ignored: present so the builder form pattern (connector_name/object_id) round-trips.",
    )
    object_id: str | None = Field(
        default=None,
        description="Ignored: present so the builder form pattern (connector_name/object_id) round-trips.",
    )
