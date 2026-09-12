---
title: RequirePermission migration — Batch 4 (Lead Intelligence & Sequences: sequence, lead_pipeline, leads, lead_scoring, lead_batch, dnc)
type: refactor
created: '2026-09-12'
status: done
baseline_commit: da2afede997539ce9bd4f5775e853757b8bac6de
review_loop_iteration: 0
context:
  - nowing_backend/app/dependencies/auth.py
  - nowing_backend/app/routes/sequence_routes.py
  - nowing_backend/app/routes/lead_pipeline_routes.py
  - nowing_backend/app/routes/leads_routes.py
  - nowing_backend/app/routes/lead_scoring_routes.py
  - nowing_backend/app/routes/lead_batch_routes.py
  - nowing_backend/app/routes/dnc_routes.py
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sau Batch 1 (20 sites), Batch 2 (18 sites) và Batch 3 (37 sites), còn ~200 call-sites gọi thủ công `check_permission` / `check_workspace_access`. Miền Lead Intelligence & Outreach Sequences là domain P0 với nhiều endpoint cần kiểm tra quyền và tenancy.

**Approach:** Migrate Batch 4 gồm 40 call-sites trên 6 route files thuộc nhóm Lead Intelligence & Sequences: `sequence_routes.py` (11), `lead_pipeline_routes.py` (10), `leads_routes.py` (6), `lead_scoring_routes.py` (5), `lead_batch_routes.py` (4), `dnc_routes.py` (4) sang `Depends(RequirePermission(...))` / `Depends(RequireWorkspaceAccess())`. Cập nhật các mock patch target trong tests tương ứng sang `app.dependencies.auth`.

## Boundaries & Constraints

**Always:**
- Chỉ refactor 6 route files mục tiêu và các test patch targets liên quan.
- Giữ nguyên HTTP contract: URL, methods, status codes, response models, error messages.
- Xoá `await check_permission(...)` và `await check_workspace_access(...)` khỏi body khi đã inject qua `Depends`.
- Cập nhật test mock patch targets sang `app.dependencies.auth.check_permission` / `check_workspace_access`.

**Ask First:**
- Đụng tới các route files ngoài 6 files trên.

**Never:**
- Không thay đổi logic nghiệp vụ trong route handlers ngoài việc bỏ call `check_permission` / `check_workspace_access`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Member đủ quyền | Session hợp lệ, role có permission | Thực thi endpoint bình thường | N/A |
| Member thiếu quyền | Session hợp lệ, role thiếu permission | 403 Forbidden | `HTTPException(403, detail=error_message)` |
| Không thuộc workspace | Session hợp lệ, không có membership | 403 Forbidden | `HTTPException(403, detail="You don't have access to this workspace")` |
| Test patch permission | Unit/integration test mock permission | Mock bypasses permission | Patch `app.dependencies.auth` |

</frozen-after-approval>

## Code Map

- `app/dependencies/auth.py` — `RequirePermission` và `RequireWorkspaceAccess`.
- `app/routes/sequence_routes.py` (11 sites): Tất cả dùng `RequireWorkspaceAccess()`.
- `app/routes/lead_pipeline_routes.py` (10 sites): Tất cả dùng `RequireWorkspaceAccess()`, inject `membership` vào handler.
- `app/routes/leads_routes.py` (6 sites): `LEADS_READ` (L271, L377, L452, L508), `LEADS_WRITE` (L478, L803).
- `app/routes/lead_scoring_routes.py` (5 sites): `LEADS_SCORE` (L45), `LEADS_READ` (L91, L139, L178), `SETTINGS_UPDATE` (L213).
- `app/routes/lead_batch_routes.py` (4 sites): `LEADS_WRITE` (L124, L199, L269, L384).
- `app/routes/dnc_routes.py` (4 sites): `LEADS_READ` (L206), `LEADS_WRITE` (L263, L294, L333).
- Test patch targets:
  - `tests/integration/routes/test_sequence_routes.py`
  - `tests/integration/routes/test_reverse_icp_route.py`
  - `tests/unit/routes/test_leads_routes.py`
  - `tests/unit/routes/test_lead_batch_ingest.py`
  - `tests/integration/routes/test_dnc_routes.py`

## Tasks & Acceptance

**Execution:**
- [x] `app/routes/sequence_routes.py` -- Migrate 11 call-sites sang `Depends(RequireWorkspaceAccess())`
- [x] `app/routes/lead_pipeline_routes.py` -- Migrate 10 call-sites sang `Depends(RequireWorkspaceAccess())`
- [x] `app/routes/leads_routes.py` -- Migrate 6 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/lead_scoring_routes.py` -- Migrate 5 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/lead_batch_routes.py` -- Migrate 4 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/dnc_routes.py` -- Migrate 4 call-sites sang `Depends(RequirePermission(...))`
- [x] Tests patch targets -- Cập nhật mock patch targets sang `app.dependencies.auth`
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- Cập nhật tiến độ Batch 4 và số lượng còn lại

**Acceptance Criteria:**
- Given endpoint trong 6 files trên, when gọi request, then quyền được kiểm tra qua `Depends(RequirePermission)` / `Depends(RequireWorkspaceAccess)`.
- Given user thiếu quyền, when gọi endpoint, then trả 403 Forbidden với message chuẩn.
- Given bộ tests unit/integration hiện hữu, when chạy pytest, then 100% pass.
- Given ruff check, then không có lint/import errors.

## Spec Change Log

_Chưa có thay đổi._

## Verification

**Commands:**
- `ruff check app/routes/sequence_routes.py app/routes/lead_pipeline_routes.py app/routes/leads_routes.py app/routes/lead_scoring_routes.py app/routes/lead_batch_routes.py app/routes/dnc_routes.py`
- `python -m pytest tests/unit/routes/test_leads_routes.py tests/unit/routes/test_lead_batch_ingest.py -q`
- `python -m pytest tests/integration/routes/test_sequence_routes.py tests/integration/routes/test_reverse_icp_route.py tests/integration/routes/test_dnc_routes.py -q`

## Suggested Review Order

**Route migration — RequireWorkspaceAccess**
- Migrate 11 sequence endpoints sang RequireWorkspaceAccess
  [`sequence_routes.py:1`](../../nowing_backend/app/routes/sequence_routes.py)
- Migrate 10 lead pipeline endpoints sang RequireWorkspaceAccess (inject membership)
  [`lead_pipeline_routes.py:1`](../../nowing_backend/app/routes/lead_pipeline_routes.py)

**Route migration — RequirePermission**
- Migrate 6 leads endpoints sang RequirePermission
  [`leads_routes.py:1`](../../nowing_backend/app/routes/leads_routes.py)
- Migrate 5 lead scoring endpoints sang RequirePermission
  [`lead_scoring_routes.py:1`](../../nowing_backend/app/routes/lead_scoring_routes.py)
- Migrate 4 lead batch endpoints sang RequirePermission
  [`lead_batch_routes.py:1`](../../nowing_backend/app/routes/lead_batch_routes.py)
- Migrate 4 DNC compliance endpoints sang RequirePermission
  [`dnc_routes.py:1`](../../nowing_backend/app/routes/dnc_routes.py)

**Test mock patch target alignment**
- Update patch targets sang app.dependencies.auth
  [`test_leads_routes.py:157`](../../nowing_backend/tests/unit/routes/test_leads_routes.py)
  [`test_lead_batch_ingest.py:29`](../../nowing_backend/tests/unit/routes/test_lead_batch_ingest.py)
  [`test_sequence_routes.py:95`](../../nowing_backend/tests/integration/routes/test_sequence_routes.py)
  [`test_reverse_icp_route.py:78`](../../nowing_backend/tests/integration/routes/test_reverse_icp_route.py)
  [`test_dnc_routes.py:58`](../../nowing_backend/tests/integration/routes/test_dnc_routes.py)
