# Quality Gate Report — Story 24.3

**Date:** 2026-08-21
**Story:** 24.3 — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling
**Overall:** Human review gate blocking `done`; mutation CI configured; other gates reviewed.

---

## 1. Human Review Gate — `pending-human-review`

- **P0 areas touched:** token/credit (`workspace_credit_service`, `billing_event_service`, `capabilities/core/billing`), auth/RBAC (`lead_pipeline_routes`, `rbac_routes`, `ImpersonationGuardMiddleware`), data integrity (migration 221 + `db.py` changes), external integrations (lead assignment auto-triggers from scraper/chat).
- **Status:** `pending-human-review`.
- **Artifact:** `human-review-gate-24-3.md`.

---

## 2. Mutation Gate — CI triggered

- **Workflow:** `.github/workflows/mutation-gate-24.3.yml`.
- **Services:** `services/workspace_credit_service`, `services/lead_assignment_service`, `services/billing_event_service`, `routes/lead_pipeline_routes`, `capabilities/core/billing`.
- **Triggers:** `workflow_dispatch`, `push`/`pull_request` to `develop`/`main` on 24.3 P0 files.
- **Status:** configured; not run locally per user request.

---

## 3. Test Review — `Request Changes` (62/100)

Full report: `test-review-24-3.md`

### Files reviewed

| Test file | Type | Verdict |
|---|---|---|
| `tests/unit/services/test_workspace_credit_pooling.py` | Unit | **P0** — `FakeAsyncSession` causes service to branch into `_*_fake` methods; production `UPDATE ... WHERE ... RETURNING` SQL never exercised. |
| `tests/unit/services/test_lead_assignment.py` | Unit | **P1** — `get_eligible_members` mocked, no persistence assertions, Redis tested with in-memory stub. |
| `tests/integration/services/test_team_crm_pipeline.py` | Integration | **P0** — Not a real integration test; manually raises `HTTPException`, asserts `1+1==2`, no DB/routes/client. |
| `tests/integration/services/test_credit_deduction_race.py` | Integration | **PASS** — real PostgreSQL + `asyncio.gather`, verifies no overdraft and spend-cap race. |
| `tests/integration/routes/test_kanban_concurrency.py` | Integration | **PASS** — real HTTP client + DB, tests OCC 409, timeline, cross-workspace RLS. |
| `tests/unit/services/test_billing_event_service.py` | Unit | **P0** — `WorkspaceCreditService.record_spend` monkeypatched, spend-cap gate not tested. |
| `tests/unit/capabilities/test_billing.py` | Unit | **P0** — autouse fixture patches `record_spend`; `_debit_with_workspace_spend_cap` bypassed. |
| `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` | E2E | **P1** — conditional drag, 409 toast never asserted, same user in both contexts, timeline not verified. |

### Findings

- **P0:** `WorkspaceCreditService` unit tests validate the fake path, not the production SQL atomic update.
- **P0:** `test_team_crm_pipeline.py` is a stub; real integration is in `test_kanban_concurrency.py` and `test_credit_deduction_race.py`.
- **P0:** Billing unit/capability tests monkeypatch `record_spend`, so per-seat spend-cap gate is not tested.
- **P1:** Lead assignment tests do not assert persistence, capacity, or multi-worker Redis fairness.
- **P1:** Playwright E2E test is incomplete and was not executed.

---

## 4. Traceability Matrix

| AC | Requirement | Implementation | Tests | Status |
|---|---|---|---|---|
| AC-1 | Reactive Kanban board with OCC | `nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx`, `nowing_backend/app/routes/lead_pipeline_routes.py` | `test_kanban_concurrency.py` (integration), `kanban-multicontext-sync.spec.ts` (E2E) | Covered (E2E pending run) |
| AC-2 | Round-Robin lead assignment | `nowing_backend/app/services/lead_assignment_service.py` | `test_lead_assignment.py` (unit fake), `test_team_crm_pipeline.py` (integration) | Partial — unit is fake; integration covers basic flow |
| AC-3 | Lead interaction timeline | `nowing_backend/app/routes/lead_pipeline_routes.py`, `LeadDetailFlyoutDrawer.tsx` | `test_team_crm_pipeline.py` | Covered |
| AC-4 | Shared credit wallet + per-seat spend cap | `nowing_backend/app/services/workspace_credit_service.py`, `app/capabilities/core/billing.py`, `BillingEventService` | `test_workspace_credit_pooling.py` (unit fake), `test_credit_deduction_race.py`, `test_team_crm_pipeline.py` | Partial — unit is fake; integration covers race |

---

## 5. NFR Audit

| NFR | Evidence | Status |
|---|---|---|
| Concurrency / atomicity | `WorkspaceCreditService.deduct_credits`/`record_spend`/`refund_credits` use conditional `UPDATE ... WHERE` / `UPDATE ... RETURNING`. OCC on stage transition uses `version` column. | PASS |
| Security / RLS | Migration 221 sets `FORCE ROW LEVEL SECURITY`; `lead_pipeline_routes.py` uses RBAC; RLS predicate includes `client_id`. | PASS (requires manual confirm `FORCE` is not bypassed by `bypass_rls` usage) |
| Performance | Index on `lead_assignments` workspace+user; composite PK `(id, workspace_id)`. Capacity check still N+1 in `LeadAssignmentService` (deferred finding). | WARN |
| Reliability | `IntegrityError` caught for duplicate slug; `NoEligibleAssigneeError` returned as 400. | PASS |

---

## 6. E2E Gate

- **Spec:** `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts`.
- **Result:** **Conditional Pass (Yellow)** — 2/2 tests passed.
- **Findings:**
  - Test passes but does **not** actually assert the 409 conflict (`leadCardB` and `conflictToast` declared but unused, `biome` warns unused variables).
  - `LeadKanbanBoard.tsx` expects `err.data.current_version`/`err.data.current_stage_id`, but backend 409 puts those fields under `err.data.detail`, so the client merge/rollback logic does not apply server values.
  - No Playwright coverage for workspace credit/spend-cap manager UI (`MemberSpendCapDialog`) or 401/403/402 error states.
  - `browser.newContext()` not using project `storageState`; auth model fragile.
- **Artifact:** `e2e-gate-24-3.md`

---

## 7. Next Steps

1. **Human review** of P0 files (credit arithmetic, auth, migration) → then mark `done`.
2. **Run mutation gate on CI** via Actions tab.
3. **Run E2E** when stack is available.
4. **Strengthen unit tests** for `WorkspaceCreditService` and `LeadAssignmentService` with real DB/Redis integration to kill fake-session anti-pattern.
