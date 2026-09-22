---
title: 'Story 39.7 — Decision Telemetry Dashboard + Cost Tracking'
type: 'feature'
created: '2026-09-22'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '87bed3a4cdb1210bfc189549dc3ab66c6a86d1e0'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Jev decision calls (39.2–39.5) already write `TokenUsage` rows (`usage_type='decision'`, `call_details` carries `task`/`model`/`backend`/`latency_ms`), but there is no admin surface to see call volume, latency, cost, or model drift — and `cost_micros` is always 0 because `_record_usage` never computes it. Per epics.md 39.7 admins need daily calls by task, median latency, accuracy when ground truth exists, total cost, a cost alert, and per-call model tracking.

**Approach:** Add a `DecisionTelemetryMixin` to `AdminTelemetryService` + two routes (`GET /admin/telemetry/decisions`, `POST /admin/telemetry/decisions/{id}/label` for ground-truth labels), compute `cost_micros` at write time in `_record_usage`, and mount a `DecisionTelemetryPanel` in the existing `/admin/telemetry` page's telemetry tab.

## Boundaries & Constraints

**Always:**
- Decision rows identified by `TokenUsage.usage_type == "decision"`; task = `call_details->>'task'`; latency = `e2e_ms` column; model = `call_details->>'model'`; backend = `call_details->>'backend'`. No schema migration — all fields already exist.
- Median via `func.percentile_cont(0.5).within_group(TokenUsage.e2e_ms.asc())` — precedent: `app/routes/admin_latency_routes.py:89`. Take `window_hours` (not days) like every sibling endpoint and reuse `_clamp_window`/`_cutoff`/`_granularity`/`_make_time_bucket_expr` — day buckets come free for window_hours > 48.
- JSONB expressions: `TokenUsage.call_details.has_key("correct")` (the `?` operator), `call_details["correct"].as_boolean()`, `call_details["task"].as_string()` / `["model"].as_string()` / `["backend"].as_string()` — same `as_string()` style as `_provider_expr`/`_model_expr`.
- Cost at write time in `DecisionService._record_usage`: jev → `round(input_tokens * DECISION_JEV_COST_PER_BTOK_INPUT_USD / 1e9 * 1e6)` micros; llm_json → `litellm.cost_per_token(model, prompt_tokens, completion_tokens)` summed ×1e6, `try/except → 0` (unknown model must not break telemetry). New env: `DECISION_JEV_COST_PER_BTOK_INPUT_USD` default `42.0` ($42/Btok input, output free — matches `scripts/jev_eval/runner.py` and ARCHITECTURE-SPINE ~$0.00002/call).
- Accuracy = `correct/labeled` over rows where `call_details ? 'correct'` — `null` (not 0) when no labeled rows. Ground truth is set post-hoc via the label endpoint which merges `{"correct": bool}` into `call_details` (reassign a new dict — JSONB mutation tracking is off).
- Cost alert: when today's UTC decision cost > `DECISION_DAILY_COST_ALERT_USD` (env, default `10.0`), insert `AdminHealthAlert(service_id="decision.jev_daily_cost", severity="high", message=...)` — but only if no `open`/`acknowledged` alert with that `service_id` exists (dedupe). The telemetry page's existing `AlertBanner`/`getActiveAlerts` poll renders it with zero new UI plumbing; the GET response also carries `cost_alert.exceeded` for an immediate inline banner.
- Drift: response carries `models[]` (distinct model+backend with calls/first_seen/last_seen) + `pinned_model` (`decision_config.DECISION_JEV_MODEL`) + `drift_detected` = any jev row's model != pinned, or >1 distinct jev model in window. When `jev-latest` alias moves upstream, the new model string appears → drift_detected.
- Both routes `Depends(require_superuser)`, same as all `/admin/telemetry/*`.
- Read-only endpoints must not write except the deduped alert insert; the label POST is the only mutator (explicit `session.commit()` like `purge_celery_queue`).
- Coverage honesty: only consumers that forward `session` produce rows — `jev_router` does this itself when `telemetry_ok` (:190-205), so `task="routing"` always shows when the flag is on; `check_passage`/`classify_intent`/`filter_passages` deliberately pass no session (39.4/39.5) → their tasks appear only where a caller forwards one. Dashboard missing tasks is expected, not a bug — document in the panel ("tasks appear as their callers opt into telemetry").

**Never:**
- No new DB tables/migrations; no Celery beat job (alert evaluation is on-read — see Design Notes).
- No Prometheus/observability-metrics wiring — `TokenUsage` is the single source.
- No changes to `decide()` signature or the question registry; no behavior change to decision consumers.
- No auto-labeling of ground truth — `correct` is only set by admin PATCH (never inferred from confidence).
- No `_bmad/marketing-growth` submodule or unrelated dirty files in the commit.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | 10 decision rows today, mixed tasks | `daily[]` grouped by (date,task) with calls+median+cost; `totals`/`by_task` consistent; `cost_micros` > 0 | N/A |
| NO_DATA | zero decision rows | zeros, `accuracy=null`, `models=[]`, `drift_detected=false`, no alert | N/A |
| ACC_LABELED | 4 labeled rows, 3 correct | `accuracy=0.75`, `labeled=4` | N/A |
| ACC_NONE | rows exist, none labeled | `accuracy=null`, `labeled=0` — never 0.0 | N/A |
| ALERT_FIRE | today cost > threshold, no open alert | `cost_alert.exceeded=true` + one `AdminHealthAlert` row | insert failure → warning log, response still returns |
| ALERT_DEDUP | exceeded + open alert exists | `exceeded=true`, zero new rows | N/A |
| ALERT_ACKED | exceeded + only acknowledged alert | `exceeded=true`, no new row (admin already saw it) | N/A |
| DRIFT | jev rows with model `jev-1.13.0` + `jev-1.14.0` | `models` lists both; `drift_detected=true` | N/A |
| COST_WRITE | `decide()` jev call, 500 input tokens | `cost_micros=21` on the TokenUsage row | pricing exc → 0, never aborts |
| COST_LLM | llm_json backend, known model | `cost_micros` via litellm; unknown model → 0 | `try/except → 0` |
| LABEL | POST label `{correct:false}` on decision row | `call_details.correct=false`, next GET counts it | N/A |
| LABEL_404 | label on nonexistent/non-decision id | 404 | HTTPException |
| WINDOW | `window_hours=0` or `>720` | clamped via `_clamp_window` to [1,720] | N/A |
| AUTH | non-superuser | 403 via `require_superuser` | existing dep |

</frozen-after-approval>

## Code Map

- `app/services/decision/service.py` — `_record_usage` (:372-431): currently omits `cost_micros`; add computed value to the `record_token_usage` call. `_pinned_model` (:443) shows config pattern.
- `app/services/decision/types.py` — `BackendResult{model,latency_ms,input_tokens,output_tokens}` (:67-74); no `cost` field — compute in service, do NOT extend the dataclass.
- `app/config/decision.py` — add `DECISION_JEV_COST_PER_BTOK_INPUT_USD` + `DECISION_DAILY_COST_ALERT_USD` (+ `__all__` entries), same `os.getenv` pattern as `DECISION_JEV_MODEL` (:65).
- `app/services/admin_telemetry/service.py` — `AdminTelemetryService(CostTelemetryMixin, ...)`; add `DecisionTelemetryMixin` to the bases; `_token_filters`, `_cutoff`, `_granularity` already exist.
- `app/services/admin_telemetry/decisions.py` — NEW mixin: `get_decision_telemetry(window_hours, workspace_id)` + `label_decision(usage_id, correct)`; reuse `_cutoff`/`_token_filters`/`_make_time_bucket_expr` from `service.py`/`_helpers.py`.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/jev_router.py` — the ONLY guaranteed telemetry producer: opens `async_session_maker()` + commits when `telemetry_ok` (:177-205). Other consumers forward no session → log-only.
- `app/services/admin_telemetry/costs.py` — SQL style precedent (`func.coalesce(func.sum(...)...)`, JSONB `as_string()` extraction).
- `app/models/admin_health.py` — `AdminHealthAlert(service_id,status,severity,message)` (:102-137); dedupe query = `service_id=="decision.jev_daily_cost"` + `status.in_(["open","acknowledged"])`.
- `app/routes/admin_telemetry_routes.py` — mount `GET /decisions` + `POST /decisions/{usage_id}/label` on existing `router` (prefix `/admin/telemetry`, registered `app/routes/__init__.py:248`); file convention is GET + POST only (see `purge_celery_queue`).
- `app/schemas/admin_telemetry.py` — add response/request pydantic models (same `ConfigDict(from_attributes=True)` style).
- `tests/unit/services/test_admin_telemetry_service.py` — `_Row`/`_MockResult`/`AsyncMock` session pattern to reuse.
- `nowing_web/lib/apis/admin-telemetry-api.service.ts` — add `DecisionTelemetry` types + `getDecisionTelemetry()` + `labelDecision()` via `baseApiService`.
- `nowing_web/components/admin/telemetry/LlmCostPanel.tsx` — panel convention: `"use client"`, `useTranslations("admin")`, Recharts (`recharts` already imported), `tick` prop for refresh.
- `nowing_web/app/admin/telemetry/page.tsx:244-249` — mount `<DecisionTelemetryPanel tick={tick}/>` inside telemetry `TabsContent`.
- `nowing_web/messages/{en,vi,es,hi,ko,pt,zh}.json` — add `admin.telemetry.*` keys (en+vi real translations, rest English copy — convention from commit `49f62a32f`).

## Tasks & Acceptance

**Execution:**
- [ ] `app/config/decision.py` — add `DECISION_JEV_COST_PER_BTOK_INPUT_USD` (42.0) + `DECISION_DAILY_COST_ALERT_USD` (10.0) + exports
- [ ] `app/services/decision/service.py` — `_record_usage` computes + passes `cost_micros` (jev formula; llm_json via `litellm.cost_per_token`, except→0)
- [ ] `app/services/admin_telemetry/decisions.py` — NEW mixin: aggregates (daily×task, by_task, totals, models, accuracy-over-labeled), deduped `AdminHealthAlert` insert, `label_decision` write logic
- [ ] `app/services/admin_telemetry/service.py` — add `DecisionTelemetryMixin` to bases
- [ ] `app/schemas/admin_telemetry.py` — `DecisionTelemetryResponse`, `DecisionDailyBucket`, `DecisionTaskBucket`, `DecisionModelBucket`, `DecisionCostAlert`, `DecisionLabelRequest`
- [ ] `app/routes/admin_telemetry_routes.py` — `GET /decisions?window_hours=&workspace_id=` + `POST /decisions/{usage_id}/label` (404 on missing/non-decision row; `session.commit()` after write)
- [ ] `tests/unit/services/test_admin_telemetry_decisions.py` — NEW: mock-session tests for every I/O matrix row (aggregations, accuracy-null, alert dedup/acked, drift, clamp)
- [ ] `tests/unit/services/decision/` — extend existing record-usage tests: jev cost formula, llm_json litellm path + unknown-model→0, pricing exception never aborts
- [ ] `nowing_web/lib/apis/admin-telemetry-api.service.ts` — types + `getDecisionTelemetry` + `labelDecision` methods
- [ ] `nowing_web/components/admin/telemetry/DecisionTelemetryPanel.tsx` — NEW: KPI cards (calls, cost USD, median ms, accuracy|n/a), by-task table, calls/day stacked chart, models list + drift badge, cost-alert banner
- [ ] `nowing_web/app/admin/telemetry/page.tsx` + `messages/*.json` (7 locales) — mount panel + i18n keys

**Acceptance Criteria:**
- Given `DecisionService` calls logging to `TokenUsage`, when an admin views `GET /admin/telemetry/decisions`, then the response shows daily calls by task type, median latency, accuracy over labeled rows, and total cost — and the telemetry tab renders them.
- Given daily Jev cost exceeds `DECISION_DAILY_COST_ALERT_USD`, when the endpoint is read, then exactly one `AdminHealthAlert` fires (deduped) and the existing alerts banner surfaces it.
- Given calls recorded under different `call_details.model` values, when the alias moves, then `models[]` + `drift_detected` expose the change against `DECISION_JEV_MODEL`.

## Implementation Notes

**2026-09-22 — implemented (subagent)**

- **Files touched (backend):** `app/config/decision.py` (+`DECISION_JEV_COST_PER_BTOK_INPUT_USD`=42.0, +`DECISION_DAILY_COST_ALERT_USD`=10.0, exports); `app/services/decision/service.py` (new module-level `_decision_cost_micros`, called inside `_record_usage`'s fail-open try); `app/services/admin_telemetry/decisions.py` (NEW `DecisionTelemetryMixin`); `app/services/admin_telemetry/service.py` (added mixin to bases); `app/schemas/admin_telemetry.py` (+6 pydantic models); `app/routes/admin_telemetry_routes.py` (`GET /decisions`, `POST /decisions/{usage_id}/label`); `tests/unit/services/test_admin_telemetry_decisions.py` (NEW, 18 tests covering every I/O matrix row); `tests/unit/services/decision/test_service.py` (+5 cost tests).
- **Files touched (frontend):** `lib/apis/admin-telemetry-api.service.ts` (types + `decisionTelemetry` + `labelDecision`); `components/admin/telemetry/DecisionTelemetryPanel.tsx` (NEW); `app/admin/telemetry/page.tsx` (mounted inside telemetry `TabsContent`); `messages/{en,vi,es,hi,ko,pt,zh}.json` (+`admin.telemetry.decision_*` keys; en/vi translated, rest English copy).
- **Decisions:**
  - Response totals are flat fields on `DecisionTelemetryResponse` (`total_calls`/`total_cost_micros`/`median_latency_ms`/`labeled`/`correct`/`accuracy`) — the frozen matrix mentions `totals`/`by_task` consistency but the schema task list names no totals model, so flat fields keep the named-model list exact.
  - "Today's UTC decision cost" for the alert honors the `workspace_id` filter like every other metric in the response; the dedupe `service_id` stays global (`decision.jev_daily_cost`) as specced.
  - Only `backend_name == "jev"` uses the Btok formula and only `== "llm_json"` hits `litellm.cost_per_token`; `mock`/stub/unknown backends record `cost_micros=0` (unpaid calls must not fabricate spend). The spec only defines jev + llm_json.
  - Alert insert commits (precedent: `alert_engine.get_active_alerts` commits inside a GET) — `get_async_session` never commits, so an uncommitted insert would silently roll back.
  - Panel uses `useTranslations("admin")` + `t("telemetry.*")` per the spec's `admin.telemetry.*` key instruction; sibling panels use the top-level `telemetry.*` namespace — noted as an intentional divergence from sibling convention.
- **Surprises:** es/hi/ko/pt/zh locale files have no `admin` top-level key at all (they're partial locales); per spec convention each got a minimal `admin.telemetry` block with English copy. `tests/unit/services` has 35 pre-existing ruff errors in 12 untouched files (chainlens, wallet, anti-bot, etc.) — all files I touched are clean.

**2026-09-22 — reviewer pass 2 hardening (subagent)**

- `decisions.py`: `pg_advisory_xact_lock(hashtext('decision.jev_daily_cost'))` now precedes the alert dedupe SELECT inside `_record_cost_alert` — serializes concurrent first-inserters so two racing dashboard hits can't double-insert; transaction-scoped so it releases on the existing commit/rollback.
- `decisions.py`: correctness filter switched from `.as_boolean()` to `call_details["correct"].as_string() == "true"` — a non-boolean JSON value can no longer cast-fail and 500 the endpoint.
- `config/decision.py`: `math.isfinite` guards on both new env floats — `nan`/`inf` env values fall back to `42.0`/`10.0`.
- `admin_telemetry_routes.py`: removed `ge=1, le=720` from `window_hours` so out-of-range values reach the service `_clamp_window` (type coercion still 422s non-integers); label route gained `response_model=DecisionLabelResponse` + `@limiter.limit("30/minute")` (+`request: Request` arg required by slowapi).
- Tests: `test_admin_telemetry_decisions.py` — `_results()` gained the advisory-lock call slot; dedupe tests pin `DECISION_DAILY_COST_ALERT_USD` and assert the *compiled* statement filters `status IN ('open','acknowledged')`; new `test_compiled_sql_carries_decision_filter_and_dedupe_statuses` compiles every emitted statement (the mock session can't verify WHERE clauses); alert-insert test asserts `status='open'` and that the message carries both dollar values; route tests disable `limiter.enabled` (slowapi rejects a non-Request `request` arg). `decision/test_service.py` — `litellm.cost_per_token` stubbed in the two fallback tests (no real pricing lookups); the Jev cost test pins `DECISION_JEV_COST_PER_BTOK_INPUT_USD`.
- Frontend: `DecisionTelemetryPanel` — stacked-bar `dataKey` switched to a function accessor + `name` prop (task names containing `.` would be parsed as nested paths by Recharts); `aria-label` on the window `<select>` and workspace `<input>`; empty-state block when `daily`, `by_task` and `models` are all empty (`decision_empty` added to all 7 locales).
- **Triage:** all 14 reviewer items applied; none deferred. Advisory lock is the only behavior change beyond hardening — dedupe is now race-safe, not just status-filtered.

## Spec Change Log

## Review Triage Log

Review pass 1 (3 reviewers: backend-correctness, spec-compliance+tests, frontend+contract) — 20 findings, 14 patched, 6 rejected/noted:

- Dedupe check-then-insert TOCTOU → two racing GETs could double-insert, violating "exactly one" AC — **medium** → patch (`pg_advisory_xact_lock(hashtext(service_id))` before dedupe SELECT; `INSERT…WHERE NOT EXISTS` rejected — same phantom under READ COMMITTED).
- `call_details["correct"].as_boolean()` CAST raises on non-bool JSON → whole endpoint 500 — **low** → patch (`as_string() == "true"`; counts JSON `true` only, never raises).
- `window_hours` route `ge=1,le=720` → 422 instead of the matrix's `_clamp_window` clamp — **low** → patch (ge/le removed; non-int still 422s on type).
- `DECISION_DAILY_COST_ALERT_USD` accepts nan/inf → silently disables/always-fires alert — **low** → patch (`math.isfinite` guard, `_DECISION_TIMEOUT_RAW` pattern; JEV price guarded symmetrically).
- `POST /decisions/{id}/label` lacks `response_model` + rate limit vs sibling mutators — **low** → patch (`DecisionLabelResponse`, `@limiter.limit("30/minute")`).
- `test_cost_alert_dedupes_acknowledged` vacuous — mock identical to open-status test, status never inspected — **medium** → patch (compiled dedupe stmt asserts `status IN ('open','acknowledged')`).
- No test asserts SQL semantics under fully-mocked sessions — **medium** → patch (`test_compiled_sql_carries_decision_filter_and_dedupe_statuses`).
- Two `llm_json` tests make real `litellm.cost_per_token` calls — **low** → patch (stubbed to `(0.0, 0.0)`).
- Cost/alert tests depend on ambient env for pricing config — **low** → patch (monkeypatch-pinned config values).
- Alert insert payload only partially asserted — **low** → patch (asserts `status=="open"` + both dollar figures in message).
- Recharts `dataKey={task}` misparses dotted task names — **low** → patch (function accessor).
- Window `<select>`/workspace `<input>` lack `aria-label` — **low** → patch.
- No empty-state for NO_DATA response — **low** → patch (`decision_empty`, all 7 locales).
- Workspace-id input refetches per keystroke — **low** → patch rejected: matches `LlmCostPanel` convention exactly; debounce would diverge from siblings.
- `labelDecision` service method has no UI caller — **false**: spec requires the endpoint + client method only; label UI is out of scope.
- Alert cost honors `workspace_id` while dedupe `service_id` is global — **false**: documented spec decision (Implementation Notes).
- Frontend AC "tab renders them" outside backend diff scope — **false**: panel verified mounted `page.tsx:247` by contract reviewer.
- Partial locales (es/hi/ko/pt/zh) missing sibling `admin.*`/`telemetry.*` namespaces → raw key paths — **rejected as out-of-scope**: pre-existing gap, next-intl falls back to key rendering, no regression.
- Spec Never-list says "admin PATCH" while tasks/routes use POST — **false**: POST chosen per file convention; self-note only.
- `_bmad/marketing-growth` dirty-submodule marker — **rejected**: unrelated working-tree artifact, excluded from commit.

## Design Notes

- **On-read alert evaluation (not Celery beat):** the AC's trigger is "when an admin views decision metrics"; an `AdminHealthAlert` row persists once fired, so the first dashboard view after a breach creates it and the banner stays until acked/resolved — no scheduler plumbing needed. A periodic beat check is deferred-work if ops wants the alert to fire with zero page views.
- **Why `e2e_ms` not `call_details->>'latency_ms'`:** real column → cleaner `percentile_cont`, consistent with chat-latency precedent. `call_details` JSONB is only used for `task`/`model`/`backend`/`correct`.
- **Write-time cost, not read-time:** `cost_micros` is the canonical column that `LlmCostPanel`/gross-margin already sum — decision rows with cost>0 automatically enrich existing panels. Historical rows keep 0 (documented, not backfilled — volume is negligible so far).
- **Ground truth via PATCH, not eval runner:** `scripts/jev_eval` bypasses `DecisionService`+session so its runs never hit `TokenUsage`. Admin labeling of sampled production decisions is the honest data source for accuracy; an eval-persistence path is deferred-work if needed later.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/services/admin_telemetry app/services/decision app/routes/admin_telemetry_routes.py app/schemas/admin_telemetry.py app/config/decision.py tests/unit/services` — expected: clean
- `cd nowing_backend && uv run pytest tests/unit/services/test_admin_telemetry_decisions.py tests/unit/services/test_admin_telemetry_service.py tests/unit/services/decision -m unit -q` — expected: all pass
- `cd nowing_backend && uv run pytest tests/unit/ -m unit -q` — expected: no new failures vs baseline (7 phone-waterfall + 1 pat-static pre-existing)
- `cd nowing_web && npx tsc --noEmit` (or repo's typecheck script) — expected: clean
- `cd nowing_web && npx vitest run` on any touched test files — expected: pass

**Manual checks:**
- `GET /admin/telemetry/decisions` as superuser → JSON shape matches schema; POST label on a decision row → `correct` appears in next GET accuracy.
