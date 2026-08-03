# Diff for Story 11.2 re-review

## nowing_backend/app/automations/actions/builtin/__init__.py

```diff
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
```

## nowing_backend/app/gateway/telegram/adapter.py

```diff
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
 
```

## nowing_backend/app/gateway/telegram/client.py

```diff
diff --git a/nowing_backend/app/gateway/telegram/client.py b/nowing_backend/app/gateway/telegram/client.py
index d3b054451..d78e8d6c2 100644
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
@@ -19,6 +23,61 @@ def retry_after_seconds(value: int | timedelta) -> float:
     return float(value)
 
 
+_PARSE_ERROR_PHRASES = (
+    "can't parse message",
+    "can't parse entities",
+    "can't find end",
+    "unmatched",
+    "character",
+)
+
+_KEYBOARD_ERROR_PHRASES = (
+    "button",
+    "keyboard",
+    "callback_data",
+    "url",
+    "inline",
+)
+
+
+def _is_parse_mode_error(message: str) -> bool:
+    return any(phrase in message for phrase in _PARSE_ERROR_PHRASES)
+
+
+def _is_keyboard_error(message: str) -> bool:
+    return any(phrase in message for phrase in _KEYBOARD_ERROR_PHRASES)
+
+
+def _raise_if_not_numeric(value: str | None, name: str) -> None:
+    if value is not None and not value.isdigit():
+        raise ValueError(f"{name} must be a numeric string, got {value!r}")
+
+
+def _build_inline_keyboard_markup(
+    bot: Bot, reply_markup: dict | None
+) -> InlineKeyboardMarkup | None:
+    """Coerce a raw dict into an ``InlineKeyboardMarkup`` or ``None`` on failure."""
+    if not reply_markup:
+        return None
+    if not isinstance(reply_markup, dict) or not isinstance(
+        reply_markup.get("inline_keyboard"), list
+    ):
+        logger.warning(
+            "Invalid Telegram reply_markup %r, dropping keyboard: missing inline_keyboard",
+            reply_markup,
+        )
+        return None
+    try:
+        return InlineKeyboardMarkup.de_json(reply_markup, bot)
+    except (TypeError, ValueError) as exc:
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
@@ -31,17 +90,25 @@ class TelegramClient:
         text: str,
         parse_mode: str | None = None,
         reply_to_message_id: str | None = None,
+        reply_markup: dict | None = None,
     ) -> PlatformSendResult:
+        _raise_if_not_numeric(reply_to_message_id, "reply_to_message_id")
+
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
+        )
         return PlatformSendResult(
             external_message_id=str(msg.message_id),
             raw_response=msg.to_dict(),
@@ -50,34 +117,171 @@ class TelegramClient:
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
+            _raise_if_not_numeric(message_id, "message_id")
+            call_kwargs["chat_id"] = chat_id
+            call_kwargs["message_id"] = int(message_id)
+
+        msg = await self._send_with_fallbacks(
+            self.bot.edit_message_text,
+            kwargs=kwargs,
+            **call_kwargs,
+        )
+
+        if msg is True:
+            return PlatformSendResult(
+                external_message_id=str(inline_message_id or message_id),
+                raw_response={"ok": True},
             )
         return PlatformSendResult(
             external_message_id=str(msg.message_id),
             raw_response=msg.to_dict(),
         )
 
+    async def _send_with_fallbacks(
+        self,
+        send_call,
+        *,
+        kwargs: dict[str, Any],
+        **call_kwargs,
+    ) -> Any:
+        """Send with one retry on ``RetryAfter`` and graceful markdown/keyboard fallbacks.
+
+        On ``BadRequest`` we try to identify the source of the error and drop
+        ``parse_mode`` or ``reply_markup`` accordingly. MarkdownV2 text is
+        unescaped when dropping parse_mode only if the original message used
+        MarkdownV2.
+        """
+        try:
+            return await self._send_once(send_call, kwargs=kwargs, **call_kwargs)
+        except BadRequest as exc:
+            msg = str(getattr(exc, "message", exc)).lower()
+            original_parse_mode = kwargs.get("parse_mode")
+
+            if _is_parse_mode_error(msg) and kwargs.get("parse_mode"):
+                logger.warning(
+                    "Bad Telegram request with parse_mode, falling back to plain text: %s",
+                    exc,
+                )
+                kwargs.pop("parse_mode", None)
+                if original_parse_mode == "MarkdownV2":
+                    for key in ("text",):
+                        if isinstance(call_kwargs.get(key), str):
+                            call_kwargs[key] = unescape_markdown_v2(call_kwargs[key])
+                return await self._send_with_fallbacks(
+                    send_call, kwargs=kwargs, **call_kwargs
+                )
+
+            if _is_keyboard_error(msg) and kwargs.get("reply_markup"):
+                logger.warning("Bad Telegram request, dropping keyboard: %s", exc)
+                kwargs.pop("reply_markup", None)
+                return await self._send_with_fallbacks(
+                    send_call, kwargs=kwargs, **call_kwargs
+                )
+
+            # Generic fallback: drop parse_mode first, then reply_markup.
+            if kwargs.get("parse_mode"):
+                logger.warning(
+                    "Bad Telegram request, falling back to plain text: %s",
+                    exc,
+                )
+                kwargs.pop("parse_mode", None)
+                if original_parse_mode == "MarkdownV2":
+                    for key in ("text",):
+                        if isinstance(call_kwargs.get(key), str):
+                            call_kwargs[key] = unescape_markdown_v2(call_kwargs[key])
+                return await self._send_with_fallbacks(
+                    send_call, kwargs=kwargs, **call_kwargs
+                )
+
+            if kwargs.get("reply_markup"):
+                logger.warning("Bad Telegram request, dropping keyboard: %s", exc)
+                kwargs.pop("reply_markup", None)
+                return await self._send_with_fallbacks(
+                    send_call, kwargs=kwargs, **call_kwargs
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
+            _raise_if_not_numeric(message_id, "message_id")
+            call_kwargs["chat_id"] = chat_id
+            call_kwargs["message_id"] = int(message_id)
+
+        await self._send_with_fallbacks(
+            self.bot.edit_message_reply_markup,
+            kwargs=kwargs,
+            **call_kwargs,
+        )
+
     async def validate(self) -> dict[str, Any]:
         me = await self.bot.get_me()
         return me.to_dict()
@@ -88,21 +292,29 @@ class TelegramClient:
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
```

## nowing_backend/app/gateway/telegram/formatting.py

```diff
diff --git a/nowing_backend/app/gateway/telegram/formatting.py b/nowing_backend/app/gateway/telegram/formatting.py
index 668a6c7ed..d2d8cea79 100644
--- a/nowing_backend/app/gateway/telegram/formatting.py
+++ b/nowing_backend/app/gateway/telegram/formatting.py
@@ -11,12 +11,20 @@ MAX_TELEGRAM_MESSAGE_UNITS = 4096
 
 _RESERVED_RE = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}\.!])")
 
+# Remove backslashes only when they escape a reserved MarkdownV2 character.
+_UNESCAPE_RE = re.compile(r"\\([" + re.escape(MARKDOWN_V2_RESERVED) + r"])")
+
 
 def escape_markdown_v2(text: str) -> str:
     """Escape all Telegram MarkdownV2 reserved characters."""
     return _RESERVED_RE.sub(r"\\\1", text)
 
 
+def unescape_markdown_v2(text: str) -> str:
+    """Undo MarkdownV2 escaping so plain-text fallback does not show backslashes."""
+    return _UNESCAPE_RE.sub(r"\1", text)
+
+
 def _utf16_len(text: str) -> int:
     return len(text.encode("utf-16-le")) // 2
 
```

## nowing_backend/tests/unit/gateway/test_formatting.py

```diff
diff --git a/nowing_backend/tests/unit/gateway/test_formatting.py b/nowing_backend/tests/unit/gateway/test_formatting.py
index 4d842e169..088ab22ec 100644
--- a/nowing_backend/tests/unit/gateway/test_formatting.py
+++ b/nowing_backend/tests/unit/gateway/test_formatting.py
@@ -1,4 +1,8 @@
-from app.gateway.telegram.formatting import chunk_message, escape_markdown_v2
+from app.gateway.telegram.formatting import (
+    chunk_message,
+    escape_markdown_v2,
+    unescape_markdown_v2,
+)
 
 
 def test_escape_markdown_v2_reserved_chars():
@@ -7,6 +11,11 @@ def test_escape_markdown_v2_reserved_chars():
     assert escape_markdown_v2(text) == r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"
 
 
+def test_unescape_markdown_v2_only_reserved_chars():
+    text = r"hello \*world and \\not reserved"
+    assert unescape_markdown_v2(text) == r"hello *world and \\not reserved"
+
+
 def test_chunk_message_preserves_content_and_limits_size():
     text = "First paragraph.\n\n" + ("x" * 5000)
 
```

## nowing_web/lib/automations/builder-schema.ts

```diff
diff --git a/nowing_web/lib/automations/builder-schema.ts b/nowing_web/lib/automations/builder-schema.ts
index 185d365bd..a33a8fa67 100644
--- a/nowing_web/lib/automations/builder-schema.ts
+++ b/nowing_web/lib/automations/builder-schema.ts
@@ -36,6 +36,7 @@ export const writeBackActionSchema = z.enum([
 	"write_back_linear",
 	"write_back_jira",
 	"write_back_slack",
+	"write_back_telegram",
 ]);
 export type WriteBackAction = z.infer<typeof writeBackActionSchema>;
 
@@ -77,11 +78,25 @@ const slackWriteBackParamsSchema = z.object({
 	object_id: z.string().trim().nullable().default(null),
 });
 
+const telegramWriteBackParamsSchema = z.object({
+	provider: z.literal("telegram"),
+	text: z.string().trim().min(1, "Message text is required"),
+	chat_id: z.string().trim().nullable().default(null),
+	parse_mode: z.enum(["Markdown", "MarkdownV2", "none"]).nullable().default("Markdown"),
+	reply_markup: z.record(z.string(), z.any()).nullable().default(null),
+	account_id: z.number().int().nullable().default(null),
+	use_system_bot: z.boolean().default(true),
+	reply_to_message_id: z.string().trim().nullable().default(null),
+	connector_name: z.string().trim().nullable().default(null),
+	object_id: z.string().trim().nullable().default(null),
+});
+
 export const writeBackParamsSchema = z.discriminatedUnion("provider", [
 	notionWriteBackParamsSchema,
 	linearWriteBackParamsSchema,
 	jiraWriteBackParamsSchema,
 	slackWriteBackParamsSchema,
+	telegramWriteBackParamsSchema,
 ]);
 export type WriteBackParams = z.infer<typeof writeBackParamsSchema>;
 
@@ -288,6 +303,13 @@ function buildWriteBackParams(
 	// Provider is only used for form discrimination; the backend action already
 	// encodes the target service.
 	const { provider: _, ...rest } = params;
+	if (
+		action === "write_back_telegram" &&
+		params.provider === "telegram" &&
+		params.parse_mode === "none"
+	) {
+		return { ...rest, parse_mode: null };
+	}
 	return rest;
 }
 
@@ -532,6 +554,26 @@ function writeBackParamsFromParams(
 			object_id,
 		};
 	}
+	if (action === "write_back_telegram") {
+		const rawParseMode = stringOrNull(params.parse_mode);
+		const parse_mode: "Markdown" | "MarkdownV2" | "none" | null =
+			rawParseMode === null ? "none" : (rawParseMode as "Markdown" | "MarkdownV2" | "none");
+		return {
+			provider: "telegram",
+			text: stringOrNull(params.text) ?? "",
+			chat_id: stringOrNull(params.chat_id),
+			parse_mode,
+			reply_markup:
+				typeof params.reply_markup === "object" && params.reply_markup !== null
+					? (params.reply_markup as Record<string, unknown>)
+					: null,
+			account_id: typeof params.account_id === "number" ? params.account_id : null,
+			use_system_bot: typeof params.use_system_bot === "boolean" ? params.use_system_bot : true,
+			reply_to_message_id: stringOrNull(params.reply_to_message_id),
+			connector_name,
+			object_id,
+		};
+	}
 	return null;
 }
 
@@ -540,6 +582,7 @@ const WRITE_BACK_ACTIONS = new Set([
 	"write_back_linear",
 	"write_back_jira",
 	"write_back_slack",
+	"write_back_telegram",
 ]);
 
 export function hydrateForm(
```

## nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx

```diff
diff --git a/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx b/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx
index 6db178d08..553dddf1a 100644
--- a/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx
+++ b/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx
@@ -37,6 +37,7 @@ const ACTION_OPTIONS: { value: WriteBackAction; label: string }[] = [
 	{ value: "write_back_linear", label: "Write back to Linear" },
 	{ value: "write_back_jira", label: "Write back to Jira" },
 	{ value: "write_back_slack", label: "Write back to Slack" },
+	{ value: "write_back_telegram", label: "Send Telegram message" },
 ];
 
 function parseOptionalInt(raw: string): number | null {
@@ -86,6 +87,19 @@ function defaultWriteBackParams(action: WriteBackAction): WriteBackParams {
 				connector_name: null,
 				object_id: null,
 			};
+		case "write_back_telegram":
+			return {
+				provider: "telegram",
+				text: "",
+				chat_id: null,
+				parse_mode: "Markdown",
+				reply_markup: null,
+				account_id: null,
+				use_system_bot: true,
+				reply_to_message_id: null,
+				connector_name: null,
+				object_id: null,
+			};
 		default:
 			// Should never happen for non write-back actions.
 			return {
@@ -214,22 +228,24 @@ export function TaskItem({
 				</Field>
 			) : (
 				<div className="space-y-3">
-					<Field
-						label="Connector name"
-						hint="Optional when only one connector of this type exists."
-					>
-						<Input
-							type="text"
-							value={params?.connector_name ?? ""}
-							aria-label="Connector name"
-							placeholder="e.g. Acme Notion"
-							onChange={(e) =>
-								updateWriteBackParam({
-									connector_name: e.target.value.trim() || null,
-								} as Partial<WriteBackParams>)
-							}
-						/>
-					</Field>
+					{task.action !== "write_back_telegram" && (
+						<Field
+							label="Connector name"
+							hint="Optional when only one connector of this type exists."
+						>
+							<Input
+								type="text"
+								value={params?.connector_name ?? ""}
+								aria-label="Connector name"
+								placeholder="e.g. Acme Notion"
+								onChange={(e) =>
+									updateWriteBackParam({
+										connector_name: e.target.value.trim() || null,
+									} as Partial<WriteBackParams>)
+								}
+							/>
+						</Field>
+					)}
 					{task.action === "write_back_notion" && params?.provider === "notion" && (
 						<>
 							<Field label="Title" required>
@@ -416,19 +432,89 @@ export function TaskItem({
 							</Field>
 						</>
 					)}
-					<Field label="Existing object id" hint="Optional: update instead of create.">
-						<Input
-							type="text"
-							value={params?.object_id ?? ""}
-							aria-label="Existing object id"
-							placeholder="page id / issue key / message ts"
-							onChange={(e) =>
-								updateWriteBackParam({
-									object_id: e.target.value.trim() || null,
-								} as Partial<WriteBackParams>)
-							}
-						/>
-					</Field>
+					{task.action === "write_back_telegram" && params?.provider === "telegram" && (
+						<>
+							<Field label="Message text" required>
+								<Input
+									type="text"
+									value={params.text}
+									aria-label="Message text"
+									placeholder="What to send"
+									onChange={(e) =>
+										updateWriteBackParam({ text: e.target.value } as Partial<WriteBackParams>)
+									}
+								/>
+							</Field>
+							<Field label="Chat id" hint="Optional: leave blank to use your paired Telegram chat">
+								<Input
+									type="text"
+									value={params.chat_id ?? ""}
+									aria-label="Chat id"
+									placeholder="@channelusername or 123456789"
+									onChange={(e) =>
+										updateWriteBackParam({
+											chat_id: e.target.value.trim() || null,
+										} as Partial<WriteBackParams>)
+									}
+								/>
+							</Field>
+							<Field label="Parse mode">
+								<Select
+									value={params.parse_mode ?? "none"}
+									onValueChange={(value) =>
+										updateWriteBackParam({
+											parse_mode: value === "none" ? null : (value as "Markdown" | "MarkdownV2"),
+										} as Partial<WriteBackParams>)
+									}
+								>
+									<SelectTrigger aria-label="Parse mode">
+										<SelectValue />
+									</SelectTrigger>
+									<SelectContent>
+										<SelectItem value="Markdown">Markdown</SelectItem>
+										<SelectItem value="MarkdownV2">MarkdownV2</SelectItem>
+										<SelectItem value="none">none</SelectItem>
+									</SelectContent>
+								</Select>
+							</Field>
+							<Field label="Reply markup (raw JSON)" hint="Optional inline keyboard JSON">
+								<Input
+									type="text"
+									value={params.reply_markup ? JSON.stringify(params.reply_markup) : ""}
+									aria-label="Reply markup"
+									placeholder='{"inline_keyboard": [[{"text": "Open", "url": "..."}]]}'
+									onChange={(e) => {
+										const raw = e.target.value.trim();
+										if (!raw) {
+											updateWriteBackParam({ reply_markup: null } as Partial<WriteBackParams>);
+											return;
+										}
+										try {
+											const parsed = JSON.parse(raw) as Record<string, unknown>;
+											updateWriteBackParam({ reply_markup: parsed } as Partial<WriteBackParams>);
+										} catch {
+											// Ignore invalid JSON while the user is typing.
+										}
+									}}
+								/>
+							</Field>
+						</>
+					)}
+					{task.action !== "write_back_telegram" && (
+						<Field label="Existing object id" hint="Optional: update instead of create.">
+							<Input
+								type="text"
+								value={params?.object_id ?? ""}
+								aria-label="Existing object id"
+								placeholder="page id / issue key / message ts"
+								onChange={(e) =>
+									updateWriteBackParam({
+										object_id: e.target.value.trim() || null,
+									} as Partial<WriteBackParams>)
+								}
+							/>
+						</Field>
+					)}
 				</div>
 			)}
 
```

## nowing_web/app/dashboard/[workspace_id]/automations/components/builder/builder-summary.tsx

```diff
diff --git a/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/builder-summary.tsx b/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/builder-summary.tsx
index a1639a18a..edbbb05a7 100644
--- a/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/builder-summary.tsx
+++ b/nowing_web/app/dashboard/[workspace_id]/automations/components/builder/builder-summary.tsx
@@ -19,7 +19,8 @@ function taskSummary(task: BuilderForm["tasks"][number]): string {
 		if (task.writeBackParams.provider === "slack") return `Post to ${task.writeBackParams.channel}`;
 		if (task.writeBackParams.provider === "jira") return `Jira: ${task.writeBackParams.summary}`;
 		if (task.writeBackParams.provider === "linear") return `Linear: ${task.writeBackParams.title}`;
-		return `Notion: ${task.writeBackParams.title}`;
+		if (task.writeBackParams.provider === "notion") return `Notion: ${task.writeBackParams.title}`;
+		return `Telegram: ${task.writeBackParams.text}`;
 	}
 	return task.action.replace(/_/g, " ");
 }
```

## nowing_web/tests/automations/builder-schema.test.ts

```diff
diff --git a/nowing_web/tests/automations/builder-schema.test.ts b/nowing_web/tests/automations/builder-schema.test.ts
index 16d31072d..36e34df7a 100644
--- a/nowing_web/tests/automations/builder-schema.test.ts
+++ b/nowing_web/tests/automations/builder-schema.test.ts
@@ -6,10 +6,12 @@
  */
 
 import assert from "node:assert/strict";
+import type { Automation } from "@/contracts/types/automation.types";
 import {
 	buildCreatePayload,
 	buildUpdatePayload,
 	createEmptyForm,
+	formFromAutomation,
 } from "@/lib/automations/builder-schema";
 
 function formWithTask() {
@@ -33,4 +35,96 @@ function testBuildUpdatePayloadEmitsSchemaVersion11() {
 testBuildCreatePayloadEmitsSchemaVersion11();
 testBuildUpdatePayloadEmitsSchemaVersion11();
 
+function testTelegramRoundTrip() {
+	const form = createEmptyForm();
+	form.name = "Telegram alert";
+	form.tasks = [
+		{
+			id: "task-1",
+			action: "write_back_telegram",
+			query: "",
+			mentions: [],
+			writeBackParams: {
+				provider: "telegram",
+				text: "Hello from automation",
+				chat_id: "12345",
+				parse_mode: "Markdown",
+				reply_markup: { inline_keyboard: [[{ text: "Open", url: "https://nowing.net" }]] },
+				account_id: null,
+				use_system_bot: true,
+				reply_to_message_id: null,
+				connector_name: null,
+				object_id: null,
+			},
+			maxRetries: null,
+			timeoutSeconds: null,
+		},
+	];
+
+	const payload = buildCreatePayload(form, 42);
+	const step = payload.definition.plan[0];
+	assert.equal(step.action, "write_back_telegram");
+	assert.equal(step.params.text, "Hello from automation");
+	assert.equal(step.params.chat_id, "12345");
+	assert.equal(step.params.parse_mode, "Markdown");
+	assert.deepEqual(step.params.reply_markup, {
+		inline_keyboard: [[{ text: "Open", url: "https://nowing.net" }]],
+	});
+	assert.equal(step.params.provider, undefined);
+
+	const automation: Automation = {
+		id: 1,
+		workspace_id: 42,
+		name: payload.name,
+		description: payload.description,
+		status: "active",
+		version: 1,
+		created_at: new Date().toISOString(),
+		updated_at: new Date().toISOString(),
+		definition: payload.definition,
+		triggers: payload.triggers as Automation["triggers"],
+	};
+
+	const hydrated = formFromAutomation(automation);
+	assert.equal(hydrated.formable, true);
+	assert.equal(hydrated.form.tasks[0].action, "write_back_telegram");
+	assert.equal(hydrated.form.tasks[0].writeBackParams?.provider, "telegram");
+	assert.equal(hydrated.form.tasks[0].writeBackParams?.text, "Hello from automation");
+	assert.equal(hydrated.form.tasks[0].writeBackParams?.chat_id, "12345");
+	assert.equal(hydrated.form.tasks[0].writeBackParams?.parse_mode, "Markdown");
+}
+
+function testTelegramNoneParseMode() {
+	const form = createEmptyForm();
+	form.name = "Telegram plain";
+	form.tasks = [
+		{
+			id: "task-1",
+			action: "write_back_telegram",
+			query: "",
+			mentions: [],
+			writeBackParams: {
+				provider: "telegram",
+				text: "plain text",
+				chat_id: null,
+				parse_mode: null,
+				reply_markup: null,
+				account_id: null,
+				use_system_bot: true,
+				reply_to_message_id: null,
+				connector_name: null,
+				object_id: null,
+			},
+			maxRetries: null,
+			timeoutSeconds: null,
+		},
+	];
+
+	const payload = buildCreatePayload(form, 42);
+	assert.equal(payload.definition.plan[0].params.parse_mode, null);
+}
+
+testTelegramRoundTrip();
+testTelegramNoneParseMode();
+
 console.log("builder-schema.test.ts: all assertions passed");
```

## nowing_backend/app/automations/actions/builtin/write_back_telegram/__init__.py (untracked)

```diff
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
```

## nowing_backend/app/automations/actions/builtin/write_back_telegram/definition.py (untracked)

```diff
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
```

## nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py (untracked)

```diff
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py
new file mode 100644
index 000000000..73a7ef4a8
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py
@@ -0,0 +1,25 @@
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
+    """Return a handler closure that sends a Telegram message.
+
+    ``execute_step`` already validates ``resolved_params`` against
+    ``TelegramActionParams`` before the retry loop, so the handler builds the
+    model instance without re-running validation to avoid deterministic
+    ``ValidationError`` retries.
+    """
+
+    async def handle(params: dict[str, Any]) -> dict[str, Any]:
+        validated = TelegramActionParams.model_construct(**params)
+        return await write_back_telegram(ctx, validated)
+
+    return handle
```

## nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py (untracked)

```diff
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py
new file mode 100644
index 000000000..16952d9f4
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py
@@ -0,0 +1,130 @@
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
+TELEGRAM = ExternalChatPlatform.TELEGRAM
+
+
+def _format_account_error(account_id: int, msg: str) -> str:
+    return f"Telegram account {account_id}: {msg}"
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
+        if account.platform != TELEGRAM:
+            raise ValueError(
+                _format_account_error(params.account_id, "not a Telegram account")
+            )
+        if account.suspended_at is not None:
+            raise ValueError(
+                _format_account_error(params.account_id, "account is suspended")
+            )
+        if account.is_system_account:
+            return account
+        if (
+            account.owner_workspace_id != ctx.workspace_id
+            and account.owner_user_id != ctx.creator_user_id
+        ):
+            raise ValueError(
+                _format_account_error(
+                    params.account_id,
+                    "does not belong to this workspace or user",
+                )
+            )
+        return account
+
+    if params.use_system_bot:
+        result = await session.execute(
+            select(ExternalChatAccount).where(
+                ExternalChatAccount.platform == TELEGRAM,
+                ExternalChatAccount.is_system_account.is_(True),
+                ExternalChatAccount.suspended_at.is_(None),
+            )
+        )
+        account = result.scalars().first()
+        if account is None:
+            raise ValueError("No system Telegram account configured")
+        return account
+
+    raise ValueError("Provide a Telegram account_id or set use_system_bot=true")
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
+            ExternalChatBinding.workspace_id == ctx.workspace_id,
+            ExternalChatBinding.user_id == ctx.creator_user_id,
+            ExternalChatBinding.state == ExternalChatBindingState.BOUND,
+            ExternalChatBinding.suspended_at.is_(None),
+            ExternalChatBinding.revoked_at.is_(None),
+        )
+    )
+    binding = result.scalars().first()
+    if binding is None or not binding.external_peer_id:
+        raise ValueError("No Telegram chat bound to this user or workspace")
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
+        "parse_mode": params.parse_mode,
+        "reply_markup": params.reply_markup,
+        "reply_to_message_id": params.reply_to_message_id,
+    }
```

## nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py (untracked)

```diff
diff --git a/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py b/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py
new file mode 100644
index 000000000..b19ad73f5
--- /dev/null
+++ b/nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py
@@ -0,0 +1,36 @@
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
+    parse_mode: str | None = Field(default="Markdown")
+    reply_to_message_id: str | None = Field(default=None)
+    reply_markup: dict | None = Field(default=None)
+    account_id: int | None = Field(
+        default=None, description="Explicit ExternalChatAccount id."
+    )
+    use_system_bot: bool = Field(
+        default=True,
+        description="Use the workspace/system shared Telegram bot instead of a BYO account.",
+    )
+    connector_name: str | None = Field(
+        default=None,
+        description="Ignored: present so the builder form pattern (connector_name/object_id) round-trips.",
+    )
+    object_id: str | None = Field(
+        default=None,
+        description="Ignored: present so the builder form pattern (connector_name/object_id) round-trips.",
+    )
```

## nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py (untracked)

```diff
diff --git a/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py b/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py
new file mode 100644
index 000000000..74df7a4f5
--- /dev/null
+++ b/nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py
@@ -0,0 +1,333 @@
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
+    _resolve_chat_id,
+    _resolve_telegram_account,
+    write_back_telegram,
+)
+from app.automations.actions.builtin.write_back_telegram.params import (
+    TelegramActionParams,
+)
+from app.db import ExternalChatAccount, ExternalChatBindingState, ExternalChatPlatform
+
+pytestmark = pytest.mark.unit
+
+
+def _account(
+    account_id: int = 1,
+    *,
+    is_system: bool = False,
+    platform=ExternalChatPlatform.TELEGRAM,
+    owner_workspace_id: int = 42,
+    owner_user_id: uuid.UUID | None = None,
+    suspended_at=None,
+) -> MagicMock:
+    account = MagicMock()
+    account.id = account_id
+    account.platform = platform
+    account.is_system_account = is_system
+    account.owner_workspace_id = owner_workspace_id
+    account.owner_user_id = owner_user_id
+    account.suspended_at = suspended_at
+    account.encrypted_credentials = "encrypted"
+    return account
+
+
+def _binding(
+    *, external_peer_id: str, state=ExternalChatBindingState.BOUND
+) -> MagicMock:
+    binding = MagicMock()
+    binding.external_peer_id = external_peer_id
+    binding.state = state
+    binding.suspended_at = None
+    binding.revoked_at = None
+    return binding
+
+
+def _make_session(get_result=None, execute_result=None):
+    session = MagicMock()
+    session.get = AsyncMock(return_value=get_result)
+    if execute_result is not None:
+        session.execute = AsyncMock(return_value=execute_result)
+    return session
+
+
+def _result_mock(first):
+    scalars_mock = MagicMock(first=MagicMock(return_value=first))
+    return MagicMock(scalars=MagicMock(return_value=scalars_mock))
+
+
+@pytest.mark.asyncio
+async def test_params_defaults():
+    params = TelegramActionParams(text="hello")
+    assert params.parse_mode == "Markdown"
+    assert params.use_system_bot is True
+    assert params.account_id is None
+    assert params.connector_name is None
+    assert params.object_id is None
+
+
+@pytest.mark.asyncio
+async def test_resolve_account_by_id():
+    account = _account(account_id=5)
+    session = _make_session(get_result=account)
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
+async def test_resolve_account_by_id_rejects_cross_workspace():
+    account = _account(
+        account_id=5,
+        owner_workspace_id=99,
+        owner_user_id=uuid.uuid4(),
+    )
+    session = _make_session(get_result=account)
+
+    params = TelegramActionParams(
+        text="Hello",
+        account_id=5,
+    )
+    with pytest.raises(ValueError, match="does not belong"):
+        await _resolve_telegram_account(
+            SimpleNamespace(
+                session=session, workspace_id=42, creator_user_id=uuid.uuid4()
+            ),
+            params,
+        )
+
+
+@pytest.mark.asyncio
+async def test_resolve_account_by_id_rejects_suspended():
+    account = _account(account_id=5, suspended_at="2026-08-01")
+    session = _make_session(get_result=account)
+
+    params = TelegramActionParams(text="Hello", account_id=5)
+    with pytest.raises(ValueError, match="suspended"):
+        await _resolve_telegram_account(
+            SimpleNamespace(session=session, workspace_id=42), params
+        )
+
+
+@pytest.mark.asyncio
+async def test_resolve_system_account():
+    account = _account(account_id=1, is_system=True)
+    session = _make_session(execute_result=_result_mock(account))
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
+async def test_resolve_use_system_bot_false_without_account_id_fails():
+    session = _make_session()
+    params = TelegramActionParams(
+        text="Hello",
+        use_system_bot=False,
+    )
+    with pytest.raises(ValueError, match="Provide a Telegram account_id"):
+        await _resolve_telegram_account(
+            SimpleNamespace(session=session, workspace_id=42), params
+        )
+
+
+@pytest.mark.asyncio
+async def test_resolve_chat_id_from_binding():
+    account = _account(account_id=1)
+    binding = _binding(external_peer_id="67890")
+    session = _make_session(get_result=account, execute_result=_result_mock(binding))
+
+    params = TelegramActionParams(text="Hello", account_id=1)
+    chat_id = await _resolve_chat_id(
+        SimpleNamespace(session=session, workspace_id=42, creator_user_id=uuid.uuid4()),
+        account,
+        params,
+    )
+    assert chat_id == "67890"
+
+
+@pytest.mark.asyncio
+async def test_resolve_chat_id_missing_binding():
+    account = _account(account_id=1)
+    session = _make_session(get_result=account, execute_result=_result_mock(None))
+
+    params = TelegramActionParams(text="Hello", account_id=1)
+    with pytest.raises(ValueError, match="No Telegram chat bound"):
+        await _resolve_chat_id(
+            SimpleNamespace(
+                session=session,
+                workspace_id=42,
+                creator_user_id=uuid.uuid4(),
+            ),
+            account,
+            params,
+        )
+
+
+@pytest.mark.asyncio
+async def test_write_back_telegram_sends_message():
+    account = _account(account_id=1)
+    session = _make_session(get_result=account)
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
+    assert result["parse_mode"] == "Markdown"
+    assert result["reply_markup"] == {
+        "inline_keyboard": [[{"text": "OK", "callback_data": "ok"}]]
+    }
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
+    session = _make_session(get_result=account)
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
+    binding = _binding(external_peer_id="67890")
+    session = _make_session(get_result=account, execute_result=_result_mock(binding))
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
+
+
+@pytest.mark.asyncio
+async def test_write_back_telegram_uses_system_bot():
+    account = _account(account_id=1, is_system=True)
+    session = _make_session(execute_result=_result_mock(account))
+
+    params = TelegramActionParams(chat_id="12345", text="Hello")
+
+    send_result = MagicMock()
+    send_result.external_message_id = "77"
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
+    assert result["account_id"] == 1
+    call = adapter.send_message.call_args.kwargs
+    assert call["external_peer_id"] == "12345"
```

## nowing_backend/tests/unit/gateway/test_telegram_client.py (untracked)

```diff
diff --git a/nowing_backend/tests/unit/gateway/test_telegram_client.py b/nowing_backend/tests/unit/gateway/test_telegram_client.py
new file mode 100644
index 000000000..b3f49dcab
--- /dev/null
+++ b/nowing_backend/tests/unit/gateway/test_telegram_client.py
@@ -0,0 +1,313 @@
+from __future__ import annotations
+
+from unittest.mock import MagicMock
+
+import pytest
+from telegram.error import BadRequest, RetryAfter
+
+from app.gateway.base.adapter import PlatformSendResult
+from app.gateway.telegram.client import TelegramClient
+from app.gateway.telegram.formatting import unescape_markdown_v2
+
+
+@pytest.fixture
+def client(mocker):
+    token = "test-token"
+    client = TelegramClient(token)
+    client.bot = mocker.AsyncMock()
+    return client
+
+
+@pytest.mark.asyncio
+async def test_send_message_passes_reply_markup(client, mocker):
+    from telegram import InlineKeyboardMarkup
+
+    sent_msg = MagicMock()
+    sent_msg.message_id = 42
+    sent_msg.to_dict.return_value = {"message_id": 42}
+    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)
+
+    reply_markup = {
+        "inline_keyboard": [[{"text": "View", "callback_data": "view_run:123"}]]
+    }
+    result = await client.send_message(
+        chat_id="12345",
+        text="Hello",
+        parse_mode="Markdown",
+        reply_markup=reply_markup,
+    )
+
+    assert isinstance(result, PlatformSendResult)
+    assert result.external_message_id == "42"
+    call_kwargs = client.bot.send_message.call_args.kwargs
+    assert call_kwargs["chat_id"] == "12345"
+    assert call_kwargs["text"] == "Hello"
+    assert call_kwargs["parse_mode"] == "Markdown"
+    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)
+
+
+@pytest.mark.asyncio
+async def test_send_message_drops_invalid_reply_markup(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 7
+    sent_msg.to_dict.return_value = {"message_id": 7}
+    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)
+
+    result = await client.send_message(
+        chat_id="12345",
+        text="Hello",
+        reply_markup={"not_a_keyboard": []},
+    )
+
+    assert result.external_message_id == "7"
+    call_kwargs = client.bot.send_message.call_args.kwargs
+    assert "reply_markup" not in call_kwargs
+
+
+@pytest.mark.asyncio
+async def test_send_message_falls_back_on_bad_markdown(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 9
+    sent_msg.to_dict.return_value = {"message_id": 9}
+    client.bot.send_message = mocker.AsyncMock(
+        side_effect=[
+            BadRequest("Can't parse message text: can't find end of bold entity"),
+            sent_msg,
+        ]
+    )
+
+    result = await client.send_message(
+        chat_id="12345",
+        text="*unclosed bold",
+        parse_mode="Markdown",
+    )
+
+    assert client.bot.send_message.call_count == 2
+    assert client.bot.send_message.call_args.kwargs.get("parse_mode") is None
+    assert result.external_message_id == "9"
+
+
+@pytest.mark.asyncio
+async def test_send_message_falls_back_on_bad_reply_markup(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 11
+    sent_msg.to_dict.return_value = {"message_id": 11}
+    client.bot.send_message = mocker.AsyncMock(
+        side_effect=[
+            BadRequest("button_data_invalid"),
+            sent_msg,
+        ]
+    )
+
+    result = await client.send_message(
+        chat_id="12345",
+        text="Hello",
+        reply_markup={
+            "inline_keyboard": [
+                [{"text": "Bad", "callback_data": "bad:data:way:too:long"}]
+            ]
+        },
+    )
+
+    assert client.bot.send_message.call_count == 2
+    assert client.bot.send_message.call_args.kwargs.get("reply_markup") is None
+    assert result.external_message_id == "11"
+
+
+@pytest.mark.asyncio
+async def test_send_message_retries_after_rate_limit(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 13
+    sent_msg.to_dict.return_value = {"message_id": 13}
+    client.bot.send_message = mocker.AsyncMock(
+        side_effect=[
+            RetryAfter(1),
+            sent_msg,
+        ]
+    )
+
+    result = await client.send_message(chat_id="12345", text="Hello")
+
+    assert client.bot.send_message.call_count == 2
+    assert result.external_message_id == "13"
+
+
+@pytest.mark.asyncio
+async def test_answer_callback_query(client, mocker):
+    client.bot.answer_callback_query = mocker.AsyncMock()
+
+    await client.answer_callback_query(
+        callback_query_id="cqid",
+        text="Done",
+        show_alert=True,
+    )
+
+    client.bot.answer_callback_query.assert_awaited_once_with(
+        callback_query_id="cqid",
+        text="Done",
+        show_alert=True,
+    )
+
+
+@pytest.mark.asyncio
+async def test_edit_message_reply_markup(client, mocker):
+    from telegram import InlineKeyboardMarkup
+
+    client.bot.edit_message_reply_markup = mocker.AsyncMock()
+
+    await client.edit_message_reply_markup(
+        chat_id="12345",
+        message_id="99",
+        reply_markup={
+            "inline_keyboard": [[{"text": "View", "callback_data": "view_run:123"}]]
+        },
+    )
+
+    call_kwargs = client.bot.edit_message_reply_markup.call_args.kwargs
+    assert call_kwargs["chat_id"] == "12345"
+    assert call_kwargs["message_id"] == 99
+    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)
+
+
+@pytest.mark.asyncio
+async def test_send_message_passes_url_button(client, mocker):
+    from telegram import InlineKeyboardMarkup
+
+    sent_msg = MagicMock()
+    sent_msg.message_id = 21
+    sent_msg.to_dict.return_value = {"message_id": 21}
+    client.bot.send_message = mocker.AsyncMock(return_value=sent_msg)
+
+    reply_markup = {
+        "inline_keyboard": [[{"text": "Open", "url": "https://nowing.net"}]]
+    }
+    result = await client.send_message(
+        chat_id="12345",
+        text="Click below",
+        reply_markup=reply_markup,
+    )
+
+    assert result.external_message_id == "21"
+    call_kwargs = client.bot.send_message.call_args.kwargs
+    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)
+    assert call_kwargs["reply_markup"].inline_keyboard[0][0].url == "https://nowing.net"
+
+
+@pytest.mark.asyncio
+async def test_edit_message_passes_reply_markup(client, mocker):
+    from telegram import InlineKeyboardMarkup
+
+    edited_msg = MagicMock()
+    edited_msg.message_id = 55
+    edited_msg.to_dict.return_value = {"message_id": 55}
+    client.bot.edit_message_text = mocker.AsyncMock(return_value=edited_msg)
+
+    markup = {"inline_keyboard": [[{"text": "Updated", "callback_data": "ok"}]]}
+    result = await client.edit_message(
+        chat_id="12345",
+        message_id="99",
+        text="Updated text",
+        reply_markup=markup,
+    )
+
+    assert result.external_message_id == "55"
+    call_kwargs = client.bot.edit_message_text.call_args.kwargs
+    assert call_kwargs["chat_id"] == "12345"
+    assert call_kwargs["message_id"] == 99
+    assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)
+
+
+@pytest.mark.asyncio
+async def test_edit_message_keeps_username_chat_id(client, mocker):
+    edited_msg = MagicMock()
+    edited_msg.message_id = 77
+    edited_msg.to_dict.return_value = {"message_id": 77}
+    client.bot.edit_message_text = mocker.AsyncMock(return_value=edited_msg)
+
+    result = await client.edit_message(
+        chat_id="@nowing_channel",
+        message_id="42",
+        text="Updated",
+    )
+
+    assert result.external_message_id == "77"
+    call_kwargs = client.bot.edit_message_text.call_args.kwargs
+    assert call_kwargs["chat_id"] == "@nowing_channel"
+
+
+@pytest.mark.asyncio
+async def test_send_message_rejects_non_numeric_reply_to(client):
+    with pytest.raises(
+        ValueError, match="reply_to_message_id must be a numeric string"
+    ):
+        await client.send_message(
+            chat_id="12345", text="Hello", reply_to_message_id="abc"
+        )
+
+
+@pytest.mark.asyncio
+async def test_edit_message_rejects_non_numeric_message_id(client):
+    with pytest.raises(ValueError, match="message_id must be a numeric string"):
+        await client.edit_message(chat_id="12345", message_id="abc", text="Updated")
+
+
+@pytest.mark.asyncio
+async def test_edit_message_inline_returns_ok(client, mocker):
+    client.bot.edit_message_text = mocker.AsyncMock(return_value=True)
+
+    result = await client.edit_message(
+        inline_message_id="inline-1",
+        text="Updated",
+    )
+
+    assert result.external_message_id == "inline-1"
+    assert result.raw_response == {"ok": True}
+
+
+@pytest.mark.asyncio
+async def test_send_message_unescapes_markdown_v2_on_parse_error(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 15
+    sent_msg.to_dict.return_value = {"message_id": 15}
+    client.bot.send_message = mocker.AsyncMock(
+        side_effect=[
+            BadRequest("Can't parse message text: can't find end of bold entity"),
+            sent_msg,
+        ]
+    )
+
+    text = r"*hello \*world"
+    await client.send_message(
+        chat_id="12345",
+        text=text,
+        parse_mode="MarkdownV2",
+    )
+
+    assert client.bot.send_message.call_count == 2
+    fallback_call = client.bot.send_message.call_args.kwargs
+    assert fallback_call.get("parse_mode") is None
+    assert fallback_call["text"] == unescape_markdown_v2(text)
+
+
+@pytest.mark.asyncio
+async def test_send_message_does_not_unescape_markdown_on_parse_error(client, mocker):
+    sent_msg = MagicMock()
+    sent_msg.message_id = 17
+    sent_msg.to_dict.return_value = {"message_id": 17}
+    client.bot.send_message = mocker.AsyncMock(
+        side_effect=[
+            BadRequest("Can't parse message text: can't find end of bold entity"),
+            sent_msg,
+        ]
+    )
+
+    text = "*unclosed bold"
+    await client.send_message(
+        chat_id="12345",
+        text=text,
+        parse_mode="Markdown",
+    )
+
+    fallback_call = client.bot.send_message.call_args.kwargs
+    assert fallback_call.get("parse_mode") is None
+    assert fallback_call["text"] == text
```

