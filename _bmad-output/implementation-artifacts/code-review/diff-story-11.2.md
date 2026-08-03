diff --git a/nowing_backend/app/automations/actions/builtin/__init__.py b/nowing_backend/app/automations/actions/builtin/__init__.py
index d8aaa6ce8..53c2be4e7 100644
--- a/nowing_backend/app/automations/actions/builtin/__init__.py
+++ b/nowing_backend/app/automations/actions/builtin/__init__.py
@@ -9,4 +9,5 @@ from . import (
     write_back_linear,  # noqa: F401
     write_back_notion,  # noqa: F401
     write_back_slack,  # noqa: F401
+    write_back_telegram,  # noqa: F401
 )
diff --git a/nowing_backend/app/gateway/base/adapter.py b/nowing_backend/app/gateway/base/adapter.py
index dfe896b4a..0c0d71d5e 100644
--- a/nowing_backend/app/gateway/base/adapter.py
+++ b/nowing_backend/app/gateway/base/adapter.py
@@ -44,6 +44,7 @@ class BasePlatformAdapter(ABC):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         """Send a new platform message."""
 
@@ -55,6 +56,7 @@ class BasePlatformAdapter(ABC):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         """Edit an existing platform message."""
 
diff --git a/nowing_backend/app/gateway/discord/adapter.py b/nowing_backend/app/gateway/discord/adapter.py
index 60db895fe..edf6b3c12 100644
--- a/nowing_backend/app/gateway/discord/adapter.py
+++ b/nowing_backend/app/gateway/discord/adapter.py
@@ -108,8 +108,9 @@ class DiscordAdapter(BasePlatformAdapter):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
-        del parse_mode
+        del parse_mode, reply_markup
         return await self.client.send_message(
             channel_id=external_peer_id,
             content=text,
@@ -123,8 +124,9 @@ class DiscordAdapter(BasePlatformAdapter):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
-        del parse_mode
+        del parse_mode, reply_markup
         return await self.client.update_message(
             channel_id=external_peer_id,
             message_id=external_message_id,
diff --git a/nowing_backend/app/gateway/slack/adapter.py b/nowing_backend/app/gateway/slack/adapter.py
index 9890261bd..7d4bc451f 100644
--- a/nowing_backend/app/gateway/slack/adapter.py
+++ b/nowing_backend/app/gateway/slack/adapter.py
@@ -95,8 +95,9 @@ class SlackAdapter(BasePlatformAdapter):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
-        del parse_mode
+        del parse_mode, reply_markup
         return await self.client.send_message(
             channel=external_peer_id,
             text=text,
@@ -110,8 +111,9 @@ class SlackAdapter(BasePlatformAdapter):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
-        del parse_mode
+        del parse_mode, reply_markup
         return await self.client.update_message(
             channel=external_peer_id,
             ts=external_message_id,
diff --git a/nowing_backend/app/gateway/telegram/adapter.py b/nowing_backend/app/gateway/telegram/adapter.py
index dc4266d42..8d807db33 100644
--- a/nowing_backend/app/gateway/telegram/adapter.py
+++ b/nowing_backend/app/gateway/telegram/adapter.py
@@ -29,6 +29,10 @@ class TelegramAdapter(BasePlatformAdapter):
             if message is not None:
                 event_kind = "edited_message"
 
+        callback_query = raw_payload.get("callback_query")
+        if callback_query is not None:
+            return self._parse_callback_query(raw_payload, callback_query)
+
         if message is None:
             return ParsedInboundEvent(
                 platform=self.platform,
@@ -41,6 +45,11 @@ class TelegramAdapter(BasePlatformAdapter):
                 raw_payload=raw_payload,
             )
 
+        return self._parse_message(raw_payload, message, event_kind)
+
+    def _parse_message(
+        self, raw_payload: dict[str, Any], message: dict[str, Any], event_kind: str
+    ) -> ParsedInboundEvent:
         chat = message.get("chat") or {}
         sender = message.get("from") or {}
         chat_type = str(chat.get("type") or "unknown")
@@ -77,6 +86,65 @@ class TelegramAdapter(BasePlatformAdapter):
             },
         )
 
+    def _parse_callback_query(
+        self, raw_payload: dict[str, Any], callback_query: dict[str, Any]
+    ) -> ParsedInboundEvent:
+        """Normalize a Telegram callback_query into a gateway event.
+
+        Callback data is placed in ``text`` so downstream routing can treat it like
+        a command or payload. ``external_message_id`` points to the message carrying
+        the inline keyboard; ``external_peer_id`` comes from the same message's chat.
+        """
+        user = callback_query.get("from") or {}
+        message = callback_query.get("message")
+
+        external_peer_id: str | None = None
+        external_message_id: str | None = None
+        external_peer_kind = "unknown"
+        chat_type = "unknown"
+
+        inline_message_id = callback_query.get("inline_message_id")
+
+        if message is not None:
+            chat = message.get("chat") or {}
+            chat_type = str(chat.get("type") or "unknown")
+            peer_kind = {
+                "private": "direct",
+                "group": "group",
+                "supergroup": "group",
+                "channel": "channel",
+            }.get(chat_type, "unknown")
+            external_peer_id = str(chat["id"]) if chat.get("id") is not None else None
+            external_message_id = (
+                str(message["message_id"])
+                if message.get("message_id") is not None
+                else None
+            )
+            external_peer_kind = peer_kind
+        elif inline_message_id is not None:
+            external_peer_id = f"inline:{inline_message_id}"
+            external_message_id = str(inline_message_id)
+            external_peer_kind = "direct"
+
+        return ParsedInboundEvent(
+            platform=self.platform,
+            event_kind="callback_query",
+            external_peer_id=external_peer_id,
+            external_peer_kind=external_peer_kind,
+            external_message_id=external_message_id,
+            external_user_id=str(user["id"]) if user.get("id") is not None else None,
+            text=callback_query.get("data"),
+            raw_payload=raw_payload,
+            display_name=user.get("first_name") or None,
+            username=user.get("username"),
+            metadata={
+                "callback_query_id": callback_query.get("id"),
+                "chat_type": chat_type,
+                "inline_message_id": callback_query.get("inline_message_id"),
+                "update_id": raw_payload.get("update_id"),
+            },
+        )
+
     async def send_message(
         self,
         *,
@@ -84,12 +152,14 @@ class TelegramAdapter(BasePlatformAdapter):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         return await self.client.send_message(
             chat_id=external_peer_id,
             text=text,
             parse_mode=parse_mode,
             reply_to_message_id=reply_to_message_id,
+            reply_markup=reply_markup,
         )
 
     async def edit_message(
@@ -99,14 +169,56 @@ class TelegramAdapter(BasePlatformAdapter):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
+        if external_peer_id.startswith("inline:"):
+            inline_message_id = external_message_id
+            return await self.client.edit_message(
+                inline_message_id=inline_message_id,
+                text=text,
+                parse_mode=parse_mode,
+                reply_markup=reply_markup,
+            )
         return await self.client.edit_message(
             chat_id=external_peer_id,
             message_id=external_message_id,
             text=text,
             parse_mode=parse_mode,
+            reply_markup=reply_markup,
+        )
+
+    async def answer_callback_query(
+        self,
+        *,
+        callback_query_id: str,
+        text: str | None = None,
+        show_alert: bool = False,
+    ) -> None:
+        await self.client.answer_callback_query(
+            callback_query_id=callback_query_id,
+            text=text,
+            show_alert=show_alert,
         )
 
+    async def edit_message_reply_markup(
+        self,
+        *,
+        external_peer_id: str,
+        external_message_id: str,
+        reply_markup: dict | None = None,
+    ) -> None:
+        if external_peer_id.startswith("inline:"):
+            await self.client.edit_message_reply_markup(
+                inline_message_id=external_message_id,
+                reply_markup=reply_markup,
+            )
+        else:
+            await self.client.edit_message_reply_markup(
+                chat_id=external_peer_id,
+                message_id=external_message_id,
+                reply_markup=reply_markup,
+            )
+
     async def validate_credentials(self) -> dict[str, Any]:
         return await self.client.validate()
 
diff --git a/nowing_backend/app/gateway/telegram/client.py b/nowing_backend/app/gateway/telegram/client.py
index d3b054451..ae2a942c5 100644
--- a/nowing_backend/app/gateway/telegram/client.py
+++ b/nowing_backend/app/gateway/telegram/client.py
@@ -3,14 +3,18 @@
 from __future__ import annotations
 
 import asyncio
+import logging
 from collections.abc import AsyncIterator
 from datetime import timedelta
 from typing import Any
 
-from telegram import Bot
+from telegram import Bot, InlineKeyboardMarkup
 from telegram.error import BadRequest, RetryAfter
 
 from app.gateway.base.adapter import PlatformSendResult
+from app.gateway.telegram.formatting import unescape_markdown_v2
+
+logger = logging.getLogger(__name__)
 
 
 def retry_after_seconds(value: int | timedelta) -> float:
@@ -19,6 +23,23 @@ def retry_after_seconds(value: int | timedelta) -> float:
     return float(value)
 
 
+def _build_inline_keyboard_markup(
+    bot: Bot, reply_markup: dict | None
+) -> InlineKeyboardMarkup | None:
+    """Coerce a raw dict into an ``InlineKeyboardMarkup`` or ``None`` on failure."""
+    if not reply_markup:
+        return None
+    try:
+        return InlineKeyboardMarkup.de_json(reply_markup, bot)
+    except Exception as exc:
+        logger.warning(
+            "Invalid Telegram reply_markup %r, dropping keyboard: %s",
+            reply_markup,
+            exc,
+        )
+        return None
+
+
 class TelegramClient:
     def __init__(self, token: str) -> None:
         self.token = token
@@ -31,17 +52,25 @@ class TelegramClient:
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         kwargs: dict[str, Any] = {}
         if parse_mode:
             kwargs["parse_mode"] = parse_mode
         if reply_to_message_id:
             kwargs["reply_to_message_id"] = int(reply_to_message_id)
-        try:
-            msg = await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
-        except RetryAfter as exc:
-            await asyncio.sleep(retry_after_seconds(exc.retry_after))
-            msg = await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
+        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
+        if markup is not None:
+            kwargs["reply_markup"] = markup
+
+        msg = await self._send_with_fallbacks(
+            self.bot.send_message,
+            chat_id=chat_id,
+            text=text,
+            kwargs=kwargs,
+            had_parse_mode=parse_mode is not None,
+            had_markup=markup is not None,
+        )
         return PlatformSendResult(
             external_message_id=str(msg.message_id),
             raw_response=msg.to_dict(),
@@ -50,34 +79,159 @@ class TelegramClient:
     async def edit_message(
         self,
         *,
-        chat_id: str,
-        message_id: str,
+        chat_id: str | None = None,
+        message_id: str | None = None,
+        inline_message_id: str | None = None,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         kwargs: dict[str, Any] = {}
         if parse_mode:
             kwargs["parse_mode"] = parse_mode
-        try:
-            msg = await self.bot.edit_message_text(
-                chat_id=chat_id,
-                message_id=int(message_id),
-                text=text,
-                **kwargs,
-            )
-        except RetryAfter as exc:
-            await asyncio.sleep(retry_after_seconds(exc.retry_after))
-            msg = await self.bot.edit_message_text(
-                chat_id=chat_id,
-                message_id=int(message_id),
-                text=text,
-                **kwargs,
-            )
+        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
+        if markup is not None:
+            kwargs["reply_markup"] = markup
+
+        call_kwargs: dict[str, Any] = {"text": text}
+        if inline_message_id is not None:
+            call_kwargs["inline_message_id"] = inline_message_id
+        else:
+            if chat_id is None or message_id is None:
+                raise ValueError(
+                    "edit_message requires chat_id+message_id or inline_message_id"
+                )
+            call_kwargs["chat_id"] = chat_id
+            call_kwargs["message_id"] = int(message_id)
+
+        msg = await self._send_with_fallbacks(
+            self.bot.edit_message_text,
+            kwargs=kwargs,
+            had_parse_mode=parse_mode is not None,
+            had_markup=markup is not None,
+            **call_kwargs,
+        )
         return PlatformSendResult(
             external_message_id=str(msg.message_id),
             raw_response=msg.to_dict(),
         )
 
+    async def _send_with_fallbacks(
+        self,
+        send_call,
+        *,
+        kwargs: dict[str, Any],
+        had_parse_mode: bool,
+        had_markup: bool,
+        **call_kwargs,
+    ) -> Any:
+        """Send with one retry on ``RetryAfter`` and graceful markdown/keyboard fallbacks.
+
+        On ``BadRequest`` we drop ``parse_mode`` first (if present), then
+        ``reply_markup`` (if present). This is type-based, not string-based, so a
+        small number of unrelated ``BadRequest`` calls may be retried once or twice.
+        ponytail: this can waste 1-2 API calls for non-markup/non-markdown errors;
+        the upgrade path is to inspect PTB error codes when Telegram exposes them.
+        """
+        try:
+            return await self._send_once(send_call, kwargs=kwargs, **call_kwargs)
+        except BadRequest as exc:
+            # Drop parse_mode first and retry.
+            if had_parse_mode and kwargs.get("parse_mode"):
+                logger.warning(
+                    "Bad Telegram request with parse_mode, falling back to plain text: %s",
+                    exc,
+                )
+                kwargs.pop("parse_mode", None)
+                # Text was likely pre-escaped for MarkdownV2; unescape so the
+                # plain-text fallback is readable.
+                for key in ("text",):
+                    if isinstance(call_kwargs.get(key), str):
+                        call_kwargs = {
+                            **call_kwargs,
+                            key: unescape_markdown_v2(call_kwargs[key]),
+                        }
+                return await self._send_with_fallbacks(
+                    send_call,
+                    kwargs=kwargs,
+                    had_parse_mode=False,
+                    had_markup=had_markup,
+                    **call_kwargs,
+                )
+
+            # Drop reply_markup and retry.
+            if had_markup and kwargs.get("reply_markup"):
+                logger.warning("Bad Telegram request, dropping keyboard: %s", exc)
+                kwargs.pop("reply_markup", None)
+                return await self._send_with_fallbacks(
+                    send_call,
+                    kwargs=kwargs,
+                    had_parse_mode=had_parse_mode,
+                    had_markup=False,
+                    **call_kwargs,
+                )
+
+            raise
+
+    async def _send_once(
+        self, send_call, *, kwargs: dict[str, Any], **call_kwargs
+    ) -> Any:
+        last_exc: RetryAfter | None = None
+        for _ in range(3):
+            try:
+                return await send_call(**call_kwargs, **kwargs)
+            except RetryAfter as exc:
+                last_exc = exc
+                await asyncio.sleep(retry_after_seconds(exc.retry_after))
+        if last_exc is not None:
+            raise last_exc
+        raise RuntimeError("unexpected empty retry loop")
+
+    async def answer_callback_query(
+        self,
+        *,
+        callback_query_id: str,
+        text: str | None = None,
+        show_alert: bool = False,
+    ) -> None:
+        await self.bot.answer_callback_query(
+            callback_query_id=callback_query_id,
+            text=text,
+            show_alert=show_alert,
+        )
+
+    async def edit_message_reply_markup(
+        self,
+        *,
+        chat_id: str | None = None,
+        message_id: str | None = None,
+        inline_message_id: str | None = None,
+        reply_markup: dict | None = None,
+    ) -> None:
+        kwargs: dict[str, Any] = {}
+        markup = _build_inline_keyboard_markup(self.bot, reply_markup)
+        if markup is not None:
+            kwargs["reply_markup"] = markup
+
+        call_kwargs: dict[str, Any] = {}
+        if inline_message_id is not None:
+            call_kwargs["inline_message_id"] = inline_message_id
+        else:
+            if chat_id is None or message_id is None:
+                raise ValueError(
+                    "edit_message_reply_markup requires chat_id+message_id or inline_message_id"
+                )
+            call_kwargs["chat_id"] = chat_id
+            call_kwargs["message_id"] = int(message_id)
+
+        await self._send_with_fallbacks(
+            self.bot.edit_message_reply_markup,
+            kwargs=kwargs,
+            had_parse_mode=False,
+            had_markup=markup is not None,
+            **call_kwargs,
+        )
+
     async def validate(self) -> dict[str, Any]:
         me = await self.bot.get_me()
         return me.to_dict()
@@ -88,21 +242,29 @@ class TelegramClient:
     async def get_updates(self, *, offset: int | None) -> AsyncIterator[dict[str, Any]]:
         next_offset = offset
         while True:
-            updates = await self.bot.get_updates(
-                offset=next_offset,
-                timeout=30,
-                allowed_updates=["message", "edited_message"],
-            )
+            try:
+                updates = await self.bot.get_updates(
+                    offset=next_offset,
+                    timeout=30,
+                    allowed_updates=["message", "edited_message", "callback_query"],
+                )
+            except Exception:
+                logger.exception(
+                    "Telegram get_updates failed; will retry from offset=%s",
+                    next_offset,
+                )
+                await asyncio.sleep(5)
+                continue
+
             for update in updates:
+                try:
+                    payload = update.to_dict()
+                except Exception:
+                    logger.exception(
+                        "Malformed Telegram update id=%s",
+                        getattr(update, "update_id", None),
+                    )
+                    next_offset = getattr(update, "update_id", 0) + 1
+                    continue
                 next_offset = update.update_id + 1
-                yield update.to_dict()
-
-
-async def retry_plaintext_on_bad_markdown(call, *args, **kwargs) -> PlatformSendResult:
-    try:
-        return await call(*args, **kwargs)
-    except BadRequest as exc:
-        if "can't parse entities" not in str(exc).lower():
-            raise
-        kwargs["parse_mode"] = None
-        return await call(*args, **kwargs)
+                yield payload
diff --git a/nowing_backend/app/gateway/whatsapp/adapter_baileys.py b/nowing_backend/app/gateway/whatsapp/adapter_baileys.py
index 330ef3bb9..4c0b59757 100644
--- a/nowing_backend/app/gateway/whatsapp/adapter_baileys.py
+++ b/nowing_backend/app/gateway/whatsapp/adapter_baileys.py
@@ -53,6 +53,7 @@ class WhatsAppBaileysAdapter(BasePlatformAdapter):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         payload: dict[str, Any] = {"chatId": external_peer_id, "message": text}
         if reply_to_message_id:
@@ -70,6 +71,7 @@ class WhatsAppBaileysAdapter(BasePlatformAdapter):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         data = await self._post(
             "/edit",
diff --git a/nowing_backend/app/gateway/whatsapp/adapter_cloud.py b/nowing_backend/app/gateway/whatsapp/adapter_cloud.py
index 58d13e83e..37d462bcf 100644
--- a/nowing_backend/app/gateway/whatsapp/adapter_cloud.py
+++ b/nowing_backend/app/gateway/whatsapp/adapter_cloud.py
@@ -69,6 +69,7 @@ class WhatsAppCloudAdapter(BasePlatformAdapter):
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         return await self.client.send_text(
             to=external_peer_id,
@@ -83,6 +84,7 @@ class WhatsAppCloudAdapter(BasePlatformAdapter):
         external_message_id: str,
         text: str,
         parse_mode: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
         raise NotImplementedError("WhatsApp Cloud API does not support message edits")
 
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py
new file mode 100644
index 000000000..c52030003
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py
@@ -0,0 +1,28 @@
+"""``TelegramActionParams`` — params for the ``write_back_telegram`` action."""
+
+from __future__ import annotations
+
+from pydantic import BaseModel, ConfigDict, Field
+
+
+class TelegramActionParams(BaseModel):
+    """Send a Telegram message from an automation step."""
+
+    model_config = ConfigDict(extra="forbid")
+
+    chat_id: str | None = Field(
+        default=None,
+        min_length=1,
+        description="Telegram chat id or @channelusername. Falls back to the creator's binding.",
+    )
+    text: str = Field(..., min_length=1)
+    parse_mode: str | None = Field(default=None)
+    reply_to_message_id: str | None = Field(default=None)
+    reply_markup: dict | None = Field(default=None)
+    account_id: int | None = Field(
+        default=None, description="Explicit ExternalChatAccount id."
+    )
+    use_system_bot: bool = Field(
+        default=False,
+        description="Use the workspace/system shared Telegram bot instead of a BYO account.",
+    )
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/__init__.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/__init__.py
new file mode 100644
index 000000000..6e07409c9
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/__init__.py
@@ -0,0 +1,11 @@
+"""``write_back_telegram`` action: send a Telegram message."""
+
+from __future__ import annotations
+
+from .factory import build_handler
+from .params import TelegramActionParams
+
+__all__ = ["TelegramActionParams", "build_handler"]
+
+# Side-effect: register on the actions store.
+from . import definition  # noqa: F401
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py
new file mode 100644
index 000000000..b25516ff9
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py
@@ -0,0 +1,19 @@
+"""``build_handler`` for the ``write_back_telegram`` action."""
+
+from __future__ import annotations
+
+from typing import Any
+
+from ...types import ActionContext, ActionHandler
+from .invoke import write_back_telegram
+from .params import TelegramActionParams
+
+
+def build_handler(ctx: ActionContext) -> ActionHandler:
+    """Return a handler closure that validates params and sends a Telegram message."""
+
+    async def handle(params: dict[str, Any]) -> dict[str, Any]:
+        validated = TelegramActionParams.model_validate(params)
+        return await write_back_telegram(ctx, validated)
+
+    return handle
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/definition.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/definition.py
new file mode 100644
index 000000000..9091bb5d9
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/definition.py
@@ -0,0 +1,18 @@
+"""Register the ``write_back_telegram`` action definition."""
+
+from __future__ import annotations
+
+from ...store import register_action
+from ...types import ActionDefinition
+from .factory import build_handler
+from .params import TelegramActionParams
+
+WRITE_BACK_TELEGRAM_ACTION = ActionDefinition(
+    type="write_back_telegram",
+    name="Write back to Telegram",
+    description="Send a Telegram message via a workspace or system account.",
+    params_model=TelegramActionParams,
+    build_handler=build_handler,
+)
+
+register_action(WRITE_BACK_TELEGRAM_ACTION)
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py
new file mode 100644
index 000000000..b99a9dd0b
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py
@@ -0,0 +1,114 @@
+"""Execute a ``write_back_telegram`` automation step."""
+
+from __future__ import annotations
+
+from typing import Any
+
+from sqlalchemy import select
+
+from app.db import (
+    ExternalChatAccount,
+    ExternalChatBinding,
+    ExternalChatBindingState,
+    ExternalChatPlatform,
+)
+from app.gateway.accounts import account_token
+from app.gateway.telegram.adapter import TelegramAdapter
+
+from ...types import ActionContext
+from .params import TelegramActionParams
+
+
+async def _resolve_telegram_account(
+    ctx: ActionContext, params: TelegramActionParams
+) -> ExternalChatAccount:
+    session = ctx.session
+
+    if params.account_id is not None:
+        account = await session.get(ExternalChatAccount, params.account_id)
+        if account is None:
+            raise ValueError(f"Telegram account {params.account_id} not found")
+        if account.platform != ExternalChatPlatform.TELEGRAM:
+            raise ValueError(f"Account {params.account_id} is not a Telegram account")
+        return account
+
+    if params.use_system_bot:
+        result = await session.execute(
+            select(ExternalChatAccount).where(
+                ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
+                ExternalChatAccount.is_system_account.is_(True),
+            )
+        )
+        account = result.scalars().first()
+        if account is None:
+            raise ValueError("No system Telegram account configured")
+        return account
+
+    result = await session.execute(
+        select(ExternalChatAccount).where(
+            ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
+            ExternalChatAccount.owner_workspace_id == ctx.workspace_id,
+        )
+    )
+    accounts = list(result.scalars().all())
+    if not accounts:
+        raise ValueError(f"No Telegram account found for workspace {ctx.workspace_id}")
+    if len(accounts) > 1:
+        raise ValueError(
+            "Multiple Telegram accounts found; provide account_id or set use_system_bot"
+        )
+    return accounts[0]
+
+
+async def _resolve_chat_id(
+    ctx: ActionContext, account: ExternalChatAccount, params: TelegramActionParams
+) -> str:
+    if params.chat_id is not None:
+        return params.chat_id
+
+    if ctx.creator_user_id is None:
+        raise ValueError(
+            "chat_id is required; no automation creator to resolve a binding"
+        )
+
+    result = await ctx.session.execute(
+        select(ExternalChatBinding).where(
+            ExternalChatBinding.account_id == account.id,
+            ExternalChatBinding.user_id == ctx.creator_user_id,
+            ExternalChatBinding.state == ExternalChatBindingState.BOUND,
+        )
+    )
+    binding = result.scalars().first()
+    if binding is None or not binding.external_peer_id:
+        raise ValueError(
+            f"No active Telegram binding found for creator {ctx.creator_user_id} on account {account.id}"
+        )
+    return binding.external_peer_id
+
+
+async def write_back_telegram(
+    ctx: ActionContext, params: TelegramActionParams
+) -> dict[str, Any]:
+    """Send a Telegram message through a workspace or system account."""
+    account = await _resolve_telegram_account(ctx, params)
+    token = account_token(account)
+    if not token:
+        raise ValueError(f"Telegram account {account.id} has no usable token")
+
+    chat_id = await _resolve_chat_id(ctx, account, params)
+    adapter = TelegramAdapter(token)
+    result = await adapter.send_message(
+        external_peer_id=chat_id,
+        text=params.text,
+        parse_mode=params.parse_mode,
+        reply_to_message_id=params.reply_to_message_id,
+        reply_markup=params.reply_markup,
+    )
+
+    return {
+        "provider": "telegram",
+        "account_id": account.id,
+        "chat_id": chat_id,
+        "message_id": result.external_message_id,
+        "text": params.text,
+    }
diff --git a/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py b/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py
new file mode 100644
index 000000000..025041dbe
--- /dev/null
+++ b/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py
@@ -0,0 +1,186 @@
+"""Unit tests for the ``write_back_telegram`` action."""
+
+from __future__ import annotations
+
+import uuid
+from types import SimpleNamespace
+from unittest.mock import AsyncMock, MagicMock, patch
+
+import pytest
+
+from app.automations.actions.builtin.write_back_telegram.invoke import (
+    _resolve_telegram_account,
+    write_back_telegram,
+)
+from app.automations.actions.builtin.write_back_telegram.params import (
+    TelegramActionParams,
+)
+from app.db import ExternalChatAccount, ExternalChatPlatform
+
+pytestmark = pytest.mark.unit
+
+
+def _account(
+    account_id: int = 1, is_system: bool = False, platform=ExternalChatPlatform.TELEGRAM
+) -> MagicMock:
+    account = MagicMock()
+    account.id = account_id
+    account.platform = platform
+    account.is_system_account = is_system
+    account.owner_workspace_id = 42
+    account.encrypted_credentials = "encrypted"
+    return account
+
+
+@pytest.mark.asyncio
+async def test_resolve_account_by_id():
+    account = _account(account_id=5)
+    session = MagicMock()
+    session.get = AsyncMock(return_value=account)
+
+    params = TelegramActionParams(
+        chat_id="12345",
+        text="Hello",
+        account_id=5,
+    )
+    result = await _resolve_telegram_account(
+        SimpleNamespace(session=session, workspace_id=42), params
+    )
+
+    assert result == account
+    session.get.assert_awaited_once_with(ExternalChatAccount, 5)
+
+
+@pytest.mark.asyncio
+async def test_resolve_system_account():
+    account = _account(account_id=1, is_system=True)
+    session = MagicMock()
+    scalars_mock = MagicMock(first=MagicMock(return_value=account))
+    result_mock = MagicMock(scalars=MagicMock(return_value=scalars_mock))
+    session.execute = AsyncMock(return_value=result_mock)
+
+    params = TelegramActionParams(
+        chat_id="12345",
+        text="Hello",
+        use_system_bot=True,
+    )
+    result = await _resolve_telegram_account(
+        SimpleNamespace(session=session, workspace_id=42), params
+    )
+
+    assert result == account
+
+
+@pytest.mark.asyncio
+async def test_write_back_telegram_sends_message():
+    account = _account(account_id=1)
+    session = MagicMock()
+    session.get = AsyncMock(return_value=account)
+
+    params = TelegramActionParams(
+        chat_id="12345",
+        text="Hello from automation",
+        account_id=1,
+        parse_mode="Markdown",
+        reply_markup={"inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]},
+    )
+
+    send_result = MagicMock()
+    send_result.external_message_id = "99"
+
+    with (
+        patch(
+            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
+            return_value="token",
+        ),
+        patch(
+            "app.automations.actions.builtin.write_back_telegram.invoke.TelegramAdapter"
+        ) as adapter_cls,
+    ):
+        adapter = MagicMock()
+        adapter.send_message = AsyncMock(return_value=send_result)
+        adapter_cls.return_value = adapter
+
+        result = await write_back_telegram(
+            SimpleNamespace(session=session, workspace_id=42), params
+        )
+
+    assert result["provider"] == "telegram"
+    assert result["account_id"] == 1
+    assert result["chat_id"] == "12345"
+    assert result["message_id"] == "99"
+
+    call = adapter.send_message.call_args.kwargs
+    assert call["external_peer_id"] == "12345"
+    assert call["text"] == "Hello from automation"
+    assert call["parse_mode"] == "Markdown"
+    assert call["reply_markup"] == {
+        "inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]
+    }
+
+
+@pytest.mark.asyncio
+async def test_write_back_telegram_requires_token():
+    account = _account(account_id=1)
+    session = MagicMock()
+    session.get = AsyncMock(return_value=account)
+
+    params = TelegramActionParams(chat_id="12345", text="Hello", account_id=1)
+
+    with (
+        patch(
+            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
+            return_value=None,
+        ),
+        pytest.raises(ValueError, match="no usable token"),
+    ):
+        await write_back_telegram(
+            SimpleNamespace(session=session, workspace_id=42), params
+        )
+
+
+@pytest.mark.asyncio
+async def test_write_back_telegram_resolves_chat_id_from_binding():
+    account = _account(account_id=1)
+    session = MagicMock()
+    session.get = AsyncMock(return_value=account)
+
+    binding = MagicMock()
+    binding.external_peer_id = "67890"
+    scalars_mock = MagicMock(first=MagicMock(return_value=binding))
+    result_mock = MagicMock(scalars=MagicMock(return_value=scalars_mock))
+    session.execute = AsyncMock(return_value=result_mock)
+
+    creator_id = uuid.uuid4()
+    params = TelegramActionParams(
+        chat_id=None,
+        text="Hello from binding",
+        account_id=1,
+    )
+
+    send_result = MagicMock()
+    send_result.external_message_id = "55"
+
+    with (
+        patch(
+            "app.automations.actions.builtin.write_back_telegram.invoke.account_token",
+            return_value="token",
+        ),
+        patch(
+            "app.automations.actions.builtin.write_back_telegram.invoke.TelegramAdapter"
+        ) as adapter_cls,
+    ):
+        adapter = MagicMock()
+        adapter.send_message = AsyncMock(return_value=send_result)
+        adapter_cls.return_value = adapter
+
+        result = await write_back_telegram(
+            SimpleNamespace(
+                session=session, workspace_id=42, creator_user_id=creator_id
+            ),
+            params,
+        )
+
+    assert result["chat_id"] == "67890"
+    call = adapter.send_message.call_args.kwargs
+    assert call["external_peer_id"] == "67890"
