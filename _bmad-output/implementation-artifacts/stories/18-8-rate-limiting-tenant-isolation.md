# Story 18.8: Rate Limiting + Tenant Isolation

Status: ready-for-dev

## Story

As a platform,
I want to enforce rate limits per workspace and per client,
so that no single client can degrade service for others.

## Acceptance Criteria

1. **Given** a public chat endpoint is called, **When** rate limit is exceeded, **Then** 429 is returned with `Retry-After` header.
2. **Given** a PAT is validated, **When** the request is processed, **Then** PostgreSQL RLS context is set (`SET LOCAL app.current_client_id`).
3. **Given** RLS is active, **When** any query runs, **Then** rows are filtered by `client_id` automatically.

## Tasks / Subtasks

- [ ] Per-workspace / per-client rate limiting (AC: #1)
  - [ ] Extend `app/rate_limiter.py:29-35` with a key function for public agent-chat: `f"agent-chat:ws:{workspace_id}:client:{client_id}"` + workspace ceiling key `f"agent-chat:ws:{workspace_id}"`
  - [ ] Add per-route limits in `app/routes/agent_chat_routes.py` using `@limiter.limit(...)` or route dependencies
  - [ ] Return `429` with `Retry-After` header (FastAPI `HTTPException` with `headers={"Retry-After": "<seconds>"}`)
  - [ ] Add `AGENT_CHAT_RATE_LIMIT_RPM` and `AGENT_CHAT_WORKSPACE_RATE_LIMIT_RPM` config in `app/config/__init__.py`
  - [ ] Emit metric `agent_chat_rate_limited` with workspace/client labels (bounded)
- [ ] Tenant context middleware (AC: #2)
  - [ ] Create `app/middleware/tenant_context.py` with `set_request_tenant_context(session, workspace_id, client_id, agent_id=None)`
  - [ ] Implement `SELECT set_config('app.workspace_id', :w, true)`, `SELECT set_config('app.current_client_id', :c, true)`, and optional `app.current_agent_id`
  - [ ] Use empty string for `client_id` when unset (internal chat) per `epic-18-pat-scope-rls-threat-model.md §3.2` decision D3
  - [ ] Apply `set_request_tenant_context` at the start of every public agent-chat route and every chat route that may carry `client_id`
  - [ ] Ensure context is reset per request (pooled connection safety; `SET LOCAL` clears on commit/rollback per `app/canonical/tenant_context.py:17-31`)
- [ ] Composite RLS policies (AC: #3)
  - [ ] Add RLS policies for tables with `client_id`: `memories`, `new_chat_threads`, `research_threads`, `token_usage`, `runs`
  - [ ] Policy predicate (per `epic-18-pat-scope-rls-threat-model.md §3.3`):
    - `workspace_id = current_setting('app.workspace_id')::int`
    - AND (`current_client_id` set AND `client_id = current_client_id`) OR (`current_client_id` unset AND `client_id IS NULL`)
  - [ ] Use `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`
  - [ ] Create policies with `WITH CHECK` matching `USING` so inserts are also tenant-scoped
  - [ ] Grant `SELECT/INSERT/UPDATE/DELETE` to app role without `BYPASSRLS`
- [ ] Pool safety and context reset (AC: #2, #3)
  - [ ] Add `app/middleware/rls_context_middleware.py` as an ASGI-style middleware or FastAPI dependency that sets GUCs per request and re-sets after `rollback()`
  - [ ] Implement L3 test cases P1-P4 from `epic-18-pat-scope-rls-threat-model.md §4.6`: two sequential requests on pooled connection, exception mid-flight, Celery sequential tasks
- [ ] Route-level authz integration (AC: #2)
  - [ ] Update `app/auth/agent_chat.py` (Story 18.1) to call `set_request_tenant_context` after PAT/workspace/client authorization
  - [ ] Update `get_async_session` or route dependencies so that internal session chat sets `app.current_client_id` to empty string (no vertical client)
- [ ] Tests (L1, L2, L3, L5)
  - [ ] L0 unit tests for scope intersection and permission check in `tests/unit/auth/test_pat_scope.py`
  - [ ] L1 DB RLS integration tests `tests/integration/rls/test_composite_client_rls.py` cases R1-R10
  - [ ] L2 HTTP/PAT matrix in `tests/integration/api/test_agent_chat_pat_matrix.py` (H1-H12)
  - [ ] L3 pool safety tests in `tests/integration/pool/test_tenant_guc_reset.py` (P1-P4)
  - [ ] L5 rate-limit/audit tests in `tests/integration/agent/test_agent_chat_rate_audit.py` (A1-A5)

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-29` (`ARCHITECTURE-SPINE.md:727-737`) — public routes live under dedicated prefix; rate limit per workspace and per client; exceed → 429 + `Retry-After`; metrics low-cardinality; do not log full message bodies.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is a hard isolation key orthogonal to `workspace_id`; composite policy order: authenticate → authorize workspace → set workspace RLS → authorize client scope → set client RLS → run query.
  - `epic-18-pat-scope-rls-threat-model.md §3.2` — GUC `app.current_client_id` set with `set_config(..., is_local => true)`; empty string for internal chat; re-set after rollback.
  - `epic-18-pat-scope-rls-threat-model.md §3.3` — composite RLS policy shape; no OR-widening for partner traffic; no `client_id` ranking boost.
  - `epic-18-pat-scope-rls-threat-model.md §4.5` — L2 HTTP/PAT matrix H1-H12.
  - `epic-18-pat-scope-rls-threat-model.md §4.6` — L3 pooled connection context reset P1-P4.
  - `epic-18-pat-scope-rls-threat-model.md §4.8` — L5 rate limit & audit A1-A5.
  - `epic-18-pat-scope-rls-threat-model.md §5 TM10-TM14` — rate abuse, PII leakage, pool GUC bleed, inactive agent, session cookie on public route.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — RLS policy migration for `memories`, `new_chat_threads`, `research_threads`, `token_usage`, `runs`
  - `nowing_backend/app/middleware/tenant_context.py` — new tenant context helper
  - `nowing_backend/app/middleware/rls_context_middleware.py` — new request-scoped middleware
  - `nowing_backend/app/canonical/tenant_context.py:17-31` — existing `set_canonical_workspace_id` pattern
  - `nowing_backend/app/rate_limiter.py:29-35` — shared limiter
  - `nowing_backend/app/config/__init__.py` — rate limit config
  - `nowing_backend/app/routes/agent_chat_routes.py` — public routes + rate limits
  - `nowing_backend/app/routes/new_chat_routes.py` — internal chat may also set tenant context
  - `nowing_backend/app/auth/agent_chat.py` (Story 18.1) — authorization + GUC set
  - `nowing_backend/app/db.py` — add `client_id` to `new_chat_threads`, `research_threads`, `token_usage`, `runs`
  - `nowing_backend/app/observability/metrics.py` — rate-limited counter

- Testing standards summary
  - Unit tests in `tests/unit/auth/test_pat_scope.py` and `tests/unit/middleware/test_tenant_context.py`
  - L1 RLS integration in `tests/integration/rls/test_composite_client_rls.py`
  - L2 API integration in `tests/integration/api/test_agent_chat_pat_matrix.py`
  - L3 pool safety in `tests/integration/pool/test_tenant_guc_reset.py`
  - L5 rate/audit in `tests/integration/agent/test_agent_chat_rate_audit.py`
  - CI gate: L1 + L2 + L3 must pass before `epic-18` moves to `in-progress` or `review`.

### Project Structure Notes

- Alignment with unified project structure
  - Middleware for tenant context lives in `app/middleware/tenant_context.py`.
  - Rate limits are configured in `app/config/__init__.py` and enforced in route modules.

- Detected conflicts or variances
  - `app/canonical/tenant_context.py` already sets `app.workspace_id` for canonical entities; public agent-chat needs the same pattern for `app.current_client_id`.
  - `new_chat_threads` and `research_threads` currently have no `client_id` column; this story and 18.5/18.6/18.7 may share a single composite migration. Coordinate with Story 18.5.
  - `runs` and `token_usage` currently have `workspace_id` but no `client_id`; add columns and RLS policies.
  - Redis rate-limit key must not include free-form `external_metadata` or user messages; use bounded `workspace_id` + `client_id` only.
  - Session cookie must be rejected on public agent-chat routes (H11); implement via `require_agent_chat_pat` dependency.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.8]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-31]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §3.2 GUC, §3.3 Composite RLS, §4.5 L2 HTTP/PAT, §4.6 L3 Pool Safety, §4.8 L5 Rate/Audit, §5 TM10-TM14]
- [Source: `nowing_backend/app/rate_limiter.py` §Limiter]
- [Source: `nowing_backend/app/canonical/tenant_context.py` §set_canonical_workspace_id]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List