# Blind Hunter findings — Telegram gateway review

- **Non-message updates are emitted as `event_kind="message"`** — `MAJOR` — `nowing_backend/app/gateway/telegram/adapter.py:22-44`  
  `parse_inbound` now defaults `event_kind` to `"message"` and only overwrites it when it finds `edited_message`. Any update that is neither `message`, `edited_message`, nor `callback_query` (e.g. `my_chat_member`, `chat_member`, `poll`, `channel_post`) is therefore produced as a `ParsedInboundEvent` with `event_kind="message"`, `external_peer_id=None`, and `text=None`. A quick reproduction parsing a `my_chat_member` payload returned `message None None`. This regression corrupts the inbound event stream, metrics, and any downstream logic that trusts `event_kind` to decide how to handle an update.

- **`edit_message` and `edit_message_reply_markup` force `chat_id` through `int()`** — `MAJOR` — `nowing_backend/app/gateway/telegram/client.py:92-94` and `nowing_backend/app/gateway/telegram/client.py:184-186`  
  Both edit paths call `int(chat_id)` (and `int(message_id)`), while `send_message` keeps `chat_id` as the string it received. The Telegram Bot API accepts `chat_id` as `int | str`, including `@channelusername`, and `TelegramAdapter.edit_message` declares `external_peer_id: str`. A non-numeric identifier or channel username passed to edit will raise `ValueError` before the request is ever sent, and the public interface is now inconsistent between send and edit.

- **Callback queries are parsed but never answered** — `MAJOR` — `nowing_backend/app/gateway/telegram/client.py:162-173` and `nowing_backend/app/gateway/telegram/adapter.py:174-185`  
  The diff adds `answer_callback_query` to both `TelegramClient` and `TelegramAdapter`, but a search of `nowing_backend/app` shows no caller. Telegram requires `answerCallbackQuery` to dismiss the loading state after a user clicks an inline button; without it, the client shows a "Bot is not responding" error even if the bot later sends a message. The feature is therefore half-integrated: callback payloads are received and routed, but the required acknowledgement is missing.

- **`edit_message_reply_markup` bypasses rate-limit and keyboard fallbacks** — `MINOR` — `nowing_backend/app/gateway/telegram/client.py:175-187`  
  Unlike `send_message` and `edit_message`, `edit_message_reply_markup` does not go through `_send_with_fallbacks`. It will not sleep and retry on `RetryAfter`, and it will not drop and retry on a `BadRequest` caused by an invalid inline keyboard. Under rate limits or malformed keyboards this method fails while the sibling methods would recover, which is a surprising inconsistency for a new public API.

- **`_build_inline_keyboard_markup` silently swallows all exceptions and drops the keyboard** — `MINOR` — `nowing_backend/app/gateway/telegram/client.py:31-35`  
  The helper catches the broad `Exception` around `InlineKeyboardMarkup.de_json` and returns `None` after logging only `exc`. A malformed dict, a missing `inline_keyboard` key, or a wrong type is therefore silently discarded, so the bot can send a message without the intended interactive buttons and the underlying configuration error is hidden in a warning log.

- **New `reply_markup` parameters are not declared in the abstract adapter interface** — `MINOR` — `nowing_backend/app/gateway/telegram/adapter.py:140-172` vs `nowing_backend/app/gateway/base/adapter.py:39-58`  
  `TelegramAdapter.send_message` and `edit_message` add `reply_markup: dict | None = None`, but `BasePlatformAdapter.send_message` and `edit_message` do not. Callers using the base interface cannot pass keyboards, and the method signatures diverge from the shared contract, making the code harder to maintain and extend to other platforms.

- **Legacy `retry_plaintext_on_bad_markdown` still wraps `edit_message` after the client gained its own fallback** — `NIT` — `nowing_backend/app/gateway/telegram/client.py:209-217` and `nowing_backend/app/gateway/telegram/translator.py:138-144`  
  The client now handles bad-markdown fallback inline, yet `TelegramStreamTranslator._edit_text` still uses `retry_plaintext_on_bad_markdown`, which only matches `"can't parse entities"` and mutates the caller's `kwargs` dict. This is redundant and can lead to double or mismatched retries now that `TelegramClient.edit_message` performs the same recovery.
