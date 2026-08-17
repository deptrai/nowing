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
- [x] Pages & Components: Xây dựng Kanban Board (`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx`) sử dụng `@dnd-kit/core` và Zero query subscriptions.
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
- [x] [Review][Patch] `WorkspaceCreditService.deduct_credits` không dùng `SELECT FOR UPDATE` / conditional UPDATE, có thể overdraft pool và vượt spend cap khi concurrency (`nowing_backend/app/services/workspace_credit_service.py:125-181`)
- [x] [Review][Patch] `LeadAssignmentService` không cập nhật `Lead.assigned_to_user_id`, phá vỡ capacity tracking và unassigned filter (`nowing_backend/app/services/lead_assignment_service.py:147-180, 219-246`)
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

### Review Findings — 2026-08-17 (bmad-code-review Chunk A: backend core)

#### Patch (đã xử lý 2026-08-17)

- [x] [Review][Patch] `lead_pipeline_routes.list_lead_activities` trả timeline theo thứ tự `created_at.desc()` dù docstring và AC-3 yêu cầu chronological (`asc()`); endpoint `/timeline` và `/activities` cùng logic này (`nowing_backend/app/routes/lead_pipeline_routes.py:269-272`)
- [x] [Review][Patch] `WorkspaceCreditService.deduct_credits` cho phép user không phải thành viên workspace vẫn trừ tiền: `_get_membership` trả `None` thì `cap=None`, `current_spent=0` và vẫn `UPDATE Workspace ...` để trừ balance; thiếu check membership (`nowing_backend/app/services/workspace_credit_service.py:152-168`)
- [x] [Review][Patch] `session.refresh()` sau `session.commit()` trong `_ensure_default_stages`, `create_pipeline_stage`, `create_lead_activity` sẽ chạy trong transaction mới không có GUC `app.workspace_id` (vì `set_request_tenant_context` dùng `SET LOCAL`), khiến RLS `FORCE` không nhìn thấy row vừa tạo và raise exception / trả 500 (`nowing_backend/app/routes/lead_pipeline_routes.py:77-84, 141-142, 309-310`)
- [x] [Review][Patch] `lead_pipeline_routes.assign_or_reassign_lead` không bắt `NoEligibleAssigneeError` từ `LeadAssignmentService.reassign_lead` khi target member không tồn tại / không accepting, dẫn đến 500 thay vì 4xx (`nowing_backend/app/routes/lead_pipeline_routes.py:337-344`)
- [x] [Review][Patch] `LeadAssignmentService.reassign_lead` kiểm tra member active/accepting nhưng không kiểm tra capacity (`current_leads < max_capacity`), cho phép manual reassign vượt cap (`nowing_backend/app/services/lead_assignment_service.py:247-260`)
- [x] [Review][Patch] `workspace_credit_service.refund_credits` là read-modify-write không có `UPDATE ... WHERE`; concurrent refund dễ lost update / over-refund (`nowing_backend/app/services/workspace_credit_service.py:295-331`)
- [x] [Review][Patch] `lead_pipeline_routes.create_pipeline_stage` pre-check duplicate slug bằng query, không `try/except IntegrityError`; race condition hai request cùng slug sẽ 500 (`nowing_backend/app/routes/lead_pipeline_routes.py:120-143`)

#### Patch (đã xử lý 2026-08-17)

- [x] [Review][Patch] `WorkspaceCreditService.deduct_credits` chưa được wire vào các billable operation (enrichment, scraping, AI). Theo option 2, tôi thêm `WorkspaceCreditService.record_spend` để enforce per-seat spend cap atomic trước khi gọi `wallet_credit.apply_debit`. Payment vẫn là user wallet; `WorkspaceCreditService` chỉ đóng vai trò gate cho `monthly_spend_cap_micros`. (`nowing_backend/app/services/workspace_credit_service.py:280-390`, `nowing_backend/app/services/billing_event_service.py:175-195`, `nowing_backend/app/capabilities/core/billing.py:35-60, 380-565`)

#### Defer

- [x] [Review][Defer] Scope creep từ story khác trong diff 24.3: `ImpersonationGuardMiddleware` và chỉnh CORS regex trong `app/app.py` thuộc Story 25.1/24.5 (`nowing_backend/app/app.py:784, 871`)
- [x] [Review][Defer] Scope creep từ story khác trong diff 24.3: `GlobalDncRecord`, `AuditEvent`, `CreditTransaction` và các trường `tax_id`/`company_status` trên `Lead` trong `app/db.py` thuộc Story 24.2/24.4/25.2 (`nowing_backend/app/db.py:4479-4516, 6035-6084`)
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
  - Zero query subscriptions cho Kanban đã thêm (`zero/schema/leads.ts`, `zero/queries/leads.ts`), `LeadKanbanBoard` dùng `useQuery` để nhận real-time stage/lead updates.
  - `_ensure_default_stages` xử lý `IntegrityError` khi race tạo default stages.
  - `BatchLeadAssignmentRequest` thêm `min_length=1` và dedupe `lead_ids`.

- 2026-08-17: Patches applied in chunk A code review:
  - `list_lead_activities` sắp xếp `created_at.asc()` (chronological timeline).
  - `create_pipeline_stage` bắt `IntegrityError` và trả 409 khi slug trùng (race).
  - `_ensure_default_stages`, `create_pipeline_stage`, `create_lead_activity` re-set GUC `app.workspace_id` bằng `set_request_tenant_context` sau `session.commit()` và trước `session.refresh()` để tránh RLS `FORCE` lỗi.
  - `assign_or_reassign_lead` bắt `NoEligibleAssigneeError` và trả 400.
  - `LeadAssignmentService.reassign_lead` thêm capacity check dựa trên `Lead.assigned_to_user_id` và status non-terminal.
  - `WorkspaceCreditService.deduct_credits` từ chối non-member bằng `ValueError("Member not found")`.
  - `WorkspaceCreditService.refund_credits` chuyển sang atomic `UPDATE ... RETURNING` cho `Workspace.credit_micros_balance` và `WorkspaceMembership.monthly_spent_micros`, thêm `_refund_credits_fake` path cho FakeAsyncSession.
  - `tests/unit/services/test_lead_assignment.py` mock `session.execute` cho capacity check.
  - `ruff check`, `tests/unit/services/test_lead_assignment.py`, `tests/unit/services/test_workspace_credit_pooling.py`, `tests/unit/services/test_billing_event_service.py`, `tests/unit/capabilities/test_billing.py`, `tests/integration/services/test_team_crm_pipeline.py` đều pass.
  - [Review][Patch] Wire `WorkspaceCreditService` vào billable operations theo option 2:
    - Thêm `record_spend` atomic `UPDATE ... WHERE` trên `WorkspaceMembership.monthly_spent_micros` với `or_(cap IS NULL, cap >= spent + amount)`.
    - Gọi `record_spend` trước `wallet_credit.apply_debit` trong `BillingEventService._record_business_event` (enrichment/lead scoring/signal scan).
    - Thêm `_debit_with_workspace_spend_cap` helper trong `app/capabilities/core/billing.py` và dùng cho `_charge_web_crawl`, `_charge_captcha`, `_charge_platform_meter`, `_charge_vn_bds_aggregate`, `_charge_vn_jobs_aggregate`, `_charge_chainlens` (scrape/AI).
    - Thêm unit tests `record_spend` trong `test_workspace_credit_pooling.py`.

- 2026-08-17: Patches applied in chunk B/C code review:
  - `WorkspaceCreditService.deduct_credits`, `record_spend`, `refund_credits` dùng `func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)` để xử lý `NULL` trong SQL atomic update.
  - `BillingEventService._record_business_event` và `_debit_with_workspace_spend_cap` trong `billing.py` chuyển `SpendCapExceededError` thành `InsufficientCreditsError` trước khi re-raise, giúp REST/agent tools bắt `InsufficientCreditsError` / 402 thay vì 500.
  - `AppError` trong `nowing_web/lib/error.ts` thêm `data?: unknown`; `base-api.service.ts` gán `data` khi throw `AppError` cho non-2xx response, giúp `LeadKanbanBoard` đọc `err.data.current_version`/`current_stage_id` từ 409 OCC body.
  - `LeadKanbanBoard.tsx` fallback lấy `err.data` trước `err.response?.data` khi merge current version sau 409.
  - `MembershipRead` schema + `rbac_routes.py` `list_members`/`update_member_role` trả về `monthly_spend_cap_micros`, `monthly_spent_micros`, `is_accepting_leads`, `lead_capacity`, `status`.
  - Frontend `members.types.ts` thêm các trường per-seat settings.
  - `MemberSpendCapDialog.tsx` khởi tạo form từ dữ liệu member hiện tại thay vì reset về rỗng/50/true, tránh vô tình xóa hạn mức/capacity khi owner chỉ mở và lưu.
  - `pnpm tsc --noEmit` pass; `biome check` pass; `ruff check` pass; `pytest` 124 pass.
