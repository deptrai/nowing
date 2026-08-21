# Human Review Gate — Story 24.3

**Date:** 2026-08-21
**Story:** 24.3 — Multi-Seat Team CRM Pipeline & Shared Workspace Credit Pooling
**Result:** ❌ P0 areas touched — human review required before `done`

## P0 Areas Detected

| P0 Area | Files / Evidence | Why it matters |
|---|---|---|
| **Token tracking / quota / credit** | `nowing_backend/app/services/workspace_credit_service.py` (per-seat spend cap, atomic credit deduction/refund), `nowing_backend/app/services/billing_event_service.py` (`_record_business_event`), `nowing_backend/app/capabilities/core/billing.py` (`_debit_with_workspace_spend_cap` replaces direct `wallet_credit.apply_debit` for web crawl / captcha / chainlens / platform meters / BDS aggregate / jobs aggregate) | Bug = revenue leak, double-charge, negative balance, credit fraud, or spend-cap bypass |
| **Authentication / authorization** | `nowing_backend/app/routes/lead_pipeline_routes.py` (pipeline CRUD, assignment, stage transitions), `nowing_backend/app/routes/rbac_routes.py` (membership read/update with `monthly_spend_cap_micros`/`lead_capacity`), `nowing_backend/app/auth/impersonation.py` + `app/app.py:790` (`ImpersonationGuardMiddleware`, scope-creep from 25.1), `nowing_backend/app/db.py` (Workspace/WorkspaceMembership changes) | Bypass = cross-workspace data leak, unauth lead reassignment, membership cap tampering |
| **Data integrity** | `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py` (new CRM tables, credit fields, RLS, indexes, composite PK), `nowing_backend/alembic/versions/222_add_credit_transactions_table.py` (scope-creep from 25.2), `nowing_backend/app/db.py` (model definitions for `lead_pipeline_stages`, `lead_assignments`, `lead_activity_logs`, `Workspace.credit_micros_balance`, `WorkspaceMembership.monthly_spend_cap_micros`) | Silent data loss, orphaned records, migration conflicts, RLS holes |
| **External integrations with side effects** | `nowing_backend/app/services/lead_assignment_service.py` auto-triggers from `lead_gen_orchestrator.py`, `lead_clipper_routes.py`, `social_stream_worker.py` — these call external scrapers/chat sources and then assign leads | Real-world side effects: lead ingestion, credit spend, workspace membership access |

## What to review manually

1. **Credit arithmetic & spend-cap atomicity**
   - `WorkspaceCreditService.deduct_credits` / `record_spend` / `refund_credits` (`nowing_backend/app/services/workspace_credit_service.py`)
   - Verify boundary inputs: `balance == requested amount exactly`, `monthly_spent_micros == cap exactly`, `NULL` cap handled, concurrent debit/refund does not overdraft.
   - Confirm conditional `UPDATE ... WHERE` correctly guards balance and per-seat cap under race.

2. **Per-seat spend-cap wiring into billable operations**
   - `_debit_with_workspace_spend_cap` in `nowing_backend/app/capabilities/core/billing.py`
   - Confirm every billable operation (web crawl, captcha, chainlens research, platform meters, VN BDS/jobs aggregate) routes through the new helper and that `SpendCapExceededError` is converted to `InsufficientCreditsError` for callers.

3. **Lead pipeline route authorization**
   - `nowing_backend/app/routes/lead_pipeline_routes.py` (all `POST/PUT/PATCH/DELETE` handlers)
   - Confirm no `allow_any_principal` remains; every route checks workspace membership and role.
   - Verify RLS `FORCE` is set on new tables and `client_id` predicate is consistent.

4. **Round-robin assignment fairness & capacity**
   - `nowing_backend/app/services/lead_assignment_service.py`
   - Confirm Redis cursor is actually used across workers (not in-memory), `current_leads` count excludes terminal stages, and `Lead.assigned_to_user_id` is updated atomically with `lead_assignments`.

5. **Migration 221 correctness & branch safety**
   - `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py`
   - Confirm `down_revision` is correct (no branch conflict), `FORCE ROW LEVEL SECURITY` present, indexes added, composite PK `(id, workspace_id)` on CRM tables.

6. **Scope-creep ownership (deferred from 24.3)**
   - `ImpersonationGuardMiddleware` / CORS chrome-extension regex → story 25.1 / 24.5
   - `GlobalDncRecord` / `AuditEvent` / `CreditTransaction` / `tax_id` / `company_status` fields → stories 24.2 / 24.4 / 25.2
   - Ensure these are tracked and not silently left untested.

## Status

- Story file updated to `pending-human-review`.
- Sprint-status `24-3` updated to `pending-human-review`.
- After manual review, update to `done` (approved) or `in-progress` (changes needed).
