---
story_key: 25-6-security-audit-trail-logs-and-in-app-broadcast-announcements
status: done
baseline_commit: ffc2be6904da940176433b336762eb091eab7d38
epic: 25
story: 6
---

# Story 25.6: Security Audit Trail Logs & In-App Broadcast Announcements

**Status:** `done`

**Governed by:** `INV-25.2` (Dual-Principal Audit Integrity - PDPD Decree 13), `INV-25.8` (Fail-Closed Superadmin Guard & PAT Rejection), `AD-110` (PII Opt-Out Blacklist & Decree 13 Compliance), Epic 25 in [`_bmad-output/planning-artifacts/epics.md`](../planning-artifacts/epics.md) lines 3531–3640.

---

## Story

As a **Platform Superadmin**,  
I want a unified security audit log viewer, a global DNC / PII exclusion blacklist manager, and an in-app broadcast announcement engine on the admin console,  
so that I can ensure full compliance with Vietnam Personal Data Protection Decree 13 (Nghị định 13/2023/NĐ-CP), enforce global anti-spam / opt-out mandates (Nghị định 91/2020/NĐ-CP), and broadcast 1-click real-time maintenance or marketing alerts to all users across the platform.

---

## Acceptance Criteria

### AC-1 — Security Audit Trail Logs API & Admin Viewer

**Given** `/admin/audit-logs` is opened by an authenticated Superadmin session,  
**When** the audit trail page loads or a query filter is applied,  
**Then**:
- The backend endpoint `GET /api/v1/admin/audit-logs` returns paginated, immutable audit records from the `audit_events` table with SQL `outerjoin` on `User` (aliased `ActorUser` and `SubjectUser`) to include `actor_email` and `subject_email` directly.
- Supports filtering by:
  - `action`: string filter from `AuditActionEnum` or free-form action string. Known values include existing actions (`user.impersonate_start`, `user.impersonate_exit`, `scraper_rule.create`, `scraper_rule.activate`, `scraper_rule.delete`, `scraper_rule.trip`, `scraper_rule.reset`, `manual_credit_quota_exceeded`) and new 25.6 actions (`global_dnc.add`, `global_dnc.remove`, `broadcast.create`, `broadcast.update`, `broadcast.delete`, `audit_log.view`).
  - `actor_id` / `actor_email`: filter by initiating admin.
  - `subject_id` / `subject_email`: filter by target user (UUID FK to `user.id`); for non-user targets (DNC record, broadcast, etc.) `subject_id` is `None` and the entity id is in `diff_payload.subject_id` / `diff_payload.entity_id`.
  - `ticket_ref`: search by support ticket reference.
  - `start_date` / `end_date`: ISO 8601 timestamp range.
  - `limit` (default 50, max 200) and `offset`.
- The UI renders an interactive table with columns: `Timestamp (UTC & Local)`, `Action Badge`, `Actor (Admin Email)`, `Subject (Target Email/Entity)`, `IP Address`, `Ticket Ref`, and a `Details` button.
- Clicking `Details` opens a slide-over drawer / modal showing formatted JSON of `diff_payload`, `user_agent`, and metadata.
- An `Export CSV` / `Export JSON` action allows downloading the filtered audit timeline for compliance reporting.

---

### AC-2 — Global DNC (Do-Not-Call) & PII Blacklist Manager (Single & Bulk CSV)

**Given** the Global DNC Blacklist section on `/admin/dnc`,  
**When** the Superadmin views, adds, bulk imports, or removes blacklisted entities,  
**Then**:
- `GET /api/v1/admin/dnc/global` lists all records in `global_dnc_records` with pagination, filter by `record_type` (`phone`, `domain`, `email`, `tax_id`), and search by masked value / reason.
- `POST /api/v1/admin/dnc/global` accepts `{ record_type, value, reason, source }`:
  - Canonicalizes the value (E.164 for phone, lowercase for domain/email/tax_id) using existing `app/lead_intelligence/dnc/normalizer` helpers.
  - Computes deterministic `value_hmac = HMAC-SHA256(canonical_value, config.SECRET_KEY)`.
  - Persists to `global_dnc_records` with unique constraint `(record_type, value_hmac)`.
  - Writes an `AuditEvent` with `action="global_dnc.add"`, `actor_id=admin_uuid`, `ip_address`, `user_agent`, `endpoint`, and `diff_payload={record_type, masked_value, value_hmac, reason, endpoint}` (INV-25.2).
  - Calls `DncComplianceService(secret_key=config.SECRET_KEY).invalidate_global_cache()` so the next global DNC check rebuilds from the DB and suppresses the entity in < 500ms.
- `POST /api/v1/admin/dnc/global/import-csv` accepts a CSV file (`record_type,value,reason`), validates and hashes each row, performs bulk upsert `ON CONFLICT DO NOTHING`, invalidates global DNC cache, and returns `{ imported_count, skipped_count, failed_count, errors }` (same shape as `DncCsvImportResponse`).
- `DELETE /api/v1/admin/dnc/global/{id}` removes the blacklist entry, calls `DncComplianceService.invalidate_global_cache()`, and records an `AuditEvent(action="global_dnc.remove")` with `actor_id`, `ip_address`, `user_agent`, `endpoint`, and `diff_payload` including `record_id`, `record_type`, and `value_hmac`.

---

### AC-3 — In-App Broadcast Announcements CRUD & Scope Targeting

**Given** the Broadcast Announcements console on `/admin/broadcasts`,  
**When** a Superadmin creates or manages an announcement,  
**Then**:
- `POST /api/v1/admin/broadcasts` creates a new announcement with schema:
  - `title`: string (1–255 chars).
  - `message`: string (Markdown-supported rich text).
  - `banner_type`: enum `info` (blue), `warning` (amber), `maintenance` (red), `promo` (emerald/purple).
  - `target_all`: boolean (default `true`).
  - `target_workspace_ids`: list of integers (optional; when `target_all=false`, validates that all workspace IDs exist).
  - `starts_at`: datetime (ISO 8601, default `now(UTC)`).
  - `expires_at`: datetime (ISO 8601, nullable).
  - `dismissible`: boolean (default `true`).
  - `is_active`: boolean (default `true`).
- Writes an `AuditEvent` with `action="broadcast.create"`, `actor_id=admin_uuid`, `ip_address`, `user_agent`, `endpoint`, and `diff_payload={title, message, banner_type, target_all, target_workspace_ids, starts_at, expires_at, dismissible, is_active, endpoint}` (INV-25.2).
- `GET /api/v1/admin/broadcasts` returns all broadcast announcements with a derived `status` field (`active` | `scheduled` | `expired` | `inactive`) computed from `is_active`, `starts_at`, and `expires_at`, sorted by `created_at DESC`.
- `PATCH /api/v1/admin/broadcasts/{id}` allows toggling `is_active`, editing message, or changing expiration time, records `action="broadcast.update"` with a `diff_payload` containing the changed fields and `endpoint`.
- `DELETE /api/v1/admin/broadcasts/{id}` deletes the announcement with audit logging (`action="broadcast.delete"`) and `diff_payload={broadcast_id, title, endpoint}`.

---

### AC-4 — Real-time Dashboard In-App Broadcast Banner Mounting & Dismissal

**Given** an active broadcast announcement exists,  
**When** any user opens `/dashboard/*` (or `/admin/*`),  
**Then**:
- The table `broadcast_announcements` is registered in `app/zero_publication.py` for Zero-cache CDC. The frontend implements a `useBroadcastAnnouncements` hook that subscribes via Zero when available and falls back to polling `GET /api/v1/broadcasts/active` every 60s.
- `GET /api/v1/broadcasts/active` is authenticated for any logged-in user (not just superadmin), accepts an optional `workspace_id` query param, and returns rows where:
  - `is_active == True`
  - `starts_at <= now(UTC)`
  - `expires_at IS NULL OR expires_at > now(UTC)`
  - `target_all == True OR workspace_id IN target_workspace_ids` (use Postgres `jsonb_exists` / `func.jsonb_array_contains` for the JSONB containment check)
- A top banner (`BroadcastBanner.tsx`) renders inside `app/dashboard/dashboard-shell.tsx` and `app/admin/admin-shell.tsx` (both client components) matching `banner_type` theme.
- If `dismissible == true`, clicking the close button (`X`) hides the banner and stores `{ [announcement_id]: dismissed_timestamp }` in `localStorage` under key `nowing:dismissed_broadcasts` so it does not reappear on subsequent page navigations during the session.
- When an announcement expires or is deactivated by admin, it unmounts gracefully without requiring a full browser refresh.

---

### AC-5 — Fail-Closed Superadmin Security Guard & PAT Rejection (INV-25.8)

**Given** any `/api/v1/admin/audit-logs*`, `/api/v1/admin/dnc/global*`, or `/api/v1/admin/broadcasts*` endpoint,  
**When** accessed by a non-superuser, an unauthenticated request, a Personal Access Token (PAT), or an impersonated session,  
**Then** the request is rejected with `HTTP 403 Forbidden` (or `401 Unauthorized`) via `require_superuser` (which depends on `require_session_context` and rejects `auth.is_impersonation`).

---

## Tasks / Subtasks

### Backend

- [x] **Task 1: Database Schema, Zero Publication & Migration for Broadcast Announcements**
  - [x] Define `BroadcastAnnouncement` model in `app/db.py`:
    ```python
    class BroadcastAnnouncement(Base):
        __tablename__ = "broadcast_announcements"
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        title = Column(String(255), nullable=False)
        message = Column(Text, nullable=False)
        banner_type = Column(String(20), nullable=False, default="info")
        target_all = Column(Boolean, nullable=False, default=True, server_default=text("true"))
        target_workspace_ids = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
        starts_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=text("now()"))
        expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
        dismissible = Column(Boolean, nullable=False, default=True, server_default=text("true"))
        is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
        created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
        updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
        created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=text("now()"))
        updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), server_default=text("now()"))
    ```
  - [x] Add `broadcast_announcements` to `ensure_publication` in `app/zero_publication.py` with all columns or an explicit column list.
  - [x] Generate a new Alembic revision from current `head` (`alembic upgrade head` then `uv run alembic revision --autogenerate -m "add broadcast announcements table"`) and edit it to add:
    - `id` as `postgresql.UUID(as_uuid=True)` primary key.
    - GIN index on `target_workspace_ids` and B-tree index on `created_by_user_id`.
    - Index `ix_broadcast_announcements_active_window` on `(is_active, starts_at, expires_at)`.
- [x] **Task 2: Admin Audit Logs Query Service & REST Routes**
  - [x] Create `app/schemas/admin_audit_logs.py` with `AuditActionEnum` (use actual existing/new lowercase dot-separated action strings), `AuditEventRead` (with `endpoint` from `diff_payload` or model column), `AuditEventListResponse`, and query filter schemas.
  - [x] Create `app/services/admin_audit_log_service.py` with SQL outer joins on `User` for `actor_email` and `subject_email`, pagination, and date range filtering.
  - [x] Create `app/routes/admin_audit_logs_routes.py` with `GET /api/v1/admin/audit-logs` guarded by `require_superuser`.
  - [x] Wire router by importing and including it in `app/routes/__init__.py` (not `app/app.py`).
- [x] **Task 3: Global DNC Blacklist Admin REST Routes (Single & CSV Import)**
  - [x] Create `app/schemas/admin_dnc.py` for global DNC requests, responses, and CSV import summaries.
  - [x] Add `app/routes/admin_dnc_routes.py` implementing `GET /api/v1/admin/dnc/global`, `POST /api/v1/admin/dnc/global`, `POST /api/v1/admin/dnc/global/import-csv`, and `DELETE /api/v1/admin/dnc/global/{id}`.
  - [x] Ensure `POST`, `CSV Import`, and `DELETE` log `AuditEvent` (INV-25.2) with `ip_address`, `user_agent`, and `endpoint`, and call `DncComplianceService.invalidate_global_cache()`.
  - [x] Wire router by importing and including it in `app/routes/__init__.py`.
- [x] **Task 4: In-App Broadcast Announcements Backend Services & Routes**
  - [x] Create `app/schemas/broadcasts.py` with `BroadcastCreate`, `BroadcastUpdate`, `BroadcastRead` (include derived `status`), and `BroadcastListResponse`.
  - [x] Create `app/services/broadcast_service.py` with CRUD, workspace existence validation, active query evaluation with `func.jsonb_exists` for `target_workspace_ids`, and derived `status`.
  - [x] Create `app/routes/admin_broadcasts_routes.py` for admin CRUD endpoints, all guarded by `require_superuser`.
  - [x] Create `app/routes/broadcasts_routes.py` for user-facing `GET /api/v1/broadcasts/active` using `get_auth_context` and an optional `workspace_id` query param.
  - [x] Wire routers by importing and including them in `app/routes/__init__.py`.
  - [x] Add a Celery Beat schedule in `app/celery_app.py` and a task (e.g., `app/tasks/celery_tasks/broadcast_tasks.py`) to refresh derived `status` / expire announcements every minute.

### Frontend

- [x] **Task 5: Frontend API Services, Hooks & Type Contracts**
  - [x] Create `contracts/types/admin-audit-logs.types.ts`, `contracts/types/admin-dnc.types.ts`, `contracts/types/broadcasts.types.ts`.
  - [x] Create `lib/apis/admin-audit-logs-api.service.ts`, `lib/apis/admin-dnc-api.service.ts`, `lib/apis/broadcasts-api.service.ts` (use `baseApiService` pattern; broadcast active endpoint accepts `workspace_id`).
  - [x] Create `lib/hooks/use-broadcast-announcements.ts` that subscribes via Zero when available and falls back to polling `broadcastsApi.active(workspace_id)` every 60s.
- [x] **Task 6: Admin Audit Trail UI (`/admin/audit-logs`)**
  - [x] Create `app/admin/audit-logs/page.tsx` with filter bar (action type dropdown, date range picker, actor/subject email, ticket ref), sortable paginated table, and diff JSON drawer modal.
  - [x] Add CSV export action for compliance audit reports.
  - [x] Add navigation link in `app/admin/admin-shell.tsx`.
- [x] **Task 7: Global DNC Blacklist Manager UI (`/admin/dnc`)**
  - [x] Create `app/admin/dnc/page.tsx` with Add Blacklist Entry modal (Phone, Domain, Email, Tax ID), CSV Bulk Import Modal, reason input, and searchable paginated table.
  - [x] Add delete confirmation dialog.
  - [x] Add navigation link in `app/admin/admin-shell.tsx`.
- [x] **Task 8: Broadcast Announcements Admin UI (`/admin/broadcasts`)**
  - [x] Create `app/admin/broadcasts/page.tsx` with list of broadcasts, status badges (Active, Scheduled, Expired, Inactive), Create/Edit Broadcast Modal (Title, Markdown Message, Banner Type, Target Workspaces, Date Pickers, Dismissible toggle), and toggle/delete actions.
  - [x] Add navigation link in `app/admin/admin-shell.tsx`.
- [x] **Task 9: In-App Broadcast Banner Component**
  - [x] Create `components/broadcasts/BroadcastBanner.tsx` supporting markdown formatting, alert styles per `banner_type`, and dismiss state persistence in `localStorage` (`nowing:dismissed_broadcasts`; note this is browser-scoped).
  - [x] Mount `BroadcastBanner` inside `app/dashboard/dashboard-shell.tsx` and `app/admin/admin-shell.tsx` (client components), not in the RSC `layout.tsx` files.

### Testing & Quality Gates

- [x] **Task 10: Backend Unit & Integration Tests**
  - [x] `tests/unit/services/test_admin_audit_log_service.py` (query filters, pagination, User joins for email resolution).
  - [x] `tests/unit/services/test_admin_dnc_service.py` (HMAC canonicalization, CSV import parser, Redis set sync, audit logging).
  - [x] `tests/unit/services/test_broadcast_service.py` (active window evaluation, workspace targeting filter, validation).
  - [x] `tests/integration/routes/test_admin_audit_logs.py` (superuser guard, query params, PAT 403).
  - [x] `tests/integration/routes/test_admin_dnc.py` (superuser guard, single add, CSV bulk import, delete, Redis cache sync, audit event persistence).
  - [x] `tests/integration/routes/test_admin_broadcasts.py` (superuser guard, CRUD, active broadcast filter).
- [x] **Task 11: Frontend Playwright E2E Tests**
  - [x] `tests/admin/audit-logs.spec.ts` (renders audit timeline, applies action filter, opens diff drawer).
  - [x] `tests/admin/dnc.spec.ts` (adds global phone/domain blacklist, imports CSV, displays masked entry, deletes entry).
  - [x] `tests/admin/broadcasts.spec.ts` (creates announcement banner, verifies active banner rendering and dismissal).

---

## Dev Agent Guardrails & Technical Architecture Requirements

### File Structure Requirements

```
nowing_backend/
├── alembic/versions/
│   └── <generated>_add_broadcast_announcements_table.py  # NEW: generate from current head
├── app/
│   ├── db.py                                      # UPDATE: Add BroadcastAnnouncement model
│   ├── zero_publication.py                        # UPDATE: Register broadcast_announcements table
│   ├── celery_app.py                              # UPDATE: Add broadcast status/expiration Beat schedule
│   ├── schemas/
│   │   ├── admin_audit_logs.py                    # NEW: AuditActionEnum, AuditEventRead, AuditEventListResponse
│   │   ├── admin_dnc.py                           # NEW: GlobalDncRecordCreate, GlobalDncCsvImportResponse
│   │   └── broadcasts.py                          # NEW: BroadcastCreate, BroadcastUpdate, BroadcastRead
│   ├── services/
│   │   ├── admin_audit_log_service.py             # NEW: outerjoin User queries
│   │   ├── admin_dnc_service.py                   # NEW: canonicalize, HMAC, CSV import, Redis cache invalidation
│   │   └── broadcast_service.py                   # NEW: CRUD + target workspace filter + derived status
│   ├── routes/
│   │   ├── __init__.py                            # UPDATE: include new admin/public routers
│   │   ├── admin_audit_logs_routes.py             # NEW: GET /api/v1/admin/audit-logs
│   │   ├── admin_dnc_routes.py                    # NEW: /api/v1/admin/dnc/global*
│   │   ├── admin_broadcasts_routes.py             # NEW: /api/v1/admin/broadcasts*
│   │   └── broadcasts_routes.py                   # NEW: GET /api/v1/broadcasts/active
│   └── tasks/celery_tasks/
│       └── broadcast_tasks.py                     # NEW: expire/refresh broadcast status
└── tests/
    ├── unit/services/
    │   ├── test_admin_audit_log_service.py        # NEW
    │   ├── test_admin_dnc_service.py              # NEW
    │   └── test_broadcast_service.py              # NEW
    └── integration/routes/
        ├── test_admin_audit_logs.py               # NEW
        ├── test_admin_dnc.py                      # NEW
        └── test_admin_broadcasts.py               # NEW

nowing_web/
├── app/
│   ├── admin/
│   │   ├── admin-shell.tsx                        # UPDATE: Add Audit Logs, DNC, Broadcasts nav links + BroadcastBanner
│   │   ├── audit-logs/page.tsx                    # NEW: Timeline table, filters, diff drawer, CSV export
│   │   ├── dnc/page.tsx                           # NEW: Global DNC table, single add & CSV upload modal
│   │   └── broadcasts/page.tsx                    # NEW: Broadcast table, create/edit modal
│   └── dashboard/
│       └── dashboard-shell.tsx                    # UPDATE: Mount BroadcastBanner
├── components/
│   └── broadcasts/
│       └── BroadcastBanner.tsx                    # NEW: Top banner component with localStorage dismissal
├── contracts/types/
│   ├── admin-audit-logs.types.ts                  # NEW
│   ├── admin-dnc.types.ts                         # NEW
│   └── broadcasts.types.ts                        # NEW
├── lib/
│   ├── apis/
│   │   ├── admin-audit-logs-api.service.ts        # NEW
│   │   ├── admin-dnc-api.service.ts               # NEW
│   │   └── broadcasts-api.service.ts              # NEW
│   └── hooks/
│       └── use-broadcast-announcements.ts         # NEW: Zero subscription with REST fallback
└── tests/admin/
    ├── audit-logs.spec.ts                         # NEW
    ├── dnc.spec.ts                                # NEW
    └── broadcasts.spec.ts                         # NEW
```

---

## Architectural Invariants & Learned Best Practices

1. **Fail-Closed Superadmin Guard (`INV-25.8`):**
   - Every `/api/v1/admin/*` endpoint MUST depend on `get_current_active_superuser` or `require_superuser` (checking `User.is_superuser == True`).
   - Personal Access Tokens (PAT) MUST be rejected with HTTP 403 / 401 fail-closed.
2. **Immutable Dual-Principal Audit Logging (`INV-25.2`):**
   - Every state-altering admin action (adding/removing DNC, creating/updating/deleting broadcasts) MUST insert an `AuditEvent` with `actor_id` (current admin user UUID), `subject_id` (optional target user UUID only), `action`, `ip_address`, `user_agent`, `endpoint`, and `diff_payload`. `endpoint` must be recorded in `diff_payload.endpoint` (or a dedicated `endpoint` column if a follow-up migration is added).
   - Never update or delete rows from `audit_events`.
3. **PII Hash Canonicalization & Vault Security (`AD-110`):**
   - All Global DNC phone numbers MUST be normalized to E.164 (`+84...`) before hashing with `HMAC-SHA256(canonical_value, config.SECRET_KEY)` using the existing `app.lead_intelligence.dnc.normalizer` helpers.
   - Domains and emails MUST be lowercased and stripped before hashing.
   - Raw phone numbers and sensitive PII are never logged in plain text in `audit_events.diff_payload` — only masked display strings (e.g. `0908 *** 456`) and the HMAC hash.
4. **Playwright E2E Mocking Conventions (Learned from 25.5):**
   - Use glob patterns (e.g. `**/api/v1/admin/audit-logs*`) rather than exact relative paths so requests to `http://localhost:8000` are intercepted cleanly.
   - Provide explicit CORS headers (`Access-Control-Allow-Origin: http://localhost:3000`, `Access-Control-Allow-Credentials: true`) on all route fulfillment helpers.
   - Always mock `**/zero/context*` and `**/users/me*` with valid UUID v4 format (`11111111-1111-4111-8111-111111111111`) to prevent TanStack Query / Zod schema validation errors.

## Verification Commands

Run these after implementation and before marking the story `done`:

**Backend (from `nowing_backend/`):**

```bash
ruff check app/db.py app/routes/admin_*.py app/routes/broadcasts_routes.py app/services/admin_*.py app/services/broadcast_service.py app/schemas/admin_*.py app/schemas/broadcasts.py app/tasks/celery_tasks/broadcast_tasks.py
ruff format app/db.py app/routes/admin_*.py app/routes/broadcasts_routes.py app/services/admin_*.py app/services/broadcast_service.py app/schemas/admin_*.py app/schemas/broadcasts.py app/tasks/celery_tasks/broadcast_tasks.py
uv run pytest tests/unit/services/test_admin_audit_log_service.py tests/unit/services/test_admin_dnc_service.py tests/unit/services/test_broadcast_service.py -q
uv run pytest tests/integration/routes/test_admin_audit_logs.py tests/integration/routes/test_admin_dnc.py tests/integration/routes/test_admin_broadcasts.py -q
uv run pytest tests/integration/test_pat_fail_closed_authz.py -q
uv run python -c "from app.app import app; print('app import OK')"
```

**Frontend (from `nowing_web/`):**

```bash
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/audit-logs app/admin/dnc app/admin/broadcasts app/admin/admin-shell.tsx app/dashboard/dashboard-shell.tsx components/broadcasts lib/apis/admin-audit-logs-api.service.ts lib/apis/admin-dnc-api.service.ts lib/apis/broadcasts-api.service.ts lib/hooks/use-broadcast-announcements.ts contracts/types/admin-audit-logs.types.ts contracts/types/admin-dnc.types.ts contracts/types/broadcasts.types.ts
pnpm test:e2e tests/admin/audit-logs.spec.ts tests/admin/dnc.spec.ts tests/admin/broadcasts.spec.ts
```

**Integration smoke (requires `docker compose -f docker/docker-compose.deps-only.yml up -d db redis`):**

```bash
cd nowing_backend
uv run alembic upgrade head
uv run pytest tests/integration/routes/test_admin_audit_logs.py tests/integration/routes/test_admin_dnc.py tests/integration/routes/test_admin_broadcasts.py -q
```

## PRD / FR Traceability

This story satisfies:

- `INV-25.2` — Dual-principal audit integrity (every admin action logged with `actor_id`, `subject_id`, `ip_address`, `user_agent`, `endpoint`, `diff_payload`).
- `INV-25.8` — Fail-closed superadmin guard and PAT/impersonation rejection via `require_superuser`.
- `AD-110` — PII opt-out / global DNC blacklist using canonicalized HMAC and existing `DncComplianceService` cache.
- Epic 25 acceptance criteria for the platform administration console (`/admin/audit-logs`, `/admin/dnc`, `/admin/broadcasts`) and in-app broadcast banner.

## Challenge Log

- **C1:** `AuditEvent` has no `endpoint` column. **Resolution:** record `endpoint` in `diff_payload.endpoint` for all new admin actions; a follow-up migration can add a dedicated column later.
- **C2:** `broadcast_announcements` must be queried by `workspace_id IN JSONB` without a full table scan. **Resolution:** add a GIN index on `target_workspace_ids` and use `func.jsonb_exists` / equivalent Postgres containment operator.
- **C3:** Current alembic head is a merge (`9a32642d01df`) from `233` and `b5cf13c425fb`. **Resolution:** generate a new Alembic revision from `head`; do not hardcode `234_`.
- **C4:** Existing `AuditEvent.action` strings are mixed lowercase dot-separated values. **Resolution:** `AuditActionEnum` is a Pydantic convenience, but the service and database accept/return the actual stored strings.
- **C5:** The public broadcast endpoint must work for any logged-in user, not only superadmins. **Resolution:** use `get_auth_context` for `GET /api/v1/broadcasts/active` and accept `workspace_id` query param.

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Global DNC cache not invalidated on admin add/delete/import | PII opt-out not honored; legal/compliance risk | Always call `DncComplianceService.invalidate_global_cache()` and verify with `DncComplianceService.is_blocked()` in integration tests |
| `BroadcastBanner` mounted in RSC layout file | SSR / hydration error or no state | Mount only in client shells (`admin-shell.tsx`, `dashboard-shell.tsx`) |
| New admin routers not included in `app/routes/__init__.py` | All admin endpoints return 404 | Include routers and run `uv run python -c "from app.app import app; print('ok')"` |
| `target_workspace_ids` JSONB query implemented incorrectly | Wrong users see banners, or targeted banners hidden | Integration test `test_admin_broadcasts.py` covers `target_all=true` and specific workspace IDs |
| `AuditEvent` missing `endpoint` / `ip_address` / `user_agent` | Compliance gap | Add `endpoint` to `diff_payload` and capture `request.client.host` + `request.headers.get("user-agent")` in every admin route |

## Quality Gates

- [ ] All `/api/v1/admin/*` routes return expected shapes and `403` for non-superuser, PAT, and impersonated sessions.
- [ ] `broadcast_announcements` table and migration are created from current alembic head with UUID PK, JSONB `target_workspace_ids`, GIN index, and active-window index.
- [ ] `AuditEvent` records contain `actor_id`, `action`, `ip_address`, `user_agent`, and `endpoint` in `diff_payload`; immutable; no updates/deletes.
- [ ] `DncComplianceService.invalidate_global_cache()` is called on DNC add/delete/import; global DNC blocks matching contacts within one `is_blocked` call.
- [ ] `BroadcastBanner` mounts in `admin-shell.tsx` and `dashboard-shell.tsx`, supports dismissal, and unmounts on expiry/deactivation.
- [ ] Playwright E2E tests for `audit-logs`, `dnc`, and `broadcasts` pass.
- [ ] `ruff`, `pytest` (unit + integration), `tsc --noEmit`, and `biome check` are green.

## Validation Findings (resolved and applied on 2026-08-26)

**Date:** 2026-08-26

**Status:** `ready-for-dev` — the critical/major issues below were corrected in the story body above.

**Method:** Manual `bmad-create-story` checklist against `epics.md`, `ARCHITECTURE-SPINE.md`, `app/db.py`, `app/users.py`, existing admin routes, DNC service, and frontend shell patterns.

### Critical — must fix before dev

1. **Router wiring location is wrong.** The story repeatedly says "Wire router into `app/app.py`" and only lists `app/app.py` in the file structure. In this codebase new routers are imported and `router.include_router(...)` is done in `app/routes/__init__.py`; `app/app.py` only mounts the consolidated `crud_router`. If a dev edits `app/app.py` directly, the new admin routes will not be reachable under `/api/v1/admin/*`.
   - *Fix:* Add `from .admin_audit_logs_routes import router as admin_audit_logs_router` (and the other three admin routers) and `router.include_router(admin_audit_logs_router)` in `app/routes/__init__.py`.

2. **Broadcast banner mount points are Server Components.** The story says "Mount `BroadcastBanner` in `app/dashboard/layout.tsx` (and `app/admin/layout.tsx`)`. Both are RSCs and cannot run the client hooks/state needed for the banner. The actual mount points are `app/dashboard/dashboard-shell.tsx` and `app/admin/admin-shell.tsx` (both are already client components). Admin nav links must also be added in `app/admin/admin-shell.tsx`.

3. **`BroadcastAnnouncement` model description will not compile.** "UUID primary key, ... TimestampMixin" is insufficient. `BaseModel` provides an *integer* `id`; a UUID model must inherit from `Base` and declare `id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`. `TimestampMixin` only provides `created_at`; the model must explicitly add `updated_at` and `created_by_user_id` (FK to `user.id` with `ondelete="SET NULL"`). Because `PATCH` is allowed, `updated_by_user_id` is also recommended.
   - *Fix:* Expand Task 1 and the file structure with the exact model columns and inheritance.

4. **Hardcoded migration file name conflicts with current alembic head.** The story prescribes `alembic/versions/234_add_broadcast_announcements_table.py`. The current head is a merge `9a32642d01df` that merges `233` and `b5cf13c425fb`; no numeric `234_` file exists. A hardcoded `234` will not sit on the current head and may create a new branch.
   - *Fix:* Instruct the dev to run `cd nowing_backend && uv run alembic revision --autogenerate -m "add broadcast announcements table"` against current `head`, then edit the generated revision to add UUID PK, JSONB, and GIN/indexes.

5. **DNC HMAC key and Redis key names are wrong.** The story says `PII_HMAC_KEY` and `nowing:dnc:global:{record_type}`. The existing `DncComplianceService` and normalizer use `config.SECRET_KEY` and `dnc:global:{record_type}`. Using a different key or Redis key will break global DNC lookups across the platform.
   - *Fix:* Use `config.SECRET_KEY` for HMAC and call `DncComplianceService(secret_key=config.SECRET_KEY).invalidate_global_cache()` after add/delete/import.

6. **Audit action enum contains values that do not match existing code.** Existing `AuditEvent.action` strings are `user.impersonate_start`, `user.impersonate_exit`, `scraper_rule.create/activate/delete/trip/reset`, `manual_credit_quota_exceeded`. The story lists `SCRAPER_RULE_UPDATED` and `TELEMETRY_PURGE_DLQ`, which do not exist, and implies a unified `AuditActionEnum` that will miss existing events unless the dev updates every service or the enum is permissive.
   - *Fix:* Define the enum with the actual existing strings (or a validated `str` with examples) and add new 25.6 actions such as `global_dnc.add`, `global_dnc.remove`, `broadcast.create`, `broadcast.update`, `broadcast.delete`, `audit_log.view`. Remove `TELEMETRY_PURGE_DLQ` unless the telemetry purge endpoint is also updated to write an `AuditEvent`.

7. **`AuditEvent` model does not have an `endpoint` column.** `INV-25.2` requires endpoint logging, but `AuditEvent` only has `ip_address`, `user_agent`, and `diff_payload`. Either add a nullable `endpoint` column (new migration) or explicitly record `endpoint` inside `diff_payload` for every admin action.
   - *Fix:* Add `endpoint` to `AuditEvent.diff_payload` in route/service helpers, or create a follow-up migration `add_endpoint_to_audit_events.py`.

8. **Zero publication for broadcasts is incomplete without a client hook.** Registering `broadcast_announcements` in `app/zero_publication.py` gives CDC, but the AC-4 claim of "real-time reactivity" needs a frontend Zero hook (or documented polling fallback). The story only describes a REST fallback.
   - *Fix:* Add a `useBroadcastAnnouncements` hook that subscribes via Zero when available and falls back to the REST endpoint, or change AC-4 to "poll every 60s".

### Major — should fix

9. **Public broadcast endpoint needs workspace targeting and non-superuser auth.** `GET /api/v1/broadcasts/active` is for all logged-in users (not superadmin) and must apply `target_workspace_ids` against the user's current workspace. The story does not specify how the route obtains `workspace_id` (query param? header?) and whether PAT/impersonation is rejected.
   - *Fix:* Use `get_auth_context`, accept `workspace_id` query param, and return only rows where `target_all=true` or `workspace_id in target_workspace_ids`.

10. **`target_workspace_ids` JSONB query pattern is not specified.** Postgres containment for `current_workspace_id IN target_workspace_ids` requires `jsonb_exists` or a `func.jsonb_array_contains` helper; the story should call it out so the active query is correct.

11. **`AuditEvent.subject_id` is a `user.id` foreign key.** The AC says `subject_id` can be a "workspace entity", but the DB column is `UUID` FK to `user.id`. For non-user targets (DNC record, broadcast) `subject_id` must be `None` and the entity id placed in `diff_payload`. `AuditEventRead.subject_email` will be `None` for those rows; this should be explicit.

12. **CSV import response shape should match existing DNC convention.** Existing `DncCsvImportResponse` uses `imported_count/skipped_count/failed_count/errors`. The story proposes `{ total_processed, added_count, skipped_count }`. Align with the existing schema to reuse types and tests.

13. **`/api/v1/admin/dnc/global` payload field name `raw_value` should be `value`.** Existing `DncRecordCreate` uses `value`; reusing `normalize_*` and `compute_*_hmac` helpers from `app.lead_intelligence.dnc.normalizer` is simpler if the field name matches.

14. **Missing verification commands and standard story sections.** The story has no `Verification Commands`, `PRD/FR Traceability`, `Challenge Log`, `Risk Register`, or `Quality Gates` sections expected by `nowing-quality-pipeline.md` for `ready-for-dev` stories.
    - *Suggested backend verification:*
      ```bash
      ruff check app/db.py app/routes/admin_*.py app/services/admin_*.py app/services/broadcast_service.py app/schemas/admin_*.py app/schemas/broadcasts.py app/tasks/broadcast_tasks.py
      ruff format ...
      uv run pytest tests/unit/services/test_admin_audit_log_service.py tests/unit/services/test_admin_dnc_service.py tests/unit/services/test_broadcast_service.py -q
      uv run pytest tests/integration/routes/test_admin_audit_logs.py tests/integration/routes/test_admin_dnc.py tests/integration/routes/test_admin_broadcasts.py -q
      uv run python -c "from app.app import app; print('app import OK')"
      ```
    - *Suggested frontend verification:*
      ```bash
      pnpm tsc --noEmit
      pnpm exec biome check --max-diagnostics 500 app/admin/audit-logs app/admin/dnc app/admin/broadcasts app/admin/admin-shell.tsx app/dashboard/dashboard-shell.tsx components/broadcasts lib/apis/admin-audit-logs-api.service.ts lib/apis/admin-dnc-api.service.ts lib/apis/broadcasts-api.service.ts contracts/types/admin-audit-logs.types.ts contracts/types/admin-dnc.types.ts contracts/types/broadcasts.types.ts
      pnpm test:e2e tests/admin/audit-logs.spec.ts tests/admin/dnc.spec.ts tests/admin/broadcasts.spec.ts
      ```

### Minor / polish

15. `broadcast_announcements` should add a GIN index on `target_workspace_ids` and an index on `created_by_user_id` in addition to the `(is_active, starts_at, expires_at)` index.
16. `banner_type` and status-derived fields should be `String(20)` with Pydantic `Literal`/`StrEnum`, matching existing model conventions.
17. The existing `nowing_web/lib/announcements/announcements-data.ts` static marketing announcements should be left untouched; the new `BroadcastBanner` is a separate platform-wide admin tool.
18. The `localStorage` dismissal key `nowing:dismissed_broadcasts` is browser-wide, not user-scoped; note this as a known ceiling or scope per-user in the component.

### Verdict

**Conditional `ready-for-dev`.** The high-level scope is correct and the security invariants are mostly aligned, but the implementation map contains several file-path and data-model pitfalls. Apply the corrections above before moving the story to `in-progress`.

---

### ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-25-6-security-audit-trail-logs-and-in-app-broadcast-announcements.md`
- **Unit Tests:**
  - `nowing_backend/tests/unit/services/test_admin_audit_log_service.py`
  - `nowing_backend/tests/unit/services/test_admin_dnc_service.py`
  - `nowing_backend/tests/unit/services/test_broadcast_service.py`
- **Integration Tests:**
  - `nowing_backend/tests/integration/routes/test_admin_audit_logs.py`
  - `nowing_backend/tests/integration/routes/test_admin_dnc.py`
  - `nowing_backend/tests/integration/routes/test_admin_broadcasts.py`
- **E2E Tests:**
  - `nowing_web/tests/admin/audit-logs.spec.ts`
  - `nowing_web/tests/admin/dnc.spec.ts`
  - `nowing_web/tests/admin/broadcasts.spec.ts`

---

### Review Findings

- [x] [Review][Patch] Invalidate Redis Global DNC Cache after DB Commit to eliminate Stale Blacklist Cache Race Condition [`nowing_backend/app/routes/admin_dnc_routes.py:102`, `nowing_backend/app/services/admin_dnc_service.py:190`]
- [x] [Review][Patch] Add `apply_publication(op.get_bind())` in Alembic migration `c7a42e189d20` upgrade and downgrade [`nowing_backend/alembic/versions/c7a42e189d20_add_broadcast_announcements_table.py:25`]
- [x] [Review][Patch] Handle UTF-8 BOM (`\ufeff`), in-memory dedup, and 10MB file size cap in DNC CSV Import [`nowing_backend/app/routes/admin_dnc_routes.py:125`, `nowing_backend/app/services/admin_dnc_service.py:207`]
- [x] [Review][Patch] Unskip all Playwright E2E tests in `audit-logs.spec.ts`, `dnc.spec.ts`, and `broadcasts.spec.ts` [`nowing_web/tests/admin/`]
- [x] [Review][Patch] Add Date Range Picker (`startDate`, `endDate`) to `/admin/audit-logs` UI Filter Bar [`nowing_web/app/admin/audit-logs/page.tsx:150`]
- [x] [Review][Patch] Push `target_workspace_ids` JSONB filtering into SQL query in `BroadcastService.get_active_broadcasts` [`nowing_backend/app/services/broadcast_service.py:255`]
- [x] [Review][Patch] Validate `expires_at > starts_at` and `target_all=False` non-empty workspaces [`nowing_backend/app/services/broadcast_service.py:108`, `nowing_backend/app/schemas/broadcasts.py`]
- [x] [Review][Patch] Fix phone normalizer `+840...` and tax ID minimum length validation [`nowing_backend/app/lead_intelligence/dnc/normalizer.py:44`, `138`]
- [x] [Review][Patch] Guard `useBroadcastAnnouncements` against corrupted non-array `localStorage` JSON [`nowing_web/lib/hooks/use-broadcast-announcements.ts:15`]
- [x] [Review][Patch] Ensure event loop safety in `expire_broadcast_announcements_task` [`nowing_backend/app/tasks/celery_tasks/broadcast_tasks.py:43`]

#### Re-triage 2026-08-27 (all three review layers completed)

Three review layers completed: acceptance auditor, blind hunter, edge case hunter.
Full reports are in:

- `_bmad-output/test-artifacts/review-25.6-chunk1-acceptance-auditor-findings.md`
- `_bmad-output/test-artifacts/review-25.6-chunk1-blind-hunter-findings.md`
- `_bmad-output/test-artifacts/review-25.6-chunk1-edge-case-hunter-findings.md`

**Decision needed**

- [x] [Review][Decision] `AuditEvent.id` type: **use `int`** (`AuditEventRead.id: int`). This matches the existing `Integer` PK in `audit_events` and the `IDModel` convention in `app/schemas/base.py`; avoids a migration. Critical. [`app/schemas/admin_audit_logs.py:38`]
- [x] [Review][Decision] Audit CSV/JSON export: **client-side only**. The admin UI already renders an `Export CSV` button that builds a CSV Blob from the loaded page; no backend streaming endpoint is required for v1. Medium. [`nowing_web/app/admin/audit-logs/page.tsx:19-56`]
- [x] [Review][Decision] `audit_log.view`: **emit the event**. Viewing the immutable audit trail is a sensitive superadmin access to user data, and `INV-25.2` requires logging admin actions on user data. Low. [`app/schemas/admin_audit_logs.py:30`, `app/routes/admin_audit_logs_routes.py:24-69`]

**Patch**

- [x] [Review][Patch] Fix the broadcast expiry Celery task: remove the non-existent `get_async_session_context` import and the `nest_asyncio` loop hack; use the canonical `get_celery_session_maker()` + `run_async_celery_task()` helpers; write an `AuditEvent` for expired banners; do not swallow all exceptions. Critical. [`app/tasks/celery_tasks/broadcast_tasks.py:1-56`, `app/celery_app.py:237,370-374`]
- [x] [Review][Patch] Add a `user_id` property to `AuthContext` (returns `self.user.id`) so `auth.user_id` works in the new admin routes and in existing `app/routes/leads_routes.py`. Critical. [`app/auth/context.py:35-41`, `app/routes/admin_dnc_routes.py:98,142,170`, `app/routes/admin_broadcasts_routes.py:80,136,192`]
- [x] [Review][Patch] Resolve `AuditEventRead.id` type to match the database primary key so `/api/v1/admin/audit-logs` does not fail Pydantic validation. Critical. [`app/schemas/admin_audit_logs.py:38`]
- [x] [Review][Patch] Remove cache invalidation calls from inside `AdminDncService`; keep invalidation only after `session.commit()` in the routes to avoid a stale-cache race. High. [`app/services/admin_dnc_service.py:191,306,350`, `app/routes/admin_dnc_routes.py:103-105,147-149,179-181`]
- [x] [Review][Patch] Harden `GET /api/v1/broadcasts/active`: switch to `require_session_context`, reject PATs, and verify the requested `workspace_id` is in the calling user's workspace memberships. High. [`app/routes/broadcasts_routes.py:22-46`]
- [x] [Review][Patch] Fix `BroadcastService.get_active_broadcasts` JSONB workspace query: drop the dead `str(workspace_id)` branch and rely on a single `.contains([workspace_id])` against the integer array. High. [`app/services/broadcast_service.py:280-289`]
- [x] [Review][Patch] DNC single-add duplicate handling: when an existing record is updated, emit `global_dnc.update` with an `old`/`new` diff; emit `global_dnc.add` only for new records. High. [`app/services/admin_dnc_service.py:142-186`, `app/schemas/admin_audit_logs.py:25-30`]
- [x] [Review][Patch] DNC CSV import: replace N+1 select/insert with a bulk `insert(...).on_conflict_do_nothing()` using the `uq_global_dnc_entry` unique constraint; validate headers; skip blank rows; bound file/row size; and do not return raw PII in error strings. High. [`app/services/admin_dnc_service.py:200-314`, `app/routes/admin_dnc_routes.py:118-135`]
- [x] [Review][Patch] Capture the real client IP in new admin routes by using `app.rate_limiter.get_real_client_ip(request)` instead of `request.client.host`. Medium. [`app/routes/admin_dnc_routes.py:38-42`, `app/routes/admin_broadcasts_routes.py:28-32`]
- [x] [Review][Patch] Add `max_length` to `BroadcastCreate.message` and `BroadcastUpdate.message` to prevent multi-megabyte banners and audit-log bloat. Medium. [`app/schemas/broadcasts.py:19,33`]
- [x] [Review][Patch] Add `AuditEvent` logging inside the broadcast expiry Celery task and fix the `is_active`/`expired` status boundary. Medium. [`app/tasks/celery_tasks/broadcast_tasks.py:20-36`, `app/services/broadcast_service.py:25-51`]
- [x] [Review][Patch] `BroadcastService.compute_status` should return `expired` when `expires_at <= now` even if `is_active` is already `False`; align the active query and the Celery task on the same `<=` boundary. Medium. [`app/services/broadcast_service.py:44-50`, `:271-278`, `broadcast_tasks.py:24-27`]
- [x] [Review][Patch] Allow `update_broadcast` to clear `starts_at` and `expires_at` with explicit `null` values; currently `v is not None` silently ignores them. Medium. [`app/services/broadcast_service.py:198-209`, `app/schemas/broadcasts.py:37-38`]
- [x] [Review][Patch] Normalize/validate broadcast datetimes to avoid `TypeError` from naive/aware comparisons and catch `TypeError` (not just `ValueError`) in the admin routes. Medium. [`app/services/broadcast_service.py:121-124`, `:196-209`, `app/routes/admin_broadcasts_routes.py:109-113,169-173`]
- [x] [Review][Patch] Validate admin audit-log date filters: require timezone-aware datetimes and enforce `start_date <= end_date`. Low. [`app/routes/admin_audit_logs_routes.py:46-51`, `app/services/admin_audit_log_service.py:53-56`]
- [x] [Review][Patch] Validate `target_workspace_ids` values: positive integers, deduplicate, cap list size, and validate existence regardless of `target_all`. Low. [`app/schemas/broadcasts.py:22,36`, `app/services/broadcast_service.py:108-125,181-197`]
- [x] [Review][Patch] Mask domain values in `GlobalDncRecordRead` for display while preserving the raw canonical value in the DB for `DncComplianceService.is_blocked()`. Low. [`app/schemas/admin_dnc.py`, `app/services/admin_dnc_service.py:28-51`]
- [x] [Review][Patch] Extend the phone normalizer to strip the redundant leading `0` after `840` for 9–10 digit inputs, not only 11–12. Low. [`app/lead_intelligence/dnc/normalizer.py:42-46`]

**Defer**

- [x] [Review][Defer] `normalize_domain` mis-parses URLs containing userinfo or ports (e.g. `http://user:pass@example.com:8080/path` becomes `user`). This is a pre-existing bug in `dnc/normalizer.py` that is not in this diff; fix it in a follow-up. Low. [`app/lead_intelligence/dnc/normalizer.py:85-99`]

**Dismiss**

- DNC CSV all-failed / all-duplicate imports producing no `AuditEvent` is acceptable when no database state changes.
- `UploadFile.read(max_size + 1)` raises `413` when the file exceeds 10 MB; it does not silently truncate valid uploads.


