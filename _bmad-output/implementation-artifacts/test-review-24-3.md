# Test Quality Review: Story 24.3 — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling

**Review date:** 2026-08-21  
**Scope:** Backend unit/integration tests and Playwright E2E test named in the story review request.  
**Overall quality score:** 62/100 (Grade C — Needs Improvement)  
**Overall verdict:** Request Changes  

---

## Summary

All 130+ Python tests in scope currently pass, and the two adjacent integration suites (`test_credit_deduction_race.py`, `test_kanban_concurrency.py`) are strong. However, the six files explicitly named in the review request are **not production-ready**:

- The requested "integration" CRM test is effectively a stub (manual `HTTPException`, no database, no routes).
- The credit-pooling unit tests test an in-memory fake path, not the production `UPDATE ... WHERE` atomic path.
- The lead-assignment unit tests mock the eligibility query and session, so they do not verify persistence, capacity checks, or Redis fairness.
- The billing unit/capability tests monkeypatch `WorkspaceCreditService.record_spend`, bypassing the per-seat spend-cap gate that Story 24.3 introduced.
- The Playwright E2E test has a conditional drag, never asserts the 409 conflict, and never verifies the chronological timeline.

**Issue count (focus files only):**

- Critical: 2
- High: 5
- Medium: 5
- Low: 2

**Test execution status:**

| Suite | Files | Status | Notes |
| --- | --- | --- | --- |
| Backend unit | `test_lead_assignment.py`, `test_workspace_credit_pooling.py`, `test_billing_event_service.py`, `test_billing.py` | 127 passed | Warnings from unawaited `AsyncMock` in `test_lead_assignment.py`. |
| Backend integration (requested) | `test_team_crm_pipeline.py` | 3 passed | Not a real integration test; see findings. |
| Backend integration (adjacent) | `test_credit_deduction_race.py`, `test_kanban_concurrency.py` | 6 passed | Real DB, concurrency, OCC, RLS. Strong. |
| Playwright E2E | `kanban-multicontext-sync.spec.ts` | not executed | Code-reviewed only. |

---

## Per-Test-File Review

### 1. `nowing_backend/tests/unit/services/test_lead_assignment.py`

**Status:** PASS (7/7) — **Quality: Needs Improvement**

**Findings:**

- **Over-mocks the eligibility engine.** `test_round_robin_assignment_even_distribution` and the other round-robin tests replace `service.get_eligible_members` with `AsyncMock` (`test_lead_assignment.py:179`). The real query that filters `status='ACTIVE'`, `is_accepting_leads=True`, and counts non-terminal leads is never exercised.
- **Does not assert intent/persistence.** No test verifies that `lead.assigned_to_user_id` is updated, that a `LeadAssignment` row is inserted, or that a `LeadActivityLog` row is written. `test_reassign_lead_creates_activity_log` (`test_lead_assignment.py:390-400`) only asserts `AssignmentResult` fields.
- **Redis cursor tested with an in-memory stub, not real Redis.** `FakeRedis` (`test_lead_assignment.py:119-134`) is synchronous and single-process. It does not validate the production `redis.incr` cursor or multi-worker fairness.
- **No concurrency or capacity edge cases.** No test for two simultaneous assignments to the same lead, batch assignment when members are at capacity, or `unassigned_lead_ids` behavior.
- **AsyncMock warnings.** Running the suite emits `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` from `lead_assignment_service.py:175` and `:188`, indicating the mocked `session.execute` is not awaited as the real code does.
- **Red-phase fallback still present.** The `try/except ImportError` block (`test_lead_assignment.py:24-109`) stubs the entire service when it cannot be imported. That is appropriate for a red-phase scaffold but should be removed now that the service exists.

### 2. `nowing_backend/tests/unit/services/test_workspace_credit_pooling.py`

**Status:** PASS (12/12) — **Quality: Critical Issues**

**Findings:**

- **Mirror test / tests the fake path, not the production code.** `FakeAsyncSession` (`test_workspace_credit_pooling.py:156-184`) has `workspaces` and `memberships` dicts, which causes `WorkspaceCreditService` to branch into `_deduct_credits_fake`, `_record_spend_fake`, and `_refund_credits_fake` (`workspace_credit_service.py:141-146`, `322-328`, `437-444`). The unit tests therefore validate the test's own in-memory logic, not the production `UPDATE ... WHERE ... RETURNING` SQL that enforces INV-24.4.
- **No atomic concurrency coverage.** The only place the atomic SQL path is tested is the adjacent integration file `test_credit_deduction_race.py`.
- **Missing boundary / negative cases for the real path:**
  - Non-member deduction (`WorkspaceCreditService` raises `ValueError("Member not found")` for non-members at `workspace_credit_service.py:150`).
  - Exact cap/balance edge (`amount == cap - spent`, `amount == balance`).
  - Refund amount greater than current `monthly_spent_micros` (should clamp at 0).
  - `record_spend` for a non-member or with `amount_micros <= 0`.
- **Tight coupling to a test-only seam.** The service's `hasattr(session, 'workspaces')` check is there only to support `FakeAsyncSession`. The tests rely on this seam rather than testing the real contract.

### 3. `nowing_backend/tests/integration/services/test_team_crm_pipeline.py`

**Status:** PASS (3/3) — **Quality: Critical Issues**

**Findings:**

- **Not an integration test.** Despite being in `tests/integration/services/`, the file never uses the app, a database, or an HTTP client.
- `test_occ_stage_transition_conflict_detection` (`test_team_crm_pipeline.py:27-52`) manually raises `HTTPException(status_code=409)` and asserts the status code. It does not call any route or service.
- `test_occ_stage_transition_success_increments_version` (`test_team_crm_pipeline.py:54-64`) only asserts Python arithmetic (`1 + 1 == 2`).
- `test_timeline_activity_schema_validation` (`test_team_crm_pipeline.py:66-75`) only constructs a Pydantic `LeadActivityLogCreate` and asserts its fields.
- **Misses all required integration coverage** from the docstring: pipeline stage auto-seeding, real OCC with concurrent HTTP requests, activity log insertion, member spend cap and lead capacity updates, chronological timeline ordering, RLS, and cross-workspace auth.
- **Should be removed or rewritten.** The real integration coverage is in `tests/integration/routes/test_kanban_concurrency.py`, which should be the canonical integration suite for AC-1/AC-3/INV-23.6.

### 4. `nowing_backend/tests/unit/services/test_billing_event_service.py`

**Status:** PASS (22+) — **Quality: Needs Improvement**

**Findings:**

- **Spend-cap gate is mocked out.** `_patch_wallet` (`test_billing_event_service.py:76-124`) monkeypatches `app.services.workspace_credit_service.WorkspaceCreditService.record_spend` to return a hardcoded success dict. The production `_record_business_event` (`billing_event_service.py:761-819`) calls `record_spend` after `check_balance` and before `apply_debit`; the test never exercises this real gate or the `SpendCapExceededError -> InsufficientCreditsError` conversion.
- **Debit-failure refund test is a mock call-count test.** `test_record_signal_scan_apply_debit_failure_refunds_member_spend` (`test_billing_event_service.py:313-410`) patches `refund_member_spend` and asserts it was called. It does not verify the real transaction rollback or the `WorkspaceMembership.monthly_spent_micros` decrement.
- **Strengths:** Good regression coverage of BillingEvent row fields, `cost_basis`, `currency`, negative-cost rejection, idempotency, and insufficient-credit error handling.
- **Scope note:** A large portion of the file (`TestRecordContactUnlockRefund24h`) is for Story 26.6, not 24.3.

### 5. `nowing_backend/tests/unit/capabilities/test_billing.py`

**Status:** PASS (64+) — **Quality: Needs Improvement**

**Findings:**

- **Autouse fixture bypasses the spend-cap gate.** `_stub_workspace_credit_spend` (`test_billing.py:75-99`) patches `WorkspaceCreditService.record_spend` to always succeed. The helper `_debit_with_workspace_spend_cap` in `app/capabilities/core/billing.py:36-71` calls `record_spend` then `wallet_credit.apply_debit`; the tests never exercise this production path, so per-seat cap enforcement in billable operations is untested.
- **All charges use a mocked session.** `_make_session` (`test_billing.py:38-51`) returns canned `MagicMock` results for owner resolution and wallet balance. No real DB, no concurrent charge race, no real atomic credit deduction.
- **Strengths:** Extensive coverage of billing math, config flags, `charge_capability` vs `gate_capability`, platform meters, chainlens cost splitting, degradation, and disabled-billing short-circuits.
- **Length:** File is 1,863 lines. While it is a suite of many small tests, it should be split by billing domain (web crawl, platform scrape, chainlens, utility) for maintainability.

### 6. `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts`

**Status:** not executed — **Quality: High Issues**

**Findings:**

- **Conditional test flow breaks determinism.** `if (await leadCardA.isVisible()) { ... }` (`kanban-multicontext-sync.spec.ts:92-94`) means the conflict test is silently skipped if the lead card is not visible. Playwright tests should fail fast on missing preconditions.
- **The 409 conflict is never asserted.** `conflictToast` is defined (`kanban-multicontext-sync.spec.ts:107-110`) but there is no `await expect(conflictToast).toBeVisible()` or equivalent. The AC-1 requirement "OCC returns 409 and rolls back conflicting drag" is not actually tested.
- **Lead creation is not asserted.** `if (leadCreateRes.ok())` (`kanban-multicontext-sync.spec.ts:46-50`) falls back to a fake `leadId` string. If the clipper request fails, the rest of the test uses a non-existent `data-testid` and `leadTitle` locators.
- **Same user in both contexts.** `acquireTestToken(request)` is used once and both `browser.newContext()` pages are unauthenticated or use the same owner. The multi-seat / role-based access scenario is not tested.
- **Timeline verification is superficial.** The test opens the drawer and checks visibility (`kanban-multicontext-sync.spec.ts:117-122`) but does not assert chronological order or the expected activity types from AC-3 (`Scraped -> Zalo Sent -> Inbound Reply -> Internal Notes -> Stage Changed`).
- **Potential flakiness:** 10s and 15s timeouts with no explicit wait for the lead card to appear in the first column before dragging, and `dragTo` with `force: true` may not reflect real user behavior.

---

## Positive Findings

The following tests were not in the explicit focus list but are the strongest evidence that the story works:

- `tests/integration/services/test_credit_deduction_race.py`
  - Real PostgreSQL + `asyncio.gather` concurrency.
  - Verifies no overdraft (`final balance == 0`) and per-seat cap race (`monthly_spent_micros == 200_000 <= 250_000 cap`).
  - Passes.

- `tests/integration/routes/test_kanban_concurrency.py`
  - Real HTTP client + DB.
  - Verifies default stages, OCC 409 on stale version, retry with current version, chronological timeline endpoint, and cross-workspace 403/404 isolation.
  - Passes.

These should be treated as the canonical integration tests for Story 24.3.

---

## Action Items

| # | Priority | File(s) | Action |
| --- | --- | --- | --- |
| 1 | P0 | `tests/integration/services/test_team_crm_pipeline.py` | Delete or fully rewrite using `client_as_regular_user` + `db_session` / real HTTP client. Move coverage to `tests/integration/routes/test_kanban_concurrency.py` and `test_credit_deduction_race.py` where appropriate. |
| 2 | P0 | `tests/unit/services/test_workspace_credit_pooling.py` | Remove `FakeAsyncSession` fake-path reliance. Use real `AsyncSession` (integration fixture or in-memory SQLite/Postgres) so the production `UPDATE ... WHERE ... RETURNING` SQL is tested. Add boundary and non-member cases. |
| 3 | P0 | `tests/unit/capabilities/test_billing.py`, `tests/unit/services/test_billing_event_service.py` | Stop monkeypatching `WorkspaceCreditService.record_spend`. Test the real `_debit_with_workspace_spend_cap` / `_record_business_event` gate, including `SpendCapExceededError` mapped to `InsufficientCreditsError` and no wallet debit when the cap is hit. |
| 4 | P1 | `tests/unit/services/test_lead_assignment.py` | Test with real `Lead` / `WorkspaceMembership` / `LeadAssignment` models, assert persisted rows, assert `Lead.assigned_to_user_id` update, test capacity and batch unassigned behavior, add Redis/multi-worker fairness test. Remove red-phase `try/except` fallback. |
| 5 | P1 | `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` | Make setup deterministic: assert lead creation, remove `if (await leadCardA.isVisible())`, assert conflict toast, use two distinct users/roles, and assert timeline event order and types. |
| 6 | P2 | `tests/unit/services/test_workspace_credit_pooling.py` | Add explicit tests for non-member rejection, exact cap/balance edges, refund > spent clamp, and `record_spend` for non-member. |
| 7 | P2 | `tests/unit/capabilities/test_billing.py` | Split the 1,863-line module into smaller domain-specific files. |

---

## Verdict

**Request Changes.**

The Story 24.3 implementation has strong real-DB concurrency tests in adjacent files, but the six tests requested for this review provide a false sense of confidence. They pass while exercising mocks, fake in-memory paths, or Python arithmetic instead of the production atomic credit-pooling, round-robin assignment, spend-cap gate, OCC, and Kanban E2E behavior that the story requires. Address the P0/P1 action items before considering this test suite production-ready.
