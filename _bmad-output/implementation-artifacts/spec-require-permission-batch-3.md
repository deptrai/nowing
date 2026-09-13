---
title: RequirePermission migration — Batch 3 (alert_rules, projects, skills, memory_browser, workspace_tables)
type: refactor
created: '2026-09-12'
status: done
baseline_commit: 5a17a9afd72d4566092ffaa09d650f30e27f60cc
review_loop_iteration: 0
context:
  - nowing_backend/app/dependencies/auth.py
  - nowing_backend/app/routes/alert_rules_routes.py
  - nowing_backend/app/routes/projects_routes.py
  - nowing_backend/app/routes/skills_routes.py
  - nowing_backend/app/routes/memory_browser_routes.py
  - nowing_backend/app/routes/workspace_tables_routes.py
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Còn ~237 call-sites gọi thủ công `await check_permission(...)` lặp lại mã kiểm tra quyền, không tận dụng cơ chế Dependency Injection của FastAPI.

**Approach:** Migrate Batch 3 gồm 37 call-sites trên 5 route files dùng path parameter `workspace_id` và `get_auth_context`: `alert_rules_routes.py` (10), `projects_routes.py` (8), `skills_routes.py` (7), `memory_browser_routes.py` (7), `workspace_tables_routes.py` (5) sang `Depends(RequirePermission(...))`. Cập nhật các mock patch target trong tests tương ứng sang `app.dependencies.auth`.

## Boundaries & Constraints

**Always:**
- Chỉ refactor 5 route files mục tiêu và các test patch targets liên quan.
- Giữ nguyên HTTP contract: URL, methods, status codes, response models, error messages.
- Xoá `await check_permission(...)` khỏi body khi đã inject qua `Depends`.
- Cập nhật test mock patch targets từ `<module>.check_permission` sang `app.dependencies.auth.check_permission`.

**Ask First:**
- Đụng tới các route files ngoài 5 files trên hoặc sửa `RequirePermission`.

**Never:**
- Không thay đổi logic nghiệp vụ trong route handlers ngoài việc bỏ call `check_permission`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Member đủ quyền | Session hợp lệ, role có permission | Thực thi endpoint bình thường | N/A |
| Member thiếu quyền | Session hợp lệ, role thiếu permission | 403 Forbidden | `HTTPException(403, detail=error_message)` |
| Không thuộc workspace | Session hợp lệ, không có membership | 403 Forbidden | `HTTPException(403, detail="You don't have access to this workspace")` |
| Test patch permission | Unit test mock check_permission | Mock bypasses permission | Patch `app.dependencies.auth.check_permission` |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/dependencies/auth.py` — `RequirePermission(permission, message)`.
- `app/routes/alert_rules_routes.py` (10 sites): L69, L115, L195, L250, L312 (`ALERTS_READ`); L86, L133 (`ALERTS_CREATE`); L213, L274 (`ALERTS_UPDATE`); L231 (`ALERTS_DELETE`).
- `app/routes/projects_routes.py` (8 sites): L96, L175 (`PROJECTS_READ`); L135 (`PROJECTS_CREATE`); L216, L300, L346, L406 (`PROJECTS_UPDATE`); L269 (`PROJECTS_DELETE`).
- `app/routes/skills_routes.py` (7 sites): L43, L84, L176 (`SKILLS_READ`); L115 (`SKILLS_CREATE`); L207 (`SKILLS_UPDATE`); L277 (`SKILLS_DELETE`); L308 (`SKILLS_EXECUTE`).
- `app/routes/memory_browser_routes.py` (7 sites): L62, L106, L126, L146, L177, L208 (`MEMORIES_VIEW`); L241 (`MEMORIES_UPDATE`).
- `app/routes/workspace_tables_routes.py` (5 sites): L36, L107 (`LEADS_READ`); L66, L138, L180 (`LEADS_WRITE`).
- Test patch targets:
  - `tests/unit/routes/test_skills_routes.py`
  - `tests/unit/routes/test_projects_routes.py`
  - `tests/unit/routes/test_workspace_tables_routes.py`

## Tasks & Acceptance

**Execution:**
- [x] `app/routes/alert_rules_routes.py` -- Migrate 10 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/projects_routes.py` -- Migrate 8 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/skills_routes.py` -- Migrate 7 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/memory_browser_routes.py` -- Migrate 7 call-sites sang `Depends(RequirePermission(...))`
- [x] `app/routes/workspace_tables_routes.py` -- Migrate 5 call-sites sang `Depends(RequirePermission(...))`
- [x] `tests/unit/routes/test_skills_routes.py` -- Cập nhật patch targets sang `app.dependencies.auth.check_permission`
- [x] `tests/unit/routes/test_projects_routes.py` -- Cập nhật patch targets sang `app.dependencies.auth.check_permission`
- [x] `tests/unit/routes/test_workspace_tables_routes.py` -- Cập nhật patch target sang `app.dependencies.auth.check_permission`
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- Cập nhật tiến độ Batch 3 và số lượng còn lại

**Acceptance Criteria:**
- Given endpoint trong 5 files trên, when gọi request, then quyền được kiểm tra qua `Depends(RequirePermission)`.
- Given user thiếu quyền, when gọi endpoint, then trả 403 Forbidden với message chuẩn.
- Given bộ tests unit/integration hiện hữu, when chạy pytest, then 100% pass.
- Given ruff check, then không có lint/import errors.

## Spec Change Log

_Chưa có thay đổi._

## Verification

**Commands:**
- `ruff check app/routes/alert_rules_routes.py app/routes/projects_routes.py app/routes/skills_routes.py app/routes/memory_browser_routes.py app/routes/workspace_tables_routes.py tests/unit/routes/test_skills_routes.py tests/unit/routes/test_projects_routes.py tests/unit/routes/test_workspace_tables_routes.py`
- `python -m pytest tests/unit/routes/test_projects_routes.py tests/unit/routes/test_skills_routes.py tests/unit/routes/test_workspace_tables_routes.py -q`
- `python -m pytest tests/integration/alerts/ tests/integration/routes/test_projects_routes.py tests/integration/routes/test_skills_routes.py tests/integration/routes/test_memory_browser_routes.py -q`

## Suggested Review Order

**Dependency enhancements**
- Thêm default error message cho RequirePermission factory
  [`auth.py:46`](../../nowing_backend/app/dependencies/auth.py#L46)

**Route migration**
- Migrate 10 alert rules endpoints sang RequirePermission
  [`alert_rules_routes.py:69`](../../nowing_backend/app/routes/alert_rules_routes.py#L69)
- Migrate 8 projects endpoints sang RequirePermission
  [`projects_routes.py:96`](../../nowing_backend/app/routes/projects_routes.py#L96)
- Migrate 7 modular skills endpoints sang RequirePermission
  [`skills_routes.py:43`](../../nowing_backend/app/routes/skills_routes.py#L43)
- Migrate 7 memory browser endpoints sang RequirePermission
  [`memory_browser_routes.py:62`](../../nowing_backend/app/routes/memory_browser_routes.py#L62)
- Migrate 5 workspace tables endpoints sang RequirePermission
  [`workspace_tables_routes.py:36`](../../nowing_backend/app/routes/workspace_tables_routes.py#L36)

**Test mock patch target alignment**
- Update patch targets sang app.dependencies.auth.check_permission
  [`test_projects_routes.py:113`](../../nowing_backend/tests/unit/routes/test_projects_routes.py#L113)
  [`test_skills_routes.py:94`](../../nowing_backend/tests/unit/routes/test_skills_routes.py#L94)
  [`test_workspace_tables_routes.py:137`](../../nowing_backend/tests/unit/routes/test_workspace_tables_routes.py#L137)

