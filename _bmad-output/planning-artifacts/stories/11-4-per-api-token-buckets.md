# Story 11.4: Per-API Token Bucket Rate Limiters

Status: ready-for-dev

## Story

As a system operator,
I want mỗi external crypto API có rate limiter riêng phù hợp với quota của provider,
so that hệ thống không bị 429 từ CoinGecko (30/min) trong khi DeFiLlama (unlimited) bị throttle không cần thiết.

## Acceptance Criteria

1. **Given** CoinGecko free tier limit 30 req/min, **When** hệ thống gửi request thứ 31 trong 1 phút, **Then** request bị queue (chờ bucket refill) thay vì gửi rồi nhận 429.
2. **Given** DeFiLlama không có rate limit công bố, **When** hệ thống gọi DeFiLlama, **Then** rate limiter cho phép burst cao hơn (ví dụ 120/min).
3. **Given** token bucket cho provider X đang empty, **When** tool gọi API, **Then** tool nhận delay (max 5s wait) rồi retry — KHÔNG fail-fast.
4. **Given** multiple Uvicorn workers, **When** rate limit state checked, **Then** counters shared qua Redis (tương tự circuit breaker) để tổng request across workers không vượt limit.
5. **Given** Redis unavailable, **When** rate check, **Then** fallback sang local in-memory counter — over-count acceptable (prefer throttle hơn spam).
6. **Given** provider config, **When** kiểm tra, **Then** rate limits configurable qua environment variables hoặc constants dict.
7. **Given** tool bị throttled bởi token bucket, **When** log, **Then** structured log: `{"event": "rate_limited", "provider": "coingecko", "wait_ms": 2000}`.

## Tasks / Subtasks

- [ ] Task 1: Token bucket implementation (AC: #1, #2, #3, #4, #5)
  - [ ] 1.1 Tạo `TokenBucketRateLimiter` class trong `nowing_backend/app/agents/new_chat/middleware/rate_limiter.py` (NEW file)
  - [ ] 1.2 Redis-backed: key `rl:{provider}:tokens` (float) + `rl:{provider}:last_refill` (timestamp). Algorithm: refill `rate` tokens per second, max `capacity`.
  - [ ] 1.3 `async acquire(timeout_s=5.0) -> bool` — wait up to timeout_s for token, return False if exhausted
  - [ ] 1.4 In-memory fallback khi Redis unavailable (cùng pattern `get_redis_client()` trả None → local counter)
- [ ] Task 2: Provider rate config (AC: #6)
  - [ ] 2.1 Define `PROVIDER_RATE_LIMITS` dict:
    ```python
    PROVIDER_RATE_LIMITS = {
        "coingecko": {"capacity": 30, "refill_rate": 0.5},    # 30/min
        "cryptopanic": {"capacity": 60, "refill_rate": 1.0},  # 60/min
        "goplus": {"capacity": 33, "refill_rate": 0.55},      # 2000/day ≈ 33/30min
        "etherscan": {"capacity": 5, "refill_rate": 0.083},   # 5/sec
        "defillama": {"capacity": 120, "refill_rate": 2.0},   # generous
        "reddit": {"capacity": 60, "refill_rate": 1.0},       # 60/min
        "alternative_me": {"capacity": 30, "refill_rate": 0.5}, # conservative
    }
    ```
- [ ] Task 3: Integration vào `crypto_tool_decorator` (AC: #1, #3, #7)
  - [ ] 3.1 Trong `nowing_backend/app/agents/new_chat/tools/utils.py`, thêm `await rate_limiter.acquire(source)` VÀO ĐẦU `crypto_tool_decorator.wrapper()` — TRƯỚC circuit breaker check. Đây là single integration point cho tất cả crypto tools.
  - [ ] 3.2 Flow trong decorator: Token Bucket acquire → Circuit Breaker check → Semaphore acquire → Execute tool
- [ ] Task 4: Tests
  - [ ] 4.1 Unit test: 30 tokens consumed → acquire waits
  - [ ] 4.2 Unit test: refill after time passes → acquire succeeds
  - [ ] 4.3 Unit test: Redis fallback behavior
  - [ ] 4.4 Integration test: concurrent acquires across "workers" respect shared counter

## Dev Notes

### Architecture Compliance

- **Không có global outbound semaphore**: Codebase hiện tại dùng per-function `asyncio.Semaphore` (e.g., `Semaphore(4)` trong `web_search.py`), KHÔNG có global outbound pacing semaphore. Story này thêm per-provider rate limiting — independent layer.
- **Stateless tools**: Crypto tools có `requires=[]` (NFR-CS4). Rate limiter inject qua module-level singleton, KHÔNG qua dependency injection.
- **Redis access**: Dùng `get_redis_client()` từ `nowing_backend/app/services/crypto_cache_lock.py` — trả về `redis.asyncio` client hoặc None. Cùng pattern với circuit breaker.

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_backend/app/agents/new_chat/middleware/rate_limiter.py` | NEW | Token bucket class + provider config |
| `nowing_backend/app/agents/new_chat/tools/utils.py` | UPDATE | Add token bucket acquire into `crypto_tool_decorator` — single integration point |

### Anti-patterns to Avoid

- **KHÔNG** scatter rate_limiter.acquire() vào từng tool file — centralize trong `crypto_tool_decorator` (`utils.py`)
- **KHÔNG** remove existing `_OUTBOUND_SEMAPHORE(5)` — token bucket là per-provider rate control, semaphore là global concurrency cap
- **KHÔNG** raise exception on throttle — wait up to 5s, chỉ return error dict `{"error": "rate_limited"}` nếu timeout
- **KHÔNG** hardcode rates trong tool files — centralize trong `PROVIDER_RATE_LIMITS` dict
- **KHÔNG** tạo Redis connection riêng — dùng `get_redis_client()` từ `crypto_cache_lock.py`

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#4]
- [Source: _bmad-output/planning-artifacts/architecture.md#Cross-cutting Concerns — API rate awareness]
- [Source: nowing_backend/app/agents/new_chat/tools/ — 4 tool files]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
