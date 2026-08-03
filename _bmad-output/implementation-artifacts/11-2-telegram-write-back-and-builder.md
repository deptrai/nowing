---
baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15
baseline_branch: develop
story_key: 11-2-telegram-write-back-and-builder
status: done
---

# Story 11.2: Telegram Write-Back, Builder UI & Chat Resolution

**Story ID:** 11.2  
**Epic:** 11 — Telegram Automation & Bot  
**Title:** Telegram Write-Back, Builder UI & Chat Resolution  
**Status:** ready-for-dev  
**Priority:** HIGH  
**Requirements:** FR-TELE-3 (`write_back_telegram`), FR-TELE-6 (UI builder), FR-TELE-7 (rate limit & error handling)  
**Architecture:** AD-2 (Alembic nếu schema mới), AD-3 (action tự đăng ký — không phải scraper), AD-15 (gateway external dependency), AD-16 (license boundary), AD-17 (Celery)  
**Dependencies:** Story 11.1 (shared `TelegramAdapter`, `ExternalChatBinding`); `write_back_telegram` backend đã có skeleton (`nowing_backend/app/automations/actions/builtin/write_back_telegram/`).

---

## 1. Goal

Hoàn thiện action `write_back_telegram` để automation step có thể gửi custom Telegram message, tự động resolve bot token và default chat dựa trên `ExternalChatAccount`/`ExternalChatBinding`, đồng thời thêm action "Send Telegram message" vào automation builder.

**Non-goal:** Không xây UI cho inline keyboard trong builder (có thể dùng raw JSON mode); không thay đổi cơ chế registry của action.

---

## 2. User Story

> As an automation builder,  
> I want a "Send Telegram message" action that authors a custom message and automatically resolves the right bot and chat,  
> so that I can push results or alerts to Telegram without writing JSON or looking up chat IDs.

---

## 3. Acceptance Criteria

### AC-1 — Action đăng ký với đúng params
**Given** backend action registry,  
**When** import `app.automations.actions.builtin`,  
**Then** `write_back_telegram` available với params: `text` (required), `chat_id` (optional), `parse_mode` (default `Markdown`), `reply_markup` (optional), `account_id` (optional), `use_system_bot` (default `true`).

### AC-2 — Resolve bot token
**Given** step chạy,  
**When** `account_id` được cung cấp,  
**Then** dùng BYO `ExternalChatAccount` đó.  
**When** `account_id` null và `use_system_bot=true`,  
**Then** dùng system Telegram account (`is_system_account=true`).  
**When** không có token hoặc `use_system_bot=false` và không có BYO,  
**Then** fail step với message rõ ràng.

### AC-3 — Resolve default `chat_id`
**Given** bot token đã resolve,  
**When** `chat_id` null,  
**Then** tìm active `ExternalChatBinding` của automation creator (`created_by_user_id`) cho account đã resolve.  
**When** không tìm thấy,  
**Then** fail step với "No Telegram chat bound to this user or workspace".

### AC-4 — Fallback khi Markdown hoặc reply_markup lỗi
**Given** text chứa Markdown lỗi hoặc `reply_markup` malformed,  
**When** gửi,  
**Then** `TelegramClient._send_with_fallbacks` (`client.py:119`) tự động: drop `parse_mode` → unescape MarkdownV2 → thử lại; drop `reply_markup` → thử lại; log warning.

### AC-5 — Step fail không kill run
**Given** thiếu token/chat hoặc lỗi Telegram,  
**When** step fail,  
**Then** trả về `status=failed`, `error` rõ ràng, và executor tiếp tục `on_failure` steps nếu có trong `definition.execution.on_failure` (`executor.py:131`).

### AC-6 — Builder UI
**Given** automation builder,  
**When** user chọn "Send Telegram message",  
**Then** form hiển thị: message text (required), chat ID (optional, hint "leave blank to use your paired Telegram chat"), parse mode select (`Markdown`/`MarkdownV2`/`none`, default `Markdown`).  
**And** `writeBackParams` có `provider: "telegram"`.  
**And** raw JSON mode cho phép `account_id`, `use_system_bot`, `reply_markup`.

### AC-7 — Serialize/Deserialize đúng
**Given** builder form với action `write_back_telegram`,  
**When** lưu automation,  
**Then** params serializes thành backend `write_back_telegram` step.  
**When** load lại,  
**Then** `hydrateForm` khôi phục đúng fields.

### AC-8 — Test coverage
**Given** code mới,  
**Then** có unit test cho resolve account/chat, fallback Markdown/keyboard, builder schema round-trip, integration test gửi message qua mock Telegram API.

---

## 4. Tasks / Subtasks

- [x] Backend params & defaults (AC #1)
  - [x] Cập nhật `TelegramActionParams` (`params.py`): `parse_mode` default `"Markdown"`, `use_system_bot` default `true`
  - [x] Đảm bảo `reply_markup` vẫn là `dict | None`
- [x] Backend resolve logic (AC #2, #3)
  - [x] `invoke.py`: `_resolve_telegram_account` ưu tiên `account_id` → system bot nếu `use_system_bot=true` → fail
  - [x] `_resolve_chat_id`: fallback từ creator binding
  - [x] Trả lỗi rõ ràng, không raise exception ra ngoài executor
- [x] Action registration (AC #1)
  - [x] `definition.py`/`factory.py`/`__init__.py` hiện đã tồn tại — verify đăng ký đúng
  - [x] Đảm bảo `app/automations/actions/builtin/__init__.py` import `write_back_telegram`
- [x] Builder schema (AC #6, #7)
  - [x] Thêm `"write_back_telegram"` vào `writeBackActionSchema` (`builder-schema.ts:33`)
  - [x] Thêm `telegramWriteBackParamsSchema` vào union `writeBackParamsSchema` (`builder-schema.ts:80`)
  - [x] Cập nhật `writeBackParamsFromParams` (`builder-schema.ts:487`) để parse `write_back_telegram`
  - [x] Cập nhật `writeBackParamsToParams` (trong `builder-schema.ts`) để serialize
  - [x] Thêm `"write_back_telegram"` vào `WRITE_BACK_ACTIONS` (`builder-schema.ts:538`)
- [x] Builder UI (AC #6, #7)
  - [x] Thêm action option vào `ACTION_OPTIONS` (`task-item.tsx:34`)
  - [x] Thêm `defaultWriteBackParams` cho Telegram (`task-item.tsx:49`)
  - [x] Render fields cho `write_back_telegram` trong `task-item.tsx` (text, chat_id hint, parse mode select)
- [x] Tests (AC #8)
  - [x] Unit test `tests/unit/automations/actions/builtin/test_write_back_telegram.py` mở rộng cho resolve/fallback
  - [x] Unit test `tests/unit/web/lib/automations/builder-schema.test.ts` (hoặc tương đương) cho round-trip
  - [x] Biome + tsc cho `task-item.tsx`, `builder-schema.ts`

### Review Findings

#### patch (high)
- [x] [Review][Patch] `BasePlatformAdapter` widened with Telegram-only `reply_markup` — remove from base and other adapters; keep only on `TelegramAdapter.send_message`/`edit_message` `[base/adapter.py:47,59]` `[discord/adapter.py:111,129]` `[slack/adapter.py:99,116]` `[whatsapp/adapter_baileys.py:56,74]` `[whatsapp/adapter_cloud.py:70,87]`
- [x] [Review][Patch] Builder form `connector_name`/`object_id` vs `TelegramActionParams.extra="forbid"` — add `connector_name` and `object_id` as optional ignored fields to `TelegramActionParams` and to `telegramWriteBackParamsSchema` `[params.py:11,20-21]` `[builder-schema.ts]`
- [x] [Review][Patch] Builder UI/schema for `write_back_telegram` completely absent `[nowing_web/lib/automations/builder-schema.ts, nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx]`
- [x] [Review][Patch] `parse_mode` default is `None` instead of `"Markdown"` `[params.py:19]`
- [x] [Review][Patch] `use_system_bot` default is `False` instead of `True` `[params.py:25-28]`
- [x] [Review][Patch] `use_system_bot=false` without `account_id` falls back to workspace BYO instead of failing `[invoke.py:47-60]`
- [x] [Review][Patch] Explicit `account_id` not verified against current workspace/user `[invoke.py:27-33]`
- [x] [Review][Patch] Account/binding resolution ignores suspension/revocation state `[invoke.py:35-60,74-79]`
- [x] [Review][Patch] Chat binding resolution not scoped by workspace `[invoke.py:74-79]`
- [x] [Review][Patch] `_send_with_fallbacks` unescapes MarkdownV2 text regardless of original parse_mode `[client.py:148-153]` / `[formatting.py:22]`

#### patch (medium)
- [x] [Review][Patch] `_send_with_fallbacks` drops `parse_mode` on any `BadRequest` instead of targeted parse/keyboard errors `[client.py:138-172]`
- [x] [Review][Patch] `_build_inline_keyboard_markup` swallows all exceptions `[client.py:32-40]`
- [x] [Review][Patch] `reply_to_message_id` cast to `int` without validation `[client.py:61]`
- [x] [Review][Patch] `factory.py` redundant validation and `with_retries` retries deterministic errors `[factory.py:15-17]`
- [x] [Review][Patch] Test coverage shallow, missing resolve/fallback/builder round-trip `[tests/unit/automations/actions/builtin/test_write_back_telegram.py]`
- [x] [Review][Patch] Success result omits `parse_mode` and `reply_markup` `[invoke.py:108-114]`

#### patch (low)
- [x] [Review][Patch] Error messages do not match spec wording `[invoke.py:55,58-59,83-84]`
- [x] [Review][Patch] `reply_to_message_id` is in params though not in AC-1 `[params.py:20]`

#### patch (re-run — low)
- [x] [Review][Patch] `writeBackParamsFromParams` casts an unknown `parse_mode` string to the narrow builder type without validation; added a guard to fall back to `"none"` `[builder-schema.ts:558-563]`

#### defer
- [x] [Review][Defer] `edit_message` assumes `msg.message_id` for inline edits `[client.py:114-117]` — deferred to Story 11.3
- [x] [Review][Defer] `edit_message`/`edit_message_reply_markup` cast `message_id` to `int` without validation `[client.py:100-105,220-225]` — deferred to Story 11.3
- [x] [Review][Defer] `get_updates` catches all exceptions and retries forever `[client.py:244-257]` — deferred to Story 11.3
- [x] [Review][Defer] Malformed update serialization resets offset to 1 `[client.py:267]` — deferred to Story 11.3
- [x] [Review][Defer] `get_updates` ignores `RetryAfter.retry_after` and sleeps fixed 5s `[client.py:251-257]` — deferred to Story 11.3
- [x] [Review][Defer] `write_back_telegram` does not chunk long messages `[invoke.py:100-106]` — deferred to Story 11.1 chunking helper

---

## 5. Dev Notes

### Architecture & License
- **AD-3 không áp dụng:** `write_back_telegram` là built-in action, không phải scraper capability. Action self-registers through `app/automations/actions/builtin/*/definition.py` imported in `app/automations/actions/builtin/__init__.py`.
- **AD-15:** `TelegramAdapter`/`TelegramClient` là external HTTP dependency đã có; `write_back_telegram` gọi trực tiếp `adapter.send_message`.
- **AD-16:** Code nằm trong `app/automations/actions/builtin/write_back_telegram/` (Apache-2.0); không động `app/proprietary/`.
- **AD-2:** Không cần schema mới nếu dùng JSONB `reply_markup` trên params; `TelegramActionParams` là Pydantic model đã lưu trong `definition_snapshot`/`step_results`.

### Current State (verified from code)
- `write_back_telegram` đã được đăng ký (`app/automations/actions/builtin/write_back_telegram/definition.py:10-17`); `app/automations/actions/builtin/__init__.py:12` import nó.
- `TelegramActionParams` hiện có:
  - `chat_id: str | None` (default None)
  - `text: str` (required)
  - `parse_mode: str | None` (default None) → **cần đổi thành default `"Markdown"`**
  - `reply_to_message_id: str | None` (default None)
  - `reply_markup: dict | None` (default None)
  - `account_id: int | None` (default None)
  - `use_system_bot: bool` (default `False`) → **cần đổi thành default `true`**
- `invoke.py` (`write_back_telegram/invoke.py:22-60`) đã resolve theo `account_id` → `use_system_bot` → workspace BYO accounts, nhưng:
  - Khi `use_system_bot=false` và không có `account_id`, nó query `owner_workspace_id` thay vì fail ngay; cần align AC.
  - `_resolve_chat_id` (`invoke.py:63-86`) đã lấy từ creator binding theo `creator_user_id` — tốt.
- `builder-schema.ts` chưa có `write_back_telegram` (`writeBackActionSchema:33-39`, `writeBackParamsSchema:80-85`, `WRITE_BACK_ACTIONS:538-543`).
- `task-item.tsx` chưa có Telegram (`ACTION_OPTIONS:34-40`, `defaultWriteBackParams:49-99`); chỉ có Notion/Linear/Jira/Slack.
- `TelegramClient.send_message` (`client.py:48-77`) đã hỗ trợ `parse_mode` và `reply_markup` và fallback `BadRequest`.

### Technical Details
- **Resolve account logic (cần sửa):**
  ```python
  if params.account_id is not None:
      account = await session.get(ExternalChatAccount, params.account_id)
      if account is None or account.platform != TELEGRAM:
          raise ValueError(...)
      return account
  if params.use_system_bot:
      account = await get_or_create_system_telegram_account(session)
      # hoặc select system account
      return account
  raise ValueError("Provide account_id or set use_system_bot=true")
  ```
  ponytail: giữ nguyên cơ chế hiện có, chỉ đổi default và đơn giản hóa fallback cuối.
- **Resolve chat_id:**
  - Nếu `params.chat_id` tồn tại → dùng.
  - Nếu `ctx.creator_user_id` None → fail.
  - Query `ExternalChatBinding` where `account_id=account.id`, `user_id=creator_user_id`, `state=BOUND`.
- **Builder params mapping:**
  - `writeBackParams` → backend step `params`:
    - `text` → `text`
    - `chat_id` → `chat_id`
    - `parse_mode` → `parse_mode`
    - `provider` bị loại bỏ ở `buildWriteBackParams` (`builder-schema.ts:287-291`).
- **Raw JSON mode:** `writeBackParams` object với `provider: "telegram"` sẽ validate qua `writeBackParamsSchema`. Các trường advanced (`account_id`, `use_system_bot`, `reply_markup`) nằm trong `params` nếu user edit raw JSON.

### Error Handling
- Thiếu token: `ValueError("Telegram account has no usable token")` → step failed.
- Thiếu chat: `ValueError("No active Telegram binding found...")` → step failed.
- `BadRequest` từ Telegram: client fallback plain text / no keyboard; nếu vẫn lỗi, step fail.

### Testing
- **Backend:** chạy `pytest tests/unit/automations/actions/builtin/test_write_back_telegram.py`.
- **Frontend:** `pnpm tsc --noEmit` từ `nowing_web`, `pnpm exec biome check` cho `builder-schema.ts` và `task-item.tsx`.
- **Integration:** tạo automation với `write_back_telegram` step, chạy, xác nhận message gửi đến mock chat.

---

## 6. Project Structure Notes

```
nowing_backend/app/automations/actions/builtin/write_back_telegram/
  __init__.py            # đã có, import definition
  definition.py          # đã có, register action
  factory.py             # đã có, build_handler
  params.py              # cập nhật defaults
  invoke.py              # cập nhật resolve logic, fallback

nowing_web/lib/automations/builder-schema.ts
  writeBackActionSchema
  telegramWriteBackParamsSchema
  writeBackParamsSchema
  writeBackParamsFromParams / writeBackParamsToParams / buildWriteBackParams
  WRITE_BACK_ACTIONS

nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx
  ACTION_OPTIONS
  defaultWriteBackParams
  render fields cho Telegram
```

---

## 7. References

- Epic / AC gốc: `_bmad-output/planning-artifacts/epics.md` §Story 11.2
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-2, AD-3, AD-15, AD-16, AD-17
- Sprint proposal: `_bmad-output/planning-artifacts/sprint-change-proposal-telegram-2026-08-03.md` §Phase 2
- Architecture review: `_bmad-output/planning-artifacts/epic-11-architecture-review-2026-08-03.md` §3.3 (connector name vs account_id/use_system_bot)
- Telegram action backend: `nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py`, `params.py`, `definition.py`, `factory.py`
- Builder: `nowing_web/lib/automations/builder-schema.ts`, `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`
- Telegram client: `nowing_backend/app/gateway/telegram/client.py`

---

## Dev Agent Record

### Agent Model Used
Claude / Sonnet 4 — story context engine.

### Completion Notes
- Backend skeleton đã có; chủ yếu cần chỉnh defaults, hoàn thiện resolve, thêm builder schema/UI.

### File List (target for implementation)
- `nowing_backend/app/automations/actions/builtin/write_back_telegram/params.py`
- `nowing_backend/app/automations/actions/builtin/write_back_telegram/invoke.py`
- `nowing_web/lib/automations/builder-schema.ts`
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`
- `nowing_backend/tests/unit/automations/actions/builtin/test_write_back_telegram.py`

### Baseline
- `baseline_branch: develop`
- `baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15`
