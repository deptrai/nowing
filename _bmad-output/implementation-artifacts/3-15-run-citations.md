---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 3-15-run-citations
status: ready-for-dev
---

# Story 3.15: Run Citations as Verifiable Sources

**Status:** ready-for-dev  
**Epic:** 3 — Knowledge Base + Long-Term Memory  
**Priority:** HIGH  
**Requirements:** FR-13, FR-39  
**Architecture:** AD-11.1, AD-15  
**Dependencies:** Story 3.8 (memory storage/retrieval), 9.6a (provenance recipe) optional but recommended.

## Story

As a researcher,  
I want scraper runs to be citable sources in chat,  
So that I can trace claims back to the exact run that produced them.

## Context

### Upstream reference

SurfSense PR #1619 (`MODSetter/SurfSense#1619`) already implemented the pattern we need to port:

- Added `RUN = "run"` to the backend `CitationSourceType` enum and taught `to_frontend_payload` to return the `run_<uuid>` handle for `RUN` entries.
- Added a new `app/capabilities/core/access/run_citation.py` helper: `attach_run_citation(registry, run_external_id, capability)` registers a `RUN` citation and returns its ordinal `[n]` plus a label line (`Cite this scraper run as [n] ...`).
- Rewired the capability tool adapter (`app/capabilities/core/access/agent.py`) so that a stored run returns a `Command(update={"messages": [...], "citation_registry": registry})` instead of a plain dict/string. The `ToolMessage` content is the original tool output plus the citation label, and the registry update carries the run citation up through LangGraph state.
- Injected `runtime: ToolRuntime` into the tool coroutine and used `_run.__annotations__["runtime"] = ToolRuntime` so `StructuredTool.from_function` passes `runtime` through while keeping the Pydantic `args_schema` unchanged.
- Added the `citation` middleware slot to `build_subagent_middleware_stack` so non-filesystem specialists (reddit, youtube, web_crawler, etc.) can write `citation_registry` back to the parent state.
- Updated `output_contract_base.md` and `citations/on.md` to tell specialists that scraper run outputs carry `[n]` labels and those labels must be appended to any claim drawn from the run.
- Frontend:
  - `citation-panel.atom.ts` was changed from a `chunkId` scalar to a `CitationTarget` union (`{kind: "chunk", chunkId: number} | {kind: "run", runId: string}`) and a new `openRunCitationPanelAtom`.
  - `citation-parser.ts` now matches `run_<uuid>` handles and emits a `run` token.
  - `citation-renderer.tsx` dispatches `run` tokens to a new `RunCitation` chip.
  - `run-citation.tsx` and `run-citation-panel.tsx` render the inline chip and the right-panel run detail, reusing the existing `RunDetail` component from the playground.
  - `RightPanel.tsx` branches between the chunk citation panel and the run citation panel based on `target.kind`.

### Nowing current state

- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/models.py` defines `CitationSourceType` but does **not** include `RUN`. `markers.py` only renders chunk IDs and URLs; all other source kinds (including `CONNECTOR_ITEM`) are dropped.
- `nowing_backend/app/capabilities/core/access/agent.py` records every run and already returns `run_id` inline (`dump["run_id"] = f"run_{run_id}"`), but it does **not** register a citation or return a `Command`. The model therefore has no `[n]` label to cite.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/citation_state.py` and `build_citation_state_mw` exist, but `build_subagent_middleware_stack` (lines 45-52) does **not** include the `citation` slot, so non-filesystem subagents cannot write `citation_registry` back to the parent state.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/snippets/output_contract_base.md` (lines 1-7) has no instruction to copy a run's `[n]` label into findings.
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/citations/on.md` (lines 1-17) says only `knowledge_base` findings are citable; it omits scraper run-backed findings.
- `nowing_web/lib/citations/citation-parser.ts` (line 20) does **not** match `run_<uuid>`, and `CitationToken` (lines 24-26) has no `run` kind.
- `nowing_web/components/citations/citation-renderer.tsx` (lines 20-31) only handles `url` and `chunk` tokens.
- `nowing_web/atoms/citation/citation-panel.atom.ts` (lines 4-12) only stores `chunkId`.
- `nowing_web/components/layout/ui/right-panel/RightPanel.tsx` (lines 92, 144, 215, 310-313) only checks `citationState.chunkId != null` and only mounts `CitationPanelContent`.
- `nowing_web/app/dashboard/[workspace_id]/playground/components/run-detail.tsx` already renders a run's `capability`, `input`, `output_text`, progress, and error. It can be reused for the citation panel.
- `nowing_backend/app/db.py` `Run` model (lines 3172-3237) stores `id` (UUID), `capability`, `input`, `output_text`, `status`, etc. `Memory` already has `source_run_id`, `source_capability`, `source_input` (Story 9.6a / FR-39), so the run detail panel has a natural provenance source and the soft `run_<uuid>` citation already works for memory recall.

## Acceptance Criteria

1. **Citation source type**
   - **Given** the citation registry, **When** a scraper run is registered as a source, **Then** `CitationSourceType` has a `RUN = "run"` value and `to_frontend_payload` returns the `run_<uuid>` string for `RUN` entries.

2. **Capability tool mints a run citation**
   - **Given** a successful scraper/research tool call that records a `Run` row, **When** the tool finalizes, **Then** it returns a `Command` whose `ToolMessage` content ends with `Cite this scraper run as [n]` and whose `citation_registry` update contains `source_type=RUN`, `locator.run_id=run_<uuid>`, and `display.capability=<name>`.
   - **And** outputs that exceed `RUN_OUTPUT_CHAR_CAP` still mint the citation against the stored run and return the capped preview plus the label.

3. **Subagents can carry citation registry**
   - **Given** a specialist subagent (e.g. `reddit`, `youtube`, `web_crawler`) calls a capability, **When** it returns a `Command` with `citation_registry`, **Then** the parent conversation merges the registry so the main agent can resolve `[n]` across the turn.

4. **Model prompt teaches run citations**
   - **Given** citations are enabled, **When** a specialist draws a finding from a scraper run, **Then** `output_contract_base.md` and `citations/on.md` instruct it to append the run's `[n]` label to the claim and to copy the label exactly.

5. **Frontend parses and renders run citations**
   - **Given** an assistant message contains `[citation:run_<uuid>]`, **When** it is rendered, **Then** it shows a "Source" chip that opens the run detail panel, and existing chunk and URL citations continue to work unchanged.

6. **Run detail panel shows provenance**
   - **Given** a user clicks a run citation, **When** the right panel opens, **Then** it displays the run's `capability`, `input`, `output_text`, progress, and error (reusing `RunDetail`), scoped to the current workspace; if the run is missing or expired, it shows a clear "Run not found" state.

7. **No fabricated public URLs**
   - **Given** a `RUN` citation, **When** it is rendered or shared, **Then** it uses the internal `run_<uuid>` handle and never fabricates a public web URL.

## Tasks / Subtasks

### Backend

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/models.py`
  - [ ] Add `RUN = "run"` to `CitationSourceType`.

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/markers.py`
  - [ ] Add `case CitationSourceType.RUN:` returning `locator.get("run_id")`.

- [ ] `nowing_backend/app/capabilities/core/access/run_citation.py` (new)
  - [ ] Define `attach_run_citation(registry, *, run_external_id: str, capability: str) -> tuple[int, str]`.
  - [ ] Register `CitationSourceType.RUN` with `locator={"run_id": run_external_id}` and `display={"capability": capability}`.
  - [ ] Return `(n, f"\n\nCite this scraper run as [{n}] after any claim drawn from its data.")`.

- [ ] `nowing_backend/app/capabilities/core/access/agent.py`
  - [ ] Import `json`, `ToolRuntime`, `ToolMessage`, `Command`.
  - [ ] Change `_run` signature to `async def _run(runtime: ToolRuntime, **kwargs: object) -> dict | str | Command`.
  - [ ] Annotate `_run.__annotations__["runtime"] = ToolRuntime` so `StructuredTool.from_function` injects `runtime` while keeping `args_schema=input_model`.
  - [ ] If `run_id` is `None`, keep the legacy return shape and skip citation.
  - [ ] Build `run_external_id = f"run_{run_id}"`; if output fits `RUN_OUTPUT_CHAR_CAP`, JSON-dump the model dump, otherwise use `_build_preview(serialized, run_id)`.
  - [ ] Load registry via `load_registry(getattr(runtime, "state", None))`.
  - [ ] Call `attach_run_citation` and return `Command(update={"messages": [ToolMessage(content=content + label, tool_call_id=runtime.tool_call_id)], "citation_registry": registry})`.
  - [ ] Leave the `chainlens.research` async branch unchanged — it returns an in-flight `run_id`, not a completed result, so no citation is minted there.

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/subagents/middleware_stack.py`
  - [ ] Import `build_citation_state_mw` from `...shared.middleware.citation_state`.
  - [ ] Add `"citation": build_citation_state_mw()` to the returned dict.

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/snippets/output_contract_base.md`
  - [ ] Append: "When a finding is drawn from a scraper run, append that run's `[n]` (the tool result states `Cite this scraper run as [n]`) to the finding text so the citation survives into the final answer. Copy the label exactly; never invent one."

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/citations/on.md`
  - [ ] Update the citable-results sentence to include "and scraper specialists' run-backed findings".

- [ ] `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py`
  - [ ] Extend `CITATION_REGEX` and `parse_citation_markers` to recognize `run_<uuid>` payloads.
  - [ ] Add `RunCitationMarker` dataclass and include it in the `CitationMarker` union.
  - [ ] Keep the regex byte-for-byte identical to the frontend `CITATION_REGEX`.

### Frontend

- [ ] `nowing_web/lib/citations/citation-parser.ts`
  - [ ] Update `CITATION_REGEX` to include a `run_[0-9a-fA-F-]+` alternative.
  - [ ] Add `run` kind to the `CitationToken` union.
  - [ ] Parse `run_` prefixed payloads into `{ kind: "run", runId: captured.trim() }`.
  - [ ] Add `nowing_web/lib/citations/citation-parser.test.ts` with at least:
    - `run_<uuid>` parses to a run token.
    - `run_` handles do not collide with numeric chunk citations.

- [ ] `nowing_web/components/citations/citation-renderer.tsx`
  - [ ] Import `RunCitation`.
  - [ ] Add branch `if (token.kind === "run")` returning `<RunCitation key={...} runId={token.runId} />`.

- [ ] `nowing_web/components/citations/run-citation.tsx` (new)
  - [ ] Inline chip with a `Database` icon and tooltip text "See where this came from".
  - [ ] On click, call `openRunCitationPanelAtom({ runId })`.

- [ ] `nowing_web/components/citations/run-citation-panel.tsx` (new)
  - [ ] Header "Scraper run" with close button.
  - [ ] Extract `scraperRunId = runId.replace(/^run_/, "")`.
  - [ ] Read `workspaceId` from `useParams` and render `<RunDetail workspaceId={workspaceId} runId={scraperRunId} />`.
  - [ ] Show "Open a workspace to view this run." when `workspaceId` is not finite.

- [ ] `nowing_web/atoms/citation/citation-panel.atom.ts`
  - [ ] Replace `chunkId: number | null` with `target: CitationTarget | null` where `CitationTarget = { kind: "chunk"; chunkId: number } | { kind: "run"; runId: string }`.
  - [ ] Keep `openCitationPanelAtom` opening chunk targets.
  - [ ] Add `openRunCitationPanelAtom` opening run targets.
  - [ ] Update `closeCitationPanelAtom` to reset to `initialState`.

- [ ] `nowing_web/components/layout/ui/right-panel/RightPanel.tsx`
  - [ ] Dynamic import `RunCitationPanelContent`.
  - [ ] Update `citationOpen` checks to `citationState.isOpen && citationState.target != null`.
  - [ ] In the citation tab render, branch on `citationState.target.kind`:
    - `run` → `<RunCitationPanelContent runId={...} onClose={closeCitation} />`
    - `chunk` → `<CitationPanelContent chunkId={...} onClose={closeCitation} />`

### Evals / parity

- [ ] `nowing_evals/src/nowing_evals/core/parse/citations.py`
  - [ ] Update `CITATION_REGEX` to the same pattern as `nowing_web/lib/citations/citation-parser.ts`.
  - [ ] Add a `RunCitation` dataclass and include it in the `CitationToken` union.
  - [ ] Add handling in `parse_citations` for `run_` payloads.
  - [ ] Update `nowing_evals/tests/core/test_parse_citations.py` parity table to include a `run_<uuid>` case.

### Tests

- [ ] `nowing_backend/tests/unit/agents/multi_agent_chat/shared/citations/test_markers.py`
  - [ ] Add `test_run_maps_to_run_handle` and `test_run_without_handle_is_dropped`.

- [ ] `nowing_backend/tests/unit/capabilities/access/test_run_citation.py` (new)
  - [ ] `test_attaches_run_and_returns_label_with_ordinal`.
  - [ ] `test_same_run_dedups_to_one_label`.

- [ ] `nowing_backend/tests/unit/capabilities/access/test_agent_tools.py`
  - [ ] Add `_invoke` helper that calls the raw coroutine with a stand-in `ToolRuntime`.
  - [ ] Update existing `ainvoke` calls to use `_invoke`.
  - [ ] Add `test_tool_registers_run_citation_when_stored` asserting the returned `Command` carries a `citation_registry` with a `RUN` entry and the label in the message content.
  - [ ] Add `test_runtime_survives_langchain_arg_parsing` asserting `tool._parse_input({..., "runtime": "RT"}, ...)` keeps `runtime`.

- [ ] `nowing_backend/tests/unit/tasks/chat/streaming/flows/shared/test_assistant_finalize_citations.py`
  - [ ] Add `test_run_ordinal_resolves_to_run_marker` asserting `[1]` with a `RUN` registry becomes `[citation:run_<uuid>]`.

## Dev Notes

- **Port, do not blindly copy.** The SurfSense stack is the same (FastAPI + Pydantic v2, LangGraph, Next.js + TypeScript), but Nowing already has a `Run` model, a `RunDetail` component, and memory provenance fields (`source_run_id`, `source_capability`, `source_input`). Reuse those instead of re-implementing run display.
- The capability tool must return a `Command(update=...)` with a `ToolMessage` so LangGraph merges both the message content and the `citation_registry` state. Returning a plain string/dict drops the registry.
- `runtime` injection: `StructuredTool.from_function` with an explicit `args_schema` still looks at the coroutine signature. Add `runtime: ToolRuntime` to `_run` and set `_run.__annotations__["runtime"] = ToolRuntime` so the runtime object is passed but not exposed to the model as an input field. Update unit tests to call the coroutine directly with a stand-in `ToolRuntime`.
- The deep-research `chainlens.research` async branch is out of scope for this story. It returns an in-flight `run_id` before the background task finishes; minting a RUN citation there would point to an empty/pending run. Continue returning the existing `{"run_id": "run_...", "status": "running"}` object.
- Run retention is ~30 days (see `RUNS_RETENTION_DAYS` in `app/capabilities/core/runs.py`). The citation handle `run_<uuid>` is a soft reference; if the run is cleaned up, the citation marker still renders and the panel should show a missing-run state, not a 500. This mirrors the existing `Memory.citation` behavior.
- `Memory` provenance (FR-39 / Story 9.6a) already stores an immutable copy of `Run.capability` and `Run.input`. The run citation panel fetches these from the live `Run` row, which is fine because the panel is read-only and the run is still within retention when the chat turn happens.
- The citation registry merge reducer (`_citation_registry_merge_reducer` in `app/agents/chat/multi_agent_chat/shared/state/reducers.py`) and `load_registry` are already implemented. Adding `build_citation_state_mw` to the shared subagent stack is the only wiring needed for non-filesystem specialists to contribute `citation_registry` updates.
- Keep the canonical regex identical in three places: `nowing_web/lib/citations/citation-parser.ts`, `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py`, and `nowing_evals/src/nowing_evals/core/parse/citations.py`. The evals parity test is the guard.
- Do not fabricate public web URLs for `RUN` citations. The payload is always the internal `run_<uuid>` handle; the frontend panel resolves it via `ScrapersApiService.getRun`.

## Verification

- [ ] Backend unit tests pass:
  ```bash
  cd nowing_backend
  pytest tests/unit/agents/multi_agent_chat/shared/citations/test_markers.py \
         tests/unit/capabilities/access/test_agent_tools.py \
         tests/unit/capabilities/access/test_run_citation.py \
         tests/unit/tasks/chat/streaming/flows/shared/test_assistant_finalize_citations.py \
         tests/unit/services/test_memory_run_citation.py -q
  ```

- [ ] Evals parity test passes:
  ```bash
  cd nowing_evals
  pytest tests/core/test_parse_citations.py -q
  ```

- [ ] Web typecheck and lint:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    lib/citations/citation-parser.ts \
    lib/citations/citation-parser.test.ts \
    components/citations/citation-renderer.tsx \
    components/citations/run-citation.tsx \
    components/citations/run-citation-panel.tsx \
    atoms/citation/citation-panel.atom.ts \
    components/layout/ui/right-panel/RightPanel.tsx
  ```

- [ ] Manual / Playwright smoke: from chat, invoke a scraper (e.g. `web.scrape`), verify the assistant answer shows a "Source" chip, click it, and confirm the right panel loads the run's input/output/progress.

## References

- Upstream PR: `MODSetter/SurfSense#1619`
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/models.py` (`CitationSourceType`)
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/markers.py` (`to_frontend_payload`)
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/registry.py` (`CitationRegistry`, `merge`)
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/citations/parser.py`
- `nowing_backend/app/capabilities/core/access/agent.py` (capability tool adapter)
- `nowing_backend/app/capabilities/core/access/run_citation.py` (new helper)
- `nowing_backend/app/capabilities/core/runs.py` (`record_run`, `RUN_OUTPUT_CHAR_CAP`)
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/middleware_stack.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/citation_state.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/shared/snippets/output_contract_base.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/citations/on.md`
- `nowing_backend/app/db.py` (`Run`, `Memory`)
- `nowing_backend/app/schemas/memory.py` (`MemorySearchHit.citation`)
- `nowing_web/lib/citations/citation-parser.ts`
- `nowing_web/components/citations/citation-renderer.tsx`
- `nowing_web/components/citations/run-citation.tsx` (new)
- `nowing_web/components/citations/run-citation-panel.tsx` (new)
- `nowing_web/atoms/citation/citation-panel.atom.ts`
- `nowing_web/components/layout/ui/right-panel/RightPanel.tsx`
- `nowing_web/app/dashboard/[workspace_id]/playground/components/run-detail.tsx`
- `nowing_evals/src/nowing_evals/core/parse/citations.py`
