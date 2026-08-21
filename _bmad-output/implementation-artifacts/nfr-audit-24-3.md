---
story_key: "24-3"
epic: "epic-24"
story: "24.3"
title: "NFR Evidence Audit — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling"
assessment_date: "2026-08-22"
assessor: "Luisphan"
workflow: "bmad-testarch-nfr v5.0"
overall_status: "CONCERNS"
---

# NFR Evidence Audit — Story 24.3

**Feature:** Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling  
**Date:** 2026-08-22  
**Assessor:** Luisphan  
**Skill:** `bmad-testarch-nfr` v5.0  
**Overall Status:** ⚠️ **CONCERNS**  

---

## Executive Summary

This audit evaluated the non-functional evidence for the four focus areas requested for Story 24.3: **concurrency/atomicity**, **security/RLS**, **performance**, and **reliability**. Implementation evidence (unit/integration tests, lint/type checks, source code, migrations) has been inspected and re-run in the current environment.

| Area | Status | Key Finding |
| --- | --- | --- |
| Concurrency / Atomicity | ⚠️ CONCERNS | `WorkspaceCreditService.deduct_credits` deducts the shared workspace balance **before** the per-seat cap is atomically verified; if the cap update fails, the balance is not refunded. `BillingEventService._record_business_event` also leaves `SpendCapExceededError` unconverted, causing callers to raise 500 instead of a controlled credit error. |
| Security / RLS | ⚠️ CONCERNS | Workspace-level RLS (`FORCE`, composite PK, tenant GUC) is correctly implemented, but **role-based lead visibility** required by INV-23.6 is not enforced. Any workspace member can view all leads, stages, and activity logs. |
| Performance | ⚠️ CONCERNS | Indexes and composite PKs are in place. Round-Robin multi-worker fairness depends on Redis; the in-memory fallback is per-worker. `assign_leads_batch` re-queries eligible members for every lead, creating O(n) query overhead and a TOCTOU window for capacity overruns. |
| Reliability | ⚠️ CONCERNS | OCC 409 handling, idempotent billing lock, and route error handling are strong. However the `deduct_credits` and `BillingEventService` atomicity gaps, plus several direct `wallet_credit.apply_debit` paths that bypass the per-seat cap, reduce fail-fast guarantees. Unit tests for the credit path use `FakeAsyncSession` or monkeypatch `record_spend`, so the production SQL gate is not unit-tested. |

**Test execution in this session:**

```bash
cd nowing_backend
uv run ruff check app/services/lead_assignment_service.py app/services/workspace_credit_service.py app/services/workspace_limits.py app/routes/lead_pipeline_routes.py app/schemas/lead_pipeline.py tests/unit/services/test_lead_assignment.py tests/unit/services/test_workspace_credit_pooling.py
uv run pytest tests/unit/services/test_lead_assignment.py tests/unit/services/test_workspace_credit_pooling.py tests/unit/services/test_billing_event_service.py tests/unit/capabilities/test_billing.py -q
uv run pytest tests/integration/routes/test_kanban_concurrency.py tests/integration/services/test_team_crm_pipeline.py tests/integration/services/test_credit_deduction_race.py -q
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/leads/pipeline/ app/dashboard/\[workspace_id\]/leads/pipeline/
```

**Results:**

- `ruff check` — pass
- Backend unit tests — **127 passed**
- Backend integration tests — **9 passed** (`test_kanban_concurrency` 4, `test_team_crm_pipeline` 3, `test_credit_deduction_race` 2)
- `pnpm tsc --noEmit` — pass
- `pnpm exec biome check ...` — pass

---

## 1. Concurrency & Atomicity

### 1.1 OCC / Kanban stage transition — PASS

`lead_pipeline_routes.transition_lead_stage` (`nowing_backend/app/routes/lead_pipeline_routes.py:192-227`) performs an atomic SQL update:

```python
update(Lead)
    .where(
        Lead.id == lead_id,
        Lead.workspace_id == workspace_id,
        Lead.version == payload.expected_version,
    )
    .values(
        stage_id=payload.stage_id,
        status=stage.slug,
        version=Lead.version + 1,
    )
    .returning(...)
```

If the update returns no row, a 409 is returned with `current_version` and `current_stage_id` so the client can merge state. The frontend `LeadKanbanBoard.tsx` reads `err.data.current_version` / `current_stage_id` and rolls back the optimistic UI state.

**Evidence:** `tests/integration/routes/test_kanban_concurrency.py` passes, including `test_kanban_stage_transition_optimistic_concurrency_and_conflict_409`.

### 1.2 Round-Robin lead assignment — CONCERNS

`LeadAssignmentService` (`nowing_backend/app/services/lead_assignment_service.py:76-223`):

- Queries active members with `is_accepting_leads=True`, `status=ACTIVE`, and `current_leads < capacity`.
- Uses `func.count(Lead.id)` grouped by `assigned_to_user_id` for capacity.
- Uses a Redis `INCR` cursor (`lead_assignment:cursor:{workspace_id}`) or an in-memory fallback.

**Concerns:**

1. **Multi-worker fairness:** the in-memory fallback is per-process; multiple workers will maintain independent cursors, breaking round-robin fairness when Redis is unavailable.
2. **Capacity TOCTOU:** `get_eligible_members` computes capacity from a snapshot. `assign_lead` then updates `Lead.assigned_to_user_id` without a row lock on the member or lead. Concurrent batches can over-assign the same member beyond `lead_capacity`.
3. **Batch efficiency:** `assign_leads_batch` calls `assign_lead` once per lead, and `assign_lead` calls `get_eligible_members` each time, producing O(n) queries for a batch of n leads.

**Evidence:** `tests/unit/services/test_lead_assignment.py` passes but over-mocks the session and Redis; it does not assert persistent `LeadAssignment`, `LeadActivityLog`, or `Lead.assigned_to_user_id` updates. No integration test covers scraper/chat → auto-assignment or multi-worker fairness.

### 1.3 Shared credit pool & per-seat spend cap — CONCERNS

#### 1.3.1 `WorkspaceCreditService.record_spend` — PASS

`record_spend` (`nowing_backend/app/services/workspace_credit_service.py:294-387`) uses an atomic `UPDATE ... WHERE` on `WorkspaceMembership.monthly_spent_micros` with the cap condition:

```python
update(WorkspaceMembership)
    .where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user_id,
        or_(
            WorkspaceMembership.monthly_spend_cap_micros.is_(None),
            WorkspaceMembership.monthly_spend_cap_micros
            >= func.coalesce(WorkspaceMembership.monthly_spent_micros, 0) + amount_micros,
        ),
    )
    .values(monthly_spent_micros=func.coalesce(WorkspaceMembership.monthly_spent_micros, 0) + amount_micros)
    .returning(...)
```

This is the correct pattern for fail-fast per-seat cap enforcement without touching the shared wallet.

#### 1.3.2 `WorkspaceCreditService.deduct_credits` — FAIL / HIGH

`deduct_credits` (`nowing_backend/app/services/workspace_credit_service.py:121-246`) first deducts from the shared `Workspace.credit_micros_balance` and **then** attempts to increment `WorkspaceMembership.monthly_spent_micros` under the cap:

```python
# lines 164-185
balance_result = await self.session.execute(
    update(Workspace)
    .where(Workspace.id == workspace_id, Workspace.credit_micros_balance >= amount_micros)
    .values(credit_micros_balance=Workspace.credit_micros_balance - amount_micros)
    .returning(Workspace.credit_micros_balance)
)

# lines 191-215 (cap check update)
spend_result = await self.session.execute(
    update(WorkspaceMembership)
    .where(..., WorkspaceMembership.monthly_spend_cap_micros >= ... + amount_micros)
    .values(monthly_spent_micros=... + amount_micros)
    .returning(WorkspaceMembership.monthly_spent_micros)
)
if spend_row is None:
    raise SpendCapExceededError(...)
```

If the membership cap update fails (e.g., a concurrent spend raised `monthly_spent_micros` past the cap, or the cap was lowered between the pre-check and the update), the workspace balance has already been reduced and is **not refunded**. This violates atomicity and can silently consume shared credits.

`deduct_credits` is currently only exercised by tests, not by live billing paths, but it remains a public API surface.

#### 1.3.3 `billing.py _debit_with_workspace_spend_cap` — PASS

`billing.py` (`nowing_backend/app/capabilities/core/billing.py:36-71`) wraps `WorkspaceCreditService.record_spend` and converts `SpendCapExceededError` to `wallet_credit.InsufficientCreditsError` before re-raising, then performs `wallet_credit.apply_debit`.

This helper is used by the main billable capability paths:

- `_charge_web_crawl` (`billing.py:416-418`)
- `_charge_captcha` (`billing.py:441-443`)
- `_charge_chainlens` (`billing.py:562-564`)
- `_charge_platform_meter` (`billing.py:815-817`)
- `_charge_vn_bds_aggregate` (`billing.py:858-860`)
- `_charge_vn_jobs_aggregate` (`billing.py:901-903`)

#### 1.3.4 `BillingEventService._record_business_event` — FAIL / HIGH

`_record_business_event` (`nowing_backend/app/services/billing_event_service.py:814-833`) calls `record_spend` **outside** a `try/except`:

```python
if cost_micros > 0 and user_id is not None:
    await wallet_credit.check_balance(session, user_id, cost_micros)
    credit_svc = WorkspaceCreditService(session=session)
    await credit_svc.record_spend(workspace_id=workspace_id, user_id=user_id, amount_micros=cost_micros)
    try:
        await wallet_credit.apply_debit(session, user_id, cost_micros)
    except Exception:
        await credit_svc.refund_member_spend(...)
        raise
```

If `record_spend` raises `SpendCapExceededError`, the exception propagates unchanged. Callers such as `contact_unlock_service.py` (`nowing_backend/app/services/contact_unlock_service.py:144-153`) catch `wallet_credit.InsufficientCreditsError` and `ValueError` but not `SpendCapExceededError`, so the route returns **500 Internal Server Error** instead of a controlled 402/403. This is a reliability and API-contract bug.

#### 1.3.5 Direct `wallet_credit.apply_debit` bypasses — CONCERNS

Several billable services still debit `User.credit_micros_balance` directly without `record_spend` or the shared workspace cap:

- `phone_waterfall_service.py:937` — contact phone enrichment
- `outcome_pricing_service.py:180` — outcome meeting booking
- `etl_credit_service.py:126` — document processing ETL
- `gateway/zalo/zns_client.py:287` — Zalo notification sends
- `web_crawl_credit_service.py:141` — legacy `charge_credits` (still callable)
- `platform_scrape_credit_service.py:75` — legacy `apply_debit` (still callable)

If these are triggered on behalf of a workspace member, the per-seat spend cap is not enforced. They should either be routed through `WorkspaceCreditService.record_spend` + `wallet_credit.apply_debit` (option 2), or deleted if superseded by `billing.py`.

**Evidence:** `tests/integration/services/test_credit_deduction_race.py` passes (2/2), proving no overdraft and cap race safety for the tested `deduct_credits`/`record_spend` paths. `tests/unit/services/test_workspace_credit_pooling.py` passes but exercises the `FakeAsyncSession` `_deduct_credits_fake` / `_record_spend_fake` paths, not the production SQL.

---

## 2. Security & RLS

### 2.1 Tenant isolation / composite PKs — PASS

- Migration 221 (`nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:112-260`) creates `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs` with composite primary keys `(id, workspace_id)` and foreign keys referencing `(leads.id, leads.workspace_id)`.
- RLS policies (`_create_rls`, lines 283-302) are `FORCE` enabled and use a tenant predicate on `workspace_id` and `client_id`.
- `set_request_tenant_context` (`nowing_backend/app/canonical/tenant_context.py:51-105`) uses `SET LOCAL`, so GUCs are transaction-scoped.
- Routes reset the GUC after `session.commit()` / `session.refresh()` to avoid RLS `FORCE` failures (e.g. `lead_pipeline_routes.py:83-84`, `156-157`, `329-330`).

**Evidence:** `tests/integration/routes/test_kanban_concurrency.py::test_kanban_cross_workspace_isolation_fail_closed` passes.

### 2.2 Route-level authorization — PASS

All CRM routes call `check_workspace_access` (`nowing_backend/app/utils/rbac.py:177-207`) which ensures the caller is a workspace member. Owner-only routes (`update_member_spend_cap`, `update_member_lead_capacity`) additionally call `is_workspace_owner` (`nowing_backend/app/routes/lead_pipeline_routes.py:479-480`, `513-514`).

### 2.3 Role-based lead visibility — FAIL / HIGH

INV-23.6 requires: *“members can only view assigned leads or all leads based on role (owner, admin, member).”*

The current implementation does **not** enforce this:

- RLS policies only filter by `workspace_id` / `client_id`, not by `assigned_to_user_id` or user role.
- `list_lead_activities`, `list_pipeline_stages`, `assign_or_reassign_lead`, and `transition_lead_stage` are all open to any workspace member.
- Any member can view any lead and any activity log in the workspace.

This is a fail-closed RLS requirement that is not yet met.

---

## 3. Performance

### 3.1 Database indexes — PASS

Migration 221 and `app/db.py` add the relevant indexes:

- `ix_leads_assigned_to_user_id`, `ix_leads_stage_id`
- `ix_lead_pipeline_stages_workspace_pos`
- `ix_lead_assignments_lookup` / `ix_lead_assignments_user`
- `ix_lead_activity_logs_timeline`
- Composite PKs on `(id, workspace_id)` for `leads`, `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs`

### 3.2 Query patterns — CONCERNS

- `LeadAssignmentService.get_eligible_members` uses a single aggregated `func.count(Lead.id)` query rather than N+1 per member.
- However, `assign_leads_batch` calls `assign_lead` once per lead, and `assign_lead` re-invokes `get_eligible_members` each time. For large imports this produces O(n) identical queries.
- `reassign_lead` runs a per-target count query for capacity; this is acceptable for a single manual operation but not batched.

### 3.3 Round-Robin cursor & multi-worker — CONCERNS

- Redis `INCR` cursor is fast and atomic.
- `LeadAssignmentService` falls back to `self._in_memory_cursors` when Redis is `None` (`lead_assignment_service.py:157-160`). This fallback is per-process, so multiple workers or containers lose cursor synchronization and assignment fairness.

### 3.4 Latency / load evidence — GAP

There are no defined P95/P99 SLOs and no load tests for the Kanban drag operation, stage transition, or batch lead assignment. This is a missing evidence gap.

---

## 4. Reliability

### 4.1 Idempotent billing — PASS

`BillingEventService._record_business_event` uses a Postgres advisory lock + `SELECT ... FOR UPDATE` on existing `BillingEvent` rows, plus a check for pending objects in `session.new` / `session.added`, to prevent duplicate billing events (`billing_event_service.py:775-812`).

### 4.2 Error handling & API contracts — CONCERNS

- `transition_lead_stage` returns 409 with a machine-readable body.
- `create_pipeline_stage` catches `IntegrityError` and returns 409.
- `assign_or_reassign_lead` catches `NoEligibleAssigneeError` and returns 400.
- `BillingEventService._record_business_event` **does not** convert `SpendCapExceededError` from `record_spend` to `InsufficientCreditsError`, breaking the contract for callers that expect `wallet_credit.InsufficientCreditsError` (`contact_unlock_service.py`, `lead_intelligence/scoring/service.py`, etc.).

### 4.3 Atomic credit flow — FAIL / HIGH

The `WorkspaceCreditService.deduct_credits` ordering bug (deduct balance before cap) and the `BillingEventService` exception-conversion gap both reduce reliability of the credit pipeline.

### 4.4 Test evidence — CONCERNS

- `tests/integration/services/test_team_crm_pipeline.py` is a stub: it never hits the database or real routes.
- `tests/unit/services/test_workspace_credit_pooling.py` tests `FakeAsyncSession` stand-ins, not the production `UPDATE ... WHERE ... RETURNING` SQL.
- `tests/unit/services/test_billing_event_service.py` and `tests/unit/capabilities/test_billing.py` monkeypatch `WorkspaceCreditService.record_spend`, so the real per-seat spend-cap gate in billable operations is not unit-tested.
- `tests/integration/services/test_credit_deduction_race.py` is strong real-Postgres coverage and passes.
- Playwright E2E `kanban-multicontext-sync.spec.ts` exists but was not executed and currently lacks 409 toast / timeline content assertions.

---

## 5. Recommended Actions

### Immediate (Before Release) — HIGH

1. **Fix `WorkspaceCreditService.deduct_credits` ordering / refund**  
   File: `nowing_backend/app/services/workspace_credit_service.py:163-215`  
   Either perform the `WorkspaceMembership` cap-gated `UPDATE` first and only on success update `Workspace.credit_micros_balance`, or explicitly refund the workspace balance when the cap update fails. This prevents lost shared credits under concurrency.

2. **Convert `SpendCapExceededError` in `BillingEventService._record_business_event`**  
   File: `nowing_backend/app/services/billing_event_service.py:814-823`  
   Wrap `record_spend` in the same `try...except SpendCapExceededError` pattern used in `billing.py _debit_with_workspace_spend_cap` and re-raise as `wallet_credit.InsufficientCreditsError` (or the expected caller contract).

3. **Implement role-based lead visibility per INV-23.6**  
   Files: `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:261-302` (RLS policy), `nowing_backend/app/routes/lead_pipeline_routes.py` (query filters)  
   Add `assigned_to_user_id` / role predicates so non-admin/non-owner members only see leads assigned to them.

### Short-term (Next Milestone) — MEDIUM

4. **Refactor unit tests to exercise production SQL**  
   Files: `nowing_backend/tests/unit/services/test_workspace_credit_pooling.py`, `tests/unit/services/test_billing_event_service.py`, `tests/unit/capabilities/test_billing.py`  
   Remove `FakeAsyncSession` and `record_spend` monkeypatching; run against real SQL or a realistic in-memory DB so the `UPDATE ... WHERE ... RETURNING` spend-cap gate is actually tested.

5. **Decide and document the shared wallet billing contract**  
   Either wire `WorkspaceCreditService.deduct_credits` into live billable operations (and fix the order bug), or remove/deprecate it if option 2 (`record_spend` + user wallet) is the intended design.

6. **Route legacy direct debit paths through the spend-cap gate**  
   Files: `phone_waterfall_service.py`, `outcome_pricing_service.py`, `etl_credit_service.py`, `gateway/zalo/zns_client.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py`  
   Replace direct `wallet_credit.apply_debit` with `WorkspaceCreditService.record_spend` + `wallet_credit.apply_debit`, or with `billing.py _debit_with_workspace_spend_cap`.

7. **Optimize and harden `LeadAssignmentService.assign_leads_batch`**  
   File: `nowing_backend/app/services/lead_assignment_service.py:198-223`  
   Compute eligible members once per batch, use row-level locks or atomic `Lead` updates to prevent capacity overruns, and remove the in-memory Redis fallback or document that Redis is required for multi-worker fairness.

### Long-term / Monitoring — LOW

8. **Define and instrument latency SLOs** for Kanban drag, stage transition, and batch assignment; add p95 telemetry or a load test.

9. **Execute and strengthen Playwright E2E** `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts` to assert 409 conflict toast, version merge, and chronological timeline content.

10. **Add integration tests** for scraper/chat → `assign_leads_batch` auto-trigger and multi-worker Round-Robin fairness.

---

## 6. Gate Status

| Criterion | Status |
| --- | --- |
| Concurrency / atomicity of shared credit pool | ⚠️ **CONCERNS** (HIGH: `deduct_credits` ordering, `BillingEventService` exception contract) |
| Fail-closed RLS / role-based visibility | ⚠️ **CONCERNS** (HIGH: role-based lead visibility missing) |
| Optimistic Concurrency Control on Kanban | ✅ **PASS** |
| Round-Robin assignment atomicity & fairness | ⚠️ **CONCERNS** (MEDIUM: capacity TOCTOU, in-memory cursor fallback) |
| Per-seat spend cap wiring | ⚠️ **CONCERNS** (MEDIUM: partial wiring; legacy direct debits bypass cap) |
| Test evidence quality | ⚠️ **CONCERNS** (MEDIUM: fake/stub unit tests, strong integration tests) |
| **Overall** | ⚠️ **CONCERNS** |

**Recommendation:** Resolve the three HIGH findings (`deduct_credits` ordering, `BillingEventService` exception conversion, and role-based RLS) before release. After fixes, re-run the full verification command set and the `bmad-testarch-nfr` workflow.

---

## 7. Next Steps in Nowing Quality Pipeline

**Completed:** `bmad-testarch-nfr` v5.0 — NFR evidence audit for Story 24.3 produced `nfr-audit-24-3.md` with overall status **CONCERNS** and 3 HIGH action items.

**Next required (P0-gated):**
- [4.13] `bmad-nowing-human-review-gate` — P0 human review for `workspace_credit_service.py`, `lead_assignment_service.py`, `lead_pipeline_routes.py`, `billing_event_service.py`, and `capabilities/core/billing.py`. This is the hard gate; do not mark story done until P0 areas are reviewed and the 3 HIGH NFR findings are addressed.

**Next recommended:**
- [4.14] `bmad-nowing-web-e2e-gate` — Run Playwright E2E for `components/leads/pipeline/LeadKanbanBoard.tsx` and `kanban-multicontext-sync.spec.ts` after backend fixes are merged. Skip only if no UI changes are touched in the next fix round.
- [4.17] `bmad-retrospective` — Run at epic-24 completion if Story 24.3 is the last story in the epic.

**Remaining in pipeline for this story:** 2 steps — 4.13 (required) and 4.14 (recommended). See `nowing-quality-pipeline.md` for the full workflow map.
