---
story_key: "24-3"
epic: "epic-24"
story: "24.3"
title: "Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling"
coverageBasis: acceptance_criteria
oracleResolutionMode: formal_requirements
oracleConfidence: high
oracleSources:
  - _bmad-output/implementation-artifacts/stories/24-3-multi-seat-team-crm-pipeline-and-shared-credits.md
externalPointerStatus: not_used
trace_date: 2026-08-21
evaluator: Luisphan
---

# Traceability Matrix — Story 24.3

## Test Evidence Summary (2026-08-21)

| Check | Command / File | Result |
|-------|----------------|--------|
| Backend unit tests | `uv run pytest tests/unit/services/test_lead_assignment.py tests/unit/services/test_workspace_credit_pooling.py tests/unit/services/test_billing_event_service.py tests/unit/capabilities/test_billing.py -q` | **127 passed** |
| Backend integration tests | `uv run pytest tests/integration/routes/test_kanban_concurrency.py tests/integration/services/test_team_crm_pipeline.py tests/integration/services/test_credit_deduction_race.py -q` | **9 passed** |
| Backend lint | `uv run ruff check app/services/lead_assignment_service.py app/services/workspace_credit_service.py app/services/workspace_limits.py app/routes/lead_pipeline_routes.py app/schemas/lead_pipeline.py tests/unit/services/test_lead_assignment.py tests/unit/services/test_workspace_credit_pooling.py` | **All checks passed** |
| Frontend typecheck | `pnpm tsc --noEmit` (from `nowing_web/`) | **Exit 0, no output** |
| Frontend lint | `pnpm exec biome check components/leads/pipeline/ app/dashboard/\[workspace_id\]/leads/pipeline/` | **Checked 2 files, no fixes applied** |

## Traceability Table

| AC | Requirement | Implementation File(s) | Test File(s) | Test Status | Notes |
|----|-------------|------------------------|--------------|-------------|-------|
| **AC-1** | Reactive Kanban board at `/dashboard/[workspace_id]/leads/pipeline` with default 5 stages (`Mới săn`, `Đang tiếp cận`, `Tiềm năng`, `Đã chốt`, `Hủy / Không nhu cầu`), drag-and-drop synced via Zero-cache, and OCC `version` column returning `409 Conflict` on simultaneous drag collisions and rolling back conflicting client state without corruption. | `nowing_web/app/dashboard/[workspace_id]/leads/pipeline/page.tsx` (renders `LeadKanbanBoard`)<br>`nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:1-555` (`@dnd-kit/core`, `useQuery` from Zero, optimistic UI rollback, 409 conflict merge, `data-testid`)<br>`nowing_web/lib/apis/lead-pipeline-api.service.ts:17-42` (`listStages`, `transitionStage`)<br>`nowing_web/zero/queries/leads.ts` and `nowing_web/zero/schema/leads.ts` (Zero subscriptions)<br>`nowing_backend/app/routes/lead_pipeline_routes.py:48-54` (default stages), `:96-109` (`list_pipeline_stages`), `:161-257` (`transition_lead_stage` with atomic `UPDATE ... WHERE version`)<br>`nowing_backend/app/db.py:4822-4830` (`Lead.stage_id`, `version`), `:4923-4968` (`LeadPipelineStage` composite PK) | `tests/integration/routes/test_kanban_concurrency.py:26-177` (default stages, OCC 409, retry, timeline, cross-workspace)<br>`tests/integration/services/test_team_crm_pipeline.py:27-75` (OCC conflict / success schemas)<br>`nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` (Playwright E2E, not executed) | **pass** (backend integration + unit); E2E spec **not run** | Integration asserts 409, version increment, and retry. E2E spec exists but not executed in this session. Zero real-time sync is exercised via unit/integration of backend; multi-client drag simulation relies on Playwright. |
| **AC-2** | Automated dynamic Round-Robin lead assignment for newly imported leads. `LeadAssignmentService` queries active members (`status='ACTIVE' AND is_accepting_leads=TRUE AND current_leads < capacity`), distributes evenly via Redis cursor, and skips deactivated accounts. Triggers automatically from scrapers, chat/social stream, and clipper imports. | `nowing_backend/app/services/lead_assignment_service.py:64-316` (`get_eligible_members`, `assign_lead`, `assign_leads_batch`, `reassign_lead`)<br>`nowing_backend/app/routes/lead_pipeline_routes.py:334-429` (`assign_or_reassign_lead`, `assign_leads_batch`)<br>`nowing_backend/app/db.py:2875-2886` (`WorkspaceMembership.is_accepting_leads`, `lead_capacity`, `status`)<br>`nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:284-317` (auto-assign after batch import)<br>`nowing_backend/app/routes/lead_clipper_routes.py:263-281` (auto-assign clipped lead)<br>`nowing_backend/app/tasks/social_stream_worker.py:257-270` (auto-assign chat/social lead)<br>`nowing_backend/app/schemas/lead_pipeline.py:80-93` (`BatchLeadAssignmentRequest` with `min_length=1` and dedupe) | `tests/unit/services/test_lead_assignment.py:142-401` (round-robin even distribution, skip inactive/paused, capacity, Redis cursor, batch, manual reassign) | **pass** (unit) | Unit tests cover all eligibility rules and Redis monotonic cursor. Auto-trigger wiring is implemented in production code but not covered by an integration test that spans scraper → assignment; `FakeRedis` used in unit tests does not verify multi-worker fairness. |
| **AC-3** | Lead interaction timeline in the Flyout Detail Drawer renders a chronological list of all interactions (`Scraped`, `Zalo Sent`, `Inbound Reply`, `Internal Notes`, `Stage Changed`). | `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx:325-408` (timeline UI, `listActivities` call, `internal_note` form)<br>`nowing_backend/app/routes/lead_pipeline_routes.py:259-331` (`list_lead_activities` with `/timeline` and `/activities`, `created_at.asc()`; `create_lead_activity`)<br>`nowing_backend/app/services/lead_assignment_service.py:177-188` (writes `assigned` log)<br>`nowing_backend/app/routes/lead_pipeline_routes.py:232-247` (writes `stage_changed` log)<br>`nowing_backend/app/db.py:5044-5102` (`LeadActivityLog` composite PK) | `tests/integration/routes/test_kanban_concurrency.py:137-161` (`test_kanban_timeline_activity_logs_chronological`)<br>`tests/integration/services/test_team_crm_pipeline.py:67-75` (`test_timeline_activity_schema_validation`) | **pass** (integration) | Endpoint returns `/timeline` with `ORDER BY created_at ASC` and an `/activities` alias. Integration test asserts endpoint returns 200; no explicit test asserts ordering of mixed activity types in the response body. |
| **AC-4** | Shared workspace credit wallet with atomic per-seat spend caps. `WorkspaceCreditService` checks `monthly_spend_cap_micros` atomically; if exceeded raises `SpendCapExceededError` and preserves the shared `Workspace.credit_micros_balance`. Wired into billable operations (enrichment, scraping, AI) through `record_spend`. | `nowing_backend/app/services/workspace_credit_service.py:121-246` (`deduct_credits`, atomic balance + spend cap)<br>`:294-387` (`record_spend`, atomic per-seat cap without touching pool)<br>`:425-489` (`refund_credits`)<br>`:582-625` (`set_member_spend_cap`, `get_member_spend_status`)<br>`nowing_backend/app/db.py:1928-1933` (`Workspace.credit_micros_balance`), `:2875-2879` (`WorkspaceMembership` cap/spent fields)<br>`nowing_backend/app/services/billing_event_service.py:814-833` (`_record_business_event` calls `record_spend` before `wallet_credit.apply_debit`)<br>`nowing_backend/app/capabilities/core/billing.py:36-71` (`_debit_with_workspace_spend_cap`) and call sites `:416`, `:441`, `:562`, `:815`, `:858`, `:901` (scrape/AI/web-crawl charges)<br>`nowing_backend/app/routes/lead_pipeline_routes.py:430-529` (member spend/lead capacity routes)<br>`nowing_web/components/team/MemberSpendCapDialog.tsx:1-155` (Spend Cap Manager UI) | `tests/unit/services/test_workspace_credit_pooling.py:191-542` (deduct, cap, refund, `record_spend`, status, edge cases)<br>`tests/integration/services/test_credit_deduction_race.py:93-211` (concurrent pool overdraft and spend-cap races)<br>`tests/unit/services/test_billing_event_service.py:313-410` (asserts `record_spend` called before debit, refund on debit failure)<br>`tests/unit/capabilities/test_billing.py` (billing math; stubs `record_spend`) | **pass** (unit + integration) | Race integration proves no overdraft and cap enforcement under 10/5 concurrent tasks. `tests/unit/capabilities/test_billing.py` stubs `record_spend`, so end-to-end cap enforcement through actual billable operations is not directly asserted in unit form. |
| **INV-24.4** | Team credit pooling and atomic quota locks: row-level atomic `UPDATE ... WHERE` on `Workspace.credit_micros_balance` and `WorkspaceMembership.monthly_spent_micros`. | Same as AC-4 implementation files, especially `workspace_credit_service.py:163-207` and `:347-372` | `tests/integration/services/test_credit_deduction_race.py:93-211` | **pass** | Verified concurrently via integration race tests. |
| **INV-23.4** | Composite primary key `(id, workspace_id)` for `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs`. | `nowing_backend/app/db.py:4928` (`LeadPipelineStage` PK), `:4976` (`LeadAssignment` PK), `:5049` (`LeadActivityLog` PK)<br>`nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:112-260` (CREATE TABLE with composite PK) | `tests/integration/routes/test_kanban_concurrency.py:164-177` (`test_kanban_cross_workspace_isolation_fail_closed`) | **pass** (implicit) | Composite PK is enforced in schema and migrations; cross-workspace isolation test exercises the tenant boundary. |
| **INV-23.6** | Fail-closed RLS: members see only leads/stages/assignments/activity for their workspace, and role-based visibility. | `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:261-302` (`ENABLE RLS`, `FORCE RLS`, tenant + `client_id` policies)<br>`nowing_backend/app/routes/lead_pipeline_routes.py` (`check_workspace_access`, `set_request_tenant_context`) | `tests/integration/routes/test_kanban_concurrency.py:164-177` (`test_kanban_cross_workspace_isolation_fail_closed`) | **pass** | Route-level workspace access check and RLS `FORCE` policies are both in place. Negative auth path coverage is light (single 403/404 test). |

## Coverage / Quality Gate Decision

- **Decision:** `PASS with CONCERNS`
- **Rationale:**
  - All 4 acceptance criteria have passing unit and/or integration tests.
  - Backend lint (`ruff`), frontend typecheck (`tsc --noEmit`), and frontend lint (`biome`) all pass.
  - 9 integration tests and 127 unit tests passed in this session.
- **Remaining concerns / missing coverage:**
  1. **Playwright E2E** (`nowing_web/tests/zero/kanban-multicontext-sync.spec.ts`) was not executed in this session; it covers the multi-client Zero-cache sync and drag-and-drop conflict UI path.
  2. **Auto-trigger integration:** no end-to-end test currently proves scraper/chat/clipper → `assign_leads_batch` round-robin assignment in a real database.
  3. **Multi-worker Round-Robin fairness:** unit tests use `FakeRedis`; production multi-instance cursor fairness is assumed by `redis.incr()` but not load-tested.
  4. **Actual billable-operation spend-cap enforcement** is wired but the unit tests in `tests/unit/capabilities/test_billing.py` mock `record_spend`; a real integration test of scraping/AI charging against a capped member is absent.
  5. **Negative auth/RLS paths** are present in code but only minimally tested (single cross-workspace 403/404 case).

## Next steps in Nowing quality pipeline

**Vừa xong:** `bmad-testarch-trace` — Tạo traceability matrix cho Story 24.3 và xác nhận tất cả backend unit/integration tests pass.

**Bước tiếp theo (BẮT BUỘC):**
- [4.13] `bmad-nowing-human-review-gate` — Human review gate cho P0 areas (credit/spend cap, auth/RLS pipeline).

**Bước tiếp theo (recommended):**
- [4.12] `bmad-testarch-nfr` — Kiểm tra NFR evidence (concurrency, Zero sync, multi-worker fairness) *(skip nếu đã có bằng chứng riêng)*.
- [4.14] `bmad-nowing-web-e2e-gate` — Chạy Playwright E2E `tests/zero/kanban-multicontext-sync.spec.ts` trước release UI *(skip nếu không đổi UI/response shape)*.

**Còn lại trong pipeline:** human review gate, E2E gate, sau đó epic retrospective (4.17) — xem `nowing-quality-pipeline.md`.
