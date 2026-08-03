# Acceptance Auditor Findings — Story 11.7 & 11.8 (Telegram Inline Keyboard & Callback Query)

## Summary

The four changed files correctly add low-level `reply_markup`, `answer_callback_query`, and `edit_message_reply_markup` plumbing to `TelegramClient` and `TelegramAdapter`. However, the higher-level integration required by the acceptance criteria is missing: no outbound caller passes `reply_markup`; `inbox_processor` does not dispatch or acknowledge `callback_query` events; and the `view_run:` / `rerun:` action handlers are absent. Several regressions and edge-case gaps also exist in `parse_inbound` and the edit APIs.

## Findings

- **Telegram write-back and notification paths never pass `reply_markup` to the adapter**
  - **AC/spec point:** Story 11.7 AC1 — `write_back_telegram` and notifications support `reply_markup` with `inline_keyboard`.
  - **Severity:** MAJOR
  - **Evidence:** `nowing_backend/app/gateway/telegram/translator.py:102-126` and `:137-154`; `nowing_backend/app/gateway/telegram/commands.py:28-87`; no `write_back_telegram` action exists in `nowing_backend/app/automations/actions/builtin/`.
  - **Explanation:** `TelegramClient.send_message` and `TelegramClient.edit_message` now accept `reply_markup`, but `TelegramStreamTranslator._send_text` / `_edit_text` and all `TelegramGatewayCommands` call `send_message`/`edit_message` without it. There is also no `write_back_telegram` automation action. As a result, no agent reply, automation result, or outbound notification can actually render an inline keyboard, despite the adapter being capable.

- **`inbox_processor` does not acknowledge or dispatch `callback_query` events**
  - **AC/spec point:** Story 11.8 AC2 and AC5 — callback query is persisted/dispatched by `inbox_processor`; bot calls `answerCallbackQuery` to remove the loading spinner.
  - **Severity:** MAJOR
  - **Evidence:** `nowing_backend/app/gateway/inbox_processor.py:356-435`; `nowing_backend/app/gateway/telegram/adapter.py:174-185`; `nowing_backend/app/gateway/telegram/client.py:162-173`.
  - **Explanation:** `TelegramAdapter.answer_callback_query` and `TelegramClient.answer_callback_query` are implemented but never invoked. `inbox_processor._dispatch_inbound_event` treats a `callback_query` as ordinary text: it extracts `command_name`, resolves a binding, and calls `call_agent_for_gateway` with `parsed.text`. It never calls `answer_callback_query`, so the Telegram client will keep the loading spinner, and the user gets no explicit confirmation that the tap was processed.

- **`view_run:` and `rerun:` callback handlers are not implemented**
  - **AC/spec point:** Story 11.8 AC3 and AC4 — `view_run:` fetches run details and edits or sends a message; `rerun:` triggers the automation and confirms.
  - **Severity:** CRITICAL
  - **Evidence:** `view_run:` / `rerun:` strings only appear in test fixtures (`nowing_backend/tests/unit/gateway/test_telegram_adapter.py:37-80` and `nowing_backend/tests/unit/gateway/test_telegram_client.py:29-161`); no matching logic in `nowing_backend/app/gateway/telegram/`, `nowing_backend/app/gateway/inbox_processor.py`, or `nowing_backend/app/gateway/telegram/commands.py`.
  - **Explanation:** The only thing that happens when a user taps a button is that `TelegramAdapter._parse_callback_query` copies `callback_data` into `parsed.text`. The generic chat path then routes `view_run:123` or `rerun:456` to the agent as if it were a normal message. No code fetches run details, triggers an automation, edits an existing message, or sends a confirmation message, so the core behavior of the two acceptance criteria is missing.

- **Webhook persistence loses the callback query's originating message id**
  - **AC/spec point:** Story 11.8 AC2 — callback query is persisted to `ExternalChatInboundEvent`.
  - **Severity:** MAJOR
  - **Evidence:** `nowing_backend/app/routes/gateway_webhook_routes.py:236-247` and `:689-700`.
  - **Explanation:** The long-poll runner uses `TelegramAdapter.parse_inbound`, which correctly reads `callback_query["message"]["message_id"]`. The webhook route, however, derives `external_message_id` from `_telegram_message(payload)` (`payload["message"]` or `payload["edited_message"]`). For a `callback_query` update, `_telegram_message` returns `None`, so the persisted `external_message_id` is `None`. This makes webhook-persisted callback-query rows diverge from long-poll rows and lose the reference to the message that carries the inline keyboard.

- **Callback queries from `inline_message_id` cannot be dispatched**
  - **AC/spec point:** Story 11.8 technical note — chat id from `message.chat.id` or `inline_message_id`.
  - **Severity:** MAJOR
  - **Evidence:** `nowing_backend/app/gateway/telegram/adapter.py:99-103` and `:121-127`; `nowing_backend/app/gateway/inbox_processor.py:334-338`.
  - **Explanation:** `_parse_callback_query` sets `external_peer_id=None` when the update only contains `inline_message_id` and no `message`. `inbox_processor._dispatch_inbound_event` immediately marks such events as `IGNORED` with `last_error="missing_external_peer_id"`. This means inline-keyboard taps from inline messages are silently dropped, contradicting the technical note that the adapter should handle `inline_message_id`.

- **Unknown Telegram updates are misclassified as `message`**
  - **AC/spec point:** Story 11.7/11.8 spec intent — preserve correct `event_kind` classification.
  - **Severity:** MINOR
  - **Evidence:** `nowing_backend/app/gateway/telegram/adapter.py:22-46` (compare old `event_kind = "other"` default in the diff).
  - **Explanation:** The refactor changed the fallback `event_kind` default from `"other"` to `"message"`. Updates that are neither `message`, `edited_message`, nor `callback_query` fall through to the empty branch and are stored with `event_kind="message"`, which conflicts with the `ExternalChatEventKind.OTHER` enum and can mislead downstream routing/auditing.

- **`TelegramClient.edit_message` narrows `chat_id` to `int` and does not support `inline_message_id`**
  - **AC/spec point:** Story 11.8 technical note — `edit_message_reply_markup(chat_id, message_id, reply_markup)`; plus `inline_message_id` handling in `parse_inbound`.
  - **Severity:** MINOR
  - **Evidence:** `nowing_backend/app/gateway/telegram/client.py:90-98` and `:175-187`; `nowing_backend/app/gateway/telegram/adapter.py:187-198`.
  - **Explanation:** Both `edit_message` and `edit_message_reply_markup` cast `chat_id` to `int` and accept only `chat_id`/`message_id`. This breaks editing messages addressed by channel username (`@channel`) and, more importantly, cannot edit the markup of messages sent via `inline_message_id`, even though `parse_inbound` explicitly extracts and stores `inline_message_id` in metadata.

- **`edit_message_reply_markup` has no API-rejection fallback for bad markup**
  - **AC/spec point:** Story 11.7 AC3 — invalid reply_markup falls back to message without keyboard and logs a warning.
  - **Severity:** MINOR
  - **Evidence:** `nowing_backend/app/gateway/telegram/client.py:175-187`.
  - **Explanation:** Unlike `send_message` and `edit_message`, `edit_message_reply_markup` is not wrapped by `_send_with_fallbacks`. If Telegram rejects the markup (for example, `button_data_invalid`), the call raises instead of logging a warning and retrying without the keyboard. This is inconsistent with the graceful fallback behavior implemented for the send/edit paths.

- **Tests do not cover `url` buttons or `edit_message` with `reply_markup`**
  - **AC/spec point:** Story 11.7 AC1 and AC2 — `reply_markup` with `inline_keyboard`; buttons with `url` open a URL and buttons with `callback_data` send a callback query.
  - **Severity:** NIT
  - **Evidence:** `nowing_backend/tests/unit/gateway/test_telegram_client.py` and `nowing_backend/tests/unit/gateway/test_telegram_adapter.py`.
  - **Explanation:** The new unit tests cover `send_message` with `callback_data` buttons, invalid markup fallback, `answer_callback_query`, and `edit_message_reply_markup`, but they omit `url` buttons, `edit_message` with `reply_markup`, and the adapter-level `send_message`/`edit_message` forwarding of `reply_markup`.

- **Bad-keyboard fallback relies on fragile error-message substrings**
  - **AC/spec point:** Story 11.7 AC3 — invalid reply_markup falls back and logs a warning.
  - **Severity:** NIT
  - **Evidence:** `nowing_backend/app/gateway/telegram/client.py:134-140`.
  - **Explanation:** `_send_with_fallbacks` only drops the keyboard if the `BadRequest` message (lowercased) contains `"button"`, `"reply_markup"`, or `"inline keyboard"`. This works for the tested `button_data_invalid` case, but if Telegram returns a different validation phrasing, the fallback will not trigger and the call will fail without attempting a plain-text send.
