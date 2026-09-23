---
title: NowingError & Exception Narrowing — Batch 1 (Financial, Credits, Billing & Verification Services)
type: refactor
created: '2026-09-13'
status: done
baseline_commit: b9eac404289ea0c46b5dcfebf06dbf66a87754eb
review_loop_iteration: 0
context:
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/services/corporate_verification_service.py
  - nowing_backend/app/services/phone_waterfall_service.py
  - nowing_backend/app/services/billable_calls.py
  - nowing_backend/app/services/token_tracking_service.py
  - nowing_backend/app/services/contact_unlock_service.py
  - nowing_backend/app/services/etl_credit_service.py
  - nowing_backend/app/services/pricing_registration.py
  - nowing_backend/app/services/token_quota_service.py
  - nowing_backend/app/services/auto_reload_service.py
  - nowing_backend/app/services/outcome_pricing_service.py
  - nowing_backend/app/services/partner_service.py
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Có 385 vị trí `except Exception` rải rác trong `app/services/`. Nhiều khối nuốt lỗi âm thầm, không ghi log đủ ngữ cảnh, hoặc che giấu các lỗi nghiêm trọng (programming errors, financial debit failures).

**Approach:** Refactor Batch 1 gồm ~47 call-sites `except Exception` trên 11 core financial, credits, billing và corporate verification services:
1. Narrow sang typed exceptions (ví dụ: `httpx.HTTPError`, `SQLAlchemyError`, `ValueError`, `KeyError`, `redis.RedisError`).
2. Map sang `NowingError` subclasses (`ExternalServiceError`, `DatabaseError`, `ValidationError`, `RateLimitError`) khi re-raise.
3. Nếu phải giữ `except Exception` (bảo đảm an toàn cho các tác vụ phụ / best-effort cleanup), bắt buộc ghi rõ comment giải thích: `# <lý do: best-effort vs re-raise on critical path>`.

## Boundaries & Constraints

**Always:**
- Giữ nguyên logic nghiệp vụ và contract của từng hàm.
- Với non-critical hooks (cache, metrics, auto-reload trigger): log warning/debug và không làm gián đoạn flow chính.
- Với critical path (trừ tiền ví, giao dịch credit, ghi audit log): re-raise typed exception để caller xử lý rollback.
- Chạy tests sau mỗi thay đổi.

**Never:**
- Không nuốt lỗi (bare pass) mà không có log hoặc comment lý do rõ ràng.
- Không thay đổi signature hoặc return types của public service functions.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| External HTTP call fail | Timeout / ConnectionError | Log chi tiết, raise ExternalServiceError hoặc fallback an toàn | Ghi rõ error code, safe_for_client |
| Cache fail | Redis connection timeout | Log warning, tiếp tục luồng chính | Best-effort, không fail transaction |
| DB query fail | SQLAlchemyError | Rollback session nếu trong transaction, re-raise DatabaseError | Transaction an toàn |
| Unhandled exception | Exception bất ngờ | Log exception với traceback hoặc re-raise | Có comment giải thích lý do giữ Exception |

</frozen-after-approval>

## Code Map

- `app/exceptions.py` — NowingError hierarchy.
- `app/services/corporate_verification_service.py` (15 sites): Tra cứu doanh nghiệp qua API bên ngoài, cache.
- `app/services/phone_waterfall_service.py` (12 sites): Waterfall enrichment sđt qua nhiều providers.
- `app/services/billable_calls.py` (4 sites): Tính toán cước cuộc gọi / token billing.
- `app/services/token_tracking_service.py` (4 sites): Track token usage per turn.
- `app/services/contact_unlock_service.py` (3 sites): Mở khóa contact có tính phí ví.
- `app/services/etl_credit_service.py` (2 sites): Trừ credit khi chạy ETL pipeline.
- `app/services/pricing_registration.py` (2 sites): Đăng ký gói pricing.
- `app/services/token_quota_service.py` (2 sites): Kiểm tra quota token.
- `app/services/auto_reload_service.py` (1 site): Trigger auto-reload ví credit.
- `app/services/outcome_pricing_service.py` (1 site): Tính phí theo kết quả.
- `app/services/partner_service.py` (1 site): Xử lý đối tác / affiliate.

## Tasks & Acceptance

**Execution:**
- [x] `corporate_verification_service.py` (15 sites)
- [x] `phone_waterfall_service.py` (12 sites)
- [x] `billable_calls.py` (4 sites)
- [x] `token_tracking_service.py` (4 sites)
- [x] `contact_unlock_service.py` (3 sites)
- [x] `etl_credit_service.py` (2 sites)
- [x] `pricing_registration.py` (2 sites)
- [x] `token_quota_service.py` (2 sites)
- [x] `auto_reload_service.py` (1 site), `outcome_pricing_service.py` (1 site), `partner_service.py` (1 site)
- [x] Verify tests & ruff check

**Acceptance Criteria:**
- 100% các call-sites `except Exception` được narrow thành typed exception hoặc có inline rationale comment chuẩn.
- Các bài test unit liên quan pass 100%.
- `ruff check` pass không có lỗi.
