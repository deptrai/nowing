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
