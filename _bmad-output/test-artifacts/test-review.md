---
stepsCompleted: ['step-01-load-context', 'step-02-discover-tests', 'step-03-quality-evaluation', 'step-04-generate-report']
lastStep: 'step-04-generate-report'
lastSaved: '2026-04-27'
workflowType: 'testarch-test-review'
inputDocuments:
  - _bmad/tea/config.yaml
  - .claude/skills/bmad-testarch-test-review/resources/tea-index.csv
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/test-quality.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/data-factories.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/test-levels-framework.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/test-healing-patterns.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/selector-resilience.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/timing-debugging.md
  - .claude/skills/bmad-testarch-test-review/resources/knowledge/playwright-cli.md
---

# Test Quality Review — Full Suite

**Quality Score**: 69/100 (D — Needs Improvement)
**Review Date**: 2026-04-27
**Review Scope**: suite (all tests in repo)
**Reviewer**: TEA Agent (Test Architect)

---

Note: This review audits existing tests; it does not generate tests.
Coverage mapping and coverage gates are out of scope here. Use `trace` for coverage decisions.

## Executive Summary

**Overall Assessment**: Needs Improvement

**Recommendation**: Request Changes

### Key Strengths

- ✅ Integration DB isolation: savepoint-based `transaction.rollback()` pattern auto-cleans all DML — no manual cleanup needed per test
- ✅ Parallel execution infrastructure: `pytest-xdist` (`-n auto`) + Playwright `fullyParallel: true` — 85% of tests parallelizable
- ✅ Frontend timer handling: `vi.useFakeTimers()` pattern consistently used (e.g., `use-typewriter.test.ts`) — no flaky timer waits in FE unit tests
- ✅ Comprehensive test coverage breadth: 152 files / 1,245 tests across BE-unit, BE-integration, BE-api, FE-unit, FE-e2e

### Key Weaknesses

- ❌ **8 HIGH isolation violations** — module-level litellm monkey-patches with no teardown, class-level method patching without restoration, session-scoped shared auth vulnerable to destructive tests
- ❌ **Global state mutations without cleanup** — `rm._active_runs` dict mutations in `test_run_manager.py` skip cleanup on assertion failure; `importlib.reload()` leaves modules in unknown state
- ❌ **500ms autouse sleep** in `integration/tools/conftest.py` adds 10+ seconds dead wait per CI run with zero benefit when network calls are mocked
- ❌ **UUID collision risk** — two independent `itertools.count(1)` counters in retriever and google_unification conftests produce identical UUID sequences in shared DB sessions

### Summary

Test suite has solid structural foundations — savepoint rollback for DB isolation, xdist parallelization, and good fixture scoping patterns. However, the integration agents layer has accumulated dangerous module-level mutations: litellm's `acompletion` is permanently monkey-patched at import time, agent class methods are replaced at class level without `patch.object()` context managers, and production-level dicts are mutated without `try/finally` guards. These 8 HIGH isolation violations create real risk of inter-test interference that manifests as flaky failures in CI.

Performance is dragged down by a blanket 500ms autouse sleep on all tool integration tests, timing-dependent asyncio.sleep patterns across 5 connector test files, and a module reload anti-pattern that conflicts with xdist's process-fork model. Determinism is reasonable (73/C) with only hard-wait patterns in 2 files, but the run_manager tests' `importlib.reload()` approach is fragile under parallelism.

---

## Quality Score Breakdown

### Dimension Scores

| Dimension | Weight | Score | Grade | HIGH | MEDIUM | LOW |
|-----------|--------|-------|-------|------|--------|-----|
| Determinism | 30% | 73 | C | 0 | 3 | 6 |
| Isolation | 30% | 63 | D | 8 | 11 | 5 |
| Maintainability | 25% | 69 | D | 1 | 7 | 0 |
| Performance | 15% | 72 | C | 3 | 8 | 4 |

### Weighted Calculation

```
Determinism:     73 × 0.30 = 21.9
Isolation:       63 × 0.30 = 18.9
Maintainability: 69 × 0.25 = 17.3
Performance:     72 × 0.15 = 10.8
                              ────
Weighted Total:               68.8 → 69/100
Grade:                        D
```

### Aggregate Violations

| Severity | Count |
|----------|-------|
| HIGH | 12 |
| MEDIUM | 29 |
| LOW | 15 |
| **Total** | **56** |

---

## Step 1: Context & Knowledge Base

### Scope
- **Review scope**: suite (all tests in repo)
- **Detected stack**: fullstack (Python BE pytest + Next.js FE vitest + Playwright)
- **Playwright Utils**: enabled (API-only profile)
- **Browser automation**: auto (CLI + MCP as needed)

### Knowledge Fragments Loaded

**Core (7):**
- test-quality.md
- data-factories.md
- test-levels-framework.md
- test-healing-patterns.md
- selector-resilience.md
- timing-debugging.md
- playwright-cli.md

## Step 2: Discovery & Metadata

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total test files | 152 |
| Total test cases | 1,245 |
| Total lines | 31,564 |

### By Level

| Level | Files | Tests |
|-------|-------|-------|
| BE-unit | 80 | 574 |
| BE-integration | 36 | 190 |
| BE-api | 4 | 52 |
| FE-unit | 26 | 401 |
| FE-e2e | 6 | 28 |

### Infrastructure
- **BE conftest files**: 12 (root + per-directory)
- **FE config**: vitest.config.ts, vitest.setup.ts, playwright.config.ts

---

## Step 3: Quality Evaluation

### 3A — Determinism (73/C)

**9 violations** (0 HIGH, 3 MEDIUM, 6 LOW)

| File | Severity | Category | Description |
|------|----------|----------|-------------|
| `tests/unit/tasks/test_run_manager.py:101` | MEDIUM | hard-wait | `asyncio.sleep(999)` — non-deterministic timing |
| `tests/integration/chat/test_run_lifecycle.py:197` | MEDIUM | hard-wait | `asyncio.sleep(0.2)` for flush — timing-dependent |
| `__tests__/lib/utils.test.ts:49` | MEDIUM | time-dependency | `Date` assertion flaky at day boundary |
| `__tests__/components/new-chat/orchestra-lab.test.tsx` (×6) | LOW | time-dependency | `Date.now()` for relative timestamp props — timing-insensitive, informational |

**Recommendations:**
1. Replace `asyncio.sleep(999)` with mocked coroutine or `asyncio.Event`
2. Replace `asyncio.sleep(0.2)` flush with `await writer.stop()` for deterministic flush
3. Use `vi.useFakeTimers()` for `formatDate(new Date())` assertion

---

### 3B — Isolation (63/D)

**24 violations** (8 HIGH, 11 MEDIUM, 5 LOW) — most critical dimension.

#### HIGH Violations (8)

| # | File | Category | Impact |
|---|------|----------|--------|
| 1 | `tests/integration/agents/conftest.py:24` | global_state_mutation | Module-level litellm monkey-patch (`acompletion`, `num_retries=0`) with **no teardown** — persists entire session |
| 2 | `tests/integration/agents/conftest.py:195` | global_state_mutation | `agent_factory` patches `_agent_cls.ainvoke`/`astream` at class level without restoration |
| 3 | `tests/api/conftest.py:48` | session_scoped_shared_state | Session-scoped `api_client` — client-level state mutations leak across tests |
| 4 | `tests/api/conftest.py:58` | session_scoped_shared_state | Session-scoped `auth_headers` — token-revoking tests invalidate all subsequent API tests |
| 5 | `tests/unit/tasks/test_run_manager.py:60` | global_state_mutation | Direct mutation of `rm._active_runs`/`rm._cancel_events` without `try/finally` — state leaks on assertion failure |
| 6 | `tests/unit/tasks/test_run_manager.py:27` | module_reload_side_effects | `importlib.reload(rm_module)` leaves module in stale state if restore reload fails |
| 7 | `tests/integration/retriever/conftest.py:23` | global_state_mutation | `_id_counter = itertools.count(1)` — UUID collision risk with google_unification counter |
| 8 | `tests/integration/google_unification/conftest.py:34` | global_state_mutation | Same `itertools.count(1)` → identical UUID sequences in shared DB |

#### MEDIUM Violations (11)

| # | File | Category |
|---|------|----------|
| 1-3 | `test_stripe_checkout/webhook/reconciliation.py:16` | Wrong import: `from tests.conftest import TEST_DATABASE_URL` (should be `tests.integration.conftest`) |
| 4 | `test_stripe_checkout.py:77` | Duplicated session-scoped `auth_token` across 3 Stripe test files |
| 5-6 | `test_run_lifecycle.py:41,97` | `LIMIT 1` subquery anchors — implicit order dependency on ambient DB state |
| 7 | `test_chat_routes.py:64` | `app.dependency_overrides` mock mutation inside test body without guaranteed restore |
| 8 | `agents/conftest.py:109` | Single `mock_session` shared across 8 patch targets — masks concurrent session bugs |
| 9 | `document_upload/conftest.py:189` | Bulk-delete purge vulnerable to xdist worker race |
| 10 | `test_run_manager.py:138` | `test_active_runs_dict_initially_empty` has implicit order dependency |
| 11 | `announcements-storage.test.ts:37` | Module-level `Object.defineProperty(globalThis, 'localStorage')` — no teardown |

**Priority fixes:**
1. **P0**: Move litellm monkey-patch into session-scoped fixture with teardown
2. **P0**: Wrap `rm._active_runs`/`rm._cancel_events` mutations in `try/finally` + add autouse cleanup fixture
3. **P0**: Replace `importlib.reload()` with `monkeypatch.setattr()` on module constant
4. **P1**: Fix wrong `TEST_DATABASE_URL` imports (3 files)
5. **P1**: Replace `itertools.count(1)` with `uuid.uuid4()` in both conftests

---

### 3C — Maintainability (69/D)

**8 violations** (1 HIGH, 7 MEDIUM advisory)

| Severity | File | Lines | Action |
|----------|------|-------|--------|
| HIGH | `test_graceful_degradation.py` | 713L | Split into focused test files |
| MEDIUM | `test_prepare_for_indexing.py` | 460L | Consider splitting |
| MEDIUM | `test_auth_routes.py` | 451L | Consider splitting |
| MEDIUM | `test_parallel_execution.py` | 442L | Consider splitting |
| MEDIUM | `test_crypto_subagent_specs.py` | 432L | Consider splitting |
| MEDIUM | `test_rbac_api.py` | 422L | Consider splitting |
| MEDIUM | `test_stream_chainlens_tool_end_events.py` | 405L | Consider splitting |
| MEDIUM | `test_local_folder_page_limits.py` | 401L | Consider splitting |

**Note:** 27 additional files in 300-400L range — informational only. Python test files with comprehensive mock setup commonly reach this range. No action required unless file continues growing.

**Calibration rationale**: Initial raw scan flagged all 35 files >300L at LOW = 1 point each, producing score 58/F. After context-aware recalibration: 300-400L files are normal for this stack's mock-heavy test patterns. Only files >500L flagged HIGH (need splitting), 400-500L flagged MEDIUM (advisory — split when adding new tests).

---

### 3D — Performance (72/C)

**15 violations** (3 HIGH, 8 MEDIUM, 4 LOW)

#### HIGH Violations (3)

| # | File | Category | Impact |
|---|------|----------|--------|
| 1 | `integration/tools/conftest.py:10` | autouse hard wait | **500ms sleep after every tool test** — 10+ seconds dead wait per CI run |
| 2 | `unit/tasks/test_run_manager.py:30` | module reload | `importlib.reload()` conflicts with xdist worker isolation |
| 3 | `integration/conftest.py:52` | fixture scope | Function-scoped DB entity fixtures (`db_user`, `db_search_space`) — ORM insert overhead accumulates |

#### MEDIUM Violations (8)

| # | Category | Files | Fix |
|---|----------|-------|-----|
| 1-3 | Hard wait 50ms | `test_dropbox/google_drive/onedrive_parallel.py` | Reduce `asyncio.sleep(0.05)` → `0.005` — saves ~720ms total |
| 4 | Timing-dependent flush | `test_run_lifecycle.py:197` | Replace `sleep(0.2)` with `await writer.stop()` |
| 5 | Cancel propagation | `test_run_manager.py:120` | Replace `sleep(0.01)` with `asyncio.gather(task, return_exceptions=True)` |
| 6 | Vitest config | `vitest.config.ts` | Add explicit `pool: 'threads'` + `poolOptions` |
| 7 | Playwright CI workers | `playwright.config.ts:15` | `'50%'` becomes 1 worker on 2-core CI — fix to `Math.max(2, ...)` |
| 8 | Rate-limiter at import time | `agents/conftest.py:27` | Move to session-scoped fixture, replace `print()` with `logging.debug()` |

**Priority fixes:**
1. **P0**: Remove 500ms autouse sleep from `integration/tools/conftest.py`
2. **P1**: Add `--dist=loadfile` to pytest addopts for xdist safety
3. **P1**: Replace `importlib.reload()` with `monkeypatch.setattr()`
4. **P2**: Reduce `asyncio.sleep(0.05)` → `0.005` in 3 connector parallel test files

---

## Best Practices Found

### 1. Savepoint-Based DB Isolation
**Location**: `tests/integration/conftest.py:52-67`
**Pattern**: Session-scoped engine + function-scoped savepoint rollback

```python
@pytest_asyncio.fixture
async def db_session(async_engine):
    async with async_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn)
        yield session
        await transaction.rollback()  # auto-cleanup all DML
```

**Why this is good**: Every integration test gets a clean DB state without explicit cleanup. Rollback is faster than truncation and works with nested transactions.

### 2. Fake Timer Pattern (Frontend)
**Location**: `__tests__/hooks/use-typewriter.test.ts`
**Pattern**: `vi.useFakeTimers()` + `vi.advanceTimersByTime()`

Eliminates real-time waits in timer-dependent tests. Consistent pattern across FE unit tests.

### 3. One-Time Auth Headers for Destructive Tests
**Location**: `tests/api/conftest.py:72`
**Pattern**: Separate `one_time_auth_headers` fixture for token-revoking tests

Prevents destructive auth tests from invalidating session-scoped shared tokens. Good architectural boundary — though enforcement is convention-based, not structural.

### 4. Shielded Async Session
**Location**: `app/db.py:2333`
**Pattern**: `shielded_async_session()` — cancel-safe DB writes

Production util correctly reused in test infrastructure to prevent asyncio cancellation from rolling back critical DB operations.

---

## Critical Issues (Must Fix Before Merge)

### 1. Permanent Module-Level litellm Monkey-Patch

**Severity**: P0 (Critical)
**Location**: `tests/integration/agents/conftest.py:24`
**Dimension**: Isolation

At import time, this conftest permanently replaces `litellm.acompletion` and sets `litellm.num_retries = 0` with **zero restoration**. Any test in the session that imports litellm — directly or transitively — sees the patched version. Combined with `_rpm_lock_holder` and `_rpm_last_call` module-level mutable state, this creates a hidden global dependency that makes agent integration tests non-reproducible in isolation.

**Fix**: Move into a session-scoped autouse fixture with teardown:
```python
@pytest.fixture(scope="session", autouse=True)
def _patch_litellm():
    original = _litellm.acompletion
    original_retries = _litellm.num_retries
    _litellm.acompletion = _throttled_acompletion
    _litellm.num_retries = 0
    yield
    _litellm.acompletion = original
    _litellm.num_retries = original_retries
```

### 2. Global Dict Mutation Without Cleanup Guard

**Severity**: P0 (Critical)
**Location**: `tests/unit/tasks/test_run_manager.py:60`
**Dimension**: Isolation

Tests directly mutate production-level `rm._active_runs` and `rm._cancel_events` dicts. Cleanup via `.pop()` is in the test body — if any assertion fails before cleanup, state leaks to subsequent tests.

**Fix**: Add autouse fixture:
```python
@pytest.fixture(autouse=True)
def _clean_run_manager_state():
    yield
    rm._active_runs.clear()
    rm._cancel_events.clear()
```

### 3. 500ms Autouse Sleep on All Tool Integration Tests

**Severity**: P0 (Critical)
**Location**: `tests/integration/tools/conftest.py:10`
**Dimension**: Performance

```python
@pytest.fixture(autouse=True)
async def api_retry_delay():
    yield
    await asyncio.sleep(0.5)  # 500ms × every test = 10+ seconds wasted
```

**Fix**: Remove entirely. Apply rate-limit protection only to specific tests that hit real APIs, not as a blanket autouse fixture.

---

## Recommendations (Should Fix)

### 1. Replace `importlib.reload()` with `monkeypatch.setattr()`

**Severity**: P1 (High)
**Location**: `tests/unit/tasks/test_run_manager.py:27`
**Dimensions**: Isolation + Performance + Determinism (cross-cutting)

```python
# ❌ Bad (current)
importlib.reload(rm_module)

# ✅ Good (recommended)
with patch("app.tasks.chat.run_manager.RESUMABLE_RUNS_ENABLED", False):
    # test body
```

### 2. Fix UUID Collision Risk

**Severity**: P1 (High)
**Locations**: `tests/integration/retriever/conftest.py:23`, `tests/integration/google_unification/conftest.py:34`

Replace `_id_counter = itertools.count(1)` with `uuid.uuid4()` for genuine per-call isolation.

### 3. Fix Wrong Import Source (3 files)

**Severity**: P1 (High)
**Locations**: `test_stripe_checkout.py:16`, `test_stripe_reconciliation.py:17`, `test_stripe_webhook.py:16`

Change `from tests.conftest import TEST_DATABASE_URL` → `from tests.integration.conftest import TEST_DATABASE_URL`

### 4. Add `--dist=loadfile` to pytest addopts

**Severity**: P1 (High)
**Location**: `pyproject.toml:190`

Prevents xdist from scheduling tests from different files on the same DB tables concurrently.

### 5. Reduce Connector Test Sleep Durations

**Severity**: P2 (Medium)
**Locations**: `test_dropbox_download_parallel.py:172`, `test_google_drive_download_parallel.py:166`, `test_onedrive_parallel.py:170`

Reduce `asyncio.sleep(0.05)` → `asyncio.sleep(0.005)`. Semaphore test only needs non-zero overlap; saves ~720ms per full suite run.

### 6. Fix Playwright CI Workers

**Severity**: P2 (Medium)
**Location**: `playwright.config.ts:15`

`workers: '50%'` becomes 1 worker on 2-core runners, serializing all E2E tests. Fix:
```typescript
workers: process.env.CI ? Math.max(2, Math.floor(os.cpus().length * 0.75)) : undefined
```

### 7. Add Explicit Vitest Parallelism Config

**Severity**: P2 (Medium)
**Location**: `vitest.config.ts`

Add `pool: 'threads'` and `poolOptions: { threads: { maxThreads: 4 } }` for deterministic CI behavior.

---

## Quality Criteria Assessment

| Criterion | Status | Violations | Notes |
|-----------|--------|------------|-------|
| Hard Waits (sleep, waitForTimeout) | ⚠️ WARN | 9 | 2 BE asyncio.sleep + 500ms autouse + 3 connector sleeps |
| Determinism (no conditionals) | ⚠️ WARN | 9 | 3 MEDIUM hard waits + 6 LOW Date.now() informational |
| Isolation (cleanup, no shared state) | ❌ FAIL | 24 | 8 HIGH: module-level mutations, no teardown |
| Fixture Patterns | ⚠️ WARN | 5 | Session-scoped auth shared; function-scoped DB entities OK |
| Data Factories | ✅ PASS | 0 | Mock factories properly scoped |
| Explicit Assertions | ✅ PASS | 0 | Clear assertion patterns throughout |
| Test Length (≤300 lines) | ⚠️ WARN | 8 | 1 file >500L, 7 files 400-500L |
| Flakiness Patterns | ⚠️ WARN | 7 | Timing-dependent sleeps + LIMIT 1 anchor queries |
| Parallelization | ⚠️ WARN | 2 | xdist -n auto without --dist=loadfile; Playwright 50% workers |

---

## Next Steps

### Immediate Actions (P0 — Before Next CI Run)

1. **Fix litellm monkey-patch** — Move to session-scoped fixture with teardown
   - Effort: 30 min
   - Files: `tests/integration/agents/conftest.py`

2. **Remove 500ms autouse sleep** — Delete blanket sleep from tool integration conftest
   - Effort: 5 min
   - Files: `tests/integration/tools/conftest.py`

3. **Add cleanup guard for run_manager dicts** — Autouse fixture clearing `_active_runs`/`_cancel_events`
   - Effort: 15 min
   - Files: `tests/unit/tasks/test_run_manager.py`

### Follow-up Actions (P1 — Next Sprint)

1. **Replace `importlib.reload()` with `monkeypatch.setattr()`** — P1, 15 min
2. **Fix UUID collision risk** — Replace `itertools.count(1)` with `uuid.uuid4()` — P1, 10 min
3. **Fix wrong `TEST_DATABASE_URL` imports** — 3 Stripe test files — P1, 5 min
4. **Add `--dist=loadfile`** to pyproject.toml addopts — P1, 2 min

### Future Improvements (P2 — Backlog)

1. Reduce connector test sleep durations (3 files) — P2
2. Fix Playwright CI workers config — P2
3. Add explicit Vitest parallelism config — P2
4. Elevate ChainlensResearchService state-reset fixture to shared conftest — P2
5. Split `test_graceful_degradation.py` (713L) into focused test files — P2

### Re-Review Needed?

⚠️ Re-review after P0 fixes — 3 critical isolation/performance issues must be addressed before the test suite can be considered reliable for CI.

---

## Decision

**Recommendation**: Request Changes

**Rationale**:

Test quality needs improvement with 69/100 score (D). The suite has good structural foundations (savepoint DB isolation, xdist parallelization, comprehensive coverage breadth) but is undermined by 12 HIGH violations — primarily in the isolation dimension where module-level mutations without teardown create real flakiness risk. The 3 P0 critical issues (litellm monkey-patch, run_manager dict cleanup, 500ms autouse sleep) are straightforward to fix and would immediately improve CI reliability.

After fixing P0 issues, projected score improvement: Isolation ~75 (+12), Performance ~80 (+8) → weighted total ~74 (C). With P1 fixes, projected ~80 (B).

---

## Knowledge Base References

This review consulted the following knowledge fragments:

- **test-quality.md** — Definition of Done for tests (no hard waits, <300 lines, <1.5 min, self-cleaning)
- **data-factories.md** — Factory functions with overrides, API-first setup
- **test-levels-framework.md** — E2E vs API vs Component vs Unit appropriateness
- **test-healing-patterns.md** — Self-healing test patterns and retry strategies
- **selector-resilience.md** — Resilient selector patterns for E2E
- **timing-debugging.md** — Timing-dependent test debugging
- **playwright-cli.md** — Playwright CLI reference

For coverage mapping, consult `trace` workflow outputs.

---

## Review Metadata

**Generated By**: BMad TEA Agent (Test Architect)
**Workflow**: testarch-test-review v4.0
**Review ID**: test-review-suite-20260427
**Timestamp**: 2026-04-27
**Version**: 1.0

---

## Appendix: Violation Summary by Dimension

### Determinism (9 violations)

| File | Severity | Category | Fix |
|------|----------|----------|-----|
| `test_run_manager.py:101` | MEDIUM | hard-wait | Mock `asyncio.sleep` |
| `test_run_lifecycle.py:197` | MEDIUM | hard-wait | `await writer.stop()` |
| `utils.test.ts:49` | MEDIUM | time-dependency | `vi.useFakeTimers()` |
| `orchestra-lab.test.tsx` (×6) | LOW | time-dependency | Informational — Date.now() for props |

### Isolation (24 violations)

| File | Severity | Category | Fix |
|------|----------|----------|-----|
| `agents/conftest.py:24` | HIGH | global_state_mutation | Session fixture with teardown |
| `agents/conftest.py:195` | HIGH | global_state_mutation | `patch.object()` context manager |
| `api/conftest.py:48` | HIGH | session_scoped_shared_state | Document/guard client mutations |
| `api/conftest.py:58` | HIGH | session_scoped_shared_state | Structural guard for token revocation |
| `test_run_manager.py:60` | HIGH | global_state_mutation | `try/finally` + autouse cleanup |
| `test_run_manager.py:27` | HIGH | module_reload_side_effects | `monkeypatch.setattr()` |
| `retriever/conftest.py:23` | HIGH | global_state_mutation | `uuid.uuid4()` |
| `google_unification/conftest.py:34` | HIGH | global_state_mutation | `uuid.uuid4()` |
| *(11 MEDIUM + 5 LOW — see Step 3B above)* | | | |

### Maintainability (8 violations)

| File | Severity | Lines | Action |
|------|----------|-------|--------|
| `test_graceful_degradation.py` | HIGH | 713L | Split into focused files |
| *(7 MEDIUM advisory — files 400-500L)* | MEDIUM | 400-460L | Split when adding tests |

### Performance (15 violations)

| File | Severity | Category | Fix |
|------|----------|----------|-----|
| `tools/conftest.py:10` | HIGH | autouse sleep 500ms | Remove entirely |
| `test_run_manager.py:30` | HIGH | module reload | `monkeypatch.setattr()` |
| `conftest.py:52` | HIGH | fixture scope | Consider module-scoping entity fixtures |
| *(8 MEDIUM + 4 LOW — see Step 3D above)* | | | |
