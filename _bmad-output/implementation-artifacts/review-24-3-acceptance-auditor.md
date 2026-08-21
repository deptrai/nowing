# Story 24.3 Acceptance Auditor Report — `bmad-code-review`

**Story:** 24.3 — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling  
**Spec reviewed:** `_bmad-output/implementation-artifacts/stories/24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`  
**Invariants reviewed:** INV-24.4, INV-23.4, INV-23.6  
**Diff reviewed:** `_bmad-output/implementation-artifacts/review-24-3-working-tree.diff`  
**Auditor:** bmad-code-review / Acceptance Auditor  
**Overall Verdict:** **REJECT / REQUEST CHANGES** — do not merge the working tree diff as the final Story 24.3 patch.

---

## Executive Summary

The working tree diff contains four categories of problems:

1. **Scope-creep / mismatch** — it adds `masothue/10.8` parser/test changes, an unrelated `MissionControlWidget` TypeScript fix, and a whole `.agents/skills/bmad-agent-e2e-tester` (XActions) skill that do not belong to Story 24.3.
2. **Regression introduced by the masothue parser diff** — the proposed one-line change in `parsers.py` would cause an `IndexError` and is directly contradicted by the new test added in the same diff.
3. **Unaddressed HIGH implementation findings** against the spec and invariants:
   - `WorkspaceCreditService.deduct_credits` is not atomic (INV-24.4 / AC-4).
   - `BillingEventService._record_business_event` leaks `SpendCapExceededError` as a 500 (AC-4 exception contract).
   - Role-based lead visibility required by INV-23.6 is not implemented.
4. **Test-suite contradiction** — unit/capability tests pass by exercising fake/mocked paths, while the traceability and NFR artifacts claim PASS/CONCERNS. The tests do not prove the acceptance criteria are met.

The 24.3 implementation is functionally close, but this diff is not acceptable as a final acceptance patch.

---

## 1. Scope-Creep / Mismatch Findings (do not belong to Story 24.3)

### 1.1 `masothue/10.8` parser & test changes

| File | Line(s) in diff | What it is | Disposition |
|------|----------------|------------|-------------|
| `nowing_backend/app/proprietary/platforms/masothue/parsers.py` | diff `review-24-3-working-tree.diff:197-198`; source `parsers.py:225` | Changes guard from `i + 1 < len(parts)` to `i + 0 < len(parts)` | **Out of scope** and **regression** |
| `nowing_backend/tests/unit/platforms/masothue/test_fetch.py` | diff `review-24-3-working-tree.diff:202-404` | New fetch tests for masothue | Out of scope |
| `nowing_backend/tests/unit/platforms/masothue/test_parsers.py` | diff `review-24-3-working-tree.diff:405-597`; new test at `test_parsers.py:575-581` | New parser tests, including `_extract_city_district_from_address` | Out of scope and **contradicts the parser change** |
| `nowing_backend/tests/unit/platforms/masothue/test_scraper.py` | diff `review-24-3-working-tree.diff:598-838` | New scraper tests | Out of scope |

**Issue:** The masothue parser change is a regression:

- `i + 0 < len(parts)` is always `True` for any valid loop index `i`.
- When the district-like token is the last segment (e.g. `"Số 10 Đường ABC, Huyện Châu Thành"`), the code will execute `parts[i + 1]` and raise `IndexError`.
- The newly added test `test_extract_city_district_from_address` (diff line 575-581) explicitly asserts `city is None` for that same case, so the diff is internally inconsistent.

These changes belong to Story 10.8 / 24.2 (MST / Waterfall Phone & Tax Code). They should be **removed from the 24.3 diff** and reviewed under their owning story. If the intent is to fix a parser edge case, the guard must remain `i + 1 < len(parts)`.

### 1.2 `MissionControlWidget.tsx`

- `nowing_web/components/leads/MissionControlWidget.tsx:239`
- Adds a strict `Set<string>` type-narrowing filter for `expandedSubtasks`.
- **Not a 24.3 acceptance-criterion.** It is a pre-existing TypeScript build fix.
- **Disposition:** Low-risk, but should be tracked as a build/debt fix in its own story, not mixed with 24.3.

### 1.3 `.agents/skills/bmad-agent-e2e-tester/` and `_bmad/memory/bmad-agent-e2e-tester/`

- New skill/sanctum diff starts at `review-24-3-working-tree.diff:894` and continues through the end of the file (`.memlog.md`, `SKILL.md`, `assets/*`, `scripts/*`, `_bmad/memory/...`).
- The skill references an **XActions** project (`api/server.js :3000`, `src/mcp/server.js :3001`, `XACTIONS_SESSION_COOKIE`), not Nowing.
- **Disposition:** Completely unrelated to Story 24.3. Remove from the diff or route to the agent-builder / skill story.

---

## 2. Core Story 24.3 Acceptance-Criteria & Invariant Violations

### 2.1 AC-4 / INV-24.4 — `WorkspaceCreditService.deduct_credits` is not atomic

**Files:**
- `nowing_backend/app/services/workspace_credit_service.py:121-246`
- Specifically lines 163-215

**Finding:**
The shared `Workspace.credit_micros_balance` is deducted with an atomic `UPDATE ... WHERE` **before** the per-seat cap `UPDATE ... WHERE` on `WorkspaceMembership.monthly_spent_micros`.

```python
# workspace_credit_service.py:163-174  (balance deducted first)
# workspace_credit_service.py:191-215  (cap checked second)
```

If the cap `UPDATE` returns no rows (line 208), `SpendCapExceededError` is raised at lines 210-215 but the workspace balance is already reduced and is **not refunded**. This violates the INV-24.4 requirement that the shared pool be preserved atomically when the per-seat cap is exceeded.

**Recommendation:**
- Reverse the order: atomically increment `monthly_spent_micros` under the cap first; only on success decrement `Workspace.credit_micros_balance`.
- Alternatively, explicitly refund the workspace balance in the `spend_row is None` branch before raising `SpendCapExceededError`.

### 2.2 AC-4 — `BillingEventService._record_business_event` leaks `SpendCapExceededError`

**File:** `nowing_backend/app/services/billing_event_service.py:814-823`

**Finding:**
`record_spend` is called without a `try/except SpendCapExceededError`:

```python
if cost_micros > 0 and user_id is not None:
    await wallet_credit.check_balance(session, user_id, cost_micros)
    credit_svc = WorkspaceCreditService(session=session)
    await credit_svc.record_spend(...)
    try:
        await wallet_credit.apply_debit(...)
    except Exception:
        await credit_svc.refund_member_spend(...)
        raise
```

If `record_spend` raises `SpendCapExceededError`, the exception propagates unchanged. Callers such as `contact_unlock_service.py` catch `wallet_credit.InsufficientCreditsError` and `ValueError` but not `SpendCapExceededError`, causing the route to return **500 Internal Server Error** instead of a controlled 402/403 credit error.

This contradicts the pattern in `nowing_backend/app/capabilities/core/billing.py:58-69`, which correctly converts `SpendCapExceededError` → `wallet_credit.InsufficientCreditsError`.

**Recommendation:** Wrap `record_spend` in a `try/except SpendCapExceededError` and re-raise as `wallet_credit.InsufficientCreditsError`.

### 2.3 INV-23.6 — Role-based / assignment-based lead visibility is missing

**Files:**
- `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:270-302` (RLS predicate)
- `nowing_backend/app/routes/lead_pipeline_routes.py:100-110`, `:267-275`, `:338-347` (and other route handlers)
- `nowing_backend/app/utils/rbac.py:177-207`

**Finding:**
INV-23.6 requires: *“members can only view assigned leads or all leads based on role (owner, admin, member).”*

Current implementation:
- RLS predicates only filter on `workspace_id` / `client_id` (`_tenant_predicate` at migration line 270-274).
- `check_workspace_access` only verifies the caller is a workspace member.
- All pipeline routes (`list_pipeline_stages`, `list_lead_activities`, `transition_lead_stage`, `assign_or_reassign_lead`) are therefore open to any member of the workspace.

**Result:** Any member can view, transition, and reassign any lead in the workspace, violating INV-23.6.

**Recommendation:** Add role/assignment predicates to route queries and/or RLS policies:
- Non-owner/admin members should only see leads where `Lead.assigned_to_user_id == auth.user.id`.
- Admins/owners can see all leads in the workspace.

### 2.4 AC-2 — Round-robin lead assignment has fairness / capacity / TOCTOU gaps

**File:** `nowing_backend/app/services/lead_assignment_service.py:76-223`

**Findings:**
1. **Capacity TOCTOU:** `get_eligible_members` computes `current_leads` from a `func.count(Lead.id)` snapshot. `assign_lead` then updates `Lead.assigned_to_user_id` without a row lock on the member or lead. Concurrent batches can over-assign a member beyond `lead_capacity`.
2. **Batch inefficiency:** `assign_leads_batch` (lines 198-223) calls `assign_lead` once per lead, and `assign_lead` re-invokes `get_eligible_members` each time, producing O(n) identical queries.
3. **Multi-worker fairness:** The Redis `INCR` cursor is correct, but the in-memory fallback at lines 157-160 is per-process. If Redis is unavailable, multiple workers/containers will maintain independent cursors and assignment fairness is lost.

**Recommendation:**
- Compute eligible members once per batch.
- Use an atomic `UPDATE ... WHERE` (or `SELECT ... FOR UPDATE`) to reserve capacity when assigning a lead.
- Either remove the in-memory fallback or clearly document that Redis is required for multi-worker fairness.

### 2.5 AC-1 — 409 conflict response shape does not match frontend merge logic

**Files:**
- `nowing_backend/app/routes/lead_pipeline_routes.py:221-226` (409 body)
- `nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:417-420` (client merge)
- `nowing_web/lib/apis/base-api.service.ts:271-280` (error wrapping)

**Finding:**
The route returns the conflict fields inside a nested `detail` object:

```python
detail={
    "error_code": "concurrency_conflict",
    "current_version": current_version,
    "current_stage_id": str(current_stage_id) if current_stage_id else None,
}
```

The global `AppError` then stores the whole JSON response in `err.data`. Therefore the client must read `err.data.detail.current_version`. However `LeadKanbanBoard.tsx` reads `err.data.current_version` / `err.data.current_stage_id` (top of `data`), so it cannot merge the server state and falls back to the stale local state.

This undermines AC-1: *“rolls back the conflicting drag on the second client without state corruption.”*

**Recommendation:** Either update `LeadKanbanBoard.tsx` to read `err.data?.detail?.current_version` / `current_stage_id` (with backward-compatible fallback), or flatten the 409 response so the conflict fields are at the top of the body.

### 2.6 AC-4 — Per-seat spend cap is not wired into all billable paths

**Files (per NFR audit):**
- `nowing_backend/app/services/phone_waterfall_service.py:937`
- `nowing_backend/app/services/outcome_pricing_service.py:180`
- `nowing_backend/app/services/etl_credit_service.py:126`
- `nowing_backend/app/gateway/zalo/zns_client.py:287`
- `nowing_backend/app/services/web_crawl_credit_service.py:141`
- `nowing_backend/app/services/platform_scrape_credit_service.py:75`

**Finding:**
These call sites still debit `User.credit_micros_balance` directly via `wallet_credit.apply_debit` without calling `WorkspaceCreditService.record_spend`. If any of these are triggered on behalf of a workspace member, the per-seat spend cap is bypassed.

**Recommendation:** Route these through `WorkspaceCreditService.record_spend` + `wallet_credit.apply_debit` (or the `_debit_with_workspace_spend_cap` helper in `app/capabilities/core/billing.py`) and add integration coverage.

---

## 3. Test-Evidence Contradictions

The diff’s own artifacts disagree:

- `traceability-24-3.md` marks all four ACs as **pass**.
- `test-review-24-3.md` gives the test suite **62/100 — Request Changes**.
- `nfr-audit-24-3.md` rates the story **CONCERNS** with three HIGH findings.

Concrete test problems:

| File | Problem |
|------|---------|
| `nowing_backend/tests/unit/services/test_workspace_credit_pooling.py` | Uses `FakeAsyncSession` (`hasattr(session, "workspaces")` seam at `workspace_credit_service.py:141-146`), exercising `_deduct_credits_fake` / `_record_spend_fake` instead of the production `UPDATE ... WHERE ... RETURNING` SQL. |
| `nowing_backend/tests/unit/services/test_billing_event_service.py` | Monkeypatches `WorkspaceCreditService.record_spend`; does not test the real spend-cap gate or exception conversion. |
| `nowing_backend/tests/unit/capabilities/test_billing.py` | Autouse fixture patches `record_spend`; `_debit_with_workspace_spend_cap` is bypassed. |
| `nowing_backend/tests/integration/services/test_team_crm_pipeline.py` | Stub test: raises `HTTPException` manually, asserts `1 + 1 == 2`, validates a Pydantic schema — never uses the DB, routes, or real services. |
| `nowing_backend/tests/unit/services/test_lead_assignment.py` | Mocks `get_eligible_members` and `session`; no persistence assertions; `FakeRedis` is single-process. |
| `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` | Conditional `if (await leadCardA.isVisible())`, declares `leadCardB`/`conflictToast` but never uses them, does not assert 409 toast, does not verify chronological timeline, uses `browser.newContext()` without `storageState`. |

**Verdict:** The tests pass but do not demonstrate that the production code satisfies AC-1 through AC-4 or the invariants. This is a dangerous false-positive.

---

## 4. Other Notable Items

### 4.1 Migration 221 docstring inconsistency

- `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:4` says `Revises: 218`.
- `down_revision` on line 21 is `"220"` (which is correct — no Alembic branch).
- **Recommendation:** Update the docstring to `Revises: 220`.

### 4.2 `mutation-gate.py` and CI workflow

- `scripts/mutation-gate.py:41-46` adds the five 24.3 P0 services.
- `scripts/mutation-gate.py:282-286` correctly switches the pytest marker to `-m "integration"` when integration test files are targeted.
- `.github/workflows/mutation-gate-24.3.yml` is a reasonable CI wrapper.
- **Note:** The mutation gate is configured but not executed; it should be run on CI before final acceptance.

---

## 5. Required Actions Before Acceptance

1. **Remove scope-creep** from the working tree diff:
   - `masothue` parser/test changes (route to Story 10.8 / 24.2).
   - `MissionControlWidget.tsx` build fix (route to a standalone build-debt ticket or pre-existing fix queue).
   - `.agents/skills/bmad-agent-e2e-tester/` and `_bmad/memory/bmad-agent-e2e-tester/` (route to the agent/skill story).
2. **Fix `WorkspaceCreditService.deduct_credits` ordering** (`workspace_credit_service.py:163-215`) so the workspace balance is not left deducted when the per-seat cap fails.
3. **Fix `BillingEventService._record_business_event` exception contract** (`billing_event_service.py:814-823`) by converting `SpendCapExceededError` to `InsufficientCreditsError`.
4. **Implement role/assignment-based lead visibility** per INV-23.6 in route queries and/or RLS policies.
5. **Align the 409 OCC response shape** between backend and `LeadKanbanBoard.tsx`.
6. **Harden `LeadAssignmentService`** for batch efficiency and multi-worker cursor fairness.
7. **Wire remaining direct-debit paths** through the per-seat spend-cap gate.
8. **Replace fake/mocked unit tests** with tests that exercise the real SQL and integration paths.
9. **Run the full verification suite** (ruff, pytest, `pnpm tsc`, biome) and the Playwright E2E `kanban-multicontext-sync.spec.ts`.

---

## 6. Final Verdict

**REJECT / REQUEST CHANGES.**

The 24.3 implementation has strong adjacent integration tests (`test_kanban_concurrency.py`, `test_credit_deduction_race.py`) and the major data-model / migration work is in place, but the working tree diff under review:

- includes unrelated and partially broken code (masothue, MissionControl, XActions agent skill),
- does not resolve the three HIGH NFR/acceptance findings (credit atomicity, exception contract, INV-23.6 visibility),
- contains a test suite that passes without exercising production behavior,
- and has inconsistent acceptance artifacts (PASS with CONCERNS vs. Request Changes).

Do not merge this diff. Re-work the scope, fix the HIGH findings, harden tests, and re-submit for acceptance.
