---
title: Sprint Change Proposal — Telegram Automation & Bot
description: ''
createdAt: '2026-08-03T00:00:00.000Z'
updatedAt: '2026-08-03T00:00:00.000Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-sprint-change-proposal-telegram-2026-08-03-md
---

# Sprint Change Proposal — Telegram Automation & Bot

**Workflow:** `bmad-correct-course` (batch mode)
**Project:** Nowing
**Date:** 2026-08-03
**Author:** Mary (Business Analyst) + Luisphan (PO)
**Status:** ✅ **ADOPTED** (PO Luisphan, 2026-08-03)

**Loại thay đổi:** Feature addition — expand existing Telegram gateway into automation notifications, write-back action, and interactive bot features.

**Đối ứng với:** Yêu cầu PO: (1) gửi notification sau automation, (2) chat với bot từ Telegram, (3) dùng các tính năng bot.

**Artifacts bị ảnh hưởng:**
- `_bmad-output/planning-artifacts/epics.md` (Epic 11 appended)
- `_bmad-output/planning-artifacts/sprint-change-proposal-telegram-2026-08-03.md`
- `nowing_backend/app/automations/runtime/executor.py`
- `nowing_backend/app/automations/actions/builtin/write_back_telegram/` (new)
- `nowing_backend/app/notifications/service/` (new handler)
- `nowing_backend/app/gateway/telegram/` (adapter/client/commands extensions)
- `nowing_web/lib/automations/builder-schema.ts`
- `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx`
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`

---

## 1. Issue Summary

**Trigger:** PO yêu cầu tích hợp Telegram để:
- Gửi notification sau khi automation chạy xong.
- Chat với Nowing agent từ Telegram bot.
- Sử dụng các tính năng bot (inline button, callback, commands).

**Reality check sau khi đọc code:**
- Telegram chat gateway đã tồn tại (`app/gateway/telegram/`) và đã có UI pairing trong `User Settings > Messaging Channels`.
- Dependency `python-telegram-bot>=22.7` đã có trong `pyproject.toml`.
- **Còn thiếu:** (a) gửi outbound notification từ automation runs, (b) automation action `write_back_telegram`, (c) khai thác tính năng bot ngoài text thuần.

**Quyết định:**
- Telegram là **P0**; crypto `market_data` pending sau.
- Scope bao gồm **Phase 1 (notification) + Phase 2 (`write_back_telegram`) + Phase 3 (bot features)**.
- Epic 11 đã append vào `epics.md`.

---

## 2. Epic Impact Assessment

| Check | Kết luận |
|---|---|
| Epic hiện tại còn hoàn thành được? | **Có.** Không epic nào chết. Epic 11 mới bổ sung. |
| Thay đổi cấp epic | Thêm **Epic 11 — Telegram Automation & Bot**. Không sửa epic cũ. |
| Epic tương lai bị ảnh hưởng | **Epic 6 (Automations)** thêm action `write_back_telegram`; **Epic 7/8** có thể mở rộng notification channel. |
| Epic nào vô hiệu / cần mới? | Không vô hiệu. Cần **Epic 11**. |
| Đổi thứ tự ưu tiên? | **Có.** Telegram trước, crypto `market_data` pending sau. |

### Epic 11 — Telegram Automation & Bot

**Mục tiêu:** Mở rộng Telegram gateway hiện có thành automation notification channel, write-back action, và bot tương tác.

| Story | Nội dung | Bind | Ưu tiên |
|---|---|---|---|
| **11.1** | Telegram notification preference toggle | FR-TELE-2 | **P0** |
| **11.2** | Send Telegram notification on automation run completion | FR-TELE-1, FR-TELE-7 | **P0** |
| **11.3** | Notification message format and deep link | FR-TELE-1, FR-TELE-6 | **P0** |
| **11.4** | `write_back_telegram` action backend | FR-TELE-3, FR-TELE-7 | **P0** |
| **11.5** | Telegram write-back UI in automation builder | FR-TELE-3, FR-TELE-6 | **P0** |
| **11.6** | Default chat resolution and connector selection | FR-TELE-3 | **P0** |
| **11.7** | Inline keyboard in Telegram messages | FR-TELE-4 | **P1** |
| **11.8** | Callback query handling | FR-TELE-4, FR-TELE-7 | **P1** |
| **11.9** | `/status` bot command | FR-TELE-5 | **P1** |
| **11.10** | `/run` bot command | FR-TELE-5 | **P1** |

---

## 3. Artifact Conflict & Impact Analysis

### 3.1 PRD

| # | Section | Thay đổi | Lý do |
|---|---|---|---|
| P1 | §4.x Automations | Thêm `write_back_telegram` action, notification trigger | Telegram là action + notification channel mới |
| P2 | §6 Out of Scope | Bỏ "Telegram bot chat" nếu đang ghi là out of scope; thực tế đã có gateway | Đồng bộ với code |
| P3 | §5 NFR | Thêm rate limit, token encryption, async notification | NFR-TELE |

### 3.2 Architecture

- **Inbound chat:** Dùng lại `app/gateway/telegram/adapter.py`, `TelegramStreamTranslator`, `TelegramGatewayCommands`.
- **Outbound automation:** Thêm `AutomationNotificationService` gọi `TelegramAdapter.send_message` qua `ExternalChatBinding`.
- **Automation action:** Thêm `app/automations/actions/builtin/write_back_telegram/`.
- **Data model:** Có thể cần thêm `user_notification_preferences` JSONB hoặc bảng riêng.

### 3.3 UI/UX

- `MessagingChannelsContent.tsx`: thêm toggle Telegram notification.
- Automation builder (`task-item.tsx`, `builder-schema.ts`): thêm action "Send Telegram message".
- Pairing flow hiện có giữ nguyên.

---

## 4. Recommended Approach

### Phase 1 — Automation Notification (P0)

1. Thêm `automation_run_complete` notification type.
2. Hook `notify_automation_terminal` vào `execute_run` sau `mark_succeeded`/`mark_failed`.
3. Thêm `send_telegram_to_user` helper tìm `ExternalChatBinding` và gọi `TelegramAdapter`.
4. UI toggle preference.

### Phase 2 — `write_back_telegram` Action (P0)

1. Tạo action backend với params: `text`, `chat_id`, `parse_mode`, `reply_markup`, `connector_name`.
2. Mở rộng builder schema + UI.
3. Resolve binding/connector mặc định.

### Phase 3 — Bot Features (P1)

1. `TelegramAdapter` parse `callback_query`, `send_message` thêm `reply_markup`.
2. `TelegramClient` thêm `answer_callback_query`, `edit_message_reply_markup`.
3. Thêm commands `/status`, `/run` trong `app/gateway/telegram/commands.py`.
4. Routing callback trong `inbox_processor`.

---

## 5. Implementation Handoff

### Scope classification: **Moderate**

- Không xây mới gateway, nhưng cần đụng automation runtime, notification system, DB schema, UI builder.
- Cần QA webhook/long-poll, rate limit, encryption token.

### Files / modules thay đổi chính

- `nowing_backend/app/notifications/types.py`
- `nowing_backend/app/notifications/constants.py`
- `nowing_backend/app/notifications/service/handlers/automation_run_complete.py` (new)
- `nowing_backend/app/automations/runtime/executor.py`
- `nowing_backend/app/automations/services/telegram.py` (new helper)
- `nowing_backend/app/automations/actions/builtin/write_back_telegram/*` (new)
- `nowing_backend/app/gateway/telegram/adapter.py` (Phase 3)
- `nowing_backend/app/gateway/telegram/client.py` (Phase 3)
- `nowing_backend/app/gateway/telegram/commands.py` (Phase 3)
- `nowing_web/lib/automations/builder-schema.ts`
- `nowing_web/app/dashboard/[workspace_id]/automations/components/builder/task-item.tsx`
- `nowing_web/app/dashboard/[workspace_id]/user-settings/components/MessagingChannelsContent.tsx`

### Success criteria

1. User nhận tin nhắn Telegram khi automation run hoàn thành/fail.
2. Automation builder có action "Send Telegram message".
3. Bot chat vẫn hoạt động; không regression ở `/start` pairing.
4. Bot token được encrypt, không xuất hiện plaintext trong log.
5. Self-host có thể dùng `longpoll` hoặc `webhook` như cũ.

---

## 6. Decisions Chốt

**D1 — Scope:** Phase 1 + Phase 2 + Phase 3 (notification, write-back, bot features).

**D2 — Priority:** Telegram là P0; crypto `market_data` pending sau.

**D3 — Implementation order:** 11.1 → 11.2 → 11.3 → 11.4 → 11.5 → 11.6 → 11.7 → 11.8 → 11.9 → 11.10.

**D4 — Reuse:** Dùng lại toàn bộ `app/gateway/telegram/`; không tạo gateway mới.

---

## 7. Next Steps

1. ✅ Epic 11 appended to `epics.md`.
2. ✅ SCP saved.
3. Bắt đầu implement Story 11.1 hoặc story PO chọn.
