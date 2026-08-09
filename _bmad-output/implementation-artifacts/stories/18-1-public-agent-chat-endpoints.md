# Story 18.1: Public Agent-Chat Endpoints

Status: ready-for-dev

## Story

As a vertical client,
I want to create chat threads and send messages via public API,
so that I can integrate Nowing chat into my application.

## Acceptance Criteria

1. **Given** a valid PAT and workspace membership, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, **Then** a chat thread is created and returned with `thread_id` and `research_thread_id`.
2. **Given** a valid PAT, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called, **Then** the message is processed by the chat agent and a response is returned.
3. **Given** an invalid PAT or non-member, **When** any public endpoint is called, **Then** 401/403 is returned.
4. **Given** a request with a malformed JSON body or missing required fields (`workspace_id`, `message`), **When** processed, **Then** 422 is returned with field-level errors.
5. **Given** an invalid `agent_id` or a valid `agent_id` not allowed for this `client_id`, **When** processed, **Then** 404 is returned with a clear error message.
6. **Given** an invalid `client_id` (not in PAT scope or not registered for this workspace), **When** processed, **Then** 400 is returned.
7. **Given** a valid PAT, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called and the chat service times out or is unavailable, **Then** 503 is returned with `Retry-After` or a `partial` status frame, not 500.
8. **Given** a `client_id` in the request, **When** the chat processes, **Then** all data access is filtered by `client_id`.
9. **Given** rate limit is exceeded, **When** the endpoint is called, **Then** 429 is returned with `Retry-After` header.
10. **Given** a PAT is presented, **When** authorized, **Then** the token's allowed `workspace_id` (and optional `client_id`/`agent_id` scopes from AD-29) are enforced server-side; client-supplied IDs cannot escalate scope.
11. **Given** every public call, **When** completed or rejected, **Then** an audit log records actor, workspace, client, agent, route, status and run id without storing message PII bodies by default.

## Tasks / Subtasks

- [ ] Extend PAT schema for scoped public agent-chat (AC: #3, #10)
  - [ ] Add `workspace_id`, `client_id`, `agent_id`, `scopes`, `token_kind` columns to `personal_access_tokens` (`app/db.py:3276-3303`)
  - [ ] Update `PATCreate` / `PATCreated` / `PATRead` in `app/schemas/pat.py` and `app/routes/personal_access_tokens_routes.py:42-66`
  - [ ] Enforce check constraints: `token_kind='agent_chat'` ⇒ workspace_id + client_id + non-empty scopes; `agent_id` implies `client_id`
  - [ ] Index `(workspace_id)`, `(client_id)`, `(token_kind)`
- [ ] Create public agent-chat routes (AC: #1, #2, #4, #7, #9)
  - [ ] Create `app/routes/agent_chat_routes.py` with `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` and `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages`
  - [ ] Add request/response schemas in `app/schemas/agent_chat.py`: `AgentChatThreadCreate`, `AgentChatMessageCreate`, `AgentChatThreadRead` (with `research_thread_id`)
  - [ ] Wire router in `app/routes/__init__.py:125`
  - [ ] On chat timeout/unavailability return 503 + `Retry-After` or `partial` status frame (reuses `?mode=async` door from `AD-17`)
- [ ] Implement scoped PAT authorization (AC: #3, #5, #6, #8, #10)
  - [ ] Add `require_agent_chat_pat` dependency in `app/auth/agent_chat.py` that runs the §2.6 authorization algorithm from `epic-18-pat-scope-rls-threat-model.md`
  - [ ] Authenticate PAT via `resolve_pat` (`app/utils/pat.py:36-52`); reject legacy unscoped PAT on `/agent-chat/*` with 403 `pat_scope_required`
  - [ ] Intersect request `client_id`/`agent_id` with PAT scope; fail on escalation
  - [ ] Validate `AgentConfig` exists, is active, and `client_id` matches (fail-closed 404)
  - [ ] Set `app.workspace_id` and `app.current_client_id` GUCs via `set_request_tenant_context` before any business query
- [ ] Integrate with chat runtime (AC: #2)
  - [ ] Map public `AgentChatMessageCreate` to internal `NewChatRequest` (`app/schemas/new_chat.py:234-313`) with `agent_id`, `client_id`, `platform_metadata`
  - [ ] Call `stream_new_chat` / `stream_resume_chat` from `app/tasks/chat/streaming/flows/__init__.py` and return SSE or JSON response per `client_platform`
  - [ ] Return `X-Run-Id` header for cost/audit correlation
- [ ] Rate limiting and abuse guard (AC: #9)
  - [ ] Configure per-workspace and per-client Redis keys in `app/rate_limiter.py:29-35`
  - [ ] Add `@limiter.limit(...)` or middleware with `429` + `Retry-After` for public agent-chat prefix
  - [ ] Feature flag `AGENT_CHAT_PUBLIC_ENABLED` (default `False` until security checklist green)
- [ ] Audit and observability (AC: #11)
  - [ ] Add `app/services/agent_chat/audit.py` to log actor, workspace, client, agent, route, status, run_id, PAT id without message body
  - [ ] Add metrics counter `agent_chat_public_calls` with bounded labels
- [ ] Tests (must pass before production flag on)
  - [ ] Unit tests for scope intersection and permission validation (`tests/unit/auth/test_pat_scope.py`)
  - [ ] Integration tests for HTTP/PAT matrix H1-H12 (`tests/integration/api/test_agent_chat_pat_matrix.py`) from `epic-18-pat-scope-rls-threat-model.md §4.5`
  - [ ] Integration tests for rate-limit 429 and 503 timeout behavior

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-29` (public agent-chat surface, `ARCHITECTURE-SPINE.md:727-737`) requires PAT-only public routes, server-enforced scopes, rate limits, and `X-Run-Id`/`external_metadata` kept out of authz.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) requires composite RLS (`workspace_id` + `client_id`) and hard isolation — never use `client_id` as a ranking boost.
  - `AD-13` (`ARCHITECTURE-SPINE.md:274-282`) allows `ResearchThread` to be created/linked from public chat only under AD-29 guardrails.
  - `AD-30` (`ARCHITECTURE-SPINE.md:739-748`) requires `AgentConfig` to be loaded fail-closed and tool allowlists explicit.
  - PAT scope model and authorization algorithm are designed in `epic-18-pat-scope-rls-threat-model.md §2` (server-enforced scopes, §2.6 algorithm, §2.7 untrusted fields).
  - Threat model `epic-18-pat-scope-rls-threat-model.md §5` covers PAT leakage (TM1), cross-workspace (TM2), client escalation (TM4), agent escalation (TM5), rate abuse (TM10), and log/PII leakage (TM11).

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — migration for scoped `personal_access_tokens` columns and agent-chat indexes
  - `nowing_backend/app/db.py` — `PersonalAccessToken` model, `NewChatThread`, `ResearchThread`
  - `nowing_backend/app/schemas/pat.py` — `PATCreate`/`PATCreated`/`PATRead`
  - `nowing_backend/app/schemas/agent_chat.py` — new public request/response schemas
  - `nowing_backend/app/schemas/new_chat.py` — `NewChatRequest` extension (Story 18.2)
  - `nowing_backend/app/routes/personal_access_tokens_routes.py:42-66` — PAT mint endpoint
  - `nowing_backend/app/routes/agent_chat_routes.py` — new public routes
  - `nowing_backend/app/routes/__init__.py:125` — mount router
  - `nowing_backend/app/auth/context.py:12-38` — `AuthContext`
  - `nowing_backend/app/auth/agent_chat.py` — new scoped-PAT authorization dependency
  - `nowing_backend/app/users.py:330-361` — `get_auth_context` PAT resolution
  - `nowing_backend/app/utils/pat.py:36-52` — `resolve_pat`
  - `nowing_backend/app/utils/rbac.py:177-192` — `check_workspace_access`
  - `nowing_backend/app/canonical/tenant_context.py:17-31` — existing `set_canonical_workspace_id` pattern
  - `nowing_backend/app/middleware/tenant_context.py` (Story 18.8) — `set_request_tenant_context`
  - `nowing_backend/app/rate_limiter.py:29-35` — shared SlowAPI limiter
  - `nowing_backend/app/tasks/chat/streaming/flows/` — chat streaming entry points
  - `nowing_backend/app/observability/metrics.py` — agent-chat counters

- Testing standards summary
  - Unit tests in `tests/unit/auth/test_pat_scope.py`
  - Integration tests in `tests/integration/api/test_agent_chat_pat_matrix.py` implementing the H1-H12 matrix from `epic-18-pat-scope-rls-threat-model.md §4.5`
  - Integration tests for composite RLS L2 in `tests/integration/rls/test_composite_client_rls.py`
  - All L1-L3 tests green before `epic-18` moves past `ready-for-dev`.

### Project Structure Notes

- Alignment with unified project structure
  - Public agent-chat routes live in `app/routes/agent_chat_routes.py` and are mounted under `/api/v1/workspaces/{workspace_id}/agent-chat/...`
  - Authorization logic is a dedicated `app/auth/agent_chat.py` dependency, not mixed into `get_auth_context`
  - Tenant context helpers belong in `app/middleware/tenant_context.py` (shared with Story 18.8)

- Detected conflicts or variances
  - `PersonalAccessToken` currently has no scope columns (`app/db.py:3276-3303`) — this story adds them; legacy PATs must continue to work on non-public routes but be rejected on `/agent-chat/*`.
  - `NewChatThread`/`ResearchThread` currently have no `client_id` columns; these are added by Stories 18.5/18.6/18.8, so 18.1 migration should include `client_id` on `new_chat_threads` or accept a follow-up migration.
  - The internal chat runtime (`stream_new_chat`) expects `chat_id` and `user_query`; public endpoint must translate thread/message to internal request.
  - `AGENT_CHAT_PUBLIC_ENABLED` feature flag is required so production enablement can wait for security review.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.1]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-30, AD-31, AD-13]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §2 PAT Scope Model, §2.6 Algorithm, §2.7 Untrusted Fields, §4.5 HTTP/PAT Matrix, §5 Threat Model]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-56]
- [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-public-agent-chat-api.md`]
- [Source: `nowing_backend/app/db.py` §PersonalAccessToken, NewChatThread, ResearchThread]
- [Source: `nowing_backend/app/schemas/new_chat.py` §NewChatRequest]
- [Source: `nowing_backend/app/users.py` §get_auth_context, resolve_pat]
- [Source: `nowing_backend/app/rate_limiter.py` §Limiter]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List