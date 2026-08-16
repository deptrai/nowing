---
story_key: "24-3"
epic: "epic-24"
story: "24.3"
title: "Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling"
status: "ready-for-dev"
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
- [ ] Alembic Migration: Bổ sung `credit_micros_balance` vào `workspaces`; thêm `monthly_spend_cap_micros`, `monthly_spent_micros` vào `workspace_memberships`.
- [ ] Schema: Tạo bảng `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs` với Composite PK `(id, workspace_id)` và publication vào `zero_publication`.
- [ ] Service: Xây dựng `LeadAssignmentService` (`nowing_backend/app/services/lead_assignment_service.py`) với Round-Robin Redis cursor.

### Frontend Implementation
- [ ] Pages & Components: Xây dựng Kanban Board (`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx`) sử dụng `@dnd-kit/core` và Zero query subscriptions.
- [ ] Workspace Settings: Bổ sung giao diện phân bổ hạn mức tín dụng (Spend Cap Manager) trong cài đặt thành viên.

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
