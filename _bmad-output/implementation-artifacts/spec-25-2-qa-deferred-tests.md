---
title: 'Giải quyết deferred QA findings Story 25-2 Manual Credit Adjustment'
type: 'chore'
created: '2026-09-10'
status: 'completed'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 25-2 để lại 4 deferred QA findings: thiếu test AC-1 validation cho nhiều trường hợp lỗi, thiếu test trực tiếp Redis Redlock / Postgres FOR UPDATE / lock_timeout, thiếu test DEBIT và non-superuser role, thiếu test CSV export / aggregate stats / 36px row height UI.

**Approach:** Bổ sung unit/integration tests và Playwright tests cho `ManualCreditAdjustmentService` và Admin Credits page, không đổi logic business hiện có.

## Boundaries & Constraints

**Always:**
- Chỉ thêm test, không sửa logic service trừ khi phát hiện lỗi thực sự.
- Dùng fixtures có sẵn: `db_workspace`, `db_superuser`, `admin_client`, `client_as_regular_user`.
- Test concurrency chỉ mô phỏng Redis lock và Postgres lock timeout nếu không có Redis thật.

**Ask First:**
- Nếu UI component thay đổi layout/row height ảnh hưởng design hiện có.

**Never:**
- Không thay đổi endpoint auth hoặc quota.
- Không thêm dependency mới.

## Code Map

- `nowing_backend/app/services/manual_credit_service.py` -- target service.
- `nowing_backend/app/routes/admin_credits_routes.py` -- route validation.
- `nowing_backend/tests/unit/services/test_manual_credits.py` -- unit validation tests.
- `nowing_backend/tests/integration/services/test_manual_credits.py` -- service-level integration tests.
- `nowing_backend/tests/integration/routes/test_admin_credits.py` -- route-level integration tests.
- `nowing_web/app/admin/credits/page.tsx` -- Admin Credits page with CSV export and stats.
- `nowing_web/components/admin/ManualCreditModal.tsx` -- adjustment modal.
- `nowing_web/lib/apis/admin-credits-api.service.ts` -- API client.
- `nowing_web/tests/admin/` -- Playwright admin tests location.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/tests/unit/services/test_manual_credits.py` -- bổ sung test cases cho `reason` min length, `ticket_ref` missing, `workspace_id` format/negative, `amount_credits` zero/negative, `direction` invalid values.
- [x] `nowing_backend/tests/integration/services/test_manual_credits.py` -- bổ sung test kiểm tra `SET LOCAL lock_timeout`, `pg_advisory_xact_lock`, và `with_for_update` được gọi.
- [x] `nowing_backend/tests/integration/routes/test_admin_credits.py` -- bổ sung test non-superuser bị 403 và test DEBIT hợp lệ không tiêu tốn quota.
- [x] `nowing_web/tests/admin/credits.spec.ts` -- bổ sung Playwright test CSV export, 4 stats cards, và row height 36px.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- cập nhật 4 findings 25-2 thành `Resolved`.

**Acceptance Criteria:**
- Given các test AC-1 validation được thêm, when chạy `pytest tests/unit/services/test_manual_credits.py`, then tất cả tests pass.
- Given các test concurrency/lock được thêm, when chạy `pytest tests/integration/services/test_manual_credits.py`, then tests pass.
- Given non-superuser client gọi POST /admin/credits/adjust, then trả về 403.
- Given DEBIT hợp lệ, then không bị từ chối bởi daily quota.
- Given Playwright test chạy, then CSV export, 4 stats cards, row height 36px được verify.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/services/test_manual_credits.py tests/integration/services/test_manual_credits.py tests/integration/routes/test_admin_credits.py` -- expected: all GREEN.
- `cd nowing_web && npx playwright test tests/admin/credits.spec.ts` -- expected: all GREEN.

**Manual checks:**
- `deferred-work.md` được cập nhật với `Resolved from: code review of 25-2...` cho 4 findings.
