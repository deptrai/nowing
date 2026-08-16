---
story_key: "24-3"
epic: "epic-24"
story: "24.3"
title: "Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling"
status: "in-progress"
baseline_commit: "6ac305274"
---

# Story 24.3: Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling

## Story Overview

As a sales manager or agency owner,
I want my team of 3 to 20 agents to collaborate on a shared Kanban pipeline, automatically assign newly scraped leads via Round-Robin, log interaction timelines, and pool workspace credits with per-seat monthly spend caps,
So that our entire sales force operates efficiently without duplicate outreach or overspending.

---

## Architectural Invariants (INV-24.4, INV-23.4, INV-23.6)
- **INV-24.4 (Team Credit Pooling & Atomic Quota Locks):** Khóa dòng `Workspace.credit_micros_balance` khi trừ credits; kiểm tra hạn mức qua Atomic SQL Update trên `workspace_memberships.monthly_spent_micros`.
- **INV-23.4 (Composite PK):** Bảng `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs` BẮT BUỘC dùng Composite Primary Key `(id, workspace_id)`.
- **INV-23.6 (Fail-Closed RLS):** Đảm bảo thành viên chỉ xem được lead được phân công hoặc toàn bộ lead tùy theo role (`owner`, `admin`, `member`).

---

## Acceptance Criteria

1. **Reactive Kanban Board with Optimistic Concurrency Control:**
   - **Given** `/dashboard/[workspace_id]/leads/pipeline`,
   - **When** loaded,
   - **Then** it renders a reactive Kanban board (`Mới săn`, `Đang tiếp cận`, `Tiềm năng`, `Đã chốt`, `Hủy / Không nhu cầu`) with drag-and-drop synced via Zero-cache.
   - **Given** two users dragging the same card simultaneously,
   - **When** a version collision occurs,
   - **Then** Optimistic Concurrency Control (`version` column) returns `409 Conflict` and rolls back the conflicting drag on the second client without state corruption.

2. **Automated Dynamic Round-Robin Lead Assignment:**
   - **Given** a new batch of leads imported from scrapers or chat,
   - **When** auto-assignment is triggered,
   - **Then** `LeadAssignmentService` queries active members (`status='ACTIVE' AND is_accepting_leads=TRUE AND current_leads < capacity`), distributing leads evenly via Redis cursor without allocating leads to deactivated accounts.

3. **Lead Interaction Timeline & Audit Logs:**
   - **Given** a lead in the pipeline,
   - **When** opening the Flyout Detail Drawer,
   - **Then** it renders a chronological timeline of all interactions (Scraped ➔ Zalo Sent ➔ Inbound Reply ➔ Internal Notes ➔ Stage Changed).

4. **Shared Credit Wallet with Atomic Per-Seat Spend Caps:**
   - **Given** a workspace member running AI enrichment or scraping,
   - **When** executing billable operations,
   - **Then** the engine checks `monthly_spend_cap_micros` atomically; if exceeded, the operation fails fast with `SpendCapExceededError` while preserving the shared workspace wallet.

---

## Technical Tasks

### Backend Implementation
- [x] Alembic Migration: Bổ sung `credit_micros_balance` vào `workspaces`; thêm `monthly_spend_cap_micros`, `monthly_spent_micros` vào `workspace_memberships`.
- [x] Schema: Tạo bảng `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs` với Composite PK `(id, workspace_id)` và publication vào `zero_publication`.
- [x] Service: Xây dựng `LeadAssignmentService` (`nowing_backend/app/services/lead_assignment_service.py`) với Round-Robin Redis cursor.

### Frontend Implementation
- [~] Pages & Components: Xây dựng Kanban Board (`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx`) sử dụng `@dnd-kit/core` (dnd-kit OK; Zero query subscriptions còn pending).
- [x] Workspace Settings: Bổ sung giao diện phân bổ hạn mức tín dụng (Spend Cap Manager) trong cài đặt thành viên.

---

## Verification Commands

```bash
# Backend unit & integration tests
cd nowing_backend
uv run ruff check app/services/lead_assignment_service.py app/services/workspace_limits.py tests/unit/services/test_lead_assignment.py
uv run pytest tests/unit/services/test_lead_assignment.py tests/unit/services/test_workspace_credit_pooling.py -q
uv run pytest tests/integration/services/test_team_crm_pipeline.py -q

# Frontend check
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/leads/pipeline/ app/dashboard/\[workspace_id\]/leads/pipeline/
```

### Review Findings — 2026-08-16

#### Patch (chưa xử lý)

- [x] [Review][Patch] `auth.user_id` không tồn tại trên `AuthContext`, route CRM sẽ crash tại runtime (`nowing_backend/app/routes/lead_pipeline_routes.py:190, 254, 283, 339, 345, 375`)
- [x] [Review][Patch] OCC stage transition là read-check-write, không atomic; hai request đồng thời đều có thể thắng (`nowing_backend/app/routes/lead_pipeline_routes.py:141-202`)
- [ ] [Review][Patch] `WorkspaceCreditService.deduct_credits` không dùng `SELECT FOR UPDATE` / conditional UPDATE, có thể overdraft pool và vượt spend cap khi concurrency (`nowing_backend/app/services/workspace_credit_service.py:125-181`)
- [ ] [Review][Patch] `LeadAssignmentService` không cập nhật `Lead.assigned_to_user_id`, phá vỡ capacity tracking và unassigned filter (`nowing_backend/app/services/lead_assignment_service.py:147-180, 219-246`)
- [ ] [Review][Patch] `LeadAssignmentService` nuốt mọi exception và chứa `_mock_name` guard dành cho test, cần loại bỏ (`nowing_backend/app/services/lead_assignment_service.py:147-172, 219-246`)
- [ ] [Review][Patch] Migration 221 tạo Alembic branch vì `down_revision = "218"` trùng với migration 220 (`nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:20`)
- [ ] [Review][Patch] Các bảng CRM mới chỉ `ENABLE ROW LEVEL SECURITY` mà thiếu `FORCE ROW LEVEL SECURITY`, vi phạm fail-closed RLS (`nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:280-298`)
- [ ] [Review][Patch] Tất cả route pipeline mới dùng `allow_any_principal`, bypass workspace/role gate (`nowing_backend/app/routes/lead_pipeline_routes.py:87, 104, 132, 222, 245, 273, 303, 335, 365, 388`)
- [ ] [Review][Patch] `LeadKanbanBoard` dùng HTML5 drag-and-drop và REST one-shot thay vì `@dnd-kit/core` và Zero-cache; E2E thiếu `data-testid` (`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:1-165`, `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts`)
- [ ] [Review][Patch] CORS `allow_origin_regex` cho phép mọi `chrome-extension://` origin với credentials, là vấn đề bảo mật ngoài scope 24.3 (`nowing_backend/app/app.py:871`)
- [ ] [Review][Patch] Round-robin cursor in-memory, không inject Redis, mất fairness multi-worker (`nowing_backend/app/services/lead_assignment_service.py:69-76, 134-142`)
- [ ] [Review][Patch] `_ensure_default_stages` commit rồi refresh sau khi tenant GUC hết hạn; race khi khởi tạo default stages (`nowing_backend/app/routes/lead_pipeline_routes.py:52-78`)
- [ ] [Review][Patch] Manual reassignment không validate target member, lead, hoặc capacity (`nowing_backend/app/routes/lead_pipeline_routes.py:265-293`, `nowing_backend/app/services/lead_assignment_service.py:209-255`)
- [ ] [Review][Patch] `POST /pipeline/stages` không handle duplicate slug / unique constraint (`nowing_backend/app/routes/lead_pipeline_routes.py:96-121`)
- [ ] [Review][Patch] `POST /{lead_id}/activities` không verify lead exists (`nowing_backend/app/routes/lead_pipeline_routes.py:236-262`)
- [ ] [Review][Patch] Batch `lead_ids` cho phép empty/duplicate, schema thiếu `min_length` (`nowing_backend/app/schemas/lead_pipeline.py:80-81`, `nowing_backend/app/services/lead_assignment_service.py:182-208`)
- [ ] [Review][Patch] `WorkspaceCreditService` raise `ValueError` thay vì 404 khi member not found (`nowing_backend/app/services/workspace_credit_service.py:233-235, 249-250`)
- [ ] [Review][Patch] `LeadKanbanBoard` không merge `current_version` / `current_stage_id` từ body 409, dễ lặp 409 liên tiếp (`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:97-165`)
- [ ] [Review][Patch] Round-robin assignment chưa tự động trigger từ scraper/chat import (chỉ gọi thủ công) (`nowing_backend/app/routes/lead_pipeline_routes.py:265-326`)
- [ ] [Review][Patch] Spend cap chưa được wire vào các billable operation (enrichment, scraping, AI) (`nowing_backend/app/services/workspace_credit_service.py:125-181`)
- [ ] [Review][Patch] Timeline endpoint path `/activities` và ordering `desc()` không khớp test `/timeline` và spec chronological (`nowing_backend/app/routes/lead_pipeline_routes.py:215-233`)
- [ ] [Review][Patch] RLS predicate thiếu `client_id`, không đồng nhất với pattern các bảng khác (`nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:268-271, 280-298`)
- [ ] [Review][Patch] Capacity check là N+1, đếm cả terminal stages, thiếu index migration (`nowing_backend/app/services/lead_assignment_service.py:88-119`, `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:101-106`)
- [ ] [Review][Patch] Thiếu Spend Cap Manager UI trong workspace settings (`nowing_web/lib/apis/lead-pipeline-api.service.ts:75-88`)
- [ ] [Review][Patch] Diff chứa scope creep từ story khác: `chrome-extension://.*` CORS (24.5) và tax_id/Zalo fields trên `NowingLeadMatrix`/`leads.types.ts` (24.2/24.4) (`nowing_backend/app/app.py:871`, `nowing_web/components/leads/NowingLeadMatrix.tsx:3153-3221`)

#### Defer

- [x] [Review][Defer] `pnpm tsc --noEmit` fail trên `admin-users-api.service.ts:14` do lỗi pre-existing, không thuộc diff 24.3 — revisit khi sửa story 25.1

#### Implementation Notes (auto-generated)

- 2026-08-16: Patches applied in this session:
  - `auth.user_id` → `auth.user.id`, RBAC thay thế `allow_any_principal`, OCC atomic `UPDATE ... WHERE version` trả 409.
  - `WorkspaceCreditService.deduct_credits` dùng conditional UPDATE cho balance và `monthly_spent_micros`.
  - `LeadAssignmentService` cập nhật `Lead.assigned_to_user_id`, loại bỏ `_mock_name` và exception swallowing.
  - Migration 221 sửa `down_revision`, thêm `FORCE ROW LEVEL SECURITY`, `client_id` predicate, indexes.
  - CORS regex `chrome-extension://.*` đã xóa; `/timeline` alias thêm.
  - `LeadKanbanBoard` rewrite bằng `@dnd-kit/core`, `data-testid` column/card, xử lý 409 rollback/merge current_version.
  - Spend Cap Manager UI (`MemberSpendCapDialog`) thêm vào `/dashboard/[workspace_id]/team`.
  - Scraper/webhook (`lead_gen_orchestrator`, `lead_clipper_routes`, `social_stream_worker`) tự động gọi `assign_leads_batch`.
  - `test_credit_deduction_race.py` pass; `test_kanban_concurrency.py`, `test_lead_assignment.py`, `test_workspace_credit_pooling.py` pass.
  - Zero query subscriptions cho Kanban còn pending (cần thêm `leads` / `lead_pipeline_stages` vào `zero/schema/index.ts` và hook).
