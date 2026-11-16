---
title: 'Story 42.4 — nowing_mcp lead tools: leads.ingest, tables.create, leads.list, credits.balance'
type: 'story-spec'
created: '2026-11-17'
status: 'done'
review_loop_iteration: 1
followup_review_recommended: true
baseline_revision: 'dae4e5f3b3197fc0bb83560df70831812d0480d1'
warnings: ['multiple-goals']
deferred:
  - summary: >-
      GET /workspaces/{id}/credits/balance chỉ RequireWorkspaceAccess — PAT
      bound workspace khác nhưng là member vẫn đọc được balance; read
      endpoints epic-wide chưa có PAT-scope seam (42.1 chỉ áp write path).
    evidence: |-
      blind-hunter F3 + verification-gap A3: check_permission không check
      pat.scopes/workspace binding; RequirePatScope chỉ gắn ở batch-ingest.
      Giống deferred item 42.1 (sibling lead-write endpoints).
    location: nowing_backend/app/routes/workspaces/core.py:~260
    severity: medium
  - summary: >-
      Lỗi backend (403/429/5xx) propagate ToolError text, không trả
      {status:'failed'} JSON — contract lỗi MCP-wide chưa thống nhất.
    evidence: |-
      edge-case EC-10a + intent-alignment: các tool khác cùng convention
      raise ToolError; đổi riêng leads tools tạo inconsistency.
    location: nowing_mcp/mcp_server/features/leads/tools.py
    severity: low
  - summary: >-
      nowing_ingest_leads không cap len(leads) phía MCP — caller gửi được
      batch tuỳ ý size; backend nhận hết.
    evidence: edge-case EC-7; REST route không giới hạn nên đây là quyết định contract rộng hơn.
    location: nowing_mcp/mcp_server/features/leads/tools.py
    severity: low
context: []
---

# Story 42.4 — `nowing_mcp` lead tools

## Intent Contract

**Goal:** expose 4 lead operations hiện có qua `nowing_mcp` để external agent không cần `sys.path.insert` vào `nowing_backend` hay tự POST REST. `nowing_mcp` là thin HTTP client — mọi tool chỉ wrap `NowingClient.request` tới REST endpoint hiện có, auth = PAT của caller (header `Authorization: Bearer nw_pat_…` hoặc env `NOWING_API_KEY`).

**Always:**
- `leads.ingest` → `POST /workspaces/{id}/leads/batch-ingest` (route đã harden ở 42.1: `RequirePatScope('leads:write')`, structured 422, auto-table, `LeadActivityLog` attribution `actor_pat_token_id`/`idempotency_key`). MCP tool forward payload + optional `Idempotency-Key` header — **không** re-implement validation/dedupe phía MCP.
- `tables.create` → `POST /workspaces/{id}/tables` (`WorkspaceTableCreate {name, icon?, filter_preset?, columns_config?}`).
- `leads.list` → `GET /workspaces/{id}/leads` — tool-side clamp `limit = max(1, min(limit or 50, 200))`, `offset = max(0, offset or 0)` (AC literal; server cũng clamp `ge=1,le=200` nhưng tool phải tự clamp).
- `credits.balance` → endpoint mới `GET /workspaces/{id}/credits/balance` (backend chưa expose `Workspace.credit_micros_balance` cho non-admin). Workspace không tồn tại → tool trả `{status:'failed', reason:'no_wallet'}`.
- Mỗi tool ≤ ~40 dòng; registration 1 dòng trong `server.py`; tool names theo convention `nowing_*` (MCP tool name charset không cho `.` — map: `leads.ingest`→`nowing_ingest_leads`, `tables.create`→`nowing_create_leads_table`, `leads.list`→`nowing_list_leads`, `credits.balance`→`nowing_get_credits_balance`).
- Trả structured output dạng JSON string giữ nguyên shape backend (kể cả `status:'failed'` payloads) — caller đọc được `rejected_indexes`/`reason_map` khi 422.

**Never:**
- Không `sys.path.insert`/import `app.*` vào `nowing_mcp` — transport duy nhất là `NowingClient` (httpx).
- Không re-invent auth: dùng `WorkspaceContext.resolve` + `client.request` (PAT tự động qua `_auth_headers`).
- Không thêm PAT-scope seam mới cho list/tables/balance (sibling-scope đã defer ở 42.1 — nhất quán giữ convention hiện có).
- Không đổi `WorkspaceTableCreate` schema (không thêm `key` — key chỉ do ingest auto-table tạo; agent muốn gán lead vào table tạo tay thì truyền `table_id` UUID vào `leads.ingest`).
- Không sửa `LeadBatchService`, route batch-ingest, hay ledger attribution — tái dùng nguyên.

**Decisions:**
- D1. Endpoint balance mới đặt trong `app/routes/workspaces/core.py` (cạnh `GET /workspaces/{id}`), dep `RequireWorkspaceAccess` (membership-only — không có permission billing riêng trong enum; PAT cũng đi qua `check_permission` + api_access gate sẵn).
- D2. Response balance: `{workspace_id: int, credit_micros_balance: int}` (micro-USD, khớp convention `credit_micros_*`). Schema `WorkspaceBalanceRead` trong `app/schemas/workspace.py`.
- D3. `no_wallet`: workspace row absent → route 404 → tool catch `ToolError` chứa 404/not-found → trả `{status:'failed', reason:'no_wallet'}`. Column `credit_micros_balance` NOT NULL default 0 nên không cần check thêm.
- D4. Feature module mới `features/leads/` (`__init__.py` + `tools.py`) — không nhét vào `lead_intelligence` (feature đó là enrichment/signals, khác lifecycle).
- D5. Attribution đến free: PAT caller → `auth.method='pat'` → ledger 42.1 đã ghi `actor_pat_token_id` — spec này không thêm code attribution.

## Code Map

| File | Vai trò |
|---|---|
| `nowing_mcp/mcp_server/features/crm/tools.py` | Pattern canonical: `register(mcp, client, context)`, `@mcp.tool(name=..., annotations=..., structured_output=False)`, `ws = await context.resolve(workspace)`, `client.request` |
| `nowing_mcp/mcp_server/core/client.py:58-96` | `request(method, path, params=, json=, headers=)` — headers merge auth; 4xx/5xx → `ToolError` với `_FAILURE_HINTS` + server detail |
| `nowing_mcp/mcp_server/core/workspace_context.py:28,82` | `WorkspaceParam`, `resolve()` → `Workspace` |
| `nowing_mcp/mcp_server/server.py:126-164` | `context = WorkspaceContext(...)`; feature `register(...)` list — thêm `leads.register(mcp, client, context)` sau `lead_intelligence` |
| `nowing_mcp/tests/test_automation_report_tools.py`, `test_chat_tool.py` | Test pattern: stub `client.request` bằng fake/monkeypatch, gọi tool function trực tiếp hoặc qua `mcp` |
| `nowing_backend/app/routes/workspaces/core.py:225` | `GET /workspaces/{workspace_id}` — đặt `credits/balance` cạnh đây |
| `nowing_backend/app/dependencies/auth.py:97` | `RequireWorkspaceAccess` — membership-only dep |
| `nowing_backend/app/models/workspaces.py:70` | `Workspace.credit_micros_balance` BigInteger NOT NULL default 0 |
| `nowing_backend/app/schemas/workspace.py:47` | `WorkspaceRead` — thêm `WorkspaceBalanceRead` |
| `nowing_backend/app/routes/lead_batch_routes.py:~120-160` | batch-ingest route (signature `leads, client_id?, table_id?`, `Idempotency-Key` header, structured 422) |
| `nowing_backend/app/routes/workspace_tables_routes.py:71` | `POST /workspaces/{id}/tables` → `WorkspaceTableRead` |
| `nowing_backend/app/routes/leads_routes.py:247-279` | `GET /workspaces/{id}/leads` — params `client_id, source, intent, min_score, status, search, sort, limit, offset`; response `LeadListResponse {items, total, limit, offset}` |

## Tasks & Acceptance

### Execution

- **T1 (backend):** `GET /workspaces/{workspace_id}/credits/balance` trong `app/routes/workspaces/core.py`: `session.get(Workspace, workspace_id)` → 404 nếu absent → `WorkspaceBalanceRead(workspace_id, credit_micros_balance)`. Deps: `get_async_session`, `get_auth_context`, `RequireWorkspaceAccess`. Schema `WorkspaceBalanceRead` vào `app/schemas/workspace.py`.
- **T2 (MCP):** `nowing_mcp/mcp_server/features/leads/__init__.py` (`from .tools import register`) + `tools.py`:
  - `nowing_ingest_leads(leads: list[dict], client_id: str|None, table_id: str|None, idempotency_key: str|None, workspace)` → POST body `{leads, client_id?, table_id?}` + header `Idempotency-Key` nếu có → `json.dumps(result)`.
  - `nowing_create_leads_table(name: str, icon: str = 'table', workspace)` → POST `{name, icon}` → `json.dumps(result)`.
  - `nowing_list_leads(client_id?, source?, status?, search?, limit?, offset?, workspace)` → clamp → GET params → render bảng markdown ngắn (`company | status | score | source`) + dòng `total`.
  - `nowing_get_credits_balance(workspace)` → GET → `{"status":"success","workspace_id":…,"credit_micros_balance":…}`; ToolError chứa `404`/`not found` → `{"status":"failed","reason":"no_wallet"}`.
- **T3:** `server.py` — `from .features import leads` (theo import pattern hiện có) + `leads.register(mcp, client, context)` sau `lead_intelligence`.
- **T4 (tests):** `nowing_mcp/tests/test_leads_tools.py` theo pattern test hiện có (stub `client.request`); backend test balance endpoint — đặt trong `tests/unit/routes/` (file mới `test_workspace_credits.py` hoặc file workspace tests hiện có — implementer chọn theo convention).

### I/O Matrix

| Row | Input | Expected |
|---|---|---|
| INGEST_OK | PAT `leads:write` + 2 lead hợp lệ | 200 shape `{status:'success', ingested_count:2, lead_ids}` — giống hệt REST |
| INGEST_422 | 1 valid + 1 degenerate | ToolError/JSON mang `{status:'failed', rejected_indexes, reason_map}` nguyên vẹn |
| INGEST_IDEM | `idempotency_key='k1'` | header `Idempotency-Key: k1` forward tới backend |
| TABLES_OK | `name='Bảng A'` | 201 `WorkspaceTableRead` json |
| LIST_CLAMP | `limit=500` → 200; `limit=0` → 50; `offset=-3` → 0 | params gửi đúng giá trị clamp |
| LIST_EMPTY | 0 lead | output chứa `total: 0` / bảng rỗng, không error |
| BALANCE_OK | workspace có balance 1500000 | `{status:'success', credit_micros_balance:1500000}` |
| BALANCE_404 | workspace không tồn tại | `{status:'failed', reason:'no_wallet'}` |
| NO_KEY | không header lẫn env | `ToolError` "No Nowing API key" (từ `_auth_headers`) |
| PAT_NO_SCOPE | PAT thiếu `leads:write` gọi ingest | 403 propagate (42.1 seam, không test lại logic — chỉ passthrough) |

### Acceptance Criteria

1. `server.py` tool list có đủ 4 tool mới, mỗi wrapper ≤ ~40 dòng.
2. `leads.ingest` trả đúng shape REST kể cả 422 structured + forward `Idempotency-Key`.
3. `leads.list` clamp limit/offset đúng formula AC.
4. `credits.balance` trả balance workspace caller; workspace absent → `{status:'failed', reason:'no_wallet'}`.
5. Auth = PAT hiện có; attribution `actor_pat_token_id` chạy qua path 42.1 (không code thêm).

## Verification

```bash
# MCP tools (từ nowing_mcp/)
cd nowing_mcp && .venv/bin/python -m pytest tests/test_leads_tools.py -x -q
# Backend balance endpoint (từ nowing_backend/)
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/ -k "credit or balance" -x -q
# Regression nhanh batch-ingest (route không đổi nhưng sanity)
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_lead_batch_ingest.py -x -q
```

## Spec Change Log

- 2026-11-17 (review pass 1): Output contract chốt lại — success paths của
  `ingest_leads`/`create_leads_table`/`get_credits_balance` trả
  `json.dumps(result)` (đúng D6/spec, caller đọc được `lead_ids`,
  `skipped_blacklisted_count`); `list_leads` giữ markdown table (T2 cho phép).
  `icon` được promote thành param tuỳ chọn của `tables.create` (default
  `"table"`). `list_leads` forward `client_id`/`source` (trước là dead params).

## Review Triage Log

### 2026-11-17 — Review pass 1

4 layers: blind-hunter (6 findings), edge-case-hunter (10), verification-gap
(4+info), intent-alignment (partial). ~15 issues sau dedup.

- [high] [patch] BH-F1/EC-1: `result.get("accepted")` — field không tồn tại
  trong `BatchLeadIngestResponse`; fallback `len(leads)` nói dối skipped/failed.
  Fix: trả `json.dumps(result)` passthrough (đúng spec output contract) —
  `ingested_count`/`skipped_blacklisted_count`/`failed_count`/`lead_ids` đi
  thẳng tới caller. Test fakes đổi sang shape thật.
- [high] [patch] BH-F2/EC-3: import `ToolError` từ
  `mcp.server.fastmcp.exceptions` — `NowingClient.request` raise
  `mcp_server.core.errors.ToolError` → `except` dead trong prod, test xanh nhờ
  fake raise sai class. Fix: import `...core.errors.ToolError`; test fakes đổi
  import tương ứng.
- [medium] [patch] EC-2b/EC-3b/IA-d: `no_wallet` trả ToolError thay vì
  `{status:'failed', reason:'no_wallet'}` như AC literal. Fix: 404 → return JSON
  literal `{"status":"failed","reason":"no_wallet"}`; test assert output thay vì
  raise.
- [medium] [patch] BH-F4/EC: `_render_leads` đọc `item.get('score')` — LeadRead
  chỉ có `composite_score`/`fit_score`/`intent_score` → cột Score luôn "—".
  Fix: `composite_score or fit_score or '—'`; fake data đổi `composite_score`.
- [medium] [patch] EC-5/IA-b: `list_leads` có param `client_id`/`source` trong
  spec signature nhưng không forward. Fix: thêm 2 param + forward query params;
  test mới `test_list_leads_forwards_filters`.
- [medium] [patch] EC-8: `offset` âm đã clamp `max(0, ...)` — verified đúng spec.
  (giữ nguyên, không đổi)
- [low] [patch] EC-2a: `tables.create` icon hardcode `"table"`. Fix: param tuỳ
  chọn `icon="table"` forward vào body; test `test_create_leads_table_custom_icon`.
- [low] [patch] BH-F6/IA-a: `idempotency_key` doc hứa dedupe — thực tế
  audit-only vào ledger; dedupe thật = `value_hmac` upsert. Fix: mô tả Field.
- [low] [patch] VG: test file dùng fake shape ảo (`accepted`, SDK ToolError) —
  suite xanh nhưng tool hỏng với client thật. Fix: fakes theo
  `BatchLeadIngestResponse` + `core.errors.ToolError`; 422 test đổi thành
  assert ToolError propagate (client raise trước khi body đọc được).
- [medium] [defer] BH-F3/EC-10b/VG-A3: `GET /credits/balance` chỉ
  `RequireWorkspaceAccess` — PAT bound workspace khác vẫn đọc được balance nếu
  là member. Cùng pattern các read endpoint khác (GET /leads); `RequirePatScope`
  chỉ áp cho write path theo quyết định 42.1. Defer nhất quán epic-wide.
- [low] [defer] EC-10a/IA-c: lỗi 403 propagate ToolError text thay vì JSON
  `{status:'failed'}` — contract lỗi thống nhất là quyết định rộng hơn scope
  story; các tool khác cùng convention.
- [low] [defer] EC-7: không cap `len(leads)` phía MCP (server route nhận list
  tuỳ ý; 500-item AC là ingest-side).
- [reject] EC-6: `table_id` str UUID đã được coerce ở `lead_batch_service`
  (42.7) — không cần xử lý MCP-side.
- [reject] EC-4: limit clamp `limit or 50` vs `limit is not None` — verified
  `max(1, min(...,200))` đúng AC; `limit=0 → 1` chấp nhận (clamp semantics).
- [reject] VG "thiếu backend test cho route mới" — sai:
  `tests/unit/routes/test_workspace_credits.py` tồn tại (3 tests, pass).
- [reject] EC-9a: `.get("ingested_count", len(leads))` explicit-0 vs missing —
  moot sau khi chuyển sang JSON passthrough.

Patches applied bởi coordinator (patch agent bị kill trước khi apply): 7 edits
tools.py + 6 edits test file; verify 16/16 `test_leads_tools.py` + 13/13
`test_workspace_credits.py` + `test_lead_batch_ingest.py` pass.
