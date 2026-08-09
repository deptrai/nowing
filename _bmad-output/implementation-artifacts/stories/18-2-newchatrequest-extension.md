---
baseline_commit: "a247f8448"
status: ready-for-dev
---

# Story 18.2: NewChatRequest Extension

## Story

As a chat system,
I want to accept `agent_id`, `client_id`, and `platform_metadata` in chat requests,
so that agents can be configured per vertical client and context can be forwarded.

## Acceptance Criteria

1. **Given** a chat request with `agent_id`, **When** processed, **Then** the system loads the corresponding `AgentConfig` and injects `system_instructions` into the prompt.
2. **Given** a chat request with `client_id`, **When** processed, **Then** all memory recall and storage is tagged with `client_id`.
3. **Given** `platform_metadata` in the request, **When** processed, **Then** the metadata is forwarded to the chat prompt context.
4. **Given** no `agent_id`, **When** processed, **Then** the default Nowing chat agent is used (backward compatible).

## Developer Context

### Epic 18 Context

Epic 18 "Vertical Client Platform (Public Agent-Chat)" provides a public API surface so external vertical clients (first: BDS AI) can run specialized agents against a Nowing workspace with PAT auth, hard tenant isolation, cost attribution and rate limits. Story 18.1 delivered the public endpoints and PAT-scope auth; 18.2 now makes the chat runtime itself understand `agent_id`, `client_id` and `platform_metadata` so the public surface can drive the same streaming chat used by the web UI without hard-coding per-vertical behavior.

Epic 18 entry criteria (all required and accepted 2026-08-07):
- AD-29, AD-30, AD-31 accepted on Architecture Spine.
- PAT scope model, composite RLS (`workspace_id` + `client_id`) and threat model test plan published.

All Epic 18 stories:
- 18.1 Public Agent-Chat Endpoints (`done`)
- 18.2 NewChatRequest Extension (this story)
- 18.3 Agent Registry
- 18.4 AgentConfig Prompt Injection
- 18.5 ResearchThread Auto-Linkage
- 18.6 Memory Tagging + RAG Filter
- 18.7 Cost Traceability
- 18.8 Rate Limiting + Tenant Isolation

### Architecture Decisions — Must Follow

**AD-29 — Public Agent-Chat Surface** (`ARCHITECTURE-SPINE.md:727-737`)
- Public routes live under `/api/v1/workspaces/{workspace_id}/agent-chat/...` and are explicitly allowlisted. Internal web chat routes stay internal.
- Auth is PAT with server-enforced scopes. Client-supplied IDs cannot escalate beyond token scope.
- Every request sets transaction-local DB context for workspace (`app.workspace_id`) and, when present, vertical client (`app.current_client_id`) **before** any business query.
- `external_metadata` and `platform_metadata` are additive and **untrusted for authorization**.

**AD-30 — AgentConfig Registry** (`ARCHITECTURE-SPINE.md:739-748`)
- `agent_configs` stores named agents: identity, `client_id`, `slug`, `system_instructions`, tool allow/deny lists, `model_name`, `citations_enabled`, `is_active`.
- Missing/inactive `agent_id` → fail closed (`404`), never silently fall through.
- Tool allowlists are explicit. New connectors do not auto-enable.
- `system_instructions` are trusted admin content; still subject to length limits and no raw secret interpolation from client metadata.

**AD-31 — Vertical Client Tenancy (`client_id`)** (`ARCHITECTURE-SPINE.md:750-764`)
- `client_id` is a **hard isolation key orthogonal to `workspace_id`**.
- Tables carrying vertical-client data gain nullable `client_id` (NULL = Nowing-internal / web app).
- Recall/list paths hard-filter by `client_id`; never use it as a ranking boost.
- Composite policy order: authenticate → authorize workspace → set workspace RLS context → authorize client scope → set client RLS context → run query.

**AD-13 — Research Thread Continuation Context** (`ARCHITECTURE-SPINE.md:274-282`)
- `ResearchThread` links 1-n `NewChatThread` via `new_chat_threads.research_thread_id`.
- Public/vertical agent-chat may create and link `ResearchThread` instances, but only through the AD-29 public surface.

**AD-14 — Auto-extract memory từ chat turn** (`ARCHITECTURE-SPINE.md:284-292`)
- After an assistant message is saved, `MemoryExtractionService` extracts facts.
- Each extraction/upsert records `TokenUsage.usage_type = "memory_create"`.
- Memory rows are workspace-scoped; `client_id` tagging is introduced in Epic 18 to keep vertical-client memories isolated.

### Untrusted Fields

| Client sends | Server uses |
|---|---|
| `workspace_id` in path / request | Must match auth scope; never taken from body alone for public calls |
| `client_id` in body | Intersected with PAT scope or thread scope; cannot widen |
| `agent_id` in body | Intersected with PAT scope + registry; fail-closed on missing/inactive |
| `platform_metadata` | Prompt context only; must be rendered as a labeled, non-secret block |
| `external_metadata` | Stored for attribution only; **never** used in authz/RLS |

### Threat Model Summary

| ID | Threat | Mitigation | Verify |
|---|---|---|---|
| TM4 | `client_id` escalation in body | Intersect with PAT/thread scope; RLS WITH CHECK | H5, R5 |
| TM5 | Agent escalation | Registry load fail-closed; PAT agent pin; tool allowlist | H6-H8, T2 |
| TM6 | Prompt injection → tool abuse | Tool allowlist enforced in runtime not prompt | T2-T3 |
| TM7 | Prompt injection → exfil via answer | Only tools/data in scope of WS+client | T1, T4 |
| TM8 | Prompt injection → instruction override | `system_instructions` admin-only; no secret interpolation | review 18.4 |
| TM9 | `external_metadata` authz confusion | Metadata never read by authz/RLS | U7 |
| TM11 | Log/PII leakage | Default no message bodies in logs | A3-A4 |
| TM13 | Inactive agent / deleted client still callable | 404 inactive; client `is_active` check | H8 |

## Technical Requirements

### 1. Database migrations

Create Alembic migration(s) for `new_chat_threads`:
- Add `agent_id` column (`Text`, nullable=True, index=True) to `new_chat_threads`.
- `client_id` column already exists on `new_chat_threads` (added by Story 18.1 migration `78f7a9b1e85f`). Verify and add index `(workspace_id, client_id)` if not present.
- Add `client_id` column to `memories` if Story 18.6/18.8 have not yet (coordinate; 18.2 should at minimum pass `client_id` to `MemoryExtractionService` so 18.6 can persist it).

### 2. Extend `NewChatRequest` schema

`app/schemas/new_chat.py`:
- Add to `NewChatRequest`:
  - `agent_id: str | None` (optional, slug format, max 63 chars)
  - `client_id: str | None` (optional, slug format, max 63 chars)
  - `platform_metadata: dict[str, Any] | None` (optional, bounded size)
- Add validator on `NewChatRequest`:
  - If `agent_id` is set, `client_id` must also be set and match the agent's `client_id`, **unless** `client_id` is provided by a trusted source (e.g. PAT scope) and the `agent_id` belongs to that client.
  - `client_id`/`platform_metadata` must not affect authz.
- Add the same three fields to `RegenerateRequest` (it is a near-copy of `NewChatRequest`) so resume/regenerate flows can preserve the agent/client context.

### 3. Extend thread creation schemas

`app/schemas/new_chat.py`:
- Add `client_id: str | None` and `agent_id: str | None` to `NewChatThreadCreate`.
- Add `client_id: str | None` and `agent_id: str | None` to `NewChatThreadRead` / `NewChatThreadWithMessages` so clients can read back the thread context.

`app/db.py` (`NewChatThread`):
- Add `agent_id = Column(Text, nullable=True, index=True)` alongside the existing `client_id`.

### 4. Persist `client_id` and `agent_id` on thread creation

`app/routes/new_chat_routes.py:790-846` (`create_thread`):
- Accept `client_id` and `agent_id` from `NewChatThreadCreate`.
- Persist them on the `NewChatThread` row.
- For internal web requests these will be `None`; for public agent-chat these are populated by `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads`.

`app/routes/agent_chat_routes.py` (`POST /threads`):
- Already passes `client_id` and `agent_id` to `NewChatThread` via `agent_id=` and `client_id=`. Ensure the fields are persisted.

### 5. Wire chat orchestrator

`app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (`stream_new_chat`):
- Add `platform_metadata: dict[str, Any] | None` parameter.
- Add `agent_config_override: AgentConfig | None` parameter (registry row from `app.db.AgentConfig`) — this allows public routes to pre-resolve the agent in the auth layer.
- If `agent_id`/`agent_config_override` is present:
  - Load `AgentConfig` from `app.db.AgentConfig` by `client_id` + `slug=agent_id` (if not already passed).
  - If missing or `is_active=False`, fail closed with 404.
  - After `load_llm_bundle`, construct a runtime `AgentConfig` (`app.agents.chat.runtime.llm_config.AgentConfig`) that merges the resolved LLM bundle with the registry row's `system_instructions`, `use_default_system_instructions`, `citations_enabled`, and `model_name` (if set) and pass it to `build_main_agent_for_thread`.
- If `agent_id` is absent:
  - Use the default Nowing chat agent (existing LLM bundle, no custom system instructions).
- Pass `platform_metadata` through `build_new_chat_input_state` (see `app/tasks/chat/streaming/flows/new_chat/input_state.py:63`) and render it as an XML context block in the prompt.

`app/tasks/chat/streaming/flows/new_chat/input_state.py`:
- Add `platform_metadata` and `client_id` to `build_new_chat_input_state`.
- Prepend a safe, non-interpolated context block such as:
  ```xml
  <platform_metadata>
  {"client_id":"bdsai.vn","agent_id":"bdsai-listing-assistant","...":"..."}
  </platform_metadata>
  ```
- Do **not** allow Jinja/f-string interpolation of `platform_metadata` into `system_instructions`.

### 6. Tool allowlist prep (Story 18.4 will finalize)

- Read `AgentConfig.enabled_tools` and `AgentConfig.disabled_tools` in the orchestrator and pass them to `build_main_agent_for_thread` → `build_main_agent_tools` (or store on the runtime context for 18.4 to filter).
- If `enabled_tools` is non-empty, **do not** auto-enable tools beyond the allowlist.

### 7. Memory tagging (coordinated with 18.6/18.8)

`app/services/memory/extraction.py`:
- Extend `MemoryExtractionService.__init__` to accept `client_id`.
- If `Memory` model gains a `client_id` column (this story or 18.6), set it when creating `Memory` rows.
- For 18.2, ensure the service can receive `client_id` from the chat turn so no refactor is needed in 18.6.

`app/tasks/chat/streaming/flows/new_chat/orchestrator.py`:
- When persisting the assistant message, pass `client_id` to the memory extraction task.

### 8. Backward compatibility

- Existing web/desktop chat requests do not send `agent_id`/`client_id`/`platform_metadata`; all three default to `None`.
- `client_id=None` must keep the existing behavior (internal / web app) and RLS must see `app.current_client_id` unset → only `client_id IS NULL` rows.
- Regression tests must run the existing chat happy path with no new fields.

### 9. Testing

Add/update tests:
- `tests/unit/schemas/test_new_chat.py`:
  - `NewChatRequest` validator with/without `agent_id`/`client_id`.
  - `platform_metadata` bounded size / no secret interpolation.
- `tests/unit/tasks/chat/test_new_chat_orchestrator.py`:
  - `stream_new_chat` loads correct `AgentConfig` and passes `system_instructions` to prompt builder.
  - `stream_new_chat` falls back to default when `agent_id` is absent.
  - `platform_metadata` appears in the assembled prompt context.
- `tests/integration/routes/test_new_chat_routes.py`:
  - `POST /threads` persists `client_id` and `agent_id`.
  - `POST /new_chat` with `agent_id` returns a streaming response using the specialized `system_instructions`.
  - `POST /new_chat` without `agent_id` is unchanged (regression).
- `tests/integration/agent_chat/test_schema_and_guc.py` (or new `tests/integration/api/test_agent_chat_pat_matrix.py`):
  - End-to-end public PAT call with `client_id`/`agent_id`/`platform_metadata` is preserved through the chat turn.

## File Structure

### Files to Create

| File | Purpose |
|---|---|
| `nowing_backend/alembic/versions/..._new_chat_thread_agent_client.py` | Add `agent_id` (and `client_id` if missing) columns to `new_chat_threads` and `memories` (or coordinate with 18.6) |
| `nowing_backend/tests/unit/schemas/test_new_chat.py` | NewChatRequest / NewChatThreadCreate validator tests |
| `nowing_backend/tests/unit/tasks/chat/test_new_chat_orchestrator.py` | Orchestrator AgentConfig + platform_metadata tests |

### Files to Modify

| File | What to Change | What to Preserve |
|---|---|---|
| `nowing_backend/app/schemas/new_chat.py:85-91` | Add `client_id`/`agent_id` to `NewChatThreadCreate` | Existing `workspace_id` and `visibility` defaults |
| `nowing_backend/app/schemas/new_chat.py:106-125` | Add `client_id`/`agent_id` to `NewChatThreadRead` / `NewChatThreadWithMessages` | Existing assistant-ui `ThreadRecord` shape |
| `nowing_backend/app/schemas/new_chat.py:234-313` | Add `agent_id`, `client_id`, `platform_metadata` to `NewChatRequest` with validators | Existing `@model_validator` for text/images |
| `nowing_backend/app/schemas/new_chat.py:314-350` | Add the same three fields to `RegenerateRequest` | Existing edit/reload semantics |
| `nowing_backend/app/db.py:640-730` | Add `agent_id` column to `NewChatThread`; add composite index `(workspace_id, client_id)` | Existing `client_id` column from 18.1 |
| `nowing_backend/app/routes/new_chat_routes.py:790-846` | Persist `client_id`/`agent_id` in `create_thread` | Existing permission check and error handling |
| `nowing_backend/app/routes/new_chat_routes.py:1694-1809` | Pass `client_id`, `agent_id`, `platform_metadata` from `NewChatRequest` to `stream_new_chat` | Existing streaming response setup |
| `nowing_backend/app/routes/agent_chat_routes.py` | Pass `platform_metadata` to `stream_new_chat`; already passes `client_id`/`agent_id` | Existing PAT auth and audit |
| `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:122-147` | Add `platform_metadata` and `agent_config_override` params; load/merge registry `AgentConfig` | Existing LLM bundle / credit flow |
| `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:434-452` | Pass `platform_metadata` to `build_new_chat_input_state` | Existing input state assembly |
| `nowing_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py:51-82` | Accept and render `platform_metadata` / `client_id` context block | Existing mention/report bootstrapping |
| `nowing_backend/app/tasks/chat/streaming/flows/shared/llm_bundle.py:30-55` | Optionally accept registry `AgentConfig` fields to build runtime `AgentConfig` with `system_instructions` | Existing model resolution logic |
| `nowing_backend/app/tasks/chat/streaming/agent/builder.py:21-38` | Optionally extend `build_main_agent_for_thread` to accept `enabled_tools`/`disabled_tools` for future 18.4 filtering | Existing `disabled_tools` parameter |
| `nowing_backend/app/services/memory/extraction.py:58-70` | Add `client_id` parameter to `MemoryExtractionService` | Existing extraction pipeline |
| `nowing_backend/app/services/memory/repository.py` | Accept `client_id` on memory create/upsert (coordinate with 18.6) | Existing dedup/upsert logic |

### Current State of Key Files

- `app/schemas/new_chat.py`:
  - `NewChatThreadCreate` has `workspace_id` and `visibility` only — no `client_id`/`agent_id`.
  - `NewChatRequest` has many optional fields (mentions, mode, client_platform, etc.) but no `agent_id`/`client_id`/`platform_metadata`.
  - `RegenerateRequest` mirrors `NewChatRequest` minus images and also lacks the three new fields.
- `app/db.py:640-730`:
  - `NewChatThread` already has `client_id` (Text, nullable, index) from 18.1.
  - `NewChatThread` does **not** have `agent_id`.
- `app/routes/new_chat_routes.py`:
  - `create_thread` does not persist `client_id`/`agent_id`.
  - `handle_new_chat` calls `stream_new_chat` without `client_id`/`agent_id`/`platform_metadata`.
- `app/routes/agent_chat_routes.py`:
  - `POST /threads` creates `NewChatThread` and passes `client_id` and `agent_id` (auth-derived) to the constructor.
  - `POST /threads/{id}/messages` calls `stream_new_chat` with `client_id` and `agent_id` but not `platform_metadata`.
- `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`:
  - `stream_new_chat` already accepts `client_id` and `agent_id` and calls `set_request_tenant_context`.
  - It does not load registry `AgentConfig` or merge `system_instructions` into the runtime `AgentConfig`.
  - It does not pass `platform_metadata` to `build_new_chat_input_state`.
- `app/tasks/chat/streaming/flows/new_chat/input_state.py`:
  - `build_new_chat_input_state` builds context from mentions/reports but has no `platform_metadata` block.
- `app/tasks/chat/streaming/flows/shared/llm_bundle.py`:
  - `_agent_config_from_resolved` returns runtime `AgentConfig` with `system_instructions=None` and `use_default_system_instructions=True`.
- `app/services/memory/extraction.py`:
  - `MemoryExtractionService.__init__` takes `workspace_id` and `user_id` only.
  - `Memory` model does not yet have `client_id` (pending 18.6/18.8 unless added here).

## Dependencies

### Story 18.2 depends on:
- **18.1** — public endpoints, PAT auth, `client_id` on `NewChatThread`, GUC helper, `AgentConfig` table.
- **18.3** — `agent_configs` table/registry. 18.2 can be implemented in parallel if the table exists (it does after 18.1); if 18.3 adds seed data, 18.2 tests can use the same seed.

### Stories that depend on 18.2:
- **18.4** — needs `agent_id`/`client_id` already wired to the prompt builder so it can harden prompt injection / tool allowlists.
- **18.5** — needs `NewChatThread` to carry `client_id`/`agent_id` when auto-linking `ResearchThread`.
- **18.6** — needs `client_id` propagated to memory extraction.
- **18.7** — needs thread/run attribution by `client_id`.
- **18.8** — needs `client_id` in `NewChatRequest` for rate-limit and RLS keys.

### Implementation Order Recommendation
- 18.2 must land after 18.1. It can be parallel with 18.3 if the `agent_configs` schema is stable.
- If 18.3 is not yet done, 18.2 can stub or reuse the seed `bdsai-listing-assistant` created by `scripts/seed_agent_chat_e2e.py` for tests.

## Dev Agent Guardrails

- **NEVER** accept client-supplied `client_id` or `agent_id` as authoritative without intersecting them with PAT scope (public) or thread scope (internal).
- **NEVER** use `platform_metadata` or `external_metadata` in authorization or RLS.
- **NEVER** use `client_id` as a ranking boost.
- **NEVER** allow a missing/inactive `agent_id` to fall through to the default agent — fail closed with 404.
- **ALWAYS** set `app.workspace_id` and `app.current_client_id` via `SET LOCAL` before any business query.
- **ALWAYS** keep the default Nowing chat behavior unchanged when `agent_id` is `None`.
- **ALWAYS** sanitize `platform_metadata` before rendering; no secret interpolation and no raw credential exposure.
- **ALWAYS** preserve legacy web/desktop chat request shapes.
- **ALWAYS** add regression tests for the no-`agent_id`/`client_id` path.

## Project Context Reference

- Project: Nowing
- Stack: Python 3.12, FastAPI, SQLAlchemy 2.x async, PostgreSQL 15+ with pgvector, Alembic, Pydantic v2, LangGraph chat runtime.
- Conventions:
  - Use `from __future__ import annotations`.
  - Use `AsyncSession` with `select`/`await session.execute`.
  - Use Pydantic v2 `BaseModel`, `ConfigDict(from_attributes=True)`.
  - Use FastAPI `APIRouter`, `Depends`, `HTTPException`.
  - Use Alembic migrations for schema changes.
  - Tests in `tests/unit/` and `tests/integration/`.

## Previous Story Intelligence

- Story 18.1 established `app/auth/agent_chat.py` and `app/routes/agent_chat_routes.py`. The function `_resolve_agent_config(session, client_id, agent_id)` is the canonical way to load a registry `AgentConfig` fail-closed.
- `stream_new_chat` already accepts `client_id` and `agent_id`; 18.2 only needs to add `platform_metadata` and the registry AgentConfig merge.
- `set_request_tenant_context(session, workspace_id, client_id, agent_id)` is in `app/canonical/tenant_context.py` and already sets GUCs for RLS.
- The runtime `AgentConfig` (`app.agents.chat.runtime.llm_config.AgentConfig`) already has `system_instructions`, `use_default_system_instructions`, `citations_enabled`. The prompt builder (`app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py`) already supports `custom_system_instructions` and `enabled_tool_names`/`disabled_tool_names`.
- Story 12.2 (TopCV Scraper) added extensive unit tests; apply similar test discipline.

## References

- `_bmad-output/planning-artifacts/epics.md` §Story 18.2
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-30, AD-31, AD-13, AD-14
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §2.6 Algorithm, §2.7 Untrusted Fields, §5 TM5-TM9
- `nowing_backend/app/schemas/new_chat.py` §NewChatRequest, NewChatThreadCreate, RegenerateRequest
- `nowing_backend/app/db.py` §NewChatThread
- `nowing_backend/app/routes/new_chat_routes.py` §create_thread, handle_new_chat
- `nowing_backend/app/routes/agent_chat_routes.py` §public thread/message routes
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` §stream_new_chat
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/input_state.py` §build_new_chat_input_state
- `nowing_backend/app/tasks/chat/streaming/flows/shared/llm_bundle.py` §_agent_config_from_resolved
- `nowing_backend/app/agents/chat/runtime/llm_config.py` §AgentConfig
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py` §build_main_agent_system_prompt
- `nowing_backend/app/services/memory/extraction.py` §MemoryExtractionService

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List

## Challenge Log (grill-me)

### Q1 — Already implemented?

Partial / reusable pieces exist; no full end-to-end implementation.

- `app/db.py` already has the `AgentConfig` registry table with `client_id`, `slug`, `system_instructions`, `enabled_tools`, `disabled_tools`, `is_active` (Story 18.1 / migration `78f7a9b1e85f`).
- `app/auth/agent_chat.py:_resolve_agent_config(session, client_id, agent_id)` already loads registry `AgentConfig` fail-closed (404 if missing/inactive). **Reuse this helper instead of writing a second loader.**
- `app/agents/chat/multi_agent_chat/main_agent/runtime/factory.py:create_multi_agent_chat_deep_agent` already accepts `enabled_tools`, `disabled_tools`, and `agent_config` with `system_instructions`, `use_default_system_instructions`, `citations_enabled`, `model_name`.
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/builder/compose.py:build_main_agent_system_prompt` already supports `custom_system_instructions`.
- `app/tasks/chat/streaming/flows/new_chat/orchestrator.py:stream_new_chat` already accepts `client_id` and `agent_id` and calls `set_request_tenant_context`.
- `NewChatThread` already has `client_id` (Story 18.1); `agent_id` is missing.
- Public `agent_chat_routes.py` already passes `client_id` and `agent_id` to `NewChatThread` and `stream_new_chat`; `platform_metadata` is not passed.

**Verdict:** Not a duplicate, but **must reuse** `_resolve_agent_config`, runtime `AgentConfig`, and `build_main_agent_system_prompt` instead of inventing new prompt-assembly code.

### Q2 — Simpler alternative?

- Instead of adding a new `agent_config_override` parameter to `stream_new_chat`, the orchestrator can load the registry `AgentConfig` directly and then mutate/copy the runtime `AgentConfig` returned by `load_llm_bundle` (it is a dataclass with the needed fields: `system_instructions`, `use_default_system_instructions`, `citations_enabled`, `model_name`). This avoids a parallel `agent_config` object model.
- Extend `build_main_agent_for_thread` (or pass through the orchestrator) to forward `enabled_tools`/`disabled_tools` from the registry to `create_multi_agent_chat_deep_agent`; the factory already accepts them.
- `platform_metadata` can be rendered as a plain XML/JSON context block inside `build_new_chat_input_state` rather than a dedicated `prompt.py` file (no such file exists in the new-chat flow).

**Verdict:** No HALT; prefer reusing existing runtime `AgentConfig` and existing `build_main_agent_for_thread` parameter surface.

### Q3 — Edge cases the spec misses (Pattern 3)

- [ ] Boundary: `platform_metadata` max size (keys, nested depth, total JSON size) — add schema bound or 422.
- [ ] Boundary: `agent_id`/`client_id` length/pattern (slug) — reuse `^[a-z0-9][a-z0-9-._]*$` from `AgentChatThreadCreate`.
- [ ] Null/empty: `agent_id` set but `client_id` omitted in `NewChatRequest` for internal web — reject or default to the agent's `client_id`.
- [ ] Null/empty: `client_id`/`agent_id` set in a web/desktop `NewChatRequest` (untrusted for internal) — ignore or reject; internal users cannot claim a vertical client.
- [ ] Consistency: `NewChatRequest.client_id`/`agent_id` differs from the `NewChatThread` the user is messaging — reject (cannot switch tenant/agent mid-thread) or intersect.
- [ ] Consistency: `RegenerateRequest` without the three new fields must inherit from the thread row.
- [ ] Concurrent: two simultaneous `POST /threads` with same `client_id`/`agent_id` — idempotent via unique constraints, not a race.
- [ ] Default agent: `client_id` present (public PAT scope) but `agent_id` absent — AC says default Nowing agent; consider whether a client-scoped default agent is needed later.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] `AgentConfig` registry query throws DB error → 503 or 500 with request_id; must not leak SQL.
- [ ] `AgentConfig` found but `is_active=False` → 404 (fail-closed per AD-30).
- [ ] `agent_id` not a valid slug → 422.
- [ ] `load_llm_bundle` returns an error after AgentConfig is loaded → surface existing SSE error frame.
- [ ] `platform_metadata` contains `{`/`}` and `system_instructions` uses `.format()` → risk of format string crash or secret interpolation. **Mitigation:** escape or avoid `.format()` for `custom_system_instructions` until Story 18.4 hardens it.
- [ ] `client_id` in `NewChatRequest` does not match `NewChatThread.client_id` → 403/400; do not silently continue.
- [ ] RLS GUC `app.current_client_id` not reset before first DB query in `stream_new_chat` → cross-tenant memory recall. **Mitigation:** call `set_request_tenant_context` immediately after opening the session (already done, but verify for resume/regenerate).
- [ ] `MemoryExtractionService` does not accept `client_id` yet → extracted memories will not be tagged in 18.2; must be addressed by 18.6.

### Triage

- No critical duplicate found; continue with test-first ATDD.
- Two **non-critical** spec gaps to add to test skeleton: web-vs-public authority for `client_id`/`agent_id`, and `platform_metadata` bounds.
- One **future-critical** security item: secret interpolation in `system_instructions` is tracked in Story 18.4; 18.2 must not make it worse.

## Story Completion Status

- [x] Epic and story context analyzed
- [x] Architecture, PRD, UX, and threat model reviewed
- [x] Existing code files inspected
- [x] Dependencies and implementation order documented
- [x] Open decisions resolved with defaults
- [x] Comprehensive developer context and guardrails captured
- [ ] Implementation pending
- [ ] Tests pending

**Status:** ready-for-dev

**Ultimate context engine analysis completed - comprehensive developer guide created.**
