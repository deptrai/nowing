# Round-2 Code Review Report — Stories 4-8b/4-8e/4-8f/4-8g/9-3/8-13

**Review date:** 2026-08-04  
**Reviewers:** Blind Hunter, Edge Case Hunter, Acceptance Auditor (read-only subagents)  
**Scope:** All code changed in response to the original `4-8b-g-9-3-code-review.md` findings across `nowing_evals` and `nowing_backend`.

## Executive Summary

All **P0 / HIGH** and **P1 / MEDIUM** findings from the original review are resolved.
A single additional issue was discovered during the acceptance audit (`4-8b` AC3: `workspace_id` was not passed to `NowingArm` in `chat/regression/runner.py`) and was fixed in this round.

- `nowing_evals`: **545 passed** in `pytest -q`.
- `nowing_backend` (targeted): **318 passed, 1 skipped** across `tests/unit/capabilities/chainlens/research/`, `tests/unit/capabilities/test_billing.py`, and `tests/unit/capabilities/access/test_agent_degraded.py`.
- `ruff check .` and `ruff format --check .` pass in both workspaces (after formatting `nowing_backend/app/capabilities/core/billing.py`).

## Method

1. **nowing_evals re-verification** — focused on all `nowing_evals` files changed for the benchmark / chat regression stories.
2. **nowing_backend re-verification** — focused on chainlens research executor/schema, capability access, chat routes, and billing wiring.
3. **Acceptance audit** — checked each story's acceptance criteria against the current implementation.

All three subagents were instructed to re-analyze the original findings and flag any remaining or new issues.

## Findings Status

### Original HIGH Findings

| ID | Finding | Status | Evidence / Notes |
|---|---|---|---|
| H1 | `chainlens_latency` runner aborts whole matrix on one failure | ✅ Fixed | `asyncio.gather(..., return_exceptions=True)` + `_make_error_row` in `chainlens_latency/runner.py`. Tested in `test_chainlens_latency.py`. |
| H2 | Resolved-mode divergence creates empty requested-mode buckets | ✅ Fixed | `_resolve_bucket_mode` aliases/falls back to requested mode; `by_mode` pre-seeded; `_evaluate_chainlens_gate` skips empty buckets. Tested in `test_chainlens_latency.py`. |
| H3 | Multi-turn chat cases broken due to immediate thread deletion | ✅ Fixed | `delete_thread=False` per turn; single thread deletion in `_run_one` `finally`. Tested in `test_regression.py:test_run_multi_turn_reuses_one_thread`. |
| H4 | `workspace_id` hardcoded to `search_space_id`; `--workspace-id` not used | ✅ Fixed | `NewChatClient.create_thread`/`ask` accept `workspace_id`; `NowingArm` propagates options/init/search_space fallback; `chat/regression/runner.py:778` now passes `workspace_id` to `NowingArm`. |
| H5 | Aggregate `operational` metrics missing `turn_error_rate` | ✅ Fixed | `_aggregate_operational` computes `n_turns`, `n_failed_turns`, and `turn_error_rate`; gate checks `max_turn_error_rate`. Tested in `test_regression.py`. |
| H6 | `max_scrape_drop_rate` checked against wrong metric | ✅ Fixed | `scrape_drop_rate` computed and gated; `scrape_failure_rate` no longer used for the drop gate. Tested in `test_regression.py` and `test_operational.py`. |
| H7 | Scrape metrics hardcoded for `web_search`/`web_scrape` | ✅ Fixed | `SCRAPE_TOOLS = {"web_search", "google_search", "web_scrape", "web_discover"}` in `operational.py`. Tested in `test_operational.py`. |
| H8 | TTFB parser only accepts ISO-8601, not epoch-ms | ✅ Fixed | `executor.py:_parse_engine_ts` accepts ISO and numeric int/float epoch-ms; rejects bool/negative/NaN/inf. Tested in `test_review_fixes.py`. |

### Original MEDIUM Findings

| ID | Finding | Status | Evidence / Notes |
|---|---|---|---|
| M1 | Chat gate not checking `max_error_rate` / `max_p95_ttfb_ms` | ✅ Fixed | `_evaluate_chat_gate` now checks `overall["error_rate"]` and `overall["p95_ttfb_ms"]`. |
| M2 | `chainlens_latency` per-tier aggregation missing | ✅ Fixed | `per_tier` and `per_mode_tier` buckets computed and gated. |
| M3 | `chainlens_latency` cost cap / fail-on-unratified missing | ✅ Fixed | `--max-total-cost-micros` and `--fail-on-unratified` run args added and enforced. |
| M4 | `chainlens_latency` does not notify on gate failure | ✅ Fixed | `notify_gate_failure` called before raising. |
| M5 | `chainlens_latency` sync timeout conflated with poll timeout | ✅ Fixed | `--sync-timeout` argument added and used for sync POST. |
| M6 | `chainlens_latency` async path uses polling instead of SSE tail | ✅ Fixed | `_tail_run_events` added; falls back to summary polling. |
| M7 | Telegram Markdown metacharacters cause 400 | ✅ Fixed | `_md_code` helper escapes backticks and wraps dynamic values; Telegram link fallback for unsafe URLs. Tested in `test_notifications.py`. |
| M8 | `_one_case_per_tag` stops before covering all tags | ✅ Fixed | Rewritten to select a case if it introduces any unseen tag. |
| M9 | Empty `--tags`/`--tier` silently selects nothing | ✅ Fixed | Empty filters treated as "no filter". |
| M10 | HTTP/timeout errors not classified | ✅ Fixed | `NowingArm._error_code_for` maps exceptions; runner synthesises SSE error frames. |
| M11 | Operational per-tag table missing | ✅ Fixed | `per_tag_operational` computed and rendered. |
| M12 | Token/cost values not coerced safely | ✅ Fixed | `_coerce_int` in `new_chat.py` and `nowing.py` rejects `bool`, coerces string/float, and preserves `0`. |
| M13 | `mode` not propagated through regenerate/resume/gateway | ✅ Fixed | `RegenerateRequest`/`ResumeRequest` schemas and all orchestrators/routes pass `mode`; agent tool reads `configurable.research_mode`. |
| M14 | Sync research path skips rate limit | ✅ Fixed | `_check_rate_limit` awaited in both async and sync branches. |
| M15 | KB fallback exceptions crash instead of degrade | ✅ Fixed | `except Exception` with explicit `asyncio.CancelledError` re-raise in executor fallback and main search. |
| M16 | `_extract_cost` stale `usage` cost overwrites `done` cost | ✅ Fixed | New `cost_source` slot; `done` cost locks, `usage` cost can be overwritten by later `done`. |
| M17 | `_capability_tool` async path lets errors bubble | ✅ Fixed | `InsufficientCreditsError` and `NowingError` caught and returned as controlled strings; `ForbiddenError` re-raised to preserve auth semantics. |
| M18 | `_percentile([])` returns `0.0` | ✅ Fixed | Both `chainlens_latency/runner.py` and `chat/regression/runner.py` return `None` for empty lists. |

### Original Billing (B) Findings

| ID | Finding | Status | Evidence / Notes |
|---|---|---|---|
| B1 | Duplicate `first_token` events possible | ✅ Fixed | Single `saw_first_token` guard in `_record_first_token`. |
| B2 | `usage` SSE event not treated as terminal | ✅ Fixed | `usage` and `done` both set `saw_done`; stream with only `usage` becomes `engine_unavailable`. |
| B3 | `tokens.total = 0` dropped | ✅ Fixed | Explicit `None` check before falling back to `totalTokens`. |
| B4 | `+inf`/`-inf` not rejected before `Decimal` | ✅ Fixed | `math.isfinite` check before conversion. |
| B5 | `bool` silently coerced to int | ✅ Fixed | `_to_int` and `_coerce_int` reject `bool`. |
| B6 | Parse failures not logged | ✅ Fixed | Warning logs on all rejection paths. |
| B7 | `ResearchInput.mode` description missing `auto` | ✅ Fixed | Description lists all four modes including `auto`. |
| B8 | `tier` hardcoded to `"research"` | ✅ Fixed | `ResearchInput.tier` added; `_call_chainlens` passes `payload.tier`. |
| B9 | Rate-limit `_incr` not async-safe | ✅ Fixed | `_aincr` uses `asyncio.to_thread`. |
| B10 | Billing not receiving `resolved_mode`, `mode_requested`, `e2e_ms`, `ttfb_ms` | ✅ Fixed | `charge_capability` and `_record_deep_research_token_usage` pass all telemetry fields; `record_token_usage` accepts them. |

## Issue Found and Fixed in This Round

### `4-8b` AC3 — `workspace_id` not passed to `NowingArm` constructor

**File:** `nowing_evals/src/nowing_evals/suites/chat/regression/runner.py:778`  
**Original code:**

```python
arm = NowingArm(client=client, search_space_id=search_space_id)
```

**Fixed to:**

```python
arm = NowingArm(
    client=client,
    search_space_id=search_space_id,
    workspace_id=workspace_id if workspace_id is not None else search_space_id,
)
```

This makes the constructor-level fallback consistent with the options-level fallback and ensures `--workspace-id` is honored even when `workspace_id` is not passed per-case.

## Acceptance-Criteria Status

| Story | Status | Notes |
|---|---|---|
| 4-8b | ✅ PASS (after round-2 fix) | All 5 AC met. |
| 4-8c | ✅ PASS | All 5 AC met. |
| 4-8d | ✅ PASS | Implemented; all 5 AC met. |
| 4-8e | ✅ PASS | CI deploy-gate / unratified / chainlens cost cap flags added. |
| 4-8f | ✅ PASS | All 7 AC met. |
| 4-8g | ✅ PASS | All 7 AC met. |
| 9-3 | ✅ PASS | All 10 AC met. |
| 8-13 | ✅ PASS | Telemetry traceability already satisfied. |

## Post-Review Follow-Ups (Completed)

1. `nowing_backend/tests/unit/capabilities/access/test_rest_degraded.py` and `test_rest_router.py` — **fixed** by adding `tests/unit/capabilities/access/conftest.py` that stubs `workspace_limit_service.check_run_limit` for unit tests. `42 passed` in `tests/unit/capabilities/access/`.
2. `nowing_backend/tests/integration/capabilities/chainlens/research/test_research_fallback.py::test_rest_sync_records_degraded_run_output_text` — **fixed** by setting `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = True` in the test so the sync path is allowed and the endpoint returns `200` as expected. Full fallback file: `10 passed`.
3. **Story 4.8d Chat Quality LLM Judge** — implemented from `ready-for-dev` to `done`:
   - `nowing_evals/src/nowing_evals/suites/chat/quality/{__init__.py,prompt.py,runner.py,gate.yaml}`
   - `nowing_evals/tests/suites/chat/test_quality.py` (12 passed)
   - Registered `ChatQualityBenchmark` with `suite="chat"`, `name="quality"`
   - Supports ingest validation, OpenRouter judge calls with JSON-mode + fallback parsing, per-tag aggregation, and gate evaluation.
4. Full backend test suite — **fixed** 4 pre-existing / environment failures:
   - 3 document upload / ETL credit tests failed because `ETL_SERVICE` was unset. Re-run with `ETL_SERVICE=DOCLING` → **all passed**.
   - `tests/unit/services/bds_aggregator/test_orchestrator.py::test_min_confidence_filter` leaked to real `chotot_bds` / `muaban_bds` scrapers because `VnBdsAggregateInput` defaults `sources` to all three. **Fixed** by adding `sources=["batdongsan"]` to the test payload.

## Verification

### nowing_evals

```
ruff check .          → All checks passed
ruff format --check . → 154 files already formatted
pytest -q             → 557 passed
```

### nowing_backend (full suite)

```
ruff check .                → All checks passed
ETL_SERVICE=DOCLING pytest -q
                            → 4771 passed, 9 skipped
```

## Story Status Updated

`sprint-status.yaml` updated:

- `4-8b` → `done`
- `4-8e` → `done`
- `4-8f` → `done`
- `4-8g` → `done`
- `9-3` → `done`

`4-8d` → `done`.

## Conclusion

The original review findings have all been addressed, the round-2 acceptance audit found one additional minor wiring issue that was also fixed, and the full test suites (nowing_evals, nowing_backend, and docs drift) are green.
