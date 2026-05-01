# Story 11.1: SSE Heartbeat & Auto-Reconnect

Status: ready-for-dev

## Story

As a user đang theo dõi Crypto Orchestra analysis,
I want SSE stream tự duy trì kết nối qua proxy/gateway và tự phục hồi khi bị đứt,
so that Orchestra status strip không bao giờ bị "frozen" giữa chừng.

## Acceptance Criteria

1. **Given** SSE stream đang active và không có data event nào trong 15s, **When** 15s trôi qua, **Then** backend gửi SSE comment `: heartbeat\n\n` để giữ connection alive qua proxy.
2. **Given** backend đang stream, **When** kiểm tra response headers, **Then** `Content-Type: text/event-stream` và `Cache-Control: no-cache` phải present.
3. **Given** frontend đang consume SSE stream qua `fetch()`, **When** stream bị đứt (network error, proxy timeout), **Then** client tự reconnect với exponential backoff (1s → 2s → 4s → max 30s).
4. **Given** reconnect thành công, **When** stream resume, **Then** client gửi `after_seq` parameter từ last received sequence number để không mất event.
5. **Given** user mở 3+ browser tabs, **When** tất cả tabs consume SSE, **Then** connections vẫn hoạt động nhờ HTTP/2 multiplexing (verify Traefik/reverse proxy config).
6. **Given** reconnect fail sau 5 lần liên tiếp, **When** max retries reached, **Then** UI hiển thị banner "Connection lost — click to retry" thay vì silent fail.
7. **Given** heartbeat interval, **When** kiểm tra production logs, **Then** heartbeat không tạo noise — chỉ là SSE comment (`:` prefix), không phải data event.

## Tasks / Subtasks

- [ ] Task 1: Backend heartbeat injection (AC: #1, #2, #7)
  - [ ] 1.1 Trong `NewStreamingService` (`nowing_backend/app/services/new_streaming_service.py`), thêm method `format_heartbeat() -> str` trả về `: heartbeat\n\n`
  - [ ] 1.2 Trong SSE stream generator (`nowing_backend/app/routes/new_chat_routes.py` hoặc caller), wrap `event_stream()` với `asyncio.wait_for` timeout 15s — khi timeout yield heartbeat
  - [ ] 1.3 Đảm bảo response headers `Cache-Control: no-cache, no-transform` và `X-Accel-Buffering: no` (nginx proxy buffering bypass)
- [ ] Task 2: Frontend reconnect logic (AC: #3, #4, #6)
  - [ ] 2.1 Trong `nowing_web/lib/apis/chat-runs-api.service.ts`, wrap `streamRun()` với reconnect wrapper
  - [ ] 2.2 Implement exponential backoff: delays = [1000, 2000, 4000, 8000, 16000, 30000] ms, max 5 retries
  - [ ] 2.3 Track `lastSeq` từ parsed SSE events, pass vào `after_seq` query param on reconnect
  - [ ] 2.4 Trên max retry failure, dispatch error event cho UI hiển thị banner
- [ ] Task 3: HTTP/2 config verification (AC: #5)
  - [ ] 3.1 Verify Traefik/reverse proxy config có enable HTTP/2 (`h2`)
  - [ ] 3.2 Nếu dùng docker-compose dev, verify `docker/docker-compose.dev.yml` Traefik labels/config
  - [ ] 3.3 Test: `curl --http2 -I https://<domain>` → verify `HTTP/2 200`
- [ ] Task 4: Tests (AC: all)
  - [ ] 4.1 Unit test: `format_heartbeat()` trả về đúng SSE comment format
  - [ ] 4.2 Unit test: stream generator yields heartbeat sau 15s idle
  - [ ] 4.3 FE test: reconnect logic với mock fetch failures → verify backoff timing
  - [ ] 4.4 FE test: `after_seq` đúng giá trị sau reconnect

## Dev Notes

### Architecture Compliance

- **SSE format**: Existing `_format_sse()` trong `NewStreamingService` dùng `data: {json}\n\n`. Heartbeat PHẢI dùng SSE comment format `: heartbeat\n\n` (với colon prefix) — đây là spec SSE, client tự ignore.
- **Stream consumer**: Frontend dùng `fetch()` + `ReadableStream` parsing (KHÔNG phải browser `EventSource`). Reconnect logic phải nằm trong wrapper quanh `streamRun()` function.
- **`after_seq` parameter**: API `GET /api/v1/threads/{id}/runs/{id}/stream?after_seq={n}` đã support — đây là resume mechanism sẵn có.

### Existing Code to Modify

| File | Action | Notes |
|------|--------|-------|
| `nowing_backend/app/services/new_streaming_service.py` | UPDATE | Thêm `format_heartbeat()` method |
| `nowing_backend/app/tasks/chat/stream_new_chat.py` | UPDATE | Wrap stream generator với heartbeat timer |
| `nowing_web/lib/apis/chat-runs-api.service.ts` | UPDATE | Wrap `streamRun()` với reconnect logic |
| `docker/docker-compose.dev.yml` hoặc Traefik config | VERIFY | HTTP/2 support |

### Anti-patterns to Avoid

- **KHÔNG** tạo heartbeat endpoint riêng — inject trực tiếp vào existing SSE stream
- **KHÔNG** dùng `setInterval` cho heartbeat — dùng `asyncio.wait_for` timeout trên stream generator
- **KHÔNG** parse heartbeat comment ở frontend — SSE spec tự ignore `:` prefix lines
- **KHÔNG** reconnect nếu user chủ động cancel (check `AbortSignal`)

### Project Structure Notes

- Backend SSE: `nowing_backend/app/services/new_streaming_service.py` (class `NewStreamingService`)
- Stream route: `nowing_backend/app/routes/new_chat_routes.py` (SSE endpoint)
- Stream task: `nowing_backend/app/tasks/chat/stream_new_chat.py` (async stream generator)
- FE stream consumer: `nowing_web/lib/apis/chat-runs-api.service.ts` (`streamRun()`)

### References

- [Source: _bmad-output/architecture-improvement-proposals-2026-05-01.md#1]
- [Source: _bmad-output/planning-artifacts/architecture.md#API & Communication Patterns]
- [Source: nowing_backend/app/services/new_streaming_service.py — `_format_sse()`, orchestra events]
- [Source: nowing_web/lib/apis/chat-runs-api.service.ts — `streamRun()` function]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
