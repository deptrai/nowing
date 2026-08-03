# Acceptance Auditor Findings — Story 11.2

## Method

- Story spec: `11-2-telegram-write-back-and-builder.md`
- Diff reviewed: `code-review/diff-story-11.2.md`
- Audited acceptance criteria: AC-1 … AC-8, plus relevant Dev Notes.

## Findings

### 1. `parse_mode` default is `None` instead of required `"Markdown"`
- **Violates:** AC-1 (params & defaults)
- **Evidence:** `nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py:19`
  ```python
  parse_mode: str | None = Field(default=None)
  ```
  AC-1 requires `parse_mode` default `Markdown`; the builder UI (AC-6) also lists `Markdown` as the default in the select. Current default means messages are sent without any parse mode unless the caller explicitly sets it.

### 2. `use_system_bot` default is `False` instead of required `true`
- **Violates:** AC-1 (params & defaults), AC-2 (system-bot resolution path)
- **Evidence:** `nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py:25-27`
  ```python
  use_system_bot: bool = Field(
      default=False,
      description="Use the workspace/system shared Telegram bot instead of a BYO account.",
  )
  ```
  AC-1 explicitly requires `use_system_bot` default `true`. This default changes the resolution priority and can cause unexpected failures for new steps.

### 3. `use_system_bot=false` without `account_id` falls back to any workspace BYO account instead of failing immediately
- **Violates:** AC-2 (resolve bot token), Dev Notes ("Khi `use_system_bot=false` và không có `account_id`, ... cần align AC")
- **Evidence:** `nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py:47-60`
  ```python
  result = await session.execute(
      select(ExternalChatAccount).where(
          ExternalChatAccount.platform == ExternalChatPlatform.TELEGRAM,
          ExternalChatAccount.owner_workspace_id == ctx.workspace_id,
      )
  )
  accounts = list(result.scalars().all())
  if not accounts:
      raise ValueError(f"No Telegram account found for workspace {ctx.workspace_id}")
  if len(accounts) > 1:
      raise ValueError(
          "Multiple Telegram accounts found; provide account_id or set use_system_bot"
      )
  return accounts[0]
  ```
  The AC/Dev Note priority is `account_id → system bot → fail`. The diff still auto-picks a single workspace BYO account, and only fails if there are zero or multiple accounts. This is the legacy behavior the spec explicitly asked to remove.

### 4. Missing error message matching the spec when no token/chat
- **Violates:** AC-2, AC-3 (fail with clear message), Dev Notes (Error Handling)
- **Evidence:**
  - `invoke.py:55` — `raise ValueError(f"No Telegram account found for workspace {ctx.workspace_id}")`
  - `invoke.py:58-59` — `raise ValueError("Multiple Telegram accounts found; provide account_id or set use_system_bot")`
  - `invoke.py:83-85` — `raise ValueError(f"No active Telegram binding found for creator {ctx.creator_user_id} on account {account.id}")`
  AC-2/AC-3 and the Error Handling section call for messages like *“Provide account_id or set use_system_bot=true”* and *“No Telegram chat bound to this user or workspace”*. The current messages are technically clear but do not match the required wording/patterns from the spec.

### 5. `write_back_telegram` raises unhandled `ValueError` instead of returning `status=failed`
- **Violates:** AC-5 (step fail does not kill run), Dev Notes ("Trả lỗi rõ ràng, không raise exception ra ngoài executor")
- **Evidence:**
  - `nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py:30,32,44,55,58,71,83,96` (all `raise ValueError`)
  - `nowing_backend/app/automations/actions/builtin/write_back_telegram/factory.py:15-17`
    ```python
    async def handle(params: dict[str, Any]) -> dict[str, Any]:
        validated = TelegramActionParams.model_validate(params)
        return await write_back_telegram(ctx, validated)
    ```
  The handler does not catch validation or resolution failures and return `{"status": "failed", "error": ...}`. Unless the executor wraps **all** thrown exceptions, these `ValueError`s will propagate and can abort the run instead of triggering `on_failure` steps.

### 6. Builder UI and schema completely absent from the diff
- **Violates:** AC-6 (Builder UI), AC-7 (serialize/deserialize)
- **Evidence:** The diff contains 14 files; none are in `nowing_web/`. The required files `nowing_web/lib/automations/builder-schema.ts` and `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx` are not modified.
- **Impact:**
  - No `telegramWriteBackParamsSchema` in `writeBackParamsSchema`.
  - No `write_back_telegram` in `writeBackActionSchema` / `WRITE_BACK_ACTIONS`.
  - No `writeBackParamsFromParams` / `writeBackParamsToParams` mapping.
  - No `ACTION_OPTIONS` or `defaultWriteBackParams` entry for Telegram.
  - No form fields for message text, chat-id hint, or parse-mode select (`Markdown`/`MarkdownV2`/`none`).
  - No raw JSON support for `account_id`, `use_system_bot`, `reply_markup`.
  - `provider: "telegram"` is never set in `writeBackParams`.

### 7. No builder-schema round-trip tests
- **Violates:** AC-8 (test coverage for builder schema round-trip)
- **Evidence:** `nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py:1-186` is the only test file in the diff. There is no `builder-schema.test.ts` or any frontend test covering `writeBackParamsFromParams` / `writeBackParamsToParams` for `write_back_telegram`.

### 8. No integration test for the real Telegram send path
- **Violates:** AC-8 ("integration test gửi message qua mock Telegram API")
- **Evidence:** `test_write_back_telegram.py` only unit-tests by mocking `TelegramAdapter` and `account_token` (e.g., `with patch(...)` blocks around file lines 91-98 and 164-171). No integration test exercises `TelegramClient.send_message`/`edit_message` with a mocked PTB `Bot` or a mock HTTP server.

### 9. Fallback test coverage missing
- **Violates:** AC-4 (fallback Markdown/keyboard), AC-8
- **Evidence:** No tests for `_send_with_fallbacks`, `BadRequest` with/without parse mode, or malformed `reply_markup` in `test_write_back_telegram.py`. The client-side logic is only covered implicitly in the mocked-adapter unit tests.

### 10. `TelegramClient._send_with_fallbacks` unconditionally unescapes MarkdownV2 text
- **Violates:** AC-4 ("drop `parse_mode` → unescape MarkdownV2 → thử lại")
- **Evidence:** `nowing_backend/app/gateway/telegram/client.py` `_send_with_fallbacks` block:
  ```python
  if had_parse_mode and kwargs.get("parse_mode"):
      ...
      for key in ("text",):
          if isinstance(call_kwargs.get(key), str):
              call_kwargs = {
                  **call_kwargs,
                  key: unescape_markdown_v2(call_kwargs[key]),
              }
  ```
  The code unescapes `text` whenever `parse_mode` was present, even if the original parse mode was `Markdown` (not `MarkdownV2`). This can corrupt `Markdown`-escaped text on a non-V2 BadRequest.

### 11. `TelegramClient._send_with_fallbacks` drops parse_mode on any `BadRequest`
- **Violates:** AC-4 (fallback should only handle Markdown/keyboard errors)
- **Evidence:** `nowing_backend/app/gateway/telegram/client.py` `_send_with_fallbacks`:
  ```python
  except BadRequest as exc:
      if had_parse_mode and kwargs.get("parse_mode"):
          ...
  ```
  The fallback triggers for **every** `BadRequest` (chat not found, message too long, etc.), not just entity-parsing errors. The code comment explicitly admits this: *“a small number of unrelated BadRequest calls may be retried once or twice”* and wastes API calls. AC-4 describes the fallback as a response to bad Markdown or malformed `reply_markup`.

### 12. `reply_to_message_id` retained in `TelegramActionParams` though not in AC-1
- **Violates:** AC-1 (param list)
- **Evidence:** `nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py:20`
  ```python
  reply_to_message_id: str | None = Field(default=None)
  ```
  AC-1 lists only `text`, `chat_id`, `parse_mode`, `reply_markup`, `account_id`, `use_system_bot`. `reply_to_message_id` is not part of the agreed public param surface and, while optional, is a deviation from the specified contract.

### 13. Existing `retry_plaintext_on_bad_markdown` removed without preserving the exact string-based markdown check
- **Violates:** AC-4 ("`TelegramClient._send_with_fallbacks` (client.py:119)" expectation), Dev Notes
- **Evidence:** `diff-story-11.2.md:541-548` removes:
  ```python
  async def retry_plaintext_on_bad_markdown(call, *args, **kwargs) -> PlatformSendResult:
      try:
          return await call(*args, **kwargs)
      except BadRequest as exc:
          if "can't parse entities" not in str(exc).lower():
              raise
          kwargs["parse_mode"] = None
          return await call(*args, **kwargs)
  ```
  The new `_send_with_fallbacks` no longer checks the error text/string for `"can't parse entities"` before dropping parse mode, relying only on exception type. This deviates from the original intent and can mis-fire fallbacks.

### 14. No frontend lint/type-check changes
- **Violates:** AC-8 ("Biome + tsc cho `task-item.tsx`, `builder-schema.ts`"), AC-6, AC-7
- **Evidence:** The diff does not touch `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx` or `nowing_web/lib/automations/builder-schema.ts`. No frontend tests, no tsc/biome artifacts are included.

## Summary

The backend action skeleton and Telegram client fallback/reply_markup plumbing are largely present, but the diff **does not implement the builder UI/schema (AC-6/AC-7)**, has **wrong parameter defaults (AC-1)**, and has **account-resolution and error-handling logic that does not fully match the story (AC-2, AC-5, Dev Notes)**. Test coverage (AC-8) is also incomplete, especially for the frontend round-trip and integration paths. The story is **not accepted** as-is.
