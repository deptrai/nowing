# Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As a sales manager or agency owner,
I want my team of 3 to 20 agents to collaborate on a shared Kanban pipeline, automatically assign newly scraped leads via Round-Robin, log interaction timelines, and pool workspace credits with per-seat monthly spend caps,
So that our entire sales force operates efficiently without duplicate outreach or overspending.

---

## Architectural Invariants
- **INV-24.4 (Team Credit Pooling & Quota Locks):** Khóa dòng `Workspace.credit_micros_balance` khi trừ credits, kiểm tra `WorkspaceMember.monthly_spend_cap_micros`.
- **INV-23.6 (Tenant & Role RLS):** Đảm bảo thành viên chỉ xem được lead được phân công hoặc toàn bộ lead tùy theo role (`owner`, `admin`, `member`).

---

## Acceptance Criteria

1. **Reactive Kanban Pipeline Board:**
   - Cung cấp route `/dashboard/[workspace_id]/leads/pipeline` với các cột trạng thái:
     - `Mới săn` (New Lead)
     - `Đang tiếp cận` (Contacted)
     - `Tiềm năng` (Qualified)
     - `Đã chốt` (Won)
     - `Hủy / Không nhu cầu` (Lost)
   - Hỗ trợ kéo thả (Drag & Drop) mượt mà với Zero-cache đồng bộ tức thì giữa các thành viên.
2. **Automated Round-Robin Lead Assignment:**
   - Khi có batch lead mới từ Scraper / AI Chat, hệ thống tự động phân bổ đều cho các Sales Rep đang `Active`.
3. **Lead Interaction Timeline & Internal Notes:**
   - Drawer xem chi tiết Lead hiển thị lịch sử: Thời điểm cào ➔ Các tin nhắn Zalo/Telegram đã gửi ➔ Ghi chú của Sales ➔ Lịch hẹn.
4. **Shared Credit Wallet with Per-Seat Spend Caps:**
   - Thành viên dùng chung số dư của Workspace. Admin có thể đặt hạn mức (VD: tối đa 500 Credits/tháng cho mỗi nhân viên).

---

## Technical Tasks
- [ ] Backend: Bổ sung bảng `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs`.
- [ ] Backend: Thêm `monthly_spend_cap_micros` và `monthly_spent_micros` vào `workspace_members`.
- [ ] Backend: Xây dựng `LeadAssignmentService` với thuật toán Round-Robin.
- [ ] Frontend: Xây dựng Kanban Board component với `@dnd-kit` và Zero query subscription.
- [ ] Unit & Integration Tests: Test kéo thả chuyển stage, test round-robin chia lead, test chặn khi nhân viên vượt spend cap.
