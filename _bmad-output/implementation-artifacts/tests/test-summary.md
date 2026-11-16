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
