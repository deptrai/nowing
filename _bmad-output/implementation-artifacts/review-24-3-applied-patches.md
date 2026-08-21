# Story 24.3 — Applied Review Patches

This document records the code-review patches applied for **Story 24.3: Multi-Seat Team CRM Pipeline and Shared Workspace Credit Pooling**.

## 1. Backend Service — `nowing_backend/app/services/lead_assignment_service.py`

- Refactored for batch efficiency:
  - `get_eligible_members` now uses a single aggregated `COUNT` query instead of N+1 queries.
  - `assign_leads_batch` keeps an in-memory capacity counter so later leads in the batch see the updated load without an extra round-trip.
- Removed in-memory cursor fallback; the service now **requires Redis** (`redis_client`) for round-robin cursor persistence.
- Atomic capacity guard with `SELECT ... FOR UPDATE` on `WorkspaceMembership` followed by a fresh lead count.
- Inactivate/upsert `LeadAssignment`: all prior `status='assigned'` rows are inactivated before inserting the new active row.
- Skip self in reassign: `reassign_lead` rejects reassigning a lead to its current owner.
- Reject terminal/already-assigned leads in `assign_lead` (won/lost or `assigned_to_user_id is not None`).
- Manual reassignment records an audit `LeadActivityLog` with `assigned_by='manual_reassignment'` and the provided reason.

## 2. Backend Routes — `nowing_backend/app/routes/lead_pipeline_routes.py`

- `transition_lead_stage` returns **404** when the lead does not exist (instead of 409).
- 409 conflict response is flattened with `current_version`/`current_stage_id` at the top-level, plus `detail` and `error_code`.
- Batch assign (`/assign-batch`) validates:
  - `lead_ids` is non-empty.
  - No duplicate `lead_ids`.
  - Every `lead_id` exists in the workspace (missing IDs return 400).
- Manual assign/reassign route (`/{lead_id}/assign`) now receives `redis_client` via `Depends(get_redis_client)` and passes it to `LeadAssignmentService`.
- Added `LeadPipelineStageRead` import and updated response model references.
- Added role/assignment visibility helpers (`_can_view_all_leads`, `_set_lead_tenant_context`, `_require_lead_visible`) so non-admin members only see leads assigned to them.
- Removed unused `func`, `or_`, `LeadAssignment` imports; fixed ambiguous list-comp variable.

## 3. Lead Routes — `nowing_backend/app/routes/leads_routes.py`

- `list_workspace_leads`, `get_lead`, `update_lead_status`, and `get_company_graph` now enforce lead visibility:
  - Workspace owners and members with `LEADS_WRITE`/`CRM_WRITE` permissions may view all leads.
  - Other members see only `assigned_to_user_id == membership.user_id`.
- Set RLS GUCs via `set_request_tenant_context` including `app.is_lead_admin`.

## 4. Tenant Context — `nowing_backend/app/canonical/tenant_context.py`

- Added `is_lead_admin` optional parameter.
- Sets `app.is_lead_admin` GUC using `set_config`.
- Stores `is_lead_admin` in `session.info`.

## 5. Alembic Migration — `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py`

- Raw `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for `leads` / `leads_partitioned` columns (`stage_id`, `assigned_to_user_id`, `version`) to make re-runs idempotent.
- Added `CREATE INDEX IF NOT EXISTS` for the new lead columns.
- Added role/assignment RLS predicates:
  - `leads` and `lead_assignments` policy includes workspace/client tenant check **plus** (`is_lead_admin='true'` OR `assigned_to_user_id == current_user_id`).
  - `lead_activity_logs` policy uses `EXISTS (SELECT 1 FROM leads ... assigned_to_user_id == current_user_id)` for non-admin visibility.
  - `lead_pipeline_stages` keeps the workspace/client tenant predicate.
- `downgrade` drops the new lead policies and reverts `leads` to the workspace-only RLS.

## 6. Frontend Kanban Board — `nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx`

- `loadData` now explicitly handles errors and shows a `conflictNotice` message instead of silently swallowing the exception.
- 409 merge reads `err.data.current_version` / `err.data.current_stage_id` with fallback to `err.data.detail.current_version` / `err.data.detail.current_stage_id`.
- After a 409 conflict the board now updates `version`, `stage_id`, and `status` (status derived from the remote stage slug when available).
- Conflict notice copy updated to indicate the state has been refreshed.

## 7. Member Spend Cap Dialog — `nowing_web/components/team/MemberSpendCapDialog.tsx`

- Rejects fractional and non-integer spend caps and lead capacities (`Number.isInteger`).
- Shows backend `detail` / `message` in the toast instead of a generic failure message.
- Restructured cap parsing to keep `capMicros` typed as `number | null` and avoid TS null narrowing issues.

## 8. Lead Detail Flyout Drawer — `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx`

- Added `timelineError` state.
- Timeline load failures now surface an inline error message with the backend detail instead of silently clearing the list.
- `timelineError` is reset on each drawer open.

## 9. E2E Test — `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts`

- Uses `storageState` from `playwright/.auth/user.json` for both browser contexts.
- Asserts the lead card is visible on both clients before dragging.
- Performs a first drag from client A, waits for Zero sync to client B, then forces an OCC conflict by moving the lead via the backend API, and performs a second drag from client B.
- Asserts the conflict toast is visible.
- Opens the flyout drawer and asserts the activity timeline is rendered.

## 10. Masothue Parser — `nowing_backend/app/proprietary/platforms/masothue/parsers.py`

- Verified the district fallback already uses the correct `i + 1 < len(parts)` guard at line 225; the `i + 0` regression was not present in the working tree, so no code change was required.

## 11. Mutation Gate Script — `scripts/mutation-gate.py`

- Fixed the `cosmic-ray exec` check at line 329 so a non-zero exit code from `cosmic-ray exec` now raises `RuntimeError` instead of being silently ignored.
- Removed an extraneous set of parentheses flagged by `ruff`.

## 12. Unit Tests — `nowing_backend/tests/unit/services/test_lead_assignment.py`

- Rewrote the test suite to exercise the new service implementation with a robust `FakeSession` / `FakeRedis` setup.
- Added coverage for:
  - round-robin even distribution,
  - skipping inactive/paused members,
  - skipping members at capacity,
  - Redis cursor persistence across service instances,
  - no-eligible-member rejection,
  - terminal/assigned lead rejection,
  - batch distribution,
  - manual reassignment + audit log + inactivation of prior assignments,
  - self-reassign rejection,
  - missing Redis rejection.

## 13. Verification Results

```bash
# Backend linting
uv run ruff check \
  app/services/lead_assignment_service.py \
  app/routes/lead_pipeline_routes.py \
  app/routes/leads_routes.py \
  app/canonical/tenant_context.py \
  alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py \
  tests/unit/services/test_lead_assignment.py \
  ../scripts/mutation-gate.py
# -> All checks passed

# Backend tests
uv run pytest \
  tests/unit/services/test_lead_assignment.py \
  tests/unit/services/test_workspace_credit_pooling.py \
  tests/unit/services/test_billing_event_service.py \
  tests/unit/capabilities/test_billing.py -q
# -> 131 passed

# Frontend typecheck
pnpm tsc --noEmit
# -> Exit 0

# Frontend lint/format
pnpm exec biome check \
  components/leads/pipeline/LeadKanbanBoard.tsx \
  components/team/MemberSpendCapDialog.tsx \
  components/leads/LeadDetailFlyoutDrawer.tsx \
  tests/zero/kanban-multicontext-sync.spec.ts
# -> All checks passed
```

## Notes

- Files explicitly **not** re-patched (per earlier instructions): `workspace_credit_service.py`, `billing_event_service.py`, `capabilities/core/billing.py`.
- The E2E spec intentionally uses a single authenticated user in both contexts; real multi-user membership is not exercised because the workspace-invite helpers were not available in the test tree.
- The new `leads` RLS predicate relies on the `app.is_lead_admin` and `app.current_user_id` GUCs; these are set by the updated `set_request_tenant_context` and by the lead route helpers.
