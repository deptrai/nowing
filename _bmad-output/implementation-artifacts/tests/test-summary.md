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

## Spec 42.9 — PAT scope sweep (2026-11-17)

Spec: `_bmad-output/implementation-artifacts/spec-42-9-lead-pat-scope-hardening.md` — follow-up bundle sau epic 42. Commit `9225b9648`.

| Suite | Kết quả |
|---|---|
| `tests/unit/routes/test_pat_scope_sweep.py` | **8 passed** — READ_OK / READ_NO_SCOPE / WRITE_OK / WRITE_NO_SCOPE / PAT_WRONG_WS / BALANCE_PAT / GATE_MESSAGE (403 chứa `api-access` + `API_ACCESS_MANAGE`) / SESSION_UNCHANGED |
| `tests/unit/routes` regression | **347 passed** |

### Lưu ý

- `resolve_lead_phone` gắn `leads:enrich` (tightening cố ý): PAT chỉ có `leads:write` giờ 403 — đúng scope cho billing-waterfall endpoint; session user không đổi.
- `phone_verification_result` không gắn seam — `require_superuser` đã chặn PAT (dead code nếu gắn).
- 403 api-access giờ nêu route bật `PUT /workspaces/{id}/api-access` — discoverability fix, endpoint vốn đã tồn tại.

## Spec 42.10 — PAT scope sweep phần còn lại (2026-11-17)

Spec: `_bmad-output/implementation-artifacts/spec-42-10-pat-scope-sweep-remaining-routes.md` — sweep nốt 4 file routes từ deferred-work sau review 42.9.

| Suite | Kết quả |
|---|---|
| `tests/unit/routes/test_pat_scope_sweep.py` | **32 passed** — +13 case parametrize wrong-scope 403 (`permission missing: {scope}` đúng từng endpoint), +`test_clipper_pat_respects_api_access_gate` (PAT `leads:clipper:write` + ws `api_access_enabled=False` → 403), +`test_clipper_session_unchanged` |
| `tests/unit/routes` regression | **371 passed** |
| `tests/integration/test_pat_fail_closed_authz.py` | **7 passed** |

### Lưu ý

- `enrichment_routes`: `list_verified_contacts`/`list_enrichment_requests` permission check chạy inline trong body (`_require_lead_read`) — seam đặt sau `get_auth_context`, không phải sau `RequirePermission`.
- `lead_clipper_routes`: seam `leads:clipper:write` vốn đã có — chỉ vá nhánh PAT thiếu `_enforce_api_access_gate` (trước: PAT bypass gate, session thì không).
- `update_icp_criteria` (perm `SETTINGS_UPDATE`) → `leads:write` (D1); zalo-connection + webhook skip (D4).
- Side-effect cần thiết: `test_zalo_copilot_context.py` cập nhật `_FakeSession` — nhánh PAT giờ cần session cho gate.
- Census 42-10 phát hiện còn `dnc_routes.py` + `lead_pipeline_routes.py` chưa seam → đã ghi deferred-work (spec 42-11 candidate), ngoài scope spec này.

## Spec 42.11 — PAT scope sweep dnc + pipeline (2026-11-17)

- Spec: `_bmad-output/implementation-artifacts/spec-42-11-pat-scope-dnc-pipeline.md`
- `pytest tests/unit/routes/test_pat_scope_sweep.py` → **45 passed** (`test_sweep_42_11_wrong_scope_403` 11 case + `wrong_workspace` 2 case mới).
- `pytest tests/unit/routes -x -q` → **384 passed** — không test cũ gãy.
- `dnc_routes`: 4 seam (list→`leads:read`, create/delete/import→`leads:write`); `lead_pipeline_routes`: 12 seam (4 read→`leads:read`, 8 mutation→`leads:write`; spend-cap/lead-capacity→`leads:write` theo D1).
- Domain `leads:*` đóng hoàn toàn sau spec này; correction: pipeline không bypass api-access gate (`RequireWorkspaceAccess` đã chạy gate) — gap duy nhất là PAT scope.

## Epic 42 retro — boundary fixes (2026-11-17)

- Boundary review (25 file giao nhau, diff 2,872 dòng) phát hiện 2 high — đã fix cùng commit `2411240b6`:
  1. `ingest_stream_leads_to_db`: stmt build trước `_resolve_lead_table_ids` + `rec` thiếu `table_id` → stream-path auto-table là dead code (lead NULL + table rác). Fix: reorder + `rec["table_id"]` + `on_conflict` coalesce.
  2. `generate_lead_hmac` không normalize domain → stream/radar path raw domain sinh hmac khác batch path → duplicate lead cùng entity. Fix: `normalize_domain` bên trong hmac (idempotent batch path).
- `pytest tests/unit/lead_intelligence/test_lead_stream_buffer.py` → **8 passed** (3 regression mới: hmac normalize, stmt chứa table_id, ordering resolver→stmt qua fake session).
- `pytest tests/unit/lead_intelligence tests/unit/services/test_lead_batch_service.py tests/integration/lead_batch/` → **355 passed** — không hồi quy.
- Medium findings → action items AI-42.7 (PAT mint validate scopes mọi token_kind) + AI-42.8 (reset `_synthesis_workspace_id` ContextVar).

## Epic 42 retro — AI-42.5 + AI-42.2 + AI-42.4 (unified PAT seam) — 2026-11-17

Đóng 4 action items retro còn lại: AI-42.5 (`reverse_icp` seam → `leads:enrich`, endpoint LLM cost-bearing), AI-42.2 (`_verify_clipper_auth` PAT branch → canonical `enforce_pat_scope`), AI-42.3 (audit MCP error convention 13 features — conform, note vào `nowing_mcp/README.md`), **AI-42.4** unified PAT seam:

- `check_permission` giờ tự `enforce_pat_scope(required_permission)` cho MỌI `RequirePermission` caller — scope ≡ perm identity, ~80 route files non-leads cover ngay; `self_host` token exempt (owner-minted full-access); binding-first trước api-access gate.
- `check_workspace_access` enforce PAT workspace binding.
- `KNOWN_PAT_SCOPES` = dynamic catalog (`Permission` enum ∪ `agent_chat:*` ∪ `leads:clipper:write`) — mint legacy 400 trên scope lạ.

### Tests

| Suite | Kết quả |
|---|---|
| `tests/unit/utils/test_pat_unified_scope.py` (mới, 9 tests) | 9 passed — scope pass/missing, binding-first, self_host exempt, session unchanged, `scopes=[]` fail-closed, workspace_access binding |
| `tests/unit/routes/test_pat_scope_sweep.py` | 48 passed — `update_icp_criteria` pin đổi `leads:write`→`settings:update` (scope=perm) |
| `tests/integration/lead_batch/` + fail-closed + clipper ingest | 37 passed — e2e api-access-disabled đổi PAT bound tới disabled_ws (binding-first order) |
| `tests/unit/routes tests/unit/utils` full regression | **715 passed** |

### Lưu ý

- Convention: PAT scopes giờ = set các permission agent cần (vd enrich-capable PAT → `["leads:read","leads:enrich"]`). `reverse_icp` dual: perm `leads:read` + seam `leads:enrich` → PAT cần cả hai.
- Endpoint không qua `check_permission`/`RequirePermission`/`RequireWorkspaceAccess` (inline `has_permission`) vẫn bypass seam — residual đã ghi deferred-work.

## Spec 43.1 — CampaignSpec direction + AD-5 validation (2026-11-17)

| Test | File | Kết quả |
|---|---|---|
| Truth-table AD-5 (parametrize) | tests/unit/lead_intelligence/test_campaign_spec_direction.py | 29 passed |
| Route guard supply→422 (execute+plan) | cùng file, class TestSupplyExecutionGuard | 2 passed |
| Regression | tests/unit/lead_intelligence/ + route sweeps | 383 passed |

**Ghi chú:** guard `spec.direction != "demand"` tại `campaign_routes.py` là tạm — gỡ khi 43.6 wire supply end-to-end. `from_campaign_create_input` reject direction-scoped keys non-default cho tới 43.5. `validate_assignment`/`model_copy` bypass validator → deferred (không consumer mutate).

## Spec 43.2 — Direction-aware adapter resolution (2026-11-17)

| Test | File | Kết quả |
|---|---|---|
| Direction resolution (26 test) | tests/unit/lead_intelligence/test_adapter_resolution_direction.py | 26 passed |
| — supply match thật (muasamcong exact / enterprise both / case+diacritics) | cùng file | 3 tests |
| — supply no-match fail-closed all supply_eligible; never demand adapter | cùng file | pinned |
| — wrapper supply ordering = registration order, no priority mutation | cùng file | pinned |
| — query synthesis cả 2 seam (planner + orchestrator effective_query) | cùng file | pinned |
| Demand regression snapshot | DEMAND_RE_* + list_all fallback | pinned bit-for-bit |
| Regression | tests/unit/lead_intelligence/ | 358 passed |

**Ghi chú:** `supply_eligible` chỉ enterprise + muasamcong; supply ordering cố định
registration order (không đọc priority bị demand mutate). Dict-spec direction qua
`_spec_direction` helper; categories non-list guard. `target_sources` explicit
thắng direction cả 2 phía (AC1 đã chốt ngoại lệ).

## Spec 43.3 — Supply post-filter tại persist seam (2026-11-17)

| Test | File | Kết quả |
|---|---|---|
| Post-filter matrix (24 test) | tests/unit/lead_intelligence/test_supply_post_filter.py | 24 passed |
| — tax_id drop/keep, min_rating D3 fail-open (unrated_kept), verified D2 strict | cùng file | pinned |
| — sparse_identity guard, outside_locations (toàn quốc/* tắt guard) | cùng file | pinned |
| — DEMAND_UNTOUCHED + seam integration (filter trước ingest, all-dropped skip) | cùng file | pinned |
| Regression | tests/unit/lead_intelligence/ | 382 passed |

**Ghi chú:** commit `0d0e39f6e`. Counters vào `LeadGenOrchestratorResult.supply_filter_counters`
(`filtered_no_tax_id`, `filtered_min_rating`, `filtered_unverified`, `filtered_sparse_identity`,
`filtered_outside_locations`, `unrated_kept`). Enterprise `verified` = có tax_code (masothue True,
đấu thầu False). Lần 1 implementer fabricate report — retry với proof `git status` bắt buộc.

## Spec 43.4 — Lead role/visibility tagging (2026-11-17)

| Test | File | Kết quả |
|---|---|---|
| Tagging matrix (7 test) | tests/unit/lead_intelligence/test_supply_role_tagging.py | 7 passed |
| — SUPPLY_TAGGED (4 keys), DEMAND_UNTAGGED, EXTRA_METADATA_MERGE, POOLABLE_LABEL, ROLE_LWW | cùng file | pinned |
| Regression | tests/unit/lead_intelligence/ | 389 passed |

**Ghi chú:** commit `96fca6bc0`. 4 keys `lead_role/campaign_direction/campaign_key/visibility`
inject tại build site trước `ingest_batch`; merge giữ keys có sẵn; role LWW qua upsert
JSONB excluded-wins (đúng D2/D3 spec).

## Spec 43.5 — FE intake "Tìm nhà cung cấp" + wire contract (2026-11-18)

| Test | File | Kết quả |
|---|---|---|
| Wire contract matrix (15 test) | tests/unit/lead_intelligence/test_supply_wire_contract.py | 15 passed |
| — SUPPLY_WIRE_OK, derived location_profile, require_tax default, invalid literal, guard remains | cùng file | pinned |
| Updated guard test | tests/unit/lead_intelligence/test_campaign_spec_direction.py | pass |
| Regression | tests/unit/lead_intelligence/ | 405 passed |

**Ghi chú:** chưa commit. FE campaign-builder thêm mode selector demand/supply, wire
top-level `direction` + `supply_criteria` (D1); `location_profile` derive từ
locations[0] qua `resolve_city_code` (D3); route guard 422 vẫn giữ (43.6 mới gỡ).

## Spec 43.6 — E2E supply campaign + gỡ route guard (2026-11-18)

Commit `60e95ddaf`. File `tests/integration/campaigns/test_supply_campaign_e2e.py` (5 tests, ~415 dòng):

| Test | Cover |
|---|---|
| `test_supply_campaign_execute_e2e` | POST execute qua PAT thật → adapters chỉ supply_eligible (enterprise/muasamcong), `filtered_no_tax_id=3`, persist lead `extra_metadata.lead_role=supplier` + `campaign_key` + `visibility` |
| `test_supply_match_mode_pool_rejected_422` | AD-5 joint validation |
| `test_supply_missing_supply_criteria_rejected_422` | AD-5 |
| `test_demand_plan_regression` | demand plan trả expected_sources demand (batdongsan/chotot) |
| `test_demand_execute_regression` | demand execute persist=false → 200 |

T4: gỡ route guard tạm `direction != "demand"` (campaign_routes.py) + `TestSupplyExecutionGuard` + `TestRouteGuardRemains` — supply đã wire đầy đủ end-to-end.
Mock: `search_leads` adapter instances + `MicroExtractionWorker` (không call mạng/LLM thật).
Regression: integration campaigns 5 + unit lead_intelligence 402 + routes 387 — toàn bộ xanh.
Note: lead "sparse-identity" case phủ bởi `filtered_no_tax_id` guard đầu (require_tax_id=true) — sparse chỉ reachable khi require_tax_id=false (unit 43.3 cover).

## Spec 44.1 — Lead campaign persistence schema + opt-in binding (2026-11-18)

Commit pending (sau test-summary update). Bảng mới `lead_campaigns`/`campaign_runs`/`campaign_leads` + RLS tenant ENABLE+FORCE (6 policy, predicate workspace-only).

| Test file | Cover | Kết quả |
|---|---|---|
| tests/unit/services/test_campaign_service.py (15) | enum khớp FE `campaignStatusSchema`; `open_campaign_run` advisory lock + 409-run-running; get-or-create ON CONFLICT + re-SELECT; junction SAVEPOINT fail-open `junction_failed`; finalize succeeded/failed → campaign status | 15 passed |
| tests/unit/lead_intelligence/test_campaign_binding.py (6) | opt-in gating (agent path 0 rows nhưng vẫn được commit fix); never infer từ spec.name; early-return finalize; ingest-fail finalize failed; junction role supplier/buyer | 6 passed |
| tests/integration/campaigns/test_campaign_persist_commit.py (2) | **commit-proof thật**: session mới thấy leads + campaign + run + junction sau request (fix latent bug `/campaigns/execute` không commit); persist=false → 0 rows | 2 passed |
| Savepoint-mock fixes | test_supply_post_filter/test_supply_role_tagging/test_lead_gen_orchestrator cần `begin_nested` trả async CM | pass |
| Regression | tests/unit/lead_intelligence + services + routes | 3231 passed |
| Alembic live (nowing_test @5432) | `upgrade 250→251` → `downgrade -1` → `upgrade head` sạch; 6 RLS policy + FORCE đúng; single head `251` | verified |

**T0 resolved:** `/campaigns/execute?persist=true` trước đây KHÔNG commit (bug tiềm ẩn — leads rollback prod, test suite che bằng savepoint conftest). Fix = `session.commit()` cuối `execute_and_persist`, mọi exit path finalize run. Deviation chấp nhận: models ở `app/models/campaigns.py` (spec ghi `models/leads/campaign.py` — top-level khớp precedent `webset_campaign.py`); `open_campaign_run` set run `'running'` ngay (44.2 map `'queued'` cho response); implicit campaign `source='execute'` cho mọi `/execute` caller (phân biệt 'api' cần auth-kind detect — ghi vào triage).

## Spec 44.2 — Campaign CRUD + launch + async run task (2026-11-18)

| Test file | Cover | Kết quả |
|---|---|---|
| tests/unit/routes/test_campaign_crud_routes.py (22) | wire-contract mapper khớp `campaignSchema` (created + implicit fallback), list shape + `?include_implicit` (assert SQL filter `source='created'`), page_size cap 100, detail 404/wrong-ws, runs newest-first, presets precedence, create 201/409-dup/422-invalid, PATCH name+status + machine-status 422 + clash 409, launch paused/archived 409 + concurrent-run 409 + happy path queue, pause running→paused/draft 422, execute async 422-without-persist + queued | 22 passed |
| tests/unit/tasks/test_campaign_launch_task.py (3) | TASK_PATH (execute_and_persist binding đúng campaign+run_id), TENANT_RLS (set_request_tenant_context workspace trên session riêng), failure → rollback + finalize 'failed' + commit + propagate, missing campaign/run → finalize + propagate | 3 passed |
| Integration | tests/integration/campaigns/ (7, gồm persist-commit + supply e2e 44.1) | 7 passed |
| Regression | tests/unit/routes/ + lead_intelligence/ + services/campaign + tasks/ | 1245 passed, 1 skipped (Windows-specific, pre-existing) |
| Import | `import app.tasks.campaign_tasks` → `launch_campaign_run` registered | ok |

**Fix trong verify round (reviewer tự bắt):**
- `_launch_campaign_run` từ plain function → lazy proxy class có `.apply_async` (runtime AttributeError nếu không mock).
- `campaign_tasks` except block thiếu `session.rollback()` → PendingRollbackError risk; đồng thời đưa `session.get` lookup + spec parse vào trong try để MỌI failure (kể cả LookupError) đều finalize 'failed' — run không kẹt 'running'.
- `/execute` có `response_model=LeadGenOrchestratorResult` filter nuốt response async `{campaign_id, run_id, status:'queued'}` → bỏ response_model.
- POST create trả 200 → 201 đúng spec CREATE_OK.
- `_FakeSession.execute`: skip `set_config` (7 GUC calls từ `set_request_tenant_context` — lệch queue kết quả); `_campaign(payload=None)` sentinel fix (trước không thể tạo implicit campaign → wire-fallback test "pass nhầm").

**Risk ghi chú:** FE `launchCampaign` (`leads-api.service.ts:232`) parse response bằng `campaignSchema` nhưng spec pin launch trả run-shape `{id, campaign_id, status:'queued', trigger}` — nếu FE strict-parse sẽ lệch; cần reconcile phía FE (ngoài scope spec).
