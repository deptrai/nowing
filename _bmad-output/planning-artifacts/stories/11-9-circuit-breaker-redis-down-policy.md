# Story 11.9 — Circuit Breaker Redis-Down Policy + Observability

**Epic:** 11 — Production Resilience & Performance
**Depends on:** Story 11.2 (Redis Circuit Breaker — done)
**Status:** backlog
**Priority:** P2 — within 4 weeks
**Created:** 2026-05-06
**Source:** Code review of story 10.1.2 + IR report 2026-05-06 § QV-2

> **🔄 Split 2026-05-06:** Story originally bundled with 11.8 rate-limiter migration. Per IR § QV-2, split into focused stories: 11.8 covers rate limiter; this 11.9 covers circuit-breaker fail-open/fail-closed policy.

---

## Problem Statement

Hiện trạng ([crypto_smart_money_flow.py:36-41](nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py#L36-L41)):
```python
async def _safe_circuit_is_open(name: str) -> bool:
    try:
        return await circuit_breaker.is_open(name)
    except Exception as exc:
        logger.warning("circuit_breaker.is_open failed for %s: %s", name, exc)
        return False  # fail-open
```

**Implication when Redis goes down:**
- `is_open` raises exception → handler returns `False` → tool tiếp tục gọi external API
- Khi API thật sự đang fail (lý do circuit lẽ ra đã mở), thiếu Redis làm hệ thống mất bảo vệ → spam 5xx → quota exhausted → cost spike + customer impact
- Story 11.2 hardened HALF_OPEN probe race nhưng không address Redis-down behavior

**Tradeoff:**
- Fail-open: cost vs availability — spam external khi Redis down (current behavior)
- Fail-closed: lose all external during Redis down → graceful degradation impossible
- Degrade-to-local: per-process counter (best-effort)

Cần explicit operator-controllable policy + observability.

---

## Acceptance Criteria

**AC1 — Policy controlled by env var:**
GIVEN `_safe_circuit_is_open(name)` cannot reach Redis
WHEN policy = `fail-open` (default, current behavior): allow request, log WARNING
WHEN policy = `fail-closed`: deny request, return 503-equivalent error to caller
WHEN policy = `degrade-to-local`: use per-process fallback counter (best-effort, accepts inconsistency)

Env var: `CIRCUIT_BREAKER_REDIS_DOWN_POLICY=fail-open|fail-closed|degrade-to-local`

**AC2 — Per-API override:**
Operator có thể set policy per API: `CIRCUIT_BREAKER_REDIS_DOWN_POLICY_NANSEN=fail-closed`. Falls back to global if not set.

**AC3 — Observability metrics:**
- Counter `circuit_breaker_redis_unavailable_total{api_name, policy}` increments khi `_safe_circuit_*` catches exception
- Counter `circuit_breaker_redis_down_blocked_total{api_name}` (only `fail-closed` mode)
- Counter `circuit_breaker_redis_down_allowed_total{api_name}` (`fail-open` mode)
- Counter `circuit_breaker_redis_down_local_total{api_name}` (`degrade-to-local` mode)
- Histogram `circuit_breaker_check_duration_ms{api_name}` cho all check paths

Alert: `circuit_breaker_redis_unavailable_total > 100/min` → page ops (regardless of policy).

**AC4 — Local fallback counter (`degrade-to-local` mode):**
Per-process in-memory counter using `_safe_circuit_*` family. Accepts divergence with Redis (max ~6x error rate cho 6-worker deployment, acceptable cost vs bypass-everything).

**AC5 — Documentation:**
Update `docs/operations/resilience.md` with section "Circuit Breaker Redis-Down Behavior":
- Decision matrix (when to use each policy)
- Cost vs availability tradeoff
- Recommended baseline: `fail-open` for low-cost APIs (CoinGecko, DefiLlama), `degrade-to-local` for paid (Nansen, Arkham), `fail-closed` only for catastrophic-cost (LLM providers)

**AC6 — Test coverage:**
```python
@pytest.mark.parametrize("policy,expected_blocked", [
    ("fail-open", False),       # request allowed
    ("fail-closed", True),      # request blocked, returns 503-like
    ("degrade-to-local", None), # consults local counter (variable)
])
async def test_redis_down_policy_behavior(policy, expected_blocked, mock_redis_failure):
    ...
```

**AC7 — Backward-compat default:**
Default policy = `fail-open` (current behavior). No regression for existing deployments.

---

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py` | UPDATE | Read `CIRCUIT_BREAKER_REDIS_DOWN_POLICY` env, branch behavior; add `_local_counter` for degrade mode |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | `_safe_circuit_is_open` honor policy + emit metrics |
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Same change applied to Nansen circuit guard |
| `nowing_backend/app/observability/metrics.py` | UPDATE | Add counter families |
| `nowing_backend/.env.example` | UPDATE | Document policy options + per-API override |
| `docs/operations/resilience.md` | UPDATE | Add section "Circuit Breaker Redis-Down Behavior" |
| `nowing_backend/tests/unit/middleware/test_circuit_breaker_redis_down.py` | CREATE | Parametrized tests per policy |

---

## Tasks/Subtasks

- [ ] Add `CIRCUIT_BREAKER_REDIS_DOWN_POLICY` env reading (global + per-API override)
- [ ] Update `_safe_circuit_is_open` cả 2 tool files (crypto_smart_money_flow + nansen_smart_money)
- [ ] Implement `_local_counter` for `degrade-to-local` mode
- [ ] Add 4 new counter families + 1 histogram
- [ ] Documentation pass (`.env.example` + runbook)
- [ ] Parametrized test suite (3 policies × 4 scenarios = 12 cases)
- [ ] Manual chaos test: kill Redis under each policy → verify expected behavior

---

## Rollout Plan

1. **Week 1:** Ship with default `fail-open` (no behavior change). Deploy alerts + dashboards.
2. **Week 2:** Tune per-API:
   - Nansen, Arkham → `degrade-to-local` (cost protection)
   - CoinGecko, DefiLlama → keep `fail-open` (low-cost, prefer availability)
3. **Week 3-4:** Monitor `circuit_breaker_redis_unavailable_total` baseline; tune Redis HA if exceeds threshold.

---

## Risks

| Risk | Mitigation |
|---|---|
| `fail-closed` policy under sustained Redis flap → all external APIs blocked | Default stays `fail-open`; operator opts in to stricter policies after baseline |
| Local fallback inconsistent với Redis on recovery | Document accepted divergence trong runbook |
| Operator confusion across 3 policies | Decision matrix in runbook + sane defaults per API class |
