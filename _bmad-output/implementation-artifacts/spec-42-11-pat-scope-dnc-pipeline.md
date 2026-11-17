---
title: Spec 42.11 — PAT scope sweep nốt DNC + Lead Pipeline routes
type: story
created: '2026-11-17'
status: 'done'
review_loop_iteration: 0
warnings: ['mechanical-sweep']
deferred: []
baseline_revision: 'eeafb7d64ce35af2b054eacfba5dbaef9b61e80c'
context: []
---

## Intent Contract

### Goal

Khép vuln class PAT-scope trên domain `leads:*`: thêm seam `_pat_scope: None = Depends(RequirePatScope(<scope>))` **SAU** dep permission hiện hữu cho mọi endpoint trong `app/routes/dnc_routes.py` (4 endpoints) và `app/routes/lead_pipeline_routes.py` (12 endpoints). Đây là 2 file cuối trong census deferred sau spec 42-10.

### Always

- Scope theo convention spec 42-9/42-10: perm/behavior của endpoint → scope `leads:*` tương ứng.
  - `dnc_routes.py`: `list_dnc_records` (`app/routes/dnc_routes.py:201`, perm `LEADS_READ`) → `leads:read`; `create_dnc_record` (`:260`), `delete_dnc_record` (`:290`), `import_dnc_csv` (`:328`) (perm `LEADS_WRITE`) → `leads:write`.
  - `lead_pipeline_routes.py` (tất cả dep `RequireWorkspaceAccess()` — membership + api-access gate chạy sẵn, KHÔNG có gate bypass):
    - `leads:read`: `list_pipeline_stages` GET `/pipeline/stages` (`:167`), `list_lead_activities` GET `/{lead_id}/timeline` + GET `/{lead_id}/activities` (một hàm, hai route decorators `:343-352`), `get_my_spend_status` GET `/members/spend-status` (`:515`), `list_meeting_slots` GET `/{lead_id}/meeting/slots` (`:623`).
    - `leads:write`: `create_pipeline_stage` POST `/pipeline/stages` (`:184`), `transition_lead_stage` PATCH `/{lead_id}/stage` (`:232`), `create_lead_activity` POST `/{lead_id}/activities` (`:376`), `assign_or_reassign_lead` POST `/{lead_id}/assign` (`:408`), `assign_leads_batch` POST `/assign-batch` (`:452`), `update_member_spend_cap` PATCH `/members/{target_user_id}/spend-cap` (`:551`), `update_member_lead_capacity` PATCH `/members/{target_user_id}/lead-capacity` (`:585`), `book_meeting_for_lead` POST `/{lead_id}/meeting/book` (`:676`).
- `RequirePatScope` import từ `app.dependencies.auth` — cùng pattern 42.9/42.10 (`_pat_scope: None = Depends(RequirePatScope(Permission.<X>.value))`), comment `# PAT scope seam (spec 42-11)`.
- Sai-scope → 403 `"permission missing: {scope}"`; PAT bound workspace khác → 403 `"workspace_id outside pat scope"` (binding-first đã trong `enforce_pat_scope`); `scopes=[]` legacy fail-closed.
- Session auth mọi endpoint: hành vi y nguyên — seam là no-op (`enforce_pat_scope` early-return khi `not auth.is_gated`).

### Never

- KHÔNG sửa `RequirePatScope` / `enforce_pat_scope` / `_enforce_api_access_gate` / `check_workspace_access` implementation.
- KHÔNG đổi `_can_view_all_leads` / `_lead_visibility_filter` / `_require_lead_visible` — role-perm check trên membership là row-visibility logic (RBAC), không phải PAT-scope bug. **Correction** so với ghi chú deferred trước: pipeline routes không bypass api-access gate (`RequireWorkspaceAccess` → `check_workspace_access` → gate đã chạy); gap duy nhất là PAT scope unchecked.
- KHÔNG tạo namespace scope mới ngoài `leads:*` — spend-cap/lead-capacity/meeting-book là lead-ops management, map vào `leads:write` (D1).
- KHÔNG thêm `RequirePatScope` vào file nào ngoài 2 file này (~80 file khác ngoài domain leads — ngoài scope).
- KHÔNG migration, KHÔNG đổi response model/schema.

### Decisions

- **D1** `update_member_spend_cap` + `update_member_lead_capacity` (PATCH `members/{uid}/spend-cap|lead-capacity`) → `leads:write`: quản lý phân bổ lead-ops, thuộc domain leads; không tạo scope `members:*` riêng.
- **D2** `list_pipeline_stages` GET nhưng có side-effect `_ensure_default_stages` (auto-seed lần đầu): giữ `leads:read` — semantic read; auto-seed là idempotent bootstrap, không phải hành vi caller-initiated.
- **D3** `book_lead_meeting` → `leads:write` (tạo booking = mutation), `get_meeting_slots` → `leads:read`.

## Code Map

- Seam: `RequirePatScope` — `app/dependencies/auth.py`; logic `enforce_pat_scope` — `app/utils/rbac.py:182-213` (binding trước scope, `"permission missing: {scope}"`).
- `app/routes/dnc_routes.py`: 4 endpoints, tất cả `RequirePermission` — thêm `_pat_scope` sau `_membership` dep (pattern giống `lead_batch_routes.py:138`).
- `app/routes/lead_pipeline_routes.py`: 12 endpoints, tất cả `RequireWorkspaceAccess()` — thêm `_pat_scope` sau `membership` dep.
- Tests: `tests/unit/routes/test_pat_scope_sweep.py` — thêm parametrize vào `test_sweep_42_10_wrong_scope_403`-style case list hoặc block riêng `test_sweep_42_11_wrong_scope_403`; `_build_router_client` reuse sẵn.

## Tasks & Acceptance

### Tasks

- [ ] T1 `dnc_routes.py`: thêm `RequirePatScope` import + 4 seam (`list→leads:read`, create/delete/import→`leads:write`).
- [ ] T2 `lead_pipeline_routes.py`: thêm `RequirePatScope` import + 12 seam theo bảng Always.
- [ ] T3 Tests `test_pat_scope_sweep.py`: parametrize wrong-scope 403 cho ~10 endpoint representative (pin đúng `"permission missing: {required_scope}"`), ≥1 case sai-workspace 403, session-unchanged đã cover sẵn.

### Acceptance

- [ ] AC1 PAT `scopes=["leads:read"]` gọi `POST /workspaces/{id}/dnc` → 403 `"permission missing: leads:write"`; `GET /workspaces/{id}/dnc` → 200.
- [ ] AC2 PAT `scopes=["leads:read"]` gọi `POST /workspaces/{id}/pipeline/stages` hoặc `PATCH .../stage` → 403 `"permission missing: leads:write"`; `GET /pipeline/stages` → 200.
- [ ] AC3 PAT bound workspace khác → 403 `"workspace_id outside pat scope"` trên cả 2 file.
- [ ] AC4 `scopes=[]` legacy PAT → 403 fail-closed mọi endpoint mới seam.
- [ ] AC5 Session auth → hành vi y nguyên (seam no-op).
- [ ] AC6 `pytest tests/unit/routes -x -q` xanh; không test cũ gãy.

## Spec Change Log

| Ngày | Loại | Thay đổi |
|---|---|---|
| 2026-11-17 | tạo | Spec từ deferred-work spec-42-10 census (dnc + pipeline = 2 file cuối domain leads). |

## Review Triage Log

### 2026-11-17 — Coordinator self-review (proportional, mechanical sweep)

- **Kết quả:** 0 high / 0 medium / 0 low — diff thuần additive seam, mọi endpoint đúng scope map.
- Verify độc lập: sweep tests **45/45**, routes regression **384/384** xanh; 11 case wrong-scope + 2 case wrong-workspace pin đúng `"permission missing: {scope}"` / `"workspace_id outside pat scope"`.
- Lưu ý: `list_meeting_slots` đặt `_pat_scope` trước param `redis_client` — hợp lệ (deps theo tên, không theo thứ tự).
- `followup_review_recommended: false` — pattern giống hệt 42-9/42-10 đã qua review sâu 2 lần; không có surface mới.

## Auto Run Result

- T1 `dnc_routes.py`: +4 seam (`list→leads:read`, create/delete/import→`leads:write`).
- T2 `lead_pipeline_routes.py`: +12 seam (4 read → `leads:read`, 8 mutation → `leads:write`; D1/D2/D3 đúng spec).
- T3 `test_pat_scope_sweep.py`: `test_sweep_42_11_wrong_scope_403` 11 case parametrized + `test_sweep_42_11_wrong_workspace_403` 2 case.
- Domain `leads:*` giờ đóng hoàn toàn: mọi endpoint leads đều qua `RequirePatScope` hoặc seam riêng (clipper).

## Design Notes

- Census đầy đủ (~80 file `get_auth_context` không seam) ở deferred-work 42-10 — phần còn lại ngoài domain `leads:*` (settings, connectors, admin...) chờ convention PAT namespace rộng hơn, không thuộc bundle này.
- Sau spec này domain leads đóng hoàn toàn: mọi endpoint leads đều qua `RequirePatScope` hoặc seam riêng (clipper `leads:clipper:write`).

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_pat_scope_sweep.py -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes -x -q
```
