# Test Quality Review — Story 9-6c

## Review Scope

- `nowing_backend/tests/integration/memory/test_memory_provenance_e2e_gate.py`
- `nowing_backend/tests/unit/services/test_revalidation_unit.py`
- `nowing_backend/tests/unit/services/test_revalidation_service.py`

## Executive Summary

**Quality Score: 94/100 (A+)**

**Recommendation: Approve**

The 9-6c test suite provides a strong E2E gate over the memory provenance and revalidation flow. Integration tests exercise the real Postgres backend, real HTTP route, and real embedding pipeline; unit tests cover the pure extraction/normalization helpers and the service-level error branches. The main weaknesses are the absence of test IDs/priority markers and one integration file that exceeds the 300-line ideal threshold.

## Strengths

- E2E integration test proves the full `Run` → memory → delete `Run` → revalidate recipe flow against real Postgres.
- Unit tests for `_extract_text` and `_normalize` reach 100% mutation score on the scoped pure helpers.
- Service-level unit tests cover not-revalidatable, invalid recipe, gate failure, charge failure, match, and mismatch paths.
- Tests reuse existing project fixtures (`db_session`, `client`, `db_workspace`) and transactional rollback for isolation.
- No hard waits, no environment-dependent race conditions, no random data.

## Weaknesses

- No test IDs or P0/P1/P2 priority markers (P2).
- `test_memory_provenance_e2e_gate.py` is 355 lines, slightly above the 300-line ideal (P2).
- Some integration fixture code (e.g., `_FakeCapability`, `_llm_returning_facts`) is local to the file and could be extracted to a shared `conftest.py` if the feature area grows (P2).

## Detailed Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| BDD Format | PASS | Each test has a clear docstring tied to an AC or behavior. |
| Test IDs | WARN (P2) | No formal test IDs present. |
| Priority Markers | WARN (P2) | No P0/P1/P2 markers on tests. |
| Hard Waits | PASS | No `sleep` or hardcoded delays. |
| Determinism | PASS | No `Math.random`, `Date.now`, or branching on runtime values. |
| Isolation | PASS | `db_session` transactional rollback; unit tests use fresh mocks. |
| Fixture Patterns | PASS | Reuses `tests/integration/memory/conftest.py` fixtures; local helpers are well-scoped. |
| Data Factories | PASS | Dummy data is simple and stable; no need for factories for this scope. |
| Network-First | N/A | Integration tests use `httpx.AsyncClient` against in-process ASGI, no route-after-navigate race. |
| Assertions | PASS | Explicit assertions on status code, DB state, response body, and return objects. |
| Test Length | WARN (P2) | `test_memory_provenance_e2e_gate.py` = 355 lines. |
| Test Duration | PASS | Full combined suite runs in ~7s with Redis. |
| Flakiness | PASS | No tight timeouts, no retry logic, no environment assumptions. |

## P0/P1/P2/P3 Breakdown

- **P0**: 0
- **P1**: 0
- **P2**: 3 (missing IDs, missing priority markers, file > 300 lines)
- **P3**: 0

## Calculation

Starting score: 100
P2 deductions: 3 × -2 = -6
Final score: 94

## Next Steps

- Proceed to `bmad-testarch-trace` and `bmad-testarch-nfr`.
- Human review gate (4.13) remains required because the diff touches the memory billing/cost path.
