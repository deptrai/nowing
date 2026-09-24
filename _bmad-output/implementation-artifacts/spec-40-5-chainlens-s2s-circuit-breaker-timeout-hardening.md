---
title: "ChainLens S2S Circuit Breaker & Timeout Hardening"
type: "feature"
created: "2026-09-24"
status: "done"
review_loop_iteration: 0
baseline_revision: "0efdbcd89dc09a32dae8d327ce45cc9e9afbea62"
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Các cuộc gọi Service-to-Service giữa Nowing và ChainLens có thể bị treo hoặc cascade failure nếu một bên quá tải hoặc mất kết nối.
**Approach:** Thiết lập deadline cứng 5.0s cho endpoint `POST /v1/private-data/search` trong `chainlens_internal.py` và xác thực bảo mật token trước khi vào query logic.

## Boundaries & Constraints

**Always:**
- Endpoint `POST /v1/private-data/search` phải fail-fast với HTTP 504 khi thời gian xử lý vượt quá 5.0 giây.
- Token S2S không hợp lệ hoặc sai workspace phải trả về HTTP 401/403 lập tức mà không truy cập DB.

</intent-contract>

## Auto Run Result

**Status**: done
**Completed Actions**:
- Bọc logic gọi `PrivateProviderService.search` với `asyncio.timeout(5.0)` trong `app/routes/chainlens_internal.py`.
- Bắt `TimeoutError` và trả HTTP 504 Gateway Timeout với thông điệp rõ ràng.
- Đã kiểm thử `tests/unit/routes/test_chainlens_s2s_hardening.py` đạt 2/2 passed tests.
