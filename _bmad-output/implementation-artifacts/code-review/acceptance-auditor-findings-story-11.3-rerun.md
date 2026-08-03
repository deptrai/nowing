# Story 11.3 Re-run — Acceptance Auditor Findings

- **AC-1 — PASS**: `TelegramClient.send_message` and `edit_message` accept `reply_markup` dicts, coerce them to `InlineKeyboardMarkup` via `_build_inline_keyboard_markup` (`client.py:56-78, 102-104, 130-132`), and include the keyboard in the API call. `TelegramAdapter` forwards `reply_markup` for both methods (`adapter.py:148-188`).

- **AC-2 — PASS**: `_build_inline_keyboard_markup` returns `None` and logs a warning for malformed or non-dict `reply_markup` (`client.py:56-78`). `_send_with_fallbacks` detects keyboard-related `BadRequest` errors, drops `reply_markup`, and retries (`client.py:196-223`).

- **AC-3 — PASS**: `TelegramAdapter._parse_callback_query` produces a `ParsedInboundEvent` with `event_kind="callback_query"`, `text=callback_query["data"]`, `external_message_id` from `message.message_id` or `inline_message_id`, and `external_peer_id` from `message.chat.id` or `inline:{inline_message_id}` (`adapter.py:89-146`).

- **AC-4 — PASS**: `inbox_processor` dispatches callback queries to `bundle.commands.handle_callback_query`, sets `event.status=PROCESSED`, and commits (`inbox_processor.py:398-444`). The outer `process_inbound_event` marks FAILED on unhandled exceptions.

- **AC-5 — PASS**: `_handle_view_run` checks `Permission.AUTOMATIONS_READ` before fetching the run, answers the callback, and edits/sends a summary with a dashboard link (`callbacks.py:83-192`).

- **AC-6 — PASS**: `_handle_rerun` checks `Permission.AUTOMATIONS_EXECUTE` before fetching the automation, creates a transient `AutomationTrigger(type=MANUAL)`, calls `launch_run`, answers the callback, and confirms (`callbacks.py:195-332`).

- **AC-7 — PASS with caveat**: `_handle_status_command` checks permission, queries the latest `AutomationRun` for the workspace, and replies with the run summary or "No recent runs in this workspace" (`commands.py:228-267`). Unbound users are sent onboarding by `inbox_processor` (`inbox_processor.py:386-394`). Caveat: the query uses an INNER JOIN to `Automation` (`commands.py:156-164`), so a run whose automation record is missing cannot reach the orphan branch in `_format_run_summary`; this edge case still reports "No recent runs" despite the review patch claim.

- **AC-8 — PASS**: `_handle_run_command` checks permission, lists active automations when no name, looks up by name, triggers a `MANUAL` run, and replies with the required messages (`commands.py:270-368`). Bot-mention stripping and 4096-char list truncation are implemented.

- **AC-9 — FAIL**: `answer_callback_query` is not called for callback queries in unbound chats. When `binding is None`, `inbox_processor` calls `send_unbound_onboarding` and returns (`inbox_processor.py:386-394`) before reaching the callback dispatch block (`inbox_processor.py:398-444`), so Telegram's loading spinner is never dismissed. This is the same gap the spec deferred to Story 11.8, but the acceptance criterion says "mọi callback".

- **AC-10 — FAIL**: Unit tests for `/status`, `/run`, and callback dispatch exist and all 83 `tests/unit/gateway` tests pass, but the AC explicitly requires integration tests for callback dispatch, command permission, and onboarding. No `tests/integration/gateway/` directory or relevant integration tests were added.

## Verification run

- `ruff check app/gateway/telegram/client.py app/gateway/telegram/adapter.py app/gateway/telegram/commands.py app/gateway/telegram/callbacks.py app/gateway/inbox_processor.py app/gateway/base/commands.py tests/unit/gateway/test_telegram_commands.py tests/unit/gateway/test_telegram_callbacks.py` — passed.
- `pytest tests/unit/gateway -q` — 83 passed.

## Conclusion

AC-1 through AC-8 are satisfied. AC-9 and AC-10 are not fully satisfied; therefore the story is **not accepted** as-is.
