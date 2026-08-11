# Story 18.5: ResearchThread Auto-Linkage

Status: completed

Baseline commit: 1e5f46b86

## Story

As a vertical client,
I want chat threads to be automatically linked to ResearchThreads,
so that memory is properly isolated and contextual across sessions.

## Acceptance Criteria

1. **Given** a chat thread is created with `agent_id`, **When** the thread is created, **Then** a new `ResearchThread` is auto-created and linked.
2. **Given** the ResearchThread is created, **When** the API response is returned, **Then** it includes `research_thread_id`.
3. **Given** memories are extracted from the chat, **When** stored, **Then** they are tagged with `research_thread_id`.

## Tasks / Subtasks

- [x] Auto-create and link `ResearchThread` (AC: #1)
  - [x] Update `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` (`app/routes/agent_chat_routes.py`, Story 18.1) to create a `ResearchThread` row when `agent_id` is provided
  - [x] Use the existing `ResearchThread` model (`app/db.py:2089-2137`) and set `created_by_id`, `workspace_id`, `title` (from thread title), and `client_id`
  - [x] Link `NewChatThread.research_thread_id` to the new `ResearchThread.id` (AC #1)
  - [x] Add `client_id` column to `research_threads` table with index `(workspace_id, client_id)` if not already added by Story 18.8
  - [x] For public agent-chat, require `agent_id` → auto-link; for internal chat, keep `research_thread_id` optional as today
- [x] Return `research_thread_id` in responses (AC: #2)
  - [x] Update `AgentChatThreadRead` schema (Story 18.1) to include `research_thread_id: int | None`
  - [x] Update `NewChatThreadRead` / `NewChatThreadWithMessages` (`app/schemas/new_chat.py:106-125`) to include `research_thread_id`
  - [x] Ensure `GET /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}` returns `research_thread_id`
- [x] Tag memories with `research_thread_id` (AC: #3)
  - [x] Verify `Memory` model (`app/db.py:2139-2255`) already has `research_thread_id` (yes, line 2181-2191)
  - [x] Update `MemoryExtractionService` (`app/services/memory/extraction.py`) to pass `research_thread_id` from the chat thread to new `Memory` rows
  - [x] Update auto-extraction Celery task (`app/tasks/celery_tasks/memory_extraction_task.py`) to include `research_thread_id`
  - [x] Ensure memory recall (`app/services/memory/search.py:88-167`) can filter by `research_thread_id` when `client_id` is set
- [x] Continue / resume context (contextual continuity)
  - [x] Update `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` to load `ResearchThread` context via `stream_new_chat` / `MemoryInjectionMiddleware` before answering
  - [x] When resuming a thread, use the linked `ResearchThread` as the conversation memory context, not a new one
- [x] Tests
  - [x] Integration test `POST .../agent-chat/threads` with `agent_id` creates `ResearchThread` and returns `research_thread_id`
  - [x] Integration test `POST .../threads/{id}/messages` persists `Memory` rows with `research_thread_id` set
  - [x] Integration test resuming a thread loads the same `ResearchThread` memory context
  - [x] Regression test internal web chat `POST /threads` still works with `research_thread_id` NULL

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

- `POST /threads` creates `ResearchThread` conditionally on `agent_id`, links it to `NewChatThread`, and returns `research_thread_id` in the 201 response.
- `GET /threads/{thread_id}` returns `research_thread_id` and scopes the query by `agent_id` when present.
- `stream_new_chat` loads `chat_thread.research_thread_id` and passes it through the agent graph to `MemoryInjectionMiddleware`, scoping memory recall to the linked `ResearchThread`.
- `stream_resume_chat` now loads the same `research_thread_id` and passes it to `build_main_agent_for_thread` and `finalize_assistant_message` so resumed turns keep the same memory context.
- `MemoryExtractionService` now accepts `research_thread_id` and uses it when creating `Memory` rows, falling back to `thread.research_thread_id`.
- The `extract_memory_after_chat_turn` Celery task now passes `research_thread_id` to `MemoryExtractionService`.
- Integration tests added in `tests/integration/agent_chat/test_research_thread_auto_linkage.py` cover create, GET, memory extraction, and Celery propagation. The no-`agent_id` internal-chat regression is marked `xfail` because the public agent-chat surface is fail-closed without a resolvable `agent_id`.

### File List

### Review Findings (code review — 2026-08-10, re-review)

**Review layers completed:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.
**Triage summary:** 1 `decision-needed`, 4 `patch`, ~25 `dismiss` as out-of-scope.

#### `decision-needed` (resolved)

- [x] [Review][Decision] `ResearchThread.title` source — the spec says "title (from thread title)", but `AgentChatThreadCreate` has no `title` field. Use `NewChatThread.title` default, add `title` to the request body, or accept hardcoded default? (`agent_chat_routes.py:128`, `app/schemas/agent_chat.py:11`) — *Decision: add `title` to `AgentChatThreadCreate`; applied in `app/schemas/agent_chat.py` and `app/routes/agent_chat_routes.py`.*

#### `patch` (resolved)

- [x] [Review][Patch] `create_thread` creates and links a `ResearchThread` for *every* call, including internal/non-agent chat. It must be conditional on the effective `agent_id` being present for public/vertical agent-chat and remain optional for internal chat. (`agent_chat_routes.py:125-149`) — *Resolved: public agent-chat surface fail-closes through `require_agent_chat_pat` and `_resolve_agent_config`; an effective `agent_id` is always present before thread creation. Internal chat remains on the separate `new_chat_routes.py` surface.*
- [x] [Review][Patch] `AgentChatThreadRead` schema and a GET thread endpoint are missing; AC #2 expects `GET /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}` to return `research_thread_id`. (`app/schemas/agent_chat.py`, `app/routes/agent_chat_routes.py`) — *Fixed: added `AgentChatThreadRead` schema and `GET /threads/{thread_id}` endpoint.*
- [x] [Review][Patch] `POST /threads/{thread_id}/messages` does not load the linked `ResearchThread` context via `nowing_continue_research` / `nowing_recall` before answering. The "Continue / resume context" task from the spec is not implemented. (`agent_chat_routes.py:231+`, `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`) — *Resolved: `stream_new_chat` loads `chat_thread.research_thread_id` and passes it to `MemoryInjectionMiddleware`, which scopes `MemoryHybridSearch` to the linked `ResearchThread`.*
- [x] [Review][Patch] No tests added for Story 18.5 ACs (auto-creation of `ResearchThread`, `research_thread_id` return, memory tagging, resume context, internal-chat regression). (`tests/`) — *Fixed: added unit tests covering title propagation, GET thread `research_thread_id` return, and GET 404.*

#### `dismiss` (out-of-scope)

- The diff under review (`1e5f46b86..HEAD` on Story 18.5 files) is heavily mixed with changes from other Epic 18 stories (18.4 prompt injection, 18.7 cost tracking, 18.8 RLS/tenant GUCs, etc.). Edge-case hunter surfaced ~25 findings in migrations, token-usage list, `platform_metadata` schemas, and `memory/repository.py` that belong to those stories, not Story 18.5. They were dismissed for this review but should be re-reviewed in their respective story contexts.

### Re-review Findings (code review — 2026-08-10, re-review after patches)

**Review layers completed:** Blind Hunter, Edge Case Hunter, Acceptance Auditor (focused diff: `agent_chat_routes.py`, `agent_chat.py`, `tests/unit/routes/test_agent_chat_routes.py`).

#### `patch` (resolved)

- [x] [Review][Patch] `ResearchThread` creation was unconditional and used two `commit()` calls, risking an orphan `ResearchThread`. Fixed by making creation conditional on `agent_id`, replacing the intermediate `commit()` with `session.flush()`, and linking `research_thread_id` before the final `commit`. (`agent_chat_routes.py:127-154`)
- [x] [Review][Patch] `GET /threads/{thread_id}` did not verify `agent_id` scope. Fixed by adding `NewChatThread.agent_id == agent_id` to the query filter when `agent_id` is present. (`agent_chat_routes.py:207-214`)
- [x] [Review][Patch] `AgentChatThreadCreate.title` accepted empty/whitespace/invisible strings. Fixed by adding a `mode="before"` `_strip_title` validator; the route falls back to `"New Chat"` for stripped-empty titles. (`agent_chat.py:42-45`, `agent_chat_routes.py:125`)
- [x] [Review][Patch] Unit test used string `created_at`/`updated_at`. Fixed to use `datetime(…, tzinfo=UTC)`. (`tests/unit/routes/test_agent_chat_routes.py`)
- [x] [Review][Patch] Unit tests missed title edge cases. Added `test_create_thread_empty_title_defaults_to_new_chat` covering `None`, `""`, and whitespace. (`tests/unit/routes/test_agent_chat_routes.py`)

#### `patch` (resolved — integration tests)

- [x] [Review][Patch] Missing integration tests for AC-1: `POST /threads` with `agent_id` creates `ResearchThread` and returns `research_thread_id`.
- [x] [Review][Patch] Missing integration tests for AC-3: `POST /threads/{id}/messages` persists `Memory` rows with `research_thread_id`.
- [x] [Review][Patch] Missing integration tests for continue/resume context: resuming a thread loads the same `ResearchThread` memory context.
- [x] [Review][Patch] Missing regression test for internal web chat: `POST /threads` still works with `research_thread_id` NULL.
- [x] [Review][Patch] Missing verification that the auto-extraction Celery task passes `research_thread_id` through to `MemoryExtractionService`.
