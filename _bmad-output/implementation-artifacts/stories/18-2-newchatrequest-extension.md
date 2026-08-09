# Story 18.2: `NewChatRequest` Extension

Status: ready-for-dev

## Story

As a chat system,
I want to accept `agent_id`, `client_id`, and `platform_metadata` in chat requests,
so that agents can be configured per vertical client and context can be forwarded.

## Acceptance Criteria

1. **Given** a chat request with `agent_id`, **When** processed, **Then** the system loads the corresponding `AgentConfig` and injects `system_instructions` into the prompt.
2. **Given** a chat request with `client_id`, **When** processed, **Then** all memory recall and storage is tagged with `client_id`.
3. **Given** `platform_metadata` in the request, **When** processed, **Then** the metadata is forwarded to the chat prompt context.
4. **Given** no `agent_id`, **When** processed, **Then** the default Nowing chat agent is used (backward compatible).

## Tasks / Subtasks

- [ ] Extend `NewChatRequest` schema (AC: #1, #2, #3, #4)
  - [ ] Add optional `agent_id: str | None`, `client_id: str | None`, `platform_metadata: dict | None` to `NewChatRequest` (`app/schemas/new_chat.py:234-313`)
  - [ ] Add validator: if `agent_id` is set, `client_id` must also be set or match the agent's `client_id`
  - [ ] Ensure `client_id`/`platform_metadata` do not affect authz (untrusted per `epic-18-pat-scope-rls-threat-model.md §2.7`)
- [ ] Extend thread creation and resume schemas (AC: #2)
  - [ ] Add `client_id` and `agent_id` columns to `NewChatThread` (`app/db.py:639-759`) and `NewChatThreadCreate` (`app/schemas/new_chat.py:85-91`)
  - [ ] Add migration to store `client_id` on `new_chat_threads` with index `(workspace_id, client_id)`
  - [ ] Update internal chat route `POST /threads` (`app/routes/new_chat_routes.py:790-846`) to persist `client_id` and `agent_id`
- [ ] Wire chat orchestrator (AC: #1, #3, #4)
  - [ ] Update `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` to read `agent_id`, `client_id`, `platform_metadata` from `NewChatRequest`
  - [ ] Load `AgentConfig` by `agent_id`; on missing/inactive, fail closed with 404 (per `AD-30`)
  - [ ] When `agent_id` is absent, continue using the default Nowing system prompt and tool set
  - [ ] Render `platform_metadata` as a trusted-but-untrusted context block in the prompt (do not interpolate secrets; no raw credential exposure)
- [ ] Memory tagging on chat input (AC: #2)
  - [ ] Pass `client_id` through to `MemoryExtractionService` so auto-extracted memories get `client_id` set (Story 18.6 / 18.8)
  - [ ] Update `app/services/memory/extraction.py` and `app/services/memory/repository.py` to accept and persist `client_id`
- [ ] Backward compatibility (AC: #4)
  - [ ] Keep existing web/desktop chat requests unchanged; `agent_id` and `client_id` default to `None`
  - [ ] Regression test existing new-chat flows with `client_id`/`agent_id` unset
- [ ] Tests
  - [ ] Unit test `NewChatRequest` validator with/without `agent_id`/`client_id`
  - [ ] Unit test orchestrator loads correct `AgentConfig` and injects system instructions
  - [ ] Integration test `POST /threads` and `POST /new_chat` with `client_id`/`platform_metadata` preserved end-to-end

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-29` (`ARCHITECTURE-SPINE.md:727-737`) — public surface allows `client_id`/`agent_id` in request, but client-supplied IDs are not authoritative; they are intersected with PAT scope before use.
  - `AD-30` (`ARCHITECTURE-SPINE.md:739-748`) — `AgentConfig` registry is platform-superuser managed; missing/inactive `agent_id` → 404 fail-closed.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is a hard isolation key; `NewChatThread` and downstream memory must carry it.
  - `epic-18-pat-scope-rls-threat-model.md §2.7` — `client_id`, `agent_id`, `platform_metadata`, and `external_metadata` are untrusted and must not be used for authorization or RLS.
  - `AD-13` (`ARCHITECTURE-SPINE.md:274-282`) — `ResearchThread` continuity context may be linked from public chat.

- Source tree components to touch
  - `nowing_backend/app/schemas/new_chat.py:234-313` — `NewChatRequest`
  - `nowing_backend/app/schemas/new_chat.py:85-91` — `NewChatThreadCreate`
  - `nowing_backend/app/db.py:639-759` — `NewChatThread` model
  - `nowing_backend/app/db.py:2089-2137` — `ResearchThread` model
  - `nowing_backend/app/routes/new_chat_routes.py:790-846` — `create_thread`
  - `nowing_backend/app/routes/new_chat_routes.py:1694-1823` — `handle_new_chat`
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — new-chat flow
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/prompt.py` — prompt assembly
  - `nowing_backend/app/services/memory/extraction.py` — `MemoryExtractionService`
  - `nowing_backend/app/services/memory/repository.py` — memory persistence
  - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` — memory recall
  - `nowing_backend/alembic/versions/` — migration for `new_chat_threads.client_id` and `agent_id` columns

- Testing standards summary
  - Unit tests in `tests/unit/schemas/test_new_chat.py` and `tests/unit/tasks/chat/test_new_chat_orchestrator.py`
  - Integration tests in `tests/integration/routes/test_new_chat_routes.py` (backward compatible) and `tests/integration/api/test_agent_chat_pat_matrix.py` (vertical client path)
  - Assert default agent is used when `agent_id` is absent
  - Assert `platform_metadata` appears in prompt context but does not override system instructions

### Project Structure Notes

- Alignment with unified project structure
  - Schema changes are minimal additive fields on existing `NewChatRequest`/`NewChatThread`
  - Orchestrator changes stay in the existing streaming flow package

- Detected conflicts or variances
  - `NewChatRequest` already has many optional fields; adding `agent_id`/`client_id`/`platform_metadata` is additive and backward compatible.
  - `client_id` on `NewChatThread` must be indexed with `workspace_id` for composite RLS; the same column is referenced by `ResearchThread` linkage.
  - `platform_metadata` keys are free-form; schema should use `dict` and downstream code must sanitize before rendering (no secret interpolation).

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.2]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-29, AD-30, AD-31]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md` §2.6 Algorithm, §2.7 Untrusted Fields, §5 TM5-TM9]
- [Source: `nowing_backend/app/schemas/new_chat.py` §NewChatRequest, NewChatThreadCreate]
- [Source: `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py`]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List