# UX Contract — Positive-Reply Notifications

**Ngày:** 2026-08-11 (revised)
**Phạm vi:** N5 — Positive-reply notifications qua email, Telegram
**Loại tài liệu:** *contract*
**Trace:** `ux-contract-epic21-addendum-2026-08-11.md` → `epic21-lead-intelligence-ux.md` → Story 11.1 (Telegram foundation)

---

## Trạng thái UI bắt buộc

| # | Trạng thái | Bắt buộc |
|---|---|---|
| N5.1 | User nhận thông báo khi lead reply tích cực | ✅ |
| N5.2 | Channel: **email**, **Telegram** (tùy cấu hình) | ✅ |
| N5.3 | Thông báo gồm: tên lead, channel, nội dung reply, link mở lead | ✅ |
| N5.4 | Toggle bật/tắt trong Settings | ✅ |
| N5.5 | Nếu channel chưa kết nối → dẫn user đến setup | ✅ |

---

## Hành vi

- Trigger: agent/email service phân loại reply là `positive` (interested, book meeting, ask question).
- Notification gửi qua tất cả channel đã bật và đã kết nối.
- Click link trong notification → mở lead detail / inbox thread.
- **Zalo disabled** — không hiển thị toggle hay gửi qua Zalo trong MVP (Zalo OA legal/ToS gate pending).
- Mở rộng Story 11.1 (Telegram run notifications) với trigger `lead_positive_reply`.

---

## Settings toggles

| Toggle | Mặc định | Channel |
|---|---|---|
| Email me about positive replies | Off | Email |
| Telegram positive reply alerts | Off | Telegram |

---

## Notification payload

| Field | Nội dung |
|---|---|
| Title | "Positive reply from {lead_name}" |
| Body | "{lead_name} replied on {channel}: \"{reply_excerpt}\"" |
| Action | Link to lead detail / inbox thread |
| Channel | Email / Telegram |

---

## Architecture Enforcement Notes

- The notification dispatch **must** reuse the Story 11.1 notification service (AD-39). New `NotificationChannel` values are `email_reply`, `email_delivered`, `email_bounced` — additional channel types, not a new dispatch pipeline.
- The `SequenceEvent` table is the canonical source for `email_reply` / `email_delivered` / `email_bounced` events; the notification payload includes `enrollment_id` and `lead_id` from `SequenceEnrollment`.
- The settings toggles **must** extend the existing user notification preferences table/schema (Story 11.1). Do not create a separate `lead_notification_settings` table.
- The notification link **must** route to the existing lead detail / chat thread UI (FR-14). No new notification detail page.
- **Zalo is disabled in MVP**; the UI must not expose a Zalo channel toggle until AD-41 is re-activated.
- All lead/notification data must be filtered by the active `client_id` (AD-31); cross-client notification leakage is a hard failure.
