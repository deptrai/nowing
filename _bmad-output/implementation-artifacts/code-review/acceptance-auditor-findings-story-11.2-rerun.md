# Acceptance Auditor Findings for Story 11.2

The diff **fully satisfies** all acceptance criteria (AC-1 through AC-8) and addresses all previously identified review findings. All AC are verified:

## Verified Acceptance Criteria

### AC-1 — Action đăng ký với đúng params - VERIFIED
- Evidence: `params.py` shows `parse_mode: str | None = Field(default="Markdown")` and `use_system_bot: bool = Field(default=True)`
- Evidence: `__init__.py` imports `write_back_telegram`
- Evidence: `definition.py` registers the action with correct params

### AC-2 — Resolve bot token - VERIFIED
- Evidence: `invoke.py` implements `_resolve_telegram_account` with proper logic: checks `account_id` first, then `use_system_bot`, then fails with clear error
- Evidence: Checks for suspended accounts
- Evidence: Verifies account belongs to workspace or user
- Evidence: Raises clear error when no token can be resolved

### AC-3 — Resolve default `chat_id` - VERIFIED
- Evidence: `invoke.py` implements `_resolve_chat_id` with workspace-scoped binding lookup
- Evidence: Queries `ExternalChatBinding` with workspace_id, user_id, state=BOUND, and suspension/revocation checks
- Evidence: Raises clear error when no binding found

### AC-4 — Fallback khi Markdown hoặc reply_markup lỗi - VERIFIED
- Evidence: `client.py` implements `_send_with_fallbacks` with targeted error detection
- Evidence: Defines `_is_parse_mode_error` and `_is_keyboard_error` helpers
- Evidence: Handles parse mode errors with MarkdownV2 unescaping
- Evidence: Handles keyboard errors
- Evidence: Provides generic fallback with logging

### AC-5 — Step fail không kill run - VERIFIED
- Evidence: `invoke.py` raises `ValueError` for failures, which executor handles as step failure
- Evidence: Factory uses `model_construct` to avoid re-validation
- Evidence: Error messages are clear and specific

### AC-6 — Builder UI - VERIFIED
- Evidence: `builder-schema.ts` adds `"write_back_telegram"` to `writeBackActionSchema`
- Evidence: Defines `telegramWriteBackParamsSchema` with all required fields
- Evidence: Adds it to `writeBackParamsSchema` union
- Evidence: `task-item.tsx` adds "Send Telegram message" to `ACTION_OPTIONS`
- Evidence: Sets default params with `parse_mode: "Markdown"` and `use_system_bot: true`
- Evidence: Renders form fields: message text, chat_id, parse mode select, reply_markup JSON input
- Evidence: Hides connector_name field for Telegram

### AC-7 — Serialize/Deserialize đúng - VERIFIED
- Evidence: `builder-schema.ts` implements `writeBackParamsFromParams` for Telegram
- Evidence: Handles parse_mode conversion ("none" → null)
- Evidence: Tests verify round-trip and parse_mode handling

### AC-8 — Test coverage - VERIFIED
- Evidence: `test_write_back_telegram.py` provides comprehensive unit tests for resolve account/chat, system bot, cross-workspace rejection, suspension checks, and message sending
- Evidence: `test_telegram_client.py` provides tests for reply_markup, fallback on bad markdown/keyboard, rate limit retry, and MarkdownV2 unescaping
- Evidence: `test_formatting.py` tests `unescape_markdown_v2`
- Evidence: `builder-schema.test.ts` tests builder schema round-trip

## Dev Notes Compliance - VERIFIED
- Action self-registers through `definition.py` imported in `__init__.py`
- `invoke.py` implements correct resolve logic per spec
- `invoke.py` scopes binding query by workspace_id
- `params.py` adds `connector_name` and `object_id` as ignored fields for round-trip compatibility
- Error messages match spec requirements
- Fallback logic logs warnings before dropping parse_mode or reply_markup

## Additional Improvements Beyond Spec
The diff also includes Telegram gateway enhancements that support the write-back functionality (reply_markup, fallbacks, callback query handling). All changes are appropriate and support the story requirements without violating any constraints.

**Status: PASS - All acceptance criteria verified, all dev notes addressed.**
