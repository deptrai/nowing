---
story_key: "26-9a"
epic: "epic-26"
story: "26.9a"
title: "Wide Research Crawl Subgraph for DSH Missions"
status: "ready-for-dev"
baseline_commit: "TBD"
---

# Story 26.9a: Wide Research Crawl Subgraph for DSH Missions

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Crawl node becomes a subgraph, not a monolithic call.**
   - Replace the single `crawl` node in `LangGraphMissionExecutor` with a `crawl_subgraph` that can dispatch to `chainlens.research` or `nowing_mcp` tools.
   - The subgraph receives the mission `query`, `payload`, and `workspace_id`.
   - It returns a list of `sources` and optionally a `wide_research_matrix` JSON.

2. **Output = `wide_research`.**
   - ChainLens sub-agent request builder (`app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` / `agent.py`) is extended with an `output=wide_research` parameter.
   - ChainLens terminal `done` frame is parsed; the body is expected to contain a structured matrix (topic × source) with citations.
   - This story does NOT render the matrix to Excel; that is Story 26.9b.

3. **Reuse existing auth and REST client.**
   - `ChainLensServiceAuth` and `DshRestClient` are used unchanged.
   - No new DB tables; results are written to `checkpoint.sources` and `checkpoint.wide_research_matrix` so resumption works.

4. **Fallback / self-host independence.**
   - If ChainLens returns no results or is unavailable, the subgraph emits `degraded=true` and continues to the next phase.
   - This aligns with Epic 9.1a (research degradation).

---

## Story

As a sales researcher,
I want the DSH `crawl` phase to optionally run a "wide research" query against ChainLens and return a structured source matrix,
so that deep-research missions can start from broad, cited coverage and later compress it into leads (Story 26.9b) or a narrative report.

---

## Acceptance Criteria

### AC-1: Crawl subgraph behind feature flag (AD-112)

- **Given** `DSH_EXECUTOR_ENGINE=langgraph` and the mission payload has `research_mode=wide`,
- **When** `LangGraphMissionExecutor` runs the `crawl` node,
- **Then** it dispatches to the `wide_research` crawl subgraph instead of the default crawl.

### AC-2: ChainLens `output=wide_research` request (AD-112, AD-15)

- **Given** a workspace with a valid `ChainLens` API key,
- **When** the crawl subgraph calls ChainLens,
- **Then** it sends `POST /api/v1/search` SSE with `output=wide_research` and the mission `query`.

### AC-3: Parse terminal `done` frame (FR-37)

- **Given** the SSE stream ends with a `done` event,
- **When** the subgraph processes the terminal frame,
- **Then** it extracts:
  - `done.usage.costDollars` → converted to micros and recorded in `checkpoint.cost_micros`.
  - `done.output.matrix` or `done.output.sources` → stored in `checkpoint.wide_research_matrix`.
  - `done.output.citations` → stored as `checkpoint.sources` (with `source_id` / `url`).

### AC-4: Degradation (FR-38)

- **Given** ChainLens is unavailable or the `done` frame is malformed,
- **When** the crawl subgraph runs,
- **Then** it records `degraded=true` and `degradation_reasons`, sets `checkpoint.phase=reasoning`, and does not block the rest of the graph.

### AC-5: Idempotent resumption (AD-108)

- **Given** a mission whose checkpoint already contains a successful `wide_research` subtask,
- **When** the worker reclaims the message,
- **Then** the crawl subgraph skips the ChainLens call and rehydrates `checkpoint.sources` and `checkpoint.wide_research_matrix`.

### AC-6: Hermetic tests

- `pytest tests/unit/tasks/test_dsh_worker_langgraph.py tests/unit/tasks/test_dsh_worker_wide_research.py -q` passes.
- `ruff check app/tasks/dsh_worker_langgraph.py app/tasks/dsh_worker_crawl_subgraph.py` is clean.

---

## Implementation Notes

### New files

| File | Purpose |
|---|---|
| `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py` | `WideResearchCrawlSubgraph` class with `build()` and node methods. |
| `nowing_backend/tests/unit/tasks/test_dsh_worker_wide_research.py` | Hermetic tests using cassettes for ChainLens SSE. |

### Changed files

| File | Change |
|---|---|
| `nowing_backend/app/tasks/dsh_worker_langgraph.py` | Replace `crawl` node with conditional `crawl_subgraph` call. |
| `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` | Add `output` parameter to the research tool builder. |
| `nowing_backend/app/services/chainlens/research/executor.py` | Accept `output=wide_research` and return structured matrix. |
