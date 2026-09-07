---
title: 'Story 29.3: Tenant Subscription Tier & Quota Management'
type: 'feature'
created: '2026-09-07'
status: 'done'
baseline_commit: 'f3490b6427c21425fb7b5de87affdb5ba13fbe46'
review_loop_iteration: 0
context: [
  "_bmad-output/implementation-artifacts/epic-29-context.md",
  "_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md"
]
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nowing chưa có hệ thống quản lý subscription tier đa tenant: superadmin không thể định nghĩa/hiệu chỉnh plan catalog, workspace owner không thể tự nâng/hạ cấp plan, và thay đổi tier thiếu khung an toàn (grace period 7 ngày, kiểm tra quota, rollback).

**Approach:** Mở rộng `WorkspaceLimit` thành plan catalog và thêm bảng `subscription_change`. Xây dựng API admin quản lý plan, API owner tự đổi tier, và các trang UI tương ứng với kiểm tra conflict và xác nhận thời điểm có hiệu lực.

## Boundaries & Constraints

**Always:**
- `WorkspaceLimit` tuân theo XOR constraint: `plan_tier` set thì `workspace_id` NULL (plan default); `workspace_id` set thì `plan_tier` NULL (per-workspace override).
- Giá trị tiền tệ lưu dạng `price_micros` + `currency`, mặc định `USD` (AD-8).
- Thay đổi tier mặc định có hiệu lực sau 7 ngày (`effective_at = now + 7d`) và `reversible_until = effective_at`.
- Downgrade gây vượt quota trả về `409 Conflict` với checklist cụ thể.
- Audit mọi thay đổi tier vào `audit_events` với `diff_payload`.
- API admin bắt buộc `require_superuser()`; API owner self-serve kiểm tra `Permission.SETTINGS_UPDATE`.
- Giữ grandfathered limits cho workspace đang active khi plan definition thay đổi.
- Chạy `alembic revision` cho schema change; KHÔNG sửa migration cũ.

**Ask First:**
- Nếu muốn hỗ trợ trial period cron chuyển đổi tự động hoặc thanh toán tích hợp, trước tiên cần xác nhận scope (v1 của 29.3 có thể bỏ qua payment gateway thực, chỉ ghi nhận `payment_method_id` tùy chọn).
- Nếu cần quota enforcement real-time trên mọi thao tác (memory create, invite, source enable) trong vòng này hay deferred.

**Never:**
- Không tự ý thay đổi giá trị plan của workspace hiện tại khi chỉnh sửa plan catalog.
- Không lưu thông tin thẻ thanh toán trong Nowing DB.
- Không tạo worktree mới, không `docker compose` tự động start BE/FE.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Superadmin tạo plan `Growth` mới | `POST /admin/saas/plans` với `plan_tier=growth`, `max_members=50`, `max_memory_count=50000`, `price_micros=4900000` | Plan default được lưu, `WorkspaceLimit` với `workspace_id=NULL` | `422` nếu `plan_tier` trùng plan default hiện có |
| Workspace owner nâng cấp Free -> Team | `POST /workspaces/{id}/subscription-change` `to_plan=team` | `subscription_change` row được tạo, `effective_at=now+7d`, `status=pending`, email confirmation đi vào queue | `403` nếu không có quyền `SETTINGS_UPDATE`; `422` nếu `to_plan` không tồn tại |
| Owner downgrade Team -> Free khi vượt quota | `POST /workspaces/{id}/subscription-change` `to_plan=free` | Trả về `409 Conflict` với `conflicts: {memory_count: 1200, limit: 1000, members: 15, limit: 3, ...}` | Không tạo `subscription_change` nếu có conflict |
| Owner chọn immediate upgrade không conflict | `to_plan=team` + `immediate=true` | `effective_at=now`, `Workspace.plan_tier` cập nhật ngay, `status=active` | `409` nếu vượt quota; `422` nếu plan không tồn tại |
| Undo tier change trong 7 ngày | `POST /workspaces/{id}/subscription-change/{change_id}/revert` | `Workspace.plan_tier` khôi phục, `subscription_change.status=reverted`, ghi `audit_events` | `409` nếu `reversible_until` hết hạn; `404` nếu không tìm thấy |
| Hủy pending change | `POST /workspaces/{id}/subscription-change/{change_id}/cancel` | `status=cancelled` | `409` nếu `status` không phải `pending` |
| Liệt kê lịch sử thay đổi | `GET /workspaces/{id}/subscription-changes` | Danh sách `from_plan`, `to_plan`, `status`, `effective_at`, `reversible_until` | `404` nếu workspace không tồn tại |
| Superadmin cập nhật plan `Team` | `PUT /admin/saas/plans/{plan_tier}` với `max_memory_count=60000` | Plan default cập nhật, workspace đang dùng `Team` giữ nguyên grandfathered | `422` nếu `plan_tier` bị đổi thành tên khác; `404` nếu plan không tồn tại |
| Plan catalog superadmin | `GET /admin/saas/plans` | Danh sách các plan với badge "System default" | `403` nếu không superuser |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/models/workspaces.py` -- chứa `Workspace` (có `plan_tier`), `WorkspaceLimit` (plan default / override); cần thêm `SubscriptionChange` model.
- `nowing_backend/alembic/versions/` -- thêm migration mới, kế thừa revision mới nhất.
- `nowing_backend/app/services/workspace_limits.py` -- logic resolve effective limits; nơi thêm `get_effective_limits` reuse, `get_usage_snapshot` dùng cho conflict check.
- `nowing_backend/app/schemas/workspace.py` -- schema `WorkspaceLimitsResponse`, `WorkspaceLimitUpdate`; cần thêm `PlanDefinitionCreate/Update/Read` và `SubscriptionChangeCreate/Read/Status`.
- `nowing_backend/app/routes/workspaces_routes.py` -- thêm endpoints subscription self-serve.
- `nowing_backend/app/routes/admin_*.py` hoặc file mới `admin_saas_routes.py` -- endpoints plan catalog và subscription admin view.
- `nowing_backend/app/models/billing.py` -- `AuditEvent` để ghi audit tier change.
- `nowing_web/lib/apis/workspaces-api.service.ts` -- client method gọi API limits/subscription.
- `nowing_web/lib/apis/admin-saas-api.service.ts` (hoặc tương tự) -- client admin plan catalog.
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/limits/page.tsx` -- trang limits hiện tại, sẽ mở rộng thêm "Change plan" / subscription history.
- `nowing_web/components/settings/workspace-limits-manager.tsx` -- UI limits hiện tại, cần thêm plan card, comparison, và subscription flow.
- `nowing_web/app/admin/saas/plans/page.tsx` -- trang admin plan catalog mới (tạo mới).
- `nowing_web/app/admin/layout.tsx` hoặc `admin-shell.tsx` -- thêm menu item cho `/admin/saas/plans`.
- `nowing_backend/tests/integration/services/test_workspace_limits.py` -- mẫu test limit service.
- `nowing_backend/tests/integration/routes/test_workspaces.py` -- mẫu test workspace routes.

## Tasks & Acceptance

**Execution:**
- [ ] `nowing_backend/app/models/workspaces.py` -- thêm model `SubscriptionChange` (`id`, `workspace_id`, `from_plan`, `to_plan`, `effective_at`, `reversible_until`, `status`, `initiated_by`, `payment_method_id`, `immediate`, `diff_payload`) và relationship từ `Workspace`.
- [ ] `nowing_backend/app/models/workspaces.py` -- mở rộng `WorkspaceLimit` thêm các cột `max_monthly_credits`, `max_sources`, `support_level`, `price_micros`, `currency` (nullable, default currency `USD` trên schema/application).
- [ ] `nowing_backend/alembic/versions/` -- tạo migration mới thêm cột `WorkspaceLimit` mới và bảng `subscription_changes`; seed plan catalog mặc định Free/Team/Growth/Enterprise.
- [ ] `nowing_backend/app/schemas/workspace.py` -- thêm `PlanDefinitionRead/Create/Update`, `SubscriptionChangeCreate/Read/Status`, `SubscriptionChangeConflict`, và `WorkspaceSubscriptionResponse`.
- [ ] `nowing_backend/app/services/workspace_limits.py` -- thêm `get_plan_catalog`, `get_subscription_changes`, `create_subscription_change`, `revert_subscription_change`, `cancel_subscription_change`, `check_plan_change_conflicts` (so sánh usage vs new plan limits).
- [ ] `nowing_backend/app/routes/workspaces_routes.py` -- thêm endpoints `POST/GET /workspaces/{id}/subscription-changes`, `POST /workspaces/{id}/subscription-changes/{change_id}/revert`, `POST /.../cancel`.
- [ ] `nowing_backend/app/routes/admin_saas_routes.py` -- tạo route mới `GET/POST/PUT/DELETE /admin/saas/plans` (hoặc bổ sung vào admin workspace routes) bảo vệ bởi `require_superuser`.
- [ ] `nowing_backend/app/routes/workspaces_routes.py` -- cập nhật `WorkspaceLimitsResponse` trả về thêm `max_monthly_credits`, `max_sources`, `support_level`, `price_micros`, `currency` nếu schema đã mở rộng.
- [ ] `nowing_web/lib/apis/workspaces-api.service.ts` -- thêm các hàm gọi subscription APIs.
- [ ] `nowing_web/lib/apis/admin-saas-api.service.ts` -- thêm các hàm CRUD plan catalog.
- [ ] `nowing_web/components/settings/workspace-limits-manager.tsx` -- hiển thị plan hiện tại, nút "Đổi plan", bảng so sánh plan, dialog xác nhận với `effective_at` mặc định 7 ngày / `immediate`, và lịch sử subscription.
- [ ] `nowing_web/components/settings/workspace-limits-manager.tsx` -- hiển thị dialog downgrade conflict checklist khi API trả `409`.
- [ ] `nowing_web/app/admin/saas/plans/page.tsx` -- trang admin hiển thị danh sách plan, form thêm/sửa plan, badge "System default".
- [ ] `nowing_web/app/admin/admin-shell.tsx` -- thêm menu "SaaS Plans".
- [ ] `nowing_backend/app/services/workspace_limits.py` -- thêm unit/integration test cho conflict check, revert, plan catalog CRUD.
- [ ] `nowing_backend/tests/integration/routes/test_workspaces.py` -- thêm test cho subscription change endpoints.

**Acceptance Criteria:**
- Given superadmin mở `/admin/saas/plans`, when trang load, then thấy danh sách plan với `max_members`, `max_memory_count`, `price_micros`, `currency`, `support_level`.
- Given workspace ở plan Free, when superadmin (hoặc owner) upgrade lên Team, then tạo `subscription_change` có `effective_at` sau 7 ngày và `status=pending`.
- Given owner downgrade xuống Free nhưng `memory_count` hoặc `member_count` vượt giới hạn mới, when gọi API, then nhận `409 Conflict` với checklist cụ thể.
- Given subscription change trong 7 ngày reversible, when owner bấm "Undo", then `Workspace.plan_tier` khôi phục, `subscription_change.status=reverted`, và `audit_events` ghi diff.
- Given workspace owner truy cập `/dashboard/[workspace_id]/workspace-settings/limits`, when trang load, then thấy plan hiện tại, nút đổi plan, so sánh plan, và lịch sử thay đổi.
- Given superadmin chỉnh sửa plan `Team`, when lưu, then plan default cập nhật nhưng workspace đang active trên `Team` giữ nguyên limit cũ cho đến khi đổi plan.

## Spec Change Log

## Design Notes

- `WorkspaceLimit` đã có logic plan default / override trong `WorkspaceLimitService.get_effective_limits`. Chỉ cần mở rộng thêm trường mới và đảm bảo `_resolve` đọc được chúng.
- `subscription_change` có `status` enum: `pending`, `active`, `cancelled`, `reverted`, `expired`. `effective_at` tính từ now + 7 ngày nếu không `immediate`. `reversible_until` = `effective_at`.
- Hàm `check_plan_change_conflicts` nên tái sử dụng `get_usage_snapshot` để so sánh `documents`, `members`, `runs` (trong `run_period_hours`), `storage_bytes`, `memory_count`, `memory_bytes` với các trường mới của plan đích.
- UI plan comparison dùng bảng 4 cột (Free/Team/Growth/Enterprise), highlight plan hiện tại, disable nâng cấp lên Enterprise nếu self-serve không cho phép (tuỳ chọn).

## Verification

**Commands:**
- `cd nowing_backend && alembic upgrade head` -- expected: migration chạy thành công.
- `cd nowing_backend && pytest tests/integration/services/test_workspace_limits.py -x` -- expected: pass.
- `cd nowing_backend && pytest tests/integration/routes/test_workspaces.py -x` -- expected: pass.
- `cd nowing_web && ./node_modules/.bin/tsc --noEmit` -- expected: no TS errors.
- `cd nowing_web && npx @biomejs/biome check components/settings/workspace-limits-manager.tsx app/admin/saas/plans/page.tsx lib/apis/admin-saas-api.service.ts` -- expected: pass.

**Manual checks (if no CLI):**
- Mở `/admin/saas/plans`, tạo plan `Growth`, kiểm tra DB có `WorkspaceLimit` với `plan_tier=growth` và `workspace_id=NULL`.
- Mở `/dashboard/1/workspace-settings/limits`, bấm "Đổi plan", chọn `Team`, xác nhận `effective_at` là 7 ngày sau.
- Thử downgrade về `Free` khi workspace có nhiều hơn giới hạn Free, xác nhận dialog hiển thị checklist.
