# Story 18.6: Memory Tagging + RAG Filter

Status: in-progress

Baseline commit: 1e5f46b86

## Story

As a platform,
I want memories tagged with `client_id`/`agent_id` and RAG recall to hard-filter by tenant,
so that one client's data never leaks into another client's chat.

## Acceptance Criteria

1. **Given** a memory is created from a chat with `client_id`, **When** stored, **Then** the memory row has `client_id` set.
2. **Given** a recall query with `client_id`, **When** the RAG system searches, **Then** only memories with matching `client_id` are returned (hard filter, not boost).
3. **Given** a recall query without `client_id`, **When** processed, **Then** only memories with `client_id = NULL` (Nowing-internal) are returned.

## Tasks / Subtasks

- [ ] Add `client_id` / `agent_id` tags to `Memory` (AC: #1)
  - [ ] Add Alembic migration: `memories.client_id` (text, nullable, index `(workspace_id, client_id)`), `memories.agent_id` (text, nullable)
  - [ ] Update `Memory` model (`app/db.py:2139-2255`)
  - [ ] Update `MemoryCreate`/`MemoryUpdate` schemas to accept `client_id` and `agent_id`
  - [ ] Update `MemoryExtractionService` (`app/services/memory/extraction.py`) to tag auto-extracted memories with `client_id` and `agent_id` from the chat context
  - [ ] Update manual memory endpoints (`app/routes/memories_routes.py`) to accept `client_id` (for admin use) and default to NULL for internal users
- [ ] Update RAG recall with hard tenant filter (AC: #2, #3)
  - [ ] Update `MemoryHybridSearch.search` (`app/services/memory/search.py:88-167`) to accept `client_id: str | None` and add `client_id` filter:
    - `client_id` provided → `Memory.client_id == client_id`
    - `client_id` not provided → `Memory.client_id.is_(None)`
  - [ ] Update `app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` to pass `client_id` from request context to recall
  - [ ] Ensure `top_k` retrieval still uses HNSW + GIN and the `client_id` filter is pushed to the SQL `WHERE` clause (no post-filter)
- [ ] DB-enforced composite RLS (AC: #2, #3)
  - [ ] Add PostgreSQL RLS policies on `memories` using `app.workspace_id` + `app.current_client_id` per `epic-18-pat-scope-rls-threat-model.md §3.3`
  - [ ] Policy predicate (pseudocode): `workspace_id = current_setting('app.workspace_id')` AND (`client_id` matches current `client_id` OR `client_id IS NULL` only when current `client_id` is unset)
  - [ ] Enable `FORCE ROW LEVEL SECURITY` on `memories`
  - [ ] Add migration to create policy and grant table usage to app role without bypass
- [ ] Update memory CRUD for tenant isolation
  - [ ] Update `app/services/memory/repository.py` to include `client_id` in scope conditions
  - [ ] Update `app/routes/memories_routes.py` to set GUCs and pass `client_id`
  - [ ] Update `app/services/memory/service.py` (legacy bridge) to default `client_id=NULL`
- [ ] Thread/ResearchThread isolation
  - [ ] Ensure `ResearchThread` memories are only returned when both `client_id` and `research_thread_id` match (or `client_id` NULL for internal)
- [ ] Tests (L1 DB policy + L4 retrieval from threat model)
  - [ ] L1 RLS integration tests `tests/integration/rls/test_composite_client_rls.py` cases R1-R10 from `epic-18-pat-scope-rls-threat-model.md §4.4`
  - [ ] Unit test `MemoryHybridSearch.search` with `client_id` set, unset, and mismatched
  - [ ] Integration test chat as `client=bds` only recalls `Mem_bds` and `Mem_internal` is not returned
  - [ ] Integration test cross-client memory creation is rejected by RLS `WITH CHECK`
  - [ ] Integration test internal chat only sees `client_id=NULL` memories

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is a hard isolation key orthogonal to `workspace_id`. Workspace membership alone is insufficient. Recall/list paths hard-filter: request with `client_id=X` → only rows with `client_id=X`; request without vertical client → only `client_id IS NULL`. Never use `client_id` as a ranking boost. Prefer DB policy composed with workspace RLS.
  - `epic-18-pat-scope-rls-threat-model.md §3.3` — composite RLS policy shape for `memories` with `workspace_id` and `client_id`; critical semantics (no OR-widening for partner traffic).
  - `epic-18-pat-scope-rls-threat-model.md §4.4` — L1 DB RLS test cases R1-R10; `FORCE RLS` and `SET LOCAL` GUCs.
  - `epic-18-pat-scope-rls-threat-model.md §4.7` — L4 retrieval & tools cases T1-T5: chat as bds recalls only `Mem_bds`, tool not in allowlist unavailable, auto-extract from bds chat stores `client_id=bds`.
  - `AD-13` (`ARCHITECTURE-SPINE.md:274-282`) — `ResearchThread` continuity context; memory link uses `research_thread_id`.
  - `AD-11` (`ARCHITECTURE-SPINE.md:238-261`) — `Memory` is workspace-wide first-class persistence; `client_id` is an additional orthogonal tenant key.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — migration for `memories.client_id`/`agent_id` + RLS policy
  - `nowing_backend/app/db.py:2139-2255` — `Memory` model
  - `nowing_backend/app/schemas/memories.py` — memory create/update schemas
  - `nowing_backend/app/services/memory/extraction.py` — auto-extraction
  - `nowing_backend/app/services/memory/repository.py` — CRUD
  - `nowing_backend/app/services/memory/search.py:88-167` — `MemoryHybridSearch`
  - `nowing_backend/app/services/memory/service.py` — legacy memory service
  - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` — memory injection
  - `nowing_backend/app/routes/memories_routes.py` — structured memory routes
  - `nowing_backend/app/middleware/tenant_context.py` (Story 18.8) — `set_request_tenant_context`
  - `nowing_backend/app/canonical/tenant_context.py:17-31` — GUC pattern

- Testing standards summary
  - Unit tests in `tests/unit/services/memory/test_search_client_filter.py`
  - L1 RLS integration tests in `tests/integration/rls/test_composite_client_rls.py` (must be in CI gate for 18.1/18.6/18.8)
  - L4 retrieval integration tests in `tests/integration/agent/test_agent_chat_tool_isolation.py`
  - DB role `nowing_app` WITHOUT BYPASSRLS for L1 tests

### Project Structure Notes

- Alignment with unified project structure
  - Tenant context belongs in `app/middleware/tenant_context.py` (shared with 18.8).
  - RLS policy migrations are Alembic ops in `alembic/versions/`.

- Detected conflicts or variances
  - `Memory` table already has `workspace_id` and `research_thread_id` but no `client_id`. Adding `client_id` is additive.
  - `MemoryInjectionMiddleware` currently uses `MemoryHybridSearch.search(..., top_k=...)`. The composite filter must be added to the SQL `WHERE` clause before HNSW/GIN retrieval, not as a Python post-filter, to preserve bounded performance (`AD-18`).
  - Manual memory routes currently do not set `client_id`; default to NULL. A future admin UI may add client-scoped memories.
  - RLS must be coordinated with Story 18.8 (middleware) to ensure `app.current_client_id` is set on every request that touches `memories`.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.6]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-31, AD-11, AD-18]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §3.3 Composite RLS, §4.4 L1 DB RLS, §4.7 L4 Retrieval & tools, §5 TM3, TM6, TM7]
- [Source: `nowing_backend/app/db.py` §Memory]
- [Source: `nowing_backend/app/services/memory/search.py` §MemoryHybridSearch]
- [Source: `nowing_backend/app/services/memory/extraction.py` §MemoryExtractionService]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List

### Review Findings (code review — 2026-08-11)

**Review layers completed:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.  
**Triage summary:** 1 `decision-needed` (resolved → patch applied), 3 `patch` applied, 3 `patch` remaining, 2 `defer`, ~10 `dismiss` as noise or handled.

#### `decision-needed` → resolved

- [x] [Review][Decision] Manual `POST /workspaces/{workspace_id}/memories` accepted arbitrary `client_id`/`agent_id` from the request body. **Decision:** derive tenant from the authenticated PAT scope and intersect with any values supplied in the request body; session/system principals have no client scope, so any non-None request values are rejected. Applied to `create_memory`, `search_memory`, `list_memories`, `update_memory`, `revalidate_memory`, and `delete_memory` in `memories_routes.py`, mirroring the fail-closed pattern in `agent_chat_routes.py`. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/memories_routes.py" lines="41-86" />

#### `patch` — applied

- [x] [Review][Patch] `MemoryUpdate` schema no longer accepts `client_id`/`agent_id`; tenant attributes are immutable on update. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/schemas/memory.py" lines="117-118" />
- [x] [Review][Patch] Column migration `10127c164b44` ruff style issues fixed with `ruff check --fix`. <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/alembic/versions/10127c164b44_add_memories_client_agent_columns_and_.py" />

#### `patch` — remaining

- [ ] [Review][Patch] `Memory.client_id` is `Text`, but `VerticalClient.client_id` is `CITEXT` per AD-31. Case-sensitivity can cause mismatches between memory rows and the canonical client natural key. Change `client_id` in `app/db.py` to `CITEXT` and add a follow-up migration to alter the column type, or add a case-insensitive comparison wrapper. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/db.py" lines="2298" />
- [ ] [Review][Patch] Missing unit tests for `MemoryHybridSearch.search` `client_id` filtering. The spec calls for `tests/unit/services/memory/test_search_client_filter.py` (or equivalent) covering set/unset/mismatched client. Add cases to `tests/unit/services/test_memory_search.py`. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/tests/unit/services/test_memory_search.py" lines="1-186" />
- [ ] [Review][Patch] Missing L4 retrieval integration tests for the chat path. The spec references `tests/integration/agent/test_agent_chat_tool_isolation.py` and threat model T1-T5. Add an end-to-end test that chat as `client=bds` only recalls `Mem_bds` and that internal chat only sees `client_id=NULL` memories. <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md" />
- [ ] [Review][Patch] `MemoryChangedPayload` does not carry `client_id` or `agent_id`. Memory change events published to a workspace-wide bus cannot be filtered by client, which may cause client-scoped automations to react to the wrong tenant's facts. Add `client_id` and `agent_id` to the payload. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/event_bus/events/memory_changed.py" lines="51-58" />

#### `patch` — resolved 2026-08-11

- [x] [Review][Patch] `MemoryRelation` has no `client_id` and `MemoryRepository.add_relation` does not set tenant GUCs. Added `client_id` column, composite `(workspace_id, client_id)` index, RLS policies in migration `b8b3fae31175`, and hardened `add_relation` to derive scope from the source memory, set tenant GUCs, and reject cross-workspace/cross-client targets. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/memory/repository.py" lines="605-670" />
- [x] [Review][Patch] `MemoryRepository._find_near_duplicate` did not include `client_id` in its scope, so `update_on_duplicate` could match a memory from another client. Added `client_id` parameter and filter. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/memory/repository.py" lines="89-125" />
- [x] [Review][Patch] `Memory.source_uuid` and `Memory.source_entity_type` existed in `app/db.py` but no migration added them. Added migration `e5b50d5e687e`. <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/alembic/versions/e5b50d5e687e_add_memory_source_uuid_entity_type.py" />

#### `defer`

_None remaining from this review._