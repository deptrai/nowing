---
story_key: 29-1-custom-workspace-roles-permissions-builder
status: done
baseline_commit: 9d2e043a1
epic: 29
story: 1
---

# Story 29.1: Custom Workspace Roles & Permissions Builder

**Status:** `done`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-100, AR-17, AR-18, UX-DR-PRFAQ-5, NFR-2, NFR-5, INV-29.1, AD-9, AD-51, `epics.md` lines 4370–4390, `ux-contract-epic-29-saas-admin-analytics.md` §1 (RB-1..RB-5).  
**Dependencies:** Existing `WorkspaceRole`, `WorkspaceMembership`, `Permission` enum (`nowing_backend/app/db/enums.py`), `rbac_routes.py`, `nowing_web/components/settings/roles-manager.tsx`.

---

## Story

As a **workspace Owner**,  
I want **to define custom roles (e.g. Analyst, Editor, Billing Viewer) with a fine-grained permissions matrix and template presets**,  
so that **I can safely delegate operational access without granting full Owner privileges or accidentally leaking sensitive administrative operations**.

---

## Acceptance Criteria

### AC-1 — Extended Permission Enum & Canonical Mapping
**Given** the backend RBAC subsystem,  
**When** permissions are listed or validated,  
**Then**:
1. The `Permission` enum in `nowing_backend/app/db/enums.py` and `nowing_web/contracts/types/permissions.types.ts` include the canonical colon-separated permissions:
   - `analytics:read` (Epic alias: `analytics_read`) — View workspace analytics & adoption metrics.
   - `billing:read` (Epic alias: `billing_read`) — View workspace plans, credit balances, and invoices.
   - `billing:manage` (Epic alias: `billing_manage`) — Upgrade/downgrade plans and manage payment methods.
   - `source:configure` (Epic alias: `source_configure`) — Enable, disable, and configure scraper/connector sources.
   - `tools:enable` (Epic alias: `tool_enable`) — Toggle MCP tools and agent tool configurations.
   - `memory:read` — Search and recall long-term research memories.
   - `memory:create`, `memory:update` (Epic alias: `memory_write`) — Create and edit memory facts.
   - `memory:delete` — Remove memory records.
   - `settings:view` (Epic alias: `settings_read`) — View workspace configuration.
   - `settings:update` (Epic alias: `settings_write`) — Edit workspace metadata and parameters.
   - `members:invite` (Epic alias: `member_invite`) — Invite new users to the workspace.
   - `members:remove` (Epic alias: `member_remove`) — Remove members from the workspace.
2. `PERMISSION_DESCRIPTIONS` in `nowing_backend/app/routes/rbac_routes.py` and `CATEGORY_CONFIG` in `roles-manager.tsx` group these new permissions under clear categories (`Analytics`, `Billing`, `Sources & Tools`, `Memory`).

### AC-2 — Owner Permission Ceiling & System Role Protection (INV-29.1, AD-51)
**Given** a role mutation via `POST /api/v1/workspaces/{workspace_id}/roles` or `PUT /api/v1/workspaces/{workspace_id}/roles/{role_id}`,  
**When** the request is validated,  
**Then**:
1. **Owner Ceiling:** The permissions granted to the custom role must be a strict subset of the workspace Owner's active permissions.
   - Custom roles **cannot** contain the wildcard `*` (`FULL_ACCESS`).
   - If a custom role includes a permission not held by the workspace Owner (or not in the allowed ceiling), the API rejects with HTTP `400 Bad Request` and detail `"Custom roles cannot grant permissions exceeding Owner ceiling"`.
2. **System Role Protection:**
   - Custom roles must have `is_system_role=False`. The API forcibly overrides or rejects any attempt to pass `is_system_role=True`.
   - Built-in system roles (`is_system_role=True`: `Owner`, `Editor`, `Viewer`) are immutable: `PUT` or `DELETE` requests targeting them must be rejected with HTTP `403 Forbidden` (`"System roles cannot be modified or deleted"`).
3. **Reserved "Admin" Name Guard (RB-4):**
   - The role name `"Admin"` (case-insensitive, e.g. `"admin"`, `"ADMIN"`, `"Admin"`) is reserved and prohibited.
   - The API rejects with HTTP `400 Bad Request` and detail `"The role name 'Admin' is reserved"`.
   - The UI provides inline validation disabling the "Save" button and rendering an error: *"The role name 'Admin' is reserved"*.

### AC-3 — Role Template Presets & Conflict Warning Chips (RB-2, RB-3)
**Given** the Owner opens the Role Builder Dialog in `roles-manager.tsx`,  
**When** creating a role,  
**Then**:
1. A template selector dropdown is displayed with presets:
   - **Viewer:** `documents:read`, `chats:read`, `comments:create`, `comments:read`, `llm_configs:read`, `podcasts:read`, `automations:read`, `connectors:read`, `logs:read`, `members:view`, `roles:read`, `settings:view`, `memory:read`.
   - **Editor:** All Viewer permissions plus `documents:create`, `documents:update`, `chats:create`, `chats:update`, `automations:create`, `automations:update`, `automations:execute`, `connectors:create`, `connectors:update`, `members:invite`, `memory:create`, `memory:update`, `tools:enable`, `source:configure`.
   - **Analyst:** `documents:read`, `chats:read`, `logs:read`, `members:view`, `memory:read`, `analytics:read`.
   - **Billing:** `settings:view`, `members:view`, `billing:read`, `billing:manage`.
   - **Custom:** Starts with empty selection.
2. Selecting a template instantly populates the permission matrix checkboxes.
3. If an Owner manually selects a permission that exceeds the recommended baseline of the active template (e.g. checking `member_remove` or `settings:update` while on the `Analyst` template), the UI renders an amber warning chip above the category: *"This exceeds the recommended template"*. The Owner is still permitted to save after acknowledging the warning.

### AC-4 — Role Clone, Audit Logging & Cache Invalidation (AR-18, RB-5)
**Given** an existing custom role,  
**When** the Owner interacts with role management actions,  
**Then**:
1. **Clone Role:** Clicking "Clone Role" opens the Create Role dialog with the name pre-filled as `"{existing_name} (Copy)"` and all permission checkboxes pre-checked matching the source role.
2. **Audit Logging (AR-18):** Every role creation, update, and deletion writes an `AuditEvent` row in `nowing_backend`:
   - `action`: `"workspace.role.create"`, `"workspace.role.update"`, `"workspace.role.delete"`.
   - `actor_id`: `auth.user.id`.
   - `diff_payload`: JSON capturing `workspace_id`, `role_id`, `role_name`, and `permissions`.
3. **Client Cache Invalidation:** `createRoleMutationAtom`, `updateRoleMutationAtom`, and `deleteRoleMutationAtom` in `roles-mutation.atoms.ts` invalidate:
   - `cacheKeys.roles.all(workspaceId)`
   - `cacheKeys.members.myAccess(workspaceId)`
   - `cacheKeys.members.all(workspaceId)`
   Ensuring member UI permissions refresh immediately without a full page reload.

---

## Tasks / Subtasks

- [x] Task 1 — Backend Permissions & Security Guardrails (AC: 1, 2, 4)
  - [x] 1.1 Add new enum keys in `nowing_backend/app/db/enums.py`:
    - `ANALYTICS_READ = "analytics:read"`
    - `BILLING_READ = "billing:read"`
    - `BILLING_MANAGE = "billing:manage"`
    - `SOURCE_CONFIGURE = "source:configure"`
    - `TOOLS_ENABLE = "tools:enable"`
  - [x] 1.2 Update `PERMISSION_DESCRIPTIONS` in `nowing_backend/app/routes/rbac_routes.py` with descriptions for the new permissions.
  - [x] 1.3 In `create_role` and `update_role` (`rbac_routes.py`):
    - Enforce reserved `"Admin"` name check (`if role_data.name.strip().lower() == "admin": raise HTTPException(400, "The role name 'Admin' is reserved")`).
    - Enforce system role protection on `update_role` and `delete_role` (`if db_role.is_system_role: raise HTTPException(403, "System roles cannot be modified or deleted")`).
    - Enforce Owner ceiling: reject if `*` is present or if any permission is outside valid system permissions.
  - [x] 1.4 Add `audit_events` emission in `create_role`, `update_role`, `delete_role`.

- [x] Task 2 — Frontend Role Builder UI & Template Presets (AC: 2, 3, 4)
  - [x] 2.1 Update TypeScript contracts in `nowing_web/contracts/types/permissions.types.ts` to include the new permissions and categories.
  - [x] 2.2 Define template configurations in `nowing_web/components/settings/roles-manager.tsx`:
    - Add `ROLE_TEMPLATES` dictionary containing presets for `viewer`, `editor`, `analyst`, `billing`, and `custom`.
  - [x] 2.3 Update `CreateRoleDialog`:
    - Add template `<Select>` dropdown at the top.
    - When template changes, auto-populate `selectedPermissions`.
    - Detect when selected permissions diverge from template and render warning chip: *"This exceeds the recommended template"*.
    - Add inline validation for role name `"Admin"` with helper text and disabled save button.
  - [x] 2.4 Add "Clone Role" in role card actions dropdown menu.
  - [x] 2.5 In `nowing_web/atoms/roles/roles-mutation.atoms.ts`, add invalidation for `cacheKeys.members.myAccess` and `cacheKeys.members.all`.

- [x] Task 3 — Automated Verification & Testing (AC: 1, 2, 3, 4)
  - [x] 3.1 Backend unit tests in `nowing_backend/tests/unit/routes/test_rbac_custom_roles.py`:
    - Test "Admin" name rejection on create and update.
    - Test system role modification/deletion rejection (HTTP 403).
    - Test Owner ceiling validation rejection when attempting to assign `*` or invalid permissions.
    - Test successful custom role creation and update with extended permissions (`analytics:read`, `billing:read`).
  - [x] 3.2 Frontend component tests for template presets, warning chip visibility, and Admin name validation.
  - [x] 3.3 E2E test in `nowing_web/tests/settings/custom-roles-builder.spec.ts` verifying role creation, template preset loading, and role cloning.

### Review Findings
- [x] [Review][Patch] Permission deduplication on role create/update [`nowing_backend/app/routes/rbac_routes.py:230, 427`] — Applied
- [x] [Review][Patch] Empty role name guard on create/update [`nowing_backend/app/routes/rbac_routes.py:188, 392`] — Applied
- [x] [Review][Patch] Optional chaining guard for workspace_id in mutation onSuccess [`nowing_web/atoms/roles/roles-mutation.atoms.ts:23, 49, 78`] — Applied
- [x] [Review][Patch] Unit tests for permission deduplication and empty permissions list [`nowing_backend/tests/unit/routes/test_rbac_custom_roles.py:377-422`] — Applied

---

## Dev Notes

### Architecture Compliance (AD-51, INV-29.1)
- **Zero New Tables:** Custom roles continue to be stored in the existing `workspace_roles` table with `is_system_role = False`.
- **Single Source of Truth:** `WorkspaceRole` is the sole source of truth for permissions. `WorkspaceMembership.role_id` maps each member to exactly one role.
- **Audit Logging:** Uses existing `AuditEvent` model (`app/models/billing.py:616`). `actor_id` is set to `auth.user.id`; role parameters are serialized into `diff_payload`.
- **System Role Guarantee:** Migration 72 eliminated the `Admin` system role. Only `Owner`, `Editor`, and `Viewer` exist as system roles.

### Files to Modify
- Backend:
  - `nowing_backend/app/db/enums.py`
  - `nowing_backend/app/routes/rbac_routes.py`
  - `nowing_backend/app/models/users.py`
- Frontend:
  - `nowing_web/contracts/types/permissions.types.ts`
  - `nowing_web/components/settings/roles-manager.tsx`
  - `nowing_web/atoms/roles/roles-mutation.atoms.ts`

---

## Challenge Log (grill-me)

### Q1 — Already implemented?
- Basic RBAC CRUD (`/workspaces/{workspace_id}/roles`, `WorkspaceRole`, `WorkspaceMembership`, `Permission` enum) exists.
- Extended permissions (`analytics:read`, `billing:read`, `billing:manage`, `source:configure`, `tools:enable`), Owner ceiling guard, immutable system role protection, "Admin" reserved name guard, template presets, conflict warning chips, role cloning, dual-principal `AuditEvent`, and client cache invalidation are NOT implemented.
- Clean — No duplicate logic found.

### Q2 — Simpler alternative?
- Existing `AuditEvent` model (`nowing_backend/app/models/billing.py:616`) can be directly reused without creating new database tables or migrations (AD-51, INV-29.1 compliance).
- Existing `WorkspaceRole` table has `is_system_role` flag and `permissions` JSONB column — no schema migration required.
- Existing `roles-manager.tsx` can directly house `ROLE_TEMPLATES`, template selector, warning chip, and clone action without external libraries.
- Clean — No simpler alternative needed, reuse existing models & components.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: Role name `"Admin"` case variations (`"admin"`, `"ADMIN"`, `"  Admin  "`). Enforce `.strip().lower() == "admin"`.
- [ ] Boundary: Custom role permission cannot contain `*` (FULL_ACCESS). Must reject with HTTP 400 `"Custom roles cannot grant permissions exceeding Owner ceiling"`.
- [ ] Null/empty: Role name with whitespace only (`"   "`) rejected by backend validator (`min_length=1`).
- [ ] Null/empty: Role `permissions` array empty `[]` — valid for Custom template initially, but if saved, members have 0 permissions.
- [ ] Foreign Key / Delete: Deleting a custom role currently referenced by members/invites sets `role_id = NULL` safely (`ondelete="SET NULL"` on `WorkspaceMembership` and `WorkspaceInvite`).
- [ ] Duplicate Name: Case-insensitive role name conflict within the same workspace.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] System Role Mutation: Attempt to `PUT` or `DELETE` system roles (`is_system_role=True`) must return HTTP 403 Forbidden with detail `"System roles cannot be modified or deleted"`.
- [ ] Audit Event Consistency: `AuditEvent` row creation should be committed in the same database transaction as the role mutation; if DB commit fails, both roll back.
- [ ] Role Clone Non-Existent: Attempting to clone a non-existent `role_id` or cross-workspace `role_id` should fail gracefully in UI or API (HTTP 404).

### Triage
- Clean — No critical architectural blockers. All findings incorporated into test skeleton and implementation plan.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5

### Completion Notes List
- Validated against AD-51, INV-29.1, and UX Contract Epic 29 §1.
- Detailed canonical permission mapping, template presets, and audit event schema.
- Conducted multi-layer adversarial code review (Blind Hunter, Edge Case Hunter, Verification Gap, Acceptance Auditor).
- Applied review patches: permission deduplication, clean whitespace validation, mutation guard for workspace_id, and 2 new regression unit tests (18 passed).
- Next.js Turbopack build 114/114 pages compiled successfully.

### File List
- `_bmad-output/implementation-artifacts/stories/29-1-custom-workspace-roles-permissions-builder.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/test-artifacts/atdd-checklist-29-1-custom-workspace-roles-permissions-builder.md`
- `nowing_backend/app/db/enums.py`
- `nowing_backend/app/routes/rbac_routes.py`
- `nowing_backend/tests/unit/routes/test_rbac_custom_roles.py`
- `nowing_web/contracts/types/permissions.types.ts`
- `nowing_web/atoms/roles/roles-mutation.atoms.ts`
- `nowing_web/components/settings/roles-manager.tsx`
- `nowing_web/tests/settings/custom-roles-builder.spec.ts`
