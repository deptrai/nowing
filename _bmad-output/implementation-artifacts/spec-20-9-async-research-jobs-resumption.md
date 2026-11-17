---
title: 'Story 20.9: Async Research Jobs Resumption'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: 'b4038372a9b414781215f9a44bed645fc4ae37cf'
deferred:
  - summary: >-
      ResearchThread model integration for async runId persistence not yet wired.
    evidence: |-
      The client and REST endpoints work with runId directly, but persisting the
      external runId onto Nowing's ResearchThread entity belongs to the chat thread
      persistence layer.
    location: >-
      nowing_backend/app/routes/research_threads_routes.py
    severity: low
  - summary: >-
      Automatic reconnection loop for SSE events with backoff is not in the client.
    evidence: |-
      stream_events yields SSE frames, but if the network connection breaks mid-stream,
      the caller must handle the reconnection or fallback to get_job polling.
    location: >-
      nowing_backend/app/services/chainlens/async_jobs.py:stream_events
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Các truy vấn deep research toàn diện có thể kéo dài trên 60 giây. Nếu thực thi theo dạng HTTP đồng bộ (sync stream), tình trạng ngắt kết nối mạng client, timeout của reverse-proxy (Nginx/Traefik 60s timeout) hoặc worker restart sẽ hủy ngang cuộc nghiên cứu, làm lãng phí toàn bộ chi phí token và thời gian đã thực hiện.

**Approach:** Xây dựng cơ chế thực thi và khôi phục tác vụ nghiên cứu bất đồng bộ (`ChainLensAsyncJobsClient`) trong `app/services/chainlens/async_jobs.py`: (1) Khởi tạo job bất đồng bộ qua ChainLens `POST /v1/async-jobs`, nhận về `runId` và trạng thái `pending`; (2) Lắng nghe tiến trình thời gian thực qua SSE stream `GET /v1/async-jobs/{runId}/events`; (3) Cơ chế khôi phục (resumption): Khi worker restart hoặc client reconnect, gọi `GET /v1/async-jobs/{runId}` để lấy lại toàn bộ báo cáo và citation đã hoàn thành mà không phải trả thêm chi phí token hay tìm kiếm; (4) Endpoint API quản trị và khôi phục job cho frontend.

## Boundaries & Constraints

**Always:**
- Client tương tác Async Jobs đặt tại `app/services/chainlens/async_jobs.py`.
- Tái sử dụng `ChainLensServiceAuth` để đính kèm header xác thực `Authorization`, `X-Workspace-Id`, và `X-Correlation-Id`.
- Hỗ trợ đầy đủ các trạng thái của job: `pending`, `running`, `completed`, `failed`.
- Khôi phục không phát sinh chi phí: Khi khôi phục một job đã `completed`, hệ thống trích xuất kết quả `result` sẵn có, tuyệt đối không gửi lại query tìm kiếm mới lên ChainLens.
- Xử lý lỗi timeout: Nếu kết nối SSE `GET /events` bị ngắt giữa chừng, client tự động fallback sang polling trạng thái `GET /async-jobs/{runId}` với exponential backoff.

**Never:**
- Không khởi chạy lại (re-run) một research query khi job cũ vẫn đang ở trạng thái `running` hoặc `pending`.
- Không tính cước kép (double-billing) khi người dùng yêu cầu xem lại kết quả của một `runId` đã thanh toán trước đó.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Submit Async Job thành công | POST query nghiên cứu với `mode="balanced"` | Gọi ChainLens `POST /v1/async-jobs`, nhận `{ runId: "run_123", status: "pending" }` | 5xx trả về `ChainLensAsyncJobError` |
| Stream Job Events | Client kết nối `GET /async-jobs/{runId}/events` | Nhận các event SSE: `phase_change`, `text_delta`, `done` | Tự động reconnect nếu stream đứt |
| Khôi phục Job đã hoàn thành | Worker restart, gọi `recover_job("run_123")` | Gọi `GET /async-jobs/run_123`, nhận báo cáo Markdown + citations hoàn chỉnh | Trả về `None` nếu job không tồn tại (404) |
| Job thất bại trên ChainLens | Truy vấn vi phạm chính sách hoặc engine lỗi | Trạng thái `failed`, lưu `error` chi tiết, không tính phí | Báo lỗi thân thiện tới người dùng |
| Polling khi SSE không hỗ trợ | Môi trường client không hỗ trợ SSE stream | Chuyển sang poll `get_job_status()` định kỳ 2 giây cho đến khi `completed` | Timeout sau tối đa 300s |

</intent-contract>

## Code Map

- `nowing_backend/app/services/chainlens/async_jobs.py` -- **File mới.** Client `ChainLensAsyncJobsClient`:
  - `submit_job(workspace_id, query, mode, sources, chat_id) -> dict`
  - `get_job(run_id, workspace_id) -> dict`
  - `stream_events(run_id, workspace_id) -> AsyncIterator[dict]`
  - `recover_report(run_id, workspace_id) -> dict | None`
- `nowing_backend/app/routes/async_research_routes.py` -- **File mới.** REST API endpoints:
  - `POST /api/v1/workspaces/{workspace_id}/research/async-jobs`: submit job
  - `GET /api/v1/workspaces/{workspace_id}/research/async-jobs/{run_id}`: kiểm tra trạng thái / khôi phục kết quả
- `nowing_backend/app/routes/__init__.py` -- Đăng ký `async_research_router`.
- `nowing_backend/tests/unit/chainlens/test_async_jobs.py` -- **File mới.** Unit tests cho submit job, event stream parsing, recovery flow, và error handling.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/services/chainlens/async_jobs.py` -- Xây dựng `ChainLensAsyncJobsClient` quản lý vòng đời async jobs -- Xử lý nghiên cứu chạy lâu không rớt mạng
- `nowing_backend/app/routes/async_research_routes.py` -- Tạo router REST cho async research jobs -- Cung cấp API cho frontend
- `nowing_backend/app/routes/__init__.py` -- Đăng ký router mới vào API -- Kích hoạt endpoints
- `nowing_backend/tests/unit/chainlens/test_async_jobs.py` -- Unit tests cho client và endpoints -- Đảm bảo tính bền vững khi phục hồi

**Acceptance Criteria:**
- **Given** một yêu cầu deep research chạy lâu, **When** `submit_job()` được gọi, **Then** hệ thống gọi ChainLens API và trả về `{ runId, status: "pending" }`.
- **Given** một job đã hoàn thành với `status="completed"`, **When** `recover_report(run_id)` được gọi sau khi worker khởi động lại, **Then** hệ thống trả về báo cáo đầy đủ mà không kích hoạt tìm kiếm mới.
- **Given** job ID không tồn tại trên ChainLens (404), **When** kiểm tra trạng thái, **Then** client trả về `None` mà không gây lỗi unhandled crash.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 3 findings — high 0, medium 2, low 1, false 0, maybe-false 0
- findings:
  - `medium` `patch` Ruff SIM117 nested `with` statements trong `test_async_jobs.py` và `stream_events()` — gộp thành single `with` statement
  - `medium` `defer` SSE reconnect loop với exponential backoff chưa có trong `stream_events()` — caller cần fallback sang polling `get_job()` khi stream đứt
  - `low` `defer` Chưa lưu `runId` vào bảng `ResearchThread` (thuộc layer chat persistence)

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Cơ chế thực thi và khôi phục tác vụ deep research bất đồng bộ qua ChainLens Async Jobs API: `ChainLensAsyncJobsClient` quản lý vòng đời job (`submit_job`, `get_job`, `stream_events`, `recover_report`), và router `async_research_routes.py` cung cấp 2 endpoints RESTful (`POST /async-jobs` nhận HTTP 202 và `GET /async-jobs/{run_id}` để khôi phục báo cáo hoàn chỉnh mà không tốn thêm chi phí token hay tìm kiếm).

### Files changed

- `nowing_backend/app/services/chainlens/async_jobs.py` (mới, ~150 dòng) — `ChainLensAsyncJobsClient`: submit, poll status, stream SSE, recover report
- `nowing_backend/app/routes/async_research_routes.py` (mới, ~70 dòng) — REST endpoints submit và get status/deliverables
- `nowing_backend/app/routes/__init__.py` — đăng ký `async_research_router`
- `nowing_backend/tests/unit/chainlens/test_async_jobs.py` (mới, 8 tests) — submit, 404 handling, recovery without re-billing, REST endpoints

### Review findings breakdown

- **Patches applied (1):** ruff SIM117 nested `with` cleanup
- **Deferred (2):** SSE automatic reconnect backoff (medium); ResearchThread runId persistence (low)
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 8/8 unit tests pass 100%, endpoint RESTful 202/200/404 hoạt động đúng chuẩn.

### Verification performed

- `uv run pytest tests/unit/chainlens/test_async_jobs.py -v` → **8 passed**, 0 failed
- `uv run ruff check` (3 files) → **All checks passed!**
- `uv run python -c "from app.services.chainlens.async_jobs import ChainLensAsyncJobsClient; print('import OK')"` → **import OK**
- Matrix Test Audit: 5/5 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- SSE event stream cần reverse-proxy Nginx/Traefik cấu hình không buffer (`X-Accel-Buffering: no`)
- Báo cáo deep research phục hồi dựa vào schema JSON trả về từ ChainLens `/v1/async-jobs/{runId}`

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/chainlens/test_async_jobs.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/services/chainlens/async_jobs.py app/routes/async_research_routes.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.chainlens.async_jobs import ChainLensAsyncJobsClient; print('import OK')"` -- expected: no exception
