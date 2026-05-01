# Story 11.2: Global Circuit Breaker (Redis-First)

Status: ready-for-dev

## Story

As a system operator,
I want circuit breaker state được shared qua Redis giữa tất cả Uvicorn workers,
so that khi 1 external API bị down, toàn bộ hệ thống fail-fast đồng nhất thay vì chỉ worker phát hiện đầu tiên.

## Acceptance Criteria

1. **Given** Uvicorn chạy 4 workers, **When** worker A detect DeFiLlama down (5 consecutive failures), **Then** workers B/C/D cũng fail-fast ngay lập tức cho DeFiLlama requests — không cần tự phát hiện lại.
2. **Given** circuit breaker OPEN cho source X, **When** `reset_timeout_s` (30s) trôi qua, **Then** state chuyển HALF_OPEN — cho phép 1 probe request.
3. **Given** probe request thành công trong HALF_OPEN, **When** success recorded, **Then** circuit CLOSE — tất cả workers resume gọi source X bình thường.
4. **Given** Redis unavailable, **When** tool gọi `is_open()`, **Then** fallback sang in-memory `_BREAKERS` dict — retain last-known state, KHÔNG crash.
5. **Given** Redis available lại, **When** next circuit state change, **Then** auto-sync lại vào Redis — in-memory fallback tự giải phóng.
6. **Given** circuit state trong Redis, **When** kiểm tra key format, **Then** key là `cb:{source}:state` và `cb:{source}:failures` với TTL = `reset_timeout_s + 10s`.
7. **Given** production logs, **When** circuit state thay đổi, **Then** log structured JSON: `{"event": "circuit_state_change", "source": "...", "from": "closed", "to": "open", "failure_count": 5}`.

## Tasks / Subtasks

- [ ] Task 1: Refactor `CircuitBreaker` class to Redis-backed (AC: #1, #2, #3, #6)
  - [ ] 1.1 Tạo `RedisCircuitBreaker` class trong `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py` (UPDATE existing file)
  - [ ] 1.2 Redis keys: `cb:{source}:state` (string: "closed"/"open"/"half_open"), `cb:{source}:failures` (int), `cb:{source}:opened_at` (float timestamp)
  - [ ] 1.3 TTL trên mỗi key = `reset_timeout_s + 10s` (auto-cleanup if source removed)
  - [ ] 1.4 Dùng existing Redis connection từ `app.config` (cùng Redis instance với Celery broker)
- [ ] Task 2: In-memory fallback (AC: #4, #5)
  - [ ] 2.1 Giữ lại `_BREAKERS` dict làm fallback store
  - [ ] 2.2 Wrap mọi Redis call trong try/except — on `redis.RedisError`, đọc/ghi từ `_BREAKERS`
  - [ ] 2.3 Khi Redis available lại, sync in-memory state vào Redis trên next `record_success()` hoặc `record_failure()`
- [ ] Task 3: Structured logging (AC: #7)
  - [ ] 3.1 Log state transitions: closed→open, open→half_open, half_open→closed
  - [ ] 3.2 Log format: JSON structured, include `source`, `from_state`, `to_state`, `failure_count`
- [ ] Task 4: Tests
  - [ ] 4.1 Unit test: 5 failures → state OPEN in Redis
  - [ ] 4.2 Unit test: OPEN + 30s → HALF_OPEN → probe success → CLOSED
  - [ ] 4.3 Unit test: Redis unavailable → fallback to in-memory → Redis back → sync
  - [ ] 4.4 Integration test: 2 concurrent "workers" (asyncio tasks) share breaker state qua Redis

## Dev Notes

### Architecture Compliance

- **Existing pattern**: `CircuitBreaker` class và `_BREAKERS` dict đã defined trong `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py`. REFACTOR in-place — không tạo file mới.
- **Redis instance**: Dùng `redis.asyncio.Redis` từ existing config — cùng Redis URL với Celery broker (`CELERY_BROKER_URL` env var). Import pattern: `from app.config import get_redis_client` hoặc tương tự.
- **Algorithm**: Giữ nguyên Hystrix-simplified logic (failure_threshold=5, reset_timeout_s=30) — chỉ thay storage layer.
- **Tool integration**: Tools gọi `_BREAKERS[source].is_open()` — interface KHÔNG ĐỔI. Internal implementation switch sang Redis.

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py` | UPDATE | Refactor `CircuitBreaker` → `RedisCircuitBreaker` + fallback |

### Anti-patterns to Avoid

- **KHÔNG** tạo Redis connection pool riêng — reuse existing Redis client
- **KHÔNG** dùng Redis WATCH/MULTI — simple GET/SET đủ (eventual consistency OK cho circuit breaker)
- **KHÔNG** đổi public API (`is_open()`, `record_success()`, `record_failure()`) — chỉ đổi internal storage
- **KHÔNG** lock Redis keys — race condition giữa workers là acceptable (worst case: 1 extra failed request)

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Circuit Breaker + Graceful Degradation]
- [Source: nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py — existing `CircuitBreaker` class]
- [Source: nowing_backend/app/celery_app.py — `CELERY_BROKER_URL` Redis config]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
