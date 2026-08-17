---
title: UX Contract — Epic 21 Addendum (Origami Refresh 2026-08-11)
project: Nowing
date: 2026-08-11
author: Sally (UX Designer)
status: partially merged into canonical contracts — pending PO/business validation for N4 Zalo and N5 notifications
---

# UX Contract — Epic 21 Addendum (Origami Refresh 2026-08-11)

**Phạm vi:** Các pattern bổ sung phát hiện từ Chrome MCP audit của Origami, chưa có trong canonical UX contracts hiện tại (`ux-contract-lead-intelligence-panel.md`, `ux-contract-fit-score-badge.md`).

**Trace:** `ux-research-origami-final-2026-08-11.md` (supersedes `ux-research-origami-refresh-2026-08-11.md`) → `epic21-lead-intelligence-ux.md` §10.

---

## 1. Onboarding Checklist (N1)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N1.1 | Sidebar hiển thị checklist “Lead-gen setup: X/5 done” | ✅ |
| N1.2 | Các bước: tạo ICP, chạy first search, enrich lead, connect campaign, gửi first message | ✅ |
| N1.3 | Các bước done có dấu ✅; bước tiếp theo highlight | ✅ |
| N1.4 | Collapse/hide checklist được | ✅ |

### Hành vi
- Checklist xuất hiện khi workspace chưa hoàn thành 5 bước.
- Click bước chưa done → mở chat với prompt gợi ý.
- Ẩn khi tất cả bước done hoặc user dismiss.

---

## 2. Workspace Mode Switch (N2)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N2.1 | Tab/switch ở đỉnh sidebar: Outbound / Research / Content | ✅ |
| N2.2 | Outbound mode: hiển thị nav Inbox, Campaigns, Senders, Tables | ✅ |
| N2.3 | Research mode: hiển thị nav New chat, Automations, Artifacts, Playground như hiện tại | ✅ |
| N2.4 | Content mode: hiển thị Deliverables / Playbooks / Reports | ✅ |

### Hành vi
- Mode persisted per user.
- Chuyển mode không reset chat/data panel.
- Sales user default = Outbound.

---

## 3. Tables Directory / Lead Lists Library (N3)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N3.1 | Màn `/tables` liệt kê tất cả lead lists | ✅ |
| N3.2 | Mỗi item hiển thị tên, last updated, source tag (X, Instagram, TikTok, Web) | ✅ |
| N3.3 | Search theo tên | ✅ |
| N3.4 | Sort: Updated, Created, Name | ✅ |
| N3.5 | Create new lead list CTA | ✅ |

### Hành vi
- Click table → mở trong data panel của chat hoặc màn table riêng.
- Tables do agent tạo tự động có tag auto; user-created có tag manual.

---

## 4. Inbox Empty State + Channel CTA (N4)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N4.1 | Inbox rỗng hiển thị heading “Start your first outreach campaign” | ✅ |
| N4.2 | Subtext: “Build a lead list from any scraper, then connect an email sequence” | ✅ |
| N4.3 | CTA “Start a campaign” nổi bật | ✅ |
| N4.4 | Outbound channel: **Email**; lead source: chọn từ tất cả scraper/connector đã kết nối | ✅ |
| N4.5 | Nếu chưa có email sender/lead source connection → dẫn đến setup | ✅ |

### Hành vi
- **LinkedIn và Zalo disabled** — không hiển thị trong MVP.
- Click “Start a campaign” → mở flow chọn lead source (từ registry scraper/connector) rồi chọn email sender + tạo sequence.
- Lead source chưa kết nối → disabled với tooltip `Connect [source] connector first`.

---

## 5. Positive-Reply Notifications (N5)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N5.1 | User nhận thông báo khi lead reply tích cực | ✅ |
| N5.2 | Channel: **email**, **Telegram** (tùy cấu hình) | ✅ |
| N5.3 | Thông báo gồm: tên lead, channel, nội dung reply, link mở lead | ✅ |
| N5.4 | Toggle bật/tắt trong Settings | ✅ |

### Hành vi
- Mở rộng Story 11.1 (Telegram notifications) với trigger `lead_positive_reply`.
- **Zalo disabled** trong MVP (legal/ToS gate pending).
- Gộp vào notification preferences per user.

---

## 6. Per-Lead Projected Cost (N6)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N6.1 | Trong table header hoặc row, hiển thị “X credits ($Y) per lead” trước khi enrich | ✅ |
| N6.2 | Cost cập nhật khi filter/sort thay đổi số lượng lead | ✅ |
| N6.3 | Nếu cost không xác định → hiển thị “estimated” + tooltip | ✅ |

### Hành vi
- Tính dựa trên FR-69 / Story 21.7.
- Hiển thị cạnh nút “Enrich X leads” / “Send & export”.

---

## 7. Source-Specific Table Tabs (N7)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N7.1 | Data panel có tab **Sources** với sub-tab **All** và các tab động cho mỗi scraper/connector đã tạo lead | ✅ |
| N7.2 | Mỗi sub-tab hiển thị lead list từ nguồn tương ứng | ✅ |
| N7.3 | Badge count trên mỗi sub-tab | ✅ |
| N7.4 | Chuyển tab không reset filter/sort | ✅ |

### Hành vi
- Sub-tab được sinh động từ registry scraper/connector (ví dụ: X, Instagram, TikTok, Reddit, YouTube, Google Search, Google Maps, Amazon, web crawl, Exa, Indeed, Walmart, batdongsan, chotot, muaban, VietnamWorks, TopCV, ITviec).
- Sub-tab chỉ hiển thị khi nguồn đó có ít nhất 1 lead.
- Phù hợp với multi-source aggregation (Epic 12 HR, BĐS, Epic 21 lead gen).
- Có thể merge/cross-reference giữa các nguồn.

---

## 8. “Connect a Campaign” Status Chip (N8)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| N8.1 | Lead table hiển thị chip “Not sending yet — connect a campaign” nếu chưa gắn sequence | ✅ |
| N8.2 | Click chip → dropdown chọn sequence hoặc “Create new sequence” | ✅ |
| N8.3 | Khi đã gắn sequence, hiển thị “Active: Sequence Name” | ✅ |
| N8.4 | Click active chip → mở sequence detail | ✅ |

### Hành vi
- Gắn với FR-66 / Story 21.4.
- Nút “Send & export” disabled hoặc warning nếu chưa connect campaign.

---

## 9. Settings Additions (from Origami Settings page)

### Trạng thái UI bắt buộc
| # | Trạng thái | Bắt buộc |
|---|---|---|
| S1 | Toggle “Show credit balance in navigation bar” | ✅ |
| S2 | Toggle “Keep sidebar expanded” | ✅ |
| S3 | Toggle “Browser notifications for agent responses” | ✅ |
| S4 | Toggle “Email me about positive replies” | ✅ |

### Hành vi
- S1: hiển thị credit_micros balance dạng compact ở top-right nav.
- S2: sidebar mở rộng mặc định.
- S3/S4: notification preferences, gắn với N5.

---

## 10. Traceability & Duplicate Check

| ID | Tính năng | Trạng thái trong Epic 21 / UX contracts | Action |
|---|---|---|---|
| N1 | Onboarding checklist | Mới | `ux-contract-sidebar-onboarding.md` |
| N2 | Workspace mode switch | Mới | `ux-contract-workspace-mode-switch.md` |
| N3 | Tables directory | Mới | `ux-contract-tables-directory.md` |
| N4 | Inbox empty state + Zalo CTA | Đã merge §8 vào `ux-contract-lead-intelligence-panel.md` | Merged |
| N5 | Positive-reply notifications | Đã tạo `ux-contract-positive-reply-notifications.md`; mở rộng Story 11.1 | Contract created |
| N6 | Per-lead projected cost | Đã merge §7 vào `ux-contract-lead-intelligence-panel.md` | Merged |
| N7 | Source-specific table tabs | Đã merge §2.1 vào `ux-contract-lead-intelligence-panel.md` | Merged |
| N8 | Connect campaign chip | Đã merge §5 vào `ux-contract-lead-intelligence-panel.md` | Merged |

**Canonical contracts updated:** `ux-contract-lead-intelligence-panel.md` (N4, N6, N7, N8) + `ux-contract-sidebar-onboarding.md`, `ux-contract-workspace-mode-switch.md`, `ux-contract-tables-directory.md`, `ux-contract-positive-reply-notifications.md`.

---

## 11. Architecture Enforcement Notes (2026-08-11)

All Epic 21 UI patterns must be backed by the shared backend components identified in the duplicate/overlap analysis. The following cross-epic reuse rules are binding:

| Pattern | Shared backend / AD | Constraint |
|---|---|---|
| N1 Onboarding checklist | `Sequence` + `CapabilityRegistry` (AD-39) | Checklist state should be derived from workspace `CapabilityRegistry` and existing `Sequence` records, not a separate onboarding table. |
| N2 Workspace mode switch | Existing workspace/session atoms | Mode is a UI state; data shown in each mode must reuse existing `Memory`, `Sequence`, `Deliverable` queries filtered by `client_id` (AD-31). |
| N3 Tables directory | `Lead` / `LeadSource` tables (AD-39) | Lead lists come from the `Lead` table filtered by `client_id`; source tags come from `CapabilityRegistry` (`emits_leads=true`) / `LeadSource`. |
| N4 Inbox empty state | `CapabilityRegistry` + `Connection` (AD-3, AD-39) | Lead-source picker is dynamic from registry (lead capabilities declare `emits_leads=true`); email sender uses existing `Connection` OAuth/email connector. |
| N5 Positive-reply notifications | Story 11.1 notification service (AD-39) | UI preference toggle adds `email_reply`, `email_delivered`, `email_bounced` to existing notification preferences; no new notification settings model. `SequenceEvent` is the canonical event source. |
| N6 Per-lead projected cost | `BillingEvent` + `credit_micros_balance` (AD-8, AD-10, AD-42) | Cost is estimated via wallet/`BillingEvent` APIs; `TokenUsage` is only for LLM token steps. Projected-cost UI reuses the usage dashboard component. |
| N7 Source-specific table tabs | `CapabilityRegistry` + `Lead` table (AD-39) | Sub-tabs rendered from actual workspace lead sources; no hard-coded source menu. |
| N8 “Connect a campaign” chip | `Sequence` table (AD-39) | Attaching a campaign sets the lead’s `sequence_id` on the `Sequence`/`SequenceEnrollment` model; `Sequence` is not an `Automation` subtype. |

**Canonical contracts updated with enforcement:** `ux-contract-lead-intelligence-panel.md`, `ux-contract-positive-reply-notifications.md`.

**Next Step:** PO validate N4 Zalo empty-state flow và N5 notification channel permissions; sau đó hand off các canonical contracts đã tạo cho implementation.
