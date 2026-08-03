# Edge Case Hunter Findings — Telegram Gateway

- **Unvalidated `int()` casts in edit/reply-markup flows crash on usernames or string IDs** — `MAJOR` (`nowing_backend/app/gateway/telegram/client.py:56`, `:92-93`, `:184-185`)
  `send_message` casts `reply_to_message_id` with `int()` without validation, and `edit_message` / `edit_message_reply_markup` cast both `chat_id` and `message_id` to `int()`. If `external_peer_id` is a channel username (e.g. `@channel`), `external_message_id` is an inline message id, or a caller passes a non-numeric string, the call raises a local `ValueError` before ever reaching Telegram. This is also inconsistent with `send_message`, which accepts string `chat_id`s/usernames but cannot edit those same messages because the edit paths force integers.

- **Only one `RetryAfter` retry is attempted** — `MAJOR` (`nowing_backend/app/gateway/telegram/client.py:153-160`)
  `_send_once` catches `RetryAfter`, sleeps once, and then makes exactly one more attempt. If Telegram returns a second `RetryAfter` on that attempt, the exception is not caught and propagates, failing the send/edit. Under burst traffic or overlapping rate-limit buckets a single retry is not enough to recover gracefully.

- **Long-poll `get_updates` loop has no internal exception recovery** — `MAJOR` (`nowing_backend/app/gateway/telegram/client.py:196-206`)
  The `while True` block calls `bot.get_updates` and iterates the result with no `try/except`. A transient `NetworkError`, `Unauthorized`, `Conflict`, `TimedOut`, or a malformed `Update` object will terminate the async generator. The BYO supervisor in `byo_long_poll.py` will restart the runner, but each crash re-fetches from the last persisted `offset` and can re-deliver uncommitted updates; a malformed update that reaches `adapter.parse_inbound` can restart the same crash loop because the offset is never advanced past it.

- **Streaming translator overwrites and duplicates chunks when a flush exceeds 4,096 UTF-16 units** — `CRITICAL` (`nowing_backend/app/gateway/telegram/translator.py:71-97`)
  When `chunk_message(self._buffer)` returns more than one chunk, `_flush` sends all chunks except the last as new messages and then sets `self._buffer = chunks[-1]`. It then edits the *last newly-sent* message to contain `chunks[-1]`, so the second-to-last chunk is overwritten and lost. Because `self._buffer` is never cleared, the next flush re-chunks the entire accumulated text and re-sends the prefix, producing duplicate messages and spam.

- **Final flush re-edits identical content, risking `BadRequest: message is not modified`** — `MAJOR` (`nowing_backend/app/gateway/telegram/translator.py:62-63`, `:71-97`)
  `_flush` never clears `self._buffer` after a successful non-final flush, so the final `_flush(final=True)` at the end of `translate` re-formats and re-sends or re-edits the same text. If the content did not change, `edit_message_text` raises `BadRequest: message is not modified`, which is not handled by the markdown/keyboard fallbacks and can abort the stream; it also wastes network calls on every stream finish.

- **Markdown-to-plaintext fallback sends already-escaped text as plain, exposing literal backslashes** — `MAJOR` (`nowing_backend/app/gateway/telegram/client.py:119-131`, `nowing_backend/app/gateway/telegram/translator.py:99-116`)
  The translator always escapes the buffer with `escape_markdown_v2` before sending. If the client (or the legacy `retry_plaintext_on_bad_markdown` wrapper) falls back by dropping `parse_mode` to `None`, it re-sends the same escaped text, so users see literal backslash characters before reserved symbols. There is no `self._plaintext_mode` toggle and no unescape step, so the fallback does not actually produce clean plain text.

- **Markdown/keyboard fallbacks rely on fragile English error substrings** — `MAJOR` (`nowing_backend/app/gateway/telegram/client.py:120-139`)
  `_send_with_fallbacks` decides whether to drop `parse_mode` or `reply_markup` by searching for `"can't parse"`, `"button"`, `"reply_markup"`, and `"inline keyboard"` in the lower-cased `BadRequest` message. If Telegram rephrases the error, returns a localized message, or uses an error code without those words, the fallback is skipped and the call is re-raised. Error-based recovery should be anchored on exception types or stable error codes, not free-form strings.

- **Malformed or unexpected payloads can crash the long-poll runner and cause a retry loop** — `MAJOR` (`nowing_backend/app/gateway/telegram/adapter.py:22-44`)
  `parse_inbound` assumes `raw_payload` is a `dict` and initializes `event_kind = "message"`. If the payload is a list, `None`, or an update type like `chat_member` or `channel_post`, the code either raises an `AttributeError`/`KeyError` or returns a misleading blank `message` event. In `runner.py` this exception bubbles up, the BYO supervisor restarts, and because the offset is advanced only after a successful yield, the same bad update is re-fetched and re-crashed until it is manually skipped.

- **`callback_query` silently wins over `message` / `edited_message` in the same payload** — `MINOR` (`nowing_backend/app/gateway/telegram/adapter.py:30-32`)
  After extracting `message` and `edited_message`, `parse_inbound` checks `callback_query` and immediately returns a callback event. A synthetic, test, or misrouted payload containing both a `message` and a `callback_query` will drop the message entirely. Real Telegram updates contain only one top-level key, but the parser should not have this hidden precedence.

- **Invalid `reply_markup` is swallowed by a bare `Exception` catch with no diagnostic payload** — `MINOR` (`nowing_backend/app/gateway/telegram/client.py:25-35`)
  `_build_inline_keyboard_markup` catches all `Exception` instances, logs a generic warning, and returns `None`. This can mask non-keyboard bugs (for example a `TypeError` from a PTB version mismatch) and the log does not include the offending `reply_markup` dict, making it hard to debug malformed keyboards. It also does not distinguish between `InlineKeyboardMarkup.de_json` returning `None` and raising.

- **Empty inbound message text becomes `None` in `_parse_message`** — `NIT` (`nowing_backend/app/gateway/telegram/adapter.py:77`)
  `text = message.get("text") or message.get("caption")` returns `None` when `text` is an empty string and `caption` is missing. This discards the fact that the message text was intentionally empty and can cause downstream handlers to treat an empty message as having no content.

- **Telegram length and empty-text limits are not validated before calls** — `MINOR` (`nowing_backend/app/gateway/telegram/client.py:43-102`, `:162-173`)
  `send_message`, `edit_message`, and `answer_callback_query` do not guard against empty text or exceed Telegram's limits (4,096 UTF-16 units for messages, 200 characters for callback answer text). The resulting `BadRequest` is not covered by the markdown/keyboard fallbacks, so the caller receives an unhandled exception.

- **Streaming translator state is not protected against concurrent `translate` calls** — `MINOR` (`nowing_backend/app/gateway/telegram/translator.py:38-70`)
  `TelegramStreamTranslator` stores shared mutable state (`self._buffer`, `self._external_message_ids`, `self._last_flush_at`) and awaits network calls inside `_flush`. If `translate` is invoked from multiple tasks concurrently, appends to `_buffer`, edits to `_external_message_ids`, and `_last_flush_at` updates can interleave, producing garbled, duplicate, or lost messages. The class is designed for a single stream consumer but does not enforce it.
