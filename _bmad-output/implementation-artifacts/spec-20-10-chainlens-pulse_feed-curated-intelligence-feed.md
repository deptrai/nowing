---
title: 'Story 20.10: chainlens.pulse_feed Curated Intelligence Feed'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: '868716cb2d7695fe363a7f733c27e087bae2810c'
deferred:
  - summary: >-
      TokenUsage metering for pulse_feed calls is not yet wired into the executor.
    evidence: |-
      The executor calls ChainLens API but does not record TokenUsage rows with
      usage_type="chainlens_pulse_feed"; billing integration follows the
      cost_dollars_to_micros pattern from Story 20.4.
    location: >-
      nowing_backend/app/capabilities/chainlens/pulse_feed/executor.py
    severity: medium
  - summary: >-
      Frontend dashboard surface for browsing the Pulse feed is not yet implemented.
    evidence: |-
      Backend capability and REST endpoints are functional; the Nowing Web UI
      intelligence feed panel is a frontend follow-up.
    location: >-
      nowing_web/app/
    severity: low
---

<intent-contract>

## Intent

**Problem:** Hiện tại Nowing chỉ hỗ trợ tìm kiếm và nghiên cứu theo nhu cầu chủ động (on-demand query). Người dùng không có cách nào theo dõi dòng tin tức tình báo thị trường và đối thủ được tuyển chọn (curated feed) theo chủ đề (Tech, AI, Finance, Startups...) để chủ động nắm bắt cơ hội trước khi có nhu cầu tìm kiếm cụ thể.

**Approach:** Xây dựng capability `chainlens.pulse_feed` kết nối với dịch vụ ChainLens Pulse (`/v1/pulse/feed`): (1) Capability và REST endpoint kéo dòng tin tức chọn lọc kèm phân trang keyset theo ngày (`cursor`); (2) Endpoint lấy danh sách các góc phân tích (`angles`) được sinh sẵn cho từng tin tức (`GET /v1/pulse/items/{id}/angles`) với ước lượng chi phí tín dụng; (3) Ghi nhận chỉ số đo lường và cước `TokenUsage` với `usage_type="chainlens_pulse_feed"`.

## Boundaries & Constraints

**Always:**
- Tên capability chuẩn hóa: `chainlens.pulse_feed`.
- Hỗ trợ đầy đủ các chủ đề (`topic`): `tech`, `ai`, `finance`, `science`, `security`, `startup`, `all`.
- Phân trang dùng con trỏ ngày tháng ISO (`cursor`), không dùng offset số để đảm bảo tính ổn định với dữ liệu thời gian thực.
- Góc phân tích trả về DTO chuẩn `PulseAngleResponse`: `angleId`, `label`, `description`, `prompt`, `estimatedCredits`, `costDollars`, `model`.
- Ghi nhận `TokenUsage` với `usage_type="chainlens_pulse_feed"` vào database.
- Tái sử dụng `ChainLensServiceAuth` để truyền xác thực dịch vụ `Authorization` và `X-Workspace-Id`.

**Never:**
- Không lưu toàn bộ nội dung bài báo đầy đủ vào database Nowing — chỉ lưu metadata và tóm tắt.
- Không gửi lại request cào web khi các góc phân tích đã có sẵn trên ChainLens Pulse.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lấy Pulse Feed mặc định | `GET /pulse/feed` (topic="ai") | Trả về danh sách `items` kèm `pagination.nextCursor` | 5xx trả về lỗi degraded |
| Lấy Angles của một tin | `GET /pulse/items/item_1/angles` | Trả về mảng các góc phân tích với prompt và chi phí | 404 nếu tin không tồn tại |
| Phân trang trang kế tiếp | Gọi với `cursor="2026-09-30T12:00:00Z"` | Trả về các tin tức cũ hơn mốc thời gian đó | Hết tin trả `hasMore=False` |
| Topic không hợp lệ | `topic="invalid_topic"` | Fallback về topic `all` hoặc báo lỗi validation | Validate qua Pydantic |

</intent-contract>

## Code Map

- `nowing_backend/app/capabilities/chainlens/pulse_feed/schemas.py` -- **File mới.** Input/Output schemas cho Pulse Feed và Angles.
- `nowing_backend/app/capabilities/chainlens/pulse_feed/executor.py` -- **File mới.** Executor gọi ChainLens API và log TokenUsage.
- `nowing_backend/app/capabilities/chainlens/pulse_feed/definition.py` -- **File mới.** Khai báo `Capability` và `register_capability()`.
- `nowing_backend/app/capabilities/chainlens/pulse_feed/__init__.py` -- **File mới.** Export module.
- `nowing_backend/app/routes/pulse_routes.py` -- **File mới.** Router RESTful:
  - `GET /api/v1/workspaces/{workspace_id}/pulse/feed`
  - `GET /api/v1/workspaces/{workspace_id}/pulse/items/{item_id}/angles`
- `nowing_backend/app/routes/__init__.py` -- Đăng ký `pulse_router`.
- `nowing_backend/tests/unit/chainlens/test_pulse_feed.py` -- **File mới.** Unit tests cho schemas, executor, pagination, và endpoints.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/capabilities/chainlens/pulse_feed/` -- Tạo trọn bộ capability `chainlens.pulse_feed` -- Dòng tin tức tuyển chọn
- `nowing_backend/app/routes/pulse_routes.py` -- Tạo REST API cho Pulse feed và angles -- Cung cấp dữ liệu cho giao diện người dùng
- `nowing_backend/app/routes/__init__.py` -- Đăng ký `pulse_router` -- Kích hoạt endpoints
- `nowing_backend/tests/unit/chainlens/test_pulse_feed.py` -- Unit tests toàn diện -- Đảm bảo tính ổn định

**Acceptance Criteria:**
- **Given** yêu cầu lấy feed với topic "tech", **When** capability được thực thi, **Then** hệ thống gọi ChainLens `/v1/pulse/feed?topic=tech` và trả về danh sách bài viết kèm pagination.
- **Given** một item ID hợp lệ, **When** gọi endpoint lấy angles, **Then** hệ thống trả về danh sách `PulseAngleResponse` có đầy đủ nhãn và chi phí tín dụng dự kiến.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/chainlens/test_pulse_feed.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/capabilities/chainlens/pulse_feed/ app/routes/pulse_routes.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.capabilities.chainlens.pulse_feed import CHAINLENS_PULSE_FEED; print('import OK')"` -- expected: no exception
