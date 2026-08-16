story_key: 25-1-multitenant-user-workspace-hub-scoped-impersonation
status: ready-for-dev
baseline_commit: 13f09ce60057422f281e263d90f2ca76db9e54a3
epic: 25
story: 1
---

# Story 25.1: Multi-Tenant User & Workspace Hub + Scoped Impersonation

Status: ready-for-dev

<!-- Note: Governed by INV-25.1, INV-25.2, INV-25.8, and Architecture Spine: epics.md (Epic 25) -->

## Story

As a Platform Superadmin,  
I want a centralized Multi-Tenant User and Workspace Management Hub with secure 1-click Support Impersonation ("Login as User"),  
So that I can monitor tenant usage, ban/suspend fraudulent accounts, and rapidly diagnose and resolve customer support tickets without sharing passwords or compromising system security.

---

## Acceptance Criteria

### AC-1 — High-Density User & Workspace Management Directory
**Given** an authenticated Superadmin interactive session on `/admin/users` or `/admin/workspaces`,  
**When** the page loads,  
**Then** it renders a high-density data matrix (36px row height, monospace IDs/UUIDs/timestamps) with:
- Search filter by email, phone, workspace name, plan, and status.
- Stats breakdown: Total users, active workspaces, plan distribution, total credits balance.
- Action triggers: `Ban / Unban User`, `Suspend Workspace`, `View Audit Logs`, `Impersonate`.

### AC-2 — Scoped Short-Lived Impersonation JWT (TTL 15m)
**Given** an active Superadmin inspecting a user in the Admin Hub,  
**When** the admin clicks `⚡ Impersonate User` and provides a support ticket reference,  
**Then** `POST /api/v1/admin/impersonate` validates `User.is_superuser == True`, issues a scoped short-lived JWT (TTL 15 minutes) containing claims:
- `sub`: `<target_user_uuid>`
- `impersonated_by`: `<admin_uuid>`
- `is_impersonation`: `true`
- `ticket_ref`: `<ticket_url_or_id>`  
**And** logs an immutable `AuditEvent` (`action='user.impersonate_start'`).

### AC-3 — Privilege Stripping & Destructive Action Hard-Block
**Given** an active impersonated session,  
**When** the client dispatches requests,  
**Then** Backend Security Middleware (`require_session_context` / `ImpersonationGuard`) strips `is_superuser` from the context and rejects with `HTTP 403 Forbidden` for:
- Any access to `/admin/*` routes.
- Destructive security operations: Change Password, Reset 2FA, Delete Account, Issue Personal Access Token (PAT).
- Nested impersonation attempts.

### AC-4 — Persistent Sticky Hazard Banner & Viewport Border
**Given** a browser in an active impersonation session on `/dashboard/[workspace_id]/*`,  
**When** any page renders,  
**Then** the UI displays:
- A persistent 40px sticky amber hazard banner at `z-[9999]` displaying: `⚠️ IMPERSONATION ACTIVE: Impersonating [User Email] in [Workspace Name] | Session: MM:SS remaining`.
- A 4px amber border framing the entire viewport (`fixed inset-0 pointer-events-none border-4 border-amber-500/80`).
- A `1-Click Exit Impersonation (Esc)` button that immediately clears impersonation cookies and returns to the Admin User Directory.

---

## Tasks / Subtasks

- [ ] Task 1: Backend Scoped Impersonation JWT & Token Manager (FastAPI)
  - [ ] Implement `create_impersonation_token(admin_user, target_user, ticket_ref, ttl_seconds=900)` in `app/users.py` / `app/auth/impersonation.py`.
  - [ ] Implement `POST /api/v1/admin/users/{user_id}/impersonate` and `POST /api/v1/admin/impersonate/exit`.
  - [ ] Add `ImpersonationGuard` middleware to strip `is_superuser` and block security mutations.
- [ ] Task 2: Dual-Principal Audit Event Logging
  - [ ] Record `actor_id` (admin) and `subject_id` (target user) on every mutation during impersonation.
- [ ] Task 3: Frontend Superadmin Navigation & Multi-Tenant Directory
  - [ ] Create `/admin/users` and `/admin/workspaces` with high-density data matrix layout (`@tanstack/react-virtual`).
  - [ ] Add Search, Filter, Ban/Suspend controls with Radix confirmation dialogs.
- [ ] Task 4: Frontend Sticky Impersonation Hazard Banner & Viewport Frame
  - [ ] Create `components/admin/ImpersonationBanner.tsx` with countdown timer and `Esc` keyboard shortcut.
  - [ ] Attach amber border frame to root layout when impersonation cookie/claim is active.
- [ ] Task 5: Automated Test Suite (Unit & Integration)
  - [ ] `tests/integration/admin/test_impersonation_security.py`: Verify token expiration, claim integrity, and privilege stripping.
  - [ ] `tests/integration/admin/test_admin_authz_fail_closed.py`: AST reflection test confirming all `/admin/*` routes enforce `require_superuser`.
