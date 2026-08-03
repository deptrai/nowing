---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 8-12-workspace-limits
status: ready-for-dev
---

# Story 8.12: Workspace Limits

**Status:** ready-for-dev  
**Epic:** 8 — Platform Operations  
**Priority:** MEDIUM  
**Requirements:** FR-3, FR-30  
**Architecture:** AD-9  
**Dependencies:** Existing `Workspace`, `Document`, `WorkspaceMembership`, `WorkspaceInvite`, `Run`, and `TokenUsage` tables; `app/config/__init__.py` deployment-mode logic; usage-service infra.

## Story

As a platform admin,
I want to enforce per-workspace limits (documents, members, storage, runs),
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
  - `Workspace` (line 1776) has no `plan_tier` or limit fields. It owns `documents`, `memberships`, `invites`, `runs`, and `logs` relationships.
  - `Document` (line 1418) is soft-archived via `archived_at`; non-archived rows are the billable/visible count.
  - `WorkspaceMembership` (line 2442) and `WorkspaceInvite` (line 2493) track membership.
  - `Run` (line 3172) tracks every scraper/capability invocation per workspace.
  - `TokenUsage` (line 1125) tracks cost/tokens, not resource counts.
- `nowing_backend/app/config/__init__.py` (lines 590–606) defines `DEPLOYMENT_MODE` (`self-hosted` vs `cloud`) and `is_cloud()` / `is_self_hosted()`.
- `nowing_backend/app/routes/documents_routes.py`:
  - `create_documents` (line 59) and `create_documents_file_upload` (line 118) check `Permission.DOCUMENTS_CREATE` but enforce only a 500 MB per-file size cap (`MAX_FILE_SIZE_BYTES`, line 56). No per-workspace document count limit.
- `nowing_backend/app/routes/rbac_routes.py`:
  - `create_invite` (line 730) and `accept_invite` (line 1018) check `Permission.MEMBERS_INVITE` / workspace access but have no member-count gate.
- `nowing_backend/app/capabilities/core/access/rest.py`:
  - `_register_verb` (line 177) builds each scraper endpoint; `gate_capability` (called at line 204) gates on wallet/credits only. No per-workspace run-count gate.
- `nowing_backend/app/services/usage_service.py` (line 36) aggregates `TokenUsage` for the dashboard; it does not count documents/members/runs.
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` (line 10) defines the workspace settings tabs (`general`, `models`, `team-roles`, `prompts`, `public-links`, `data-retention`); no limits tab.
- `nowing_web/lib/apis/workspaces-api.service.ts` (line 31) and `nowing_web/contracts/types/workspace.types.ts` (line 5) have no limit/usage contract.
- `nowing_web/lib/query-client/cache-keys.ts` (line 53) has `workspaces` cache keys; no `limits` key.
- `nowing_web/components/usage/usage-content.tsx` (line 31) shows the credit/token usage dashboard pattern and `SummaryCard` component that can be reused for limit bars.

## Acceptance Criteria

1. **Plan-based limit model**
   - **Given** a workspace, **When** limits are resolved, **Then** the effective limit is the per-workspace override if set, else the plan default (`free`/`team`/`enterprise`), else unlimited (`null`) for self-hosted.
   - **And** `max_documents`, `max_members`, `max_runs`, and `max_storage_bytes` are each independently nullable; a `null` limit means no limit.

2. **Backend gating — documents**
   - **Given** a workspace at its document limit, **When** `POST /documents` or `POST /documents/fileupload` is called, **Then** the request is rejected with `402`/`403` and `error.code = "limit_exceeded"` before any file is persisted or queued.

3. **Backend gating — members**
   - **Given** a workspace at its member limit, **When** an owner creates an invite (`POST /workspaces/{id}/invites`) or a user accepts an invite (`POST /invites/accept`), **Then** the operation is rejected with `402`/`403` and `error.code = "limit_exceeded"`.

4. **Backend gating — runs**
   - **Given** a workspace at its run limit for the current period, **When** any scraper/capability verb is invoked (`POST /workspaces/{id}/scrapers/{platform}/{verb}`), **Then** the request is rejected with `402`/`403` and `error.code = "limit_exceeded"` before the executor runs.

5. **Usage vs limit API**
   - **Given** a workspace admin, **When** they open workspace settings, **Then** `GET /workspaces/{id}/limits` returns the effective plan/tier, the configured limits, and the current usage counts (documents, members, runs, storage) in a single payload.

6. **Settings UI**
   - **Given** the workspace settings page, **When** an admin navigates to the new "Limits" tab, **Then** they see usage vs limit bars, the current plan, and an upgrade CTA when a limit is at or above 80%.

7. **Self-host defaults**
   - **Given** `NOWING_DEPLOYMENT_MODE=self-hosted`, **When** limits are resolved for any workspace, **Then** all limits are `null` and no existing upload, invite, or run is blocked.

8. **Idempotent & safe**
   - **Given** concurrent uploads/invites/runs, **When** the limit boundary is reached, **Then** only one request wins; the others get `limit_exceeded` without over-counting partial work.

## Tasks / Subtasks

### Backend

- [ ] Add plan/limit data model (AC #1)
  - [ ] Migration `184_add_workspace_plan_and_limits.py`:
    - Add `workspaces.plan_tier` (String(20), default `"free"`, index).
    - Add `workspace_limits` table:
      - `id`, `plan_tier` (nullable, unique for plan defaults), `workspace_id` (nullable, unique for overrides, FK `workspaces.id` on delete CASCADE),
      - `max_documents` (Integer, nullable), `max_members` (Integer, nullable), `max_runs` (Integer, nullable),
      - `max_storage_bytes` (BigInteger, nullable), `run_period_hours` (Integer, default 720),
      - `created_at`, `updated_at`.
  - [ ] Update `nowing_backend/app/db.py`:
    - Add `plan_tier` to `Workspace` (line 1776) and `workspace_limits` relationship.
    - Add `WorkspaceLimit` model after `Workspace`.
  - [ ] Seed plan defaults:
    - In `nowing_backend/app/config/__init__.py` near deployment-mode config (line 590), add a `WORKSPACE_PLAN_LIMITS` JSON/env map for `free`/`team`/`enterprise`.
    - For self-host, the service treats all limits as `None` regardless of plan.

- [ ] Create `nowing_backend/app/services/workspace_limits.py` (AC #1, #2, #3, #4)
  - [ ] `WorkspaceLimits` dataclass with `plan_tier`, `max_documents`, `max_members`, `max_runs`, `max_storage_bytes`, `run_period_hours`.
  - [ ] `get_effective_limits(session, workspace_id) -> WorkspaceLimits`: returns per-workspace override or plan default; on self-host returns all `None`.
  - [ ] `count_documents(session, workspace_id)`, `count_members(session, workspace_id)`, `count_runs(session, workspace_id)`, `sum_storage_bytes(session, workspace_id)`.
  - [ ] `check_document_limit(session, workspace_id, additional)`, `check_member_limit(session, workspace_id, additional)`, `check_run_limit(session, workspace_id)`. Each raises `HTTPException(status_code=403, detail={"error_code":"limit_exceeded","limit_type":"...","used":...,"limit":...})`.

- [ ] Gate document upload (AC #2)
  - [ ] In `nowing_backend/app/routes/documents_routes.py`:
    - After the `check_permission` call in `create_documents` (line 72), call `check_document_limit(session, request.workspace_id, len(request.content))`.
    - After the `check_permission` call in `create_documents_file_upload` (line 155), call `check_document_limit(session, workspace_id, len(files))`.
  - [ ] Count only non-archived `Document` rows where `archived_at IS NULL`.

- [ ] Gate member invite (AC #3)
  - [ ] In `nowing_backend/app/routes/rbac_routes.py`:
    - `create_invite` (line 746): after permission check, call `check_member_limit(session, workspace_id, 1)` counting active memberships + active/unexpired invites with remaining uses.
    - `accept_invite` (line 1019): before creating the `WorkspaceMembership` (line 1077), call `check_member_limit(session, invite.workspace_id, 1)`.

- [ ] Gate run creation (AC #4)
  - [ ] In `nowing_backend/app/capabilities/core/access/rest.py`:
    - Inside `_register_verb.endpoint` before `await gate_capability(payload, unit, ctx)` (line 205), call `check_run_limit(session, workspace_id)`.
    - Count `Run` rows with `workspace_id == workspace_id`, `created_at >= now - run_period_hours`, and `status != "cancelled"`.

- [ ] Expose usage/limit API (AC #5)
  - [ ] Add Pydantic schemas in `nowing_backend/app/schemas/workspace.py`:
    - `WorkspaceLimitItem`, `WorkspaceLimitsResponse`.
  - [ ] Export from `nowing_backend/app/schemas/__init__.py` (line 148).
  - [ ] Add `GET /workspaces/{workspace_id}/limits` in `nowing_backend/app/routes/workspaces_routes.py` (after the `/mcp-tools` block, line 567). Requires `Permission.SETTINGS_VIEW`.

- [ ] Self-host defaults (AC #7)
  - [ ] Ensure `WorkspaceLimitService.get_effective_limits` short-circuits to `None` for all limits when `config.is_self_hosted()`.
  - [ ] Add `.env.example` documentation for `NOWING_DEPLOYMENT_MODE` and optional `WORKSPACE_PLAN_LIMITS`.

- [ ] Tests (AC #8)
  - [ ] `nowing_backend/tests/unit/services/test_workspace_limits.py` — effective limits, counting, concurrency at boundary.
  - [ ] `nowing_backend/tests/integration/routes/test_documents_limits.py` — document upload blocked at limit, self-host unlimited.
  - [ ] `nowing_backend/tests/integration/routes/test_member_invite_limits.py` — invite and accept blocked at member limit.
  - [ ] `nowing_backend/tests/integration/capabilities/test_runs_limits.py` (or `tests/integration/routes/test_scraper_limits.py`) — run verb blocked at run limit.
  - [ ] `nowing_backend/tests/integration/routes/test_workspace_limits.py` — `GET /workspaces/{id}/limits` returns correct usage and limits.

### Frontend

- [ ] Add limit contract (AC #5)
  - [ ] `nowing_web/contracts/types/workspace.types.ts`:
    - Add `workspaceLimitItem` and `workspaceLimitsResponse` zod schemas; extend `workspace` with `plan_tier` if needed.
  - [ ] `nowing_web/lib/apis/workspaces-api.service.ts` (line 31): add `getWorkspaceLimits(workspaceId: number)`.
  - [ ] `nowing_web/lib/query-client/cache-keys.ts` (line 53): add `workspaces.limits: (workspaceId) => ["workspaces", "limits", workspaceId]`.

- [ ] Build workspace settings UI (AC #6)
  - [ ] `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` (line 10): add `"limits"` to `WorkspaceSettingsTab` and the nav items list with an icon (e.g. `Gauge`).
  - [ ] `nowing_web/app/dashboard/[workspace_id]/workspace-settings/limits/page.tsx` (new): render `WorkspaceLimitsManager`.
  - [ ] `nowing_web/components/settings/workspace-limits-manager.tsx` (new):
    - Fetch `workspaceLimits` via `useQuery`.
    - Display plan badge and four usage bars (documents, members, runs, storage).
    - Use the existing `SummaryCard` pattern from `components/usage/usage-content.tsx` (line 160) or a new `LimitBar` component.
    - Show an upgrade CTA when any limit is ≥ 80% used.
    - Disable/enable the "Invite member" and "Upload" affordances in settings based on limits (the backend is the source of truth; the UI is defense-in-depth).

- [ ] i18n
  - [ ] `nowing_web/messages/en.json` `workspaceSettings` block (line 768): add `nav_limits`, `nav_limits_desc`, `limits_title`, `limits_plan_label`, `limits_documents`, `limits_members`, `limits_runs`, `limits_storage`, `limits_upgrade_cta`.
  - [ ] Mirror to `ko`, `zh`, `pt`, `es`, `hi` message files or leave as English fallback and file a follow-up.

### Verification

- [ ] Backend unit + integration tests pass (commands in Dev Notes).
- [ ] Frontend typecheck + lint pass.
- [ ] Manual QA:
  - Create a workspace, set `max_documents=2` (cloud mode), upload 3 files; verify the third fails with `limit_exceeded`.
  - Set `max_members=2`, invite a third user; verify invite creation fails.
  - Set `max_runs=1`, run a scraper twice in the period; verify the second fails.
  - Switch `NOWING_DEPLOYMENT_MODE=self-hosted`; verify all gates open.

## Dev Notes

- **Port the pattern, not the scope.** PR #1609 is the canonical upstream reference for *how* to add a config-driven `/limits` route and limit-aware UI affordances. It does **not** implement document/member/run limits, so the resource-limit model, gating, and usage API are new Nowing work.
- **Use `config.is_self_hosted()` as the single kill switch.** Do not hard-code plan names in gating logic. When self-hosted, `get_effective_limits` must return `None` for all limit fields so existing behavior is unchanged.
- **Count conservatively.** For documents, count non-archived rows before the new insert. For members, count active memberships plus active/unexpired invites with remaining uses to prevent invite-spam bypass. For runs, count non-cancelled runs within `run_period_hours`.
- **Return structured errors.** All limit failures should produce the same envelope shape: `{"error_code": "limit_exceeded", "limit_type": "documents|members|runs|storage", "used": <int>, "limit": <int|null>}` with status `403` (or `402` if the billing team prefers a payment-required signal).
- **Do not rely on the UI for enforcement.** The backend gates are the source of truth; the settings UI is for visibility and upgrade prompting only.
- **Keep the DB migration reversible.** Use Alembic `op.add_column`/`op.create_table` with explicit `downgrade` removal, and run `apply_publication(op.get_bind())` only if the new columns/tables need Zero replication.
- **Storage is a soft limit for this story.** `max_storage_bytes` may be enforced in a follow-up (it requires aggregating `DocumentFile` sizes); for 8.12, it is sufficient to expose the value in the API and UI and enforce documents/members/runs.

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
- `nowing_backend/app/db.py` (`Workspace` line 1776, `Document` line 1418, `WorkspaceMembership` line 2442, `WorkspaceInvite` line 2493, `Run` line 3172, `TokenUsage` line 1125)
- `nowing_backend/app/config/__init__.py` (`is_self_hosted`/`is_cloud` lines 598–606)
- `nowing_backend/app/routes/documents_routes.py` (`create_documents` line 59, `create_documents_file_upload` line 118)
- `nowing_backend/app/routes/rbac_routes.py` (`create_invite` line 730, `accept_invite` line 1018)
- `nowing_backend/app/capabilities/core/access/rest.py` (`_register_verb` line 177, `gate_capability` call line 205)
- `nowing_backend/app/services/usage_service.py`
- `nowing_backend/app/schemas/workspace.py` and `nowing_backend/app/schemas/__init__.py` (line 148)
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx`
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/general/page.tsx`
- `nowing_web/components/usage/usage-content.tsx` (SummaryCard pattern line 160)
- `nowing_web/lib/apis/workspaces-api.service.ts`
- `nowing_web/contracts/types/workspace.types.ts`
- `nowing_web/lib/query-client/cache-keys.ts`
- `nowing_web/messages/en.json` (`workspaceSettings` line 768)
