# Review Spec: Telegram Inline Keyboard & Callback Query

## Scope
Review the implementation of Story 11.7 (Inline Keyboard) and Story 11.8 (Callback Query Handling) for Nowing Telegram gateway.

## Files under review
- `nowing_backend/app/gateway/telegram/client.py`
- `nowing_backend/app/gateway/telegram/adapter.py`
- `nowing_backend/tests/unit/gateway/test_telegram_client.py`
- `nowing_backend/tests/unit/gateway/test_telegram_adapter.py`

## Story 11.7 — Inline Keyboard in Telegram Messages

**As an** automation builder, **I want** to attach inline keyboard buttons to Telegram messages, **so that** recipients can tap buttons to view or re-run automations.

### Acceptance Criteria
- `write_back_telegram` and notifications support `reply_markup` with `inline_keyboard`.
- Buttons with `url` open a URL; buttons with `callback_data` send a `callback_query`.
- Invalid `reply_markup` falls back to message without keyboard and logs a warning.

### Technical notes
- Extend `TelegramClient.send_message` with param `reply_markup: dict | None`; convert dict to `InlineKeyboardMarkup`.
- Extend `TelegramAdapter.send_message` with `reply_markup` to forward to client.

## Story 11.8 — Callback Query Handling

**As a** Telegram user, **I want** button taps to be processed by the Nowing bot, **so that** I can take actions without typing commands.

### Acceptance Criteria
- `TelegramAdapter.parse_inbound` recognizes `callback_query` and normalizes `event_kind="callback_query"` with `callback_data`.
- Callback query is persisted to `ExternalChatInboundEvent` and dispatched by `inbox_processor`.
- `view_run:` callback fetches run details and edits or sends a message.
- `rerun:` callback triggers the automation and confirms with a message.
- Bot calls `answerCallbackQuery` to remove the loading spinner.

### Technical notes
- Add `TelegramClient.answer_callback_query(callback_query_id, text, show_alert)` and `edit_message_reply_markup(chat_id, message_id, reply_markup)`.
- Update `TelegramAdapter.parse_inbound` to extract `callback_query` (chat id from `message.chat.id` or `inline_message_id`); update `inbox_processor` dispatch.
