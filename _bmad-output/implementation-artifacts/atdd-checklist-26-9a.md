---
stepsCompleted:
  - step-01-preflight-and-context
  - step-02-generation-mode
  - step-03-test-strategy
  - step-04-generate-tests
  - step-05-validate-and-complete
lastStep: step-05-validate-and-complete
lastSaved: "2026-08-20"
workflowType: testarch-atdd
storyId: 26.9a
storyKey: 26-9a-wide-research-crawl-subgraph
storyFile: _bmad-output/implementation-artifacts/26-9a-wide-research-crawl-subgraph.md
atddChecklistPath: _bmad-output/implementation-artifacts/atdd-checklist-26-9a.md
generatedTestFiles:
  - nowing_backend/tests/unit/capabilities/chainlens/research/test_wide_research_output.py
  - nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph_wide.py
  - nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py
inputDocuments: []
---

# ATDD Checklist — Epic 26, Story 26.9a: Wide Research Crawl Subgraph

**Date:** 2026-08-20
**Author:** Master Test Architect
**Primary Test Level:** backend / unit

---

## Story Summary

As a sales researcher,
I want the DSH `crawl` phase to optionally run a "wide research" query against ChainLens and return a structured source matrix,
so that deep-research missions can start from broad, cited coverage and later compress it into leads (Story 26.9b) or a narrative report.

---

## Acceptance Criteria

1. **AC-1:** LangGraph crawl node dispatches to wide-research subgraph when `payload.extras.research_mode == "wide"`.
2. **AC-2:** ChainLens is called with `output="table"` and a matrix `output_schema`.
3. **AC-3:** `ResearchInput` and `ResearchOutput` schemas support `output`/`output_schema`/`structured_output`.
4. **AC-4:** Structured output is parsed into `checkpoint.wide_research_matrix` and `checkpoint.sources`.
5. **AC-5:** `checkpoint.cost_micros` is set from `ResearchOutput.cost_micros`.
6. **AC-6:** Degradation is handled without blocking the graph (`checkpoint.degraded = true`).
7. **AC-7:** Idempotent resumption when `checkpoint.wide_research_matrix` already exists.
8. **AC-8:** Hermetic tests and `ruff` clean.

---

## Story Integration Metadata

- **Story ID:** `26.9a`
- **Story Key:** `26-9a-wide-research-crawl-subgraph`
- **Story File:** `_bmad-output/implementation-artifacts/26-9a-wide-research-crawl-subgraph.md`
- **Checklist Path:** `_bmad-output/implementation-artifacts/atdd-checklist-26-9a.md`
- **Generated Test Files:**
  - `nowing_backend/tests/unit/capabilities/chainlens/research/test_wide_research_output.py`
  - `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph_wide.py`
  - `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py`

---

## Red-Phase Test Scaffolds Created

### API / Schema Tests (2 tests)

**File:** `nowing_backend/tests/unit/capabilities/chainlens/research/test_wide_research_output.py`

- ✅ **Test:** `test_research_input_accepts_output_table_and_output_schema`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-3: `ResearchInput` accepts `output="table"` and `output_schema`.
- ✅ **Test:** `test_research_output_has_structured_output`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-4: `ResearchOutput` carries `structured_output` from the ChainLens `done` frame.

### Component / DSH Executor Tests (1 test)

**File:** `nowing_backend/tests/unit/tasks/test_dsh_worker_langgraph_wide.py`

- ✅ **Test:** `test_crawl_node_dispatches_with_output_table_and_schema`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-1 + AC-2: `LangGraphMissionExecutor._crawl_node` dispatches wide-research mode and calls `chainlens_research` with `output="table"` and `output_schema`.

### Subgraph Tests (3 tests)

**File:** `nowing_backend/tests/unit/tasks/test_dsh_worker_crawl_subgraph.py`

- ✅ **Test:** `test_subgraph_builds_and_persists_matrix`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-1, AC-4, AC-5: `WideResearchCrawlSubgraph` builds, runs, and persists `wide_research_matrix`, `cost_micros`, and `sources`.
- ✅ **Test:** `test_subgraph_marks_degraded_when_chainlens_unavailable`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-6: the subgraph marks `degraded=true` and continues to `reasoning`.
- ✅ **Test:** `test_subgraph_skips_chainlens_when_matrix_already_in_checkpoint`
  - **Status:** RED — `@pytest.mark.skip`
  - **Verifies:** AC-7: resumption skips ChainLens and rehydrates existing `wide_research_matrix`.

---

## Data Factories Created

None. Existing `_FakeDshRestClient` in `test_dsh_worker_langgraph.py` was adapted for the new test file.

---

## Fixtures Created

- `_FakeDshRestClient` in `test_dsh_worker_langgraph_wide.py` records `chainlens_research` kwargs including `output`, `output_schema`, and `mode`.

---

## Verification Commands

```bash
cd nowing_backend
uv run --active ruff check tests/unit/capabilities/chainlens/research/test_wide_research_output.py tests/unit/tasks/test_dsh_worker_langgraph_wide.py tests/unit/tasks/test_dsh_worker_crawl_subgraph.py
uv run --active pytest tests/unit/capabilities/chainlens/research/test_wide_research_output.py tests/unit/tasks/test_dsh_worker_langgraph_wide.py tests/unit/tasks/test_dsh_worker_crawl_subgraph.py -q
```

**Expected red-phase result:** all tests are reported as `skipped` (6 tests). Remove `@pytest.mark.skip` per AC during `dev-story` to turn red → green.
