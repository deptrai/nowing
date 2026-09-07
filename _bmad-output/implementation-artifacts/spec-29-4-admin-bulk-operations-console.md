---
title: 'Story 29.4: Admin Bulk Operations Console'
type: 'feature'
created: '2026-09-07'
status: 'in-progress'
baseline_commit: '09a6ba0d9c1fb6308a8832b750f0107a74a7f272'
review_loop_iteration: 0
context: [
  "_bmad-output/implementation-artifacts/epic-29-context.md",
  "_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md"
]
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nowing chưa có console để superadmin (và owner có quyền) thực hiện thao tác hàng loạt trên workspace/member/memory nguồn: không có filter có cấu trúc, không có dry-run, không có job theo dõi tiến độ, không có kiểm soát idempotency, và audit trail theo từng subject bị thiếu — gây rủi ro khi xử lý abuse, compliance hoặc thay đổi đa tenant.

**Approach:** Thêm `BulkAction` enum, `bulk_op_job` + `bulk_op_errors` tables, structured filter builder (allow-list field/operator), dry-run preview, async job execution qua Celery, `Idempotency-Key` guard, per-subject `audit_events`, và trang `/admin/saas/bulk-ops` cho superadmin + `/dashboard/[workspace_id]/settings/bulk-ops` cho Owner scope.

## Boundaries & Constraints

**Always:**
- `BulkAction` enum là allow-list duy nhất: `archive_inactive_workspaces`, `rotate_api_keys`, `assign_role`, `delete_source_type_memories`, `apply_tier`, `revoke_membership`.
- Structured filter builder dùng allow-list field/operator theo từng action; KHÔNG cho phép free-form text query.
- Dry-run bắt buộc trước khi execute; nút Execute disabled cho đến khi dry-run xong.
- Mọi execute request phải gửi `Idempotency-Key` (UUID v4); backend lưu `key` + `request_hash` (SHA-256) vào `idempotency_keys` table (TTL 24h) và từ chối duplicate key trừ khi request hash khớp.
- Job chạy async qua Celery task `bulk_op_executor`; poll `GET /admin/saas/bulk-ops/{job_id}` để xem progress.
- `rotate_api_keys` là high-risk: bắt buộc password/MFA confirmation trước khi execute.
- Owner chỉ được execute trong workspace của mình (`workspace_id` filter bắt buộc trong filter spec) và phải có `Permission.SETTINGS_UPDATE` + `Permission.MEMBERS_REMOVE`; superadmin có thể cross-workspace.
- Mỗi subject thay đổi phải ghi `AuditEvent` với `actor_id`, `subject_type`, `subject_id`, `diff_payload`, `idempotency_key`.
- `bulk_op_errors` lưu `job_id`, `subject_type`, `subject_id`, `error_message`, `retryable`; UI hiển thị link download.
- `Workspace` chưa có `archived_at` — migration phải thêm cột này cho `archive_inactive_workspaces`.
- Chạy `alembic revision` cho schema mới; KHÔNG sửa migration cũ.
- Tái sử dụng `require_superuser()` cho admin routes, `check_permission` cho owner routes.

**Ask First:**
- Nếu muốn thêm action mới ngoài enum (ví dụ `delete_workspace`, `export_data`), cần xác nhận scope và AC bổ sung.
- Nếu cần hỗ trợ `rotate_api_keys` thực sự (revoke + re-issue API keys) hay chỉ đánh dấu `api_access_enabled=false` để reset.

**Never:**
- Không dùng raw SQL string interpolation cho filter builder; luôn parameterized qua SQLAlchemy `select()` + `where()`.
- Không cho phép action `archive_inactive_workspaces` chạy trên workspace đang có `is_active=true` trừ khi `inactive_days` filter > 0.
- Không lưu `idempotency_key` dưới dạng plaintext trong log; chỉ lưu hash trong `bulk_op_job`.
- Không tạo worktree mới, không `docker compose` tự động start BE/FE.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Superadmin mở `/admin/saas/bulk-ops` | Trang load | Thấy dropdown action, structured filter builder, nút Dry-run | `403` nếu không superuser |
| Owner mở `/dashboard/{id}/settings/bulk-ops` | Trang load | Chỉ thấy actions phù hợp workspace scope; `workspace_id` filter tự động inject | `403` nếu không `SETTINGS_UPDATE` + `MEMBERS_REMOVE` |
| Dry-run `archive_inactive_workspaces` | Filter: `last_activity < 90d`, `plan_tier = free` | Preview `COUNT(*)`, list workspace IDs, conflict warnings | `422` nếu filter field/operator không trong allow-list |
| Execute với `Idempotency-Key` mới | `POST /admin/saas/bulk-ops` + key | `202 Accepted`, `job_id`, `status=queued` | `400` nếu thiếu hoặc key > 64 chars |
| Execute với `Idempotency-Key` trùng | Cùng key, khác body | `409 Conflict` với `idempotency_conflict` | Không tạo job mới |
| Execute với `Idempotency-Key` trùng, cùng body | Cùng key, cùng SHA-256 | Trả về job hiện có (`200`) | Idempotent |
| Poll job đang chạy | `GET /admin/saas/bulk-ops/{job_id}` | `{status: "running", processed_count, affected_count, error_count}` | `404` nếu job không tồn tại |
| Job xong, có lỗi | `status=completed` với `error_count > 0` | List `bulk_op_errors` downloadable | Không throw |
| `rotate_api_keys` high-risk | Chọn action, chưa confirm MFA | `403` hoặc UI yêu cầu password/MFA | Block execute |
| `assign_role` khi 29.1 chưa ship | Action `assign_role` | `409` với `missing_dependency` | Disable UI nếu role service chưa có |
| `apply_tier` khi 29.3 chưa ship | Action `apply_tier` | `409` với `missing_dependency` | Disable UI nếu plan service chưa có |
| `revoke_membership` owner scope | Owner chọn workspace khác | `403` "Cannot operate outside own workspace" | Inject `workspace_id` bắt buộc |
| `delete_source_type_memories` | `source_type=SCRAPER_RUN` + `workspace_id` | Xóa memories theo filter, audit từng memory | `422` nếu `source_type` không hợp lệ |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/models/bulk_ops.py` (mới) — `BulkOpJob`, `BulkOpError`, `BulkAction` enum.
- `nowing_backend/alembic/versions/` — migration mới: `bulk_op_jobs` + `bulk_op_errors` tables.
- `nowing_backend/app/services/bulk_ops_service.py` (mới) — filter validation, dry-run, execute, idempotency, permission gate.
- `nowing_backend/app/routes/admin_saas_routes.py` — extend hoặc tách `admin_bulk_ops_routes.py` cho superadmin endpoints.
- `nowing_backend/app/routes/workspaces_routes.py` — owner-scoped endpoints `/workspaces/{id}/bulk-ops`.
- `nowing_backend/app/tasks/celery_tasks/bulk_op_tasks.py` (mới) — `bulk_op_executor` task.
- `nowing_backend/app/models/billing.py` — `AuditEvent` reuse.
- `nowing_backend/app/models/workspaces.py` — `Workspace`, `WorkspaceMembership`, `WorkspaceRole` reuse.
- `nowing_backend/app/db/enums.py` — `Permission` reuse.
- `nowing_backend/app/utils/rbac.py` — `check_permission` reuse.
- `nowing_web/contracts/types/admin-bulk-ops.types.ts` (mới) — Zod schemas.
- `nowing_web/lib/apis/admin-bulk-ops-api.service.ts` (mới) — client.
- `nowing_web/app/admin/saas/bulk-ops/page.tsx` (mới) — superadmin UI.
- `nowing_web/components/admin/bulk-ops/` — `FilterBuilder`, `DryRunCard`, `JobProgress`, `IdempotencyKeyField`, `MfaConfirmDialog`.
- `nowing_web/app/admin/admin-shell.tsx` — thêm nav `/admin/saas/bulk-ops`.
- `nowing_web/messages/en.json`, `vi.json` — i18n keys.
- `nowing_backend/tests/integration/services/test_bulk_ops_service.py` (mới) — unit/integration tests.
- `nowing_backend/tests/integration/routes/test_admin_bulk_ops.py` (mới) — route tests.

## Tasks & Acceptance

**Execution:**
- [ ] `nowing_backend/app/models/admin_ops.py` (new) — `BulkAction` enum, `BulkOpJob`, `BulkOpError`, `IdempotencyKey` models; hoặc thêm vào `app/models/workspaces.py` nếu admin domain chưa có file riêng.
- [ ] `nowing_backend/alembic/versions/` — migration thêm `archived_at` vào `workspaces`, tạo `bulk_op_jobs` + `bulk_op_errors` + `idempotency_keys` với indexes (`job_id`, `status`, `actor_id`, `idempotency_key` unique, `idempotency_keys.key` unique, `expires_at`).
- [ ] `nowing_backend/app/services/bulk_ops_service.py` — implement `validate_filter`, `dry_run`, `execute`, `get_job`, `cancel_job`, `check_permissions` (superadmin vs owner scope), `audit_per_subject`, `record_errors`.
- [ ] `nowing_backend/app/tasks/celery_tasks/bulk_op_tasks.py` — Celery task `bulk_op_executor` nhận `job_id`, iterate subjects, update progress, ghi audit + errors.
- [ ] `nowing_backend/app/routes/admin_saas_routes.py` hoặc `admin_bulk_ops_routes.py` — endpoints `POST /admin/saas/bulk-ops/dry-run`, `POST /admin/saas/bulk-ops`, `GET /admin/saas/bulk-ops/{job_id}`, `GET /admin/saas/bulk-ops/{job_id}/errors`, `POST /admin/saas/bulk-ops/{job_id}/cancel` (cancelable set).
- [ ] `nowing_backend/app/routes/workspaces_routes.py` — endpoints `POST /workspaces/{id}/bulk-ops` (owner scope, tự inject `workspace_id` filter).
- [ ] `nowing_backend/app/schemas/bulk_ops.py` (mới) — `BulkAction`, `FilterSpec`, `DryRunRequest/Response`, `ExecuteRequest/Response`, `JobStatusResponse`, `BulkOpErrorRead`.
- [ ] `nowing_web/contracts/types/admin-bulk-ops.types.ts` — Zod schemas cho request/response.
- [ ] `nowing_web/lib/apis/admin-bulk-ops-api.service.ts` — `dryRun`, `execute`, `getJob`, `getErrors`, `cancelJob`.
- [ ] `nowing_web/app/admin/saas/bulk-ops/page.tsx` — trang superadmin với ActionSelector, FilterBuilder, DryRunCard, IdempotencyKeyField, JobProgress.
- [ ] `nowing_web/components/admin/bulk-ops/` — tái sử dụng components cho owner view nếu cần.
- [ ] `nowing_web/app/admin/admin-shell.tsx` — thêm nav "Bulk Ops".
- [ ] `nowing_web/messages/en.json`, `vi.json` — i18n.
- [ ] `nowing_backend/tests/integration/services/test_bulk_ops_service.py` — test filter validation, dry-run, idempotency, permission gate.
- [ ] `nowing_backend/tests/integration/routes/test_admin_bulk_ops.py` — test routes với superuser + owner.
- [ ] `nowing_web/tests/admin/bulk-ops.spec.ts` — E2E happy path (optional nếu scope cho phép).

**Acceptance Criteria:**
- Given superadmin mở `/admin/saas/bulk-ops`, when trang load, then thấy dropdown `BulkAction`, structured filter builder, nút Dry-run.
- Given admin chọn action + filter, when bấm Dry-run, then preview `COUNT(*)` và danh sách affected subjects, nút Execute disabled cho đến khi dry-run xong.
- Given admin xác nhận dry-run + `Idempotency-Key`, when bấm Execute, then backend trả `202 Accepted` với `job_id`, job chạy async, và `Idempotency-Key` duplicate bị từ chối trừ khi request hash khớp.
- Given job đang chạy, when poll `GET /admin/saas/bulk-ops/{job_id}`, then thấy `status`, `affected_count`, `processed_count`, `error_count`, progress bar, và nút Cancel nếu action trong cancelable set.
- Given job hoàn thành, when kết thúc, then mỗi subject có `AuditEvent` với `diff_payload`, và `bulk_op_errors` lưu lỗi retryable.
- Given action `rotate_api_keys`, when admin chưa confirm MFA, then execute bị block và UI yêu cầu password/MFA.
- Given Owner dùng bulk-ops, when execute, then chỉ được phép trong workspace của mình và phải có `SETTINGS_UPDATE` + `MEMBERS_REMOVE`; superadmin có thể cross-workspace.
- Given `assign_role` hoặc `apply_tier` khi 29.1/29.3 chưa ship, when chọn action, then API trả `409` với `missing_dependency` và UI disable action đó.

## Design Notes

- `bulk_op_job.status`: `queued`, `running`, `completed`, `failed`, `cancelled`, `partial`.
- `bulk_op_job.filter` lưu JSONB theo `FilterSpec` (allow-list field/operator per action).
- `FilterSpec` schema: list of clauses `{"field": str, "operator": "eq|neq|gt|gte|lt|lte|in|not_in", "value": any}`.
- `idempotency_key` là UUID v4 client-generated, max 64 chars; `request_hash` = SHA-256 của body; lưu vào `idempotency_keys` table với TTL 24h.
- Cancelable actions: `archive_inactive_workspaces`, `delete_source_type_memories`, `revoke_membership` (nếu đang `queued` hoặc `running`); `rotate_api_keys`, `apply_tier`, `assign_role` không cancel được sau khi `running`.
- `rotate_api_keys` cần `password` hoặc `mfa_token` trong request body; backend verify trước khi enqueue; v1 chỉ set `Workspace.api_access_enabled = false`.
- Owner scope: `workspace_id` trong filter bị force bằng path param; không cho phép override.
- `delete_source_type_memories` dùng `source_type` từ `MemorySourceType` enum; hard delete theo `workspace_id` + `source_type`.
- `archive_inactive_workspaces` set `Workspace.archived_at = now` (cột `archived_at` phải được migration thêm trước đó).
- `apply_tier` gọi `workspace_limit_service.create_subscription_change` với `immediate=true` nếu không conflict; `assign_role` gọi role assignment service từ 29.1.
- Progress update: task ghi `processed_count` sau mỗi batch (size 100), `error_count` vào `bulk_op_errors`.
- Audit: mỗi subject → `AuditEvent(action=bulk_op.{action}.{subject_type}, actor_id, subject_id, diff_payload, idempotency_key)`; cuối job → summary `AuditEvent(action=bulk_op.{action}.summary)`.

## Verification

**Commands:**
- `cd nowing_backend && alembic upgrade head` — expected: migration chạy thành công.
- `cd nowing_backend && pytest tests/integration/services/test_bulk_ops_service.py -x` — expected: pass.
- `cd nowing_backend && pytest tests/integration/routes/test_admin_bulk_ops.py -x` — expected: pass.
- `cd nowing_web && ./node_modules/.bin/tsc --noEmit` — expected: no TS errors.
- `cd nowing_web && npx @biomejs/biome check app/admin/saas/bulk-ops/page.tsx lib/apis/admin-bulk-ops-api.service.ts components/admin/bulk-ops/` — expected: pass.
- `cd nowing_web && npx playwright test tests/admin/bulk-ops.spec.ts` — expected: pass (nếu có).

**Manual checks (if no CLI):**
- Mở `/admin/saas/bulk-ops`, chọn `archive_inactive_workspaces`, filter `plan_tier=free`, `last_activity>90d`, Dry-run → Execute với Idempotency-Key, poll job → completed.
- Thử execute lại cùng `Idempotency-Key` → `409` hoặc trả về job cũ.
- Thử `rotate_api_keys` mà không confirm MFA → bị chặn.
- Owner vào `/dashboard/{id}/settings/bulk-ops`, chọn `revoke_membership`, filter `role=viewer` → chỉ thấy members trong workspace đó.
