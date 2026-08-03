---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 8-12-workspace-limits
status: done
---

# Story 8.12: Workspace Limits

**Status:** done  
**Epic:** 8 — Platform Operations  
**Priority:** MEDIUM  
**Requirements:** FR-3, FR-30  
**Architecture:** AD-9  
**Dependencies:** Existing `Workspace`, `Document`, `WorkspaceMembership`, `WorkspaceInvite`, `Run`, and `TokenUsage` tables; `app/config/__init__.py` deployment-mode logic; usage-service infra.

> **Note on line numbers:** Code references in this story are against `baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2`. Exact line numbers will shift after the migration and model changes; use the named function/class as the primary anchor.

## Story

As a platform admin,  
I want to enforce per-workspace limits (documents, members, runs, storage visibility),  
So that I can offer tiered plans and prevent abuse on the cloud offering.

## Context

### Upstream reference

SurfSense PR #1609 (`MODSetter/SurfSense#1609`) and its merged commit `38b784fbacb1f7f0a05e2cd2259a0d7963b8c6ff` implement a **per-user workspace creation limit**, not per-workspace resource limits:

- Adds `MAX_WORKSPACES_PER_USER = int(os.getenv("MAX_WORKSPACES_PER_USER", "100"))` in `surfsense_backend/app/config/__init__.py`.
- Gates `POST /workspaces` creation in `surfsense_backend/app/routes/workspaces_routes.py` (returns `409` with a clear limit message).
- Adds `GET /workspaces/limits` returning `{ "max_workspaces_per_user": ... }`.
- Surfaces the limit in `surfsense_web` through `workspaceLimitsAtom`, `workspacesApiService.getWorkspaceLimits`, `cacheKeys.workspaces.limits`, and disables the "add workspace" affordances in `LayoutDataProvider`, `CreateWorkspaceDialog`, `IconRail`, and sidebars.

> **Verification:** No SurfSense PR currently implements per-workspace document/member/run/storage plan limits. PR #1609 is therefore used as the **pattern reference** for the config/env limit model, the `/limits` route, the Jotai/TanStack Query atom, and the UI affordance. The per-workspace resource-limit feature must be designed and built from first principles in Nowing.

### Nowing current state

- `nowing_backend/app/db.py`:
  - `Workspace` (search `class Workspace`) has no `plan_tier` or limit fields. It owns `documents`, `memberships`, `invites`, `runs`, and `logs` relationships.
  - `Document` (`class Document`) is soft-archived via `archived_at`; non-archived rows are the billable/visible count.
  - `WorkspaceMembership` and `WorkspaceInvite` track membership.
  - `Run` tracks every scraper/capability invocation per workspace with `status` values `running`, `success`, `error`, `cancelled`.
  - `TokenUsage` tracks cost/tokens, not resource counts.
- `nowing_backend/app/config/__init__.py` (`DEPLOYMENT_MODE` block) defines `DEPLOYMENT_MODE` (`self-hosted` vs `cloud`) and `is_cloud()` / `is_self_hosted()`.
- `nowing_backend/app/routes/documents_routes.py`:
  - `create_documents` and `create_documents_file_upload` check `Permission.DOCUMENTS_CREATE` but enforce only a 500 MB per-file size cap. No per-workspace document count limit.
- `nowing_backend/app/routes/rbac_routes.py`:
  - `create_invite` and `accept_invite` check `Permission.MEMBERS_INVITE` / workspace access but have no member-count gate.
- `nowing_backend/app/capabilities/core/access/rest.py`:
  - `_register_verb.endpoint` builds each scraper endpoint; `gate_capability` gates on wallet/credits only. No per-workspace run-count gate.
- `nowing_backend/app/services/usage_service.py` aggregates `TokenUsage` for the dashboard; it does not count documents/members/runs.
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` defines the workspace settings tabs (`general`, `models`, `team-roles`, `prompts`, `public-links`, `data-retention`); no limits tab.
- `nowing_web/lib/apis/workspaces-api.service.ts` and `nowing_web/contracts/types/workspace.types.ts` have no limit/usage contract.
- `nowing_web/lib/query-client/cache-keys.ts` has `workspaces` cache keys; no `limits` key.
- `nowing_web/components/usage/usage-content.tsx` shows the credit/token usage dashboard pattern and `SummaryCard` component that can be reused for limit bars.

## Acceptance Criteria

1. **Plan-based limit model**
   - **Given** a workspace, **When** limits are resolved, **Then** the effective limit is the per-workspace override if set, else the plan default (`free`/`team`/`enterprise`), else unlimited (`null`) for self-hosted.
   - **And** `max_documents`, `max_members`, `max_runs`, and `max_storage_bytes` are each independently nullable; a `null` limit means no limit.

2. **Backend gating — documents**
   - **Given** a workspace at its document limit, **When** `POST /documents` or `POST /documents/fileupload` is called, **Then** the request is rejected with `403` and `error_code = "limit_exceeded"` before any file is persisted or queued.

3. **Backend gating — members**
   - **Given** a workspace at its member limit, **When** an owner creates an invite (`POST /workspaces/{workspace_id}/invites`) or a user accepts an invite (`POST /invites/accept`), **Then** the operation is rejected with `403` and `error_code = "limit_exceeded"`.

4. **Backend gating — runs**
   - **Given** a workspace at its run limit for the current period, **When** any scraper/capability verb is invoked (`POST /workspaces/{workspace_id}/scrapers/{platform}/{verb}`), **Then** the request is rejected with `403` and `error_code = "limit_exceeded"` before the executor runs.

5. **Usage vs limit API**
   - **Given** a workspace Owner (`Permission.SETTINGS_UPDATE` is required), **When** they open workspace settings, **Then** `GET /workspaces/{id}/limits` returns the effective plan/tier, the configured limits, and the current usage counts (documents, members, runs, storage) in a single payload.
   - **Note:** `Permission.SETTINGS_VIEW` is also held by Viewer/Editor, so the limits API must require `SETTINGS_UPDATE` to keep usage/limit data Owner-only.

6. **Settings UI**
   - **Given** the workspace settings page, **When** an admin navigates to the new "Limits" tab, **Then** they see usage vs limit bars, the current plan, and an upgrade CTA when a limit is at or above 80%.
   - **And** the CTA opens the upgrade flow defined by `NEXT_PUBLIC_UPGRADE_URL` (Stripe checkout or contact link).

7. **Self-host defaults**
   - **Given** `NOWING_DEPLOYMENT_MODE=self-hosted`, **When** limits are resolved for any workspace, **Then** all limits are `null` and no existing upload, invite, or run is blocked.

8. **Idempotent & safe**
   - **Given** concurrent uploads/invites/runs, **When** the limit boundary is reached, **Then** only one request wins; the others get `limit_exceeded` without over-counting partial work. This is enforced by acquiring a per-workspace advisory lock during the limit check and inserting within the same transaction.

9. **Storage visibility (deferred enforcement)**
   - **Given** a workspace with a `max_storage_bytes` limit, **When** the limits API is called, **Then** `max_storage_bytes` and current storage usage (sum of `DocumentFile` sizes or document count as proxy) are returned.
   - **And** `max_storage_bytes` is **not enforced** in this story; a follow-up story will add storage gating.

## Error contract

All limit failures return `HTTP 403` with the following JSON body:

```json
{
  "error_code": "limit_exceeded",
  "limit_type": "documents|members|runs|storage",
  "used": 42,
  "limit": 50
}
```

For `storage`, `limit` and `used` are bytes. For `runs`, the count includes runs with `status IN ('running', 'success', 'error')` within the current `run_period_hours`.

## Tasks / Subtasks

### Backend

- [ ] Add plan/limit data model (AC #1)
  - [ ] Migration `189_add_workspace_plan_and_limits.py`:
    - Add `workspaces.plan_tier` (`String(20)`, default `"free"`, index).
    - Add `workspace_limits` table:
      - `id` (PK, int)
      - `plan_tier` (`String(20)`, nullable) — set for plan-default rows, `NULL` for workspace-override rows
      - `workspace_id` (`Integer`, nullable, FK `workspaces.id` on delete CASCADE) — set for override rows, `NULL` for plan-default rows
      - `max_documents` (`Integer`, nullable)
      - `max_members` (`Integer`, nullable)
      - `max_runs` (`Integer`, nullable)
      - `max_storage_bytes` (`BigInteger`, nullable)
      - `run_period_hours` (`Integer`, default 720)
      - `created_at`, `updated_at`
    - Add **partial unique indexes** (not nullable-column `UNIQUE`) so Postgres actually enforces one default per plan and one override per workspace:
      ```sql
      CREATE UNIQUE INDEX uq_workspace_limits_plan_default
        ON workspace_limits(plan_tier) WHERE workspace_id IS NULL;
      CREATE UNIQUE INDEX uq_workspace_limits_workspace_override
        ON workspace_limits(workspace_id) WHERE plan_tier IS NULL;
      ```
    - Seed plan defaults (`free`/`team`/`enterprise`) by inserting rows with `plan_tier` set and `workspace_id` NULL. Values may be overridden by `WORKSPACE_PLAN_LIMITS` env JSON, but the table is the source of truth.
  - [ ] Update `nowing_backend/app/db.py`:
    - Add `plan_tier` to `Workspace` and a `workspace_limits` relationship.
    - Add `WorkspaceLimit` model after `Workspace`.
  - [ ] Update `nowing_backend/app/config/__init__.py`:
    - Add `WORKSPACE_PLAN_LIMITS` as an optional JSON/env map used only to **override** seeded plan defaults on startup.
    - For self-host, the service treats all limits as `None` regardless of plan.

- [ ] Create `nowing_backend/app/services/workspace_limits.py` (AC #1, #2, #3, #4, #8)
  - [ ] `ResolvedWorkspaceLimits` dataclass with `plan_tier`, `max_documents`, `max_members`, `max_runs`, `max_storage_bytes`, `run_period_hours`.
  - [ ] `WorkspaceLimitService` class:
    - `get_effective_limits(session, workspace_id) -> ResolvedWorkspaceLimits`: returns per-workspace override or plan default, resolving `run_period_hours` in the order override → plan default → `720`. On self-host returns all `None`.
    - `count_documents(session, workspace_id)`, `count_members(session, workspace_id)`, `count_runs(session, workspace_id)`.
    - `sum_storage_bytes(session, workspace_id)`: sum `DocumentFile.size_bytes` for non-archived documents in the workspace. Documents without files count as `0`; this is a visibility metric only in 8.12.
    - `check_document_limit(session, workspace_id, additional)`, `check_member_limit(session, workspace_id, additional)`, `check_run_limit(session, workspace_id)`.
  - [ ] Each public method that enforces a limit acquires `pg_advisory_xact_lock(hashtext('workspace_limits:' || workspace_id))` at the start of the request transaction to prevent races at the boundary.
  - [ ] Each check raises `HTTPException(status_code=403, detail={"error_code":"limit_exceeded","limit_type":"...","used":...,"limit":...})`.

- [ ] Gate document upload (AC #2, #8)
  - [ ] In `nowing_backend/app/routes/documents_routes.py`:
    - `create_documents`: after `check_permission`, call `check_document_limit(session, request.workspace_id, len(request.content))` under the advisory lock. **This is a best-effort gate because `Document` rows for `DocumentType.EXTENSION` are created asynchronously by Celery.** The Celery worker does not re-check the limit; if strict enforcement is needed later, add a limit check inside `process_extension_document_task`.
    - `create_documents_file_upload`: after duplicate detection and **before** creating pending `Document` rows, compute `new_files = len(files) - len(duplicate_document_ids)` and call `check_document_limit(session, workspace_id, new_files)` under the advisory lock. Count only non-archived documents where `archived_at IS NULL`.

- [ ] Gate member invite (AC #3, #8)
  - [ ] In `nowing_backend/app/routes/rbac_routes.py`:
    - `create_invite` (`POST /workspaces/{workspace_id}/invites`): after permission check, call `check_member_limit(session, workspace_id, 1)` under the advisory lock. Count active memberships plus active/unexpired invites with remaining uses (`max_uses IS NULL OR max_uses - uses_count > 0`).
    - `accept_invite` (`POST /invites/accept`): after loading the invite and **before** creating the `WorkspaceMembership`, call `check_member_limit(session, invite.workspace_id, 1)` under the advisory lock.

- [ ] Gate run creation (AC #4, #8)
  - [ ] In `nowing_backend/app/capabilities/core/access/rest.py`:
    - Inside `_register_verb.endpoint` before `await gate_capability(payload, unit, ctx)`, call `check_run_limit(session, workspace_id)` under the advisory lock.
    - Count `Run` rows with `workspace_id == workspace_id`, `created_at >= now - run_period_hours`, and `status IN ('running', 'success', 'error')`.
    - **Lock trade-off:** the advisory lock is held until the request transaction commits (which happens inside `create_pending_run`/`record_run`). This serializes run gating per workspace, including the `gate_capability` wallet check. For v1 this is acceptable; if `gate_capability` becomes slow, consider pre-inserting a `pending` run row and committing the limit gate in a smaller transaction.
    - Add an integration test for the async path to ensure `start_async_run` is not called when the limit is hit.

- [ ] Expose usage/limit API (AC #5)
  - [ ] Add Pydantic schemas in `nowing_backend/app/schemas/workspace.py`:
    - `WorkspaceLimitItem`, `WorkspaceLimitsResponse`.
  - [ ] Export from `nowing_backend/app/schemas/__init__.py`.
  - [ ] Add `GET /workspaces/{workspace_id}/limits` in `nowing_backend/app/routes/workspaces_routes.py`. Requires `Permission.SETTINGS_UPDATE` so only Owners can view workspace limits/usage.

- [ ] Self-host defaults (AC #7)
  - [ ] Ensure `WorkspaceLimitService.get_effective_limits` short-circuits to `None` for all limits when `config.is_self_hosted()`.
  - [ ] Add `.env.example` documentation for `NOWING_DEPLOYMENT_MODE` and optional `WORKSPACE_PLAN_LIMITS`.

- [ ] Plan-change procedure (AC #1)
  - [ ] When a workspace's `plan_tier` is updated, the effective limits automatically resolve to the new plan default unless a `workspace_limits` override row for that workspace exists. Do not auto-delete overrides.

- [ ] Tests (AC #8)
  - [ ] `nowing_backend/tests/unit/services/test_workspace_limits.py` — effective limits, counting, concurrency at boundary.
  - [ ] `nowing_backend/tests/integration/routes/test_documents_limits.py` — document upload blocked at limit, self-host unlimited, duplicate upload not double-counted.
  - [ ] `nowing_backend/tests/integration/routes/test_member_invite_limits.py` — invite and accept blocked at member limit.
  - [ ] `nowing_backend/tests/integration/capabilities/test_runs_limits.py` — run verb blocked at run limit, including async mode.
  - [ ] `nowing_backend/tests/integration/routes/test_workspace_limits.py` — `GET /workspaces/{id}/limits` returns correct usage and limits.

### Frontend

- [ ] Add limit contract (AC #5)
  - [ ] `nowing_web/contracts/types/workspace.types.ts`:
    - Add `workspaceLimitItem` and `workspaceLimitsResponse` zod schemas; extend `workspace` with `plan_tier` if needed.
  - [ ] `nowing_web/lib/apis/workspaces-api.service.ts`: add `getWorkspaceLimits(workspaceId: number)`.
  - [ ] `nowing_web/lib/query-client/cache-keys.ts`: add `workspaces.limits: (workspaceId) => ["workspaces", "limits", workspaceId]`.

- [ ] Build workspace settings UI (AC #6)
  - [ ] `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx`: add `"limits"` to `WorkspaceSettingsTab` and the nav items list with an icon (e.g. `Gauge`).
  - [ ] `nowing_web/app/dashboard/[workspace_id]/workspace-settings/limits/page.tsx` (new): render `WorkspaceLimitsManager`.
  - [ ] `nowing_web/components/settings/workspace-limits-manager.tsx` (new):
    - Fetch `workspaceLimits` via `useQuery`.
    - Display plan badge and four usage bars (documents, members, runs, storage).
    - Use the existing `SummaryCard` pattern from `components/usage/usage-content.tsx` or a new `LimitBar` component.
    - Show an upgrade CTA when any limit is ≥ 80% used. The CTA opens `NEXT_PUBLIC_UPGRADE_URL`.
    - Disable/enable the "Invite member" and "Upload" affordances in settings based on limits (the backend is the source of truth; the UI is defense-in-depth).

- [ ] i18n
  - [ ] `nowing_web/messages/en.json` `workspaceSettings` block: add `nav_limits`, `nav_limits_desc`, `limits_title`, `limits_plan_label`, `limits_documents`, `limits_members`, `limits_runs`, `limits_storage`, `limits_upgrade_cta`.
  - [ ] Mirror to `ko`, `zh`, `pt`, `es`, `hi` message files or leave as English fallback and file a follow-up.

### Verification

- [ ] Backend unit + integration tests pass (commands in Dev Notes).
- [ ] Frontend typecheck + lint pass.
- [ ] Manual QA:
  - Create a workspace, set `max_documents=2` (cloud mode), upload 3 files (one duplicate); verify the third new file fails with `limit_exceeded`.
  - Set `max_members=2`, invite a third user; verify invite creation fails.
  - Set `max_runs=1`, run a scraper twice in the period; verify the second fails.
  - Switch `NOWING_DEPLOYMENT_MODE=self-hosted`; verify all gates open.

## Dev Notes

- **Port the pattern, not the scope.** PR #1609 is the canonical upstream reference for *how* to add a config-driven `/limits` route and limit-aware UI affordances. It does **not** implement document/member/run limits, so the resource-limit model, gating, and usage API are new Nowing work.
- **Use `config.is_self_hosted()` as the single kill switch.** Do not hard-code plan names in gating logic. When self-hosted, `get_effective_limits` must return `None` for all limit fields so existing behavior is unchanged.
- **Count conservatively.** For documents, count non-archived rows before the new insert. For members, count active memberships plus active/unexpired invites with remaining uses to prevent invite-spam bypass. For runs, count `running`, `success`, and `error` runs within `run_period_hours`.
- **Return structured errors.** All limit failures produce the same envelope shape: `{"error_code": "limit_exceeded", "limit_type": "documents|members|runs|storage", "used": <int>, "limit": <int|null>}` with status `403`.
- **Do not rely on the UI for enforcement.** The backend gates are the source of truth; the settings UI is for visibility and upgrade prompting only.
- **Keep the DB migration reversible.** Use Alembic `op.add_column`/`op.create_table` with explicit `downgrade` removal. Use partial unique indexes (see Tasks) and run `apply_publication(op.get_bind())` if the new tables need Zero replication.
- **Storage is a soft limit for this story.** `max_storage_bytes` is exposed in the API and UI as the sum of `DocumentFile.size_bytes` for non-archived documents (documents without files count as `0`). Enforcement is deferred to a follow-up story.
- **Concurrency.** Use `pg_advisory_xact_lock(hashtext('workspace_limits:' || workspace_id))` around the count + check so concurrent requests at the boundary do not over-allocate. The lock is transaction-scoped and released on commit/rollback. Combine with an immediate `INSERT`/`UPDATE` of the resource being gated inside the same transaction. For the run gate, the lock is held through `gate_capability` until `create_pending_run`/`record_run` commits; this is acceptable for v1 but may become a serialization point under high concurrency.
- **Plan defaults live in the DB.** The migration seeds `workspace_limits` rows for `free`/`team`/`enterprise`. `WORKSPACE_PLAN_LIMITS` env is only an optional override at startup. This keeps multi-environment config predictable and version-controlled.

## Verification

- [ ] Backend tests:
  ```bash
  cd nowing_backend
  pytest tests/unit/services/test_workspace_limits.py -q
  pytest tests/integration/routes/test_documents_limits.py -q
  pytest tests/integration/routes/test_member_invite_limits.py -q
  pytest tests/integration/capabilities/test_runs_limits.py -q
  pytest tests/integration/routes/test_workspace_limits.py -q
  ```
- [ ] Backend lint:
  ```bash
  cd nowing_backend
  ruff check app/db.py app/schemas/workspace.py app/routes/workspaces_routes.py app/routes/documents_routes.py app/routes/rbac_routes.py app/capabilities/core/access/rest.py app/services/workspace_limits.py
  ruff format app/services/workspace_limits.py app/routes/workspaces_routes.py
  ```
- [ ] Frontend typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics 500 \
    components/settings/workspace-limits-manager.tsx \
    app/dashboard/\[workspace_id\]/workspace-settings/layout-shell.tsx \
    app/dashboard/\[workspace_id\]/workspace-settings/limits/page.tsx \
    contracts/types/workspace.types.ts \
    lib/apis/workspaces-api.service.ts \
    lib/query-client/cache-keys.ts
  ```

## References

- Upstream pattern PR: `MODSetter/SurfSense#1609` (per-user workspace creation limit, not per-workspace resource limits)
- Upstream commit: `38b784fbacb1f7f0a05e2cd2259a0d7963b8c6ff`
- `nowing_backend/app/db.py` (`Workspace`, `Document`, `WorkspaceMembership`, `WorkspaceInvite`, `Run`, `TokenUsage`)
- `nowing_backend/app/config/__init__.py` (`is_self_hosted`/`is_cloud`)
- `nowing_backend/app/routes/documents_routes.py` (`create_documents`, `create_documents_file_upload`)
- `nowing_backend/app/routes/rbac_routes.py` (`create_invite`, `accept_invite`)
- `nowing_backend/app/capabilities/core/access/rest.py` (`_register_verb`, `gate_capability`)
- `nowing_backend/app/services/usage_service.py`
- `nowing_backend/app/schemas/workspace.py` and `nowing_backend/app/schemas/__init__.py`
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx`
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/general/page.tsx`
- `nowing_web/components/usage/usage-content.tsx` (SummaryCard pattern)
- `nowing_web/lib/apis/workspaces-api.service.ts`
- `nowing_web/contracts/types/workspace.types.ts`
- `nowing_web/lib/query-client/cache-keys.ts`
- `nowing_web/messages/en.json` (`workspaceSettings`)

### Review Findings

#### `decision_needed` (resolved)

- [x] [Review][Decision] Unknown/invalid `plan_tier` handling and case sensitivity — `workspace_limits.py:118`, `workspace_limits.py:137-144`. **Resolved:** normalize `plan_tier` to lowercase; unknown tier falls back to `free` to avoid accidental unlimited in cloud. Do not add a fixed `CHECK` enum (allow new plans via migration/env). Converted to patch below.
- [x] [Review][Decision] Disable invite/upload affordances in settings — `workspace-limits-manager.tsx`. **Resolved:** defer. The backend is the source of truth; the settings page is visibility/upgrade only. Global UI affordance gating is out of scope for 8.12 and recorded in `deferred-work.md`.

#### `patch`

- [x] [Review][Patch] Document file upload overcounts due to autoflush — `documents_routes.py:264-282`. New `Document` objects are added to the session before `check_document_limit`; with `AsyncSession(autoflush=True)`, the count query flushes them and `used` includes the new rows while `additional` also counts them. Move `session.add` to after the limit check.
- [x] [Review][Patch] Unknown/mixed-case `plan_tier` falls back to unlimited — `workspace_limits.py:117-122`, `workspace_limits.py:137-144`. Normalize `plan_tier` to lowercase and fall back to `free` defaults when no DB row or env override exists.
- [x] [Review][Patch] `accept_invite` overcounts at member boundary — `rbac_routes.py:1075-1099`. The active invite being accepted is still counted by `count_members` while `additional=1` is added. If a single-use invite is at the workspace limit, a valid accept is rejected. Move `invite.uses_count += 1` before `check_member_limit` so the consumed invite is excluded from the count.
- [x] [Review][Patch] Negative limit values not validated — `workspace_limits.py:137-143`, `workspace_limits.py:230-269`. Negative `max_*` or `run_period_hours` cause nonsensical gating. Add validation and/or CHECK constraints to reject negative values.
- [x] [Review][Patch] `WORKSPACE_PLAN_LIMITS` env JSON not validated — `config/__init__.py:55-63`, `workspace_limits.py:131-132`. Malformed values can cause runtime 500s. Add schema/structural validation on startup or at lookup.
- [x] [Review][Patch] Advisory lock uses `hashtext` — `workspace_limits.py:64-67`. Use `pg_advisory_xact_lock(workspace_id)` directly to avoid hash collision and cross-workspace lock contention.
- [x] [Review][Patch] Partial unique index allows both-NULL `workspace_limits` row — `189_add_workspace_plan_and_limits.py:71-84`. Add `CHECK ((plan_tier IS NOT NULL) OR (workspace_id IS NOT NULL))` to reject semantically invalid rows.
- [x] [Review][Patch] `run_period_hours` not validated for <= 0 — `workspace_limits.py:143`, `workspace_limits.py:187-196`. Zero/negative period breaks `count_runs`. Validate and fall back to 720.
- [x] [Review][Patch] Missing concurrent boundary test — `tests/integration/services/test_workspace_limits.py`. AC #8 claims concurrency safety but no `asyncio.gather` boundary test exists.
- [x] [Review][Patch] Frontend `formatBytes` negative guard — `workspace-limits-manager.tsx:42-49`. Defensive guard against negative `storage_bytes` to avoid `NaN` display.

#### `defer`

- [x] [Review][Defer] Storage sum does not reconcile deleted backend files — `workspace_limits.py:199-209`. `DocumentFile.size_bytes` is a DB metric; if storage backend files are deleted independently the sum will be off. Storage is a soft/exploratory limit in 8.12; enforcement is deferred to a follow-up story.
