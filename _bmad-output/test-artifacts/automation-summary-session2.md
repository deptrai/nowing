---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-identify-targets', 'step-03-generate-tests', 'step-03c-aggregate', 'step-04-run-and-validate']
lastStep: 'step-04-run-and-validate'
lastSaved: '2026-04-27'
workflowType: 'testarch-automate'
inputDocuments:
  - '_bmad-output/test-artifacts/traceability-report-backend.md'
  - '_bmad-output/test-artifacts/traceability-report.md'
  - '_bmad-output/test-artifacts/automation-summary.md'
  - '_bmad-output/test-artifacts/automation-summary-backend.md'
  - '_bmad-output/test-artifacts/test-review.md'
  - '_bmad/tea/config.yaml'
---

# Test Automation Session 2 — Fullstack Gap Closure

**Date**: 2026-04-27
**Stack**: `fullstack` (nowing_backend + nowing_web)
**Mode**: BMad-Integrated (stories + traceability reports available)

---

## Step 1: Preflight & Context

### Stack Detection
- **Detected**: `fullstack`
  - Backend: `pyproject.toml` (Python 3.12, FastAPI, pytest)
  - Frontend: `package.json` (Next.js 16, React 19, Vitest 3.2.4, Playwright)
  - Both `conftest.py` and `playwright.config.ts` present

### Execution Mode
- **BMad-Integrated** — stories, traceability reports, and prior automation summaries available

### Framework Verification
- BE: pytest 9.x + pytest-asyncio + pytest-xdist + pytest-mock ✅
- FE unit: Vitest 3.2.4 + @testing-library/react ✅
- FE e2e: Playwright ✅

### Config Flags
- `tea_use_playwright_utils`: true
- `tea_use_pactjs_utils`: false
- `tea_pact_mcp`: none
- `tea_browser_automation`: auto
- `test_stack_type`: auto → detected fullstack

### Existing Test Inventory
- BE: 159 test files (646 unit passing, integration tests separate)
- FE unit: 26 test files (401 passing)
- FE e2e: 6 spec files (Playwright)

### Prior Sessions
1. **Session 1 (FE)**: 112 tests generated for `lib/` utilities — all passing
2. **Session 1 (BE)**: 20 tests for auth routes (GAP-1 closed)
3. **Test Review**: Score 69/100, 56 violations found → all 14 critical/high/medium fixes applied

### Open Gaps (from traceability-report-backend.md)
| GAP | Story | Priority | Status |
|-----|-------|----------|--------|
| GAP-1 | Auth API (1.2) | P0 | ✅ CLOSED (session 1) |
| GAP-2 | Chat Session API route (3.1) | P1 | ❌ Open |
| GAP-3 | SSE Stream route (3.2) | P1 | ❌ Open |
| GAP-4 | Gift system backend (6.1-6.5, 6.8) | P2 | ❌ Open |
| GAP-5 | Model quota enforcement (3.5/5.4) | P2 | ❌ Open |

### New Code Since Last Report (2026-04-21 → 2026-04-27)
- **Story 9-UX-1b**: Background agent resume (run_manager, run_event_writer, new chat routes)
- **Story 9-UX-1**: Orchestra strip v2, source attribution, narration
- **Story 9-UX-1c**: Architectural fixes (ETA, server timestamps)
- New test files added: test_run_lifecycle.py, test_run_event_writer.py, test_run_manager.py, test_subscribe_first_replay.py, test_vercel_wire_format.py, test_source_attribution_middleware.py

### FE Gaps (from traceability-report.md)
- P0/P1: 100% covered ✅
- P2 gaps: 2 criteria uncovered (non-blocking)

### Knowledge Fragments Loaded
- Core: test-levels-framework, test-priorities-matrix, data-factories, selective-testing, ci-burn-in, test-quality
- Extended (on-demand): error-handling, timing-debugging

---

## Step 2: Coverage Plan — Full Audit

### Scope: Full coverage audit (BE + FE)

---

### Backend Targets

#### T1 — `citation_harvester.py` (P1, Unit)
**File**: `app/services/citation_harvester.py` (79 lines, 3 functions)
**Coverage**: 0% — zero tests exist
**Story**: 9-UX-1 (source attribution)
**Target**: `tests/unit/services/test_citation_harvester.py`
**Tests planned**:
- `_infer_provider`: all known providers (coingecko, defillama, goplus, etherscan, dexscreener, messari, coinmarketcap), unknown suffix → "Unknown", prefix/infix match, case-insensitive
- `harvest_citations`: single tag, multiple tags, duplicate IDs (first wins), nested/adjacent tags, empty input, no tags
- `strip_cite_tags`: removes tags keeping inner value, no tags returns original, multiple tags
- **Est. ~18-22 tests**

#### T2 — Chat route endpoints coverage expansion (P1, Unit)
**File**: `app/routes/new_chat_routes.py` (1900+ lines)
**Existing coverage**: 15 tests in `test_chat_routes.py` (CRUD: create/list/get/delete threads)
**Missing endpoints** (from new 9-UX-1b code):
- `POST /threads/{id}/runs` — dispatch run
- `GET /threads/{id}/runs/active` — list active runs
- `GET /threads/{id}/runs/{rid}/stream` — SSE replay+tail
- `POST /threads/{id}/resume` — resume abandoned run
- `POST /threads/{id}/regenerate` — regenerate (backward-compat)
- `POST /threads/{id}/messages` — create message
- `PATCH /threads/{id}/visibility` — update visibility
**Target**: expand `tests/unit/routes/test_chat_routes.py`
**Tests planned**: ~20-25 tests (happy path + auth + validation per endpoint)

#### T3 — `run_manager.py` expansion (P1, Unit)
**File**: `app/tasks/chat/run_manager.py` (16.9K)
**Existing**: 7 tests (mark_abandoned, cancel_run, active_runs)
**Missing**: `start_run()`, `resume_run()`, `_run_agent_task()` internal flow, feature flag guard
**Target**: expand `tests/unit/tasks/test_run_manager.py`
**Tests planned**: ~8-10 new tests

#### T4 — Chat routes GAP-2 (Story 3.1) (P1, Unit)
**Status**: Already CLOSED by existing `test_chat_routes.py` (15 tests for create/list/get/delete)
**Note**: traceability report from April 21 marked this as "NONE" but tests were added since then

#### T5 — Gift system GAP-4 (Stories 6.1-6.5, 6.8) (P2, Unit)
**Missing**: entire gift API — checkout, redeem, history, admin approve
**Decision**: DEFER — P2 priority, gift system may not be actively used
**Recommend**: create when gift stories enter active development

#### T6 — Model quota GAP-5 (Story 3.5/5.4) (P2, Unit)
**Missing**: quota enforcement logic
**Decision**: DEFER — P2 priority

---

### Frontend Targets

#### T7 — `chat-runs-api.service.ts` (P1, Unit)
**File**: `lib/apis/chat-runs-api.service.ts` (96 lines)
**Coverage**: 0%
**Target**: `__tests__/lib/apis/chat-runs-api.test.ts`
**Tests planned**: mock fetch, test `startRun()`, `getActiveRuns()`, `cancelRun()`, error handling
**Est. ~10-12 tests**

#### T8 — `citation/schema.ts` (P1, Unit)
**File**: `components/tool-ui/citation/schema.ts` (91 lines)
**Coverage**: 0% — Zod schema validation
**Target**: `__tests__/components/tool-ui/citation/schema.test.ts`
**Tests planned**: valid input parses, missing fields rejected, edge cases
**Est. ~8-10 tests**

#### T9 — `chart-spec.ts` (P2, Unit)
**File**: `components/new-chat/report/embedded-charts/chart-spec.ts` (53 lines)
**Coverage**: 0% — chart type mapping logic
**Target**: `__tests__/components/new-chat/report/chart-spec.test.ts`
**Tests planned**: each chart type maps correctly, unknown type fallback
**Est. ~6-8 tests**

#### T10 — Report components (P2, Component)
**Files**: `crypto-report-layout.tsx` (85L), `report-toc.tsx` (152L), `token-hero-card.tsx` (201L), `source-detail-panel.tsx` (142L), `citation-chip-v2.tsx` (155L)
**Coverage**: 0% on all
**Decision**: DEFER to next session — these are presentational components, lower risk. Prioritize T1-T3, T7-T8 first.

#### T11 — Orchestra components (P2, Component)
**Files**: `lab-header.tsx` (106L), `agent-lane.tsx` (202L), `activity-timeline.tsx` (101L)
**Coverage**: Partially covered by `orchestra-lab.test.tsx` (33 tests) — but that file tests the atom reducers + some component behavior. The individual component files may need specific tests.
**Decision**: DEFER — existing 33-test suite provides good coverage of the orchestration layer

---

### Priority Summary

| ID | Target | Priority | Level | Est. Tests | Status |
|----|--------|----------|-------|------------|--------|
| ID | Target | Priority | Level | Est. Tests | Actual | Status |
|----|--------|----------|-------|------------|--------|--------|
| T1 | citation_harvester.py | **P1** | Unit | 18-22 | **32** | ✅ DONE |
| T2 | Chat route expansion (runs/resume) | **P1** | Unit | 20-25 | **27** | ✅ DONE |
| T3 | run_manager expansion | **P1** | Unit | 8-10 | **7** | ✅ DONE |
| T7 | chat-runs-api.service.ts | **P1** | Unit | 10-12 | **14** | ✅ DONE |
| T8 | citation/schema.ts | **P1** | Unit | 8-10 | **37** | ✅ DONE |
| T9 | chart-spec.ts | P2 | Unit | 6-8 | **14** | ✅ DONE |
| T5 | Gift system (6.1-6.5, 6.8) | P2 | Unit | ~30 | — | DEFER |
| T6 | Model quota (3.5/5.4) | P2 | Unit | ~10 | — | DEFER |
| T10 | Report components | P2 | Component | ~25 | — | DEFER |
| T11 | Orchestra components | P2 | Component | ~15 | — | DEFER |

**Session target: T1 + T2 + T3 + T7 + T8 + T9 = ~70-87 new tests → Actual: 131 new tests**

### Execution Order (completed)
1. **T1** (citation_harvester) — 32 tests, 0.09s
2. **T8** (citation schema) — 37 tests
3. **T9** (chart-spec) — 14 tests
4. **T7** (chat-runs-api) — 14 tests
5. **T2** (chat routes expansion) — 27 tests
6. **T3** (run_manager expansion) — 7 tests

---

## Step 3: Test Generation — Results

### Files Created

| File | Target | Tests | Time |
|------|--------|-------|------|
| `tests/unit/services/test_citation_harvester.py` | T1 | 32 | 0.09s |
| `__tests__/components/tool-ui/citation/schema.test.ts` | T8 | 37 | — |
| `__tests__/components/new-chat/report/chart-spec.test.ts` | T9 | 14 | — |
| `__tests__/lib/apis/chat-runs-api.test.ts` | T7 | 14 | — |
| `tests/unit/routes/test_chat_routes.py` (expanded) | T2 | +27 | 39s |
| `tests/unit/tasks/test_run_manager.py` (expanded) | T3 | +7 | 32s |

### Bug Fixes During Generation
- Fixed pre-existing test bug: `test_mark_abandoned_skipped_when_flag_disabled` patched `RESUMABLE_RUNS_ENABLED` but actual attribute is `_RESUMABLE_RUNS_ENABLED`

---

## Step 4: Run & Validate

### Backend Unit Tests
- **904 passed**, 14 failed (all pre-existing), 1 skipped
- Pre-existing failures:
  - `test_crypto_subagent_wiring` — code uses `_build_gp_middleware` but test expects `_build_gp_middleware()`
  - 9 `test_page_limits_gdrive` — `NameError: CONNECTOR_ID`
  - 4 `test_page_limits_onedrive_dropbox` — same `NameError: CONNECTOR_ID`
- **All 66 new/expanded BE tests pass** ✅

### Frontend Vitest
- **466 passed**, 0 failed
- Up from 401 → +65 new tests
- **All 65 new FE tests pass** ✅

### Total New Tests This Session: **131**
- BE: 66 (32 + 27 + 7)
- FE: 65 (37 + 14 + 14)
