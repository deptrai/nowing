---
baseline_commit: "470b5a95c"
status: done
---

# Story 18.1: Public Agent-Chat Endpoints

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

## Developer Context

### Epic 18 Context

Epic 18 "Vertical Client Platform (Public Agent-Chat)" provides a public API surface so external vertical clients (first: BDS AI) can run specialized agents against a Nowing workspace with PAT auth, hard tenant isolation, cost attribution and rate limits. It was split from Epic 13 during SCP 2026-08-08 and does **not** depend on canonical entity storage. Tenant isolation is enforced via `client_id` tags on existing `Memory` / `ResearchThread` / `Run` / `TokenUsage` / `new_chat_threads` tables per AD-31, not canonical storage.

Epic 18 entry criteria (all required and accepted 2026-08-07):
- AD-29, AD-30, AD-31 accepted on Architecture Spine.
- PAT scope model, composite RLS (`workspace_id` + `client_id`) and threat model test plan published.

All Epic 18 stories are `ready-for-dev`:
- 18.1 Public Agent-Chat Endpoints (this story)
- 18.2 NewChatRequest Extension
- 18.3 Agent Registry
- 18.4 AgentConfig Prompt Injection
- 18.5 ResearchThread Auto-Linkage
- 18.6 Memory Tagging + RAG Filter
- 18.7 Cost Traceability
- 18.8 Rate Limiting + Tenant Isolation

### Architecture Decisions — Must Follow

**AD-29 — Public Agent-Chat Surface** (`ARCHITECTURE-SPINE.md:727-737`)
- Public routes live under `/api/v1/workspaces/{workspace_id}/agent-chat/...` and are explicitly allowlisted. Internal web chat routes stay internal.
- Auth is PAT (or equivalent machine credential) with server-enforced scopes. Client-supplied IDs cannot escalate beyond token scope.
- Every request sets transaction-local DB context for workspace (`app.workspace_id`) and, when present, vertical client (`app.current_client_id`) **before** any business query.
- Rate limit per workspace and per client; exceed → `429` + `Retry-After`.
- Responses carry `X-Run-Id` for cost/audit. `external_metadata` on TokenUsage/Run is additive and untrusted for authorization.
- Security review required before enabling in production.

**AD-30 — AgentConfig Registry** (`ARCHITECTURE-SPINE.md:739-748`)
- `agent_configs` stores named agents: identity, `system_instructions`, tool allow/deny lists, model preference, citations flag, active flag.
- Missing/inactive `agent_id` → fail closed (`404`), never silently fall through.
- Tool allowlists are explicit. New connectors do not auto-enable.

**AD-31 — Vertical Client Tenancy (`client_id`)** (`ARCHITECTURE-SPINE.md:750-764`)
- `client_id` is a **hard isolation key orthogonal to `workspace_id`**. Workspace membership alone is insufficient.
- Tables carrying vertical-client data gain nullable `client_id` (NULL = Nowing-internal / web app).
- Recall and list paths hard-filter:
  - request with `client_id=X` → only rows with `client_id=X`
  - request without `client_id` → only rows with `client_id IS NULL`
- Never use `client_id` as ranking boost.
- Composite policy order: authenticate → authorize workspace → set workspace RLS context → authorize client scope → set client RLS context → run query.

**AD-13 — Research Thread Continuation Context** (`ARCHITECTURE-SPINE.md:274-282`)
- `ResearchThread` links 1-n `NewChatThread` via `new_chat_threads.research_thread_id`.
- Public/vertical agent-chat may create and link `ResearchThread` instances, but only through the AD-29 public surface.

### PAT Scope Model (from `epic-18-pat-scope-rls-threat-model.md` §2)

**Scope object (MVP):**
```text
PatScope {
  workspace_id: int          # single workspace FK
  client_id:  string | null  # null = no vertical client (legacy/internal)
  agent_id:   string | null  # optional pin to one agent
  scopes:     string[]       # permission strings
}
```

**Schema delta for `personal_access_tokens`:**
| Column | Type | Notes |
|---|---|---|
| `workspace_id` | `Integer NULL FK workspaces.id` | NULL = legacy unscoped |
| `client_id` | `Text NULL` | stable string matching `vertical_clients.client_id` |
| `agent_id` | `Text NULL` | optional pin |
| `scopes` | `JSONB NOT NULL DEFAULT '[]'` | permission strings |
| `token_kind` | `Text NOT NULL DEFAULT 'legacy'` | `legacy` \| `agent_chat` |

**Check constraints:**
- `token_kind = 'agent_chat'` ⇒ `workspace_id IS NOT NULL AND client_id IS NOT NULL AND scopes <> '[]'`
- `agent_id IS NOT NULL` ⇒ `client_id IS NOT NULL`

**Indexes:** `(workspace_id)`, `(client_id)`, `(token_kind)`

**Permission vocabulary (MVP):**
| Permission | Allows |
|---|---|
| `agent_chat:thread:create` | `POST .../agent-chat/threads` |
| `agent_chat:message:create` | `POST .../threads/{id}/messages` |
| `agent_chat:thread:read` | `GET` thread/messages if exposed |
| `agent_chat:run:read` | correlate `X-Run-Id` / run status if exposed |

**Mint request example:**
```json
{
  "label": "bdsai-prod",
  "expires_in_days": 90,
  "token_kind": "agent_chat",
  "workspace_id": 42,
  "client_id": "bdsai.vn",
  "agent_id": "bdsai-listing-assistant",
  "scopes": [
    "agent_chat:thread:create",
    "agent_chat:message:create",
    "agent_chat:thread:read"
  ]
}
```

Server validation at mint:
1. Caller is workspace Owner (or permission to manage integrations/API keys).
2. `client_id` exists in `vertical_clients` (or allowlisted seed).
3. If `agent_id` set → row exists, `is_active`, and `agent.client_id == body.client_id`.
4. Scopes ⊆ catalog; reject unknown strings.
5. Plaintext token shown once.

### Authorization Algorithm (9-step, fixed order)

```text
1. Authenticate
   - Bearer nw_pat_* → resolve_pat → AuthContext.pat_auth
   - else 401
2. Classify route
   - Must be on public agent-chat allowlist prefix
   - else if PAT: 403
3. Authorize workspace
   - path.workspace_id must equal pat.workspace_id
   - user must still be active member of that workspace (membership revoked ⇒ 403)
4. Authorize client scope
   - effective_client_id := request.client_id or pat.client_id
   - If request.client_id present and ≠ pat.client_id → 403 (no escalation)
   - If pat.client_id set and request omits client_id → bind to pat.client_id
5. Authorize agent scope
   - Load AgentConfig by agent_id (body or pat default)
   - missing/inactive → 404 (AD-30 fail closed)
   - agent.client_id must equal effective_client_id
   - if pat.agent_id set and ≠ requested → 403
6. Authorize permission
   - required permission for route ∈ pat.scopes
7. Set DB transaction context (before any business query)
   - set_config('app.workspace_id', workspace_id, true)
   - set_config('app.current_client_id', client_id, true)
   - optional: set_config('app.current_agent_id', agent_id, true)
8. Rate limit (workspace + client keys) → 429 + Retry-After
9. Execute handler; emit X-Run-Id; audit row (no message body)
```

### Untrusted Fields

| Client sends | Server uses |
|---|---|
| `workspace_id` in path | Must match PAT; never taken from body alone |
| `client_id` in body | Intersected with PAT; cannot widen |
| `agent_id` in body | Intersected with PAT + registry |
| `external_metadata` | Stored for attribution only; **never** used in authz/RLS |
| `platform_metadata` | Prompt context only; untrusted |

### Composite RLS Policy Shape (MVP)

```sql
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories FORCE ROW LEVEL SECURITY;

CREATE POLICY memories_tenant_isolation ON memories
  USING (
    workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::int
    AND (
      -- vertical request: hard match
      (
        NULLIF(current_setting('app.current_client_id', true), '') IS NOT NULL
        AND client_id = current_setting('app.current_client_id', true)
      )
      OR
      -- internal request: only NULL client rows
      (
        NULLIF(current_setting('app.current_client_id', true), '') IS NULL
        AND client_id IS NULL
      )
    )
  )
  WITH CHECK ( /* same predicate */ );
```

### Threat Model Summary (from `epic-18-pat-scope-rls-threat-model.md` §5)

| ID | Threat | Mitigation | Verify |
|---|---|---|---|
| TM1 | PAT leakage | Single-workspace+client scoped PAT; expiry; revoke; short TTL | H3, H10 |
| TM2 | Cross-workspace access | Path workspace must equal PAT; membership check | H2, H9 |
| TM3 | Cross-client memory recall | Composite RLS + hard filter; no ranking boost | R1–R3, T1 |
| TM4 | Client_id escalation in body | Intersect with PAT; RLS WITH CHECK | H5, R5 |
| TM5 | Agent escalation | Registry load fail-closed; PAT agent pin; tool allowlist | H6–H8, T2 |
| TM6 | Prompt injection → tool abuse | Tool allowlist enforced in runtime not prompt | T2–T3 |
| TM7 | Prompt injection → exfil via answer | Only tools/data in scope of WS+client | T1, T4 |
| TM8 | Prompt injection → instruction override | system_instructions admin-only; no secret interpolation | review 18.4 |
| TM9 | external_metadata authz confusion | Metadata never read by authz/RLS | U7 |
| TM10 | Rate abuse / cost DoS | Per WS + per client limits; billable path metering | A1–A2 |
| TM11 | Log/PII leakage | Default no message bodies in logs | A3–A4 |
| TM12 | Pool GUC bleed | SET LOCAL only; L3 tests | P1–P4 |
| TM13 | Inactive agent / deleted client still callable | 404 inactive; client is_active check | H8 |
| TM14 | Session cookie on public route | Public surface PAT-only (recommend) | H11 |
| TM15 | Model returns connector secrets | Secrets never in tool results; env only | review |

### Open Decisions — Resolved Defaults

| ID | Decision | Default |
|---|---|---|
| D1 | Multi-workspace PAT arrays vs single FK | **Single `workspace_id` FK** for MVP |
| D2 | Public routes session-allowed? | **PAT-only** on public surface |
| D3 | Empty GUC vs unset for internal client | **Set empty string every request** via `SET LOCAL` |
| D4 | Canonical data shared across clients in one WS? | **Yes shared**; use separate WS for hard split |
| D5 | RBAC permission name to mint agent_chat PAT | **Workspace Owner** |

## Technical Requirements

### 1. Database migrations

Create Alembic migration(s):
- Add `workspace_id`, `client_id`, `agent_id`, `scopes`, `token_kind` to `personal_access_tokens`.
- Add check constraints and indexes.
- Add `client_id` column to `new_chat_threads` and `research_threads` (or accept follow-up migrations by Stories 18.5/18.6/18.8; do not block 18.1 on those).
- Create `vertical_clients` table if it does not exist:
  - `id` UUID PK
  - `client_id` CITEXT UNIQUE NOT NULL
  - `display_name` TEXT NOT NULL
  - `is_active` BOOL NOT NULL DEFAULT true
  - `created_at` / `updated_at`
- Create `agent_configs` table if it does not exist (or coordinate with Story 18.3):
  - `id` UUID PK
  - `client_id` CITEXT NOT NULL (FK or validated string)
  - `name` / `slug` TEXT NOT NULL
  - `system_instructions` TEXT
  - `enabled_tools` JSONB
  - `disabled_tools` JSONB
  - `model_name` TEXT
  - `citations_enabled` BOOL DEFAULT false
  - `is_active` BOOL DEFAULT true

### 2. Extend PAT schema and mint endpoint

`app/schemas/pat.py`:
- `PATCreate`: add `token_kind`, `workspace_id`, `client_id`, `agent_id`, `scopes`.
- `PATCreated` / `PATRead`: add the same fields (except plaintext `token` only in `PATCreated`).

`app/routes/personal_access_tokens_routes.py`:
- Extend `create_personal_access_token` to accept and validate new fields.
- Validate workspace membership, `client_id`, `agent_id`, and scope catalog.
- Keep session-only minting.

### 3. Create `app/schemas/agent_chat.py`

Request/response schemas:
- `AgentChatThreadCreate`: `agent_id` (optional), `client_id` (optional), `platform_metadata` (optional dict).
- `AgentChatMessageCreate`: `content` (str), `external_metadata` (optional dict).
- `AgentChatThreadRead`: `thread_id`, `research_thread_id`.
- `AgentChatMessageResponse`: stream-oriented or structured assistant response; include `X-Run-Id` header.
- `AgentChatError`: `detail`, `code`.

### 4. Create `app/routes/agent_chat_routes.py`

Endpoints:
- `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads`
- `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages`

Both endpoints:
- Use a new `require_agent_chat_pat` dependency.
- Validate `AGENT_CHAT_PUBLIC_ENABLED` feature flag; if disabled, return 503.
- Run the 9-step authorization algorithm.
- Set DB GUCs before any business query.
- Apply rate limits.
- For `threads`: create `NewChatThread` with `source='agent_chat'`, bind to `workspace_id` and `client_id`, create/link `ResearchThread`, return IDs and `X-Run-Id`.
- For `messages`: map to internal `NewChatRequest` with `agent_id`, `client_id`, `platform_metadata`, stream response, return SSE or JSON with `X-Run-Id`.
- On timeout/unavailability return 503 with `Retry-After` or structured `partial` frame.

### 5. Create `app/auth/agent_chat.py`

New FastAPI dependency `require_agent_chat_pat`:
- Calls `get_auth_context` then enforces:
  - `auth.method == 'pat'`
  - `auth.pat.token_kind == 'agent_chat'`
  - route on allowlist
  - workspace match
  - membership still active
  - client/agent scope intersection
  - permission in `pat.scopes`
- Sets GUCs via helper from `app/canonical/tenant_context.py` extended for `client_id`.
- Returns an enriched auth context with `effective_client_id`, `effective_agent_id`.

### 6. Extend tenant context helper

`app/canonical/tenant_context.py`:
- Add `set_request_tenant_context(session, workspace_id, client_id, agent_id=None)`.
- Must use `set_config(..., true)` (transaction-local, `SET LOCAL`).
- Must set `app.workspace_id`, `app.current_client_id`, optional `app.current_agent_id`.

### 7. Integrate chat runtime

`app/tasks/chat/streaming/flows/__init__.py` / `new_chat.py`:
- Call `stream_new_chat` / `stream_resume_chat` with:
  - `workspace_id`
  - `chat_id`
  - `user_id` (PAT owner's user id as string)
  - `user_query` (from message content)
  - `agent_id` (effective agent)
  - `client_id` (effective client)
  - `platform_metadata`
  - `auth_context`
  - `mode` (default suitable for agent-chat)
  - `client_platform='api'`
- Map `AgentChatMessageCreate` to `NewChatRequest` with `agent_id`, `client_id`, `platform_metadata`.

### 8. Rate limiting

`app/rate_limiter.py` or route decorators:
- Add per-workspace and per-client Redis key functions.
- Return `429` with `Retry-After` header when exceeded.
- Default conservative public limit (e.g. `30/minute` per client, `100/minute` per workspace).

### 9. Audit and observability

`app/services/agent_chat/audit.py`:
- Log: actor_user_id, pat_id, workspace_id, client_id, agent_id, route, HTTP status, run_id.
- Do not log message bodies.

`app/observability/metrics.py`:
- Add `agent_chat_public_calls` counter with bounded labels: workspace_id, client_id, agent_id, route, status.

### 10. Feature flag

`app/config/__init__.py`:
- Add `AGENT_CHAT_PUBLIC_ENABLED = os.getenv("AGENT_CHAT_PUBLIC_ENABLED", "FALSE").upper() == "TRUE"`.

### 11. Backward compatibility

- Legacy unscoped PATs continue to work on existing allowlisted non-public PAT routes.
- Legacy unscoped PATs on `/agent-chat/*` must return 403 with `pat_scope_required`.

### Review Findings (2026-08-09)

#### Patch

- [x] [Review][Patch] Schema type for `agent_configs` / `vertical_clients` should match spec (CITEXT/UUID) instead of Text/Integer — `alembic/versions/78f7a9b1e85f_public_agent_chat_scope.py`, `app/db.py`
  - Spec calls for `vertical_clients.client_id CITEXT UNIQUE` and `agent_configs.id UUID PK`, `agent_configs.client_id CITEXT`. Migration and ORM currently use `Text` / `Integer` (via `BaseModel.id`).
- [x] [Review][Patch] Add tenant isolation at DB layer (RLS composite policy for `client_id`) — `alembic/versions/78f7a9b1e85f_public_agent_chat_scope.py`
  - AD-31 requires hard client_id filtering. Current code filters at the application layer; no `CREATE POLICY` / `ENABLE ROW LEVEL SECURITY` in migration.
- [x] [Review][Patch] HTTP status for "agent exists but not for this client" should be 404 (not 403) to match AC-5 — `app/auth/agent_chat.py:84-87`
  - AC-5 says "404 ... for valid agent_id not allowed for this client_id". Code returns 403; 403 reveals the agent exists.
- [x] [Review][Patch] Add and validate `agent_chat:*` scope catalog when minting PAT — `app/auth/agent_chat.py:188-193`, `app/routes/personal_access_tokens_routes.py`
  - Current code only checks `required_scope in pat.scopes`. If a PAT can be minted/inserted with arbitrary strings, it bypasses intent.
- [x] [Review][Patch] Feature flag defaults to enabled (`"true"`) instead of `False` until security review is green — `app/config/__init__.py:689-691`
- [x] [Review][Patch] Rate limiting is not implemented; routes have no per-workspace/per-client 429 + Retry-After — `app/routes/agent_chat_routes.py`, `app/rate_limiter.py`
  - AC-9 / AD-29 require this. Only a unit test fakes a 429 response.
- [x] [Review][Patch] PAT schema and mint endpoint not extended for `token_kind`, `workspace_id`, `client_id`, `agent_id`, `scopes` — `app/schemas/pat.py`, `app/routes/personal_access_tokens_routes.py`
  - Technical Requirement §2 is unimplemented. Scoped PATs cannot be created through the API.
- [x] [Review][Patch] `AgentChatThreadCreate.agent_id` / `client_id` should be optional and fall back to PAT scope — `app/schemas/agent_chat.py:11-16`
  - Spec says optional; schema marks them required. Body values are still intersected with PAT scope, so making them optional is safe and matches intent.
- [x] [Review][Patch] `send_message` thread lookup should include `workspace_id` and `client_id` in the `WHERE` clause — `app/routes/agent_chat_routes.py:213-215`
  - Defense in depth; current code filters after the fetch and relies on a second comparison.
- [x] [Review][Patch] `stream_new_chat` generator only catches `TimeoutError`; other exceptions return 500 instead of 503/partial frame — `app/routes/agent_chat_routes.py:163-179`
  - AC-7 / Technical Requirement §4 require graceful handling of timeout or unavailability, not 500.
- [x] [Review][Patch] Error detail `f"invalid credentials: {exc}"` can leak internal exception text — `app/auth/agent_chat.py:136-139`
  - Replace with a generic message and log the exception server-side.
- [x] [Review][Patch] Audit does not cover auth/dependency-level rejections (403/429/401/503) — `app/auth/agent_chat.py`, `app/routes/agent_chat_routes.py`
  - AC-11 says every public call must be audited. Dependency failures currently bypass `log_public_call`.
- [x] [Review][Patch] Metric route label is high-cardinality (`request.url.path` contains `thread_id`) — `app/routes/agent_chat_routes.py:135`, `app/observability/metrics.py`
  - Use a route template to avoid cardinality explosion.
- [x] [Review][Patch] `workspace_id` fallback to `request.query_params` is unnecessary and ambiguous — `app/auth/agent_chat.py:155-157`
  - Path parameter is always present for these routes; remove query fallback.
- [x] [Review][Patch] Add format/length validation for `client_id` and `agent_id` (slug-like) and bound `platform_metadata`/`external_metadata` — `app/schemas/agent_chat.py`, `app/auth/agent_chat.py`
  - Prevents oversized payloads and malformed identifiers reaching SQL/LLM layers.

#### Defer

- [x] [Review][Defer] `GET /threads/{thread_id}` / `agent_chat:thread:read` endpoint — `app/routes/agent_chat_routes.py`
  - Not in 18.1 ACs; permission vocabulary hints at future scope. Defer to 18.4+.

## File Structure

### Files to Create

| File | Purpose |
|---|---|
| `nowing_backend/app/routes/agent_chat_routes.py` | Public agent-chat endpoints |
| `nowing_backend/app/schemas/agent_chat.py` | Public request/response schemas |
| `nowing_backend/app/auth/agent_chat.py` | Scoped PAT authorization dependency |
| `nowing_backend/app/services/agent_chat/audit.py` | Audit logging |
| `nowing_backend/app/middleware/tenant_context.py` | Request-level tenant context helper (shared with 18.8) |
| `nowing_backend/tests/unit/auth/test_pat_scope.py` | PAT scope unit tests |
| `nowing_backend/tests/integration/api/test_agent_chat_pat_matrix.py` | HTTP/PAT matrix H1-H12 |
| `nowing_backend/tests/integration/rls/test_composite_client_rls.py` | Composite RLS L2 tests |
| `nowing_backend/tests/integration/pool/test_tenant_guc_reset.py` | Pool GUC reset L3 tests |
| `nowing_backend/alembic/versions/..._agent_chat_pat_scope.py` | Migration for PAT scope + vertical_clients |

### Files to Modify

| File | What to Change | What to Preserve |
|---|---|---|
| `nowing_backend/app/db.py:3276-3303` | Add `workspace_id`, `client_id`, `agent_id`, `scopes`, `token_kind` to `PersonalAccessToken`; add `client_id` to `NewChatThread` / `ResearchThread` if not deferred | Existing `is_expired`/`is_valid` properties; token hashing behavior |
| `nowing_backend/app/schemas/pat.py` | Add scope fields to `PATCreate`/`PATCreated`/`PATRead` | Existing `ConfigDict(from_attributes=True)` |
| `nowing_backend/app/routes/personal_access_tokens_routes.py:42-66` | Accept/validate scope fields; enforce workspace owner check; validate client/agent | Session-only minting; plaintext once |
| `nowing_backend/app/routes/__init__.py:125` | Include `agent_chat_router` | Existing router order |
| `nowing_backend/app/schemas/new_chat.py:234-313` | Add `agent_id`, `client_id`, `platform_metadata` (or coordinate with Story 18.2) | Existing frontend request shape |
| `nowing_backend/app/users.py:330-361` | No direct changes; `resolve_pat` already loads `PersonalAccessToken`; ensure it loads new scope columns | Existing auth resolution flow |
| `nowing_backend/app/utils/pat.py:36-52` | No direct changes; new columns load via ORM | Token validation logic |
| `nowing_backend/app/auth/context.py` | No direct changes; `AuthContext.pat` already holds `PersonalAccessToken` | Frozen dataclass pattern |
| `nowing_backend/app/utils/rbac.py:177-192` | Add scope validation in `_enforce_api_access_gate` or new `check_agent_chat_scope` | Existing `api_access_enabled` check |
| `nowing_backend/app/canonical/tenant_context.py` | Extend `set_canonical_workspace_id` to also set `client_id` and `agent_id` | `SET LOCAL` pattern; `session.info` marker |
| `nowing_backend/app/rate_limiter.py:29-35` | Add per-workspace/per-client key funcs for public agent-chat | Existing limiter config |
| `nowing_backend/app/tasks/chat/streaming/flows/__init__.py` | Possibly re-export or add wrapper | Existing entry points |
| `nowing_backend/app/observability/metrics.py` | Add `agent_chat_public_calls` counter | Existing metric functions |
| `nowing_backend/app/config/__init__.py` | Add `AGENT_CHAT_PUBLIC_ENABLED` | Existing env parsing patterns |

### Current State of Key Files

- `app/db.py`: `PersonalAccessToken` has only `user_id`, `token_hash`, `token_prefix`, `label`, `expires_at`, `last_used_at` (no scope columns). `NewChatThread` has `workspace_id`, `created_by_id`, `research_thread_id`, no `client_id`.
- `app/schemas/pat.py`: `PATCreate` only has `label`, `expires_in_days`.
- `app/routes/personal_access_tokens_routes.py`: session-only creation, simple token generation.
- `app/canonical/tenant_context.py`: sets only `app.workspace_id` via `set_config(..., true)`.
- `app/users.py`: `get_auth_context` resolves PAT via `resolve_pat` and returns `AuthContext.pat_auth`.
- `app/utils/rbac.py`: `_enforce_api_access_gate` checks `workspace.api_access_enabled` for gated auth; no scope checking.
- `app/rate_limiter.py`: SlowAPI limiter with IP-based default key; default 1024/minute.
- `app/routes/new_chat_routes.py:1694-1809`: reference pattern for POST chat route using `get_auth_context`, `check_permission`, `stream_new_chat`, `StreamingResponse`.
- No `agent_chat_routes.py`, `agent_chat.py` schemas, `app/auth/agent_chat.py`, or `app/services/agent_chat/audit.py` exist.
- No `vertical_clients` table; no `agent_configs` table.

## Detected Conflicts or Variances

1. `client_id` name collision: existing OAuth connector flows use `client_id` for third-party OAuth credentials. In Epic 18, `client_id` means vertical client. Use `vertical_clients.client_id` (stable string) and avoid confusing it with OAuth `client_id` in connector code.
2. `NewChatThread` currently has `source='nowing'` default. Agent-chat threads should use `source='agent_chat'`.
3. `PersonalAccessToken` currently has no scope columns. Legacy tokens must keep working on non-public PAT routes but be rejected on `/agent-chat/*`.
4. `NewChatRequest` (Story 18.2) does not yet have `agent_id`, `client_id`, `platform_metadata`. Story 18.1 and 18.2 must coordinate: 18.1 may temporarily extend the schema or implement a minimal mapping pending 18.2.
5. `ResearchThread` and `new_chat_threads` lack `client_id` columns; these may be added by Stories 18.5/18.6/18.8. Story 18.1 should either add them now or clearly defer and document the dependency.
6. `AgentConfig` registry (Story 18.3) does not exist. For 18.1, either stub a minimal `agent_configs` table or clearly mark that agent validation is a hard dependency on 18.3.

## Testing Requirements

### Unit Tests

`tests/unit/auth/test_pat_scope.py`:
- Scope intersection: request client_id ≠ pat client_id → 403.
- Request client_id omitted and pat client_id set → binds to pat client_id.
- pat.agent_id set and request agent_id differs → 403.
- Legacy `token_kind='legacy'` on `/agent-chat/*` → 403 `pat_scope_required`.
- Missing permission → 403.

### Integration Tests

`tests/integration/api/test_agent_chat_pat_matrix.py` (H1-H12):
| ID | Auth | Call | Expect |
|---|---|---|---|
| H1 | PAT_bds (agent_chat, WS1, client bds) | create thread on WS1 | 201 |
| H2 | PAT_bds | create thread on WS2 | 403 |
| H3 | PAT_legacy | create thread on WS1 | 403 `pat_scope_required` |
| H4 | none | create thread | 401 |
| H5 | PAT_bds | message + body client_id=hr | 403 |
| H6 | PAT_bds | message + agent_id=A_hr | 403/404 |
| H7 | PAT_bds_any_agent | agent_id=A_bds active | 200 |
| H8 | PAT_bds | agent_id=A_bds inactive | 404 |
| H9 | PAT_bds | owner removed from WS1 | 403 |
| H10 | PAT_bds expired | any | 401 |
| H11 | Session cookie | public agent-chat | 401/403 |
| H12 | PAT_bds | internal `/new_chat` if still gated | existing allowlist test still green |

`tests/integration/rls/test_composite_client_rls.py` (L2):
- client_id=X sees only X rows.
- internal (NULL client_id) sees only NULL rows.
- no OR-widening.

`tests/integration/pool/test_tenant_guc_reset.py` (L3):
- After `rollback()`, context is cleared.
- New request re-sets GUCs before query.

### End-to-End / Security

- `tests/e2e` or integration: rate limit 429, 503 timeout/partial frame, audit log sink verification.
- Security review checklist §5.6 before production enablement.

## Dependencies

### Story 18.1 depends on:
- **18.8** — composite RLS + tenant context helper (GUC setting). Must be implemented or at least designed enough for 18.1 to use.
- **18.2** — `NewChatRequest` extension with `agent_id`, `client_id`, `platform_metadata`.
- **18.3** — `agent_configs` table/registry to validate `agent_id`.

### Stories that depend on 18.1:
- **18.4** — needs public endpoints to call agent runtime.
- **18.5** — needs public endpoints to create and link `ResearchThread`.
- **18.6** — needs public endpoints to set `client_id` on memories.
- **18.7** — needs `X-Run-Id` header from public endpoints.

### Implementation Order Recommendation

For a clean build, implement in this order:
1. **18.8** — tenant isolation foundation (GUC helper, composite RLS, `vertical_clients`).
2. **18.3** — `agent_configs` table (or stub for 18.1).
3. **18.2** — `NewChatRequest` extension.
4. **18.1** — public endpoints (this story).
5. **18.4, 18.5, 18.6, 18.7** — parallel after 18.1.

If Story 18.1 must ship first, stub the minimal `agent_configs` and `vertical_clients` tables, extend `NewChatRequest` locally, and clearly document follow-up in 18.2/18.3.

## Dev Agent Guardrails

- **NEVER** accept client-supplied `workspace_id`, `client_id`, or `agent_id` as authoritative. Always intersect with PAT scope.
- **NEVER** use `external_metadata` or `platform_metadata` in authorization or RLS.
- **NEVER** use `client_id` as a ranking boost.
- **NEVER** allow legacy unscoped PAT on `/agent-chat/*`. Return 403 `pat_scope_required`.
- **ALWAYS** set `app.workspace_id` and `app.current_client_id` via `SET LOCAL` before any business query.
- **ALWAYS** return `X-Run-Id` header on success and `Retry-After` on 429/503.
- **ALWAYS** fail closed (404) on missing/inactive `agent_id`.
- **ALWAYS** keep public routes separate from internal web chat routes.
- **ALWAYS** leave `AGENT_CHAT_PUBLIC_ENABLED` default `False` until security checklist is green.
- **ALWAYS** preserve legacy PAT behavior on non-public routes.

## Project Context Reference

- Project: Nowing
- Stack: Python 3.12, FastAPI, SQLAlchemy 2.x async, PostgreSQL 15+ with pgvector, Alembic, Pydantic v2, SlowAPI limiter, Redis, LangGraph chat runtime.
- Conventions:
  - Use `from __future__ import annotations`.
  - Use `AsyncSession` with `select`/`await session.execute`.
  - Use Pydantic v2 `BaseModel`, `ConfigDict(from_attributes=True)`.
  - Use FastAPI `APIRouter`, `Depends`, `HTTPException`.
  - Use Alembic migrations for schema changes.
  - Follow existing `app/routes/` pattern for router registration in `app/routes/__init__.py`.
  - Tests in `tests/unit/` and `tests/integration/`, use `pytest.mark.asyncio` and `pytest.mark.integration`.

## References

- `_bmad-output/planning-artifacts/epics.md` §Story 18.1
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-30, AD-31, AD-13
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §2, §2.6, §2.7, §4.5, §5
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-56, NFR-MULTI-1
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-public-agent-chat-api.md`
- `nowing_backend/app/db.py` §PersonalAccessToken, NewChatThread, ResearchThread
- `nowing_backend/app/schemas/pat.py`
- `nowing_backend/app/schemas/new_chat.py` §NewChatRequest
- `nowing_backend/app/users.py` §get_auth_context
- `nowing_backend/app/utils/pat.py` §resolve_pat
- `nowing_backend/app/utils/rbac.py` §_enforce_api_access_gate
- `nowing_backend/app/canonical/tenant_context.py`
- `nowing_backend/app/rate_limiter.py`
- `nowing_backend/app/routes/new_chat_routes.py` §handle_new_chat
- `nowing_backend/app/routes/personal_access_tokens_routes.py`
- `nowing_backend/app/routes/__init__.py`

## Previous Story Intelligence

- Recent commit patterns in repo show feature/story-based commits with conventional prefixes (`feat:`, `test:`, `fix:`).
- Story 12.2 (TopCV Scraper) added extensive unit tests and mutation-killing patterns; apply similar test discipline.
- No Epic 18 code reviews exist yet; this story will set the pattern for 18.2-18.8.

## Git Intelligence

- No Epic 18 implementation has landed on `develop` yet.
- Existing `PersonalAccessToken` has no scope columns; `client_id` is unused in DB; `agent_configs` table does not exist.
- Existing public chat (`app/routes/public_chat_routes.py`) is snapshot/sharing read-only, not agent-chat write surface. Do not conflate the two.

## Latest Tech Information

- FastAPI 0.115+, Pydantic 2.12+, SQLAlchemy 2.0.35+ (verify `pyproject.toml`).
- SlowAPI limiter with Redis storage; per-workspace/per-client keys may require custom `key_func` (see `limits` library docs if needed).
- PostgreSQL `SET LOCAL` is transaction-scoped and clears on commit/rollback, which is the desired GUC isolation for pooled connections.

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List

## Story Completion Status

- [x] Epic and story context analyzed
- [x] Architecture, PRD, UX, and threat model reviewed
- [x] Existing code files inspected
- [x] Dependencies and implementation order documented
- [x] Open decisions resolved with defaults
- [x] Comprehensive developer context and guardrails captured
- [ ] Implementation pending
- [ ] Tests pending

**Status:** done

**Ultimate context engine analysis completed - comprehensive developer guide created.**
