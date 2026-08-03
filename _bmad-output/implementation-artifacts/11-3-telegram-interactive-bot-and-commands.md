---
baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15
baseline_branch: develop
story_key: 11-3-telegram-interactive-bot-and-commands
status: done
---

# Story 11.3: Telegram Interactive Bot & Commands

**Story ID:** 11.3  
**Epic:** 11 — Telegram Automation & Bot  
**Title:** Telegram Interactive Bot & Commands  
**Status:** ready-for-dev  
**Priority:** MEDIUM (P1)  
**Requirements:** FR-TELE-4 (inline keyboard), FR-TELE-5 (bot commands), FR-TELE-7 (rate limit & error handling)  
**Architecture:** AD-1 (monolith module), AD-4 (permission middleware), AD-5 (Zero sync), AD-15 (gateway external dependency), AD-16 (license), AD-17 (async Celery)  
**Dependencies:** Story 11.1 (notification format + deep link), Story 11.2 (`write_back_telegram` + `reply_markup`); `app/gateway/telegram/` đã có support `reply_markup`, `callback_query`, và `view_run`/`rerun` handlers.

---

## 1. Goal

Mở rộng Telegram bot để:

- `send_message`/`edit_message` hỗ trợ `reply_markup` với inline keyboard (đã phần lớn xong).
- `parse_inbound` nhận diện `callback_query` và `inline_message_id` (đã xong).
- `inbox_processor` dispatch `view_run:` / `rerun:` callback (đã xong).
- Thêm bot commands `/status` và `/run <name>` với permission check, trigger automation, và onboarding khi chưa pair.

**Non-goal:** Không thay đổi cơ chế pairing `/start`; không thêm command mới ngoài `/status`, `/run`.

---

## 2. User Story

> As a Telegram user,  
> I want inline keyboards and `/status`, `/run` commands so I can view runs and trigger automations directly from the chat,  
> so that I can take action without opening the dashboard.

---

## 3. Acceptance Criteria

### AC-1 — Inline keyboard trong `send_message`/`edit_message`
**Given** `TelegramClient.send_message` hoặc `edit_message` được gọi với `reply_markup` dict chứa `inline_keyboard`,  
**When** gửi,  
**Then** `TelegramClient` chuyển dict thành `InlineKeyboardMarkup` (`client.py:62-64`, `client.py:92-94`) và gửi kèm bàn phím.  
**And** nút `url` mở URL, nút `callback_data` gửi `callback_query`.

### AC-2 — Invalid `reply_markup` fallback
**Given** `reply_markup` malformed hoặc không hợp lệ,  
**When** gửi,  
**Then** `_build_inline_keyboard_markup` (`client.py:26-40`) trả `None`, log warning, gửi message không keyboard.  
**And** nếu `BadRequest` do keyboard, `_send_with_fallbacks` drop `reply_markup` và retry (`client.py:162-172`).

### AC-3 — `parse_inbound` nhận diện `callback_query`
**Given** webhook payload chứa `callback_query`,  
**When** `TelegramAdapter.parse_inbound` xử lý,  
**Then** trả `ParsedInboundEvent` với `event_kind="callback_query"`, `text=callback_query.data`, `external_message_id` từ `message.message_id` hoặc `inline_message_id`, `external_peer_id` từ `message.chat.id` hoặc `inline:{inline_message_id}` (`adapter.py:89-146`).

### AC-4 — Callback persisted và dispatch
**Given** `callback_query` đến,  
**When** `inbox_processor` chạy,  
**Then** persist `ExternalChatInboundEvent`, gọi `bundle.commands.handle_callback_query` (`inbox_processor.py:398-415`), chuyển đến `app/gateway/telegram/callbacks.py`.

### AC-5 — `view_run:` callback
**Given** callback data `view_run:<run_id>`,  
**When** xử lý,  
**Then** kiểm tra `Permission.AUTOMATIONS_READ`, fetch run, gọi `answer_callback_query` để tắt spinner, edit/sends message với summary và link (`callbacks.py:67-116`).

### AC-6 — `rerun:` callback
**Given** callback data `rerun:<automation_id>`,  
**When** xử lý,  
**Then** kiểm tra `Permission.AUTOMATIONS_EXECUTE`, tạo transient `AutomationTrigger(type=MANUAL)`, gọi `launch_run` (`callbacks.py:119-185`), gọi `answer_callback_query`, reply confirm.

### AC-7 — `/status` command
**Given** user đã pair và gửi `/status`,  
**When** xử lý,  
**Then** kiểm tra `Permission.AUTOMATIONS_READ`, tìm latest `AutomationRun` trong workspace, reply name/status/finished_at/link.  
**When** không có run,  
**Then** reply "No recent runs in this workspace".  
**When** chưa pair,  
**Then** reply onboarding + pairing link.

### AC-8 — `/run <name>` command
**Given** user đã pair và gửi `/run <automation_name>`,  
**When** xử lý,  
**Then** kiểm tra `Permission.AUTOMATIONS_EXECUTE`, tìm automation active theo name trong workspace, tạo transient `AutomationTrigger(type=MANUAL)`, gọi `launch_run`, reply "Run started. You will be notified when it completes."  
**When** automation không tồn tại,  
**Then** reply "Automation '<name>' not found".  
**When** thiếu tên,  
**Then** reply danh sách automation active.  
**When** không có quyền,  
**Then** reply access-denied.

### AC-9 — `answerCallbackQuery` cho mọi callback
**Given** bất kỳ callback nào,  
**When** xử lý xong,  
**Then** `TelegramClient.answer_callback_query` được gọi để tắt loading spinner (`client.py:190-201`).

### AC-10 — Test coverage
**Given** code mới,  
**Then** có unit test cho `handle_status_command`, `handle_run_command`, integration test cho callback dispatch, command permission, và onboarding.

---

## 4. Tasks / Subtasks

- [x] TelegramClient / Adapter (AC #1, #2, #3)
  - [x] Verify `TelegramClient.send_message`/`edit_message` support `reply_markup` (`client.py:48-117`)
  - [x] Verify `_build_inline_keyboard_markup` fallback warning (`client.py:26-40`)
  - [x] Verify `_parse_callback_query` handles `inline_message_id` (`adapter.py:89-146`)
- [x] `inbox_processor` callback dispatch (AC #4)
  - [x] Đảm bảo `callback_query` dispatch tồn tại và gọi `TelegramGatewayCommands.handle_callback_query`
- [x] Callback handlers (AC #5, #6, #9)
  - [x] Verify `view_run`/`rerun` logic trong `app/gateway/telegram/callbacks.py` đúng permission
  - [x] Đảm bảo `answer_callback_query` luôn gọi trước khi return
- [x] `/status` command (AC #7)
  - [x] Thêm `handle_status_command` trong `app/gateway/telegram/commands.py`
  - [x] Thêm dispatch trong `app/gateway/inbox_processor.py` (sau `/new`, trước agent chat)
  - [x] Query latest run theo `binding.workspace_id`
- [x] `/run <name>` command (AC #8)
  - [x] Thêm `handle_run_command` trong `app/gateway/telegram/commands.py`
  - [x] Thêm dispatch trong `inbox_processor.py`
  - [x] Tìm automation theo name, tạo transient `AutomationTrigger(type=MANUAL)`, gọi `launch_run`
- [x] Base commands / bundle (AC #7, #8)
  - [x] Thêm `handle_status_command`/`handle_run_command` vào `BaseGatewayCommands` (default return False)
  - [x] Đảm bảo `TelegramGatewayCommands` override
- [x] Tests (AC #10)
  - [x] Unit tests `tests/unit/gateway/test_telegram_commands.py`
  - [x] Unit tests `tests/unit/gateway/test_telegram_callbacks.py` mở rộng
  - [x] Integration test `/status` / `/run` qua mock `ExternalChatBinding`

### Review Findings (code review 2026-08-04)

#### patch (high)
- [x] [Review][Patch] Fail-open auth when bound user cannot be loaded; command/callback handlers skip `check_permission` `[commands.py:126-132, 193-208, 267-282]` `[callbacks.py:90-98, 138-146]`
- [x] [Review][Patch] `/run` with no argument and `/run <name>` enumerate/probe automations before `AUTOMATIONS_EXECUTE` check `[commands.py:239-282]`
- [x] [Review][Patch] Callback handlers do not catch `check_permission` or `launch_run` failures, so the Telegram spinner may stay `[callbacks.py:76-173]` `[inbox_processor.py:398-415]`

#### patch (medium)
- [x] [Review][Patch] Callback handlers fetch run/automation before permission check, leaking existence before 403 `[callbacks.py:76-98, 128-146]`
- [x] [Review][Patch] `inbox_processor` callback dispatch lacks `try/finally` to guarantee `answer_callback_query` on handler error `[inbox_processor.py:398-415]`
- [x] [Review][Patch] `_handle_run_command` catches `launch_run` failure and sends raw exception text to user `[commands.py:290-301]`
- [x] [Review][Patch] `/run` active-automation list has no length guard and can exceed Telegram 4096-char limit `[commands.py:156-167, 249-253]`
- [x] [Review][Patch] Tests mock `check_permission`/`launch_run` and do not exercise fail-open auth, permission denial, or `send_message`/`launch_run` failure paths `[tests/unit/gateway/test_telegram_commands.py]`

#### patch (low)
- [x] [Review][Patch] Dashboard run link is a relative path, not a clickable URL in Telegram `[commands.py:105-117]` `[callbacks.py:20-21, 57-59]`
- [x] [Review][Patch] Bot mention not stripped from the `/run` automation-name argument `[commands.py:236-239, 256-265]`
- [x] [Review][Patch] Wrong type hint for `user_id` in `_load_user` (`int | None` vs UUID) `[commands.py:120]`
- [x] [Review][Patch] Orphaned latest run with missing automation is reported as "No recent runs" `[commands.py:147-153, 210-216]`
- [x] [Review][Patch] Confirmation `send_message` after a successful `launch_run` is unguarded; a send failure marks the event `FAILED` and may cause a retry/duplicate run `[commands.py:303-307]`

#### defer
- [x] [Review][Defer] Group/inline `callback_query` without a binding can fall through to onboarding and never answers the callback — pre-existing in `inbox_processor` callback handling, deferred to Story 11.8
- [x] [Review][Defer] No idempotency / duplicate-run prevention for rapid `/run` or `rerun` invocations — requires rate-limit design, deferred to Story 11.8
- [x] [Review][Defer] `view_run`/`rerun` not additionally scoped to `binding.workspace_id` — `check_permission` already enforces workspace membership; explicit scoping can be added later if desired

#### dismiss
- [x] [Review][Dismiss] Missing `external_peer_id` silently marks event `PROCESSED` — `inbox_processor` already ignores/answers events with no peer before reaching the command handler

### Review Findings (re-run 2026-08-04)

*Note: Blind Hunter layer failed with rate-limit error; triage is based on Acceptance Auditor and Edge Case Hunter only.*

#### patch (high)
- [x] [Review][Patch] AC-9: `answer_callback_query` is not called for `callback_query` in an unbound chat; Telegram spinner stays `[inbox_processor.py:386-394]`
- [x] [Review][Patch] AC-10: missing integration tests for callback dispatch, command permission, and onboarding
- [x] [Review][Patch] Unbound or group/inline `callback_query` without a binding falls through to onboarding and never answers the callback `[inbox_processor.py:366-394, 398-444]` `[commands.py:91-113]`

#### patch (medium)
- [x] [Review][Patch] `/status` and `/run` command handlers do not catch `adapter.send_message` failures on reply paths `[commands.py:228-267, 270-368]`
- [x] [Review][Patch] `/status` and `/run` do not reject `SUSPENDED` bindings `[inbox_processor.py:160-169]` `[commands.py:228-267, 270-368]` `[callbacks.py:83-331]`
- [x] [Review][Patch] `_active_automations_for_workspace` is unbounded and builds the full list before truncating `[commands.py:172-183, 204-225]`

#### patch (low)
- [x] [Review][Patch] `/run` with a bot-mention-only argument returns a confusing "not found" error instead of the active-automation list `[commands.py:280-285, 319-327]`
- [x] [Review][Patch] Orphan-run branch in `_format_run_summary` is unreachable because `_latest_run_for_workspace` inner-joins `Automation` `[commands.py:153-169, 120-134]`
- [x] [Review][Patch] `_handle_view_run` fallback `send_message` for `edit_message` failures does not work for inline `external_peer_id` `[callbacks.py:154-170]`

#### defer
- [x] [Review][Defer] Callback handlers do not additionally scope `run_id`/`automation_id` to `binding.workspace_id` — `check_permission` already enforces workspace membership; explicit resource scoping can be added later
- [x] [Review][Defer] Group chat callback queries authorize any member as the bound user; Telegram user identity is not checked against `binding.user_id` — requires group-callback design, deferred to Story 11.8
- [x] [Review][Defer] No rate limit or idempotency on `/run` and `rerun` — requires rate-limit/token design, deferred to Story 11.8
- [x] [Review][Defer] `inbox_processor` can re-dispatch an event while it is already `PROCESSING` — requires row-level state-machine fix, deferred to Story 11.8

---

## 5. Dev Notes

### Architecture & License
- **AD-4:** `/status` và `/run` phải gọi `check_permission(..., Permission.AUTOMATIONS_READ / AUTOMATIONS_EXECUTE)` (`app/utils/rbac.py:129`). `AuthContext.session(user)` từ `ExternalChatBinding.user`.
- **AD-15:** Telegram API là external dependency; mọi gọi đi qua `TelegramClient`, đã retry `RetryAfter`.
- **AD-17:** `launch_run` enqueue `automation_run_execute` Celery task, không chạy sync trong command handler.
- **AD-16:** Code trong `app/gateway/telegram/` Apache-2.0.

### Current State (verified from code)
- `TelegramClient.send_message` đã nhận `reply_markup` và `_send_with_fallbacks` fallback khi Markdown/keyboard lỗi (`client.py:48-188`).
- `TelegramClient.edit_message`, `edit_message_reply_markup`, `answer_callback_query` đã tồn tại (`client.py:79-233`).
- `TelegramAdapter.send_message`, `edit_message`, `edit_message_reply_markup`, `answer_callback_query` đã forward xuống client (`adapter.py:148-220`).
- `_parse_callback_query` nhận `inline_message_id` và `message.chat.id` (`adapter.py:89-146`).
- `inbox_processor` dispatch `callback_query` tới `bundle.commands.handle_callback_query` (`inbox_processor.py:398-415`).
- `app/gateway/telegram/callbacks.py` đã implement `_handle_view_run` và `_handle_rerun` với permission check, transient `AutomationTrigger(type=TriggerType.MANUAL)`, `launch_run`, và `answer_callback_query` (`callbacks.py:1-239`).
- `inbox_processor` hiện xử lý `/start`, `/help`, `/new` (`inbox_processor.py:357-436`); **chưa có `/status` và `/run`**.
- `TelegramGatewayCommands` (`commands.py:92-136`) chỉ có `handle_start_command`, `handle_help_command`, `send_unbound_onboarding`, `handle_callback_query`.
- `BaseGatewayCommands` (`base/commands.py:14-41`) chưa có `handle_status_command`/`handle_run_command`.

### Technical Details
- **Command dispatch trong `inbox_processor`:**
  Thêm sau block `/new` (`inbox_processor.py:425-436`):
  ```python
  if cmd == "/status":
      handled = await bundle.commands.handle_status_command(
          session=session, adapter=adapter, event=parsed, binding=binding
      )
      if handled:
          event.status = ExternalChatEventStatus.PROCESSED
          await session.commit()
          return

  if cmd == "/run":
      handled = await bundle.commands.handle_run_command(
          session=session, adapter=adapter, event=parsed, binding=binding
      )
      if handled:
          event.status = ExternalChatEventStatus.PROCESSED
          await session.commit()
          return
  ```
  ponytail: cần binding đã resolved ở trên; nếu binding None thì `inbox_processor` đã gửi onboarding và return.
- **`/status` handler:**
  ```python
  async def handle_status_command(self, *, session, adapter, event, binding):
      auth = AuthContext.session(binding.user)
      await check_permission(session, auth, binding.workspace_id, Permission.AUTOMATIONS_READ.value, ...)
      run = await _latest_run_for_workspace(session, binding.workspace_id)
      if run is None:
          await adapter.send_message(external_peer_id=event.external_peer_id, text="No recent runs in this workspace.")
          return True
      summary = _format_run_summary(run, run.automation)
      await adapter.send_message(external_peer_id=event.external_peer_id, text=summary)
      return True
  ```
  Query latest run:
  ```python
  select(AutomationRun).join(Automation).where(
      Automation.workspace_id == workspace_id
  ).order_by(AutomationRun.created_at.desc()).limit(1)
  ```
- **`/run` handler:**
  ```python
  async def handle_run_command(self, *, session, adapter, event, binding):
      text = event.text or ""
      parts = text.split(maxsplit=1)
      if len(parts) == 1:
          # list active automations
          automations = await _list_active_automations(session, binding.workspace_id)
          ...
          return True
      name = parts[1].strip()
      automation = await _find_active_automation_by_name(session, binding.workspace_id, name)
      if automation is None:
          await adapter.send_message(..., text=f"Automation '{name}' not found.")
          return True
      auth = AuthContext.session(binding.user)
      await check_permission(session, auth, binding.workspace_id, Permission.AUTOMATIONS_EXECUTE.value, ...)
      trigger = AutomationTrigger(automation_id=automation.id, type=TriggerType.MANUAL, params={}, static_inputs={})
      await launch_run(session=session, trigger=trigger, runtime_inputs={"fired_by": "telegram"})
      await adapter.send_message(..., text="Run started. You will be notified when it completes.")
      return True
  ```
- **Permission helper:** `AuthContext` ở `app/auth/context.py:12`; `check_permission` ở `app/utils/rbac.py:129`.
- **Deep link:** dùng `_dashboard_run_url` trong `callbacks.py:20-21`; cân nhắc đổi từ `/workspaces/...` sang `/dashboard/...` để match web route.
- **Latest run format:** dùng `_format_run_summary` (`callbacks.py:51-60`) hoặc tương tự.

### Error Handling
- `check_permission` raise `HTTPException(403)` → catch và reply access-denied, không crash processor.
- Automation không active → reply trạng thái.
- `launch_run` raise `DispatchError` → reply lỗi rõ ràng, không crash.
- `Binding` None → `inbox_processor` đã gửi onboarding trước khi đến handler.

### Testing
- **Backend:** `pytest tests/unit/gateway/test_telegram_commands.py` (tạo mới hoặc mở rộng `test_telegram_callbacks.py`).
- **Integration:** gửi mock webhook `/status`, `/run`, `callback_query` và xác nhận reply messages/permissions.
- **Frontend:** không có UI mới ngoài deep link; kiểm tra `tsc --noEmit` nếu sửa shared types.

---

## 6. Project Structure Notes

```
nowing_backend/app/gateway/
  telegram/
    client.py              # đã hỗ trợ reply_markup / edit / answer_callback
    adapter.py             # đã parse callback_query / inline_message_id
    commands.py            # thêm handle_status_command, handle_run_command
    callbacks.py           # view_run / rerun đã có, cần verify
  base/commands.py         # thêm default handle_status_command, handle_run_command
  inbox_processor.py       # thêm dispatch /status, /run

nowing_backend/app/automations/
  persistence/enums/trigger_type.py   # MANUAL đã reserved
  dispatch/launch.py                  # launch_run đã có

nowing_backend/tests/unit/gateway/
  test_telegram_commands.py           # mới
  test_telegram_adapter.py            # mở rộng nếu cần
  test_telegram_callbacks.py          # mở rộng
```

---

## 7. References

- Epic / AC gốc: `_bmad-output/planning-artifacts/epics.md` §Story 11.3
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-1, AD-4, AD-5, AD-15, AD-16, AD-17
- Sprint proposal: `_bmad-output/planning-artifacts/sprint-change-proposal-telegram-2026-08-03.md` §Phase 3
- Architecture review: `_bmad-output/planning-artifacts/epic-11-architecture-review-2026-08-03.md` §2.1 (manual trigger), §2.2 (TelegramClient reply_markup)
- Blocker resolution: `_bmad-output/planning-artifacts/telegram-blocker-resolution-2026-08-03.md`
- Review spec: `_bmad-output/implementation-artifacts/code-review/review-spec-telegram.md`
- Telegram gateway: `nowing_backend/app/gateway/telegram/client.py`, `adapter.py`, `commands.py`, `callbacks.py`
- Inbox: `nowing_backend/app/gateway/inbox_processor.py`, `base/commands.py`, `registry.py`
- Automation launch: `nowing_backend/app/automations/dispatch/launch.py`

---

## Dev Agent Record

### Agent Model Used
Claude / Sonnet 4 — story context engine.

### Completion Notes
- Phần lớn gateway Telegram và callback query đã được implement; story này tập trung thêm `/status`, `/run` commands và dispatch.
- Đã thêm `handle_status_command`/`handle_run_command` vào `TelegramGatewayCommands` và `BaseGatewayCommands`.
- Đã thêm dispatch `/status` và `/run` trong `inbox_processor.py` sau `/new` và trước agent chat.
- Đã thêm `tests/unit/gateway/test_telegram_commands.py` với 7 test case bao phủ status, run list, run trigger, not found, permission denied.
- `ruff check/format` pass; `pytest tests/unit/gateway/` pass 68/68.
- Applied all 13 `patch` review findings from the 2026-08-04 review: fail-closed auth, permission-before-query for `/status` and `/run`, callback error handling and `answer_callback_query` guarantees, inbox-processor `try/finally`, generic launch-run error messages, 4096-char automation-list guard, bot-mention stripping, UUID type hint, full dashboard URLs, orphan-run reporting, guarded confirmation sends, and expanded unit tests.
- Applied the 9 re-run 2026-08-04 `patch` findings: unbound-callback `answer_callback_query` in `inbox_processor.py`, new `tests/integration/gateway/test_telegram_inbox.py`, send-failure guards in `/status`/`/run`, `SUSPENDED` binding rejection, bounded active-automation query with incremental list truncation, bot-mention-only `/run` list behavior, `outerjoin` for orphan runs, and no `send_message` fallback for inline `view_run` edits. `ruff check/format` and `pytest tests/unit/gateway/` and `pytest tests/integration/gateway/test_telegram_inbox.py` all pass.

### File List (changed / new)
- `nowing_backend/app/gateway/telegram/commands.py` (modified)
- `nowing_backend/app/gateway/base/commands.py` (modified)
- `nowing_backend/app/gateway/inbox_processor.py` (modified)
- `nowing_backend/app/gateway/telegram/callbacks.py` (modified)
- `nowing_backend/tests/unit/gateway/test_telegram_commands.py` (modified)
- `nowing_backend/tests/unit/gateway/test_telegram_callbacks.py` (modified)
- `nowing_backend/tests/integration/gateway/test_telegram_inbox.py` (new)

### Change Log
- Added `/status` and `/run` command handlers with permission checks and run query/formatting.
- Wired `/status` and `/run` dispatch into `inbox_processor.py`.
- Added `BaseGatewayCommands.handle_status_command` and `handle_run_command` defaults.
- Added `tests/unit/gateway/test_telegram_commands.py`.
- Added `tests/integration/gateway/test_telegram_inbox.py` covering `/status`, `/run`, callback dispatch, onboarding, and `SUSPENDED` rejection.
- Re-run patch: ensured unbound callback queries answer the spinner, wrapped all `/status`/`/run` sends, rejected `SUSPENDED` bindings, bounded active-automation queries, handled bot-mention-only `/run`, enabled orphan-run reporting, and removed inline `view_run` fallback sends.

### Baseline
- `baseline_branch: develop`
- `baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15`
