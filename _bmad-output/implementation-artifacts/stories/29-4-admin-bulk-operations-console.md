---
story_key: 29-4-admin-bulk-operations-console
status: ready-for-dev
baseline_commit: 179c9cfac52ff63e147fe6e8e1002167d73e018d
epic: 29
story: 4
---

# Story 29.4: Admin Bulk Operations Console

**Status:** `ready-for-dev`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-103, AR-17, AR-18, UX-DR-PRFAQ-5, INV-29.1, INV-29.2, AD-9, AD-54.  
**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory/schema), Epic 8 (billing/cost/wallet), Epic 25 (admin baseline), Epic 29.1 (custom roles for `assign_role`), Epic 29.3 (tier/quota for `apply_tier`).

---

## Story

As a **platform superuser or delegated Workspace Owner**,  
I want **a bulk operations console to query, dry-run, and execute actions across workspaces or members**,  
so that **I can respond to abuse, compliance requests, and tenant-wide changes safely and auditably**.

---

## Acceptance Criteria

### AC-1 — Action Catalog & Permission Boundary (INV-29.1, AD-9, AD-54)
**Given** the bulk-ops console,  
**When** an actor opens it,  
**Then**:
1. Superadmin sees all `BulkAction` values: `archive_inactive_workspaces`, `rotate_api_keys`, `assign_role`, `delete_source_type_memories`, `apply_tier`, `revoke_membership`.
2. Workspace Owner only sees actions that operate within `workspace_id` they own and that they have `Permission.SETTINGS_UPDATE` + `Permission.MEMBERS_REMOVE` for.
3. Owner route injects `workspace_id` filter immutably; any filter attempting to override another workspace is rejected with `403`.
4. `assign_role` and `apply_tier` are disabled/return `409 missing_dependency` if Story 29.1 / 29.3 services are not present.

### AC-2 — Structured Filter Builder (FR-103)
**Given** the admin opens `/admin/saas/bulk-ops`,  
**When** they build a filter,  
**Then**:
1. The UI uses a structured filter builder (not free-form NLP) against an allow-list of fields and operators.
2. Filter target table depends on action (e.g. `workspaces` for `archive_inactive_workspaces`, `workspace_memberships` for `revoke_membership`, `memories` for `delete_source_type_memories`).
3. The backend validates all fields/operators against `BULK_FILTER_ALLOWLIST[action]` and rejects with `422` if disallowed.
4. Dry-run preview returns exact `COUNT(*)` and paginated subject IDs without mutating data.

### AC-3 — Dry-Run & Execute with Idempotency (INV-29.2)
**Given** the admin selects an action and completes dry-run,  
**When** they provide an `Idempotency-Key` header and click Execute,  
**Then**:
1. Backend creates `bulk_op_job` row with `status=queued`, `action`, `filter` (JSONB), `actor_id`, `idempotency_key`, `request_hash` (SHA-256).
2. Returns `202 Accepted` with `job_id`.
3. Rejects duplicate `Idempotency-Key` with `409` unless the request hash matches (then returns existing job).
4. `Idempotency-Key` must be UUID v4, max 64 chars; missing or invalid returns `400`.

### AC-4 — Async Job Execution & Progress (FR-103, NFR-1)
**Given** a bulk op is running,  
**When** the admin polls `GET /admin/saas/bulk-ops/{job_id}`,  
**Then**:
1. Response contains `status`, `affected_count`, `processed_count`, `error_count`, `started_at`, `finished_at`.
2. Progress percent is `processed_count / affected_count` (or `0` if no affected count yet).
3. Cancel button is visible if action is in the cancelable set (`archive_inactive_workspaces`, `delete_source_type_memories`, `revoke_membership`) and `status` is `queued` or `running`.
4. Job status values: `queued`, `running`, `completed`, `failed`, `cancelled`, `partial`.

### AC-5 — Audit & Error Handling (AR-18)
**Given** any bulk op completes or fails,  **When** the job finishes,  **Then**:
1. One `AuditEvent` per affected subject is written with `actor_id`, `subject_type`, `subject_id`, `diff_payload`, `idempotency_key`.
2. A summary `AuditEvent` row is written with `action=bulk_op.{action}.summary`, `affected_count`, `error_count`.
3. Failed rows are written to `bulk_op_errors` with `job_id`, `subject_type`, `subject_id`, `error_message`, `retryable`.
4. UI exposes a download link for `bulk_op_errors` CSV/JSON.

### AC-6 — High-Risk Action Gate (NFR-2, FR-103)
**Given** the admin selects `rotate_api_keys`,  **When** they attempt to execute,  **Then**:
1. UI requires password/MFA confirmation before submitting.
2. Backend verifies the password/MFA token before enqueueing the job.
3. Failure to confirm returns `403` without creating a `bulk_op_job`.

### AC-7 — UI Workflows (UX-DR-PRFAQ-5 BO-1..BO-6)
**Given** the frontend,  **Then**:
1. `/admin/saas/bulk-ops` renders the superadmin console with action selector, structured filter builder, dry-run card, idempotency key input, and job polling view.
2. `/admin/admin-shell.tsx` includes navigation link to `Bulk Ops`.
3. Owner view can be a tab inside `/dashboard/[workspace_id]/workspace-settings/bulk-ops` (or `/settings/bulk-ops`).
4. Filter builder field/operator list is driven by contract type per action.

---

## Dev Notes

### Architecture Compliance
- Use SQLAlchemy 2.0 async pattern; all filter builder output must be compiled to `select()` + `where()` with parameterized values.
- Reuse `require_superuser()` for superadmin routes and `check_permission()` from `app/utils/rbac.py` for owner-scoped routes.
- Reuse `AuditEvent` from `app/models/billing.py` and `WorkspaceLimit`/`SubscriptionChange` logic from `app/services/workspace_limits.py` for `apply_tier`.
- Celery integration: add `bulk_op_executor` task in `app/tasks/celery_tasks/bulk_op_tasks.py` following `health_retention_task.py` pattern.
- Idempotency table `bulk_op_jobs` already includes `idempotency_key` unique index; no separate `idempotency_keys` table needed for this story.

### Model Assumptions
- `Workspace` table may need an `archived_at` / `is_active` column for `archive_inactive_workspaces`; if absent, the migration must add it.
- `WorkspaceMembership` has `role_id`; `revoke_membership` can either delete row or set `archived_at` depending on existing convention.
- `Memory` has `source_type` (MemorySourceType enum) and `workspace_id`; `delete_source_type_memories` uses `MemorySourceType` allow-list.
- API keys: `Workspace.api_access_enabled` can be toggled off for `rotate_api_keys` v1; full key rotation may be deferred.

### Permission Guard
- Owner must hold both `Permission.SETTINGS_UPDATE` and `Permission.MEMBERS_REMOVE`; if custom roles (29.1) are present, resolve role permissions via `membership.role.permissions`.
- Superadmin bypasses workspace permission but must still pass `require_superuser()`.

### Filter Allow-List Examples
- `archive_inactive_workspaces` fields: `plan_tier`, `created_at`, `last_activity_at`, `vertical`.
- `revoke_membership` fields: `role_id`, `joined_at`, `user_id`.
- `delete_source_type_memories` fields: `source_type`, `created_at`, `confidence`.
- Operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`.

### Testing Standards
- Unit test filter validation and idempotency in `tests/integration/services/test_bulk_ops_service.py`.
- Route tests in `tests/integration/routes/test_admin_bulk_ops.py`.
- TS contract tests in `nowing_web/tests/admin/bulk-ops-schema.test.ts`.
- Optional Playwright E2E in `nowing_web/tests/admin/bulk-ops.spec.ts`.

### Files to Touch
- `nowing_backend/app/models/bulk_ops.py` (new)
- `nowing_backend/alembic/versions/<new>_add_bulk_op_job_and_error_tables.py` (new)
- `nowing_backend/app/services/bulk_ops_service.py` (new)
- `nowing_backend/app/tasks/celery_tasks/bulk_op_tasks.py` (new)
- `nowing_backend/app/schemas/bulk_ops.py` (new)
- `nowing_backend/app/routes/admin_saas_routes.py` (extend) or `admin_bulk_ops_routes.py` (new)
- `nowing_backend/app/routes/workspaces_routes.py` (owner endpoints)
- `nowing_backend/app/db/__init__.py` (export new models)
- `nowing_web/contracts/types/admin-bulk-ops.types.ts` (new)
- `nowing_web/lib/apis/admin-bulk-ops-api.service.ts` (new)
- `nowing_web/app/admin/saas/bulk-ops/page.tsx` (new)
- `nowing_web/components/admin/bulk-ops/` (new)
- `nowing_web/app/admin/admin-shell.tsx` (nav)
- `nowing_web/messages/en.json`, `vi.json` (i18n)

### References
- FR-103, AR-17, AR-18, UX-DR-PRFAQ-5 in `_bmad-output/planning-artifacts/epics.md` §Epic 29.
- UX-DR BO-1..BO-6 in `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md` §4.
- INV-29.1, INV-29.2 in `epics.md` §Architectural Invariants.
- `admin_credits_routes.py` idempotency pattern.
- `admin_saas_routes.py` CRUD pattern from Story 29.3.
- `check_permission` in `app/utils/rbac.py`.
- `AuditEvent` in `app/models/billing.py`.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

### Change Log
