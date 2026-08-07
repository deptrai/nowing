# Epic 18 Entry Gate — PAT Scope Model, Composite RLS Test Plan, Threat Model

**Status:** design-ready (gate item 3 of Epic 18 entry criteria)  
**Date:** 2026-08-07  
**Governs:** AD-29, AD-30, AD-31 · Stories 18.1–18.8  
**Baseline code:** `PersonalAccessToken` has **no scopes today** (`label`/`expires_at` only); `AuthContext.is_gated` marks PAT; public agent-chat does not exist yet.

---

## 1. Goals / Non-goals

### Goals
1. Machine credentials (PAT) can be **bound** to `workspace_id` (+ optional `client_id`, `agent_id`) so partner keys cannot escalate.
2. DB enforces **hard isolation** for vertical-client rows via composite context: `app.workspace_id` **and** `app.current_client_id`.
3. Test plan proves fail-closed behavior (including connection-pool context reset).
4. Threat model covers prompt injection + tool exfiltration before public enablement.

### Non-goals (this doc)
- Implementing migrations/routes (Stories 18.x).
- End-user workspace CRUD for agents (AD-30 MVP = platform superuser registry).
- Billing productization beyond attribution fields already planned in 18.7.

---

## 2. PAT Scope Model

### 2.1 Current state (verified)

| Surface | Behavior |
|--------|----------|
| `personal_access_tokens` | `user_id`, `token_hash`, `token_prefix`, `label`, `expires_at`, `last_used_at` — **no scope columns** |
| Mint API `POST /pats` | Session-only; body = `{label, expires_in_days?}` |
| Resolve | SHA-256 hash lookup; active user; non-expired |
| `AuthContext` | `method: session \| pat \| system`; `is_gated == (method == "pat")` |
| Gating | `require_session_context` rejects PAT; most interactive routes session-only |

Implication: today a PAT authenticates as **the user**, then every workspace the user can access is potentially reachable if a route accepts PAT. Epic 18 must not ship public agent-chat on that model.

### 2.2 Scope object (server-enforced)

A PAT carries a **scope grant** stored on the token row (not in the plaintext token string).

```text
PatScope {
  workspace_ids: int[] | "*"     # MVP: single workspace preferred; multi allowed for platform ops
  client_ids:    string[] | null # null = no vertical client (internal/legacy PAT)
  agent_ids:     string[] | null # null = any active agent for allowed clients (still subject to registry)
  permissions:   string[]        # see §2.4
}
```

**MVP recommendation (pilot BDS AI):**

| Field | MVP value | Rationale |
|------|-----------|-----------|
| `workspace_id` | **exactly one** required | Matches AD-29 "at minimum workspace_id"; simpler audit |
| `client_id` | **exactly one** required for public agent-chat PATs | Hard vertical isolation |
| `agent_ids` | optional allowlist; default = agents for that `client_id` that are `is_active` | Prevents calling a more powerful agent |
| `permissions` | fixed set for agent-chat PAT type | Least privilege |

Legacy PATs (no scope columns / null scope):
- Continue to work for **already-allowlisted** non-public PAT surfaces (if any).
- **Must not** authorize `/agent-chat/*` (fail closed: 403 `pat_scope_required`).

### 2.3 Schema delta (Story 18.1 / pre-18.1 migration)

Add to `personal_access_tokens` (names illustrative):

| Column | Type | Notes |
|--------|------|-------|
| `workspace_id` | `Integer NULL FK workspaces.id` | MVP single workspace; NULL = legacy unscoped |
| `client_id` | `Text NULL` | Stable string matching `vertical_clients.client_id` / agent_configs |
| `agent_id` | `Text NULL` | Optional pin to one agent name/slug |
| `scopes` | `JSONB NOT NULL DEFAULT '[]'` | Permission strings; empty = legacy |
| `token_kind` | `Text NOT NULL DEFAULT 'legacy'` | `legacy` \| `agent_chat` \| (future) |

Check constraints (DB):
- `token_kind = 'agent_chat'` ⇒ `workspace_id IS NOT NULL AND client_id IS NOT NULL AND scopes <> '[]'`
- `agent_id IS NOT NULL` ⇒ `client_id IS NOT NULL`

Indexes:
- `(workspace_id)`, `(client_id)`, `(token_kind)` for admin listing.

### 2.4 Permission vocabulary (MVP)

| Permission | Allows |
|------------|--------|
| `agent_chat:thread:create` | `POST .../agent-chat/threads` |
| `agent_chat:message:create` | `POST .../threads/{id}/messages` |
| `agent_chat:thread:read` | `GET` thread/messages (if exposed) |
| `agent_chat:run:read` | Correlate `X-Run-Id` / run status (if exposed) |

Explicitly **out of MVP PAT**:
- PAT mint/revoke
- Agent registry write
- Billing/admin
- Arbitrary scraper REST outside agent tool allowlist
- Memory admin CRUD outside chat-driven paths

### 2.5 Mint UX / API

Extend `PATCreate` (session-only):

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
1. Caller has workspace membership with permission to manage integrations/API keys (define exact RBAC key in 18.1; default **Owner**).
2. `client_id` exists in `vertical_clients` (or is allowlisted seed).
3. If `agent_id` set → row exists, `is_active`, and `agent.client_id == body.client_id`.
4. Scopes ⊆ catalog; reject unknown strings.
5. Never put secrets in `label`.

Response still shows plaintext **once**.

### 2.6 Request authorization algorithm (public agent-chat)

Order is fixed (AD-31 composite policy order):

```text
1. Authenticate
   - Bearer nw_pat_* → resolve_pat → AuthContext.pat_auth
   - else 401
2. Classify route
   - Must be on public agent-chat allowlist prefix
   - else if PAT: 403 (existing gated behavior / fail-closed allowlist test)
3. Authorize workspace
   - path.workspace_id must equal pat.workspace_id
   - user must still be active member of that workspace (membership revoked ⇒ 403 even if PAT unexpired)
4. Authorize client scope
   - Effective client_id := request.client_id or pat.client_id
   - If request.client_id present and ≠ pat.client_id → 403 (no escalation)
   - If pat.client_id set and request omits client_id → bind to pat.client_id (do not fall through to internal NULL scope)
5. Authorize agent scope
   - Load AgentConfig by agent_id (body or pat default)
   - missing/inactive → 404 (AD-30 fail closed)
   - agent.client_id must equal effective client_id
   - if pat.agent_id set and ≠ requested → 403
6. Authorize permission
   - required permission for route ∈ pat.scopes
7. Set DB transaction context (before any business query)
   - set_config('app.workspace_id', workspace_id, true)
   - set_config('app.current_client_id', client_id, true)
   - optional: set_config('app.current_agent_id', agent_id, true) for audit triggers
8. Rate limit (workspace + client keys) → 429 + Retry-After
9. Execute handler; emit X-Run-Id; audit row (no message body by default)
```

### 2.7 Client-supplied IDs are never authoritative

| Client sends | Server uses |
|--------------|-------------|
| `workspace_id` in path | Must match PAT; never taken from body alone |
| `client_id` in body | Intersected with PAT; cannot widen |
| `agent_id` in body | Intersected with PAT + registry |
| `external_metadata` | Stored for attribution only; **never** used in authz or RLS |
| `platform_metadata` | Prompt context only; untrusted (see threat model) |

### 2.8 Backward compatibility

| Caller | Behavior after change |
|--------|----------------------|
| Existing unscoped PAT on old allowlisted routes | Unchanged if route still accepts gated PAT |
| Unscoped PAT on `/agent-chat/*` | **403** `pat_scope_required` |
| Session user on internal chat | Unchanged; `client_id` context unset / NULL internal scope |
| Session superuser admin registry | Session-only (`require_superuser`) |

---

## 3. Vertical client representation (AD-31)

### 3.1 Decision (MVP)

Introduce first-class table:

```text
vertical_clients
  id              UUID PK
  client_id       CITEXT UNIQUE NOT NULL   -- e.g. "bdsai.vn"
  display_name    TEXT NOT NULL
  is_active       BOOL NOT NULL DEFAULT true
  created_at / updated_at
```

- `agent_configs.client_id` → FK/text match to `vertical_clients.client_id`
- Memory / Run / TokenUsage / ResearchThread (as needed) get nullable `client_id` text column + index `(workspace_id, client_id)`
- NULL `client_id` = Nowing-internal (web app session chat)

### 3.2 GUC / session variables

| GUC | Set by | Meaning |
|-----|--------|---------|
| `app.workspace_id` | existing canonical + general tenant helpers | Workspace RLS |
| `app.current_client_id` | new helper `set_vertical_client_id(session, client_id \| None)` | Vertical RLS |
| `app.current_agent_id` | optional audit | Not required for RLS MVP |

Rules:
- Always `set_config(..., is_local => true)` (transaction-scoped) — same pattern as `set_canonical_workspace_id`.
- Unset client on internal session chat: set to empty string **or** use policy that treats missing setting as internal-only (see §4). Prefer **explicit** set every request to avoid pool bleed.
- After `rollback()`, re-set context before retry (SET LOCAL clears).

### 3.3 Composite RLS policy shape

For tables with both keys (example: `memories`):

```sql
-- pseudocode
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories FORCE ROW LEVEL SECURITY;

-- SELECT/WRITE policies share the same predicate
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

**Critical semantics (AD-31):**
- Request with `client_id=X` → **only** `client_id=X` (never NULL, never Y)
- Request without vertical client (internal) → **only** `client_id IS NULL`
- Never OR-widen (`client_id = X OR client_id IS NULL`) for partner traffic
- Never use `client_id` as ranking boost in application SQL

Tables in MVP scope for composite policy:
1. `memories` (18.6) — required
2. `research_threads` if linked from public chat (18.5)
3. `runs` / `token_usage` if they store `client_id` (18.7) — at least application filter + prefer RLS
4. `new_chat_threads` (or equivalent) created via agent-chat

Canonical entity tables remain **workspace-only** RLS (Epic 13); public agent tools that read canonical data do so under workspace context + tool allowlist, not client_id row ownership (canonical is shared workspace knowledge unless a future AD says otherwise).

### 3.4 Application helper API

Mirror canonical helper:

```python
async def set_request_tenant_context(
    session: AsyncSession,
    *,
    workspace_id: int,
    client_id: str | None,
    agent_id: str | None = None,
) -> None:
    await session.execute(text("SELECT set_config('app.workspace_id', :w, true)"), {"w": str(workspace_id)})
    await session.execute(
        text("SELECT set_config('app.current_client_id', :c, true)"),
        {"c": client_id or ""},  # empty => internal policy branch
    )
    if agent_id is not None:
        await session.execute(
            text("SELECT set_config('app.current_agent_id', :a, true)"),
            {"a": agent_id},
        )
    session.info["workspace_id"] = workspace_id
    session.info["client_id"] = client_id
```

Celery / background jobs that touch client-tagged rows must receive both IDs explicitly (no ambient threadlocal).

---

## 4. Composite RLS + PAT — Test Plan

### 4.1 Test layers

| Layer | Where | Purpose |
|-------|-------|---------|
| L0 Unit | pure functions | scope intersection, permission checks |
| L1 DB policy | PostgreSQL integration (real RLS) | FORCE RLS predicates |
| L2 API | FastAPI + PAT | HTTP status matrix |
| L3 Pool safety | two sequential requests on pooled conn | context reset |
| L4 Agent tools | tool allowlist + retrieval | no cross-client memory; no denied tools |
| L5 Abuse | rate limit + audit redaction | 429, no body logs |

CI gate for Stories **18.1 / 18.6 / 18.8**: L1 + L2 + L3 must pass before merge. L4/L5 before production flag on.

### 4.2 Fixtures

```text
Users:       U_owner (member WS1+WS2), U_other (member WS2 only)
Workspaces:  WS1, WS2
Clients:     C_bds="bdsai.vn", C_hr="hr.example"
Agents:      A_bds (client=C_bds, tools=[canonical_search, bds_scrape]), A_hr (client=C_hr)
PATs:
  PAT_bds   kind=agent_chat workspace=WS1 client=C_bds agent=A_bds scopes=[thread+message]
  PAT_bds_any_agent  same but agent_id NULL
  PAT_legacy unscoped
  PAT_ws2   agent_chat on WS2/C_bds
Rows:
  Mem_internal  WS1 client NULL
  Mem_bds       WS1 client C_bds
  Mem_hr        WS1 client C_hr
  Mem_ws2_bds   WS2 client C_bds
```

### 4.3 L0 — Unit cases

| ID | Case | Expect |
|----|------|--------|
| U1 | intersect request client with PAT client equal | ok |
| U2 | request client ≠ PAT client | deny |
| U3 | request agent ≠ PAT agent pin | deny |
| U4 | agent.client_id ≠ effective client | deny |
| U5 | missing permission on route | deny |
| U6 | legacy PAT on agent-chat permission check | deny |
| U7 | external_metadata ignored by authz function | ok (no effect) |

### 4.4 L1 — DB RLS cases (integration)

Setup: role **without** BYPASSRLS; `SET LOCAL` GUCs; `FORCE ROW LEVEL SECURITY`.

| ID | GUC workspace | GUC client | Query | Expect visible |
|----|---------------|------------|-------|----------------|
| R1 | WS1 | `bdsai.vn` | SELECT memories | only Mem_bds |
| R2 | WS1 | `` (empty) | SELECT memories | only Mem_internal |
| R3 | WS1 | `hr.example` | SELECT memories | only Mem_hr |
| R4 | WS2 | `bdsai.vn` | SELECT memories | only Mem_ws2_bds |
| R5 | WS1 | `bdsai.vn` | INSERT memory client=hr | **fail** WITH CHECK |
| R6 | WS1 | `bdsai.vn` | INSERT memory client=NULL | **fail** WITH CHECK |
| R7 | WS1 | empty | INSERT memory client=bds | **fail** |
| R8 | unset workspace GUC | bds | SELECT | **zero rows** / error (fail closed) |
| R9 | WS1 | bds | UPDATE Mem_hr | 0 rows |
| R10 | After COMMIT, new txn without SET | SELECT | 0 rows (no sticky GUC) |

Same matrix smoke-tested for `research_threads` and `token_usage` once columns exist.

### 4.5 L2 — HTTP / PAT matrix

| ID | Auth | Call | Expect |
|----|------|------|--------|
| H1 | PAT_bds | create thread on WS1 | 200/201 |
| H2 | PAT_bds | create thread on WS2 | 403 |
| H3 | PAT_legacy | create thread on WS1 | 403 `pat_scope_required` |
| H4 | none | create thread | 401 |
| H5 | PAT_bds | message + body client_id=hr | 403 |
| H6 | PAT_bds | message + agent_id=A_hr | 403/404 |
| H7 | PAT_bds_any_agent | agent_id=A_bds active | 200 |
| H8 | PAT_bds | agent_id inactive | 404 |
| H9 | PAT_bds | owner removed from WS1 membership | 403 |
| H10 | PAT_bds expired | any | 401 |
| H11 | Session cookie | public agent-chat | 401/403 (PAT-only surface) **or** documented session deny |
| H12 | PAT_bds | internal `/new_chat` if still gated | existing allowlist test still green |

### 4.6 L3 — Pooled connection context reset

| ID | Steps | Expect |
|----|-------|--------|
| P1 | Request A (WS1/bds) then Request B (WS1/internal session) on same worker connection | B never sees Mem_bds |
| P2 | Request A success; Request B begins after A exception/rollback mid-flight | B must set own GUCs; no leak of A's client |
| P3 | Celery task for WS1/bds then task for WS1/hr sequential same process | isolation holds |
| P4 | `SET LOCAL` does not survive commit (assert `current_setting` empty/new default next txn) | pass |

### 4.7 L4 — Retrieval & tools

| ID | Case | Expect |
|----|------|--------|
| T1 | Chat as bds recalls memory | only Mem_bds (+ non-memory workspace docs per product rules) |
| T2 | Attempt tool not in A_bds allowlist | tool unavailable; not callable |
| T3 | Model outputs exfil instruction to call denied tool | runtime still blocks |
| T4 | Canonical search tool (if allowed) | workspace RLS only; no client_id bypass of membership |
| T5 | Auto-extract memory from bds chat | stored with client_id=bds |

### 4.8 L5 — Rate limit & audit

| ID | Case | Expect |
|----|------|--------|
| A1 | Exceed per-(workspace, client) RPM | 429 + Retry-After |
| A2 | Exceed per-workspace ceiling | 429 even if client under local cap |
| A3 | Audit log fields | actor_user_id, pat_id, workspace_id, client_id, agent_id, route, status, run_id |
| A4 | Audit log body | message content **absent** by default |
| A5 | Metrics cardinality | labels bounded (no raw user message, no free-form metadata keys) |

### 4.9 Suggested automated file layout

```text
nowing_backend/tests/
  unit/auth/test_pat_scope.py
  integration/rls/test_composite_client_rls.py
  integration/api/test_agent_chat_pat_matrix.py
  integration/pool/test_tenant_guc_reset.py
  integration/agent/test_agent_chat_tool_isolation.py
```

Minimum assertions library:
- helper `as_pat(token)` 
- helper `set_gucs(session, workspace_id, client_id)`
- fixture DB role `nowing_app` WITHOUT bypassrls for L1

### 4.10 Exit criteria for gate item 3

Design accepted when:
1. This document merged on `develop`.
2. Story 18.1 task list references §2 algorithm and §4.5 matrix.
3. Story 18.6/18.8 task lists reference §3.3 policies and §4.4/§4.6 cases.
4. No open decision blocking migration shape (see §6).

---

## 5. Threat Model (short) — Public Agent-Chat

### 5.1 Assets
- Workspace documents, canonical entities, memories (esp. other clients' memories)
- Tool side-effects (scrapers, connectors, writes)
- Credit wallet / run output
- PAT plaintext (shown once), PAT hash
- Agent system_instructions (admin trusted)
- Partner end-user PII inside messages / external_metadata

### 5.2 Actors
- Honest vertical backend (holds PAT)
- Compromised vertical backend / leaked PAT
- Malicious end-user of vertical (prompt injection)
- Malicious workspace member minting over-broad PAT
- Curious superuser / insider (out of scope beyond audit)

### 5.3 Trust boundaries
```text
[Vertical end-user] 
    -> [Vertical app]  --PAT-->  [Nowing public agent-chat]
                                    |-- RLS/GUC --> Postgres
                                    |-- tools --> scrapers/connectors
                                    |-- LLM provider
```
Everything from vertical app **except** PAT cryptographic authenticity is **untrusted**: messages, platform_metadata, external_metadata, client-supplied ids.

### 5.4 Top threats & mitigations

| ID | Threat | Impact | Mitigation | Verify |
|----|--------|--------|------------|--------|
| TM1 | PAT leakage | Full agent-chat on bound tenant | Single-workspace+client scoped PAT; expiry; revoke; short TTL recommended; no legacy PAT on public routes | H3, H10 |
| TM2 | Cross-workspace access | Data from other WS | Path workspace must equal PAT; membership check | H2, H9 |
| TM3 | Cross-client memory recall | Partner data leak | Composite RLS + hard filter; no ranking boost | R1–R3, T1 |
| TM4 | Client_id escalation in body | Read other vertical | Intersect with PAT; RLS WITH CHECK | H5, R5 |
| TM5 | Agent escalation | Stronger tools/prompt | Registry load fail-closed; PAT agent pin; tool allowlist explicit | H6–H8, T2 |
| TM6 | Prompt injection → tool abuse | Unauthorized scrape/exfil | Tool allowlist enforced in runtime not prompt; deny-by-default new connectors (AD-30) | T2–T3 |
| TM7 | Prompt injection → exfil via answer | Sensitive doc content to attacker | Only tools/data in scope of WS+client; citations optional; no other-client memories | T1, T4 |
| TM8 | Prompt injection → instruction override | Ignore system policy | system_instructions admin-only; length limits; no secret interpolation from metadata; treat user/platform_metadata as data | code review 18.4 |
| TM9 | external_metadata authz confusion | Confused deputy | Metadata never read by authz/RLS | U7 |
| TM10 | Rate abuse / cost DoS | Wallet drain / noisy neighbor | Per WS + per client limits; billable path metering (FR-37); 429 | A1–A2 |
| TM11 | Log/PII leakage | Compliance | Default no message bodies in logs; PII redaction on canonical already | A3–A4 |
| TM12 | Pool GUC bleed | Cross-tenant row visibility | SET LOCAL only; L3 tests; explicit set every request | P1–P4 |
| TM13 | Inactive agent / deleted client still callable | Stale capability | 404 inactive; client is_active check at authz | H8 |
| TM14 | Session cookie accepted on public route | Browser CSRF / ambient auth confusion | Public surface PAT-only (recommend) | H11 |
| TM15 | Model returns connector secrets | Secret exfil | Secrets never in tool results; env only on server | review |

### 5.5 Residual risk (accepted for pilot with flag off until review)
- Malicious **authorized** client can still burn its own wallet within rate limits.
- Shared workspace canonical knowledge is visible to all clients in that workspace if tools allow — document for BDS pilot (single-client workspace recommended).
- LLM provider sees prompt content (DPA / subprocessors).

### 5.6 Production enablement checklist
- [ ] Scoped PAT mint live; legacy blocked on public routes  
- [ ] L1–L3 tests green in CI  
- [ ] Rate limits configured non-zero  
- [ ] Audit sink verified  
- [ ] Security review sign-off on TM6–TM8  
- [ ] Feature flag `AGENT_CHAT_PUBLIC_ENABLED` default false  

---

## 6. Open decisions (do not block design accept; resolve in 18.1 kickoff)

| # | Question | Default if undecided |
|---|----------|----------------------|
| D1 | Multi-workspace PAT arrays vs single FK | **Single** `workspace_id` MVP |
| D2 | Public routes session-allowed? | **PAT-only** |
| D3 | Empty GUC vs unset for internal client | **Set empty string** every request |
| D4 | Canonical data shared across clients in one WS? | **Yes shared** (workspace knowledge); isolate via separate WS for hard split |
| D5 | RBAC permission name to mint agent_chat PAT | Workspace **Owner** |

---

## 7. Mapping to stories

| Story | Consumes |
|-------|----------|
| 18.1 Public endpoints | §2 algorithm, §4.5, TM1–5, TM14 |
| 18.2 Request schema | §2.7 untrusted fields |
| 18.3–18.4 Registry / prompt | AD-30, TM5–8 |
| 18.5 ResearchThread link | client_id on thread; RLS when column exists |
| 18.6 Memory filter | §3.3, §4.4, §4.7 |
| 18.7 Cost metadata | TM9; attribution only |
| 18.8 Rate limit + RLS middleware | §3.2–3.4, §4.6, §4.8 |

---

## 8. Gate statement

With this document:

- Epic 18 entry criterion **#3** (PAT scope model + composite RLS designed and test-planned) is **satisfied at design level**.
- Criteria #1 (E13 P0) and #2 (AD-29/30/31 accept) are already done on `develop` as of 2026-08-07.
- Coding of 18.x may start against this design; production traffic stays behind flag + security checklist §5.6.

