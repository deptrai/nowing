"""Thin async Telegram Bot API client."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import BadRequest, RetryAfter

from app.gateway.base.adapter import PlatformSendResult
from app.gateway.telegram.formatting import unescape_markdown_v2

logger = logging.getLogger(__name__)


def retry_after_seconds(value: int | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


_PARSE_ERROR_PHRASES = (
    "can't parse message",
    "can't parse entities",
    "can't find end",
    "unmatched",
    "character",
)

_KEYBOARD_ERROR_PHRASES = (
    "button",
    "keyboard",
    "callback_data",
    "url",
    "inline",
)


def _is_parse_mode_error(message: str) -> bool:
    return any(phrase in message for phrase in _PARSE_ERROR_PHRASES)


def _is_keyboard_error(message: str) -> bool:
    return any(phrase in message for phrase in _KEYBOARD_ERROR_PHRASES)


def _raise_if_not_numeric(value: str | None, name: str) -> None:
    if value is not None and not value.isdigit():
        raise ValueError(f"{name} must be a numeric string, got {value!r}")


def _build_inline_keyboard_markup(
    bot: Bot, reply_markup: dict | None
) -> InlineKeyboardMarkup | None:
    """Coerce a raw dict into an ``InlineKeyboardMarkup`` or ``None`` on failure."""
    if not reply_markup:
        return None
    if not isinstance(reply_markup, dict) or not isinstance(
        reply_markup.get("inline_keyboard"), list
    ):
        logger.warning(
            "Invalid Telegram reply_markup %r, dropping keyboard: missing inline_keyboard",
            reply_markup,
        )
        return None
    try:
        return InlineKeyboardMarkup.de_json(reply_markup, bot)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "Invalid Telegram reply_markup %r, dropping keyboard: %s",
            reply_markup,
            exc,
        )
        return None


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.bot = Bot(token=token)

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> PlatformSendResult:
        _raise_if_not_numeric(reply_to_message_id, "reply_to_message_id")

        kwargs: dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = int(reply_to_message_id)
        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
        if markup is not None:
            kwargs["reply_markup"] = markup

        msg = await self._send_with_fallbacks(
            self.bot.send_message,
            chat_id=chat_id,
            text=text,
            kwargs=kwargs,
        )
        return PlatformSendResult(
            external_message_id=str(msg.message_id),
            raw_response=msg.to_dict(),
        )

    async def edit_message(
        self,
        *,
        chat_id: str | None = None,
        message_id: str | None = None,
        inline_message_id: str | None = None,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> PlatformSendResult:
        kwargs: dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
        if markup is not None:
            kwargs["reply_markup"] = markup

        call_kwargs: dict[str, Any] = {"text": text}
        if inline_message_id is not None:
            call_kwargs["inline_message_id"] = inline_message_id
        else:
            if chat_id is None or message_id is None:
                raise ValueError(
                    "edit_message requires chat_id+message_id or inline_message_id"
                )
            _raise_if_not_numeric(message_id, "message_id")
            call_kwargs["chat_id"] = chat_id
            call_kwargs["message_id"] = int(message_id)

        msg = await self._send_with_fallbacks(
            self.bot.edit_message_text,
            kwargs=kwargs,
            **call_kwargs,
        )

        if msg is True:
            return PlatformSendResult(
                external_message_id=str(inline_message_id or message_id),
                raw_response={"ok": True},
            )
        return PlatformSendResult(
            external_message_id=str(msg.message_id),
            raw_response=msg.to_dict(),
        )

    async def _send_with_fallbacks(
        self,
        send_call,
        *,
        kwargs: dict[str, Any],
        **call_kwargs,
    ) -> Any:
        """Send with one retry on ``RetryAfter`` and graceful markdown/keyboard fallbacks.

        On ``BadRequest`` we try to identify the source of the error and drop
        ``parse_mode`` or ``reply_markup`` accordingly. MarkdownV2 text is
        unescaped when dropping parse_mode only if the original message used
        MarkdownV2.
        """
        try:
            return await self._send_once(send_call, kwargs=kwargs, **call_kwargs)
        except BadRequest as exc:
            msg = str(getattr(exc, "message", exc)).lower()
            original_parse_mode = kwargs.get("parse_mode")

            if _is_parse_mode_error(msg) and kwargs.get("parse_mode"):
                logger.warning(
                    "Bad Telegram request with parse_mode, falling back to plain text: %s",
                    exc,
                )
                kwargs.pop("parse_mode", None)
                if original_parse_mode == "MarkdownV2":
                    for key in ("text",):
                        if isinstance(call_kwargs.get(key), str):
                            call_kwargs[key] = unescape_markdown_v2(call_kwargs[key])
                return await self._send_with_fallbacks(
                    send_call, kwargs=kwargs, **call_kwargs
                )

            if _is_keyboard_error(msg) and kwargs.get("reply_markup"):
                logger.warning("Bad Telegram request, dropping keyboard: %s", exc)
                kwargs.pop("reply_markup", None)
                return await self._send_with_fallbacks(
                    send_call, kwargs=kwargs, **call_kwargs
                )

            # Generic fallback: drop parse_mode first, then reply_markup.
            if kwargs.get("parse_mode"):
                logger.warning(
                    "Bad Telegram request, falling back to plain text: %s",
                    exc,
                )
                kwargs.pop("parse_mode", None)
                if original_parse_mode == "MarkdownV2":
                    for key in ("text",):
                        if isinstance(call_kwargs.get(key), str):
                            call_kwargs[key] = unescape_markdown_v2(call_kwargs[key])
                return await self._send_with_fallbacks(
                    send_call, kwargs=kwargs, **call_kwargs
                )

            if kwargs.get("reply_markup"):
                logger.warning("Bad Telegram request, dropping keyboard: %s", exc)
                kwargs.pop("reply_markup", None)
                return await self._send_with_fallbacks(
                    send_call, kwargs=kwargs, **call_kwargs
                )

            raise

    async def _send_once(
        self, send_call, *, kwargs: dict[str, Any], **call_kwargs
    ) -> Any:
        last_exc: RetryAfter | None = None
        for _ in range(3):
            try:
                return await send_call(**call_kwargs, **kwargs)
            except RetryAfter as exc:
                last_exc = exc
                await asyncio.sleep(retry_after_seconds(exc.retry_after))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("unexpected empty retry loop")

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        await self.bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def edit_message_reply_markup(
        self,
        *,
        chat_id: str | None = None,
        message_id: str | None = None,
        inline_message_id: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
        if markup is not None:
            kwargs["reply_markup"] = markup

        call_kwargs: dict[str, Any] = {}
        if inline_message_id is not None:
            call_kwargs["inline_message_id"] = inline_message_id
        else:
            if chat_id is None or message_id is None:
                raise ValueError(
                    "edit_message_reply_markup requires chat_id+message_id or inline_message_id"
                )
            _raise_if_not_numeric(message_id, "message_id")
            call_kwargs["chat_id"] = chat_id
            call_kwargs["message_id"] = int(message_id)

        await self._send_with_fallbacks(
            self.bot.edit_message_reply_markup,
            kwargs=kwargs,
            **call_kwargs,
        )

    async def validate(self) -> dict[str, Any]:
        me = await self.bot.get_me()
        return me.to_dict()

    async def leave_chat(self, *, chat_id: str) -> None:
        await self.bot.leave_chat(chat_id=chat_id)

    async def get_updates(self, *, offset: int | None) -> AsyncIterator[dict[str, Any]]:
        next_offset = offset
        while True:
            try:
                updates = await self.bot.get_updates(
                    offset=next_offset,
                    timeout=30,
                    allowed_updates=["message", "edited_message", "callback_query"],
                )
            except Exception:
                logger.exception(
                    "Telegram get_updates failed; will retry from offset=%s",
                    next_offset,
                )
                await asyncio.sleep(5)
                continue

            for update in updates:
                try:
                    payload = update.to_dict()
                except Exception:
                    logger.exception(
                        "Malformed Telegram update id=%s",
                        getattr(update, "update_id", None),
                    )
                    next_offset = getattr(update, "update_id", 0) + 1
                    continue
                next_offset = update.update_id + 1
                yield payload
