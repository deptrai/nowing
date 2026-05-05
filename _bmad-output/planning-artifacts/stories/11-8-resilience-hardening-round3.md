# Story 11.8 — Resilience & Performance Hardening Round 3

**Epic:** 11 — Production Resilience & Performance
**Depends on:** Story 11.2 (Redis Circuit Breaker — done), Story 11.4 (Per-API Token Buckets — done), Story 11.7 (Round 2 — done)
**Status:** backlog
**Priority:** P2 — within 4 weeks (after 10.1.x stories)
**Created:** 2026-05-06
**Source:** Code review of story 10.1.2 (2026-05-06) — surfaced 2 deferred resilience items không thuộc round 1/2

---

## Problem Statement

Round 1 (story 11-1 → 11-6) thiết lập production-ready resilience: SSE heartbeat, Redis circuit breaker, orphaned cache purge, per-API token buckets, client quota.

Round 2 (story 11-7) hardened follow-ups từ adversarial review.

Round 3 surface trong code review của 10.1.2 (smart money failover). Hai items chưa được cover:

### Item A: Tool-level `_ApiRateLimiter` không Redis-coordinated

**Hiện trạng:**
- Story 11.4 implement `RateLimiter` middleware (Redis Lua, multi-worker safe) — covers global outbound API pacing
- Trong khi đó, tools (`nansen_smart_money.py`, `crypto_smart_money_flow.py`) dùng class riêng `_ApiRateLimiter` ở `nowing_backend/app/agents/new_chat/tools/_rate_limiter.py` — **per-process module singleton** với `asyncio.Lock`, không sync giữa workers

**Implication:**
- Production có 4 Celery workers + 2 FastAPI workers = 6 processes
- Nansen rate limit 100 req/min (Pro tier)
- Mỗi process dùng độc lập budget 100 → tổng outbound 600 req/min → vi phạm Nansen budget
- Nếu Nansen 429, workers retry độc lập → cascading 429s

**Story 11.4 không cover** vì `_ApiRateLimiter` là tool-internal class, không phải `RateLimiter` middleware. Cần migrate hoặc bridge.

### Item B: Circuit breaker fail-open trên Redis exception

**Hiện trạng** ([crypto_smart_money_flow.py:36-41](nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py#L36-L41)):
```python
async def _safe_circuit_is_open(name: str) -> bool:
    try:
        return await circuit_breaker.is_open(name)
    except Exception as exc:
        logger.warning("circuit_breaker.is_open failed for %s: %s", name, exc)
        return False  # fail-open
```

**Implication:**
- Redis down → `is_open` raise exception → handler returns `False` → tool tiếp tục gọi external API
- Khi API thật sự đang fail (lý do circuit lẽ ra đã mở), thiếu Redis làm hệ thống mất bảo vệ → spam 5xx → quota exhausted → cost spike
- Story 11.2 hardened HALF_OPEN probe race nhưng không address Redis-down behavior

**Tradeoff:**
- Fail-open: cost vs availability — spam external khi Redis down
- Fail-closed: lose all external during Redis down → graceful degradation impossible

Cần explicit policy + observability.

---

## Acceptance Criteria

### AC1 — Tool-level rate limiter migrate sang Redis-coordinated

GIVEN tool gọi external API (Nansen/Arkham/Dune)
WHEN xác định rate limit budget
THEN dùng global `RateLimiter` middleware (Redis Lua, multi-worker safe) thay vì `_ApiRateLimiter` per-process

**Migration path:**
- `_ApiRateLimiter` deprecated → log warning khi instantiate
- New helper `acquire_global_rate_limit(api_name: str, max_calls: int, window: int)` uses Redis Lua script (same as 11.4)
- Tool code updated:
  ```python
  # Before:
  await _arkham_rl.acquire()
  # After:
  await acquire_global_rate_limit("arkham", max_calls=1, window=1)
  ```

### AC2 — Multi-worker test verify rate limit shared

```python
async def test_arkham_rate_limit_shared_across_workers():
    # Spawn 3 concurrent processes (or 3 asyncio tasks with separate Redis clients)
    # Each issues 5 acquire() calls
    # Total acquired in 1s window must be <= max_calls (1) — Lua atomicity guarantees
```

### AC3 — Fail-open vs fail-closed policy explicit

GIVEN circuit breaker `_safe_circuit_is_open(name)` cannot reach Redis
THEN behavior controlled by env var `CIRCUIT_BREAKER_REDIS_DOWN_POLICY`:
- `fail-open` (default, current behavior): allow request, log WARNING
- `fail-closed`: deny request, return 503-equivalent error
- `degrade-to-local`: use local fallback counter (best-effort, per-process)

### AC4 — Observability metrics

Counters:
- `circuit_breaker_redis_unavailable_total{api_name="..."}` — increments khi `_safe_circuit_*` catches exception
- `rate_limiter_redis_unavailable_total{api_name="..."}` — same cho rate limiter
- `rate_limiter_global_acquire_duration_ms{api_name="..."}` — histogram

Alerts:
- `circuit_breaker_redis_unavailable_total` > 100/min → page ops
- `rate_limiter_redis_unavailable_total` > 100/min → page ops

### AC5 — Documentation

Update `docs/operations/resilience.md`:
- Section "Redis-down behavior" — document chosen policy + cost/availability tradeoff
- Section "Rate limit hierarchy" — explain global RateLimiter (Redis) vs deprecated `_ApiRateLimiter`

### AC6 — Backward-compat shim

GIVEN existing tools dùng `_arkham_rl.acquire()`
WHEN migration complete
THEN `_ApiRateLimiter` class kept với `DeprecationWarning` for 1 release cycle
AND both old and new path work concurrently
AND scheduled removal trong story 11.9 (if needed)

---

## Files to Modify / Create

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/tools/_rate_limiter.py` | UPDATE | Add `DeprecationWarning` + `acquire_global_rate_limit` helper using Lua script |
| `nowing_backend/app/middleware/rate_limiter.py` | UPDATE | Expose Lua-based `acquire(api_name, max_calls, window)` for tool layer |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Migrate `_arkham_rl` and `_dune_rl` to global helper |
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Migrate `_nansen_rl` |
| `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py` | UPDATE | Read `CIRCUIT_BREAKER_REDIS_DOWN_POLICY` env, branch behavior |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | `_safe_circuit_is_open` honor policy |
| `nowing_backend/app/observability/metrics.py` | UPDATE | Add new counters/histograms |
| `nowing_backend/.env.example` | UPDATE | `CIRCUIT_BREAKER_REDIS_DOWN_POLICY=fail-open` documentation |
| `docs/operations/resilience.md` | UPDATE | Round 3 documentation |
| `nowing_backend/tests/integration/test_global_rate_limiter.py` | CREATE | Multi-process / multi-task tests |
| `nowing_backend/tests/unit/middleware/test_circuit_breaker_redis_down.py` | CREATE | Test all 3 policies |

---

## Tasks/Subtasks

- [ ] Audit: list all current `_ApiRateLimiter` usages (`grep -r "_ApiRateLimiter\|_arkham_rl\|_dune_rl\|_nansen_rl" nowing_backend/`)
- [ ] Implement `acquire_global_rate_limit(api_name, max_calls, window_seconds)` reusing 11.4's Lua script
- [ ] Add deprecation warning to `_ApiRateLimiter.__init__`
- [ ] Migrate `crypto_smart_money_flow.py`: `_arkham_rl`, `_dune_rl` → global helper
- [ ] Migrate `nansen_smart_money.py`: `_nansen_rl` → global helper
- [ ] Add `CIRCUIT_BREAKER_REDIS_DOWN_POLICY` env handling
- [ ] Update `_safe_circuit_is_open` cả 2 tool files
- [ ] Add metrics + alerts
- [ ] Documentation update
- [ ] Multi-worker integration test
- [ ] Manual chaos test: kill Redis → verify policy behavior + alerts fire
- [ ] Rollout plan: deploy với `policy=fail-open` (current behavior preserved) → tune to `degrade-to-local` post-monitor

---

## Risks

| Risk | Mitigation |
|---|---|
| Redis Lua script overhead per tool call (~5-10ms) → noticeable latency on hot path | Pipeline scripts; benchmark before rollout |
| Migration touches all crypto tools → wide blast radius | Feature flag `USE_GLOBAL_RATE_LIMITER=true` per-tool, gradual rollout |
| `fail-closed` policy under sustained Redis flap → all external APIs blocked | Default policy stays `fail-open`; ops opts into stricter policies after observing baseline |
| Local fallback counter (`degrade-to-local`) not consistent with Redis recovery | Document accepted divergence (matches 11.4 AC#5: "over-count acceptable") |

---

## Test Plan

```python
# test_global_rate_limiter.py
@pytest.mark.asyncio
async def test_global_rate_limiter_lua_atomic_across_workers():
    """Simulate 3 'workers' (separate asyncio tasks with separate Redis clients).
    Each tries 10 acquires in parallel. Only max_calls=1/window=1s allowed.
    Assert total acquires <= 1 per second across all workers.
    """
    ...


# test_circuit_breaker_redis_down.py
@pytest.mark.parametrize("policy,expected", [
    ("fail-open", False),       # is_open returns False → allow request
    ("fail-closed", True),      # is_open returns True → block request
    ("degrade-to-local", None), # consult local counter
])
async def test_redis_down_policies(policy, expected, mock_redis_failure):
    ...
```

---

## Rollout Plan

1. **Week 1:** Ship code với `USE_GLOBAL_RATE_LIMITER=false` per-tool (no behavior change). Add metrics + alerts.
2. **Week 2:** Enable `USE_GLOBAL_RATE_LIMITER=true` for `arkham` (lowest traffic). Monitor latency + 429 rate.
3. **Week 3:** Enable for `dune` and `nansen`. Compare quota usage cross-worker.
4. **Week 4:** Decide on `CIRCUIT_BREAKER_REDIS_DOWN_POLICY` based on observed Redis uptime + cost data.
5. **Story 11.9 (future):** Remove `_ApiRateLimiter` after 1 release cycle.
