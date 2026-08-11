---
title: Origami UI/UX Refresh — Lead-Gen Pilothouse for Nowing (Epic 21)
date: 2026-08-11
author: Sally (UX Designer)
source: Chrome MCP + live screenshot from https://origami.chat
type: ux-research
---

# Origami UI/UX Refresh — Lead-Gen Pilothouse for Nowing

## Tóm tắt

Đã dùng Chrome MCP để điều khiển tab đang mở sẵn `https://origami.chat` (tab 282531806) và khám phá các màn chính. Phần lớn khung layout/chat+data panel đã có trong `epic21-lead-intelligence-ux.md` (2026-08-10). Bản refresh này bổ sung các pattern mới phát hiện từ navigation deeper và so sánh với UX contracts + Epic 21 hiện tại để tránh duplicate.

---

## 1. Các màn hình đã khám phá

### 1.1 Chat + Data Panel (màn screenshot gốc)
- **Layout:** sidebar trái + chat panel giữa + data table panel phải.
- **Lead table:** 9 dòng, cột Fit Score, Tên doanh nghiệp, Website, Ngành, Mô tả, Địa điểm, Loại khách.
- **Giá hiển thị inline:** “Projected price 2.5 credits ($0.036) per lead”.
- **Filter chips:** “Doanh nghiệp ở Việt Nam”, “Doanh nghiệp thực sự liên quan đến trầm hương”.
- **Campaign connection:** “Not sending yet — connect a campaign”.
- **Suggested Next Actions:** tìm decision-maker, lọc ý định mua rõ ràng, so sánh X/Instagram/TikTok.

### 1.2 Tables List (`/tables`)
- Danh sách các “table” (lead lists) với search, cập nhật lần cuối.
- Các bảng: Doanh nghiệp trầm hương VN, Cá nhân quan tâm (Instagram/TikTok/mở rộng), Tín hiệu tìm mua trên web.
- Cho thấy Origami tổ chức leads theo nhiều nguồn (X, Instagram, TikTok, web signals) → mỗi nguồn một table.

### 1.3 Inbox / Campaign Empty State (`/sequences/inbox`)
- Empty state: “Start your first outreach campaign”.
- CTA rõ ràng: “Start a campaign”.
- Channel selection: **Email** và **LinkedIn** (links to `/sequences/senders`).
- Khi lead list chưa connect campaign, UI dẫn người dùng đến setup.

### 1.4 Settings / Profile
- Profile: avatar, tên, email.
- Preferences:
  - Browser notifications (agent finish responding).
  - Show credit balance (display in nav).
  - Keep sidebar expanded.
  - Email me about positive replies.

### 1.5 Chats List (`/chats`)
- Danh sách chat với updated time, created time, tag (ví dụ “Crypto”), sort dropdown, create button.
- Mỗi chat có actions menu.

### 1.6 Top-Level Project Modes
- Sidebar có 2 tab ở đỉnh: **Outbound** và **Content**.
- Mặc định đang ở Outbound (lead-gen/campaigns). Content có thể là research/deliverables mode — chưa click được vì ref hết hạn, nhưng rõ ràng là switch mode.

---

## 2. UX pattern chính từ Origami

| Pattern | Mô tả | Giá trị |
|---------|-------|---------|
| Chat-first workspace | Chat là trung tâm, data panel là bản đồ kết quả | Giảm learning curve |
| 2-panel layout (chat + data table) | Không cần rời khỏi cuộc trò chuyện để xem leads | Context liên tục |
| Table-as-a-list (multi-source) | Mỗi nguồn/topic một table riêng | Tổ chức theo chiến dịch/vertical |
| Suggested next actions | 3-4 nút AI gợi ý bước tiếp theo | Giảm decision paralysis |
| Empty state with channel CTA | Inbox rỗng → chọn kênh outreach ngay | Activation tốt |
| Per-lead cost projection | Giá tính trước mỗi lead | Trust, transparency |
| Campaign connection prompt | “Not sending yet — connect a campaign” | Clear status, clear next step |
| Onboarding sidebar checklist | “Next steps: 0 of 5 done” | Tiến độ activation |
| Settings for sales notifications | Email khi có positive reply | Re-engagement |

---

## 3. So sánh với Nowing hiện tại và UX contracts

### 3.1 Đã có trong UX contracts / Epic 21

| Pattern | Tài liệu Nowing | Ghi chú |
|---------|-----------------|---------|
| 2-panel layout chat + data | `ux-contract-lead-intelligence-panel.md` §1 | ✅ Đã có |
| Data table (Leads / Signals / Sequences tabs) | `ux-contract-lead-intelligence-panel.md` §2 | ✅ Đã có |
| Fit score badge (0-100, green/yellow/red) | `ux-contract-fit-score-badge.md` | ✅ Đã có |
| Suggested actions (max 3, cost indicator) | `ux-contract-lead-intelligence-panel.md` §3 | ✅ Đã có |
| Filter chips | `ux-contract-lead-intelligence-panel.md` §4 | ✅ Đã có |
| Row actions: star, enrich, sequence, remove | `ux-contract-lead-intelligence-panel.md` §2.4 | ✅ Đã có |
| Campaign / sequence integration | `epic21-lead-intelligence-ux.md` §4.2.5 | ✅ Đã có |
| Credit display / usage dashboard | `ux-contract-usage-dashboard.md` | ✅ U1-U7 |

### 3.2 Chưa có trong Nowing — đề xuất bổ sung

| # | Pattern/Feature | Mô tả | Liên kết Epic/Story | Mức độ ưu tiên |
|---|-----------------|-------|---------------------|----------------|
| **N1** | **Onboarding checklist cho lead-gen workspace** | Sidebar hiển thị “Next steps: X/5 done” để kích hoạt người dùng mới qua các bước: tạo ICP, chạy first search, enrich lead, connect campaign, gửi first message. | Epic 21 onboarding mới hoặc mở rộng Story 21.1 | P1 |
| **N2** | **Workspace mode switch (Outbound / Research / Content)** | Tab ở đỉnh sidebar cho phép chuyển giữa “Outbound” (lead-gen), “Research” (chat/reports), “Content” (deliverables/playbooks). Giúp người dùng sales không bị ngập trong research UI. | UX contract mới; liên quan Epic 21 + Epic 8 dashboard | P1 |
| **N3** | **Tables directory / Lead lists library** | Một màn `/tables` liệt kê tất cả lead lists, search, sort theo updated time. Nowing hiện chỉ có data panel bên trong chat. | Story mới trong Epic 21 (lead list management) | P2 |
| **N4** | **Inbox empty state + channel CTA (Email / LinkedIn / Zalo)** | Khi chưa có campaign, hiển thị rõ “Start your first outreach campaign” với chọn kênh. Tại VN phải có **Zalo**. | Story 21.4 + 21.6 | P0 (VN) |
| **N5** | **Positive-reply notification (Email / Zalo / Telegram)** | Tự động thông báo khi lead reply tích cực. Nowing đã có Telegram notifications (Story 11.1), chưa có email/Zalo trigger theo lead reply. | Epic 21.6 / Story 11.x mở rộng | P1 |
| **N6** | **Per-lead projected price inline** | Bên cạnh bảng leads hiển thị “X credits ($Y) per lead” trước khi enrich/send. Tăng trust. | Story 21.7 / FR-69 | P1 |
| **N7** | **Source-specific lead tables (X / Instagram / TikTok / Web)** | Mỗi nguồn một table riêng, có thể merge sau. Phù hợp với multi-source aggregation của Nowing (HR vertical, BĐS vertical). | Story 21.1 hoặc Epic 12 | P2 |
| **N8** | **“Connect a campaign” status chip** | Trong lead table hiển thị campaign chưa connect và CTA rõ ràng. | Story 21.4 | P1 |

### 3.3 Khác biệt cốt lõi nên giữ của Nowing
- **Multiple chat tabs** — Origami chỉ có 1 chat active, Nowing có nhiều chat.
- **Research memory + citations** — Origami chưa thấy durable memory / provenance.
- **MCP / API Playground** — Nowing có power-user surface, Origami không.
- **Self-host / open-core** — khác biệt lớn về license và deployment.

---

## 4. Đề xuất UI/UX cải tiến cho Nowing Epic 21

### 4.1 Layout / Navigation
- **Bổ sung workspace mode switch** (Outbound / Research / Content) ngay trên sidebar.
- **2-panel mặc định bật** khi agent trả về leads/signals; có thể thu gọn.
- **Tables directory** trong left sidebar hoặc top-level nav để quản lý nhiều lead lists.

### 4.2 Lead Table
- **Inline projected cost** trước khi enrich/connect campaign.
- **Campaign status chip** rõ ràng (“Not sending yet — connect a campaign” / “Active: Sequence X”).
- **Multi-source table tabs** (X, Instagram, TikTok, Web) nếu research từ nhiều nguồn.

### 4.3 Empty States & Activation
- **Inbox empty state** hướng dẫn setup campaign và chọn kênh (Email, LinkedIn, Zalo).
- **Onboarding checklist** ở sidebar cho workspace lead-gen mới.

### 4.4 Notifications
- **Positive reply notification** qua email + Zalo/Telegram.
- **Browser notification** khi agent hoàn thành deep-research hoặc campaign có reply.

---

## 5. Kiểm tra trùng lặp với epics/ui specs

- **Không trùng:** N1, N2, N3, N4 (empty state Zalo), N5 (positive reply email/Zalo), N6 (per-lead projected price inline), N7 (source-specific tables), N8 (campaign status chip) — chưa thấy trong `epic21-lead-intelligence-ux.md` hay `ux-contract-lead-intelligence-panel.md`.
- **Đã có / cần refine:** 2-panel, data table, fit score, filter chips, suggested actions, row actions, campaign integration — đã có trong UX contracts.
- **Không nên copy:** “Show credit balance in nav” vì `ux-contract-usage-dashboard.md` đã định nghĩa credit balance; có thể thêm toggle hiển thị nhưng không phải feature mới.

---

## 6. Next step đề xuất

1. **P0 — Empty state / channel CTA (N4):** VN market cần Zalo, cần UX contract mới hoặc cập nhật `ux-contract-lead-intelligence-panel.md`.
2. **P1 — Workspace mode switch (N2) + Onboarding checklist (N1):** Giúp sales user activate nhanh hơn, giảm cognitive load.
3. **P1 — Positive-reply notifications (N5):** Mở rộng Story 11.1 (Telegram) sang email/Zalo cho lead-gen.
4. **P2 — Tables directory (N3) + Source-specific tables (N7):** Quản lý nhiều lead lists và multi-source research.

---

**Status:** Superseded. Final synthesis is in `ux-research-origami-final-2026-08-11.md`; this draft remains as the raw research trace.
