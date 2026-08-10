# Story 9.1a — Public-Repo Gate Evidence

**Story:** `9-1a-research-degradation-selfhost-independence`  
**Date:** 2026-08-10  
**Baseline commit:** `25ba542c2a3dec95b0a4020da8c129242ba748e2` on `develop`  

---

## 1. Commands run

### 1.1 Targeted unit tests

```bash
cd nowing_backend
uv run --active python -m pytest \
  tests/unit/capabilities/chainlens/research \
  tests/unit/capabilities/access/test_rest_router.py \
  tests/unit/capabilities/access/test_agent_tools.py \
  tests/unit/capabilities/test_billing.py \
  tests/unit/utils/test_crawl_classifier.py \
  -q
```

**Result:** `360 passed, 1 skipped, 10 warnings`  
The single skip is the ChainLens fixture-drift test, which requires `CHAINLENS_REPO_PATH`.

### 1.2 Integration fallback tests

Database: local PostgreSQL started via `docker compose -f docker/docker-compose.deps-only.yml up -d db`.  
Redis port 6379 was already in use; the DB container started successfully.

```bash
cd nowing_backend
uv run --active alembic upgrade head
uv run --active python -m pytest tests/integration/capabilities/chainlens/research/test_research_fallback.py -q
```

**Result:** `10 passed, 13 warnings`

### 1.3 Lint / format

```bash
cd nowing_backend
uv run --active ruff check app/capabilities/chainlens/research \
  app/capabilities/core/access/rest.py app/capabilities/core/access/agent.py \
  tests/unit/capabilities/chainlens/research \
  tests/unit/capabilities/access/test_rest_router.py \
  tests/unit/capabilities/access/test_agent_tools.py

uv run --active ruff format app/capabilities/chainlens/research \
  app/capabilities/core/access/rest.py app/capabilities/core/access/agent.py \
  tests/unit/capabilities/chainlens/research \
  tests/unit/capabilities/access/test_rest_router.py \
  tests/unit/capabilities/access/test_agent_tools.py
```

**Result:** `All checks passed!` (2 files reformatted by `ruff format`).

---

## 2. What the tests cover

| AC / requirement | Test file(s) |
|---|---|
| Self-host no key returns `engine_unavailable` | `test_executor.py`, `test_research_fallback.py` |
| Timeout / unreachable / 401/403/429/5xx degrade | `test_executor.py`, `test_degradation.py` |
| Explicit `partial` event parsing | `test_executor.py`, `test_review_fixes.py` |
| Explicit `insufficientEvidence` event parsing | `test_executor.py`, `test_degradation.py` |
| `heartbeat` and unknown events tolerated | `test_executor.py`, `test_review_fixes.py` |
| KB fallback bounded (`top_k <= 5`) and tenant-isolated | `test_research_fallback.py` |
| REST sync/async store same typed output | `test_rest_router.py`, `test_research_fallback.py` |
| Agent door returns degraded output without raising | `test_agent_tools.py` |
| `billable_units == 0` for `engine_unavailable` no-content | `test_billing.py`, `test_cost_metering.py` |
| Low-cardinality metrics, no secret leakage | `test_mutation_killers*.py`, `test_review_fixes.py` |

---

## 3. Fix applied during verification

`tests/unit/capabilities/access/test_rest_router.py::_build_app_with_rows` fake `_Session.execute()` only accepted `(self, stmt)`.  
`set_request_tenant_context()` calls `session.execute(text(...), {"workspace_id": ...})` to set RLS GUCs, so the mock failed with `takes 2 positional arguments but 3 were given`.

Changed the fake method signature to:

```python
async def execute(self, stmt, *args, **kwargs):
    return _Result()
```

This is a test-only change; production `AsyncSession.execute()` already supports parameter bindings.

---

## 4. Public-repo gate statement

- Gate 1 (self-host / no-key / degradation behavior) is satisfied by the test suite above.
- Gate 2 (legal attribution `AI-2026-07-25-7`) is outside the scope of this engineering story and remains tracked separately.

---

## 5. Outstanding / follow-up work

- `CHAINLENS_REPO_PATH` is not set locally, so the SSE fixture-drift test is skipped. It runs in CI when the ChainLens repo is mounted.
- Story 9.3 owns async agent door, progress-to-UI mapping, and mode-default `quality -> balanced` validation.
- Story 9.5 owns metered self-host access through Nowing Cloud API.
