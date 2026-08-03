"""Telegram platform adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.gateway.base.adapter import (
    BasePlatformAdapter,
    ParsedInboundEvent,
    PlatformSendResult,
)
from app.gateway.telegram.client import TelegramClient


class TelegramAdapter(BasePlatformAdapter):
    platform = "telegram"

    def __init__(self, token: str) -> None:
        self.client = TelegramClient(token)

    def parse_inbound(self, raw_payload: dict[str, Any]) -> ParsedInboundEvent:
        event_kind = "other"
        message = raw_payload.get("message")
        if message is not None:
            event_kind = "message"
        else:
            message = raw_payload.get("edited_message")
            if message is not None:
                event_kind = "edited_message"

        callback_query = raw_payload.get("callback_query")
        if callback_query is not None:
            return self._parse_callback_query(raw_payload, callback_query)

        if message is None:
            return ParsedInboundEvent(
                platform=self.platform,
                event_kind=event_kind,
                external_peer_id=None,
                external_peer_kind="unknown",
                external_message_id=None,
                external_user_id=None,
                text=None,
                raw_payload=raw_payload,
            )

        return self._parse_message(raw_payload, message, event_kind)

    def _parse_message(
        self, raw_payload: dict[str, Any], message: dict[str, Any], event_kind: str
    ) -> ParsedInboundEvent:
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_type = str(chat.get("type") or "unknown")
        peer_kind = {
            "private": "direct",
            "group": "group",
            "supergroup": "group",
            "channel": "channel",
        }.get(chat_type, "unknown")
        display_name = chat.get("title") or " ".join(
            part for part in (sender.get("first_name"), sender.get("last_name")) if part
        )

        return ParsedInboundEvent(
            platform=self.platform,
            event_kind=event_kind,
            external_peer_id=str(chat["id"]) if chat.get("id") is not None else None,
            external_peer_kind=peer_kind,
            external_message_id=(
                str(message["message_id"])
                if message.get("message_id") is not None
                else None
            ),
            external_user_id=str(sender["id"])
            if sender.get("id") is not None
            else None,
            text=message.get("text") or message.get("caption"),
            raw_payload=raw_payload,
            display_name=display_name or None,
            username=sender.get("username") or chat.get("username"),
            metadata={
                "chat_type": chat_type,
                "update_id": raw_payload.get("update_id"),
            },
        )

    def _parse_callback_query(
        self, raw_payload: dict[str, Any], callback_query: dict[str, Any]
    ) -> ParsedInboundEvent:
        """Normalize a Telegram callback_query into a gateway event.

        Callback data is placed in ``text`` so downstream routing can treat it like
        a command or payload. ``external_message_id`` points to the message carrying
        the inline keyboard; ``external_peer_id`` comes from the same message's chat.
        """
        user = callback_query.get("from") or {}
        message = callback_query.get("message")

        external_peer_id: str | None = None
        external_message_id: str | None = None
        external_peer_kind = "unknown"
        chat_type = "unknown"

        inline_message_id = callback_query.get("inline_message_id")

        if message is not None:
            chat = message.get("chat") or {}
            chat_type = str(chat.get("type") or "unknown")
            peer_kind = {
                "private": "direct",
                "group": "group",
                "supergroup": "group",
                "channel": "channel",
            }.get(chat_type, "unknown")
            external_peer_id = str(chat["id"]) if chat.get("id") is not None else None
            external_message_id = (
                str(message["message_id"])
                if message.get("message_id") is not None
                else None
            )
            external_peer_kind = peer_kind
        elif inline_message_id is not None:
            external_peer_id = f"inline:{inline_message_id}"
            external_message_id = str(inline_message_id)
            external_peer_kind = "direct"

        return ParsedInboundEvent(
            platform=self.platform,
            event_kind="callback_query",
            external_peer_id=external_peer_id,
            external_peer_kind=external_peer_kind,
            external_message_id=external_message_id,
            external_user_id=str(user["id"]) if user.get("id") is not None else None,
            text=callback_query.get("data"),
            raw_payload=raw_payload,
            display_name=user.get("first_name") or None,
            username=user.get("username"),
            metadata={
                "callback_query_id": callback_query.get("id"),
                "chat_type": chat_type,
                "inline_message_id": callback_query.get("inline_message_id"),
                "update_id": raw_payload.get("update_id"),
            },
        )

    async def send_message(
        self,
        *,
        external_peer_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> PlatformSendResult:
        return await self.client.send_message(
            chat_id=external_peer_id,
            text=text,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    async def edit_message(
        self,
        *,
        external_peer_id: str,
        external_message_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> PlatformSendResult:
        if external_peer_id.startswith("inline:"):
            inline_message_id = external_message_id
            return await self.client.edit_message(
                inline_message_id=inline_message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        return await self.client.edit_message(
            chat_id=external_peer_id,
            message_id=external_message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        await self.client.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def edit_message_reply_markup(
        self,
        *,
        external_peer_id: str,
        external_message_id: str,
        reply_markup: dict | None = None,
    ) -> None:
        if external_peer_id.startswith("inline:"):
            await self.client.edit_message_reply_markup(
                inline_message_id=external_message_id,
                reply_markup=reply_markup,
            )
        else:
            await self.client.edit_message_reply_markup(
                chat_id=external_peer_id,
                message_id=external_message_id,
                reply_markup=reply_markup,
            )

    async def validate_credentials(self) -> dict[str, Any]:
        return await self.client.validate()

    async def leave_chat(self, *, external_peer_id: str) -> None:
        await self.client.leave_chat(chat_id=external_peer_id)

    async def fetch_updates(
        self, *, offset: int | None
    ) -> AsyncIterator[dict[str, Any]]:
        async for update in self.client.get_updates(offset=offset):
            yield update
