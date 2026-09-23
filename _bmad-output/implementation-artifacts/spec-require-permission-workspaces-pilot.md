---
title: RequirePermission migration (workspaces pilot) + NowingError adoption pilot (billing/credits)
status: done
baseline_commit: d86329f5eb2d4c56c2e432fb6c84bdbe0edbd090
review_loop_iteration: 0
date: 2026-09-12
context:
  - nowing_backend/app/dependencies/auth.py
  - nowing_backend/app/utils/rbac.py
  - nowing_backend/app/exceptions.py
  - nowing_backend/app/routes/workspaces/
  - nowing_backend/app/services/billing_service.py
  - nowing_backend/app/services/billing_event_service.py
  - nowing_backend/app/services/wallet_credit.py
  - nowing_backend/app/services/manual_credit_service.py
---

## Problem / Intent

Hai tech-debt re-deferred trong `deferred-work.md` với ghi chú "làm sau oversized split đợt 2" — split đợt 2 đã xong (commit d86329f5e). Pilot xử lý cả hai trên phạm vi P0 nhỏ nhất:

1. **RequirePermission migration**: ~268 call-sites `await check_permission(...)` thủ công trên ~70 route files. `RequirePermission`/`RequireWorkspaceAccess` đã tồn tại ở `app/dependencies/auth.py` nhưng chưa adopt. Pilot migrate toàn bộ `app/routes/workspaces/` (20 call-sites, 4 files).
2. **NowingError adoption**: ~1.800 `except Exception` toàn app vs 49 raise NowingError/16 files. Pilot refactor 6 `except Exception` trong billing/credits services — narrow sang typed exceptions (`RedisError`, `SQLAlchemyError`) hoặc NowingError subclass, giữ nguyên behaviour.

Mục tiêu: chứng minh pattern + đo effort để nhân rộng, KHÔNG migrate toàn app.

## Code Map

### RequirePermission migration (workspaces)

- `app/dependencies/auth.py` — `RequirePermission(permission, message)` + `RequireWorkspaceAccess` đã có. Resolve `workspace_id` từ path param, inject `session`+`auth` qua Depends, trả `WorkspaceMembership`. **Reuse trực tiếp, không sửa.**
- `app/utils/rbac.py:129` — `check_permission(...)`; `check_workspace_access` ~L165.
- `app/routes/workspaces/core.py`: L275, L437, L481 `check_permission`; L238 `check_workspace_access` → `RequireWorkspaceAccess`. L80 `require_session_context` + L127 `allow_any_principal` KHÔNG gọi check_permission → giữ nguyên.
- `app/routes/workspaces/settings.py`: L51, L110, L234, L297 (4×).
- `app/routes/workspaces/subscriptions.py`: L48, L131, L172, L207, L247 (5×).
- `app/routes/workspaces/bulk_ops.py`: L46+L53, L92+L99, L143, L169, L195 (7×). Hai cặp đầu cần 2 permissions mỗi endpoint.

**Pattern**: thay `await check_permission(session, auth, workspace_id, P.value, "msg")` bằng thêm param `_membership: WorkspaceMembership = Depends(RequirePermission(P.value, "msg"))` và xoá await. Giữ `session`/`auth` params nếu body còn dùng. Response semantics giữ nguyên vì dependency gọi thẳng `check_permission`. **Multi-permission** (bulk_ops): khai báo 2 Depends riêng — FastAPI resolve cùng `workspace_id`, mỗi cái gọi `check_permission` một lần.

### NowingError pilot (billing/credits)

- `app/exceptions.py` — hierarchy: `NowingError` base (code/message/status), `DatabaseError`, `ExternalServiceError`, `NotFoundError`, `ForbiddenError`, `ValidationError`, `PermissionDeniedError`, `RateLimitError`, `LLMError`, `ExternalAPIError`. Global handler đã map structured envelope.
- `app/services/wallet_credit.py:123` — auto-reload best-effort → narrow `(RedisError, SQLAlchemyError)`, giữ swallow.
- `app/services/billing_service.py:46` Redis init; L192 Redis delete during refund → narrow `(RedisError, OSError)`, giữ log+swallow.
- `app/services/billing_event_service.py:838` — `except Exception` sau `apply_debit` fail → refund member_spend rồi `raise`. Critical path: narrow `(SQLAlchemyError, wallet_credit.InsufficientCreditsError)`, giữ `raise`. InsufficientCreditsError vẫn propagate (re-raised ở L828).
- `app/services/manual_credit_service.py:140,151` — Redis lock acquire/release → narrow `(RedisError,)`, giữ log+fallback.

**Nguyên tắc**: narrow sang lib-specific exceptions cho best-effort paths; chỉ NowingError subclass khi lỗi propagate ra response. Không đổi HTTP status/detail.

## Tasks & Acceptance

- [x] **T1**: Migrate `settings.py` (4 sites) sang `Depends(RequirePermission(...))`. AC: không còn `await check_permission`; xoá import nếu unused; `ruff check` pass.
- [x] **T2**: Migrate `subscriptions.py` (5 sites). AC như T1.
- [x] **T3**: Migrate `core.py` — 3× `check_permission` + 1× `check_workspace_access`→`RequireWorkspaceAccess`. AC như T1; `create_workspace`/`list_workspaces` không đổi.
- [x] **T4**: Migrate `bulk_ops.py` (7 sites, 2 endpoint cần 2 permissions → 2 Depends). AC như T1.
- [x] **T5**: Refactor 6 `except Exception` trong 4 billing/credits files theo Code Map. AC: không còn `except Exception` trần; mỗi site có comment ngắn giải thích; `ruff check` pass.
- [x] **T6**: `pytest tests/unit/ -k workspace` + `pytest tests/unit/ -k billing hoặc credit` pass; integration `tests/integration/workspaces/` nếu có → pass.
- [x] **T7**: Cập nhật `deferred-work.md`: resolve 2 mục với evidence; thêm entry follow-up cho ~248 call-sites + ~1.794 except Exception còn lại.

## Out of Scope

- ~248 `check_permission` call-sites ngoài `workspaces/`; `except Exception` ngoài 4 billing files.
- Đổi permission semantics, roles, thêm permission mới; sửa `RequirePermission`.
- Frontend changes.
