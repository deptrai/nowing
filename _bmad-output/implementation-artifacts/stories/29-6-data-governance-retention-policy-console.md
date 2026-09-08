---
story_key: 29-6-data-governance-retention-policy-console
status: in-progress
baseline_commit: 0e2be000a0e55a397f9476f3bcf7e99f9ac7fb13
epic: 29
story: 6
---

# Story 29.6: Data Governance & Retention Policy Console

**Status:** `completed`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-97, FR-104, AR-13, AR-17, AR-18, UX-DR-PRFAQ-5, UX-DR-PRFAQ-6, NFR-1, NFR-2, NFR-5, INV-28.2, INV-29.2, AD-28.3.  
**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory, `Memory`, `MemoryVersion`, `MemoryRelation`, `MemorySourceType`), Epic 21.14 (`WorkspaceDncRecord`, `GlobalDncRecord`, `DncComplianceService`), Epic 28.3 (ToS review + source risk tier ownership), Epic 28.5 (`memory_retention_*` columns, `archived_at`, `MemoryErasureService`, `apply_memory_retention_policies` Celery task), Epic 29.1 (`WorkspaceRole` + permissions), Epic 29.4 (`BulkOpJob`/`bulk_op_errors` + idempotency pattern).

---

## Story

As a **workspace Owner or platform superuser**,  
I want **a governance console to manage data retention policy, source risk tiers, DNC list, and right-to-delete flows**,  
so that **Nowing cloud stays compliant with scraped-source ToS and data-subject requests, while self-host operators keep responsibility for their own compliance**.

---

## Acceptance Criteria

### AC-1 — Governance Console Overview (FR-97, FR-104, AR-13, UX-DR-PRFAQ-6 GV-1)
**Given** the Owner or superuser opens `/dashboard/[workspace_id]/governance`,  
**When** the page loads,  
**Then**:
1. The UI shows a governance menu with tabs: `Data Retention`, `Source Risk Tiers`, `DNC`, `Audit Log`, `Workspace Status`.
2. The `Data Retention` tab displays the active retention policy from `Workspace`: `document_retention_days`, `auto_archive_enabled`, `document_retention_action`, `memory_retention_days`, `memory_auto_archive_enabled`, `memory_retention_action`.
3. The `DNC` tab displays the workspace `WorkspaceDncRecord` list with `record_type`, `value`, `reason`, `source`, `created_at`, `updated_at`.
4. The `Audit Log` tab lists `audit_events` filtered to the current `workspace_id` with columns `action`, `actor_id`, `created_at`, `diff_payload` summary.
5. The `Workspace Status` tab shows whether `workspace.archived_at` is set and allows restore within the unarchive window when permitted.
6. All tabs enforce `workspace_id` scoping in SQL `WHERE` (no cross-tenant leakage).

### AC-2 — Retention Policy Editing (FR-97, AD-28.3, AR-18)
**Given** the Owner edits the retention policy,  
**When** they save changes,  
**Then**:
1. Backend validates that `memory_retention_days` and `document_retention_days` are positive integers `<= 36500` when the corresponding `auto_archive_enabled` flag is `true`.
2. The retention policy update is logged to `audit_events` with `action="governance.retention_policy_update"`, `actor_id`, and `diff_payload` containing the before/after values.
3. The existing Celery tasks `apply_document_retention_policies` and `apply_memory_retention_policies` continue to pick up the new values on the next run — no additional scheduling is required in this story.
4. If any source risk tier is configured with a stricter retention window than the requested workspace policy, the backend rejects the save with `422` and a field-level error naming the violating `source_type` and its required minimum retention days.
5. Only Owner or users with `settings:update` permission can edit; viewers with `settings:view` see read-only state.

### AC-3 — Source Risk Tier Management (FR-97, AD-28.3)
**Given** the Owner or superuser opens `Source Risk Tiers`,  
**When** they view or edit tiers,  
**Then**:
1. The page shows the mapping `source_type` → `risk_tier` for all `MemorySourceType` values used by the workspace (or a curated list from `memory_source_legal_tiers` when the table exists).
2. If the `memory_source_legal_tiers` table does not yet exist, the backend creates it via Alembic with columns `id` (serial PK), `source_type` (String, unique), `risk_tier` (`low` | `medium` | `high`), `recommended_retention_days` (Integer, nullable), `notes` (Text, nullable), `created_at`, `updated_at`.
3. Changing a `source_type` from `low` to `high` triggers a workspace-scoped scrape pause: the backend sets `Workspace.api_access_enabled = false` (or introduces `scrape_paused_at` / `scraping_paused` if a dedicated flag already exists) and emits `audit_events` with `action="governance.source_risk_tier_change"`.
4. The UI shows a warning modal requiring explicit opt-in before allowing resumption.
5. Resumption is only allowed after the Owner confirms they accept the risk; resuming writes `audit_events` with `action="governance.source_risk_tier_resume"`.

### AC-4 — Right-to-Delete Request Queue (FR-97, AD-28.3, INV-28.2)
**Given** the Owner or a user with `memory:delete` permission opens `Right-to-Delete`,  
**When** they submit a request,  
**Then**:
1. The UI supports two request types: `single_memory` (by `memory_id`) and `bulk` (by `source_type`, `source_id`, `source_entity_type`, optional `created_before`/`created_after` filters).
2. Before execution, the backend runs a **dry-run** that returns `affected_count` and a preview list of `memory_id` values (capped at 1,000 for UI display) without mutating data.
3. On explicit confirmation, the backend creates a `bulk_op_job` row (reusing `BulkOpJob` from Story 29.4) with `action="delete_source_type_memories"`, `idempotency_key`, `request_hash`, and `filter_spec` describing the request.
4. Bulk deletion is executed in chunks of 1,000 rows with `processed_count` / `affected_count` progress reporting and cancel-ability while `status` is `queued` or `running`.
5. `single_memory` requests are executed synchronously through `MemoryErasureService.delete_memory` and return `204`.
6. Every deletion writes `audit_events` with `action="memory_delete"` (single) or `action="bulk_delete"` (bulk) and `diff_payload` containing `reason`, `requester_id`, and `affected_count`.

### AC-5 — Workspace DNC Management (FR-97, AR-13, AD-28.3)
**Given** the Owner opens the `DNC` tab,  
**When** they add or remove a record,  
**Then**:
1. `POST /workspaces/{workspace_id}/dnc` accepts `record_type` (`phone`, `email`, `domain`, `tax_id`), `value`, and `reason`; the backend normalizes the value and computes `value_hmac` using the existing `hash_phone_hmac` / normalizer functions before inserting into `workspace_dnc_records`.
2. Duplicate `(workspace_id, record_type, value_hmac)` entries upsert `reason` and `source` without stacking rows.
3. After insert/update, `DncComplianceService.invalidate_workspace_cache(workspace_id)` is called so suppression takes effect within < 1s.
4. `DELETE /workspaces/{workspace_id}/dnc/{record_id}` removes the workspace-scoped record and invalidates the cache.
5. If `GLOBAL_DNC_ENABLED` is `true`, the UI also displays global `global_dnc_records` that conflict with workspace entries; conflicting workspace entries are marked `superseded_by_global` in the response payload (derived, not persisted).
6. Every DNC mutation writes `audit_events` with `action="governance.dnc_add"` / `governance.dnc_remove"` and `diff_payload` containing `record_type`, `value_hmac`, and `reason`.

### AC-6 — Self-Host vs Cloud Policy Boundary (FR-97, AD-28.3)
**Given** the deployment mode,  
**When** the governance console loads,  
**Then**:
1. Cloud deployments show the full console and enforce the retention policy validation described in AC-2.
2. Self-host deployments display a notice that the operator retains responsibility for source compliance; the console still allows local DNC management and retention edits, but source risk tier warnings are advisory rather than blocking.
3. The `Workspace Status` tab clearly distinguishes `archived_at` soft-deleted workspaces (restorable within 7 days) from hard-deleted workspaces (not reversible).

### AC-7 — Audit & Observability (AR-18, NFR-2, NFR-5)
**Given** any governance mutation,  
**Then**:
1. Every retention policy change, source risk tier change, DNC add/remove, and right-to-delete execution writes an `audit_events` row with `actor_id`, `action`, `diff_payload`, and `created_at`.
2. The `Audit Log` tab supports filtering by `action` prefix (`governance.*`, `memory_delete`, `bulk_delete`) and date range.
3. All mutations are idempotent where applicable: DNC upserts use the unique constraint, bulk deletes reuse `idempotency_key` from `bulk_op_jobs`, and right-to-delete dry-run is side-effect free.

---

## Dev Notes

### Architecture Compliance
- Use SQLAlchemy 2.0 async `AsyncSession`; every route opens its own session via `get_async_session`.
- Reuse `check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)` for Owner/Editor mutations and `Permission.SETTINGS_VIEW.value` for read-only views.
- Superadmin routes use `require_superuser()` from `app/users.py` where platform-wide visibility is required (e.g., global DNC list).
- Reuse `MemoryErasureService` from `app/services/memory/erasure_service.py` for single and bulk deletion; do not duplicate the chunked delete loop.
- Reuse `BulkOpJob` / `BulkOpError` / `IdempotencyKey` models and patterns from Story 29.4 for bulk right-to-delete jobs.
- Reuse `DncComplianceService` and `hash_phone_hmac` / `normalize_*` helpers from `app/lead_intelligence/dnc/` for all DNC writes.
- Retention policy validation happens in `app/routes/workspaces_routes.py` (or a new `governance_routes.py`) by extending the existing `update_workspace` retention-field validation.
- Source risk tier storage: if `memory_source_legal_tiers` does not exist, create it via Alembic and add a read/write service; do not invent a parallel table.

### Model Assumptions
- `Workspace` columns already exist: `document_retention_days`, `auto_archive_enabled`, `document_retention_action`, `memory_retention_days`, `memory_auto_archive_enabled`, `memory_retention_action`, `archived_at` (added in Story 29.4), `api_access_enabled`.
- `Memory` columns: `id`, `workspace_id`, `source_type`, `source_id`, `source_entity_type`, `archived_at`, `created_at`, `confidence`.
- `MemorySourceType` values are the enum members from `app/db/enums.py` (`DOCUMENT`, `CHAT_MESSAGE`, `SCRAPER_RUN`, `MANUAL`, `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `CRM_CONNECTION`, `CRM_SYNC`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`, `LUMA_CONNECTOR`, `ELASTICSEARCH_CONNECTOR`, `WEBCRAWLER_CONNECTOR`, `BOOKSTACK_CONNECTOR`, `CIRCLEBACK_CONNECTOR`, `OBSIDIAN_CONNECTOR`, `MCP_CONNECTOR`, `EXA_MCP_CONNECTOR`, `DROPBOX_CONNECTOR`, `COMPOSIO_GOOGLE_DRIVE_CONNECTOR`, `COMPOSIO_GMAIL_CONNECTOR`, `COMPOSIO_GOOGLE_CALENDAR_CONNECTOR`, `RSS_FEED`).
- `WorkspaceDncRecord` columns: `id` (UUID), `workspace_id`, `record_type`, `value`, `value_hmac`, `reason`, `source`, `created_at`, `updated_at`.
- `GlobalDncRecord` columns: `id` (UUID), `record_type`, `value`, `value_hmac`, `reason`, `source`, `created_at`, `updated_at`.
- `BulkOpJob` columns: `id` (UUID), `action`, `status`, `actor_id`, `workspace_id`, `filter_spec` (JSONB), `action_params` (JSONB), `idempotency_key`, `request_hash`, `total_count`, `processed_count`, `affected_count`, `error_count`, `celery_task_id`, `started_at`, `completed_at`, `error_message`.
- `AuditEvent` columns: `action` (String), `actor_id` (UUID), `subject_id` (UUID), `diff_payload` (JSONB), `ticket_ref`, `ip_address`, `user_agent`, `created_at`, `updated_at`.

### Permission Guard
- `GET /workspaces/{workspace_id}/governance` → `Permission.SETTINGS_VIEW` (Owner/Superadmin implicit).
- `PUT /workspaces/{workspace_id}/governance/retention` → `Permission.SETTINGS_UPDATE`.
- `POST /workspaces/{workspace_id}/governance/dnc` → `Permission.SETTINGS_UPDATE`.
- `DELETE /workspaces/{workspace_id}/governance/dnc/{record_id}` → `Permission.SETTINGS_UPDATE`.
- `POST /workspaces/{workspace_id}/governance/right-to-delete` → `Permission.MEMORY_DELETE` (or `SETTINGS_UPDATE` for Owner).
- `POST /workspaces/{workspace_id}/governance/source-risk-tiers` → `Permission.SETTINGS_UPDATE`.
- `GET /admin/saas/governance` → `require_superuser()` for platform-wide read.

### Query & Performance
- DNC list query: `select(WorkspaceDncRecord).where(WorkspaceDncRecord.workspace_id == workspace_id).order_by(WorkspaceDncRecord.created_at.desc())` — use existing `ix_workspace_dnc_records_workspace_type` index.
- Audit log query: `select(AuditEvent).where(AuditEvent.diff_payload['workspace_id'].astext == str(workspace_id)).order_by(AuditEvent.created_at.desc())` — audit events do not have a dedicated `workspace_id` column; filter inside `diff_payload` JSONB or add a computed column if performance becomes an issue.
- Right-to-delete dry-run uses `MemoryErasureService.count_matching_memories` — no new query needed.
- Source risk tier lookup: `select(MemorySourceLegalTier).where(MemorySourceLegalTier.source_type.in_(...))` — add index on `source_type`.

### Response Shapes (Backend)
- `GET /api/v1/workspaces/{workspace_id}/governance` returns:
  ```json
  {
    "retention_policy": {
      "document_retention_days": 365,
      "auto_archive_enabled": false,
      "document_retention_action": "archive",
      "memory_retention_days": 365,
      "memory_auto_archive_enabled": false,
      "memory_retention_action": "archive"
    },
    "source_risk_tiers": [{"source_type": "reddit", "risk_tier": "medium", "recommended_retention_days": 180}],
    "dnc_records": [{"id": "...", "record_type": "phone", "value": "+84901234567", "reason": "Opt-out", "source": "manual", "created_at": "..."}],
    "workspace_status": {"archived_at": null, "can_restore": true}
  }
  ```
- `PUT /api/v1/workspaces/{workspace_id}/governance/retention` accepts the same `retention_policy` object; returns the updated `WorkspaceRead` or `422` with field errors.
- `POST /api/v1/workspaces/{workspace_id}/governance/right-to-delete` accepts:
  ```json
  {"type": "single_memory", "memory_id": 123, "reason": "..."}
  ```
  or
  ```json
  {"type": "bulk", "source_type": "reddit", "source_id": 456, "dry_run": true, "reason": "..."}
  ```
  Dry-run returns `{"dry_run": true, "affected_count": N, "preview_memory_ids": [...]}`; confirm returns `{"job_id": "...", "status": "queued"}`.
- `POST /api/v1/workspaces/{workspace_id}/governance/dnc` returns the created `DncRecordRead`.
- `DELETE /api/v1/workspaces/{workspace_id}/governance/dnc/{record_id}` returns `204`.

### Frontend Components (proposed)
- `app/dashboard/[workspace_id]/governance/page.tsx` — page shell with tab navigation.
- `components/governance/GovernanceTabs.tsx` — Data Retention / Source Risk / DNC / Audit Log / Workspace Status tabs.
- `components/governance/RetentionPolicyPanel.tsx` — form for document + memory retention fields (reuse `data-retention-manager.tsx` pattern).
- `components/governance/SourceRiskTierTable.tsx` — editable table for source → risk tier mapping with high-risk confirmation modal.
- `components/governance/DncList.tsx` — list + add/remove form (reuse patterns from `components/leads/` or `components/settings/`).
- `components/governance/RightToDeletePanel.tsx` — request type selector, dry-run preview card, confirm + job polling (reuse `bulk-ops` UI patterns from Story 29.4).
- `components/governance/AuditLogTable.tsx` — filterable table for `audit_events`.
- `lib/apis/governance-api.service.ts` — API client.
- `contracts/types/governance.types.ts` — Zod schemas.
- `app/dashboard/[workspace_id]/layout.tsx` or nav provider — add "Governance" nav item under workspace settings.

### Testing Standards
- Integration tests in `nowing_backend/tests/integration/routes/test_governance_routes.py`:
  - governance overview returns correct retention policy and DNC list scoped to workspace;
  - retention update rejects invalid `memory_retention_days` when `memory_auto_archive_enabled` is true;
  - source risk tier change to `high` pauses scraping and writes `audit_events`;
  - right-to-delete dry-run returns count without deleting; confirm creates `bulk_op_job` and chunks deletes;
  - DNC add/remove upserts correctly and invalidates cache;
  - 403 for non-owner attempting to edit retention policy.
- Integration tests in `nowing_backend/tests/integration/services/test_governance_service.py`:
  - `MemoryErasureService.bulk_delete_memories` chunking and audit;
  - retention policy validation against `memory_source_legal_tiers` shortest-window rule;
  - `audit_events` payload shape for `governance.*` actions.
- Frontend contract tests in `nowing_web/tests/governance/governance-schema.test.ts`.
- Optional Playwright E2E in `nowing_web/tests/governance/governance.spec.ts`.

### Files to Touch (NEW and UPDATE)
- **NEW:**
  - `nowing_backend/alembic/versions/YYYYMMDD_add_memory_source_legal_tiers.py` — create `memory_source_legal_tiers` table (if missing) and add `scrape_paused_at` or equivalent pause flag to `workspaces` if not present.
  - `nowing_backend/app/models/memory_source_legal_tier.py` — `MemorySourceLegalTier` model.
  - `nowing_backend/app/schemas/governance.py` — `GovernanceOverviewRead`, `RetentionPolicyUpdate`, `SourceRiskTierUpdate`, `DncRecordCreate`, `DncRecordRead`, `RightToDeleteRequest`, `RightToDeleteResponse`, `AuditLogFilter`, `AuditLogRead`.
  - `nowing_backend/app/services/governance_service.py` — retention policy validation, source risk tier CRUD, DNC orchestration, right-to-delete orchestration.
  - `nowing_backend/app/routes/governance_routes.py` — workspace-scoped governance endpoints.
  - `nowing_backend/tests/integration/routes/test_governance_routes.py`
  - `nowing_backend/tests/integration/services/test_governance_service.py`
  - `nowing_web/app/dashboard/[workspace_id]/governance/page.tsx`
  - `nowing_web/components/governance/*`
  - `nowing_web/contracts/types/governance.types.ts`
  - `nowing_web/lib/apis/governance-api.service.ts`
  - `nowing_web/messages/en.json` + `vi.json` i18n keys.
- **UPDATE:**
  - `nowing_backend/app/models/__init__.py` — export `MemorySourceLegalTier`.
  - `nowing_backend/app/db/__init__.py` — export new model and enums if needed.
  - `nowing_backend/app/routes/__init__.py` — register `governance_routes`.
  - `nowing_backend/app/routes/workspaces_routes.py` — extend retention validation to check source risk tiers, or delegate to `GovernanceService`.
  - `nowing_backend/app/services/bulk_ops_service.py` — allow `action="delete_source_type_memories"` to accept `dry_run` preview from governance console if not already supported.
  - `nowing_backend/app/tasks/celery_tasks/bulk_op_tasks.py` — ensure `delete_source_type_memories` is wired for chunked execution with progress.
  - `nowing_web/components/layout/providers/LayoutDataProvider.tsx` — add "Governance" nav item.
  - `nowing_web/app/dashboard/[workspace_id]/workspace-settings/` — link to governance console.

---

## References

- `nowing_backend/app/models/workspaces.py` — `Workspace` retention columns, `WorkspaceDncRecord`, `GlobalDncRecord`.
- `nowing_backend/app/models/memory.py` — `Memory`, `MemorySourceType`, `MemoryVersion`, `MemoryRelation`.
- `nowing_backend/app/models/billing.py` — `AuditEvent`.
- `nowing_backend/app/models/bulk_ops.py` — `BulkOpJob`, `BulkOpError`, `IdempotencyKey`, `BulkAction`.
- `nowing_backend/app/services/memory/erasure_service.py` — `MemoryErasureService` (single + bulk delete, dry-run, chunked 1,000).
- `nowing_backend/app/services/bulk_ops_service.py` — bulk job creation, idempotency, progress.
- `nowing_backend/app/lead_intelligence/dnc/service.py` — `DncComplianceService` cache invalidation.
- `nowing_backend/app/lead_intelligence/dnc/normalizer.py` — `hash_phone_hmac`, `normalize_*`.
- `nowing_backend/app/routes/dnc_routes.py` — existing DNC endpoints to reuse or wrap.
- `nowing_backend/app/routes/workspaces_routes.py` — existing retention validation in `update_workspace`.
- `nowing_backend/app/tasks/celery_tasks/memory_retention_task.py` — `apply_memory_retention_policies`.
- `nowing_backend/app/tasks/celery_tasks/document_retention_task.py` — `apply_document_retention_policies`.
- `nowing_backend/app/utils/rbac.py` — `check_permission`.
- `nowing_backend/app/users.py` — `require_superuser`.
- `_bmad-output/planning-artifacts/epics.md` — Epic 29 / Story 29.6 source AC.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md` — retention policy, right-to-delete, source risk tier decisions.
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md` — GV-1..GV-6 governance console contract.
- `_bmad-output/implementation-artifacts/stories/28-5-workspace-memory-storage-cap-and-retention.md` — retention schema, `archived_at`, `MemoryErasureService`.
- `_bmad-output/implementation-artifacts/stories/29-4-admin-bulk-operations-console.md` — `BulkOpJob`, idempotency, chunked delete patterns.
- `_bmad-output/implementation-artifacts/stories/29-5-memory-browser-research-timeline-for-analyst.md` — memory browser, flag-for-review, `memory_review_queue`.

## Challenge Log (grill-me)

### Q1 — Already implemented?
- **Partially implemented:** `MemoryErasureService` (single + bulk delete), `WorkspaceDncRecord`/`GlobalDncRecord` models, DNC routes (`app/routes/dnc_routes.py`), retention columns on `Workspace`, and `apply_memory_retention_policies`/`apply_document_retention_policies` Celery tasks already exist.
- **Missing:** unified governance console UI, `memory_source_legal_tiers` table, governance-scoped `audit_events` actions (`governance.*`), right-to-delete request queue UI, and source-risk-tier → scrape-pause integration.
- **Verdict:** Extend and compose existing services; do not re-implement `MemoryErasureService` or `DncComplianceService`.

### Q2 — Simpler alternative?
- **DNC writes** can reuse `app/routes/dnc_routes.py` helper `create_dnc_record_service` rather than duplicating HMAC + upsert logic.
- **Bulk delete** can reuse `BulkOpJob` + `bulk_op_tasks.py` from Story 29.4 instead of creating a new job table.
- **Retention editing** can extend `update_workspace` in `workspaces_routes.py` rather than creating a new endpoint, but a dedicated `governance_routes.py` keeps the console cohesive.
- **Verdict:** Reuse services; create a thin governance route layer.

### Q3 — Edge cases spec misses (Pattern 3)
- [x] Boundary: `memory_retention_days` = 1 and = 36500 must be accepted; `0` or `36501` rejected.
- [x] Null/empty: `WorkspaceDncRecord.value` NULL (masked only) → UI shows `value_hmac` truncated; `GlobalDncRecord` conflict when workspace value is NULL → skip conflict check.
- [x] Concurrent: two Owners editing retention simultaneously → `SELECT ... FOR UPDATE` on `workspaces` row serializes; second write sees the updated value and re-validates.
- [x] Dry-run idempotency: multiple dry-run calls must not create `bulk_op_job` rows.
- [x] Cancel during bulk delete: `bulk_op_job.status = 'cancelled'` must stop the chunked loop between batches.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [x] `DncComplianceService.invalidate_workspace_cache` throws → the DNC row is already committed; return `201` but log the invalidation failure and retry in background (cache TTL will eventually expire).
- [x] `MemoryErasureService.bulk_delete_memories` fails mid-batch → `bulk_op_errors` records the failed batch and job status becomes `partial`.
- [x] `memory_source_legal_tiers` table does not exist → source risk tier tab shows empty state and retention validation falls back to workspace-only check (no crash).
- [x] `GLOBAL_DNC_ENABLED` missing/undefined → default to `False` (workspace-only DNC).
- [x] `AuditEvent` insert fails inside governance route → wrap in same transaction; if audit fails, the governance mutation rolls back.

### Triage
- **Critical:** None. Existing services cover the heavy lifting; story is composition + UI.
- **Non-critical gaps to fold into ATDD:** boundary validation, concurrent retention edits, dry-run idempotency, cache-invalidation failure handling, missing `memory_source_legal_tiers` fallback.
- **Action:** Proceed to `bmad-nowing-test-first-atdd`.

## Dev Agent Record

### Agent Model Used

Opus 5 (1M context) — 2026-09-08

### Debug Log References

- Backend governance service + routes + migration: `a2e8e71315bc_add_memory_source_legal_tiers_and_.py`, `app/models/memory_source_legal_tier.py`, `app/schemas/governance.py`, `app/services/governance_service.py`, `app/routes/governance_routes.py`, `tests/integration/routes/test_governance_routes.py`, `tests/integration/services/test_governance_service.py`.
- Backend integration tests: 8/8 service tests + 11/11 route tests pass against `postgresql+asyncpg://postgres:postgres@localhost:5432/nowing_test`.
- Frontend: `app/dashboard/[workspace_id]/governance/page.tsx`, `components/governance/*`, `contracts/types/governance.types.ts`, `lib/apis/governance-api.service.ts`, `messages/en.json` + `messages/vi.json`.
- Navigation: added `nav_governance` link in `app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` (and corresponding i18n keys).

### Completion Notes List

- Governance console page is available at `/dashboard/[workspace_id]/governance` with five tabs (Data Retention, Source Risk Tiers, DNC, Audit Log, Workspace Status).
- Retention editing validates positive days ≤ 36500 and checks stricter source risk tier windows before saving.
- Source risk tier upsert to `high` pauses scraping (`api_access_enabled=False` + `scrape_paused_at`) and writes `governance.source_risk_tier_change` audit.
- Right-to-delete uses `BulkOpJob` + Celery chunked deletes for bulk requests; `single_memory` deletes synchronously via `MemoryErasureService`.
- DNC add/remove reuses `create_dnc_record_service` + `DncComplianceService.invalidate_workspace_cache`; global DNC conflicts flagged with `superseded_by_global`.
- Audit log scoped to workspace via `diff_payload['workspace_id']` filter; all governance mutations write `governance.*` audit events.
- Frontend translations added for `en` and `vi` under `governance` and `workspaceSettings.nav_governance`.

### File List

**Backend**
- `nowing_backend/alembic/versions/a2e8e71315bc_add_memory_source_legal_tiers_and_.py` (NEW)
- `nowing_backend/app/models/memory_source_legal_tier.py` (NEW)
- `nowing_backend/app/models/__init__.py` (UPDATE — export `MemorySourceLegalTier`)
- `nowing_backend/app/db/__init__.py` (UPDATE — export `MemorySourceLegalTier`)
- `nowing_backend/app/schemas/governance.py` (NEW)
- `nowing_backend/app/services/governance_service.py` (NEW)
- `nowing_backend/app/routes/governance_routes.py` (NEW)
- `nowing_backend/app/routes/__init__.py` (UPDATE — register governance router)
- `nowing_backend/app/services/bulk_ops_service.py` (UPDATE — allow `source_id`/`source_entity_type` filters for `DELETE_SOURCE_TYPE_MEMORIES`)
- `nowing_backend/tests/integration/routes/test_governance_routes.py` (NEW)
- `nowing_backend/tests/integration/services/test_governance_service.py` (NEW)

**Frontend**
- `nowing_web/app/dashboard/[workspace_id]/governance/page.tsx` (NEW)
- `nowing_web/components/governance/governance-console.tsx` (NEW)
- `nowing_web/components/governance/retention-policy-panel.tsx` (NEW)
- `nowing_web/components/governance/source-risk-tier-panel.tsx` (NEW)
- `nowing_web/components/governance/dnc-panel.tsx` (NEW)
- `nowing_web/components/governance/audit-log-panel.tsx` (NEW)
- `nowing_web/components/governance/workspace-status-panel.tsx` (NEW)
- `nowing_web/components/governance/right-to-delete-panel.tsx` (NEW)
- `nowing_web/contracts/types/governance.types.ts` (NEW)
- `nowing_web/lib/apis/governance-api.service.ts` (NEW)
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` (UPDATE — add Governance nav item)
- `nowing_web/messages/en.json` (UPDATE — add `governance` + `workspaceSettings.nav_governance` keys)
- `nowing_web/messages/vi.json` (UPDATE — add `governance` + `workspaceSettings.nav_governance` keys)

### Change Log

- **2026-09-08:** Implemented Story 29.6 backend governance console (retention policy, source risk tiers, DNC, right-to-delete, audit log, workspace archive/restore) + frontend page, components, API service, and i18n.
