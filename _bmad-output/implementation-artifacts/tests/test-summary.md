# Test Summary — Story 42.1 (PAT-scoped REST batch ingest)

Ngày: 2026-11-17 · Spec: `spec-42-1-pat-scoped-batch-ingest-verify-harden.md`

## E2E / API tests mới

File: `nowing_backend/tests/integration/lead_batch/test_pat_batch_ingest_e2e.py` — 6 tests,
exercise **real auth path** (`Bearer nw_pat_…` → `resolve_pat` → `AuthContext.pat_auth`
→ `RequirePermission` → `RequirePatScope` → service → ledger), không mock auth.

| Test | Matrix row | Kết quả |
|---|---|---|
| `test_pat_ingest_persists_lead_and_writes_ledger` | PAT_OK | PASS — lead + `LeadActivityLog` (`actor_pat_token_id`, `idempotency_key`) |
| `test_pat_without_leads_write_scope_gets_403` | PAT_NO_SCOPE | PASS — 403 `permission missing: leads:write`, 0 lead |
| `test_pat_bound_to_other_workspace_gets_403` | PAT_WRONG_WS | PASS — 403 `workspace_id outside pat scope` |
| `test_pat_on_api_access_disabled_workspace_gets_403` | api_access gate | PASS — 403 trước scope check (gate ordering) |
| `test_degenerate_batch_returns_structured_422_and_rolls_back` | DEGENERATE_BATCH | PASS — 422 `{status:'failed', rejected_indexes:[1,2], reason_map}`, rollback |
| `test_pat_repush_idempotent_dedup_and_ledger_per_call` | REPUSH_IDEMPOTENT | PASS — 1 lead sau 2 call, 2 ledger rows (attribution per call, by design) |

## Regression suites

- `tests/integration/lead_batch/` → **23 passed** (17 hiện hữu + 6 mới)
- `tests/unit/routes/test_lead_batch_ingest.py` + `test_lead_batch_service.py`
  + `test_kb_persistence_embed_fail.py` → **35 passed**

## Lưu ý

- E2E dùng `token_kind="legacy"` PAT (không chịu `chk_pat_agent_chat_requires_scope`
  constraint) — đúng contract story: legacy PAT scopes=[] fail-closed, scoped PAT hoạt động.
- `api_access_enabled=False` chặn PAT ở permission gate **trước** scope seam — hành vi
  có chủ đích, được test độc lập.

---

# Story 42.2 — ToolResultEnvelope e2e

**File:** `nowing_backend/tests/unit/agents/multi_agent_chat/shared/tools/mcp/test_medirus_envelope_e2e.py` — 8 tests, real `StructuredTool.ainvoke` chain (handler → `_execute_medirus_tool` → `_format_result` → JSON), chỉ mock `MedirusMcpClient`.

| Test | Matrix row | Result |
|---|---|---|
| `test_e2e_success_envelope_contract` | MEDIRUS_OK | PASS — đúng 4 keys `{status, reason, recovery_hint, items}` |
| `test_e2e_exception_maps_to_failed_with_hint` | FAIL_4010 | PASS — hint seeded + `(untrusted suggestedAction: …)` |
| `test_e2e_in_band_failure_maps_to_failed` | FAIL_4030 | PASS — in-band `{success:false}` → failed + PROXY hint |
| `test_e2e_empty_result_status` | EMPTY_DATA | PASS — `empty_result`, items `[]` |
| `test_e2e_degraded_status_passthrough` | DEGRADED_META | PASS — `degraded` + reason |
| `test_e2e_dry_run_stub_is_preview_not_success` | DRYRUN_PREVIEW | PASS — `preview`, không giống success |
| `test_e2e_early_validation_failed_envelope_no_hint` | EARLY_VALIDATION | PASS — failed, `recovery_hint=None`, `call_tool` không được gọi |
| `test_e2e_generic_exception_generic_hint` | GENERIC_EXC | PASS — `generic: check logs, retry` |

## Regression

- Spec verification (3 files) → **57 passed**; wide sweep `tests/unit/capabilities` + `tests/unit/agents/multi_agent_chat` → **1316 passed**, 1 fail `test_parallel_tasks` pre-existing.

## Lưu ý

- `preview` chỉ reachable qua daemon echo (`preview: true` flag / `preview` list) — agent args không expose `dryRun`; hành vi đúng contract "dryRun stub không giống success".
- `_fail()` early-validation cố tình `recovery_hint=None` — deterministic failure không nên gợi ý retry.

---

# Test Summary — Story 42.7 (Leads route + auto-table + empty state)

Ngày: 2026-11-17 · Spec: `spec-42-7-leads-route-auto-table.md` · Commit: `f66b3b5b0`

## Tests mới / sửa

| Suite | Coverage | Kết quả |
|---|---|---|
| `TestAutoTableResolution` (`test_lead_batch_service.py`, 8 tests) | T2 — get-or-create default/keyed table, reuse key, race-thua re-SELECT, valid UUID + **str** table_id giữ nguyên, invalid str + stale→default, 2 client_id→2 key 1 INSERT | PASS |
| `tests/integration/db/test_migration_250_roundtrip.py` | A5 — seed orphan lead → upgrade → default table tạo + lead trỏ đúng; downgrade gỡ constraint+column | PASS |
| `tests/integration/lead_batch/` (23 incl. PAT e2e 42.1) | Regression toàn funnel ingest sau khi thêm resolver + stream-path adoption | PASS |
| `nowing_web/tests/leads/split-canvas.spec.ts` (rewrite) | `/leads` giờ mount canvas (không redirect) — testid `nowing-leads-canvas-standalone`, row click mở flyout | source-only (chưa chạy — cần dev server + browser) |

## Regression

- `.venv/bin/python -m pytest tests/unit/services/test_lead_batch_service.py tests/unit/routes/test_lead_batch_ingest.py tests/integration/lead_batch/ tests/integration/db/test_migration_250_roundtrip.py -q` → **60 passed**
- `pnpm tsc --noEmit` (nowing_web) → clean; `alembic heads` → single head `250`

## Lưu ý

- `ingest_stream_leads_to_db` (scraper path) giờ cũng resolve default table — orphan `table_id IS NULL` không còn sinh mới (kể cả cửa sổ deploy sau backfill).
- str `table_id` từ `save_leads` được coerce `UUID(str)` — caller override giờ thật sự giữ (trước patch bị nuốt sang default).
- Deploy: `alembic upgrade head` chạy backfill one-shot trước khi code mới nhận traffic.

---

# Test Summary — Story 42.4 (nowing_mcp lead tools)

Ngày: 2026-11-17 · Spec: `spec-42-4-nowing-mcp-lead-tools.md` · Commit: `570a6bbd7`

## Tests mới / sửa

| Suite | Coverage | Kết quả |
|---|---|---|
| `nowing_mcp/tests/test_leads_tools.py` (16) | 4 tools qua `build_server` + `call_tool` thật (NowingClient fake theo shape backend thật): ingest JSON passthrough + `Idempotency-Key` header + 422→ToolError + skipped/failed counts; tables.create default icon + custom icon; list clamp limit[1..200]/offset≥0 + forward `client_id`/`source` + markdown render + empty; balance OK + 404→`{status:'failed',reason:'no_wallet'}` + NO_KEY | PASS |
| `nowing_backend/tests/unit/routes/test_workspace_credits.py` (3) | `GET /workspaces/{id}/credits/balance` — balance value, zero balance 200, unknown ws 404 | PASS |

## Regression

- `nowing_mcp`: `pytest tests/test_leads_tools.py -x -q` → **16 passed**
- `nowing_backend`: `pytest tests/unit/routes/test_workspace_credits.py tests/unit/routes/test_lead_batch_ingest.py -x -q` → **13 passed**

## Lưu ý

- Success output của ingest/tables/balance là `json.dumps(result)` — caller đọc được `lead_ids`, `skipped_blacklisted_count` (spec D6); `leads.list` giữ markdown table.
- 422 reject-all không đọc được body phía MCP — `NowingClient` raise `ToolError` trước; contract `{status:'failed', rejected_indexes}` chỉ lộ diện nếu client đổi behavior (ghi chú cho followup).
- `no_wallet` chỉ reachable khi workspace row absent (404); `credit_micros_balance` NOT NULL default 0 — không có wallet object riêng.
- Deferred: `GET /credits/balance` (và các read endpoint khác) chưa có `RequirePatScope` — PAT bound ws-khác nhưng là member vẫn đọc được; contract lỗi MCP chưa thống nhất (403 → ToolError text, không phải JSON).

# Story 42.3 — `GET /workspaces/{id}/scrapers/health`

Ngày: 2026-11-17 · Spec: `spec-42-3-scrapers-health.md` · Commit: `89aaed195`

## Tests mới / sửa

| Suite | Coverage | Kết quả |
|---|---|---|
| `nowing_backend/tests/unit/routes/test_scraper_health.py` (13) | OK/DEGRADED/DOWN/IDLE/NEVER_RAN(×2)/CROSS_WS(+RLS GUC assert `app.workspace_id`)/UNAUTH 403+401/LEGACY_CAP/truncate-200/down-beats-degraded/last_error-survives-success | PASS |

## Regression

- `pytest tests/unit/routes -x -q` → **339 passed** (13 mới trong tổng số)

## Lưu ý

- `last_error` = run **fail** mới nhất all-time (query riêng `status='error'`), không bị success mới hơn phủ — theo spec Design Note.
- Window query loại `status='cancelled'` khỏi attempts (user chủ động hủy ≠ failure); `running` vẫn tính.
- Chưa verify trên DB thật: SQL 3 query chỉ chạy qua fake session; AC6 EXPLAIN <200ms cần check khi deploy (query all-time sort theo capability — không full index-only).
- RLS: `runs` có FORCE RLS — endpoint set `app.workspace_id` GUC trước select; test bắt được nếu ai xóa dòng `set_request_tenant_context`.

# Story 42.5 — HITL reject: Gemini functionResponse mismatch fix

Ngày: 2026-11-17 · Spec: `spec-42-5-hitl-gemini-function-response.md` · Commit: `59f79e435`

## Tests mới / sửa

| Suite | Coverage | Kết quả |
|---|---|---|
| `tests/unit/agents/multi_agent_chat/hitl_gemini/test_fixture_repro.py` (3) | T1 AD-6: replay checkpoint có dangling `call_prod_5` → chứng minh `CorrectedError` uncaught (5 functionCall vs 4 functionResponse); approve path vẫn khớp; invariant check | PASS |
| `test_hitl_pairing_regression.py` (3) | T3: approve_single / mixed approve+reject (resume 2 lần — interrupt per-call) / all_reject → mọi functionCall đúng 1 functionResponse | PASS |

## Regression

- `pytest tests/unit/agents/multi_agent_chat/hitl_gemini` → **6 passed**
- HITL regression (checkpointed_subagent + subagents/hitl + permissions + new_chat hitl/permissions + dedup) → **133 passed**, 1 deselect: `test_one_atask_failure_does_not_corrupt_sibling_atask` — pre-existing, confirm fail trên baseline `git stash`.

## Lưu ý

- Reject path không còn raise `RejectedError`/`CorrectedError` — fix LOẠI BỎ nguồn `chat_stream_error` trước đây (không thêm error path mới, T5).
- Unknown permission decision → fail-closed cùng shape reject.
- Fixture là fallback snapshot-shaped (14 msgs) với `_provenance` — không phải raw prod thread 52 msgs.

# Story 42.6 — Step-cap graceful degradation: partial synthesis

Ngày: 2026-11-17 · Spec: `spec-42-6-step-cap-partial-synthesis.md` · Commit: `01d5fc09b`

## Tests mới

| Suite | Coverage | Kết quả |
|---|---|---|
| `tests/unit/tasks/chat/streaming/test_partial_synthesis.py` (12) | cap_hit prefix/fallback/none, tool-part helpers, notices, synthesize success/fail/timeout/empty, e2e `stream_agent_events` cap-hit emit text frames, status part contract | PASS |

## Regression

- `pytest tests/unit/tasks/chat/streaming -x -q` → **59 passed** (gồm 12 test mới).

## Lưu ý

- Synthesis LLM = workspace AGENT model, inject qua ContextVar (không đổi signature `run_stream_loop`); orchestrator khác không set → notice-only graceful.
- Prompt synthesis cap 20 tool parts (review patch — cap-hit run có tới ~80 parts).
- `PARTIAL_STATUS_PART` là status part mới; FE loader đã drop unknown status parts (T6 verify-only, không sửa FE).
- Test timeout chiếm ~15s trong suite (đúng `SYNTHESIS_TIMEOUT_S`).

# Story 42.8 — Medirus workspaceId forwarding + NOWING_DEV_BYPASS_QUOTA

Ngày: 2026-11-17 · Spec: `spec-42-8-medirus-workspaceid-forwarding.md` · Commit: `05b78a8a6`

## Tests mới / extend

| Suite | Coverage | Kết quả |
|---|---|---|
| `test_medirus_gateway.py` (+4) | inject workspaceId, merge context giữ key cũ, workspace_id=None không inject, factory→handler threading | PASS |
| `tests/unit/services/test_dev_quota_bypass.py` (9) | bypass matrix (self-host+dev on; cloud off; self-host+prod off; DEBUG-only off), warn latch 1 lần, credit_reserve/credit_get_usage early-return | PASS |

## Regression

- `pytest tests/unit/capabilities/test_medirus_proxy.py -x -q` → **11 passed**.
- `pytest test_medirus_gateway.py test_dev_quota_bypass.py` → **31 passed** (sau patch `_loader.py`).

## Lưu ý

- Review patch: `discover_single_mcp_connector` dùng `connector.workspace_id` (bug NameError — unit tests không cover discovery path).
- Runtime verify với Medirus daemon thật deferred — check `medirus-mcp.log` hết MissingWorkspaceId sau deploy.
- AC3 deviation: 5 files sửa (spec ước ≤3) — forwarding bắt buộc chạm gateway/http/loader.

## Epic 42 — E2E coverage bổ sung (2026-11-17)

Per-story e2e theo handoff (`bmad-qa-generate-e2e-tests`): real app + real Postgres + real PAT.

| Story | File | Coverage | Kết quả |
|---|---|---|---|
| 42.3 | `tests/integration/scrapers/test_scraper_health_e2e.py` (4) | aggregate 24h real DB, envelope down, cross-workspace RLS không leak, non-member 403 | PASS |
| 42.4 | `nowing_mcp/tests/test_leads_e2e.py` (4) | wire-level `mcp.call_tool` → real `NowingClient` → `httpx.MockTransport`: ingest path+idempotency header, clamp limit/offset, 404→`no_wallet`, no-key → ToolError | PASS |
| 42.7 | `tests/integration/lead_batch/test_auto_table_e2e.py` (4) | auto-create table `key=client_id`+link lead, reuse 1 table, deleted→recreate id mới+relink, explicit `table_id` giữ nguyên (service-level — REST schema không expose) | PASS |
| 42.5/42.6/42.8 | đã có | fixture repro + stream-level e2e + factory threading test (trong unit suites của từng story) | PASS |

### Regression

- `pytest tests/integration/lead_batch/ tests/integration/scrapers/` → **31 passed**.
- `pytest nowing_mcp tests/` (full) → **128+4 passed**.

### Lưu ý

- `LeadItem` REST schema không expose `table_id` — explicit table_id chỉ qua funnel `save_leads`; test explicit-id chạy service-level.
- MCP e2e chỉ được wire-level (`httpx.MockTransport`) vì 2 venv không share deps — backend path đã có integration tests riêng.
