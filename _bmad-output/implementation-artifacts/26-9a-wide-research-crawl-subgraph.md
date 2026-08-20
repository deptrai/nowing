---
story_key: "26-9a"
epic: "epic-26"
story: "26.9a"
title: "Wide Research Crawl Subgraph for DSH Missions"
status: "review"
baseline_commit: "cdb95035773a4f653d8670911cd5432432f5524d"
---

# Story 26.9a: Wide Research Crawl Subgraph for DSH Missions

## Source Artifacts

- **PRD:** `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — FR-37 (Deep-Research Cost Metering), FR-38 (Research Degradation & Self-Host Independence), FR-24 (Deep-Research Engine Integration), FR-39 (Memory→Scraper-Run Provenance).
- **Epics:** `_bmad-output/planning-artifacts/epics.md` — Epic 26, Story 26.8, Story 26.9b.
- **Architecture:** `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` — AD-102 (Decoupled Sidecar), AD-106 (Agent-Team Hierarchical Delegation), AD-107 (Hermetic Testability), AD-108 (Checkpoint/Resumption), AD-112 (In-Sandbox Python Data Science Studio).
- **ChainLens (cross-repo):** `chainlens-research/_bmad-output/implementation-artifacts/stories/52-1-dsh-multi-agent-swarm-controller-and-zero-hop-search-pipeline.md` (DSH swarm controller, `output: 'wide_research'` ledger event), `48-3-sse-table-structured-output` (SSE `output=table` + `outputSchema` support). **Direction A uses existing `output=table` + `outputSchema` instead of waiting for a public `output=wide_research` query param.**

---

## Story

As a sales researcher,
I want the DSH `crawl` phase to optionally run a "wide research" query against ChainLens and return a structured source matrix,
so that deep-research missions can start from broad, cited coverage and later compress it into leads (Story 26.9b) or a narrative report.

---

## Technical Context

### Already [BUILT] — DO NOT re-implement

- **`LangGraphMissionExecutor`** — `app/tasks/dsh_worker_langgraph.py` has a 4-node graph `crawl → reasoning → extraction → ingestion`. The `crawl` node calls `DshRestClient.chainlens_research(workspace_id, query)` and stores `sources` in `checkpoint`. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/tasks/dsh_worker_langgraph.py" lines="162-217" />
- **`DshRestClient.chainlens_research`** — `app/tasks/dsh_worker.py` calls `POST /api/v1/workspaces/{workspace_id}/scrapers/chainlens/research?mode=async` with payload `{"query": ..., "mode": "balanced"}` and polls `GET /scrapers/runs/{run_id}`. The terminal `output_text` line is parsed as a JSON `ResearchOutput` dict. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/tasks/dsh_worker.py" lines="163-202" />
- **`ResearchInput` / `ResearchOutput` schemas** — `app/capabilities/chainlens/research/schemas.py`. `ResearchInput` has `query`, `mode`, `sources`, `system_instructions`, `history`, `chat_id`, `tier`, `workspace_id`, `correlation_id`. `ResearchOutput` has `answer`, `sources`, `cost_micros`, `cost_dollars`, `degraded`, `status`, etc. No `output` or `output_schema` fields yet. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/capabilities/chainlens/research/schemas.py" lines="69-184" />
- **ChainLens `POST /api/v1/search` contract** — ChainLens `ChatRequestBody` supports `output` values `search | answer | research | contents | table | csv | share | code_context` and `outputSchema` (Story 48-3). Nowing's `chainlens.research` executor does **not** yet forward these. <ref_snippet file="/Users/luisphan/Documents/chainlens-research/apps/api/src/search/search-request.types.ts" lines="184-187" />
- **`ChainLensServiceAuth.cost_dollars_to_micros`** — already converts `costDollars` → micros. `ResearchOutput.cost_micros` is already populated. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/chainlens/auth.py" lines="40-45" />
- **`dsh_worker.py` checkpoint update** — `_checkpoint_update` builds JSON-serialisable payloads; `patch_dsh_mission_checkpoint` on `dsh_routes.py` persists to `dsh_missions.checkpoint` JSONB. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/routes/dsh_routes.py" lines="312-349" />

### [GAP] this story closes

1. **Crawl node cannot request structured wide-research output.** It always calls `chainlens.research` with default `mode=balanced` and no `output`/`output_schema`.
2. **No `wide_research_matrix` persistence.** The `crawl` node only stores `sources`; it does not build/store a topic×source matrix.
3. **No resumption hook for wide research.** The `crawl` node skips on `_subtask_success(state, "crawl")`, but if `checkpoint.wide_research_matrix` exists, it should also skip the ChainLens call.

---

## Critical Design Decisions (Direction A)

1. **Use ChainLens `output=table` + `outputSchema` (available today).**
   - We do **not** wait for a ChainLens `output=wide_research` query param. Story 52.1 uses `output: 'wide_research'` only as a `billableEventType` in the DSH swarm ledger; the public `POST /api/v1/search` DTO does **not** list `wide_research`.
   - `output=table` is streaming-only and compatible with the existing SSE call path. `outputSchema` asks ChainLens to return a structured JSON table.
   - If `outputSchema` is omitted or ChainLens returns markdown, the subgraph falls back to parsing the `answer` markdown table.

2. **`ResearchInput` gains `output` and `output_schema` fields.**
   - `output: Literal["answer", "research", "table"] | None = None` (default keeps current behaviour).
   - `output_schema: dict[str, Any] | None = None` — a JSON schema describing the requested matrix. Example in AC-2.
   - The executor forwards these to ChainLens in `_call_chainlens` body.

3. **`ResearchOutput` gains `structured_output: dict | None`.**
   - When ChainLens emits a `done` frame with an `output` object (because `outputSchema` was provided), the SSE parser stores it here.
   - If `structured_output` is missing, the subgraph parses `answer`.

4. **Crawl "subgraph" is a `StateGraph` invoked inside `_crawl_node`.**
   - New `app/tasks/dsh_worker_crawl_subgraph.py` defines `WideResearchCrawlSubgraph.build()` returning `StateGraph`.
   - `LangGraphMissionExecutor._crawl_node` checks `payload.get("extras", {}).get("research_mode") == "wide"` and, when `DSH_EXECUTOR_ENGINE=langgraph`, runs the subgraph instead of the inline `chainlens_research` call.
   - The legacy executor (`DeepLeadResearchExecutor`) is unchanged and does not support wide research (acceptable; this is LangGraph-only).

5. **Wide-research matrix shape.**
   ```json
   {
     "topics": ["topic A", "topic B"],
     "sources": [{"title": "...", "url": "...", "source_type": "web"}],
     "matrix": [[true, false], [false, true]]
   }
   ```
   - `matrix[i][j]` = `true` if `sources[i]` supports `topics[j]`.
   - Alternative `rows` format allowed if ChainLens `outputSchema` returns rows: `[{"entity": "...", "attribute": "...", "value": "...", "source_url": "..."}]`.

6. **Cost, degradation, resumption.**
   - `cost_micros` is read directly from `ResearchOutput.cost_micros` (already converted from `costDollars`).
   - `ResearchOutput.status` in `("partial", "insufficient_evidence", "timeout", "engine_unavailable")` or `degraded=True` triggers `degraded=true` in checkpoint.
   - Resumption: `_subtask_success(state, "crawl")` and `checkpoint.wide_research_matrix` present → skip ChainLens and rehydrate.

---

## Acceptance Criteria

### AC-1: LangGraph crawl node dispatches to wide-research subgraph

- **Given** `DSH_EXECUTOR_ENGINE=langgraph` and mission `payload["extras"]["research_mode"] == "wide"`,
- **When** `LangGraphMissionExecutor` reaches the `crawl` node,
- **Then** it calls `WideResearchCrawlSubgraph` instead of the inline `chainlens_research` call.

### AC-2: ChainLens called with `output=table` and `outputSchema`

- **Given** a workspace with a valid `ChainLens` API key,
- **When** the crawl subgraph calls `DshRestClient.chainlens_research`,
- **Then** the JSON payload sent to `POST .../scrapers/chainlens/research?mode=async` contains:
  - `query` (from `payload.query`),
  - `mode` (`payload.extras.get("mode", "balanced")`),
  - `output: "table"`,
  - `output_schema` (a matrix schema), e.g.:
    ```json
    {
      "type": "object",
      "properties": {
        "topics": { "type": "array", "items": { "type": "string" } },
        "sources": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "title": { "type": "string" },
              "url": { "type": "string" },
              "source_type": { "type": "string" }
            }
          }
        },
        "matrix": {
          "type": "array",
          "items": { "type": "array", "items": { "type": "boolean" } }
        }
      }
    }
    ```

### AC-3: `ResearchInput` and `ResearchOutput` schemas support `output`/`output_schema`

- **Given** `ResearchInput` is used by the `chainlens.research` capability,
- **When** a caller provides `output="table"` and `output_schema`,
- **Then** the capability accepts them and the executor forwards them to the ChainLens `POST /api/v1/search` body.

### AC-4: Structured output parsed into `wide_research_matrix`

- **Given** the ChainLens SSE `done` frame contains an `output` object matching the schema,
- **When** the subgraph finalizes,
- **Then** it stores the validated `output` dict as `checkpoint.wide_research_matrix`.
- **And** it stores `ResearchOutput.sources` as `checkpoint.sources`.

### AC-5: Cost recorded from `ResearchOutput.cost_micros`

- **Given** ChainLens returns a `ResearchOutput` with `cost_micros`,
- **When** the crawl subgraph succeeds,
- **Then** `checkpoint.cost_micros` is set to `ResearchOutput.cost_micros`.

### AC-6: Degradation handled without blocking the graph

- **Given** ChainLens is unavailable, returns `status != "complete"`, or `degraded=True`,
- **When** the crawl subgraph runs,
- **Then** it sets `checkpoint.degraded = true`, records `degradation_reason`, sets `phase=reasoning`, and does not raise (so `extraction`/`ingestion` can continue with empty/fallback sources).

### AC-7: Idempotent resumption

- **Given** a mission whose `checkpoint.subtasks` already contains a successful `crawl` subtask and `checkpoint.wide_research_matrix`,
- **When** the worker reclaims the message after a crash,
- **Then** the crawl subgraph skips the ChainLens call and rehydrates `checkpoint.sources` and `checkpoint.wide_research_matrix`.

### AC-8: Hermetic tests and lint

- `pytest tests/unit/tasks/test_dsh_worker_langgraph.py tests/unit/tasks/test_dsh_worker_crawl_subgraph.py -q` passes.
- `ruff check app/tasks/dsh_worker_langgraph.py app/tasks/dsh_worker_crawl_subgraph.py app/tasks/dsh_worker.py app/capabilities/chainlens/research/schemas.py app/capabilities/chainlens/research/executor.py` is clean.

---

## Implementation Plan

### Step 1 — Extend `ResearchInput` / `ResearchOutput` schemas

In `nowing_backend/app/capabilities/chainlens/research/schemas.py`:
- Add to `ResearchInput`:
  - `output: Literal["answer", "research", "table"] | None = None` (default keeps current behavior; use `table` for wide research).
  - `output_schema: dict[str, Any] | None = None`.
- Add to `ResearchOutput`:
  - `structured_output: dict[str, Any] | None = None` — holds parsed `done.output` when `outputSchema` is used.

### Step 2 — Forward `output`/`output_schema` in ChainLens executor

In `nowing_backend/app/capabilities/chainlens/research/executor.py`:
- `_call_chainlens`: add `output` and `outputSchema` to the request `body` when `payload.output` is set.
- `SseParser.finalize`: if a `done` frame has an `output` object, store it in `ResearchOutput.structured_output`.
- Do **not** change default behaviour when `output` is unset.

### Step 3 — Extend `DshRestClient.chainlens_research`

In `nowing_backend/app/tasks/dsh_worker.py`:
- Change signature to `chainlens_research(self, workspace_id: int, query: str, output: str | None = None, output_schema: dict | None = None, mode: str = "balanced")`.
- Include `output`, `output_schema`, and `mode` in the async payload.

### Step 4 — Build `WideResearchCrawlSubgraph`

New `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py`:
- `WideResearchCrawlSubgraph` with `StateGraph`:
  - `build_research_input` node: read `state["payload"]`, build payload with `output="table"` and `output_schema`.
  - `call_chainlens` node: call `rest_client.chainlens_research(...)` with extended args.
  - `parse_matrix` node: validate `ResearchOutput.structured_output` or parse `answer`; build `wide_research_matrix`; store in `state["checkpoint"]`.
  - `handle_degradation` conditional edge.
- Expose `build(rest_client)` method.

### Step 5 — Wire into `LangGraphMissionExecutor`

In `nowing_backend/app/tasks/dsh_worker_langgraph.py`:
- In `_crawl_node`:
  - If `state["payload"].get("extras", {}).get("research_mode") == "wide"`:
    - Build/run `WideResearchCrawlSubgraph`.
  - Else: keep existing inline `chainlens_research` call (regression guard).
- Ensure resumption uses `_subtask_success(state, "crawl")` and `checkpoint.get("wide_research_matrix")`.

### Step 6 — Tests

- `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py` (new): hermetic graph tests with mocked `DshRestClient`.
- `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph.py` (modify): add test for `research_mode=wide` dispatch and resumption.
- `nowing_backend/tests/unit/capabilities/chainlens/research/` (modify): add test for `output=table` + `output_schema` forward and `structured_output` parsing.
- Use cassettes or `respx` for `httpx` mocking.

---

## Files to Create / Modify

**Create:**
- `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py` — `WideResearchCrawlSubgraph`.
- `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py` — unit tests.

**Modify:**
- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — add `output`, `output_schema`, `structured_output`.
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — forward `output`/`output_schema` to ChainLens; capture `structured_output`.
- `nowing_backend/app/tasks/dsh_worker.py` — extend `DshRestClient.chainlens_research` signature.
- `nowing_backend/app/tasks/dsh_worker_langgraph.py` — dispatch to crawl subgraph.
- `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph.py` — add wide-research tests.

---

## Verification

```bash
cd nowing_backend
uv run --active ruff check app/tasks/dsh_worker.py app/tasks/dsh_worker_langgraph.py app/tasks/dsh_worker_crawl_subgraph.py app/capabilities/chainlens/research/schemas.py app/capabilities/chainlens/research/executor.py tests/unit/tasks/test_dsh_worker*.py tests/unit/capabilities/chainlens/research/
uv run --active pytest tests/unit/tasks/test_dsh_worker.py tests/unit/tasks/test_dsh_worker_langgraph.py tests/unit/tasks/test_dsh_worker_crawl_subgraph.py tests/unit/capabilities/chainlens/research/ -q
```

---

## ATDD Artifacts (red-phase)

- Checklist: `_bmad-output/implementation-artifacts/atdd-checklist-26-9a.md`
- Backend red-phase scaffolds:
  - `nowing_backend/tests/unit/capabilities/chainlens/research/test_wide_research_output.py`
  - `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph_wide.py`
  - `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py`
- All scaffolds currently use `@pytest.mark.skip`; remove per AC as they turn green during `dev-story`.

## Dev Notes

- **No new dependencies.** `langgraph>=1.1.3`, `deepagents>=0.4.12`, `httpx` already declared.
- **PII:** `wide_research_matrix` should not contain raw PII. If `sources` include personal data, use the same masking as the `Source` model (emails/phones redacted by ChainLens; do not add new PII).
- **Cost basis:** `ResearchOutput.cost_micros` is the source of truth. Do not recompute from `costDollars` in the subgraph.
- **Backward compatibility:** `ResearchInput.output` default is `None`; existing chat/agent calls are unaffected. `DshRestClient.chainlens_research` keeps default `mode="balanced"` when `output` not provided.
- **Future:** When ChainLens exposes a public `output=wide_research` (Story 52.2), this subgraph can switch `output="wide_research"` and drop the `output_schema` fallback.

---

## Tasks/Subtasks

- [x] Step 1 — Extend `ResearchInput` / `ResearchOutput` schemas
- [x] Step 2 — Forward `output`/`output_schema` in ChainLens executor
- [x] Step 3 — Extend `DshRestClient.chainlens_research`
- [x] Step 4 — Build `WideResearchCrawlSubgraph`
- [x] Step 5 — Wire into `LangGraphMissionExecutor`
- [x] Step 6 — Make ATDD tests green and run `ruff`

---

## File List

- `nowing_backend/app/capabilities/chainlens/research/schemas.py`
- `nowing_backend/app/capabilities/chainlens/research/executor.py`
- `nowing_backend/app/tasks/dsh_worker.py`
- `nowing_backend/app/tasks/dsh_worker_langgraph.py`
- `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py`
- `nowing_backend/tests/unit/capabilities/chainlens/research/test_wide_research_output.py`
- `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph_wide.py`
- `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py`

---

## Dev Agent Record

### Implementation Plan

1. Add `output`/`output_schema` to `ResearchInput`, `structured_output` to `ResearchOutput`.
2. Update `_call_chainlens` to forward these to ChainLens and `SseParser` to capture `done.output`.
3. Extend `DshRestClient.chainlens_research` signature and payload.
4. Create `WideResearchCrawlSubgraph` as a buildable `ainvoke` entry point with call/parse/resume logic.
5. Modify `LangGraphMissionExecutor._crawl_node` to dispatch to the subgraph when `payload.extras.research_mode == "wide"`.
6. Unskip ATDD tests, make them pass, and keep `ruff` clean.

### Debug Log

- Baseline commit: `cdb95035773a4f653d8670911cd5432432f5524d`.
- `ResearchInput.output`/`output_schema` and `ResearchOutput.structured_output` added to schemas.
- `_call_chainlens` now forwards `output`/`outputSchema` to ChainLens and `SseParser.finalize` captures the `done.output` object.
- `DshRestClient.chainlens_research` accepts `output`, `output_schema`, `mode`.
- `WideResearchCrawlSubgraph` implemented as a standalone `ainvoke` entry point with resumption, cost capture, degradation, and fallback matrix synthesis.
- `LangGraphMissionExecutor._crawl_node` dispatches to the subgraph when `payload.extras.research_mode == "wide"`.
- ATDD red-phase tests unskipped and green; added extra degradation/partial test.

### Completion Notes

- All ACs satisfied.
- 265 existing unit tests in `tests/unit/capabilities/chainlens/research` and `tests/unit/tasks/test_dsh_worker*` remain green.
- 7 new/updated tests pass: `test_wide_research_output.py` (2), `test_dsh_worker_langgraph_wide.py` (1), `test_dsh_worker_crawl_subgraph.py` (4).
- `ruff` clean on all changed Python files.

---

## Change Log

- 2026-08-20: Implemented Story 26.9a end-to-end.
  - Added `output`/`output_schema`/`structured_output` to ChainLens research schemas.
  - Extended ChainLens executor to forward `output`/`outputSchema` and parse `done.output`.
  - Extended `DshRestClient.chainlens_research` with `output`, `output_schema`, `mode`.
  - Created `app/tasks/dsh_worker_crawl_subgraph.py` with resumption, degradation, cost, and matrix synthesis.
  - Wired `LangGraphMissionExecutor._crawl_node` to dispatch to `WideResearchCrawlSubgraph` when `research_mode=wide`.
  - Unskipped and greened ATDD tests; added `test_dsh_worker_crawl_subgraph.py` with fake client.

