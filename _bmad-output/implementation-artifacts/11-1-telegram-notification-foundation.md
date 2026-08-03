---
baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15
baseline_branch: develop
story_key: 11-1-telegram-notification-foundation
status: done
---

# Story 11.1: Telegram Notification Foundation

**Story ID:** 11.1  
**Epic:** 11 — Telegram Automation & Bot  
**Title:** Telegram Notification Foundation  
**Status:** review  
**Priority:** HIGH  
**Requirements:** FR-TELE-1 (automation run notification), FR-TELE-2 (notification preference), FR-TELE-6 (UI builder + settings), FR-TELE-7 (rate limit & error handling)  
**Architecture:** AD-2 (Async SQLAlchemy + Alembic), AD-5 (Zero sync cho real-time state), AD-8 (unified credit wallet / TokenUsage — xem xét tracking), AD-15 (gateway là external dependency), AD-16 (license boundary), AD-17 (Celery async door)  
**Dependencies:** `app/gateway/telegram/` (TelegramClient, TelegramAdapter) đã tồn tại; `NotificationService` + `Notification` model đã tồn tại; `ExternalChatBinding` đã có. Không có story trước trong Epic 11.

---

## 1. Goal

Thêm lớp notification preference cho Telegram, khi automation run kết thúc (`succeeded`/`failed`) thì:

- Tạo in-app notification loại `automation_run_complete` (sync qua Zero).
- Nếu user có active `ExternalChatBinding` Telegram và bật preference, gửi Telegram message trong 30 giây.
- Format rõ ràng, có deep link về run, tuân thủ 4096 UTF-16 units, xử lý `RetryAfter`, và KHÔNG làm run fail khi gửi lỗi.

**Non-goal:** Không xây mới gateway Telegram; không tạo notification channel khác (Slack/Discord) trong story này.

---

## 2. User Story

> As a user,  
> I want to enable or disable Telegram notifications for automation runs and receive a clear message with a deep link when a run completes or fails,  
> so that I can control whether Nowing messages me on Telegram and quickly review results without keeping the dashboard open.

---

## 3. Acceptance Criteria

### AC-1 — Preference toggle visible đúng điều kiện
**Given** user mở User Settings > Messaging Channels,  
**When** user có ít nhất một `ExternalChatBinding` Telegram ở trạng thái `bound`,  
**Then** toggle "Notify me on Telegram when an automation run completes" xuất hiện trong Telegram card.

### AC-2 — Preference persist và có hiệu lực ngay
**Given** user bật/tắt toggle,  
**When** lưu,  
**Then** giá trị persist trong DB (JSONB `notification_preferences` hoặc bảng riêng) và áp dụng cho các run kế tiếp.  
**And** tắt preference vẫn tạo in-app notification `automation_run_complete`, nhưng KHÔNG gửi Telegram.

### AC-3 — Notification tạo khi run kết thúc
**Given** `AutomationRun` chuyển sang `succeeded` hoặc `failed`,  
**When** `repository.mark_succeeded`/`mark_failed` hoàn tất,  
**Then** tạo `Notification` type `automation_run_complete` cho `automation.created_by_user_id` (hoặc owner của binding), gắn `workspace_id`, `run_id`, `automation_id`, `status` trong metadata.

### AC-4 — Gửi Telegram khi đủ điều kiện
**Given** run kết thúc,  
**When** user có active Telegram binding cho workspace và `notification_preferences.automation_run_complete.telegram == true`,  
**Then** enqueue Celery task gửi Telegram message, đảm bảo message rời khỏi worker trong 30s.

### AC-5 — Không gửi khi thiếu binding hoặc tắt preference
**Given** no binding hoặc preference tắt,  
**When** run kết thúc,  
**Then** chỉ tạo in-app notification, không gọi Telegram API.

### AC-6 — Message chunked/truncated đến 4096 UTF-16 units
**Given** kết quả/error dài,  
**When** gửi,  
**Then** cắt theo `chunk_message` (`app/gateway/telegram/formatting.py:51`) sao cho mỗi phần ≤ 4096 UTF-16 code units. Phần đầu chứa summary và deep link.

### AC-7 — `RetryAfter` và delivery failure không fail run
**Given** Telegram trả `RetryAfter` hoặc lỗi network,  
**When** gửi,  
**Then** retry tối đa theo `TelegramClient._send_once` (`client.py:176`), sleep theo `retry_after`, log lỗi, metric.  
**And** lỗi gửi KHÔNG propagate ra executor, run vẫn `succeeded`/`failed`.

### AC-8 — Format success/failure
**Given** run thành công,  
**Then** message bắt đầu bằng `✅ Automation '<name>' finished successfully`.
**Given** run thất bại,  
**Then** message bắt đầu bằng `❌ Automation '<name>' failed` + dòng lỗi đầu tiên (nếu có).
**And** tên automation in đậm, trạng thái highlight, deep link `/dashboard/{workspace_id}/automations/{automation_id}?run_id={run_id}`; dashboard đọc query param, scroll và mở chi tiết run.

### AC-9 — API cập nhật preference
**Given** authenticated user,  
**When** gọi `PATCH /users/me/notification-preferences`,  
**Then** cập nhật JSONB và trả `UserRead` (hoặc schema riêng).

### AC-10 — Test coverage
**Given** code mới,  
**Then** có unit test cho formatter/chunking, integration test cho executor hook, test cho preference endpoint, và test fallback khi Telegram lỗi.

---

## 4. Tasks / Subtasks

- [x] Migration + schema (AC #1, #2)
  - [x] Tạo Alembic migration `187_add_user_notification_preferences` thêm `notification_preferences` JSONB vào `user`
  - [x] Cập nhật `app/notifications/types.py` thêm `"automation_run_complete"`
  - [x] Cập nhật `app/notifications/constants.py` `CATEGORY_TYPES["status"]`
- [x] Backend endpoint (AC #9)
  - [x] `PATCH /api/v1/users/me/notification-preferences` trong `app/routes/users_routes.py`
  - [x] Schema `UserNotificationPreferencesUpdate` trong `app/schemas/users.py`
- [x] UI toggle (AC #1, #2)
  - [x] Thêm toggle trong `MessagingChannelsContent.tsx` (Telegram card)
  - [x] Fetch/PATCH qua `userApiService.getMe` + `authenticatedFetch`
- [x] Notification handler + Celery dispatch (AC #3, #4, #5)
  - [x] Dùng `NotificationService.create_notification` thay vì class handler riêng
  - [x] Tạo Celery task `automation.notify_telegram_run_complete` trong `app/automations/tasks/notify_run_complete.py`
  - [x] Hook vào `app/automations/runtime/executor.py` sau `mark_succeeded`/`mark_failed`
- [x] Message formatter (AC #6, #8)
  - [x] Hàm `format_automation_run_message(run, automation)` trong `app/automations/services/telegram_notifications.py`
  - [x] Dùng `escape_markdown_v2`, `chunk_message` từ `app/gateway/telegram/formatting.py`
- [x] Tests (AC #10)
  - [x] Unit test message format + chunk
  - [x] Integration test preference endpoint
  - [x] Integration test executor notification hook
  - [x] Mock Telegram API test cho gửi lỗi

---

## 5. Dev Notes

### Architecture & License
- **AD-2:** Mọi thay đổi schema phải có Alembic migration. Thêm cột JSONB vào `user` là đơn giản nhất; nếu `User` model của fastapi-users gây khó khăn, tách bảng `user_notification_preferences(user_id PK, preferences JSONB)`.
- **AD-5:** `Notification` đã có trong `zero_publication` (`ARCHITECTURE-SPINE.md:99`); in-app notification sẽ real-time trên web mà không cần thêm publication.
- **AD-8 / AD-10:** Telegram Bot API miễn phí, nhưng nên tạo `TokenUsage` với `usage_type = "telegram_message"` để tracking (không debit wallet). Quyết định PO: có tính phí user không? Mặc định hiện tại là không.
- **AD-15:** Telegram là external HTTP dependency; `TelegramClient` đã retry `RetryAfter` (`client.py:176`), thêm log/metric số lỗi.
- **AD-16:** Code Telegram nằm trong `app/gateway/telegram/` (Apache-2.0), không động `app/proprietary/`.

### Current State (verified from code)
- `NotificationService.create_notification` tồn tại (`app/notifications/service/facade.py:35`) — dùng để tạo in-app notification.
- `NotificationType` Literal hiện chưa có `automation_run_complete` (`app/notifications/types.py:7`).
- `TelegramClient.send_message` đã hỗ trợ `reply_markup` và `_send_with_fallbacks` (`client.py:48-188`), chunk không tự xử lý — phải chunk trước khi gọi.
- `chunk_message` tồn tại (`app/gateway/telegram/formatting.py:51`), dùng `_utf16_len` để đếm đúng UTF-16 units.
- `executor.py` gọi `repository.mark_succeeded(session, run)` (`executor.py:82`) rồi `session.commit()`. Hook nên gọi SAU `session.commit()` để đảm bảo run đã persisted với terminal status, hoặc dùng `on_commit` nếu có.
- `ExternalChatBinding` query active binding theo `user_id`, `account_id`, `state=BOUND` (`app/db.py:971-1068`).
- `account_token(account)` trả token từ `TELEGRAM_SHARED_BOT_TOKEN` nếu system, hoặc decrypt `encrypted_credentials` (`app/gateway/accounts.py:20`).
- `User` model chưa có `notification_preferences` (`app/db.py:2616-2766`).

### Technical Details
- **Resolver binding cho notification:**
  ```python
  select(ExternalChatBinding).where(
      ExternalChatBinding.user_id == user_id,
      ExternalChatBinding.account_id == account_id,
      ExternalChatBinding.state == ExternalChatBindingState.BOUND,
  )
  ```
- **Celery task pattern:** dùng `run_async_celery_task` + `get_celery_session_maker` như `app/automations/tasks/execute_run.py:19-32`.
- **Message format (MarkdownV2):**
  ```
  ✅ Automation *'<name>'* finished successfully
  ...
  [Open run]({deep_link})
  ```
  Escape tên nếu chứa ký tự đặc biệt (`escape_markdown_v2`).
- **Deep link format:** `/dashboard/{workspace_id}/automations/{automation_id}/runs/{run_id}` (confirm với web route thực tế; `callbacks.py` hiện dùng `/workspaces/...` cần align).
- **Retry/fallback:** Dùng `TelegramClient.send_message` trực tiếp; nó tự drop `parse_mode`/`reply_markup` khi `BadRequest` (`client.py:138-173`).

### Error Handling
- Thiếu binding hoặc preference tắt → không gọi Telegram, chỉ tạo in-app.
- Thiếu token → log warning, không fail run.
- `RetryAfter` → sleep rồi retry 3 lần; cuối cùng log failure.
- Exception bất kỳ trong Celery task → catch và log, không raise về executor.

### Testing
- **Backend:** `pytest tests/unit/automations/test_telegram_notification_formatter.py`, `tests/integration/automations/test_run_notification.py`.
- **Frontend:** `pnpm tsc --noEmit`, `pnpm exec biome check` cho `MessagingChannelsContent.tsx`.
- **E2E:** Tạo automation → đợi chạy xong → kiểm tra notification và Telegram message (nếu có test bot).

---

## 6. Project Structure Notes

```
nowing_backend/
  alembic/versions/..._add_user_notification_preferences.py
  app/
    db.py                              # thêm notification_preferences (hoặc bảng mới)
    routes/users_routes.py             # PATCH /users/me/notification-preferences
    schemas/users.py                   # UserNotificationPreferencesUpdate
    notifications/
      types.py                         # thêm "automation_run_complete"
      constants.py                     # CATEGORY_TYPES["status"]
      service/handlers/automation_run_complete.py  # handler mới
      service/facade.py                # expose handler
    automations/
      runtime/executor.py              # hook sau mark_succeeded/mark_failed
      services/telegram_notifications.py  # format + resolve + send
      tasks/notify_run_complete.py     # Celery task
nowing_web/
  app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx  # UI toggle
  lib/apis/user-api.service.ts       # PATCH notification-preferences (nếu cần)
```

---

## 7. References

- Epic / AC gốc: `_bmad-output/planning-artifacts/epics.md` §Story 11.1
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-2, AD-5, AD-8, AD-15, AD-16, AD-17
- Sprint proposal: `_bmad-output/planning-artifacts/sprint-change-proposal-telegram-2026-08-03.md` §Phase 1
- Blocker resolution: `_bmad-output/planning-artifacts/telegram-blocker-resolution-2026-08-03.md`
- Telegram gateway: `nowing_backend/app/gateway/telegram/client.py`, `adapter.py`, `formatting.py`
- Automation runtime: `nowing_backend/app/automations/runtime/executor.py`, `repository.py`
- Notification: `nowing_backend/app/notifications/service/facade.py`, `persistence/models.py`

---

## Review Findings

All review findings from the code-review pass were addressed and re-tested:

- [x] **High:** Truncate in-app notification title to `TITLE_MAX_LENGTH` and keep Telegram header safe.
- [x] **High:** Defensively read `notification_preferences.automation_run_complete` and require `telegram is True`.
- [x] **Medium:** Filter suspended/revoked bindings and failing/suspended accounts in `resolve_telegram_binding_for_run`.
- [x] **Medium:** Disallow `notification_preferences: null` in `UserUpdate` via a `field_validator`.
- [x] **Medium:** Raise Celery task soft/time limits and `expires` to avoid dropping or killing notification sends.
- [x] **Medium:** Avoid splitting MarkdownV2 escape sequences in `chunk_message` hard cuts.
- [x] **Low:** Deep link kept as query-param `?run_id=...`; dashboard reads, scrolls, and expands the run.
- [x] **Low:** Telegram toggle only shown for bound connections.
- [x] **Low:** Toggle has try/catch, in-flight guard, and reverts on `authenticatedFetch` errors.
- [x] **Low:** Record `record_gateway_outbound` metrics for sent/failed Telegram sends.
- [x] **Low:** Strict boolean `automation_run_complete.telegram is True` check.
- [x] **Low:** Map all terminal `RunStatus` values to labels and skip non-terminal runs.
- [x] **Low:** Replace two-level preference merge with recursive deep merge.
- [x] [Review][Defer] **Low:** Concurrency/atomicity of `PATCH /users/me/notification-preferences` (read-merge-write) — see `_bmad-output/implementation-artifacts/deferred-work.md`.
- [x] **Low:** Update spec AC-8/AC-9 to match the implemented deep-link and endpoint path.

---

## Dev Agent Record

### Agent Model Used
Claude / Sonnet 4 — story context engine.

### Completion Notes
- Đã thêm migration `187_add_user_notification_preferences` + cột `notification_preferences` JSONB trên `User`.
- Đã thêm `PATCH /users/me/notification-preferences` với deep-merge, trả `UserRead` có `notification_preferences`.
- Đã thêm `automation_run_complete` vào `NotificationType` và `CATEGORY_TYPES["status"]`.
- Đã thêm toggle Telegram trong `MessagingChannelsContent.tsx`, chỉ hiện khi có Telegram binding `bound`.
- Đã thêm `send_automation_run_telegram_notification` + `format_automation_run_message` + `resolve_telegram_binding_for_run`.
- Đã thêm Celery task `automation.notify_telegram_run_complete` và hook trong `executor.py` sau `mark_succeeded`/`mark_failed` (fire-and-forget).
- Đã xử lý chunk message theo UTF-16 4096, escape MarkdownV2, deep link `/dashboard/{workspace_id}/automations/{automation_id}?run_id={run_id}`.
- Lỗi gửi Telegram được catch/log/metric, không làm run fail; `RetryAfter` do `TelegramClient` xử lý.
- Đã giải quyết tất cả findings từ blind-hunter, edge-case-hunter, acceptance-auditor (trừ concurrency read-merge-write được defer).
- Đã chạy và pass: `ruff check`/`ruff format`, `pytest` (unit + integration chỉ định), `pnpm tsc --noEmit`, `pnpm exec biome check`.

### File List (changed / new)
- `nowing_backend/alembic/versions/187_add_user_notification_preferences.py` (new)
- `nowing_backend/app/db.py` (modified — `notification_preferences` on `User`)
- `nowing_backend/app/schemas/users.py` (modified)
- `nowing_backend/app/routes/users_routes.py` (modified)
- `nowing_backend/app/notifications/types.py` (modified)
- `nowing_backend/app/notifications/constants.py` (modified)
- `nowing_backend/app/automations/runtime/executor.py` (modified)
- `nowing_backend/app/automations/services/telegram_notifications.py` (new)
- `nowing_backend/app/automations/tasks/notify_run_complete.py` (new)
- `nowing_backend/app/celery_app.py` (modified)
- `nowing_backend/tests/unit/automations/test_telegram_notification_formatter.py` (new)
- `nowing_backend/tests/integration/automations/test_run_notification.py` (new)
- `nowing_backend/tests/integration/routes/test_user_notification_preferences.py` (new)
- `nowing_web/contracts/types/user.types.ts` (modified)
- `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx` (modified)
- `AGENTS.md` (modified — added Story 11.1 verification commands)

### Baseline
- `baseline_branch: develop`
- `baseline_commit: 4d98bc5c9bae93c453d531290904f71cf09c8a15`
