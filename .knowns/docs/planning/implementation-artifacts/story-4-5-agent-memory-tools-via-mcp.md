---
title: Story 4.5 — Agent Memory Tools via MCP
description: ''
createdAt: '2026-07-28T12:47:48.503Z'
updatedAt: '2026-07-28T15:17:33.451Z'
tags:
  - bmad
  - bmad-source-bmad-output-implementation-artifacts-4-5-agent-memory-tools-via-mcp-md
---

---
baseline_commit: 79cd5b078bba38863f237f66db52bbfcb5d694af
story_key: 4-5-agent-memory-tools-via-mcp
status: done
---

# Story 4.5 — Agent Memory Tools via MCP

**Story ID:** 4.5  
**Epic:** Epic 4 — Chat & Agents  
**Title:** Agent Memory Tools via MCP  
**Status:** done  
**Priority:** P1  
**Source artifacts:**
- PRD: `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (FR-32, FR-33, FR-34, UJ-6, OQ-4)
- Epics: `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md` (Story 4.5)
- Architecture: `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-7, AD-11, AD-12, AD-14)
- Previous story: `/Users/luisphan/Documents/nowing/_bmad-output/implementation-artifacts/3-8-long-term-research-memory.md`

---

## 1. Goal

Expose Story 3.8’s unified long-term memory to MCP clients through `nowing_remember`, `nowing_recall`, `nowing_update_fact`, and `nowing_continue_research`. Add an async/Celery `MemoryExtractionService` that automatically turns assistant turns into durable memory, so agents do not lose context between sessions.

This story unblocks **Story 4.6** (research continuity) and **Story 6.5** (memory-driven automations).

---

## 2. User Story & Acceptance Criteria

> As an AI agent builder,  
> I want Claude/Cursor/OpenCode to remember and recall workspace context through Nowing MCP tools,  
> So that agents don’t lose context between sessions.

### AC-1: `nowing_remember` saves a memory
**Given** the MCP server is configured and `nowing_remember` is registered in `nowing_mcp/mcp_server/features/memory.py`  
**When** an agent calls `nowing_remember(content=..., type=...)` with an active workspace selected  
**Then** the tool calls `POST /workspaces/{id}/memories` and returns the saved memory id  
**And** the new memory is searchable with `nowing_recall`.

### AC-2: `nowing_recall` retrieves relevant memories
**Given** the agent has `memory:read` permission in the active workspace  
**When** the agent calls `nowing_recall(query=..., top_k=...)`  
**Then** the tool calls `POST /workspaces/{id}/memories/search` and returns a compact ranked list of relevant memories.

### AC-3: `nowing_update_fact` corrects a memory
**Given** the agent has `memory:update` permission and a `memory_id`  
**When** the agent calls `nowing_update_fact(memory_id=..., corrected_content=...)`  
**Then** the tool calls `PATCH /memories/{id}`, updates the memory, and preserves the old version in `MemoryVersion`.

### AC-4: Auto-extract memory after each assistant turn
**Given** an assistant message is persisted by `finalize_assistant_turn`  
**When** `finalize_assistant_message` completes  
**Then** a Celery task runs `MemoryExtractionService` to extract facts from the user + assistant messages  
**And** only facts with `confidence >= threshold` (default 0.7) are saved  
**And** near-duplicate memories (vector similarity > 0.92) are updated rather than inserted  
**And** each extraction records `TokenUsage.usage_type = "memory_create"`.

### AC-5: Workspace owners can disable auto-extraction
**Given** a workspace has `memory_auto_extract_enabled = False`  
**When** an assistant turn finalizes  
**Then** no Celery extraction task is enqueued for that workspace.

### AC-6: Catalog and selfcheck stay in sync
**Given** `app/mcp_tools.py` already lists the four memory tools  
**When** `nowing_mcp/mcp_server/selfcheck.py` runs  
**Then** `EXPECTED_TOOLS` matches `MCP_TOOL_NAMES` and the offline manifest is healthy.

---

## 3. Technical Context

### 3.1 Backend memory system (already done — Story 3.8)

- **Models & enums:** `Memory`, `MemoryVersion`, `MemoryRelation`, `ResearchThread`, `MemoryType`, `MemorySourceType`, `MemoryRelationType` in `nowing_backend/app/db.py`.  
  [Source: `nowing_backend/app/db.py`]
- **Permissions:** `Permission.MEMORY_CREATE / READ / UPDATE / DELETE` and `DEFAULT_ROLE_PERMISSIONS` already wired. Editor has create/read/update; Viewer has read; Owner has full access.  
  [Source: `nowing_backend/app/db.py`]
- **Routes:** `nowing_backend/app/routes/memories_routes.py` already exposes:
  - `POST /workspaces/{id}/memories` → `create_memory`
  - `POST /workspaces/{id}/memories/search` → `search_memory`
  - `PATCH /memories/{id}` → `update_memory`
  - `DELETE /memories/{id}` → `delete_memory`  
  [Source: `nowing_backend/app/routes/memories_routes.py`]
- **Schemas:** `MemoryCreate`, `MemoryUpdate`, `MemoryRead`, `MemorySearchRequest`, `MemorySearchResponse`, `MemorySearchHit` in `nowing_backend/app/schemas/memory.py`.  
  [Source: `nowing_backend/app/schemas/memory.py`]
- **Repository & search:** `app/services/memory/repository.py` (`MemoryRepository.create_memory` with dedup + token usage) and `app/services/memory/search.py` (`MemoryHybridSearch` with RRF).  
  [Source: `nowing_backend/app/services/memory/repository.py`, `nowing_backend/app/services/memory/search.py`]
- **Catalog:** `app/mcp_tools.py` already declares `McpToolGroup.MEMORY` and the four memory tools.  
  [Source: `nowing_backend/app/mcp_tools.py`]

> **Important detail:** `MemoryHybridSearch.search` currently ignores the `type` field carried by `MemorySearchRequest` and `MemorySearchHit.score` is hardcoded to `0.0` in `memories_routes.py`. For `nowing_recall` filtering you must thread `type` through the search call and optionally surface real scores.

> **Important detail:** `MemoryRepository._find_near_duplicate` returns a duplicate only when vector distance `< 0.08` **and** the content matches exactly. For auto-extraction, semantic near-duplicates should update the existing row per AD-14 (`similarity > 0.92` → update, not insert). Add an `update_on_duplicate: bool = False` parameter to `create_memory` so manual/agent calls keep current exact-match behavior while extraction can opt into semantic upsert.

### 3.2 MCP server patterns (already done — Story 2.5)

- `nowing_mcp/mcp_server/server.py` builds a `WorkspaceAwareFastMCP` subclass that filters `tools/list` and guards `call_tool` against `GET /workspaces/{id}/mcp-tools`.  
  [Source: `nowing_mcp/mcp_server/server.py`]
- `nowing_mcp/mcp_server/core/client.py` (`NowingClient.request`) is the authenticated REST client.  
  [Source: `nowing_mcp/mcp_server/core/client.py`]
- `nowing_mcp/mcp_server/core/workspace_context.py` resolves workspace names/ids and tracks active workspace per caller. Every workspace-scoped tool accepts `workspace: WorkspaceParam` (str|None).  
  [Source: `nowing_mcp/mcp_server/core/workspace_context.py`]
- Feature packages live under `nowing_mcp/mcp_server/features/`. Follow `knowledge_base` (`__init__.py` + `search_tools.py` + `document_tools.py` + `annotations.py`) as the canonical pattern.  
  [Source: `nowing_mcp/mcp_server/features/knowledge_base/__init__.py`]
- `selfcheck.py` validates the offline manifest. `EXPECTED_TOOLS` must equal `MCP_TOOL_NAMES` from `app.mcp_tools`.  
  [Source: `nowing_mcp/mcp_server/selfcheck.py`]

### 3.3 Chat finalization hook

`finalize_assistant_message` in `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py` runs inside the streaming `finally` block ( shielded `anyio.CancelScope`). After it awaits `finalize_assistant_turn`, enqueue the extraction Celery task. Keep this best-effort: wrap the `.delay()` call in `try/except` and log, never raise.

Inputs available in scope:
- `stream_result.assistant_message_id`
- `stream_result.turn_id`
- `chat_id`
- `workspace_id`
- `user_id`

[Source: `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`]

### 3.4 Celery, billing, and token usage

- `nowing_backend/app/tasks/celery_tasks/__init__.py` provides `run_async_celery_task` and `get_celery_session_maker`.  
  [Source: `nowing_backend/app/tasks/celery_tasks/__init__.py`]
- `nowing_backend/app/celery_app.py` lists task modules in `include=[...]`. Any new task file must be added there.  
  [Source: `nowing_backend/app/celery_app.py`]
- `token_tracking_service.scoped_turn()` returns a fresh `TurnTokenAccumulator`. Use it around the extraction LLM call, then `record_token_usage(..., usage_type="memory_create", message_id=assistant_message.id)`.  
  [Source: `nowing_backend/app/services/token_tracking_service.py`]
- `get_agent_llm(session, workspace_id, disable_streaming=True)` resolves the workspace’s chat model.  
  [Source: `nowing_backend/app/services/llm_service.py`]
- `embed_texts` / `embed_text` in `app/utils/document_converters.py` are the thread-safe drop-in embedding helpers.  
  [Source: `nowing_backend/app/utils/document_converters.py`]

### 3.5 Per-workspace auto-extract flag

AD-14 says a workspace can enable/disable auto-extraction. Add a `memory_auto_extract_enabled` boolean column to `Workspace` with default `True`. Also add corresponding env-level defaults in `app.config` (`MEMORY_AUTO_EXTRACT_ENABLED`, `MEMORY_AUTO_EXTRACT_CONFIDENCE`, `MEMORY_AUTO_EXTRACT_MAX_ITEMS`) so self-hosters can cheaply disable globally.

To keep the API contract consistent, expose the column in `WorkspaceRead` and `WorkspaceUpdate` and in the frontend `workspace.types.ts` schema.

---

## 4. Scope

### In scope
- `nowing_mcp/mcp_server/features/memory.py` registering `nowing_remember`, `nowing_recall`, `nowing_update_fact`, `nowing_continue_research`.
- `nowing_mcp/mcp_server/selfcheck.py` updated and passing.
- `MemoryExtractionService` in `app/services/memory/extraction.py`.
- Celery task `extract_memory_after_chat_turn` in `app/tasks/celery_tasks/memory_extraction_task.py`.
- Hook in `finalize_assistant_message`.
- `Workspace.memory_auto_extract_enabled` column + migration + API/frontend schema updates.
- `MemoryHybridSearch` `type` filter and `MemoryRepository` semantic dedup option.
- Backend and MCP tests.

### Out of scope
- Full `ResearchThread` CRUD / chat-thread-to-research-thread resolution (Story 4.6).
- Memory browser / research timeline UI.
- `memory_change` automation trigger (Story 6.5).
- Dedicated cheap “extraction” model role — reuse the workspace chat model for now.

---

## 5. Implementation Plan

### Step 1 — Backend: extraction service & Celery

1. **Migration** `nowing_backend/alembic/versions/179_add_workspace_memory_auto_extract.py`:
   - Add `memory_auto_extract_enabled` Boolean to `workspaces`, `nullable=False`, `server_default="true"`.
   - Backfill existing rows to `true`.

2. **Model** `nowing_backend/app/db.py`:
   - Add `memory_auto_extract_enabled = Column(Boolean, nullable=False, default=True, server_default="true")` to `Workspace`.

3. **Schemas** `nowing_backend/app/schemas/workspace.py` and `nowing_web/contracts/types/workspace.types.ts`:
   - Add `memory_auto_extract_enabled: bool | None = None` to `WorkspaceUpdate`.
   - Add `memory_auto_extract_enabled: bool` to `WorkspaceRead`.
   - Add the field to the Zod `workspace` schema and `updateWorkspaceRequest` pick list.

4. **Config** `nowing_backend/app/config/__init__.py`:
   - Add defaults:
     ```python
     MEMORY_AUTO_EXTRACT_ENABLED = os.getenv("MEMORY_AUTO_EXTRACT_ENABLED", "true").strip().lower() == "true"
     MEMORY_AUTO_EXTRACT_CONFIDENCE = float(os.getenv("MEMORY_AUTO_EXTRACT_CONFIDENCE", "0.7"))
     MEMORY_AUTO_EXTRACT_MAX_ITEMS = int(os.getenv("MEMORY_AUTO_EXTRACT_MAX_ITEMS", "3"))
     ```

5. **Repository dedup** `nowing_backend/app/services/memory/repository.py`:
   - Change `create_memory` signature to accept `update_on_duplicate: bool = False`.
   - In `_find_near_duplicate`, keep the exact-match branch for the default path.
   - When `update_on_duplicate=True` and a near-duplicate (distance < 0.08) is found, call `self.update_memory(existing.id, corrected_content=content, corrected_by_id=created_by_id)` so old content is versioned, then return.

6. **Search type filter** `nowing_backend/app/services/memory/search.py` and `nowing_backend/app/routes/memories_routes.py`:
   - `MemoryHybridSearch.search` accepts `type: str | None = None`.
   - If provided, add `Memory.type == type` to `base_conditions`.
   - `search_memory` passes `body.type`.

7. **Extraction service** `nowing_backend/app/services/memory/extraction.py`:
   - Define a Pydantic model for the LLM extraction result, e.g.:
     ```python
     class ExtractedFact(BaseModel):
         content: str
         type: str = "semantic"
         tags: list[str] = Field(default_factory=list)
         confidence: float = Field(default=0.9, ge=0.0, le=1.0)

     class MemoryExtractionResult(BaseModel):
         facts: list[ExtractedFact] = Field(default_factory=list)
     ```
   - `MemoryExtractionService.extract_from_turn(thread_id, turn_id, assistant_message_id) -> list[Memory]`:
     - Load the assistant message and the user message with `(thread_id, turn_id, role)`.
     - Load the thread to get `workspace_id` and `research_thread_id`.
     - Load `Workspace` and return `[]` if `memory_auto_extract_enabled` is `False` and env global is `False`.
     - Convert both messages to plain text with `app.utils.content_utils.extract_text_content`.
     - Build a prompt that asks for JSON only with durable facts, decisions, preferences; no greetings/chitchat.
     - Use `get_agent_llm(session, workspace_id, disable_streaming=True)`. If `None`, skip.
     - Call LLM inside `async with scoped_turn() as acc:`.
     - Strip fences and parse JSON → `MemoryExtractionResult`.
     - Filter facts by `confidence >= config.MEMORY_AUTO_EXTRACT_CONFIDENCE` and limit to `config.MEMORY_AUTO_EXTRACT_MAX_ITEMS`.
     - For each fact, call `repo.create_memory(..., source_type=MemorySourceType.CHAT_MESSAGE, source_id=assistant_message_id, created_by_id=user_message.author_id, research_thread_id=thread.research_thread_id, update_on_duplicate=True)`.
     - After `scoped_turn`, call `record_token_usage(..., usage_type="memory_create", workspace_id=workspace_id, user_id=user_message.author_id, message_id=assistant_message_id, prompt_tokens=..., completion_tokens=..., total_tokens=..., cost_micros=acc.total_cost_micros)`.

8. **Celery task** `nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py`:
   ```python
   @celery_app.task(name="extract_memory_after_chat_turn", bind=True)
   def extract_memory_after_chat_turn(self, message_id: int):
       return run_async_celery_task(lambda: _extract_memory_after_chat_turn(message_id))
   ```
   `_extract_memory_after_chat_turn` opens `get_celery_session_maker()()`, loads the assistant `NewChatMessage` with its thread, then calls `MemoryExtractionService.extract_from_turn`.

9. **Celery include** `nowing_backend/app/celery_app.py`:
   - Add `"app.tasks.celery_tasks.memory_extraction_task"` to `include`.

10. **Finalization hook** `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`:
    - After `await finalize_assistant_turn(...)`, add:
      ```python
      try:
          from app.tasks.celery_tasks.memory_extraction_task import extract_memory_after_chat_turn
          extract_memory_after_chat_turn.delay(stream_result.assistant_message_id)
      except Exception:
          logger.exception("Failed to enqueue memory extraction for message %s", stream_result.assistant_message_id)
      ```

### Step 2 — MCP server memory tools

1. **Create package** `nowing_mcp/mcp_server/features/memory/`:
   - `__init__.py` with `register(mcp, client, context)`.
   - `annotations.py` with `READ`, `WRITE`, `UPDATE` `ToolAnnotations` constants, mirroring `knowledge_base/annotations.py`.

2. **Implement tools** in `nowing_mcp/mcp_server/features/memory/__init__.py`:
   - `nowing_remember` (WRITE):
     - Params: `content` (str, required), `type` (str, default `"semantic"`), `tags` (list[str], optional), `confidence` (float, default 1.0), `source_type` (str, default `"manual"`), `source_id` (int|None), `workspace` (WorkspaceParam).
     - Resolve workspace, call `POST /workspaces/{id}/memories` with `MemoryCreate` payload.
     - Return compact markdown string by default; support `response_format="json"`.
   - `nowing_recall` (READ):
     - Params: `query` (str, required), `top_k` (int, default 5, max 20), `type` (str|None), `tags` (list[str], optional), `research_thread_id` (int|None), `workspace` (WorkspaceParam).
     - Resolve workspace, call `POST /workspaces/{id}/memories/search`.
     - Render compact markdown list (`# N result(s) for "query"`) or JSON.
   - `nowing_update_fact` (UPDATE):
     - Params: `memory_id` (int), `corrected_content` (str).
     - Call `PATCH /memories/{memory_id}`.
     - Return confirmation.
   - `nowing_continue_research` (READ):
     - Params: `research_thread_id` (int, required), `query` (str, optional, default `""`), `top_k` (int, default 5), `workspace` (WorkspaceParam).
     - Resolve workspace, call `POST /workspaces/{id}/memories/search` with `research_thread_id`.
     - Return compact context.
     - *Note for 4.5:* only `research_thread_id` is supported. Story 4.6 will add chat-thread resolution.

3. **Register** in `nowing_mcp/mcp_server/server.py`:
   - Import `memory` and call `memory.register(mcp, client, context)` after `knowledge_base.register`.

4. **Selfcheck** `nowing_mcp/mcp_server/selfcheck.py`:
   - Add the four memory tool names to `EXPECTED_TOOLS`.

### Step 3 — Tests

- **Backend extraction** `nowing_backend/tests/integration/memory/test_memory_extraction.py`:
  - Mock `get_agent_llm` and assert facts are created with `source_type=chat_message` and `source_id=message_id`.
  - Assert `TokenUsage` row with `usage_type="memory_create"` is created.
  - Assert workspace with `memory_auto_extract_enabled=False` skips extraction.
  - Assert dedup updates an existing near-duplicate rather than inserting a second row.
- **Backend routes** `nowing_backend/tests/integration/workspaces/test_memory_routes.py`:
  - Add red-phase test for `type` filter on `POST /workspaces/{id}/memories/search`.
- **MCP tools** `nowing_mcp/tests/test_memory_tools.py`:
  - Test `nowing_remember` calls `POST /workspaces/1/memories`.
  - Test `nowing_recall` calls `POST /workspaces/1/memories/search`.
  - Test `nowing_update_fact` calls `PATCH /memories/42`.
  - Test `nowing_continue_research` calls search with `research_thread_id`.
  - Ensure `selfcheck_run()` returns empty problems.

### Step 4 — Verification

- Run `alembic upgrade head`.
- `uv run pytest nowing_backend/tests/integration/workspaces/test_memory_routes.py`
- `uv run pytest nowing_mcp/tests`
- `python -m nowing_mcp.mcp_server.selfcheck`
- `uv run ruff check .` in both `nowing_backend` and `nowing_mcp`.

---

## 6. API Contract

### Backend REST endpoints

`POST /workspaces/{workspace_id}/memories`
```json
{
  "content": "Competitor X raised prices by 10% in Q2 2026.",
  "type": "semantic",
  "tags": ["competitor", "pricing"],
  "confidence": 0.95,
  "source_type": "chat_message",
  "source_id": 123,
  "research_thread_id": null
}
```
Returns `MemoryRead` 201.

`POST /workspaces/{workspace_id}/memories/search`
```json
{
  "query": "pricing",
  "top_k": 5,
  "type": null,
  "tags": ["competitor"],
  "research_thread_id": null
}
```
Returns `MemorySearchResponse` 200.

`PATCH /memories/{memory_id}`
```json
{
  "corrected_content": "Competitor X raised prices by 12% in Q2 2026."
}
```
Returns `MemoryRead` 200 with previous versions.

### MCP tool schemas

`nowing_remember`
```
content (str, required)
type (str, default "semantic")
tags (list[str], optional)
confidence (float, default 1.0)
source_type (str, default "manual")
source_id (int, optional)
workspace (str|int, optional)
```

`nowing_recall`
```
query (str, required)
top_k (int, default 5, max 20)
type (str, optional)
tags (list[str], optional)
research_thread_id (int, optional)
workspace (str|int, optional)
```

`nowing_update_fact`
```
memory_id (int, required)
corrected_content (str, required)
```

`nowing_continue_research`
```
research_thread_id (int, required)
query (str, optional, default "")
top_k (int, default 5)
workspace (str|int, optional)
```

---

## 7. Files to Create / Modify

### Create
- `nowing_backend/alembic/versions/179_add_workspace_memory_auto_extract.py`
- `nowing_backend/app/services/memory/extraction.py`
- `nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py`
- `nowing_mcp/mcp_server/features/memory/__init__.py`
- `nowing_mcp/mcp_server/features/memory/annotations.py`
- `nowing_mcp/tests/test_memory_tools.py`
- `nowing_backend/tests/integration/memory/test_memory_extraction.py`
- `_bmad-output/test-artifacts/atdd-checklist-4-5-agent-memory-tools-via-mcp.md`

### Modify
- `nowing_backend/app/db.py` — add `memory_auto_extract_enabled` to `Workspace`
- `nowing_backend/app/schemas/workspace.py` — add field to `WorkspaceRead`/`WorkspaceUpdate`
- `nowing_web/contracts/types/workspace.types.ts` — add field to `workspace` and `updateWorkspaceRequest`
- `nowing_backend/app/config/__init__.py` — add `MEMORY_AUTO_EXTRACT_*` env defaults
- `nowing_backend/app/services/memory/repository.py` — `update_on_duplicate` parameter
- `nowing_backend/app/services/memory/search.py` — `type` filter
- `nowing_backend/app/routes/memories_routes.py` — pass `body.type`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py` — enqueue extraction task
- `nowing_backend/app/celery_app.py` — include `memory_extraction_task`
- `nowing_mcp/mcp_server/server.py` — register memory feature
- `nowing_mcp/mcp_server/selfcheck.py` — add four memory tools to `EXPECTED_TOOLS`
- `docs/api-contracts-backend.md` and `docs/api-contracts-mcp.md` — update if maintained

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Extraction LLM cost grows quickly | Cap `MEMORY_AUTO_EXTRACT_MAX_ITEMS` at 3 by default; skip when workspace flag is false. |
| LLM returns unparseable JSON | Wrap parse in `try/except`, log warning, skip turn. |
| Race between message commit and Celery task | Enqueue after `finalize_assistant_turn` returns (it commits). Celery task re-queries the message by id. |
| Deduplication false positives | Only enable semantic upsert (`update_on_duplicate=True`) for auto-extraction; threshold 0.92. |
| `MemorySearchHit.score` still `0.0` | Optional: extend `MemoryHybridSearch.search` to return `(memory, score)` and fix the route. Not required for 4.5 AC but improves UX. |
| PAT lacks workspace membership | `check_permission` in routes will reject with 403; MCP server surfaces the backend error. |

---

## 9. Definition of Done

- [x] All four MCP tools register and `selfcheck.py` passes.
- [x] `nowing_remember` creates a `Memory` row in the active workspace.
- [x] `nowing_recall` returns ranked relevant memories from `POST /workspaces/{id}/memories/search`.
- [x] `nowing_update_fact` calls `PATCH /memories/{id}` and preserves the previous version.
- [x] `nowing_continue_research` searches memories by `research_thread_id`.
- [x] `MemoryExtractionService` extracts facts after assistant turns and records `TokenUsage` with `usage_type="memory_create"`.
- [x] Celery task is wired, included in `celery_app.include`, and called from `finalize_assistant_message`.
- [x] Workspace `memory_auto_extract_enabled` flag is persisted and honored.
- [x] `MemorySearchRequest.type` filter works end-to-end.
- [x] Backend and MCP tests are green.

---

## 10. Tasks / Subtasks

### Backend extraction
- [x] Migration `179_add_workspace_memory_auto_extract.py`
- [x] Update `Workspace` model and workspace schemas/frontend types
- [x] Add `MEMORY_AUTO_EXTRACT_*` config
- [x] Update `MemoryRepository` semantic dedup (`update_on_duplicate`)
- [x] Add `type` filter to `MemoryHybridSearch` and route
- [x] Create `MemoryExtractionService`
- [x] Create Celery task and add to `celery_app.include`
- [x] Hook `finalize_assistant_message`

### MCP memory tools
- [x] Create `nowing_mcp/mcp_server/features/memory/` package
- [x] Implement `nowing_remember`
- [x] Implement `nowing_recall`
- [x] Implement `nowing_update_fact`
- [x] Implement thin `nowing_continue_research`
- [x] Register memory feature in `build_server`
- [x] Update `selfcheck.py` `EXPECTED_TOOLS`

### Tests & docs
- [x] `nowing_mcp/tests/test_memory_tools.py`
- [x] `nowing_backend/tests/integration/memory/test_memory_extraction.py`
- [x] `nowing_backend/tests/integration/workspaces/test_memory_type_filter.py`
- [x] Create ATDD checklist
- [ ] Update API contract docs if maintained

### Verification
- [x] `alembic upgrade head`
- [x] `uv run pytest nowing_backend/tests/integration/workspaces/test_memory_routes.py`
- [x] `uv run pytest nowing_mcp/tests`
- [x] `python -m nowing_mcp.mcp_server.selfcheck`
- [x] `uv run ruff check .` on changed files

### Review Findings

- [x] [Review][Decision] Extraction failure handling strategy — Chosen (by reviewer): hybrid (option 3) + Celery retry. Swallow transient LLM/embedding failures (timeout, rate-limit, connection) with retry; escalate auth/config/misconfiguration by re-raising. Generic unexpected errors also re-raise.

- [x] [Review][Patch] Add timeout around extraction LLM call to avoid blocking the Celery worker indefinitely [nowing_backend/app/services/memory/extraction.py:377]
- [x] [Review][Patch] Log a warning when the extraction LLM returns an invalid memory type and falls back to SEMANTIC [nowing_backend/app/services/memory/extraction.py:391]
- [x] [Review][Patch] Validate `type` and `source_type` in `MemoryCreate` and `MemorySearchRequest` schemas (or repository) so invalid enum values return 4xx instead of 500 [nowing_backend/app/schemas/memory.py:43,58]
- [x] [Review][Patch] Make `MEMORY_AUTO_EXTRACT_CONFIDENCE` and `MEMORY_AUTO_EXTRACT_MAX_ITEMS` env parsing robust to non-numeric values (fall back to defaults instead of crashing startup) [nowing_backend/app/config/__init__.py:585]
- [x] [Review][Patch] Skip memory extraction when both user and assistant text are empty/whitespace to avoid wasteful LLM calls [nowing_backend/app/services/memory/extraction.py:363]
- [x] [Review][Patch] Fall back to `workspace.user_id` (or service `user_id`) for token usage attribution when `user_message.author_id` is None [nowing_backend/app/services/memory/extraction.py:356]
- [x] [Review][Patch] Wrap per-fact `repo.create_memory` in extraction to catch embedding failures and continue with remaining facts [nowing_backend/app/services/memory/extraction.py:395]
- [x] [Review][Patch] Treat workspace-not-found for an existing thread as `logger.error` (or raise) rather than a warning because it indicates data corruption [nowing_backend/app/services/memory/extraction.py:330]

### Review Findings — Re-run 2026-07-24

- [x] [Review][Decision] Should `MemoryExtractionService` verify `created_by_id` has `memory:create` permission before persisting chat-derived memories? — **Dismissed.** Auto-extraction is a workspace feature gated by `workspace.memory_auto_extract_enabled` and `config.MEMORY_AUTO_EXTRACT_ENABLED`; the chat turn already passed workspace access controls. Manual `nowing_remember` correctly checks `memory:create` separately.

- [x] [Review][Patch] `assistant_finalize.py` enqueues the memory extraction Celery task unconditionally. AC-5 requires no task is enqueued when `workspace.memory_auto_extract_enabled=False`. Move the workspace check before `.delay()`. [nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py:152-158] (HIGH)

- [x] [Review][Patch] `MemoryRepository._find_near_duplicate` does not filter by `created_by_id` when `workspace_id=None`, so user-scoped deduplication can match or overwrite memories belonging to other users. Add `created_by_id` to the duplicate query when workspace is null. [nowing_backend/app/services/memory/repository.py:68-93] (HIGH)

- [x] [Review][Patch] `_env_float` and `_env_int` in `config/__init__.py` emit warnings with `print()` and only catch `ValueError`; `MEMORY_AUTO_EXTRACT_CONFIDENCE` and `MEMORY_AUTO_EXTRACT_MAX_ITEMS` are not range-validated. Use `logger.warning`, catch `TypeError`/`OverflowError`, and clamp the parsed values to sensible ranges. [nowing_backend/app/config/__init__.py:27-47,607-612] (MEDIUM)

- [x] [Review][Patch] `nowing_continue_research` declares `research_thread_id` as optional (`int | None = None`), but the spec lists it as required. Remove the default and make the parameter required. [nowing_mcp/mcp_server/features/memory/__init__.py:157,178; nowing_mcp/mcp_server/features/memory/annotations.py:37-40] (MEDIUM)

- [x] [Review][Patch] `ExtractedFact.content` and `MemoryCreate.content` accept empty or whitespace-only strings, allowing useless memory rows. Add `min_length=1` validation. [nowing_backend/app/services/memory/extraction.py:60-63; nowing_backend/app/schemas/memory.py:43-45] (MEDIUM)

- [x] [Review][Patch] `MemoryRepository.update_memory` uses `scalar_one()` and will raise `NoResultFound` if the memory is deleted between the route check and update. Use `scalar_one_or_none()` and return `None` or raise a 404. [nowing_backend/app/services/memory/repository.py:197-200] (LOW)

- [x] [Review][Patch] `MemoryExtractionService` user-message selection orders only by `created_at`; ties are non-deterministic. Add `NewChatMessage.id` as a secondary sort key. [nowing_backend/app/services/memory/extraction.py:145-155] (LOW)

- [x] [Review][Patch] `MemoryRepository.update_memory` creates a `MemoryVersion` even when `corrected_content` equals the existing `memory.content`, producing duplicate version rows. Add a content-changed guard. [nowing_backend/app/services/memory/repository.py:202-207] (LOW)

- [x] [Review][Patch] `MemorySearchRequest.top_k` lacks an upper bound and `query` lacks a minimum-length check, allowing very expensive or empty searches. Add `le=100` and `min_length=1` to the schema. [nowing_backend/app/schemas/memory.py:69-72] (LOW)

- [x] [Review][Patch] `_SIMILARITY_THRESHOLD = 0.97` in `repository.py` is defined but never used. Remove the dead constant. [nowing_backend/app/services/memory/repository.py:29] (LOW)

### Review Findings — Adversarial Re-run 2026-07-24

Third review (Blind Hunter + Edge Case Hunter + Acceptance Auditor over `git diff 314a9e866..13e2f34a5`). Acceptance Auditor: all 6 ACs Met — no hard AC violation, nothing missing. Findings below are correctness/robustness issues not caught by the prior two rounds. Note: the previous round's `query min_length=1` addition is what introduced Decision D1.

- [x] [Review][Decision] (RESOLVED — chose backend query-less thread recall) `nowing_continue_research` is broken for its no-query use — tool sends `query or ""` (empty), but `MemorySearchRequest.query` now has `min_length=1`, so `nowing_continue_research(research_thread_id=N)` without a query → deterministic 422. The tool's docstring advertises query as optional ("scopes recall to the research thread"). Decision: (a) make `query` required in the tool, or (b) support query-less thread recall in the backend (list thread memories by recency, bypassing embedding + tsquery). [nowing_mcp/mcp_server/features/memory/__init__.py:162,166; nowing_backend/app/schemas/memory.py:73] (HIGH)

- [x] [Review][Decision] (RESOLVED — preserve original author on auto-dedup) Auto-extraction dedup overwrites and re-attributes another member's workspace memory — `create_memory(update_on_duplicate=True)` calls `_find_near_duplicate(content_match_required=False)`, which returns ANY workspace memory within 0.08 cosine distance regardless of author; `update_memory` then overwrites its content and sets `created_by_id` to the current turn's author. Owner-scoping only guards `workspace_id is None`. Decision: should workspace auto-dedup overwrite a near-neighbor authored by a different member, and should original authorship be preserved (update content/confidence only)? [nowing_backend/app/services/memory/repository.py:74-92,143-158] (MEDIUM)

- [x] [Review][Patch] (FIXED) Confidence filter is applied AFTER the `facts[:max_items]` slice, so high-confidence facts beyond the slice are dropped when the LLM returns low-confidence facts first. Filter by confidence, then slice to `max_items`. [nowing_backend/app/services/memory/extraction.py:215-216] (MEDIUM)

- [x] [Review][Patch] (FIXED) Extraction reads `response.content` directly instead of normalizing it; for providers that return content-block lists, `_parse_llm_output`'s `.strip()` raises `AttributeError` outside the LLM try/except and is not in the task's `autoretry_for` → permanent Celery task failure (extraction silently never runs for those providers). Route through `extract_text_content(response.content)` (already imported and used for message content). [nowing_backend/app/services/memory/extraction.py:190] (MEDIUM)

- [x] [Review][Patch] (FIXED) `create_memory` update_on_duplicate branch calls `update_memory(...)` without `skip_version_if_unchanged=True`, so re-derived identical facts (retry/duplicate-delivery/repeat turn) create redundant `MemoryVersion` rows with `previous_content == corrected_content`. The REST route passes the flag; this path should too. [nowing_backend/app/services/memory/repository.py:145] (LOW)

- [x] [Review][Patch] (FIXED) `create_memory` is annotated `-> Memory` but the update_on_duplicate branch returns `update_memory(...)` which is `Memory | None` (returns None if the duplicate is deleted concurrently); `extract_from_turn` then appends `None` to `created_memories`. Handle None (fall through to insert a fresh row) and correct the annotation. [nowing_backend/app/services/memory/repository.py:123,145] (LOW)

- [x] [Review][Patch] (FIXED) `research_thread_id: ResearchThreadId = None` in `remember`/`recall` where `ResearchThreadId = Annotated[int, ...]` — the generated schema declares a non-nullable int with a null default, so an explicit `null` from a client fails validation. Make it `int | None`. [nowing_mcp/mcp_server/features/memory/annotations.py:37; nowing_mcp/mcp_server/features/memory/__init__.py:52,100] (LOW)

- [x] [Review][Defer] `PATCH`/`DELETE /memories/{id}` skip permission checks when `memory.workspace_id is None` (personal memories); `nowing_update_fact` (new in 4.5) now exposes this to any PAT-authenticated MCP client → potential IDOR write on another user's personal memory. [nowing_backend/app/routes/memories_routes.py:125,155] — RESOLVED (re-run 2026-07-24): PATCH/DELETE now enforce owner-only access (403) for workspace-less memories; regression test `test_cannot_modify_other_users_personal_memory`.

- [x] [Review][Defer] Memory extraction is not idempotent — Celery at-least-once redelivery or a double `finalize_assistant_message` enqueues extraction twice → duplicate LLM calls, extra `memory_create` token rows, and version churn. Needs an idempotency key on `message_id`. [nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py; nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py] — RESOLVED (re-run 2026-07-24): extraction skips when a memory with source_id==assistant_message_id already exists; test `test_extract_is_idempotent_for_same_message`.

- [x] [Review][Defer] `selfcheck.py EXPECTED_TOOLS` and `app/mcp_tools.py MCP_TOOL_NAMES` are two hand-maintained lists; currently in sync (AC-6 Met) but nothing asserts equality, so future drift is uncaught by code. [nowing_mcp/mcp_server/selfcheck.py:16] — RESOLVED: already guarded by `nowing_mcp/tests/test_mcp_tool_filter.py::test_backend_catalog_matches_selfcheck` (asserts `MCP_TOOL_NAMES == EXPECTED_TOOLS`); auditor F-5 was a false positive (it inspected selfcheck.py only, not the test suite).

- [x] [Review][Defer] Memory poisoning — user-controlled turn text drives the extraction prompt and the LLM-supplied confidence is the only gate before writing to shared workspace memory that agents later recall. By-design for auto-extraction (mitigated by confidence threshold + workspace toggle); consider provenance labeling. [nowing_backend/app/services/memory/extraction.py] — MITIGATED (re-run 2026-07-24): extraction system prompt hardened to ignore instructions embedded in turn text; provenance already recorded via `source_type=chat_message`. Full mitigation (human review / per-user isolation) remains a product decision.

_Dismissed as noise (5): whitespace-only content still passes `min_length=1` (no strip); `_env_float` accepts `"nan"/"inf"` (operator misconfig only); MCP `top_k` clamp le=20 vs backend le=100 (intentional); `MemorySearchHit.score` hardcoded 0.0 (unchanged by this diff; spec says not required for 4.5); per-fact out-of-range confidence drops the fact (LLM rarely emits >1.0)._

### Review Findings — Adversarial Re-run #2 (verification of fixes) 2026-07-24

Re-ran all three layers on the fix diff (`git diff -- nowing_backend nowing_mcp`, 9 files). **Acceptance Auditor: all 6 ACs still Met — no regressions.** Two hunters converged on a real defect introduced by the W2 idempotency guard, plus a fail-open in the W1 fix. All fixed:

- [x] [Review][Patch] (FIXED) W2 guard + per-fact commits caused silent partial data loss: a worker crash between per-fact commits let the guard (source_id marker) skip the remaining facts on redelivery. Made per-turn extraction atomic — `MemoryRepository.create_memory`/`update_memory` gained a `commit` flag; extraction now flushes each fact and commits once at the end, so a mid-loop crash leaves nothing committed and redelivery re-extracts cleanly. [nowing_backend/app/services/memory/repository.py; extraction.py] (was HIGH)
- [x] [Review][Patch] (FIXED) W1 owner-check could fail open: `str(None) == str(None)` would grant access if both `created_by_id` and `auth.user.id` were null. Now fails closed: `memory.created_by_id is None or str(...) != str(...)` → 403. [nowing_backend/app/routes/memories_routes.py:PATCH,DELETE] (was MEDIUM)
- [x] [Review][Patch] (FIXED) `extract_text_content(response.content)` could return a non-str for unusual content shapes; coerce to `""` before parsing to avoid `.strip()` errors escaping the try/except. [nowing_backend/app/services/memory/extraction.py] (was LOW)

- [x] [Review][Defer] Idempotency guard is not concurrency-safe (TOCTOU): two extractions for the same message running concurrently (double finalize) can both pass the SELECT. Rare; sequential redelivery (the common case) is handled. Full fix = a Postgres advisory lock on message id. — deferred, documented in the guard comment
- [x] [Review][Defer] A turn that extracts zero facts is not marked, so a redelivery re-invokes the LLM (one wasted call, no data effect). — deferred, accepted for best-effort extraction
- [x] [Review][Defer] Manual exact-duplicate re-create still overwrites `source_id`/`tags`/`confidence` unconditionally (pre-existing `else` branch; only `created_by_id`/`research_thread_id` are guarded). — deferred, pre-existing, LOW

---

## 11. Notes for Downstream Stories

- **Story 4.6** will extend `nowing_continue_research` to accept a `chat_thread_id`, resolve it to a `ResearchThread` (creating one if missing), and load previous citations / last state.
- **Story 6.5** will add `memory_change` automation triggers and a `continue_research` action; the extraction service should emit events or signals that the trigger package can subscribe to (consider SQLAlchemy events or a lightweight `MemoryCreatedEvent`).

---

## 12. ATDD Artifacts

- **ATDD Checklist:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/test-artifacts/atdd-checklist-4-5-agent-memory-tools-via-mcp.md" />
- **Backend extraction tests:** <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/tests/integration/memory/test_memory_extraction.py" />
- **Backend search type-filter tests:** <ref_file file="/Users/luisphan/Documents/nowing/nowing_backend/tests/integration/workspaces/test_memory_type_filter.py" />
- **MCP tests:** <ref_file file="/Users/luisphan/Documents/nowing/nowing_mcp/tests/test_memory_tools.py" />
- **Selfcheck:** `python -m nowing_mcp.mcp_server.selfcheck`

---

## 13. Dev Agent Record

### Agent Model Used
SWE-1.7 Max / Devin CLI

### Debug Log References
- Implemented `Workspace.memory_auto_extract_enabled` with migration 179.
- Added `MEMORY_AUTO_EXTRACT_*` environment defaults to `app.config`.
- Extended `MemoryRepository` with `update_on_duplicate` for semantic upsert.
- Threaded `type` through `MemoryHybridSearch` and `memories_routes.search_memory`.
- Created `MemoryExtractionService` with `scoped_turn` token accounting.
- Created `extract_memory_after_chat_turn` Celery task and hooked `finalize_assistant_message`.
- Created `nowing_mcp/mcp_server/features/memory/` with `nowing_remember`, `nowing_recall`, `nowing_update_fact`, `nowing_continue_research`.
- Updated `selfcheck.py` `EXPECTED_TOOLS`; selfcheck passes (30 tools).
- Removed `@pytest.mark.skip` from Story 4.5 red-phase tests.

### Completion Notes List
- All backend memory extraction/integration tests pass (19 tests).
- All MCP tests pass (55 tests).
- `alembic upgrade head` applied migration 179 successfully.
- `python -m mcp_server.selfcheck` OK.
- Ruff clean on all changed files.
- API contract docs (`docs/api-contracts-backend.md`) were not updated in this pass; the REST contract is encoded in the tests and route/schemas.

### File List
- `nowing_backend/alembic/versions/179_add_workspace_memory_auto_extract.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/workspace.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/services/memory/search.py`
- `nowing_backend/app/routes/memories_routes.py`
- `nowing_backend/app/services/memory/extraction.py`
- `nowing_backend/app/tasks/celery_tasks/memory_extraction_task.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`
- `nowing_mcp/mcp_server/features/memory/__init__.py`
- `nowing_mcp/mcp_server/features/memory/annotations.py`
- `nowing_mcp/mcp_server/server.py`
- `nowing_mcp/mcp_server/selfcheck.py`
- `nowing_web/contracts/types/workspace.types.ts`
- `nowing_backend/tests/integration/memory/test_memory_extraction.py`
- `nowing_backend/tests/integration/workspaces/test_memory_type_filter.py`
- `nowing_mcp/tests/test_memory_tools.py`
- `_bmad-output/implementation-artifacts/4-5-agent-memory-tools-via-mcp.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## 14. References

- PRD memory requirements: [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` § FR-32, FR-33, FR-34]
- Epic 4 story: [Source: `_bmad-output/planning-artifacts/epics.md` § Story 4.5]
- Architecture decisions: [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` § AD-11, AD-12, AD-13, AD-14]
- Previous story context: [Source: `_bmad-output/implementation-artifacts/3-8-long-term-research-memory.md`]
- MCP tool-filter pattern: [Source: `_bmad-output/implementation-artifacts/2-5-workspace-mcp-tool-toggle.md`]
- Memory routes: [Source: `nowing_backend/app/routes/memories_routes.py`]
- Memory repository: [Source: `nowing_backend/app/services/memory/repository.py`]
- Memory search: [Source: `nowing_backend/app/services/memory/search.py`]
- Memory schemas: [Source: `nowing_backend/app/schemas/memory.py`]
- MCP catalog: [Source: `nowing_backend/app/mcp_tools.py`]
- MCP server composition: [Source: `nowing_mcp/mcp_server/server.py`]
- Workspace context: [Source: `nowing_mcp/mcp_server/core/workspace_context.py`]
- MCP client: [Source: `nowing_mcp/mcp_server/core/client.py`]
- Selfcheck: [Source: `nowing_mcp/mcp_server/selfcheck.py`]
- Assistant finalization: [Source: `nowing_backend/app/tasks/chat/streaming/flows/shared/assistant_finalize.py`]
- Celery helpers: [Source: `nowing_backend/app/tasks/celery_tasks/__init__.py`]
- Celery app: [Source: `nowing_backend/app/celery_app.py`]
- Token tracking: [Source: `nowing_backend/app/services/token_tracking_service.py`]
- LLM service: [Source: `nowing_backend/app/services/llm_service.py`]
- Content utils: [Source: `nowing_backend/app/utils/content_utils.py`]
