---
title: "Jev Stream Dedup & PII Guardrail Pipeline"
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

**Problem:** Dữ liệu cào từ mạng xã hội có thể chứa thông tin định danh cá nhân nhạy cảm (CCCD/CMND) và dẫn đến trùng lặp lead trong CRM nếu không có tầng lọc thông minh.
**Approach:** Đưa PII Sanitization (redact CCCD/CMND) và Jev Entity Deduplication vào pipeline tiêu thụ `stream:social:raw_posts` trong `social_stream_worker.py`.

## Boundaries & Constraints

**Always:**
- Redact toàn bộ CCCD (12 số) và CMND (9 số) thành `[REDACTED_ID]` trước khi xử lý lead.
- Phân tầng kết quả đối soát Entity Match: >= 1.5 merge, 0.5 - 1.5 curation, < 0.5 entity mới.
- Bảo đảm cam kết XACK sau khi hoàn tất DB transaction.

</intent-contract>

## Auto Run Result

**Status**: done
**Completed Actions**:
- Tạo `app/tasks/jev_guardrails.py` với `sanitize_pii_content` và `evaluate_entity_dedup`.
- Cập nhật `social_stream_worker.py` làm sạch content trước khi bóc tách thực thể và lưu DB.
- Unit test `tests/unit/tasks/test_jev_guardrails.py` passed 5/5.
