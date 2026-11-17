---
title: '42.3 — GET scrapers/health: aggregated channel status từ runs table'
type: feature
created: '2026-11-17'
status: 'in-progress'
baseline_revision: 'e22f09a44d151fd5ff2a2ac8d5f0b2361dfb3a71'
review_loop_iteration: 0
context: []
warnings: ['endpoint-path-deviation', 'error-code-field-deviation']
deferred: []
---

## Intent Contract

- **Purpose**: agent planning một scrape gọi 1 endpoint duy nhất biết channel (capability) nào chết/sống trong 24h qua — từ aggregate `runs` table, không live-probe (B3: probe làm xấu kênh đang rate-limit).
- **Source**: `_bmad-output/planning-artifacts/epics.md:5621-5633` (story 42.3) + epic-42-context invariant B3.
- **Always**
  - Endpoint chỉ ĐỌC DB: window 24h + `GROUP BY capability` → per-channel `{channel, last_status, last_error, last_seen_at, success_rate_24h}`.
  - `success_rate_24h = attempts ? hits/attempts : null` (null = idle >24h, không trả 0% giả); `hits` = runs `status='success'`.
  - `last_seen_at` + `last_status` lấy từ run mới nhất **all-time** per capability (không giới hạn 24h window).
  - Channel trong registry (`all_capabilities()`) chưa từng chạy → row với `last_status: 'unknown'`, `success_rate_24h: null` — không error.
  - Authz: `get_auth_context` + `check_workspace_access` (workspace-scoped session hoặc PAT) — filter `runs` theo `workspace_id` caller, không leak cross-workspace; set tenant GUC trước query (RLS).
  - Top-level envelope `{status: 'ok'|'degraded'|'down', channels: [...], checked_at}` — rule: 'down' nếu ≥1 channel observed có `success_rate_24h == 0`; 'degraded' nếu ≥1 channel có `0 < rate < 1`; else 'ok'. Channel idle/unknown không ảnh hưởng.
- **Never**
  - KHÔNG scrape, KHÔNG ping channel, KHÔNG gọi executor, KHÔNG network call — DB read only (B3, binding).
  - KHÔNG ghi vào `runs`, KHÔNG tạo table/index mới (dùng `ix_runs_workspace_created` sẵn có).
  - KHÔNG đổi schema `runs` hay vocabulary status (`success|error|running|cancelled` — `async_runner.py`).
  - KHÔNG cache phía app (query rẻ hơn cache-invalidation logic; index đủ cho <200ms).
  - KHÔNG đụng verb doors / run history routes hiện có trong `rest.py`.

## I/O Matrix

| Case | Input | Expected |
|---|---|---|
| OK | channel có 5/5 success trong 24h | row `success_rate_24h: 1.0`, `last_status: 'success'`, envelope `status:'ok'` |
| DEGRADED | channel 3/5 success | row `rate: 0.6` → envelope `status:'degraded'` |
| DOWN | channel 0/3 success | row `rate: 0.0` + `last_error` từ run fail mới nhất → envelope `status:'down'` |
| IDLE | channel chỉ có runs cũ >24h | `success_rate_24h: null`; `last_status`/`last_seen_at` từ run all-time |
| NEVER_RAN | channel trong registry, 0 run | row `last_status:'unknown'`, `rate: null`, `last_seen_at: null` |
| CROSS_WS | runs của workspace khác | không xuất hiện (filter workspace_id + RLS GUC) |
| UNAUTH | không session/PAT, hoặc không member workspace | 401/403 theo `check_workspace_access` |
| LEGACY_CAP | capability trong runs nhưng không còn trong registry | vẫn trả row (observed wins) |

## Code Map

- `app/capabilities/core/access/rest.py` — thêm `_register_health(router)` gọi từ `build_capabilities_router()` (line 152, cạnh `_register_run_history`). Route: `GET /workspaces/{workspace_id}/scrapers/health` (prefix `/api/v1` ở `app/routes/__init__.py:354` → path đầy đủ `/api/v1/workspaces/{id}/scrapers/health`). Response models `ChannelHealth` + `ScraperHealthResponse` định nghĩa inline cạnh `RunSummary` (line 107) — theo convention hiện có.
- `app/models/scraper.py:104` — `Run` (table `runs`): `workspace_id` (int), `capability` (str, indexed), `status` ('success'|'error'|'running'|'cancelled'), `error` (Text, free-form), `duration_ms`, `created_at` (TimestampMixin). Index `ix_runs_workspace_created (workspace_id, created_at)` line 125.
- `app/capabilities/core/async_runner.py:117-189,416,459,488` — status vocabulary nguồn sự thật: `success` / `error` / `running` / `cancelled`.
- `app/utils/rbac.py:212` — `check_workspace_access(session, auth, workspace_id)` (403 nếu không member).
- `app/tenant_context.py` — `set_request_tenant_context(session, workspace_id=...)` BẮT BUỘC trước query runs (RLS — precedent `rest.py:425`, `run_reader.py:70`).
- `app/users.py:336` — `get_auth_context` (session + PAT hai door như `list_runs`).
- `app/capabilities/core/store.py:66` — `all_capabilities()` cho danh sách channel never-ran.
- Queries (2 statements, SQLAlchemy core):
  1. Window: `SELECT capability, count(*) attempts, count(*) FILTER (WHERE status='success') hits, max(created_at) FROM runs WHERE workspace_id=:ws AND created_at >= now() - interval '24 hours' GROUP BY capability` (index-covered).
  2. All-time latest: `SELECT DISTINCT ON (capability) capability, status, error, created_at FROM runs WHERE workspace_id=:ws ORDER BY capability, created_at DESC`.
- Tests: `nowing_backend/tests/unit/routes/test_scraper_health.py` — theo convention `test_leads_routes.py` (TestClient + FastAPI + dependency-override `get_async_session`, fake session trả rows).

## Tasks & Acceptance

### Execution
- [ ] T1: response models `ChannelHealth` (`channel, last_status, last_error, last_seen_at, success_rate_24h, attempts_24h`) + `ScraperHealthResponse` (`status, channels, checked_at`) trong `rest.py`.
- [ ] T2: `_register_health(router)` — 2 queries ở Code Map, merge: registry channels ∪ observed capabilities; never-ran → `last_status:'unknown'`; derive envelope `status` theo rule Always; `checked_at = datetime.now(UTC).isoformat()`.
- [ ] T3: wire `_register_health(router)` vào `build_capabilities_router()`; route name `scraper:health`.
- [ ] T4: tests `test_scraper_health.py` — cover đủ 8 case I/O Matrix (fake session trả rows cho 2 queries; override `get_auth_context` + `check_workspace_access`).

### Acceptance
- [ ] AC1: `GET .../scrapers/health` trả per-channel `{channel, last_status, last_error, last_seen_at, success_rate_24h}` từ aggregate 24h + latest all-time.
- [ ] AC2: `success_rate_24h` null khi idle >24h; never-ran → `last_status:'unknown'`, HTTP 200.
- [ ] AC3: endpoint chỉ đọc DB — zero network/scrape call trong code path (review bằng đọc code + test không mock executor).
- [ ] AC4: cross-workspace runs không leak (test case CROSS_WS).
- [ ] AC5: envelope `status` ok/degraded/down theo rule; `checked_at` ISO 8601 UTC.
- [ ] AC6: EXPLAIN cả 2 query dùng `ix_runs_workspace_created` (hoặc justify) — <200ms trên 10k runs (verify trên staging/dev DB nếu có; else note trong PR).

## Spec Change Log

- 2026-11-17 — tạo spec từ AC epics.md:5621-5633.

## Design Notes

- **Endpoint path deviation (AC ghi `GET /api/v1/scrapers/health`)**: path thật là `/api/v1/workspaces/{workspace_id}/scrapers/health` — vì AC cũng yêu cầu workspace-scoped authz mà `AuthContext` không mang workspace id (session user có nhiều workspace; PAT bind 1 workspace). Đặt cạnh các scraper routes sibling (`/workspaces/{id}/scrapers/*`) trong cùng router = zero new wiring. Ghi chú này supersede literal path trong AC.
- **`last_error_code` deviation**: `runs.error` là free text (Text column), không có cột error-code. Spec trả `last_error` (raw, truncate 200 chars) từ run fail mới nhất all-time. Nếu sau này cần code có cấu trúc, thêm cột — out of scope.
- **Vì sao không cache**: 2 indexed queries trên 10k rows ~ vài ms; cache引入 invalidation phức tạp hơn lợi ích. AC <200ms đạt sẵn.
- **`running` status**: run đang chạy tính vào `attempts` nhưng không phải `hits` → kéo rate xuống. Chấp nhận (channel đang chạy = chưa thành công); không special-case.
- **RLS**: mọi read `runs` trong repo set tenant GUC trước (`rest.py:425` precedent) — bỏ bước này query có thể trả rỗng/403 tùy policy; test phải qua cùng path.
- **Không phải liveness probe**: AC briefing nhắc "liveness 200/500" — endpoints FastAPI mặc định: DB lỗi → exception → 500;healthy → 200. Không thêm logic liveness riêng.

## Review Triage Log

### 2026-11-17 — Review pass 1

4 layers: blind-hunter (6 findings), edge-case-hunter (8), verification-gap (4 + notes), intent-alignment (COMPLIANT). ~20 issues post-dedup.

**Patches applied (coordinator inline, không có implementer agent):**
- [medium] `last_error` lấy từ run **fail** mới nhất all-time (Design Note đúng, Code Map query lỏng hơn) — thêm query 3 `DISTINCT ON (capability) WHERE status='error'` + `_health_row` nhận `error_latest`; test mới `test_last_error_survives_newer_success` pin error sống sót qua success mới hơn. (BH-1)
- [medium] Window query thêm `Run.status != "cancelled"` — cancelled (user chủ động) không tính attempts → tránh envelope 'down' giả; 'running' vẫn tính theo Design Note. (BH-2)
- [medium] RLS GUC silent regression — `_FakeSession` wire `tenant_guc_calls` khi stmt chứa `set_config`; `test_cross_workspace_not_leaked` assert `app.workspace_id` set thành `"7"`. Xóa `set_request_tenant_context` giờ đỏ test. (VG-1, BH-3)
- [low] DISTINCT ON tie — `.order_by(..., Run.id.desc())` tiebreak deterministic. (EC-2)
- [low] `or True` tautology trong `test_idle_channel_rate_null` → assert thật trên `last_seen_at`. (IA-1, VG-3, EC-1)
- [low] Precedence down>degraded chưa pin → `test_down_beats_degraded_with_mixed_channels`. (VG-4)
- [low] `checked_at` chỉ truthy → assert `endswith("Z")` (UTC AC5). (VG-misc)
- [low] `test_never_ran_channel_unknown` vacuous → assert mọi channel `last_status=='unknown'` + rate null (registry thật ~32 caps). (BH-5, EC-7)
- [low] Thiếu nhánh 401 → `test_no_auth_returns_401`. (EC-8)
- [low] Docstring "index-covered" quá mạnh cho query all-time → ghi rõ index assist WHERE, sort theo capability. (EC-4)

**Rejected:** `last_24h` dead column (spec query normative có nó, harmless); PG-only `.distinct(col)` (prod là Postgres); READ-COMMITTED 2-statement skew (health endpoint chấp nhận staleness); fake-session route bằng SQL-text (vẫn hoạt động, đã thêm params-detect cho error query).

**Deferred:** SQL 2 query chưa execute trên DB thật + AC6 EXPLAIN `<200ms` — spec cho phép note trong PR.

## Auto Run Result

- Implement: `rest.py` `_register_health` + `ChannelHealth`/`ScraperHealthResponse` + `_health_row` (3 queries: window 24h GROUP BY, latest DISTINCT ON, latest-error DISTINCT ON).
- Review pass 1: 10 patches applied; `test_scraper_health.py` 13 tests xanh; `tests/unit/routes` 336+ xanh.
- `followup_review_recommended`: false (0 high còn lại; medium patches đều test-pinned).

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_scraper_health.py -x -q
cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes -x -q
```
