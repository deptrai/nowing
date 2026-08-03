# Blind Hunter Findings — Story 11.2

Findings are based on the implementation diff (`diff-story-11.2.md`) and the story spec (`11-2-telegram-write-back-and-builder.md`).

- **Builder UI and schema for `write_back_telegram` are entirely absent from the diff.**
  - Evidence: `diff-story-11.2.md` contains no changes for `nowing_web/lib/automations/builder-schema.ts` or `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`. The current `builder-schema.ts` still omits `write_back_telegram` from `writeBackActionSchema` (lines 33-39), the `writeBackParamsSchema` union (lines 80-85), `writeBackParamsFromParams` (lines 487-536), and `WRITE_BACK_ACTIONS` (lines 538-543); `task-item.tsx` still omits it from `ACTION_OPTIONS` and `defaultWriteBackParams` (lines 34-99). This violates AC-6 and AC-7.

- **`TelegramActionParams.parse_mode` defaults to `None` instead of `"Markdown"`.**
  - Evidence: `nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py:19` reads `parse_mode: str | None = Field(default=None)`. AC-1 and AC-6 require the default to be `"Markdown"`.

- **`TelegramActionParams.use_system_bot` defaults to `False` instead of `True`.**
  - Evidence: `params.py:25-28` reads `use_system_bot: bool = Field(default=False, ...)`. AC-1 and AC-2 require the default to be `true`.

- **Account resolution falls back to workspace BYO accounts when `use_system_bot=False` and no `account_id` is supplied, instead of failing immediately.**
  - Evidence: `write_back_telegram/invoke.py:47-60` queries `ExternalChatAccount.owner_workspace_id == ctx.workspace_id` in the final branch. AC-2 says this branch must fail with a clear message; the story’s own dev notes also flag this as needing alignment.

- **An explicit `account_id` is not verified to belong to the current workspace or user, allowing cross-workspace account misuse.**
  - Evidence: `_resolve_telegram_account` (`invoke.py:27-33`) fetches by primary key and only checks `platform == ExternalChatPlatform.TELEGRAM`; it does not enforce `owner_workspace_id == ctx.workspace_id` or user ownership.

- **Account and binding resolution ignore suspension/revocation state.**
  - Evidence: `_resolve_telegram_account` (`invoke.py:35-60`) does not filter `ExternalChatAccount.suspended_at.is_(None)`. `_resolve_chat_id` (`invoke.py:74-79`) does not filter `ExternalChatBinding.suspended_at` or `revoked_at`. Existing code such as `app/gateway/byo_long_poll.py:66,118` does filter `suspended_at.is_(None)` for account queries.

- **Chat binding resolution does not scope by workspace.**
  - Evidence: `_resolve_chat_id` (`invoke.py:74-79`) filters `account_id`, `user_id`, and `state == BOUND`, but not `ExternalChatBinding.workspace_id`. The model has `workspace_id` (`app/db.py:984-988`), so a binding from another workspace could be resolved.

- **`reply_to_message_id` is cast to `int` without validation, producing an opaque `ValueError` for bad input at send time.**
  - Evidence: `TelegramClient.send_message` (`app/gateway/telegram/client.py:61`) does `kwargs["reply_to_message_id"] = int(reply_to_message_id)`; `TelegramActionParams.reply_to_message_id` (`params.py:20`) is an unvalidated `str | None`.

- **The Markdown fallback unconditionally unescapes MarkdownV2 text regardless of the original `parse_mode`, stripping any backslash-prefixed character.**
  - Evidence: `client.py:148-153` calls `unescape_markdown_v2(call_kwargs["text"])` after dropping `parse_mode`; `app/gateway/telegram/formatting.py:22` implements `unescape_markdown_v2` as `re.sub(r"\\(.)", r"\1", text)`, which removes backslashes before *any* character, not just MarkdownV2 reserved ones. This can corrupt literal backslashes in the plain-text fallback.

- **Fallback ordering drops `parse_mode` before `reply_markup` even when the keyboard may be the real cause of `BadRequest`.**
  - Evidence: `client.py:136-172` always tries the parse-mode drop + text unescape first and only drops `reply_markup` on the next `BadRequest`. The `ponytail` comment at `client.py:132-134` admits this is type-based, not string-based, and can waste 1-2 API calls.

- **The fallback logic no longer distinguishes Telegram entity-parsing errors from other `BadRequest`s, masking real errors and wasting calls.**
  - Evidence: `client.py:136-172` triggers parse-mode and keyboard retries on *any* `BadRequest`. The removed `retry_plaintext_on_bad_markdown` helper (diff lines 541-548) previously checked `if "can't parse entities" not in str(exc).lower(): raise` before retrying, which was a more targeted fallback.

- **`TelegramClient.get_updates` catches all exceptions (including invalid token / unauthorized) and retries forever with a fixed 5-second sleep.**
  - Evidence: `client.py:244-257` uses a bare `except Exception:` and `await asyncio.sleep(5); continue` with no maximum retry count and no special handling for `Unauthorized` or `InvalidToken`. This can loop indefinitely on non-transient failures.

- **Malformed update serialization can reset the long-poll offset to 1, causing duplicate or skipped updates.**
  - Evidence: `client.py:267` sets `next_offset = getattr(update, "update_id", 0) + 1` when `update.to_dict()` raises. If `update_id` is missing it defaults to `0`, so the next poll starts from offset `1` instead of the current `next_offset`.

- **`_build_inline_keyboard_markup` swallows all exceptions, hiding programming errors and silently discarding user keyboards.**
  - Evidence: `client.py:32-40` uses `except Exception as exc:` around `InlineKeyboardMarkup.de_json` and returns `None`. It does not distinguish malformed user JSON from library/internal errors, and the bad keyboard is dropped without failing the step.

- **The `BasePlatformAdapter` abstract contract was widened with a Telegram-only `reply_markup` parameter, forcing every adapter to accept and ignore it.**
  - Evidence: `app/gateway/base/adapter.py:47,59` adds `reply_markup` to `send_message` and `edit_message`. `discord/adapter.py`, `slack/adapter.py`, `whatsapp/adapter_baileys.py`, and `whatsapp/adapter_cloud.py` all use `del parse_mode, reply_markup` to ignore it. This is a leaky abstraction driven by one provider.

- **The new `write_back_telegram` test suite is shallow and misses the scenarios AC-8 requires.**
  - Evidence: `tests/unit/automations/actions/builtin/test_write_back_telegram.py` has only five tests (hunk lines 851-1001) and does not cover: account not found, non-Telegram account, no/multiple workspace accounts, missing binding, default `parse_mode`/`use_system_bot` values, Markdown/keyboard fallback, builder schema round-trip, or integration against a mock Telegram API.

- **`TelegramClient.edit_message` assumes the result always has `message_id`, which is false for inline messages.**
  - Evidence: `client.py:114-117` returns `external_message_id=str(msg.message_id)`. PTB `edit_message_text` returns `True` for `inline_message_id`; `TelegramAdapter.edit_message` (`adapter.py:174-181`) can invoke this path, so `msg.message_id` will raise `AttributeError` on inline edits.

- **The builder form pattern always emits `connector_name`/`object_id`, but `TelegramActionParams` forbids extra fields.**
  - Evidence: `task-item.tsx:218-231,419-430` always collects `connector_name` and `object_id`; `builder-schema.ts:283-292` returns the whole `WriteBackParams` object minus `provider`; `params.py:11` sets `extra="forbid"` and `TelegramActionParams` has no `connector_name`/`object_id` fields. When the builder UI is eventually added, submissions will fail backend validation unless the schema is adjusted.

- **Long messages are not chunked, so a text over Telegram’s 4096-character limit will fail after both fallbacks are exhausted.**
  - Evidence: `client.py:119-188` only drops `parse_mode` and `reply_markup`; it never splits text. `app/gateway/telegram/formatting.py:51-67` provides `chunk_message`, but it is not used by the client or action.

- **`factory.py` performs redundant Pydantic validation inside the handler, so validation errors would be retried instead of failing fast.**
  - Evidence: `write_back_telegram/factory.py:14-15` calls `TelegramActionParams.model_validate(params`, but `app/automations/runtime/step.py:63-69` already validates resolved params before building the handler. If the handler re-validation fails, `app/automations/runtime/retries.py:24-27` catches `Exception` and retries, wasting attempts on a deterministic validation error.

- **The success return dict from `write_back_telegram` omits `parse_mode` and `reply_markup`, limiting downstream edit/reply workflows.**
  - Evidence: `invoke.py:108-114` returns only `provider`, `account_id`, `chat_id`, `message_id`, and `text`. The keyboard and parse mode that were actually sent are not surfaced to later steps.
