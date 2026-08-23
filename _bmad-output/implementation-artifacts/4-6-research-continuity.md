---
story_key: 4-6-research-continuity
status: done
baseline_commit: beb0cbf469fd79cba2907ed0199f85e1d969fdde
---

# Story 4.6: Research Continuity

Status: done

**Story ID:** 4.6
**Epic:** Epic 4 — Chat & Agents
**Priority:** P1
**Source artifacts:**
- PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (FR-33 Research Continuity, UJ-7, SM-8)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Epic 4, Story 4.6)
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-11, AD-12, AD-13)
- Previous story: `_bmad-output/implementation-artifacts/4-5-agent-memory-tools-via-mcp.md`

---

## Story

As an AI agent (and the workspace member behind it),
I want `nowing_continue_research(thread_id)` to return both the thread's ranked related memories **and** its previous citations, and to fail clearly when the thread does not exist,
so that I can resume a multi-session research thread with the full prior context (facts + sources) instead of only its memories.

## Acceptance Criteria

Derived from **FR-33 (Research Continuity)**. The recall half is already [BUILT] by Stories 3.8 + 4.5; this story closes the two gaps (citations + existence error).

### AC-1: `nowing_continue_research(thread_id)` returns memories **and** previous citations
**Given** a `ResearchThread` exists in the active workspace and is linked to one or more chat threads that produced citations
**When** an agent calls `nowing_continue_research(research_thread_id=<id>)`
**Then** the response contains (a) the N ranked related memories scoped to the thread (existing behavior) **and** (b) the list of previous citations of the thread (deduplicated), each with at least a source label/title and URL/locator where available.

### AC-2: Missing thread fails with a clear error; no implicit creation
**Given** `research_thread_id` does **not** resolve to a `ResearchThread` in the active workspace
**When** `nowing_continue_research` is called with that id
**Then** the tool returns a clear "research thread not found" error
**And** it does **NOT** create a thread implicitly (per FR-33; this overrides the earlier note in Story 4.5 §11 that suggested "creating one if missing").

### AC-3: Recall definition is unchanged from FR-32
**Given** the thread exists
**When** memories are recalled inside continue
**Then** they use the same hybrid recall path and "recall hit" definition as `nowing_recall` (`MemoryHybridSearch` scoped by `research_thread_id`), i.e. no separate/divergent ranking is introduced.

### AC-4: Citation aggregation is workspace-scoped and safe
**Given** the thread's chat threads contain persisted `[citation:<payload>]` markers in message content
**When** citations are aggregated
**Then** only citations from chat threads belonging to that `ResearchThread` **and** that workspace are returned, deduplicated, and capped at a sane limit; malformed markers are skipped rather than raising.

---

## Technical Context

### Already [BUILT] — DO NOT re-implement

- **`ResearchThread` model + schema** — `research_threads` table (migration `177_add_research_memory_tables`). Fields: `workspace_id`, `created_by_id`, `title`, `current_chat_thread_id`, `updated_at`, relationships `new_chat_threads`, `memories`, `current_chat_thread`. [Source: `nowing_backend/app/db.py:1968-2015`]
- **Thread ↔ chat link** — `NewChatThread.research_thread_id` nullable FK (`ondelete=SET NULL`). [Source: `app/db.py:712-746`]
- **Thread ↔ memory link** — `Memory.research_thread_id` nullable FK. [Source: `app/db.py:2048-2089`]
- **Thread-scoped memory recall** — `POST /workspaces/{id}/memories/search` accepts `research_thread_id` and, since Story 4.5's D1 fix, accepts an **empty query** for recency-ordered thread recall (bypasses embedding/keyword ranking). [Source: `app/routes/memories_routes.py`, `app/services/memory/search.py`]
- **`nowing_continue_research` MCP tool** — currently calls `memories/search` scoped to `research_thread_id` and renders only memory items; no citations, no existence check. [Source: `nowing_mcp/mcp_server/features/memory/__init__.py` — `continue_research`]

### The [GAP] this story closes

1. **Citations** (AC-1b, AC-4) — `continue_research` returns only memories; it must also return the thread's prior citations.
2. **Existence error** (AC-2) — a non-existent `research_thread_id` currently yields an empty recall silently; it must return a clear "not found" error.

### How citations are stored (critical for AC-1/AC-4)

There is **no citations table**. Citations are persisted **inline** in assistant message content: during finalization, `[n]` markers are rewritten to `[citation:<payload>]` in each text part before persisting. [Source: `app/tasks/chat/streaming/flows/shared/assistant_finalize.py:_resolve_citations` (lines ~54-66)]. The per-conversation `[n] ↔ source` map is `CitationRegistry` (`by_n: {n: CitationEntry(source_type, locator, display)}`) [Source: `app/agents/chat/multi_agent_chat/shared/citations/registry.py`; entry model in `.../citations/models.py`].

Therefore, "previous citations of a thread" must be aggregated from the persisted messages of the thread's chats: `ResearchThread.new_chat_threads` → each `NewChatThread` → its `NewChatMessage` rows → parse `[citation:<payload>]` markers out of the JSONB `content` text parts, dedupe, and normalize into `{label/title, url}` items.

---

## Implementation Plan (design)

Recommended approach — one new backend endpoint + a thin MCP tool change:

### Step 1 — Backend: research-thread context endpoint
Add `GET /workspaces/{workspace_id}/research-threads/{thread_id}/context` (new file `app/routes/research_threads_routes.py`, registered in `app/routes/__init__.py`):
1. `check_permission(..., Permission.MEMORY_READ.value)` (continue = a read of the thread's memory/context; reuse the memory read permission).
2. Load `ResearchThread` by `id` **and** `workspace_id`. If `None` → `raise HTTPException(404, "Research thread not found")` (AC-2 — no implicit creation).
3. **Memories:** run `MemoryHybridSearch` scoped by `research_thread_id` (empty query → recency, or optional `query` param → ranked), identical to `nowing_recall` (AC-3). Reuse the same code path the memories/search route uses; do not fork ranking.
4. **Citations:** call a new service `app/services/memory/thread_citations.py::collect_thread_citations(session, research_thread)` that:
   - Loads all `NewChatMessage` for the thread's `new_chat_threads` (assistant role, ordered by recency).
   - Extracts `[citation:<payload>]` markers from text parts (regex mirroring the finalize rewrite; reuse/lift the marker parser from the citations module rather than re-inventing).
   - Dedupes by payload/locator, caps at a limit (e.g. 50), normalizes to `{ "label"/"title", "url" }`.
5. Return `ResearchThreadContext { thread_id, title, memories: [MemorySearchHit], citations: [ThreadCitation] }`.

### Step 2 — MCP: update `nowing_continue_research`
- Call the new endpoint instead of `memories/search`.
- Surface a clear "research thread not found" message when the backend returns 404 (`NowingClient.request` raises `ToolError`; catch/translate).
- Render **both** memories and citations in markdown; keep `response_format=json` returning the full `{memories, citations}` object.
- Keep `research_thread_id` required and the optional `query` param (empty allowed).

### Step 3 — Tests
- Backend integration: thread with memories + a chat thread whose messages contain `[citation:...]` → endpoint returns both, deduped; non-existent thread → 404; thread in another workspace → 404 (isolation); malformed marker → skipped.
- MCP: `nowing_continue_research` returns memories + citations for an existing thread; returns a clear not-found error for a missing thread (fake client).
- Reuse `nowing_mcp/tests/test_memory_tools.py` patterns; backend `tests/integration/workspaces/` + a new `tests/integration/memory/test_research_continuity.py`.

### Step 4 — Verification
- `uv run --active python -m pytest nowing_backend/tests/integration/memory/test_research_continuity.py nowing_backend/tests/integration/workspaces/test_memory_routes.py -q`
- `cd nowing_mcp && uv run --active python -m pytest tests/test_memory_tools.py -q`
- `cd nowing_mcp && uv run --active python -m mcp_server.selfcheck` (30 tools stay healthy; tool count unchanged — no new tool)
- `uv run ruff check` on changed files.

---

## API Contract

**New:** `GET /workspaces/{workspace_id}/research-threads/{thread_id}/context?query=<optional>&top_k=<1..100>`
- 200 → `{ "thread_id": int, "title": str|null, "memories": MemorySearchHit[], "citations": ThreadCitation[] }`
- 404 → `{ "detail": "Research thread not found" }`
- 403 → missing `memory:read`

`ThreadCitation` (new schema in `app/schemas/memory.py` or a new `research_thread.py`): `{ "label": str, "url": str|null, "source_type": str|null }`.

**Unchanged:** `nowing_continue_research(research_thread_id: int, query: str = "", top_k: int = 5, workspace: str|None)` — same signature; richer response.

---

## Files to Create / Modify

**Create:**
- `nowing_backend/app/routes/research_threads_routes.py` — the context endpoint.
- `nowing_backend/app/services/memory/thread_citations.py` — citation aggregation service.
- `nowing_backend/app/schemas/memory.py` additions (or `app/schemas/research_thread.py`) — `ThreadCitation`, `ResearchThreadContext`.
- `nowing_backend/tests/integration/memory/test_research_continuity.py`.

**Modify:**
- `nowing_backend/app/routes/__init__.py` — register the new router.
- `nowing_mcp/mcp_server/features/memory/__init__.py` — `continue_research` calls the new endpoint, renders memories + citations, translates 404.
- `nowing_mcp/tests/test_memory_tools.py` — extend for citations + not-found.

---

## Tasks / Subtasks

- [x] Backend: citation aggregation service (AC-1, AC-4)
  - [x] `collect_thread_citations(session, research_thread)` — load thread's chat messages, parse `[citation:<payload>]` markers (reuse citations module parser), dedupe, cap, normalize.
- [x] Backend: research-thread context endpoint (AC-1, AC-2, AC-3)
  - [x] New router `research_threads_routes.py`; `memory:read` permission check.
  - [x] Load `ResearchThread` by id + workspace_id → 404 clear error if missing (no implicit create).
  - [x] Memories via `MemoryHybridSearch` scoped by `research_thread_id` (same path as recall).
  - [x] Return `{thread_id, title, memories, citations}`.
  - [x] Register router in `app/routes/__init__.py`.
- [x] Schemas: `ThreadCitation`, `ResearchThreadContext`.
- [x] MCP: update `nowing_continue_research` to call the endpoint, render memories + citations, translate 404 → clear tool error (AC-1, AC-2).
- [x] Tests
  - [x] Integration: existing thread → memories + deduped citations; missing thread → 404; cross-workspace thread → 404; malformed marker skipped.
  - [x] MCP: memories + citations rendered; not-found error surfaced.
- [x] Verification: pytest suites + selfcheck + ruff (see Step 4).

### Review Findings

- [x] [Review][Patch] `RunCitationMarker` chưa được `_marker_to_citation` xử lý — đã thêm branch xử lý `RunCitationMarker` trả về `ThreadCitation(label=run_id, url=None, source_type="run")`; export `RunCitationMarker` trong `__init__.py` [nowing_backend/app/services/memory/thread_citations.py:97-111]
- [x] [Review][Patch] Chunk id âm được chấp nhận — đã thêm guard `if chunk_id < 0: continue` trong `parse_citation_markers` [nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py:89-91]
- [x] [Review][Patch] `collect_thread_citations` không lọc `client_id` — đã thêm `NewChatThread.client_id == thread_client_id` (với `client_id` normalized như `MemoryHybridSearch`) để tenant-isolate citations [nowing_backend/app/services/memory/thread_citations.py:133-147]
- [x] [Review][Defer] Citation regex copy từ TS/evals nhưng không có parity guard — rủi ro drift cross-package; cần cross-package parity test sau [nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py:10-14]
- [x] [Review][Defer] MCP dùng substring `not found` để phát hiện 404 — brittle, cần `NowingClient` expose HTTP status [nowing_mcp/mcp_server/features/memory/__init__.py:194-200]

**Dismissed:** 15 findings từ Blind Hunter (noise / pre-existing) + 25 findings từ Edge Case Hunter (đã có guard hoặc không phải lỗi). Acceptance Auditor: no AC violation.

## Dev Notes

### ATDD Artifacts (red-phase — activate during dev-story)

- Checklist: `_bmad-output/test-artifacts/atdd-checklist-4-6-research-continuity.md`
- Backend red-phase scaffold: `nowing_backend/tests/integration/memory/test_research_continuity.py` (5 tests, `@pytest.mark.skip`)
- MCP red-phase scaffold: `nowing_mcp/tests/test_research_continuity.py` (2 tests, `@pytest.mark.skip`)
- Remove the `@pytest.mark.skip` marker per task as it turns green (red → green → refactor).

### Existing pattern to mirror
- The memory REST routes (`app/routes/memories_routes.py`) show the exact `check_permission` + `MemoryHybridSearch` + `MemorySearchHit` response shape to reuse for the memories half. Do **not** fork ranking (AC-3).
- The MCP tool pattern (`features/memory/__init__.py`) — `context.resolve(workspace)`, `client.request(...)`, `to_json`/markdown render helpers — is already in place; `continue_research` just changes its endpoint + rendering.

### Citation extraction
- Reuse the citation marker format/parser from the citations module and `assistant_finalize.py:_resolve_citations`; do NOT hand-roll a divergent regex. The persisted marker is `[citation:<payload>]` inside text parts of `NewChatMessage.content` (JSONB list of parts).
- Only assistant messages carry citations. Scope strictly to the thread's `new_chat_threads` and the workspace (AC-4 isolation).

### Read before modifying
- Read `nowing_mcp/mcp_server/features/memory/__init__.py` (`continue_research` + `_render_recall`) fully; extend rendering rather than replacing the recall behavior.
- Read `app/routes/__init__.py` to match router registration conventions.

## Risks & Open Decisions

- **[DECISION] Citation source of truth.** Citations are inline markers, not a table. Confirm the parser lifts the exact payload written by `_resolve_citations` (and whether payload is a URL or an encoded locator needing `CitationRegistry`/`CitationEntry` shape). If message content does not retain enough to render a label+URL, decide whether to (a) enrich from `CitationRegistry` state if still available, or (b) render URL-only. **Recommend (b) URL-only for MVP** unless a richer payload is already persisted.
- **[CONTRADICTION resolved]** Story 4.5 §11 said 4.6 would "resolve a chat_thread_id → ResearchThread (creating one if missing)". FR-33 AC-2 forbids implicit creation. **PRD wins: no implicit creation; clear error on missing thread.** Accepting a `chat_thread_id` alias is out of scope for this story.
- **Scope guard:** recall-quality/eval gate (NFR-8) is explicitly [PARTIAL]/deferred in the PRD and is **not** part of 4.6.

## Guardrails / Anti-patterns
- Do **not** create a `ResearchThread` implicitly in `continue_research` (FR-33 AC-2).
- Do **not** introduce a second/divergent recall ranking — reuse `MemoryHybridSearch` (AC-3).
- Do **not** add a new MCP tool — extend the existing `nowing_continue_research` (keeps `EXPECTED_TOOLS`/`MCP_TOOL_NAMES` at 30; selfcheck + `test_backend_catalog_matches_selfcheck` stay green).
- Do **not** leak cross-workspace or cross-thread citations (AC-4).
- Do **not** raise on a malformed citation marker — skip it.

## References
- FR-33 / UJ-7 / SM-8 — `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:210-224, 58, 520`
- AD-11/12/13 — `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:110-141`
- `ResearchThread` model — `nowing_backend/app/db.py:1968-2015`
- `NewChatThread.research_thread_id` — `app/db.py:712-746`
- `Memory.research_thread_id` — `app/db.py:2048-2089`
- Memory routes + search — `app/routes/memories_routes.py`, `app/services/memory/search.py`
- Citation persistence — `app/tasks/chat/streaming/flows/shared/assistant_finalize.py:54-66`
- Citation registry/models — `app/agents/chat/multi_agent_chat/shared/citations/registry.py`, `.../citations/models.py`
- Current `nowing_continue_research` — `nowing_mcp/mcp_server/features/memory/__init__.py`
- Previous story (recall half + D1 empty-query fix) — `_bmad-output/implementation-artifacts/4-5-agent-memory-tools-via-mcp.md`

## Dev Agent Record

### Review Findings — Code Review 2026-07-24

Three-layer review (Blind + Edge + Acceptance) of the staged 4.6 diff (12 files, +893/−31). **Consensus: production code is sound** — permission gating (403 before 404), workspace+thread citation scoping, regex safety (no backtracking, single query — no N+1), dedup/cap/malformed-skip are all correctly implemented. The real weakness is **test fidelity**: the AC-4 isolation property is implemented but not genuinely verified.

- [x] [Review][Patch] (FIXED) AC-4 isolation is not tested: `test_continue_context_other_workspace_thread_is_404` requests the thread via its OWN workspace and uses `assert ... in (200, 403)` (tautology); the real cross-workspace path and the 403 permission gate have ZERO coverage. Add non-member fixtures to `tests/integration/memory/conftest.py` and real tests: (a) non-member → 403; (b) thread in workspace B requested via workspace A → 404. [test_research_continuity.py; memory/conftest.py] (HIGH)
- [x] [Review][Patch] (FIXED) No test proves citation isolation (F-2): dropping either WHERE predicate in `collect_thread_citations` would leak citations uncaught. Add a test where a second thread's citations do NOT appear in the target thread's response. [test_research_continuity.py] (MEDIUM)
- [x] [Review][Patch] (FIXED) AC-3 test sorts ids (`sorted(...) == sorted(...)`), so it verifies same-set not same-ranking; a divergent order would pass. Compare ordered lists. [test_research_continuity.py] (MEDIUM)
- [x] [Review][Patch] (FIXED) Citation dedup key is exact-string (`f"url:{marker.url}"`); `…/p` vs `…/p/` vs case-different host produce duplicates that inflate the payload and burn the cap. Normalize the URL (lowercase scheme+host, strip trailing slash) for the dedup key. [thread_citations.py:_marker_to_citation] (MEDIUM)
- [x] [Review][Patch] (FIXED) `_iter_text_parts` drops citations when a message `content` is a bare part-dict (not wrapped in a list) — only `str`/`list` handled. Handle a single dict. [thread_citations.py:_iter_text_parts] (LOW)
- [x] [Review][Patch] (FIXED) Add a chunk-citation test (url=None branch of `_marker_to_citation`) — currently only URL markers are exercised. [test_research_continuity.py] (LOW)

- [x] [Review][Defer] MCP 404→"not found" translation is a brittle substring match on error prose: a non-404 error containing "not found" is mislabeled, and the real cross-workspace 403 won't get the friendly message. Robust fix needs `NowingClient` to expose the HTTP status. [features/memory/__init__.py] — deferred, needs client change
- [x] [Review][Defer] Citation regex is hand-copied across web/evals/backend with no shared parity guard — silent drift risk. [citations/parser.py] — deferred, cross-package
- [x] [Review][Defer] `_render_continue` markdown omits thread title/id (JSON mode keeps them); non-dict 200 body would `AttributeError`; MCP top_k caps at 20 vs backend 100. [features/memory/__init__.py] — deferred, low impact
- [x] [Review][Defer] `embeddings[0]` can IndexError on embed failure — pre-existing pattern mirrored from `/memories/search`, not newly introduced. [research_threads_routes.py] — deferred, pre-existing

_Dismissed (note): unrelated import reordering churn in `routes/__init__.py`; negative chunk ids accepted as labels (harmless)._

### Agent Model Used

Kiro (BMAD `dev-story` agent).

### Debug Log References

- Backend: `uv run --active python -m pytest tests/integration/memory/test_research_continuity.py tests/integration/memory/test_memory_extraction.py tests/integration/workspaces/test_memory_routes.py -q` → **26 passed**.
- MCP: `uv run --active python -m pytest tests/test_research_continuity.py tests/test_memory_tools.py -q` → **10 passed**; full MCP suite → **58 passed** (incl. `test_backend_catalog_matches_selfcheck`).
- MCP selfcheck: `uv run --active python -m mcp_server.selfcheck` → `selfcheck OK: 30 tools registered and well-formed`.
- Regression guard: citation unit tests (`tests/unit/.../citations/`, `test_assistant_finalize_citations.py`) → **36 passed**.
- Ruff: clean on every created/modified file.

### Completion Notes List

- **Endpoint:** `GET /api/v1/workspaces/{workspace_id}/research-threads/{thread_id}/context?query=&top_k=` → `200 {thread_id, title, memories: MemorySearchHit[], citations: ThreadCitation[]}`; `404 {"detail": "Research thread not found"}`; `403` on missing `memory:read`. New router `research_threads_routes.py` registered in `app/routes/__init__.py`.
- **AC-2 (no implicit creation):** thread is loaded by `id` **and** `workspace_id`; a miss raises `HTTPException(404)` — nothing is created. Verified by the "creates nothing" test (row count unchanged).
- **AC-3 (recall unchanged):** memories come from `MemoryHybridSearch` scoped by `research_thread_id`, using the exact same path/params as `POST /memories/search` (empty query → recency). The AC-3 test asserts the endpoint's memory ids equal `memories/search`'s ids — no divergent ranking.
- **AC-1b / AC-4 (citations):** new service `app/services/memory/thread_citations.py::collect_thread_citations` aggregates citations from the thread's chat threads' **assistant** messages, scoped by `research_thread_id` **and** `workspace_id` (strict isolation), deduped, capped at 50, malformed markers skipped.
- **Citation extraction (reuse, not hand-rolled):** the backend citation module had no parser (only the `[n]→[citation:...]` writer). I added `app/agents/chat/multi_agent_chat/shared/citations/parser.py` whose `CITATION_REGEX` is the **canonical** pattern copied byte-for-byte from the source of truth (`nowing_web/lib/citations/citation-parser.ts`, also ported in `nowing_evals`). It parses `[citation:<payload>]` into URL vs chunk markers. This keeps every surface (web renderer, evals, backend) recognizing identical markers rather than introducing a divergent regex.
- **[DECISION] resolved (URL-only MVP + normalization):** web-URL markers → `{label: <host>, url, source_type: "url"}`. Knowledge-base chunk markers carry no persisted URL/label, so they are surfaced with a minimal label (`doc-<id>`/`chunk <id>`) and `url=None` (AC-1b: "label/title always; URL where available"), rather than enriched from the non-persisted `CitationRegistry`. The ATDD tests only exercise URL citations; this is a superset that keeps the nullable schema fields meaningful.
- **MCP (`nowing_continue_research`):** now calls the new context endpoint instead of `memories/search`, renders **both** memories (via `_render_recall`) and citations (via `_render_citations`), returns the full `{memories, citations}` object under `response_format=json`, and translates a backend `ToolError` containing "not found" into a clear "research thread … not found; no thread was created" `ToolError`. Signature unchanged (`research_thread_id` required, `query` optional). **No new tool** — `EXPECTED_TOOLS`/`MCP_TOOL_NAMES` stay at 30; selfcheck + catalog-match tests remain green.
- **Test adjustments (why):**
  - `nowing_backend/tests/integration/memory/conftest.py` **created** — the ATDD scaffold uses the `client` fixture, which lived only in `tests/integration/workspaces/conftest.py` (a sibling not visible to `memory/`). Added a `client` fixture (authed as `db_user`, sharing the test's `db_session`) so the activated tests can hit the app over ASGI. Assertions were left faithful to AC-1..AC-4.
  - `nowing_mcp/tests/test_research_continuity.py` — implemented the two `NotImplementedError` helpers: `_server_with_client` builds a plain `FastMCP`, registers the memory tools against the fake client, and seeds the active workspace (so `context.resolve` needs no network); `_invoke_continue_research` sets a request context and calls the tool. Added a local `settings` fixture (mirrors `test_memory_tools.py`) since there is no shared MCP conftest.
  - `nowing_mcp/tests/test_memory_tools.py` — the pre-existing `test_continue_research_calls_search_with_thread` asserted the tool called `/memories/search`; that contract changed, so it was replaced by `test_continue_research_reads_context_endpoint` (asserts the `/research-threads/{id}/context` call + rendered memories **and** citation URL) and a new `test_continue_research_missing_thread_surfaces_not_found`; the fake client gained a context-endpoint branch.
- **Guardrails honored:** no implicit `ResearchThread` creation; reused `MemoryHybridSearch` (no divergent ranking); no new MCP tool (30 tools); strict workspace+thread isolation for citations; malformed markers skipped (never raised).
- Not committed, not deployed — all changes left uncommitted for human review.
- **Re-verification (2026-08-23):** `test_research_continuity.py` + `test_memory_routes.py` → 25 passed; `mcp` `test_research_continuity.py` + `test_memory_tools.py` → 17 passed; `mcp_server.selfcheck` → 65 tools registered and well-formed; `ruff check` clean on changed files.
- **Code review 2026-08-23:** 3 patches applied (RunCitationMarker, negative chunk id, client_id tenant filter); 2 items deferred (regex parity guard, MCP 404 substring); ~40 findings dismissed. New unit test `tests/unit/agents/multi_agent_chat/shared/citations/test_parser.py` passes; backend integration + MCP suites remain green.
- **Test review 2026-08-23:** `bmad-testarch-test-review` approved với 5 low/medium recommendations. Đã giải quyết: thêm integration tests cho `RunCitationMarker`, `client_id` filter, citation cap (50); strengthen AC-1 assertions. Còn lại `urlcite` placeholder đã có unit test. Chi tiết: `_bmad-output/implementation-artifacts/test-reviews/test-review-4-6-research-continuity.md`.

### File List

**Created (backend):**
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py`
- `nowing_backend/app/services/memory/thread_citations.py`
- `nowing_backend/app/routes/research_threads_routes.py`
- `nowing_backend/tests/integration/memory/conftest.py`
- `nowing_backend/tests/unit/agents/multi_agent_chat/shared/citations/test_parser.py`

**Modified (backend):**
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/__init__.py` (export the new parser + `RunCitationMarker`)
- `nowing_backend/app/schemas/memory.py` (`ThreadCitation`, `ResearchThreadContext`)
- `nowing_backend/app/schemas/__init__.py` (export the new schemas)
- `nowing_backend/app/routes/__init__.py` (register the research-threads router)
- `nowing_backend/tests/integration/memory/test_research_continuity.py` (activated red-phase scaffold → green)

**Modified (MCP):**
- `nowing_mcp/mcp_server/features/memory/__init__.py` (`continue_research` → context endpoint, render memories + citations, 404 translation)
- `nowing_mcp/tests/test_research_continuity.py` (implemented helpers + `settings` fixture, activated scaffold → green)
- `nowing_mcp/tests/test_memory_tools.py` (updated continue test for the new endpoint + added not-found test + fake context branch)
