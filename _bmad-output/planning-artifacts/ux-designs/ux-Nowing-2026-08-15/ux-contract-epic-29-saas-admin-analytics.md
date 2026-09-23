# UX Contract — Epic 29: SaaS Operations & Admin Governance

**Ngày:** 2026-08-30  
**Phạm vi:** UX contracts cho Epic 29 (Stories 29.1–29.4, 29.6) và cập nhật traceability cho Story 29.5.  
**Bám vào:** FR-100 · FR-101 · FR-102 · FR-103 · FR-104 · UX-DR-PRFAQ-5 · UX-DR-PRFAQ-6 · AD-51 · AD-52 · AD-53 · AD-54 · AD-55  
**Loại tài liệu:** *contract* — định nghĩa trạng thái UI bắt buộc.

---

## 1. Custom Workspace Roles (FR-100, UX-DR-PRFAQ-5)

**Bài toán:** Workspace Owner cần tạo và quản lý các vai trò tuỳ chỉnh dựa trên mẫu, mà không vi phạm ranh giới RBAC (không có role `Admin` hệ thống).

| # | Trạng thái UI bắt buộc |
|---|---|
| RB-1 | **Roles List** — danh sách `WorkspaceRole` trong workspace, phân biệt rõ `is_system_role=True` (Owner/Editor/Viewer) và `is_system_role=False` (custom). |
| RB-2 | **Create Role from Template** — dropdown chọn mẫu `Viewer`, `Editor`, `Analyst`, `Billing`, `Custom`; sau khi chọn, UI load permission preset tương ứng. |
| RB-3 | **Permission Matrix** — grid checkbox các permission (memory_read, memory_write, analytics_read, billing_read, settings_write, member_invite, member_remove, source_configure) với trạng thái disabled nếu vượt quá quyền Owner. |
| RB-4 | **Admin Name Guard** — nếu user nhập tên chứa "Admin" hoặc trùng tên role có sẵn, hiển thị lỗi inline và disable Save. |
| RB-5 | **Role Assignment in Members** — trong màn hình members, Owner có thể chọn role từ dropdown cho từng thành viên. |

---

## 2. Workspace Health Dashboard (FR-101, UX-DR-PRFAQ-5)

**Bài toán:** Owner/Analyst cần nhanh chóng đánh giá sức khoẻ và xu hướng của workspace.

| # | Trạng thái UI bắt buộc |
|---|---|
| HD-1 | **Metric Cards** — 6 cards trên cùng: `active_members_dau`, `active_members_wau`, `total_memories`, `memory_growth_count`, `recall_queries`, `research_queries`, `credits_consumed_micros`, `cost_per_turn_micros`. Mỗi card hiển thị value, change % so với 7 ngày trước, và sparkline 14 ngày. |
| HD-2 | **Quota Progress Bars** — so sánh từng metric với `WorkspaceLimit`, đổi màu cam khi ≥ 80% và đỏ khi ≥ 100%. CTA "Nâng cấp plan" khi ≥ 80%. |
| HD-3 | **Top Sources Table** — bảng xếp hạng `source_type` theo số memory mới (7 ngày qua) và `source_coverage_gap_count`. |
| HD-4 | **Coverage Gap Drawer** — click vào "Source coverage gap" mở drawer liệt kê các `source_type` đã bật nhưng không có memory mới trong 30 ngày. |
| HD-5 | **Drill-down Filter** — mỗi metric clickable, dẫn đến màn chi tiết lọc theo `workspace_id` + time range. |

---

## 3. Subscription Tier & Quota Management (FR-102, UX-DR-PRFAQ-5)

**Bài toán:** Superadmin quản lý plan catalog; Owner tự phục vụ đổi tier.

| # | Trạng thái UI bắt buộc |
|---|---|
| PM-1 | **Plan Catalog (superadmin)** — bảng các `WorkspaceLimit` với `plan_tier` (Free/Team/Growth/Enterprise), `price_micros`, `currency`, `max_members`, `max_memory_count`, `max_memory_bytes`, `max_monthly_credits`, `max_sources`, `support_level`. Có badge "System default". |
| PM-2 | **Workspace Billing Settings (Owner)** — hiển thị plan hiện tại, nút "Change plan", và danh sách các plan có thể upgrade/downgrade. |
| PM-3 | **Plan Comparison Table** — so sánh các plan theo cột, highlight plan hiện tại. |
| PM-4 | **Downgrade Conflict Dialog** — khi downgrade bị chặn, hiển thị checklist: memory count, member count, source count, credit usage vượt giới hạn mới. |
| PM-5 | **Change Confirmation** — dialog xác nhận `effective_at` (mặc định 7 ngày) hoặc immediate checkbox; hiển thị `reversible_until`. |
| PM-6 | **Subscription History** — danh sách `subscription_change` với `from_plan`, `to_plan`, `status`, `effective_at`. |

---

## 4. Admin Bulk Operations (FR-103, UX-DR-PRFAQ-5)

**Bài toán:** Superadmin/Owner thực hiện thao tác hàng loạt an toàn, có dry-run và idempotency.

| # | Trạng thái UI bắt buộc |
|---|---|
| BO-1 | **Action Selector** — dropdown `BulkAction` allow-list: `archive_inactive_workspaces`, `rotate_api_keys`, `assign_role`, `delete_source_type_memories`, `apply_tier`, `revoke_membership`. |
| BO-2 | **Structured Filter Builder** — drag-and-drop hoặc form để thêm điều kiện trên allow-list field/operator theo bảng đích (không cho phép nhập text tự do). |
| BO-3 | **Dry-Run Result Card** — hiển thị `COUNT(*)` và conflict preview, nút "Execute" disabled cho đến khi dry-run hoàn tất. |
| BO-4 | **Idempotency Key Input** — field hiển thị UUID tự sinh, cho phép user nhập hoặc copy. |
| BO-5 | **Job Polling View** — sau khi execute, hiển thị `job_id`, `status`, `affected_count`, `processed_count`, `error_count`, progress bar, và link download `bulk_op_errors`. |
| BO-6 | **High-Risk MFA Gate** — khi chọn `rotate_api_keys`, hiển thị bước xác nhận password/MFA trước khi submit. |

---

## 5. Governance & DNC Console (FR-104 phần governance, UX-DR-PRFAQ-6)

**Bài toán:** Owner cần quản lý tuỳ chọn không liên lạc (DNC) và lifecycle tài liệu theo chính sách retention.

| # | Trạng thái UI bắt buộc |
|---|---|
| GV-1 | **Governance Settings Menu** — sidebar hoặc tabs: Data Retention, DNC, Audit Log, Workspace Status. |
| GV-2 | **DNC List** — danh sách `WorkspaceDncRecord` (phone/email) với lý do, nguồn, thời gian thêm. |
| GV-3 | **DNC Add/Remove** — form thêm phone/email với reason dropdown; nút "Remove" kèm xác nhận (không xoá cứng, chỉ đảo ngược hiệu lực). |
| GV-4 | **Retention Policy Panel** — hiển thị `document_retention_days`, `auto_archive_enabled`, `document_retention_action` từ Story 28.3; chỉ Owner có thể chỉnh sửa. |
| GV-5 | **Audit Log** — bảng `audit_events` liên quan đến workspace, filter theo actor, action, date range. |
| GV-6 | **Workspace Archive/Restore** — nút "Archive workspace" chuyển `archived_at`; nút "Restore" hoàn tác trong policy cho phép. |

---

## 6. Memory Browser / Research Timeline (FR-104, UX-DR-PRFAQ-1) — Traceability Update

Tài liệu `ux-contract-readiness-gaps.md` §7.1 đã định nghĩa MB-1..MB-4. Các trạng thái này bây giờ thuộc về **Story 29.5** / **Epic 29**, không còn là `E3 (post-MVP)`. Cần cập nhật phần §8 của `ux-contract-readiness-gaps.md`.

| # | Trạng thái UI bắt buộc |
|---|---|
| MB-1 | **Research Timeline Panel** — danh sách memory theo thread, sort theo `created_at`, group theo `source_type` / `research_thread_id`. |
| MB-2 | **Source Type + Confidence Filter** — chips cho `SCRAPER_RUN`, `CHAT_TURN`, `DOCUMENT`, `CONNECTOR`; slider confidence ≥ threshold. |
| MB-3 | **Click-to-Source Citation** — click citation badge mở drawer/source panel. |
| MB-4 | **Version History Peek** — hover/long-press memory hiển thị số version và timestamp correction gần nhất. |
| MB-5 | **Flag for Review Button** — trên mỗi memory row, nút "Flag" tạo `memory_review_queue` row với reason input. |
| MB-6 | **Pagination / Cursor** — infinite scroll hoặc page size mặc định 50, có selector 25/50/100. |

---

## 7. Mapping to Stories

| Story | UX Sections | FR | AD |
|---|---|---|---|
| 29.1 | §1 | FR-100 | AD-9, AD-51 |
| 29.2 | §2 | FR-101 | AD-52 |
| 29.3 | §3 | FR-102 | AD-8, AD-53 |
| 29.4 | §4 | FR-103 | AD-54 |
| 29.5 | §6 | FR-104 | AD-11, AD-55 |
| 29.6 | §5 | FR-104 (governance) | AD-28.3, AD-55 |
