---
title: 'PAT-scope sweep: enrichment / scoring / clipper / outbound routes'
type: 'story'
created: '2026-11-17'
status: 'done'
baseline_revision: '42936c2a209112dd0f149eb8630882034e3f1029'
context: []
review_loop_iteration: 1
followup_review_recommended: false
warnings: ['multiple-goals']
deferred: []
---

# PAT-scope sweep: enrichment / scoring / clipper / outbound

## Intent Contract

**Goal:** Đóng nốt lỗ hổng PAT scope cho 4 file routes còn lại trong domain leads — mọi endpoint dùng `get_auth_context` + `RequirePermission` đều phải qua seam `RequirePatScope` (cùng pattern batch-ingest 42.1 + sweep 42.9), và nhánh PAT của clipper seam riêng phải tôn trọng `api_access_enabled` gate.

**Decisions:**
- D1 `update_icp_criteria` khai báo `SETTINGS_UPDATE` — settings namespace ngoài convention leads:* → map `leads:write` (ICP criteria là config của lead pipeline, write-level).
- D2 `lead_clipper_routes.py` giữ nguyên seam riêng `_verify_clipper_auth` (scope `leads:clipper:write` — browser-extension token riêng); chỉ vá thiếu sót: nhánh PAT chưa chạy `_enforce_api_access_gate`.
- D3 `generate_zalo_draft` + `dispatch_lead_telegram_alert` khai báo `LEADS_READ` → gắn `leads:read` theo đúng perm khai báo (asymmetry scope-vs-cost đã defer ở 42.9 — convention mới cần spec riêng, không đổi ngầm ở đây).
- D4 Outbound zalo-connection endpoints (`get/upsert/delete_workspace_zalo_connection`, perm `SETTINGS_*`) → **skip**, không gắn seam — PAT scope cho settings namespace là concern khác, ngoài convention leads:*.

**Always:**
- Mọi `RequirePermission(...)` endpoint trong `enrichment_routes.py`, `lead_scoring_routes.py`, `outbound_routes.py` (trừ phần skip D4 + webhook) có `_pat_scope: None = Depends(RequirePatScope(<scope>))` đặt SAU dep permission hiện có.
- Scope map đúng perm khai báo: `LEADS_ENRICH→leads:enrich`, `LEADS_SCORE→leads:score`, `LEADS_READ→leads:read`, `LEADS_WRITE→leads:write`; `SETTINGS_UPDATE→leads:write` (D1).
- Nhánh PAT của `_verify_clipper_auth` gọi `_enforce_api_access_gate` trước scope check → PAT trên `api_access_enabled=False` workspace nhận 403 gate message.
- Test sweep mới: mỗi endpoint mới pin ≥1 case PAT sai scope → 403 `"permission missing: {scope}"` (parametrize), + case clipper-PAT trên api-disabled ws → 403 chứa `"api-access"`.
- `_pat_scope` sau permission dep trong signature (FastAPI resolve theo thứ tự) — giữ session behavior y nguyên.

**Never:**
- Không sửa `RequirePatScope`/`enforce_pat_scope`/`_enforce_api_access_gate` implementation.
- Không namespace scope mới ngoài `leads:*` hiện có (clipper `leads:clipper:write` đã tồn tại — không đổi).
- Không đổi `_verify_clipper_auth` session branch, shape lỗi, hoặc `CLIPPER_REQUIRED_SCOPE`.
- Không gắn seam cho `zalo_inbound_webhook` (webhook không qua auth dep).
- Không đổi session-path behavior; không migration, không MCP code, không docs ngoài spec.

## Code Map

- `nowing_backend/app/routes/enrichment_routes.py` — `enrich_leads_bulk` POST :82 (LEADS_ENRICH), `enrich_cost` GET :123 (LEADS_ENRICH), `enrich_lead` POST :151 (LEADS_ENRICH), `list_verified_contacts` GET :200 (`_require_lead_read` → `leads:read`), `list_enrichment_requests` GET :230 (`_require_lead_read` → `leads:read`).
- `nowing_backend/app/routes/lead_scoring_routes.py` — `score_leads` POST :45 (LEADS_SCORE), `list_lead_scores` GET :90 (LEADS_READ), `get_latest_lead_score` GET :137 (LEADS_READ), `get_lead_score_history` GET :175 (LEADS_READ), `update_icp_criteria` PUT :209 (SETTINGS_UPDATE → D1 `leads:write`).
- `nowing_backend/app/routes/lead_clipper_routes.py` — `_verify_clipper_auth` :158-198: PAT branch check `leads:clipper:write` + workspace binding NHƯNG không `_enforce_api_access_gate` → thêm `await _enforce_api_access_gate(session, auth, workspace_id)` trong PAT branch (trước scope check); `clip_lead` :345 (session LEADS_WRITE), `get_zalo_copilot_context` :495 (session LEADS_READ — seam đã có, chỉ gate fix).
- `nowing_backend/app/routes/outbound_routes.py` — `generate_zalo_draft` POST :184 (LEADS_READ → `leads:read`), `send_zns_message` POST :262 (LEADS_WRITE → `leads:write`), `dispatch_lead_telegram_alert` POST :567 (LEADS_READ → `leads:read`); SKIP `get/upsert/delete_workspace_zalo_connection` :404,:439,:527 (D4) và `zalo_inbound_webhook` :614.
- Seam/precedent: `RequirePatScope` `nowing_backend/app/dependencies/auth.py`; `enforce_pat_scope` + `_enforce_api_access_gate` `nowing_backend/app/utils/rbac.py:182-213,:124-130`; test pattern `nowing_backend/tests/unit/routes/test_pat_scope_sweep.py` (fake-auth `_build_client`, parametrize wrong-scope).
- `CLIPPER_REQUIRED_SCOPE = "leads:clipper:write"` `lead_clipper_routes.py:51`; `Permission.LEADS_SCORE = "leads:score"` `app/db/enums.py:395`.

## Tasks & Acceptance

**Execution**
- [ ] T1 `enrichment_routes.py`: `_pat_scope` cho 5 endpoint theo map (`leads:enrich`×3, `leads:read`×2). `list_verified_contacts`/`list_enrichment_requests` seam đặt sau `_require_lead_read` dep nếu có, hoặc sau `get_auth_context` — giữ helper nguyên vẹn.
- [ ] T2 `lead_scoring_routes.py`: `_pat_scope` cho 5 endpoint (`leads:score`, `leads:read`×3, `leads:write` cho `update_icp_criteria`).
- [ ] T3 `lead_clipper_routes.py`: thêm `await _enforce_api_access_gate(session, auth, workspace_id)` trong PAT branch `_verify_clipper_auth` (sau expired check, trước scope check); import từ `app.utils.rbac`.
- [ ] T4 `outbound_routes.py`: `_pat_scope` cho 3 endpoint (`leads:read`×2, `leads:write`×1).
- [ ] T5 Tests: thêm cases vào `tests/unit/routes/test_pat_scope_sweep.py` — parametrize wrong-scope → 403 `permission missing` cho ≥8 endpoint mới (đủ mỗi scope: enrich, score, read trên 3 file, write trên 2 file, icp_criteria); `test_clipper_pat_respects_api_access_gate` (PAT `leads:clipper:write` + ws `api_access_enabled=False` → 403 chứa `"api-access"`); `test_clipper_session_unchanged`.

**Acceptance**
- [ ] AC1 PAT `scopes=["leads:write"]` gọi `POST /workspaces/{id}/leads/enrich` → 403 `"permission missing: leads:enrich"`; `scopes=[]` legacy cũng 403 (fail-closed).
- [ ] AC2 PAT `scopes=["leads:read"]` gọi `GET .../enrich-cost`, `GET .../verified-contacts`, scoring reads → 200; gọi `PUT .../icp-criteria`, `POST .../score`, outbound sends → 403.
- [ ] AC3 PAT `scopes=["leads:clipper:write"]` trên `api_access_enabled=False` workspace gọi `clip_lead` → 403 chứa `"api-access"` (trước: qua được).
- [ ] AC4 PAT bound workspace khác gọi bất kỳ endpoint nào mới gắn → 403 `"workspace_id outside pat scope"`.
- [ ] AC5 Session auth mọi endpoint: hành vi y nguyên (đi qua `check_permission`/`_verify_clipper_auth` session branch như cũ).
- [ ] AC6 `pytest tests/unit/routes -x -q` xanh; sweep file xanh; không test cũ gãy.

## Spec Change Log

| Ngày | Loại | Thay đổi |
|---|---|---|
| 2026-11-17 | tạo | Spec từ deferred-work sau review 42.9 (decision: narrow 42.9 → sweep nốt đây). |

## Review Triage Log

### 2026-11-17 — Review pass 1 (coordinator self-review + 1 verification-gap agent layer)

- Diff: 7 files, +395/−8 — 4 route files (seam additions ~36 dòng), `test_pat_scope_sweep.py` (+245), `test_zalo_copilot_context.py` (+38), spec.
- Review depth: 1 layer (verification-gap, opus) — diff cơ học nhỏ, convention đã chốt ở 42.9.
- Kết quả: **0 high / 1 medium / 1 low / 0 false** — cả 2 đã vá trong vòng này.

| Finding | Verdict | Xử lý |
|---|---|---|
| [medium] `test_lead_clipper_ingest.py` integration gãy: fixture `clipper_client` workspace `api_access_enabled=False` (server default) → 2 test success fail `403 != 200`, và `test_..._rejected_without_clipper_scope` pass **sai lý do** (gate bắn trước scope check → 403 không phải vì thiếu scope) | **patched** | `api_access_enabled=True` trong fixture — giờ cả 3 đi qua gate, scope check được verify thật |
| [low] Gate đặt trước workspace-binding check → PAT bound ws khác nhận verdict api-access của ws target (lộ flag) thay vì `"not authorized"` — lệch convention binding-first của `enforce_pat_scope` | **patched** | Đảo thứ tự: validity → binding → gate → scope trong `_verify_clipper_auth` PAT branch |
| Phát hiện ngoài diff (census): `dnc_routes.py` + `lead_pipeline_routes.py` chưa seam — cùng vuln class | **deferred** | ghi deferred-work (spec 42-11 candidate); ngoài enumeration spec này |

`followup_review_recommended: false`

## Auto Run Result

- **Implement:** implementer agent (sonnet) — T1 enrichment (3×enrich + 2×read), T2 scoring (score + 3×read + icp→write D1), T3 clipper gate fix, T4 outbound (draft→read, zns→write, telegram→read) skip settings (D4), T5 tests. Test `test_zalo_copilot_context.py` update `_FakeSession` (PAT branch giờ cần session cho gate).
- **Review:** 2 findings vá tại chỗ (xem Triage Log).
- **Verification (independent re-run):** sweep 32 → **35 passed** (thêm 3 clipper integration), `tests/integration/test_pat_fail_closed_authz.py` 7 passed, `tests/integration/routes/test_lead_clipper_ingest.py` 3 passed.

## Design Notes

- Review 42.9 claim "clipper routes chưa check PAT" **một phần sai**: seam `_verify_clipper_auth` đã check `leads:clipper:write` + workspace binding cho PAT — chỉ thiếu api-access gate (nhánh PAT bypass `_enforce_api_access_gate`, session path đi qua `check_permission` → gate sẵn).
- Endpoints qua `check_permission`/`check_workspace_access`/`_require_lead_read` → api-access gate đã chạy sẵn (gate nằm trong cả 3); chỉ các inline-check trực tiếp `get_user_permissions` (kiểu `resolve_phone` 42.9) mới bypass.
- D4 skip settings endpoints: PAT với `scopes=["settings:update"]` hiện chưa là use-case; nếu sau này cần → spec convention namespace riêng.

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_pat_scope_sweep.py -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/integration/test_pat_fail_closed_authz.py -x -q
```
