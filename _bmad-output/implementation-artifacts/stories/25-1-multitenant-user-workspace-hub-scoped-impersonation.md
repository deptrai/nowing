story_key: 25-1-multitenant-user-workspace-hub-scoped-impersonation
status: ready-for-dev
baseline_commit: 13f09ce60057422f281e263d90f2ca76db9e54a3
epic: 25
story: 1
---

# Story 25.1: Multi-Tenant User & Workspace Hub + Scoped Impersonation

Status: in-review

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
**Then** `POST /api/v1/admin/users/{user_id}/impersonate` validates `User.is_superuser == True`, issues a scoped short-lived JWT (TTL 15 minutes) containing claims:
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

- [x] Task 1: Backend Scoped Impersonation JWT & Token Manager (FastAPI)
  - [x] Implement `create_impersonation_token(admin_user, target_user, ticket_ref, ttl_seconds=900)` in `app/users.py` / `app/auth/impersonation.py`.
  - [x] Implement `POST /api/v1/admin/users/{user_id}/impersonate` and `POST /api/v1/admin/impersonate/exit`.
  - [x] Add `ImpersonationGuard` middleware to block destructive security operations.
- [x] Task 2: Dual-Principal Audit Event Logging
  - [x] Record `actor_id` (admin) and `subject_id` (target user) on every mutation during impersonation.
- [x] Task 3: Frontend Superadmin Navigation & Multi-Tenant Directory
  - [x] Create `/admin/users` and `/admin/workspaces` with live data tables, search, and nav.
  - [ ] Add advanced filter, Ban/Suspend controls with Radix confirmation dialogs.
- [x] Task 4: Frontend Sticky Impersonation Hazard Banner & Viewport Frame
  - [x] Create `components/admin/ImpersonationBanner.tsx` with countdown timer and `Esc` keyboard shortcut.
  - [x] Attach amber border frame to root layout when impersonation claim is active.
- [x] Task 5: Automated Test Suite (Unit & Integration)
  - [x] `tests/integration/routes/test_admin_impersonation.py`: Verify token expiration, claim integrity, and privilege stripping.
  - [x] `tests/integration/admin/test_admin_authz_fail_closed.py`: AST reflection test confirming all `/admin/*` routes enforce `require_superuser`.

### Review Findings — Code Review 25.1 (2026-08-17)

#### Decision

- [x] [Review][Decision] Giữ endpoint path `/admin/users/{user_id}/impersonate`; cập nhật AC-2 spec cho khớp.

#### Patch (P0)

- [x] [Review][Patch] Thêm Alembic migration `223_add_audit_events_table` và cập nhật model `AuditEvent` (`actor_id`/`subject_id` nullable, `ondelete="SET NULL"`, thêm `ip_address`, `user_agent`, `diff_payload`)
- [x] [Review][Patch] Xóa mutation `user.is_superuser = False` trong `get_auth_context`; `require_superuser` đã nhận diện impersonation qua `AuthContext` từ target user.

#### Patch (P1)

- [x] [Review][Patch] `impersonate_user` dùng `uuid.UUID` cho `user_id` (FastAPI tự validate), validate `ticket_ref` 1-255 ký tự, kiểm tra `target_user.is_active`, chặn self-impersonation, populate `ip_address`/`user_agent`
- [x] [Review][Patch] Implement `POST /admin/impersonate/exit` cơ bản: yêu cầu `auth.is_impersonation`, ghi audit `user.impersonate_exit`
- [x] [Review][Patch] Implement `GET /admin/users` cơ bản (limit 1000, trả về id/email/is_active/is_superuser/is_verified)
- [x] [Review][Patch] Implement `GET /admin/workspaces` và `/admin/workspaces` page — AC-1
- [x] [Review][Patch] Thêm `ImpersonationGuard` middleware áp dụng cho các destructive security operation (đổi password, reset 2FA, xóa account, issue PAT) — còn lại cho Task 1/2

#### Patch (P2)

- [x] [Review][Patch] `ttl_seconds` trong `create_impersonation_token` giới hạn 1-3600 giây
- [x] [Review][Patch] `jwt.decode` 2 lần trong `get_auth_context` — chấp nhận vì `read_token` không expose payload; để tối ưu sau
- [x] [Review][Patch] `AuthContext` là frozen dataclass nhưng chứa mutable `User` — chấp nhận; tách copy user object sẽ tốn kém và không cần thiết sau khi bỏ mutation

#### Defer

- [x] [Review][Defer] E2E tests `nowing_web/tests/admin/impersonation.spec.ts` còn scaffold `test.fail` — thuộc ATDD red-phase, implement sau.
