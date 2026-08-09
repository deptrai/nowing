# Story 18.5: ResearchThread Auto-Linkage

Status: ready-for-dev

## Story

As a vertical client,
I want chat threads to be automatically linked to ResearchThreads,
so that memory is properly isolated and contextual across sessions.

## Acceptance Criteria

1. **Given** a chat thread is created with `agent_id`, **When** the thread is created, **Then** a new `ResearchThread` is auto-created and linked.
2. **Given** the ResearchThread is created, **When** the API response is returned, **Then** it includes `research_thread_id`.
3. **Given** memories are extracted from the chat, **When** stored, **Then** they are tagged with `research_thread_id`.

## Tasks / Subtasks

- [ ] Auto-create and link `ResearchThread` (AC: #1)
  - [ ] Update `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` (`app/routes/agent_chat_routes.py`, Story 18.1) to create a `ResearchThread` row when `agent_id` is provided
  - [ ] Use the existing `ResearchThread` model (`app/db.py:2089-2137`) and set `created_by_id`, `workspace_id`, `title` (from thread title), and `client_id`
  - [ ] Link `NewChatThread.research_thread_id` to the new `ResearchThread.id` (AC #1)
  - [ ] Add `client_id` column to `research_threads` table with index `(workspace_id, client_id)` if not already added by Story 18.8
  - [ ] For public agent-chat, require `agent_id` → auto-link; for internal chat, keep `research_thread_id` optional as today
- [ ] Return `research_thread_id` in responses (AC: #2)
  - [ ] Update `AgentChatThreadRead` schema (Story 18.1) to include `research_thread_id: int | None`
  - [ ] Update `NewChatThreadRead` / `NewChatThreadWithMessages` (`app/schemas/new_chat.py:106-125`) to include `research_thread_id`
  - [ ] Ensure `GET /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}` returns `research_thread_id`
- [ ] Tag memories with `research_thread_id` (AC: #3)
  - [ ] Verify `Memory` model (`app/db.py:2139-2255`) already has `research_thread_id` (yes, line 2181-2191)
  - [ ] Update `MemoryExtractionService` (`app/services/memory/extraction.py`) to pass `research_thread_id` from the chat thread to new `Memory` rows
  - [ ] Update auto-extraction Celery task (`app/tasks/memory/extract.py` or similar) to include `research_thread_id`
  - [ ] Ensure memory recall (`app/services/memory/search.py:88-167`) can filter by `research_thread_id` when `client_id` is set
- [ ] Continue / resume context (contextual continuity)
  - [ ] Update `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` to load `ResearchThread` context via `nowing_continue_research` before answering
  - [ ] When resuming a thread, use the linked `ResearchThread` as the conversation memory context, not a new one
- [ ] Tests
  - [ ] Integration test `POST .../agent-chat/threads` with `agent_id` creates `ResearchThread` and returns `research_thread_id`
  - [ ] Integration test `POST .../threads/{id}/messages` persists `Memory` rows with `research_thread_id` set
  - [ ] Integration test resuming a thread loads the same `ResearchThread` memory context
  - [ ] Regression test internal web chat `POST /threads` still works with `research_thread_id` NULL

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-13` (`ARCHITECTURE-SPINE.md:274-282`) — `ResearchThread` is continuation context; links 1-n `ChatThread` via `new_chat_threads.research_thread_id`; public/vertical agent-chat may create and link `ResearchThread` instances only through the AD-29 public surface.
  - `AD-31` (`ARCHITECTURE-SPINE.md:750-764`) — `client_id` is a hard isolation key; `ResearchThread` and `Memory` must carry it when the chat is vertical-client chat.
  - `AD-11` (`ARCHITECTURE-SPINE.md:238-261`) — `Memory` has `research_thread_id` as nullable FK; `app/services/memory/search.py` already filters by it.
  - `AD-30` (`ARCHITECTURE-SPINE.md:739-748`) — `AgentConfig` loaded before this step.

- Source tree components to touch
  - `nowing_backend/alembic/versions/` — migration for `research_threads.client_id` (if not in 18.8)
  - `nowing_backend/app/db.py:2089-2137` — `ResearchThread`
  - `nowing_backend/app/db.py:639-759` — `NewChatThread` (research_thread_id already exists)
  - `nowing_backend/app/db.py:2139-2255` — `Memory` (research_thread_id already exists)
  - `nowing_backend/app/schemas/agent_chat.py` — `AgentChatThreadRead`
  - `nowing_backend/app/schemas/new_chat.py:106-125` — `NewChatThreadRead`, `NewChatThreadWithMessages`
  - `nowing_backend/app/routes/agent_chat_routes.py` (Story 18.1) — thread creation route
  - `nowing_backend/app/services/memory/extraction.py` — `MemoryExtractionService`
  - `nowing_backend/app/services/memory/repository.py` — memory create
  - `nowing_backend/app/tasks/memory/extract.py` (or `app/celery_app.py:261-304` memory task) — Celery extraction
  - `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — load `ResearchThread` context
  - `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` — memory recall

- Testing standards summary
  - Integration tests in `tests/integration/routes/test_agent_chat_pat_matrix.py` (H1 resume path)
  - Integration tests in `tests/integration/services/test_memory_extraction.py` for `research_thread_id` tagging
  - Assert `research_thread_id` is returned on public thread create
  - Assert memory recall for a vertical client only sees `client_id` + `research_thread_id` scoped memories

### Project Structure Notes

- Alignment with unified project structure
  - `ResearchThread` and `NewChatThread` are existing tables; this story only adds auto-linking and `client_id` tagging.
  - Extraction service already creates `Memory` rows; pass `research_thread_id` from the thread context.

- Detected conflicts or variances
  - `NewChatThread.research_thread_id` is currently nullable and set manually; public agent-chat should auto-create when `agent_id` is present, but internal chat can still allow manual linking.
  - `ResearchThread.client_id` does not exist yet; this story and 18.6/18.8 may share the migration. Coordinate with Story 18.8 to avoid duplicate migrations.
  - Memory extraction runs in Celery; the task must receive `research_thread_id` and `client_id` explicitly because ambient GUCs do not survive the queue hop.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` §Story 18.5]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-13, AD-31]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §FR-33 / FR-56]
- [Source: `nowing_backend/app/db.py` §ResearchThread, NewChatThread, Memory]
- [Source: `nowing_backend/app/services/memory/search.py` §MemoryHybridSearch.search]
- [Source: `nowing_backend/app/services/memory/extraction.py`]

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

### Completion Notes List

### File List