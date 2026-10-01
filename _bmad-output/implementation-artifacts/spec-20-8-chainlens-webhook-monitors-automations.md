---
title: 'Story 20.8: ChainLens Webhook Monitors Automations'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: '15ecdeb948df51ad9649d681308c39d28a1ba51c'
deferred:
  - summary: >-
      Postgres enum automation_trigger_type needs an ALTER TYPE migration for chainlens_monitor.
    evidence: |-
      The Python StrEnum has CHAINLENS_MONITOR, but Postgres type automation_trigger_type
      requires an Alembic migration with ALTER TYPE ADD VALUE (outside transaction block)
      before real DB insert.
    location: >-
      nowing_backend/app/automations/persistence/enums/trigger_type.py
    severity: medium
  - summary: >-
      Frontend trigger configuration UI for ChainLens Monitor is not yet implemented.
    evidence: |-
      Backend webhook receiver and client are functional, but Nowing Web automation
      builder needs a form component for selecting monitor query and cron schedule.
    location: >-
      nowing_web/app/
    severity: low
---

<intent-contract>

## Intent

**Problem:** Người dùng Nowing muốn tự động hóa các hành động khi có tin tức thị trường mới hoặc cập nhật đối thủ (ví dụ: phát hiện đối thủ ra mắt sản phẩm mới -> tự động cào và tóm tắt). Hiện tại Automations chỉ hỗ trợ trigger định kỳ cục bộ (schedule) hoặc sự kiện nội bộ (event, memory_change), chưa thể kết nối với bộ máy giám sát định kỳ thông minh của ChainLens.

**Approach:** Tích hợp `TriggerType.CHAINLENS_MONITOR` vào hệ thống Automation của Nowing: (1) Mở rộng `TriggerType` enum hỗ trợ `chainlens_monitor`; (2) Client `ChainLensMonitorClient` quản lý vòng đời monitor trên ChainLens (`POST /v1/monitors`, `DELETE /v1/monitors/{id}`); (3) Webhook route `POST /api/v1/webhooks/chainlens/monitors` nhận kết quả tìm kiếm delta từ ChainLens, xác thực chữ ký HMAC-SHA256 bằng `CHAINLENS_AUTH_CONTEXT_SECRET` (hoặc secret key hệ thống) để chống giả mạo; (4) Khởi chạy `AutomationRun` tương ứng với payload chứa kết quả tìm kiếm mới.

## Boundaries & Constraints

**Always:**
- Enum `TriggerType` được bổ sung giá trị `CHAINLENS_MONITOR = "chainlens_monitor"`.
- Webhook endpoint bắt buộc phải xác thực tính toàn vẹn chữ ký HMAC-SHA256 qua header `X-ChainLens-Signature` hoặc query token bằng `hmac.compare_digest` trước khi xử lý payload.
- Mọi outbound request gửi tới ChainLens Monitors API phải đi kèm Service Auth Token hoặc HMAC context auth headers theo chuẩn của Story 20.4.
- Khi Automation bị xóa hoặc chuyển trạng thái `paused`, hệ thống phải gọi API của ChainLens để hủy hoặc tạm dừng monitor tương ứng nhằm tránh lãng phí chi phí.
- Fail-safe: Nếu ChainLens API tạm thời không phản hồi khi đăng ký monitor, lưu trạng thái lỗi rõ ràng trong `AutomationTrigger.last_error` mà không làm crash transaction của Automation.

**Never:**
- Không chấp nhận webhook payload không có chữ ký hợp lệ (trả về 401 Unauthorized ngay lập tức).
- Không nhân bản dữ liệu corpus tìm kiếm của ChainLens vào cơ sở dữ liệu Nowing (chỉ lưu delta payload trong run context).
- Không tạo polling daemon riêng trong Nowing — toàn bộ việc giám sát định kỳ do ChainLens chủ động ping qua Webhook.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Tạo Trigger Monitor | User tạo Automation với trigger `chainlens_monitor`, query "Đối thủ X", cron "@daily" | Gọi ChainLens `POST /v1/monitors`, nhận `monitorId`, lưu vào trigger params | Ghi lỗi nếu ChainLens 5xx |
| Webhook Delta hợp lệ | ChainLens ping webhook với HMAC đúng và mảng kết quả tìm kiếm mới | Xác thực thành công, tìm trigger theo `monitor_id`, enqueue `AutomationRun` | 200 OK trả về ChainLens |
| Webhook sai chữ ký | Kẻ tấn công gửi request giả mạo tới webhook endpoint | Xác thực thất bại, từ chối với 401 Unauthorized | Ghi log security warning |
| Xóa Automation | User xóa Automation có `chainlens_monitor` | Gọi ChainLens `DELETE /v1/monitors/{monitorId}`, xóa trigger trong DB | Không block xóa nếu ChainLens 404 |
| Monitor ID không khớp | Webhook gửi `monitor_id` không tồn tại trong hệ thống | Bỏ qua an toàn, trả về 200 OK hoặc 404 có ghi log | Không raise unhandled exception |

</intent-contract>

## Code Map

- `nowing_backend/app/automations/persistence/enums/trigger_type.py` -- **Sửa.** Thêm `CHAINLENS_MONITOR = "chainlens_monitor"` vào `TriggerType`.
- `nowing_backend/app/services/chainlens/monitors.py` -- **File mới.** Client `ChainLensMonitorClient`: tạo, xóa và cập nhật monitor trên ChainLens (`POST /v1/monitors`, `DELETE /v1/monitors/{id}`).
- `nowing_backend/app/routes/chainlens_webhooks.py` -- **File mới.** Router `POST /api/v1/webhooks/chainlens/monitors` xác thực HMAC-SHA256 và kích hoạt `AutomationRun`.
- `nowing_backend/app/routes/__init__.py` -- Đăng ký `chainlens_webhooks` router.
- `nowing_backend/tests/unit/automations/test_chainlens_monitors.py` -- **File mới.** Unit tests cho `TriggerType`, client quản lý monitor, webhook signature validation và dispatching run.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/automations/persistence/enums/trigger_type.py` -- Thêm `CHAINLENS_MONITOR` vào `TriggerType` -- Mở rộng miền giá trị trigger
- `nowing_backend/app/services/chainlens/monitors.py` -- Tạo `ChainLensMonitorClient` xử lý API gọi sang ChainLens -- Giao tiếp dịch vụ monitor
- `nowing_backend/app/routes/chainlens_webhooks.py` -- Tạo webhook route xử lý delta updates từ ChainLens -- Cổng nhận tin tức tự động
- `nowing_backend/app/routes/__init__.py` -- Đăng ký webhook router mới -- Kích hoạt endpoint
- `nowing_backend/tests/unit/automations/test_chainlens_monitors.py` -- Unit tests cho client, webhook HMAC, và dispatch flow -- Đảm bảo an toàn và tính chính xác

**Acceptance Criteria:**
- **Given** trigger kind `chainlens_monitor`, **When** `TriggerType("chainlens_monitor")` được khởi tạo, **Then** enum trả về `TriggerType.CHAINLENS_MONITOR`.
- **Given** webhook request từ ChainLens mang chữ ký HMAC hợp lệ và payload delta, **When** gửi tới `/api/v1/webhooks/chainlens/monitors`, **Then** endpoint trả về 200 OK và kích hoạt thực thi `AutomationRun`.
- **Given** webhook request mang chữ ký không hợp lệ hoặc thiếu chữ ký, **When** gửi tới endpoint, **Then** hệ thống trả về lỗi 401 Unauthorized.
- **Given** một Automation bị xóa, **When** trigger là `chainlens_monitor`, **Then** `ChainLensMonitorClient.delete_monitor()` được gọi với `monitor_id` tương ứng.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 3 findings — high 0, medium 2, low 1, false 0, maybe-false 0
- findings:
  - `medium` `patch` Webhook route query dùng `AutomationTrigger.trigger_type` (không tồn tại) thay vì `AutomationTrigger.type` — sửa thành `AutomationTrigger.type == TriggerType.CHAINLENS_MONITOR`; 12/12 tests pass
  - `medium` `defer` Postgres enum `automation_trigger_type` cần Alembic migration `ALTER TYPE ADD VALUE` ngoài transaction block trước khi deploy prod
  - `low` `defer` UI cấu hình trigger `chainlens_monitor` trong automation builder frontend chưa có (thuộc scope frontend)

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Tích hợp tính năng giám sát định kỳ thông minh từ ChainLens vào hệ sinh thái Automation của Nowing: `TriggerType.CHAINLENS_MONITOR` mở rộng miền giá trị trigger, `ChainLensMonitorClient` giao tiếp tạo/xóa monitor qua API của ChainLens, và webhook endpoint `POST /api/v1/webhooks/chainlens/monitors` xác thực chữ ký HMAC-SHA256 để khởi chạy `AutomationRun` khi có tin tức thị trường delta mới.

### Files changed

- `nowing_backend/app/automations/persistence/enums/trigger_type.py` — thêm `CHAINLENS_MONITOR = "chainlens_monitor"`
- `nowing_backend/app/services/chainlens/monitors.py` (mới, ~120 dòng) — `ChainLensMonitorClient`: `create_monitor`, `delete_monitor`, `verify_webhook_signature` (HMAC-SHA256 constant-time compare)
- `nowing_backend/app/routes/chainlens_webhooks.py` (mới, ~120 dòng) — webhook router tiếp nhận delta search findings, verify signature, tìm trigger và gọi `launch_run`
- `nowing_backend/app/routes/__init__.py` — đăng ký `chainlens_webhooks_router`
- `nowing_backend/tests/unit/automations/test_chainlens_monitors.py` (mới, 12 tests) — enum, HMAC verification, client CRUD, webhook dispatch

### Review findings breakdown

- **Patches applied (1):** sửa tên thuộc tính model `AutomationTrigger.type` thay vì `trigger_type`
- **Deferred (2):** Alembic migration cho Postgres enum `automation_trigger_type` (medium); Frontend form UI cho trigger builder (low)
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 12/12 unit tests pass 100%, webhook security gate đã được kiểm thử với chữ ký hợp lệ và không hợp lệ.

### Verification performed

- `uv run pytest tests/unit/automations/test_chainlens_monitors.py -v` → **12 passed**, 0 failed
- `uv run ruff check` (5 files) → **All checks passed!**
- `uv run python -c "from app.services.chainlens.monitors import ChainLensMonitorClient; print('import OK')"` → **import OK**
- Matrix Test Audit: 5/5 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- Postgres enum `automation_trigger_type` cần migration trước khi chạy trên DB thật (Alembic DDL)
- Frontend automation builder chưa có form UI cho trigger này

## Design Notes

**Cơ chế Xác thực Webhook HMAC-SHA256:**
ChainLens gửi chữ ký trong header `X-ChainLens-Signature` tính theo công thức:
`HMAC-SHA256(secret=CHAINLENS_AUTH_CONTEXT_SECRET, body=raw_request_bytes)`.
Nowing sử dụng `hmac.compare_digest(computed, received)` để so sánh theo thời gian không đổi, chống tấn công timing attack.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/automations/test_chainlens_monitors.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/automations/persistence/enums/trigger_type.py app/services/chainlens/monitors.py app/routes/chainlens_webhooks.py` -- expected: 0 errors
- `cd nowing_backend && uv run python -c "from app.services.chainlens.monitors import ChainLensMonitorClient; print('import OK')"` -- expected: no exception
