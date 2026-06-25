# Story 11.2: Circuit Breaker Hardening (Structured Logging + HALF_OPEN Probe)

Status: done

## Story

As a system operator,
I want circuit breaker có explicit HALF_OPEN state với probe logic và structured logging cho mọi state transition,
so that tôi có thể monitor circuit breaker behavior qua logs/metrics và hệ thống recover chính xác hơn sau API outage.

## Acceptance Criteria

1. **Given** circuit OPEN cho source X và cooldown 30s đã qua, **When** request tiếp theo đến, **Then** state chuyển HALF_OPEN — chỉ cho phép **1 probe request**, các request khác vẫn fail-fast.
2. **Given** HALF_OPEN probe thành công, **When** `record_success()`, **Then** circuit CLOSE — tất cả requests resume.
3. **Given** HALF_OPEN probe thất bại, **When** `record_failure()`, **Then** circuit quay lại OPEN thêm 30s.
4. **Given** Redis unavailable, **When** tool gọi `is_open()`, **Then** return **last-known state** từ in-memory cache thay vì always False (closed).
5. **Given** circuit state thay đổi, **When** log, **Then** structured JSON: `{"event": "circuit_state_change", "source": "defillama", "from": "open", "to": "half_open"}`.
6. **Given** existing `is_open()`, `record_success()`, `record_failure()` API, **When** refactor, **Then** public interface KHÔNG đổi — chỉ internal behavior.

## Tasks / Subtasks

- [x] Task 1: HALF_OPEN probe logic (AC: #1, #2, #3)
  - [x] 1.1 Thêm Redis key `cb:state:{source}` (string: "closed"/"open"/"half_open")
  - [x] 1.2 Khi `open_until` expired, tự động chuyển state sang "half_open" và dùng `cb:probe_allowed` để kiểm soát probe
  - [x] 1.3 Trong `is_open()`: Dùng `DECR` trên `cb:probe_allowed` để chỉ cho phép chính xác 1 probe request
  - [x] 1.4 `record_failure()` trong half_open: Quay lại OPEN state và reset cooldown
- [x] Task 2: In-memory last-known state cache (AC: #4)
  - [x] 2.1 Thêm `_local_state_cache: dict[str, bool]` để mirror trạng thái circuit
  - [x] 2.2 Cập nhật cache mỗi khi Redis call thành công
  - [x] 2.3 Khi Redis exception, trả về giá trị từ cache (graceful degradation)
- [x] Task 3: Structured logging (AC: #5)
  - [x] 3.1 Log state transitions sử dụng `logger.info` với extra fields
  - [x] 3.2 Format structured: `{"event": "circuit_state_change", "source": "...", "from": "...", "to": "..."}`
- [x] Task 4: Tests (AC: all)
  - [x] 4.1 Unit test: OPEN expired -> HALF_OPEN (1 probe allowed)
  - [x] 4.2 Unit test: probe success/fail logic
  - [x] 4.3 Unit test: Redis downtime fallback
  - [x] 4.4 Unit test: Verify log emission và state transitions

## Dev Notes
- Logic `HALF_OPEN` được xử lý atomic thông qua Redis `DECR`.
- Cache in-memory giúp hệ thống không bị "ngập lụt" request khi Redis gặp sự cố nhưng vẫn giữ được rào chắn bảo vệ last-known.
- Structured logging tương thích với các công cụ log aggregation (ELK, Datadog).

## Dev Agent Record

### Agent Model Used
Gemini 2.0 Flash

### Debug Log References
- Triển khai `_update_state` private method để quản lý Redis state và Logging tập trung.
- Fix lỗi unit test mismatch do thay đổi thứ tự gọi Redis.

### Completion Notes List
- [2026-05-02] Hoàn thành Circuit Breaker hardening. Toàn bộ unit tests pass.

### File List
- `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py`
- `nowing_backend/tests/unit/middleware/test_circuit_breaker.py`
- `nowing_backend/tests/unit/middleware/test_circuit_breaker_hardened.py`

### Review Findings

- [x] [Review][Decision→Patch] Structured JSON logging — đã đổi sang `logger.info(json.dumps({...}))` trực tiếp (xem `_emit_state_change_log` trong `circuit_breaker.py`). Test `test_state_change_log_is_json` verify format.
- [x] [Review][Patch] HALF_OPEN probe race — dùng `set` thay vì `SETNX` cho `cb:probe_allowed` → multi-worker có thể slip nhiều probe (AC#1 vi phạm khi có nhiều worker) — `nowing_backend/app/agents/new_chat/middleware/circuit_breaker.py:96-105`
- [x] [Review][Patch] `record_failure` race với `record_success` — đọc `state` non-atomic, có thể spurious reopen ngay sau khi probe vừa close circuit — `circuit_breaker.py:120-140`
- [x] [Review][Patch] `cb:probe_allowed` không có TTL → key leak ở giá trị âm nếu `record_success`/`record_failure` không fire (request timeout không complete) — `circuit_breaker.py:97`
- [x] [Review][Patch] Test `test_cb_half_open_after_timeout` không thực sự exercise cooldown→half_open path: `mock_redis.get.return_value = str(past_time).encode()` làm state read trả past_time string thay vì "open", path fall qua final `return False` mà không kiểm tra logic — `nowing_backend/tests/unit/middleware/test_circuit_breaker.py:562-569`
