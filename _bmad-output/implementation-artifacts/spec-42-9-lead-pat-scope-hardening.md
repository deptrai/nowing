---
title: 'Epic 42 follow-up — PAT scope cho read/write endpoints còn lại + api-access discoverability + MCP error convention'
type: 'story'
created: '2026-11-17'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
warnings:
  - 'followup-bundle'
baseline_revision: '5d0851b0a7a1a7ab24e064101516b6a10da08038'
context: []
deferred: []
---

# Intent Contract

## Goal

Đóng các lỗ hổng PAT-scope mà Epic 42 (story 42.1 + 42.4) phát hiện nhưng chưa vá, trên nhóm endpoint được liệt kê tại Always/Code Map (`lead_batch_routes.py`, `leads_routes.py`, `workspaces/core.py`): mỗi endpoint nhận `get_auth_context` + `RequirePermission`/`RequireWorkspaceAccess` phải đi qua seam `RequirePatScope` giống batch-ingest — PAT bound workspace khác hoặc thiếu scope → 403. Kèm: 403 `api_access_enabled` phải nói rõ cách bật; tài liệu hóa MCP error convention; dev-setup note cho `patchright install`. (Goal thu hẹp theo enumeration sau review 2026-11-17 — sweep nốt `enrichment_routes`/`lead_scoring_routes`/`lead_clipper_routes`/`outbound_routes` chuyển spec 42-10, xem deferred-work.)

## Always

- `RequirePatScope(scope)` reuse seam hiện có (`app/dependencies/auth.py`) — scope dùng **đúng `Permission.*` value endpoint đang khai báo** (mechanical, không sáng tạo scope mới).
- `unlock_contact`, `relock_contact`, `pii_opt_out` → `RequirePatScope(LEADS_WRITE)`; `list_workspace_leads`, `get_lead`, `get_company_graph` → `RequirePatScope(LEADS_READ)`; `update_lead_status`, `reverse_icp`, `resolve_lead_phone`, `report_invalid_phone`, `phone_verification_result` → scope theo perm hiện khai báo; `GET /credits/balance` → `RequirePatScope(LEADS_READ)` (balance là lead-ops read — không mở namespace mới).
- `RequirePatScope` đặt SAU `RequirePermission`/`RequireWorkspaceAccess` trong signature — FastAPI resolve theo thứ tự, membership check chạy trước (giữ đúng pattern batch-ingest).
- `_enforce_api_access_gate` (`app/utils/rbac.py`) detail 403 bổ sung hướng dẫn bật: `"API access is not enabled for this workspace. Enable via PUT /api/v1/workspaces/{workspace_id}/api-access (requires API_ACCESS_MANAGE, session auth)."`.
- Session/system auth path không đổi hành vi (RequirePatScope là pass-through cho non-PAT).

## Never

- KHÔNG sửa `RequirePatScope`/`enforce_pat_scope` implementation — chỉ gắn dependency.
- KHÔNG thêm scope namespace mới (`workspace:read`, `credits:read`...) — dùng `leads:read`/`leads:write` có sẵn.
- KHÔNG đổi `PUT /workspaces/{id}/api-access` route hay `GET /workspaces` PAT filter (silent filter là cố ý — discoverability fix nằm ở 403 message).
- KHÔNG refactor MCP tools khác ngoài convention doc — chỉ document + align module `features/leads` nếu lệch.
- KHÔNG đụng `medirus_proxy.py`, `MedirusMcpClient`, migration nào.

## Decisions

- D1: Credits balance scope = `leads:read`. Lý do: external agent dùng `nowing_get_credits_balance` là lead-ops agent; namespace mới cho 1 endpoint là over-engineering. Document trong test.
- D2: MCP convention — **domain-level failure → trả `{status:'failed', reason}` JSON** (như `no_wallet`); **transport/API failure → raise `ToolError`** với structured passthrough (như 422 batch-ingest). Ghi vào `nowing_mcp/README.md` (hoặc docstring `features/leads/tools.py` nếu README không có section phù hợp) — không refactor tool khác.
- D3: `patchright` — thêm note `patchright install chromium` vào dev setup doc canonical (tìm file: `nowing_backend/README*` hoặc `docs/`); không thêm runtime hint logic.

## I/O Matrix

| Case | Input | Expect |
|---|---|---|
| READ_OK | PAT `leads:read`, `GET /leads` | 200 + leads |
| READ_NO_SCOPE | PAT `leads:write` only, `GET /leads` | 403 `"permission missing: leads:read"` |
| WRITE_OK | PAT `leads:write`, `POST /leads/{id}/unlock-contact` | 200 |
| WRITE_NO_SCOPE | PAT `leads:read` only, unlock | 403 `"permission missing: leads:write"` |
| PAT_WRONG_WS | PAT bound ws-A, call path ws-B | 403 `"workspace_id outside pat scope"` |
| BALANCE_PAT | PAT `leads:read`, `GET /credits/balance` | 200 `{workspace_id, credit_micros_balance}` |
| GATE_MESSAGE | PAT trên ws `api_access_enabled=false` | 403 detail chứa `"api-access"` hint |
| SESSION_UNCHANGED | session auth, toàn bộ endpoints | hành vi cũ |

# Code Map

- `app/dependencies/auth.py` — `RequirePatScope` (seam 42.1, đã có).
- `app/routes/lead_batch_routes.py:230,299,414` — `unlock_contact` / `relock_contact` / `pii_opt_out`, đều `RequirePermission(LEADS_WRITE)` — thêm `_pat_scope` dep.
- `app/routes/leads_routes.py` — `list_workspace_leads` :252 (LEADS_READ), `reverse_icp_endpoint` :373, `get_lead` :447, `update_lead_status` :471, `get_company_graph` :501, `resolve_lead_phone_endpoint` :704, `report_invalid_phone_endpoint` :799, `phone_verification_result_endpoint` :839 — thêm `_pat_scope` dep theo perm hiện khai báo của từng endpoint.
- `app/routes/workspaces/core.py:260` — `get_credits_balance` (`RequireWorkspaceAccess`) → thêm `RequirePatScope(LEADS_READ)` + `:430` `update_workspace_api_access` (đã tồn tại — KHÔNG đụng, chỉ reference trong 403 message).
- `app/utils/rbac.py` — `_enforce_api_access_gate` 403 detail.
- `nowing_mcp/README.md` hoặc `nowing_mcp/mcp_server/features/leads/tools.py` docstring — convention D2.
- Dev setup doc — patchright note D3.
- Tests mới/mở rộng: `tests/unit/routes/test_lead_batch_ingest.py` (hoặc file mới `test_pat_scope_sweep.py`) + `tests/unit/routes/test_workspace_credits.py`.

# Tasks & Acceptance

## T1 — RequirePatScope sweep `lead_batch_routes.py`

- Add `_pat_scope: None = Depends(RequirePatScope(Permission.LEADS_WRITE.value))` sau `_membership` vào `unlock_contact`, `relock_contact`, `pii_opt_out` — mirror đúng pattern `batch_ingest_leads` :138.
- AC: PAT `leads:write` ws-bound OK; PAT `leads:read`-only → 403 `"permission missing"`; PAT ws khác → 403 outside-scope; session không đổi.

## T2 — RequirePatScope sweep `leads_routes.py` + `core.py` balance

- Mỗi endpoint thêm dep với scope = `Permission.*` endpoint đang khai báo (LEADS_READ cho read, perm tương ứng cho write/mutation).
- `get_credits_balance`: `RequirePatScope(LEADS_READ)` sau `RequireWorkspaceAccess` (D1).
- AC: matrix READ_OK/READ_NO_SCOPE/PAT_WRONG_WS/BALANCE_PAT xanh.

## T3 — api-access gate discoverability

- `_enforce_api_access_gate` detail → nối thêm câu hướng dẫn bật (Always §).
- AC: `GATE_MESSAGE` assert substring `"api-access"` trong 403 detail.

## T4 — MCP error convention doc

- 1 đoạn convention D2 trong `nowing_mcp/README.md` (hoặc docstring module leads nếu README thiếu section) + audit `features/leads/tools.py` — nếu tool nào lệch convention thì align.
- AC: doc tồn tại; leads module consistent (422→ToolError passthrough, no_wallet→JSON đã đúng).

## T5 — patchright dev-setup note

- Thêm `patchright install chromium` vào dev setup doc canonical (D3).
- AC: doc chứa lệnh.

## T6 — Tests

- `test_pat_scope_sweep.py` (hoặc extend `test_lead_batch_ingest.py`): ít nhất 1 test/row matrix T1–T3 (reuse fake-auth pattern có sẵn).
- AC: spec `## Verification` green; regression `tests/unit/routes` green.

# Spec Change Log

_(chưa có)_

# Review Triage Log

## 2026-11-17 — Coordinator self-review (small mechanical bundle)

- Quét toàn diff 7 file + test file mới; routes regression 347/347 xanh; sweep tests 8/8.
- [low → accepted decision] `resolve_lead_phone_endpoint` gắn `LEADS_ENRICH` (implementer chọn). Old inline perm check là `has_enrich or has_write` → PAT có duy nhất `leads:write` trước đây qua được, giờ 403. Tightening CỐ Ý: phone resolution là billing waterfall, đúng scope là enrich; session user không đổi; legacy PAT `scopes=[]` vốn fail-closed. Ghi nhận để biết khi có complaint.
- [reject] `phone_verification_result_endpoint` không gắn seam — đã bị `require_superuser` chặn PAT trước đó, seam là dead code. Đúng.
- [reject] Chỉ `list_workspace_leads` có test row trong sweep — các endpoint khác dùng cùng seam pattern, coverage đủ cho mechanical change.
- Verdict: 0 high / 0 medium / 0 action pending. `followup_review_recommended: false`.

## 2026-11-17 — bmad-code-review (4 layers: blind + edge-case + verification-gap + acceptance)

Sau dedup ~20 findings → 1 decision-needed / 5 patch / 0 defer / 4 reject-false. Regression ngoài diff phát hiện thêm 1 test hỏng — đã vá ngay (`test_pat_fail_closed_authz.py` exact-match detail → `startswith`, 7/7 xanh lại).

- [decision_needed] **Sweep còn thiếu 3 file routes**: `enrichment_routes.py` (enrich_leads_bulk :80, enrich_cost :121, enrich_lead :149, list_verified_contacts :197, list_enrichment_requests :227), `lead_scoring_routes.py` (5 endpoints gồm `score_leads` perm `LEADS_SCORE`), `lead_clipper_routes.py` (`clip_lead` :341, `get_zalo_copilot_context` :486) — thêm `outbound_routes.py` (`zalo-draft` :173, `zns-send` :251, `telegram-alert` :556). Tất cả `get_auth_context` + perm nhưng không `_pat_scope` → PAT scopes bất kỳ (kể cả `[]` + `api_access_enabled=True`) gọi được endpoint **tốn credit** — đúng class lỗ hổng spec vá. Goal "mọi endpoint lead/credits" overbroad so với Always enumeration. → Cần user chọn: sweep nốt (spec mới/extend) hay narrow Goal + defer.
- [patch] **`resolve_lead_phone` bypass api-access gate**: `leads_routes.py:715` chỉ `get_auth_context` + `_pat_scope` + inline `get_user_permissions` (không qua `check_permission` → `_enforce_api_access_gate` không chạy) → PAT trên workspace `api_access_enabled=False` vẫn gọi được billing waterfall 1.5 credits. Pre-existing nhưng diff đụng đúng dòng auth của nó. Fix: `await _enforce_api_access_gate(session, auth, workspace_id)` sau block perms (session unaffected — gate chỉ fire khi `is_gated`). Kèm fix ordering finding (PAT scope chạy trước membership — endpoint không có membership dep; gate call đặt sau perms check giữ đúng thứ tự verdict).
- [patch] **Pin scope cho 8 site chưa test**: `relock_contact`, `pii_opt_out`, `reverse_icp`, `get_lead`, `update_lead_status`, `get_company_graph`, `resolve_phone` (assert PAT `leads:write` → 403 `permission missing: leads:enrich`), `report_invalid_phone` — parametrize no-scope rows (~8 dòng), hiện sai-wiring sẽ ship green.
- [patch] **f-string `{workspace_id}` trong gate message**: `rbac.py:124` là plain string → in ra nguyên placeholder. Đổi thành f-string với `workspace.id` (vẫn giữ substring `api-access` theo AC).
- [patch] **README MCP ví dụ sai**: `nowing_mcp/README.md:130` liệt kê "insufficient credits" là domain-level failed-JSON — thực tế 402 nằm trong `_FAILURE_HINTS` → raise `ToolError` (client.py:167-172). Chỉ `no_wallet` là domain-JSON. Sửa ví dụ.
- [patch] **README patchright fragile**: `patchright` chỉ là transitive dep (`scrapling[fetchers]`) — đổi lệnh thành `uv run --with patchright patchright install chromium` cho robust.
- [reject] PAT-vs-session asymmetry `resolve_phone` (session: enrich OR write; PAT: enrich-only) — cố ý, đã ghi decision; [reject] test cruft (limiter/dead param/helper dup) — cosmetic, tests xanh; [false] "422 payload mất rejected_indexes" — ToolError message embed đủ JSON text (`Nowing returned 422: {...}`); [reject] `BALANCE_PAT` mock bypass gate — cố ý isolate scope logic, gate đã được cover bởi `GATE_MESSAGE` + integration test.
- [defer ghi vào deferred-work.md]: `reverse_icp` dùng `leads:read` cho endpoint chạy LLM (asymmetry với enrich/write — semantics cần chuẩn hoá scope-to-cost ở spec sau).

# Design Notes

### Review Findings

- [x] [Review][Decision] **Sweep nốt 3 file routes hay narrow Goal?** — `enrichment_routes.py` / `lead_scoring_routes.py` / `lead_clipper_routes.py` (+ `outbound_routes.py`) cùng class lỗ hổng PAT chưa gắn seam; Goal spec overbroad so với Always list. Chọn: (1) sweep nốt vào bundle này — +~15 endpoint + tests, hoặc (2) narrow Goal về đúng enumeration, viết spec tiếp theo (42.10) cho phần còn lại. → **RESOLVED 2026-11-17: user chọn (2) narrow Goal + defer 42-10** (goal đã sửa, deferred-work.md đã ghi).
- [x] [Review][Patch] `resolve_lead_phone` bypass api-access gate [nowing_backend/app/routes/leads_routes.py:715] — áp: `_enforce_api_access_gate` sau inline perms check + import; test `test_resolve_phone_pat_respects_api_access_gate`.
- [x] [Review][Patch] Pin no-scope tests cho 8 endpoint còn lại [nowing_backend/tests/unit/routes/test_pat_scope_sweep.py] — áp: 2 parametrize (6 leads routes + relock/pii) + gate test = +9 test.
- [x] [Review][Patch] f-string `{workspace_id}` trong gate message [nowing_backend/app/utils/rbac.py:124] — áp.
- [x] [Review][Patch] README MCP: ví dụ "insufficient credits" sai (402 → ToolError) [nowing_mcp/README.md:130] — áp.
- [x] [Review][Patch] README patchright: dùng `uv run --with patchright` [nowing_backend/README.md] — áp.
- [x] [Review][Defer] `reverse_icp` gắn `leads:read` nhưng chạy LLM (asymmetry scope-vs-cost) — deferred: cần convention scope-to-cost riêng, không đổi trong bundle này [nowing_backend/app/routes/leads_routes.py:385]

- `GET /workspaces` PAT filter `api_access_enabled` (core.py:146) + `PUT /workspaces/{id}/api-access` (core.py:430, `API_ACCESS_MANAGE`, session-only) **đã tồn tại** — bundle này KHÔNG thêm endpoint, chỉ sửa message.
- `RequirePatScope` fail-closed với `scopes=[]` → legacy PAT đọc leads cũng cần khai báo `leads:read` khi tạo (docs cho Hermes guide đã nêu).
- Deferred tiếp (không làm trong bundle): MCP error contract refactor toàn bộ modules khác; Medirus session-lifecycle audit; MissingWorkspaceId runtime verify (deploy checklist); EXPLAIN AC6 (PR note).

# Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_lead_batch_ingest.py tests/unit/routes/test_workspace_credits.py -x -q
```
