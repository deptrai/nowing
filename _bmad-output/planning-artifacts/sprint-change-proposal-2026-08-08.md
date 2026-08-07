---
title: "Sprint Change Proposal — Epic 13 Expansion: Public Agent-Chat API & Agent Registry"
project: Nowing
date: 2026-08-08
status: approved
author: Winston (Architect) + Luis (PO)
scope: Epic 13 (Canonical Entity Storage & Multi-Domain Indexing)
---

# Sprint Change Proposal — Epic 13 Expansion

---

## Section 1 — Issue Summary

### 1.1 Trigger

BDS AI co-evolution proposal (2026-08-08) requires Nowing to expose **public agent-chat APIs** that do not currently exist. The BDS AI team needs:

1. Public chat endpoints (`POST /agent-chat/threads`, `POST /agent-chat/messages`) for service accounts
2. Agent Registry to store per-agent system prompts and tool configuration
3. Memory tagging with `client_id`/`agent_id` for tenant isolation
4. ResearchThread auto-linkage on chat thread creation
5. Cost traceability via `external_metadata` on TokenUsage/Run

### 1.2 Core Problem

Nowing's chat infrastructure is currently **internal-only** (web app → backend). There are no public APIs for vertical clients like BDS AI to integrate with. The architecture implicitly assumes all chat originates from the Nowing web app.

BDS AI's proposal makes them the **first vertical client** of Nowing — which requires building the public API layer that all future verticals will use.

### 1.3 Evidence

- BDS AI proposal: `bdsai-client-integration-proposal.md` (8 stories N.1-N.8)
- Architecture spine AD-27/AD-28: designed for this but stories not yet implemented
- AD-13: currently silent on public endpoints (needs amendment)
- Existing chat endpoints: internal-only, no PAT auth, no `client_id` concept

---

## Section 2 — Impact Analysis

### 2.1 Epic Impact

| Epic | Status | Impact | Adjustment |
|------|--------|--------|------------|
| **Epic 13** (Canonical Entity) | In progress | **Directly affected** — needs 8 new stories for public chat infrastructure | Add stories 13.4-13.11 |
| Epic 14 (News) | Planned | Depends on Epic 13 memory tagging | No change (waits for 13) |
| Epic 15 (Finance) | Planned | Depends on Epic 13 memory tagging | No change (waits for 13) |
| Epic 16 (Company) | Planned | Depends on Epic 13 memory tagging | No change (waits for 13) |
| Epic 17 (E-commerce) | Planned | Depends on Epic 13 memory tagging | No change (waits for 13) |

### 2.2 Story Impact

**New stories required in Epic 13:**

| Story | Title | AD | Effort |
|-------|-------|-----|--------|
| 13.4 | Public Agent-Chat Endpoints | AD-13 | 1 day |
| 13.5 | NewChatRequest extension | AD-13 | 0.5 day |
| 13.6 | Agent Registry | AD-27 | 0.5 day |
| 13.7 | AgentConfig prompt injection | AD-27 | 0.5 day |
| 13.8 | ResearchThread auto-linkage | AD-13 | 0.5 day |
| 13.9 | Memory tagging + RAG filter | AD-27 | 0.5 day |
| 13.10 | Cost traceability | AD-28 | 0.5 day |
| 13.11 | Rate limiting + tenant isolation | AD-13 | 0.5 day |
| **Total** | | | **~4.5 days** |

### 2.3 Artifact Conflicts

| Artifact | Conflict | Update Required |
|----------|----------|-----------------|
| **PRD** | No FR for public chat | Add FR-48, FR-49, NFR-MULTI-1 |
| **Architecture** | AD-13 silent on public endpoints | Amend AD-13 to explicitly allow public endpoints with guardrails |
| **Epics** | Epic 13 has only 3 stories | Add 8 stories (13.4-13.11) |
| **DB Schema** | No `agent_configs` table, no tenant tags | 3 migrations |
| **UX Contract** | N/A | No impact (BDS builds their own UI) |

### 2.4 Technical Impact

| Component | Impact |
|-----------|--------|
| **Chat flow** | Add `agent_id` loading → `AgentConfig` → system prompt injection |
| **Memory/RAG** | Hard `client_id` filter on all recall queries |
| **Auth** | PAT validation middleware for public endpoints |
| **DB** | New `agent_configs` table + columns on `memories`, `token_usage`, `runs` |
| **Security** | RLS policies for tenant isolation |

---

## Section 3 — Recommended Approach

### Option 1 — Direct Adjustment ✅ RECOMMENDED

- **Description:** Add 8 stories to Epic 13 for public chat infrastructure
- **Effort:** Medium (~4.5 days)
- **Risk:** Low — builds on existing patterns
- **Viability:** ✅ Viable

### Option 2 — Potential Rollback

- **Description:** Not applicable — nothing to rollback
- **Viability:** ❌ Not viable

### Option 3 — MVP Review

- **Description:** MVP still achievable. Public chat adds scope but enables BDS revenue.
- **Viability:** ✅ Viable

### Recommended: Option 1 (Direct Adjustment)

**Rationale:**
- Minimal disruption — adds stories to existing epic
- Builds reusable infrastructure for ALL future verticals
- Validates architecture decisions (AD-27/AD-28)
- Enables BDS AI co-evolution (first paying customer)

---

## Section 4 — Detailed Change Proposals

### Change A: Amend AD-13

**File:** `ARCHITECTURE-SPINE.md`

**Current (line 187):**
```
### AD-13 — Research Thread là continuation context
- **Binds:** Story 4.6, Story 6.5
- **Prevents:** mỗi chat là một island, mất lịch sử research
- **Rule:**
  - `ResearchThread` liên kết 1-n `ChatThread`...
```

**Proposed:**
```
### AD-13 — Research Thread là continuation context
- **Binds:** Story 4.6, Story 6.5, **Epic 13 (N.1-N.8)**
- **Prevents:** mỗi chat là một island, mất lịch sử research; **cross-tenant data leakage via public endpoints**
- **Rule:**
  - `ResearchThread` liên kết 1-n `ChatThread`...
  - **Public agent-chat endpoints allowed** with PAT auth, workspace membership validation, tenant isolation (hard `client_id` filter), and rate limiting.
  - **Amendment 2026-08-08:** BDS AI co-evolution requires exposing chat APIs to vertical clients. All public endpoints MUST enforce `client_id` hard filter + RLS.
```

---

### Change B: Add Stories to Epic 13

**File:** `epics.md`

**Add after Story 13.3:**

```markdown
### Story 13.4: Public Agent-Chat Endpoints `[P0]`

As a vertical client,
I want to create chat threads and send messages via public API,
So that I can integrate Nowing chat into my application.

**Acceptance Criteria:**
- **Given** a valid PAT and workspace membership, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, **Then** a chat thread is created and returned with `thread_id` and `research_thread_id`.
- **Given** a valid PAT, **When** `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called, **Then** the message is processed by the chat agent and a response is returned.
- **Given** an invalid PAT or non-member, **When** any public endpoint is called, **Then** 401/403 is returned.
- **Given** a `client_id` in the request, **When** the chat processes, **Then** all data access is filtered by `client_id`.

**Kỹ thuật:** `app/routes/agent_chat_routes.py`, PAT auth middleware, rate limiter.

---

### Story 13.5: NewChatRequest Extension `[P0]`

As a chat system,
I want to accept `agent_id`, `client_id`, and `platform_metadata` in chat requests,
So that agents can be configured per vertical client and context can be forwarded.

**Acceptance Criteria:**
- **Given** a chat request with `agent_id`, **When** processed, **Then** the system loads the corresponding `AgentConfig` and injects `system_instructions` into the prompt.
- **Given** a chat request with `client_id`, **When** processed, **Then** all memory recall and storage is tagged with `client_id`.
- **Given** `platform_metadata` in the request, **When** processed, **Then** the metadata is forwarded to the chat prompt context.

**Kỹ thuật:** Extend `NewChatRequest` schema, add fields to `app/schemas/new_chat.py`.

---

### Story 13.6: Agent Registry `[P0]`

As a platform administrator,
I want to register agents with custom system prompts and tool configurations,
So that different vertical clients can have specialized chat agents.

**Acceptance Criteria:**
- **Given** the migration runs, **When** complete, **Then** an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`.
- **Given** the seed script runs, **When** complete, **Then** `bdsai-listing-assistant` is seeded as the first agent.
- **Given** an `agent_id` is provided in a chat request, **When** processed, **Then** the system loads the corresponding `AgentConfig` or returns 404 if not found.

**Kỹ thuật:** `app/db.py` (AgentConfig model), migration `194_add_agent_configs.py`, seed script.

---

### Story 13.7: AgentConfig Prompt Injection `[P0]`

As a chat system,
I want to inject agent-specific system instructions into the chat prompt,
So that each vertical client gets a specialized agent experience.

**Acceptance Criteria:**
- **Given** a chat request with `agent_id`, **When** the chat flow starts, **Then** `AgentConfig.system_instructions` is prepended to the default system prompt.
- **Given** an `agent_id` with `enabled_tools`, **When** the chat agent selects tools, **Then** only tools in the allowlist are available.
- **Given** no `agent_id`, **When** processed, **Then** the default Nowing chat agent is used (backward compatible).

**Kỹ thuật:** `app/agents/chat/multi_agent_chat/orchestrator.py` — load config, inject prompt, filter tools.

---

### Story 13.8: ResearchThread Auto-Linkage `[P0]`

As a vertical client,
I want chat threads to be automatically linked to ResearchThreads,
So that memory is properly isolated and contextual across sessions.

**Acceptance Criteria:**
- **Given** a chat thread is created with `agent_id`, **When** the thread is created, **Then** a new `ResearchThread` is auto-created and linked.
- **Given** the ResearchThread is created, **When** the API response is returned, **Then** it includes `research_thread_id`.
- **Given** memories are extracted from the chat, **When** stored, **Then** they are tagged with `research_thread_id`.

**Kỹ thuật:** `app/routes/agent_chat_routes.py` — auto-create ResearchThread, update response schema.

---

### Story 13.9: Memory Tagging + RAG Filter `[P1]`

As a platform,
I want memories tagged with `client_id`/`agent_id` and RAG recall to hard-filter by tenant,
So that one client's data never leaks into another client's chat.

**Acceptance Criteria:**
- **Given** a memory is created from a chat with `client_id`, **When** stored, **Then** the memory row has `client_id` set.
- **Given** a recall query with `client_id`, **When** the RAG system searches, **Then** only memories with matching `client_id` are returned (hard filter, not boost).
- **Given** a recall query without `client_id`, **When** processed, **Then** only memories with `client_id = NULL` (Nowing-internal) are returned.

**Kỹ thuật:** Migration `195_add_memory_tenant_tags.py`, update `app/retriever/chunks_hybrid_search.py`.

---

### Story 13.10: Cost Traceability `[P1]`

As a vertical client,
I want to attribute costs to my users and listings,
So that I can track and bill for Nowing usage.

**Acceptance Criteria:**
- **Given** a chat request with `external_metadata` (listing_id, broker_id, user_id), **When** processed, **Then** the `TokenUsage` row stores the metadata.
- **Given** a `client_id`, **When** querying TokenUsage, **Then** cost reports can be generated per client per day.
- **Given** an `X-Run-Id` header in the response, **When** the client receives it, **Then** they can correlate costs with their internal records.

**Kỹ thuật:** Migration `196_add_token_usage_metadata.py`, update `app/services/token_tracking_service.py`.

---

### Story 13.11: Rate Limiting + Tenant Isolation `[P1]`

As a platform,
I want to enforce rate limits per workspace and per client,
So that no single client can degrade service for others.

**Acceptance Criteria:**
- **Given** a public chat endpoint is called, **When** rate limit is exceeded, **Then** 429 is returned with `Retry-After` header.
- **Given** a PAT is validated, **When** the request is processed, **Then** PostgreSQL RLS context is set (`SET LOCAL app.current_client_id`).
- **Given** RLS is active, **When** any query runs, **Then** rows are filtered by `client_id` automatically.

**Kỹ thuật:** Middleware in `app/middleware/tenant_context.py`, rate limiter with Redis.
```

---

### Change C: PRD Updates

**File:** `prd-Nowing-2026-07-22/prd.md`

**Add:**
- FR-48: Public agent-chat API for vertical clients
- FR-49: Agent Registry with per-agent system prompts and tool configuration
- NFR-MULTI-1: Tenant isolation — hard `client_id` filter on all data access

---

### Change D: Database Migrations

| Migration | What |
|-----------|------|
| `194_add_agent_configs.py` | Create `agent_configs` table + seed `bdsai-listing-assistant` |
| `195_add_memory_tenant_tags.py` | Add `client_id`, `agent_id`, `research_thread_id` to `memories` |
| `196_add_token_usage_metadata.py` | Add `external_metadata` to `token_usage` and `runs` |

---

## Section 5 — Implementation Handoff

### Change Scope: **Moderate**

| Role | Responsibility |
|------|---------------|
| **Developer** | Implement stories 13.4-13.11 in order |
| **Architect** | Amend AD-13, verify RLS policies, review security |
| **Product Owner** | Update PRD (FR-48, FR-49), update epics.md, update sprint-status.yaml |

### Implementation Order

```
13.6 (Agent Registry) → 13.5 (NewChatRequest) → 13.7 (Prompt Injection)
    ↓
13.4 (Public Endpoints) → 13.8 (ResearchThread Linkage)
    ↓
13.9 (Memory Tags) → 13.10 (Cost Traceability) → 13.11 (Rate Limiting)
```

### Success Criteria

- [ ] BDS AI can create chat threads via public API with PAT auth
- [ ] BDS AI chat responses use domain-specific system prompt
- [ ] BDS AI memories are isolated from Nowing-internal and other clients
- [ ] Cost reports can be generated per client per day
- [ ] Rate limiting prevents abuse

---

**Proposal Status:** Draft — awaiting user approval
**Next Step:** User approval → Developer agent implements stories
