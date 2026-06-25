# Story 11.8 — Redis-Coordinated Tool-Level Rate Limiter

**Epic:** 11 — Production Resilience & Performance
**Depends on:** Story 11.4 (Per-API Token Buckets — done)
**Status:** backlog
**Priority:** P2 — within 4 weeks
**Created:** 2026-05-06
**Source:** Code review of story 10.1.2 + IR report 2026-05-06 § QV-2

> **🔄 Split 2026-05-06:** Story originally bundled rate-limiter migration + circuit-breaker fail-open policy. Per IR § QV-2, split into focused stories: this 11.8 covers rate limiter only; circuit-breaker policy moved to story 11.9.

---

## Problem Statement

Story 11.4 implemented `RateLimiter` middleware (Redis Lua script, multi-worker safe) for global outbound API pacing. However, tools (`nansen_smart_money.py`, `crypto_smart_money_flow.py`) sử dụng class riêng `_ApiRateLimiter` (`app/agents/new_chat/tools/_rate_limiter.py`) — **per-process module singleton** với `asyncio.Lock`, không sync giữa workers.

**Impact in production:**
- 4 Celery workers + 2 FastAPI workers = 6 processes
- Nansen rate limit 100 req/min (Pro tier)
- Mỗi process dùng độc lập budget 100 → tổng outbound 600 req/min
- **Vi phạm Nansen budget by 6x** → cascading 429s, circuit breaker trips, customer-visible degradation

Story 11.4 không cover vì `_ApiRateLimiter` là tool-internal class, không phải `RateLimiter` middleware.

---

## Acceptance Criteria

**AC1 — Tool-level rate limiter migrate sang Redis-coordinated:**
GIVEN tool gọi external API (Nansen/Arkham/Dune)
WHEN xác định rate limit budget
THEN dùng global Redis-coordinated helper thay vì `_ApiRateLimiter` per-process

Migration path:
- `_ApiRateLimiter` deprecated → log warning khi instantiate
- New helper `acquire_global_rate_limit(api_name, max_calls, window_seconds)` reuses 11.4's Lua script
- Tool code updated:
  ```python
  # Before:
  await _arkham_rl.acquire()
  # After:
  await acquire_global_rate_limit("arkham", max_calls=1, window_seconds=1)
  ```

**AC2 — Multi-worker integration test verifies shared budget:**
```python
async def test_arkham_rate_limit_shared_across_workers():
    # 3 concurrent asyncio tasks with separate Redis clients
    # Each issues 5 acquire() calls
    # Total acquired in 1s window must be <= max_calls (1) — Lua atomicity guarantees
```

**AC3 — Backward-compat shim:**
`_ApiRateLimiter` class kept với `DeprecationWarning` for 1 release cycle. Both old and new path work concurrently. Removal scheduled in story 11.10 (future).

**AC4 — Observability:**
- Counter `rate_limiter_redis_unavailable_total{api_name}` increments khi Redis raises exception
- Histogram `rate_limiter_global_acquire_duration_ms{api_name}` tracks Lua script latency
- Alert: `rate_limiter_redis_unavailable_total > 100/min` → page ops

**AC5 — Local fallback when Redis unavailable:**
Reuse 11.4 pattern: fallback sang in-process counter (over-count acceptable per AC#5 of 11.4).

**AC6 — Feature flag for gradual rollout:**
Per-tool env flag `USE_GLOBAL_RATE_LIMITER_<API>=true|false` (default false). Operator có thể bật từng API riêng:
- Week 1: Arkham (lowest traffic)
- Week 2: Dune
- Week 3: Nansen

---

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/tools/_rate_limiter.py` | UPDATE | Add `DeprecationWarning` + new `acquire_global_rate_limit()` helper |
| `nowing_backend/app/middleware/rate_limiter.py` | UPDATE | Expose Lua-based `acquire_for(api_name, max_calls, window_seconds)` for tool layer |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Migrate `_arkham_rl`, `_dune_rl` (gated by `USE_GLOBAL_RATE_LIMITER_ARKHAM`, `_DUNE`) |
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Migrate `_nansen_rl` (gated by `USE_GLOBAL_RATE_LIMITER_NANSEN`) |
| `nowing_backend/app/observability/metrics.py` | UPDATE | Add new counters/histograms |
| `nowing_backend/.env.example` | UPDATE | Document feature flags |
| `nowing_backend/tests/integration/test_global_rate_limiter.py` | CREATE | Multi-task tests with separate Redis clients |

---

## Tasks/Subtasks

- [ ] Audit: `grep -r "_ApiRateLimiter\|_arkham_rl\|_dune_rl\|_nansen_rl" nowing_backend/`
- [ ] Implement `acquire_global_rate_limit()` reusing 11.4 Lua script
- [ ] Add `DeprecationWarning` to `_ApiRateLimiter.__init__`
- [ ] Migrate `crypto_smart_money_flow.py` (`_arkham_rl`, `_dune_rl`) — gated by env flags
- [ ] Migrate `nansen_smart_money.py` (`_nansen_rl`) — gated by env flag
- [ ] Add metrics + alerts
- [ ] Multi-worker integration test
- [ ] Doc update (`docs/operations/resilience.md` + `.env.example`)
- [ ] Manual chaos test: kill Redis → verify fallback + alerts fire
- [ ] Rollout per AC6 plan

---

## Risks

| Risk | Mitigation |
|---|---|
| Redis Lua script overhead per tool call (~5-10ms) | Pipeline scripts; benchmark before rollout |
| Migration touches all crypto tools → wide blast radius | Per-tool feature flag gradual rollout (AC6) |
| Local fallback counter inconsistent với Redis recovery | Document accepted divergence (matches 11.4 AC#5) |

---

## Test Plan

```python
@pytest.mark.asyncio
async def test_global_rate_limiter_lua_atomic_across_workers():
    """3 'workers' (separate asyncio tasks with separate Redis clients).
    Each tries 10 acquires in parallel. Only max_calls=1/window=1s allowed.
    Total acquires <= 1 per second across all workers (Lua atomicity).
    """
    ...
```

Manual chaos:
1. Set `USE_GLOBAL_RATE_LIMITER_ARKHAM=true`
2. Run 6 workers concurrent
3. Trigger 600 requests/min total
4. Verify Arkham received ≤ 60 requests/min (rate limit honored)
5. Kill Redis container → verify alerts fire + fallback engages
