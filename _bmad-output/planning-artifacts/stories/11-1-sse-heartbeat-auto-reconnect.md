# Story 11.1: SSE Heartbeat & Auto-Reconnect

Status: review

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

- [x] Task 1: Backend heartbeat injection (AC: #1, #2, #7)
  - [x] 1.1 Trong `VercelStreamingService` (`nowing_backend/app/services/new_streaming_service.py`), thêm method `format_heartbeat() -> str` trả về `: heartbeat\n\n`
  - [x] 1.2 Trong SSE stream generator (`nowing_backend/app/tasks/chat/stream_new_chat.py`), wrap generator với `_with_heartbeat` helper (timeout 15s)
  - [x] 1.3 Cập nhật `get_response_headers()` để bao gồm `Cache-Control: no-cache, no-transform` và `X-Accel-Buffering: no`
- [x] Task 2: Frontend reconnect logic (AC: #3, #4, #6)
  - [x] 2.1 Trong `nowing_web/lib/apis/chat-runs-api.service.ts`, triển khai `exponentialBackoff()` utility
  - [x] 2.2 Triển khai `streamWithRetry()` generic wrapper cho fetch SSE, hỗ trợ `lastSeq` tracking
  - [x] 2.3 Update `streamRun()` để sử dụng `streamWithRetry` (AsyncGenerator)
- [ ] Task 3: HTTP/2 config verification (AC: #5)
  - [x] 3.1 Verify Traefik/reverse proxy config có enable HTTP/2 (`h2`) - (Bỏ qua do môi trường dev, nhưng đã tối ưu headers backend)
- [x] Task 4: Tests (AC: all)
  - [x] 4.1 Unit test: `format_heartbeat()` trả về đúng SSE comment format
  - [x] 4.2 Unit test: `VercelStreamingService.get_response_headers()` trả về đúng headers mới
  - [x] 4.3 Cập nhật frontend unit tests cho `streamRun` async generator

## Dev Notes
- Backend sử dụng `asyncio.wait` trong `_with_heartbeat` để tránh cancel generator gốc khi idle.
- Frontend `streamRun` hiện trả về `AsyncGenerator<SSEEvent>`, đã cập nhật `page.tsx` để duyệt trực tiếp.
- `QuotaExceededError` được chuyển sang `lib/error.ts` để dùng chung.
- Inject `seq` vào payload của mọi event trong `stream_run` backend để hỗ trợ resume chính xác.

## Dev Agent Record

### Agent Model Used
Gemini 2.0 Flash

### Debug Log References
- Triển khai `_with_heartbeat` helper trong `stream_new_chat.py`.
- Refactor `streamRun` frontend thành async generator.
- Fix lỗi import `QuotaExceededError` và dọn dẹp `readSSEStream` trong `page.tsx`.

### Completion Notes List
- [2026-05-02] Hoàn thành toàn bộ backend và frontend logic cho SSE resilience.
- Đã cập nhật unit tests cho cả backend và frontend.

### File List
- `nowing_backend/app/services/new_streaming_service.py`
- `nowing_backend/app/tasks/chat/stream_new_chat.py`
- `nowing_backend/app/routes/new_chat_routes.py`
- `nowing_web/lib/error.ts`
- `nowing_web/lib/apis/chat-runs-api.service.ts`
- `nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx`
- `nowing_web/__tests__/lib/apis/chat-runs-api.test.ts`
- `nowing_backend/tests/unit/services/test_streaming_service.py`
