# Code Review Triage — Story 11.2: Telegram Write-Back, Builder UI & Chat Resolution

**Review spec:** `_bmad-output/implementation-artifacts/11-2-telegram-write-back-and-builder.md`  
**Diff:** `_bmad-output/implementation-artifacts/code-review/diff-story-11.2.md`  
**Findings files:**
- `blind-hunter-findings-story-11.2.md`
- `edge-case-hunter-findings-story-11.2.json`
- `acceptance-auditor-findings-story-11.2.md`

## Triaged findings

### patch (19)

#### high

1. **`BasePlatformAdapter` widened with Telegram-only `reply_markup`** `[patch][high]` `[base/adapter.py:47,59]`  
   No generic caller passes `reply_markup` to a `BasePlatformAdapter`; only `TelegramStreamTranslator` and `write_back_telegram` use it, and both hold a `TelegramAdapter`. Best practice: remove `reply_markup` from the abstract `send_message`/`edit_message` signatures and from Discord/Slack/WhatsApp adapters; keep it as an optional param on `TelegramAdapter` only.

2. **Builder form emits `connector_name`/`object_id` but `TelegramActionParams` forbids extras** `[patch][high]` `[task-item.tsx:218-231,419-430]` / `[params.py:11]`  
   The builder form always emits `connector_name` and `object_id` for every write-back action. Other `write_back_*` Pydantic models include these two optional fields and ignore them when not relevant. Best practice: add `connector_name` and `object_id` as optional nullable fields to `TelegramActionParams` and to the `telegramWriteBackParamsSchema`; the Telegram backend can ignore them or map `connector_name` to account selection later.


3. **Builder UI/schema for `write_back_telegram` completely absent** `[patch][high]`  
   The diff contains no `nowing_web` changes. `builder-schema.ts` and `task-item.tsx` still lack `write_back_telegram`, `telegramWriteBackParamsSchema`, `writeBackParamsFromParams`/`writeBackParamsToParams` mapping, and `WRITE_BACK_ACTIONS` entry. Violates AC-6, AC-7, AC-8.

4. **`parse_mode` default is `None` instead of `"Markdown"`** `[patch][high]` `[params.py:19]`  
   `TelegramActionParams.parse_mode` defaults to `None`. AC-1 and AC-6 require `Markdown` default.

5. **`use_system_bot` default is `False` instead of `True`** `[patch][high]` `[params.py:25-28]`  
   AC-1 and AC-2 require `use_system_bot` default `true`.

6. **`use_system_bot=false` without `account_id` falls back to workspace BYO** `[patch][high]` `[invoke.py:47-60]`  
   AC-2 priority is `account_id → system bot → fail`. The final branch currently queries the workspace's BYO accounts and auto-picks one if exactly one exists. Should fail immediately instead.

7. **Explicit `account_id` not verified against current workspace/user** `[patch][high]` `[invoke.py:27-33]`  
   `_resolve_telegram_account` fetches by primary key and only checks `platform == TELEGRAM`. It does not enforce `owner_workspace_id == ctx.workspace_id` or user ownership, allowing cross-workspace token misuse.

8. **Account/binding resolution ignores suspension/revocation state** `[patch][high]` `[invoke.py:35-60,74-79]`  
   `_resolve_telegram_account` does not filter `suspended_at.is_(None)`; `_resolve_chat_id` does not filter `suspended_at`/`revoked_at` on `ExternalChatBinding`. Existing code such as `byo_long_poll.py:66,118` does filter these fields.

9. **Chat binding resolution not scoped by workspace** `[patch][high]` `[invoke.py:74-79]`  
   `_resolve_chat_id` filters by `account_id`, `user_id`, `state == BOUND`, but not `workspace_id`. `ExternalChatBinding` has a `workspace_id` column, so a binding from another workspace could be resolved.

10. **`_send_with_fallbacks` unescapes MarkdownV2 text regardless of original parse_mode** `[patch][high]` `[client.py:148-153]` / `[formatting.py:22]`  
    `unescape_markdown_v2` strips backslashes before *any* character. When `_send_with_fallbacks` drops `parse_mode`, it unescapes even if the original `parse_mode` was `Markdown` (not V2) or `HTML`, corrupting literal backslashes in the plain-text fallback.

#### medium

11. **`_send_with_fallbacks` drops `parse_mode` on any `BadRequest`** `[patch][medium]` `[client.py:138-172]`  
    The fallback triggers for every `BadRequest` (chat not found, message too long, etc.), not just entity-parsing errors. The removed `retry_plaintext_on_bad_markdown` helper previously checked `"can't parse entities"` before retrying. This wastes 1-2 API calls and can mask real errors.

12. **`_build_inline_keyboard_markup` swallows all exceptions** `[patch][medium]` `[client.py:32-40]`  
    It catches `Exception` around `InlineKeyboardMarkup.de_json` and silently returns `None`. It does not distinguish malformed user JSON from library/internal errors and never surfaces the real cause.

13. **`reply_to_message_id` cast to `int` without validation** `[patch][medium]` `[client.py:61]`  
    `TelegramClient.send_message` calls `int(reply_to_message_id)`. A non-numeric string raises an opaque `ValueError` at send time. `TelegramActionParams.reply_to_message_id` is an unvalidated `str | None`.

14. **`factory.py` performs redundant validation and `with_retries` will retry deterministic errors** `[patch][medium]` `[factory.py:15-17]` / `[step.py:63-69]` / `[retries.py:24-27]`  
    `step.py` already validates resolved params against `TelegramActionParams` before building the handler. `factory.py` re-validates inside the handler, and `with_retries` retries any exception (including deterministic `ValueError`s for missing chat/account). This wastes retry attempts.

15. **Test coverage is shallow and misses required scenarios** `[patch][medium]` `[tests/unit/automations/actions/builtin/test_write_back_telegram.py]`  
   Only 5 unit tests. Missing: account not found, non-Telegram account, no/multiple workspace accounts, missing binding, default `parse_mode`/`use_system_bot` values, Markdown/keyboard fallback, builder schema round-trip, and integration test with a mock Telegram API.

16. **Success return omits `parse_mode` and `reply_markup`** `[patch][medium]` `[invoke.py:108-114]`  
   The result dict only contains `provider`, `account_id`, `chat_id`, `message_id`, `text`. The parse mode and keyboard that were actually sent are not surfaced, limiting downstream edit/reply workflows.

#### low

17. **Error messages do not match the wording in the spec** `[patch][low]` `[invoke.py:55,58-59,83-84]`  
   Current messages are technically clear but not aligned with the spec's wording such as *"Provide account_id or set use_system_bot=true"* and *"No Telegram chat bound to this user or workspace"*. Minor but affects consistency.

18. **`reply_to_message_id` is in `TelegramActionParams` though not in AC-1** `[patch][low]` `[params.py:20]`  
   AC-1 lists `text`, `chat_id`, `parse_mode`, `reply_markup`, `account_id`, `use_system_bot`. Either remove `reply_to_message_id` from the public surface or update AC-1 to include it.

### defer (6)

19. **`TelegramClient.edit_message` assumes `msg.message_id` for inline edits** `[defer]` `[client.py:114-117]`  
   `edit_message_text` returns `True` when `inline_message_id` is used, so `msg.message_id` will raise `AttributeError`. This path is used by Story 11.3 callback/rerun flows, not `write_back_telegram`. Deferred to Story 11.3 review.

20. **`edit_message` and `edit_message_reply_markup` cast `message_id` to `int` without validation** `[defer]` `[client.py:100-105,220-225]`  
   Same as `reply_to_message_id` but for edit paths. Not exercised by Story 11.2 `send_message`; deferred to Story 11.3.

21. **`get_updates` catches all exceptions and retries forever with a fixed 5s sleep** `[defer]` `[client.py:244-257]`  
   `Unauthorized` or `InvalidToken` will loop indefinitely. Not part of Story 11.2 scope; belongs to Story 11.3 long-poll/command handling. Deferred.

22. **Malformed update serialization can reset the long-poll offset to 1** `[defer]` `[client.py:267]`  
   `next_offset = getattr(update, "update_id", 0) + 1` defaults to `1` when `update_id` is missing, causing duplicate/skipped updates. Belongs to Story 11.3.

23. **`get_updates` ignores `RetryAfter.retry_after` and sleeps fixed 5s** `[defer]` `[client.py:251-257]`  
   The `RetryAfter` exception carries a wait time but `get_updates` catches the broad `Exception` and always sleeps 5s. Belongs to Story 11.3.

24. **Long messages are not chunked in `write_back_telegram`** `[defer]` `[invoke.py:100-106]`  
   `TelegramActionParams.text` can exceed 4096 UTF-16 code units; the action does not call `chunk_message` and will fail. Story 11.1 covers notification message chunking; `write_back_telegram` should reuse that helper in a follow-up.

### dismiss (1)

25. **Removed `retry_plaintext_on_bad_markdown` helper** `[dismiss]`  
   Functionally replaced by `_send_with_fallbacks`; the targeted error-string behavior is already captured in finding #11. Dismissed as duplicate.

## Counts

- 0 `decision-needed`
- 19 `patch` (9 high, 8 medium, 2 low)
- 6 `defer`
- 1 `dismiss`

## Verdict

**CHANGES REQUESTED.** The diff does not satisfy Story 11.2 acceptance criteria as-is. The two most critical gaps are the missing builder UI/schema and the incorrect parameter defaults/account resolution logic. Security scoping (workspace, suspension, revocation) is also incomplete. Several shared `TelegramClient` fallbacks need hardening before the action can reliably send formatted messages and keyboards.
