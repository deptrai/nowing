# Deferred Work

## Deferred from: code review of 3-14-memory-injection-bounded-retrieval (2026-08-05)

- **Finding:** Over-materialization of candidates in `search.py` — `top_k*3` bounded materialization is acceptable for current corpus sizes.
  - **Action:** Marked `[x] [Review][Defer]` in `3-14-memory-injection-bounded-retrieval.md`.
  - **Reason / when to revisit:** Revisit if corpus grows beyond ~1M rows or if p95 memory pressure becomes measurable in AC-3 latency evidence.

- **Finding:** RRF ranking tie-break tests are missing exhaustive coverage.
  - **Action:** Marked `[x] [Review][Defer]` in `3-14-memory-injection-bounded-retrieval.md`.
  - **Reason / when to revisit:** Add dedicated tie-break tests once AC-3 p95 latency is stable and the search ordering contract is frozen.

- **Finding:** `_is_templated` does not detect Jinja control-flow tags (`{% ... %}`).
  - **Action:** Marked `[x] [Review][Defer]` in `3-14-memory-injection-bounded-retrieval.md`.
  - **Reason / when to revisit:** Current automation templates use value placeholders only; upgrade when control-flow templates are used in production.

- **Finding:** D10 / D5 non-automation scope matrix not addressed in chunk B.
  - **Action:** Marked `[x] [Review][Defer]` in `3-14-memory-injection-bounded-retrieval.md`.
  - **Reason / when to revisit:** Covered by spec and route/MCP tests; revisit if a new non-automation surface is added.

## Deferred from: code review of 8-12-workspace-limits (2026-08-04)

- **Finding:** Storage sum does not reconcile deleted backend files — `workspace_limits.py:199-209`.
- **Action:** Marked `[x] [Review][Defer]` in `8-12-workspace-limits.md`.
- **Reason / when to revisit:** `sum_storage_bytes` sums `DocumentFile.size_bytes` from DB rows. If a storage backend file is deleted without deleting the `DocumentFile` row (or vice versa), the metric drifts. Storage limits are soft/exploratory in Story 8.12. Revisit when storage enforcement is implemented.

- **Finding:** Disable/enable Invite member and Upload affordances based on limits — `workspace-limits-manager.tsx`.
- **Action:** Marked `[x] [Review][Defer]` in `8-12-workspace-limits.md`.
- **Reason / when to revisit:** The backend is the source of truth for limit enforcement. The settings limits page is visibility/upgrade only. UI affordance gating in the team/invite and document upload flows is a defense-in-depth UX improvement that should be picked up when the product wants to reduce failed-action feedback loops for plan-limited workspaces.

## Deferred from: code review of story 11.1

- **Finding:** Concurrent `PATCH /users/me/notification-preferences` updates can lose keys because `_merge_notification_preferences` reads the user row, merges in memory, and overwrites the whole JSONB column.
- **Action:** Marked `[x] [Review][Defer]` in `11-1-telegram-notification-foundation.md`.
- **Reason / when to revisit:** Resolving this correctly requires either `SELECT FOR UPDATE` on the user row or an optimistic lock on `updated_at` so overlapping patches merge against the latest value atomically. This is a real correctness issue but is out of scope for the foundation story; it should be picked up when notification preferences expand beyond a single top-level key or when the endpoint is exposed to higher concurrency (e.g., user-facing automation toggles from multiple devices).

## Deferred from: code review of 10-1-batdongsan-scraper (2026-08-03) — RESOLVED

- **Finding:** `ScrapeOutput.cost_micros` is set to 0 for degraded runs in `batdongsan.scrape/executor.py`, but `charge_capability` in `app/capabilities/core/billing.py` still debited the wallet via `_charge_platform_meter` when `output.billable_units > 0`, creating a mismatch between displayed cost and actual charge.
- **Action taken (2026-08-03):** Updated `_charge_platform_meter` in `app/capabilities/core/billing.py` to detect `output.degraded`, record a 0-cost `TokenUsage` audit row, and skip `service.charge`. This fix is cross-platform and applies to `batdongsan`, `muaban_bds`, and `chotot` platform scrapers.
- **Verification:** `ruff check app/capabilities/core/billing.py` ✅ / `pytest tests/unit/capabilities/test_billing.py -q` ✅ 63 passed / `pytest tests/unit/capabilities/batdongsan ...` ✅ 44 passed.

## Deferred from: code review of 7-7-mcp-server-tool-expansion (2026-08-05)

- Double-submit on `POST /automations/{id}/run` — no idempotency key; two concurrent POSTs create two PENDING runs. Pre-existing pattern (Telegram `/run` has same gap). Needs idempotency key or dedup lock.
- Double query in `RunService.launch` — `_authorize` loads automation via `session.get`, then `launch_run`→`resolve_active_automation` re-queries via `select`. Minor inefficiency; defensive double-check. Could pass the already-loaded automation into `launch_run`.
- Celery `apply_async` failure leaves run stuck PENDING — no rollback of the persisted run row if enqueue fails. Pre-existing dispatch pattern (`launch_run` commits before `apply_async`).
- No test for provider-down SSE scenario (connection reset mid-stream in `nowing_chat`). Test gap — `stream_sse` raises `ToolError` on `httpx.RequestError` but no test covers mid-stream reset.
- No test for credit/quota exhaustion during chat (402 mid-stream). Test gap — `_FAILURE_HINTS[402]` exists but no chat test asserts the 402 path.

## Deferred from: code review of 2-6-indeed-jobs-scraper (2026-08-08)

- No timeout on detail page fetch — `scraper.py:590-622` calls `WebCrawlerConnector.crawl_url()` and `StealthyFetcher.fetch()` without explicit timeout. Would need architectural change to thread timeout through connector. Pre-existing pattern across all scrapers.
- No test for multi-page pagination — `test_scraper.py` tests `max_items=2` but doesn't test `max_pages > 1`. Test gap, not a code bug.
- Billing rate 5000 vs spec's recommended 3500 — `INDEED_SCRAPE_MICROS_PER_ITEM` defaults to 5000, spec recommends ~3500. Business decision, not a code bug.

## Deferred from: code review of 2-10-exa-mcp-search-connector (2026-08-08)

- Registry shared across concurrent tool calls — pre-existing pattern from capability tools; LangGraph state merge handles reconciliation. Not introduced by this diff.

## Deferred from: code review defer items resolution (2026-08-08)

- source_spec: none
  summary: Robustness improvements (15 items) — provider validation, negative days validation, SSN pattern, case sensitivity, exception swallowing, DB CHECK constraint, HMAC workspace hash, DB error handling, max_queries upper bound, large output handling, race conditions, empty string output, API key whitespace, no pagination, counter persistence
  evidence: Split from multi-goal defer resolution. Each improvement is an independent guard. Low priority — code works correctly for happy paths.

- source_spec: none
  summary: Architectural decisions (8 items) — cost tracking vs call count, top_k/max_passages_per_doc clamping location, quality mode ChainLens conditional gating, no pagination on list endpoint, change provider on connection with models, API key whitespace trimming, counter persistence with timestamp expiration, document_retention_days migration backfill default
  evidence: Split from multi-goal defer resolution. Each item needs a design decision before implementation can begin.

- source_spec: none
  summary: Pre-existing/cross-package issues (7 items) — JSON regex nesting, judge error logging, MCP sources validation, AC-6 REST test, JSON regex for flat objects, AC-1/AC-5 test gaps, document_retention_days migration backfill
  evidence: Split from multi-goal defer resolution. These belong to other packages and should be addressed when those packages are refactored.

- source_spec: none
  summary: Internal sync queries missing archived_at filter (3 items) — local folder dedup (documents_routes.py:1728), local folder upsert (documents_routes.py:1948), all folder docs for subtree (documents_routes.py:2011)
  evidence: Split from multi-goal defer resolution. These queries need analysis of sync behavior with archived documents before adding the filter — adding it blindly could break folder sync.

## Deferred from: test gap closure review (2026-08-08)

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Archived doc search test could pass for wrong reason — add negative assertion that both chunks exist in DB before verifying search filters archived
  evidence: Blind Hunter BH-3. Test creates visible+archived docs with identical content but doesn't verify both chunks exist in DB before asserting search results.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Zero sync Playwright test has no skip condition for missing backend — test fails in CI if Zero services not running
  evidence: Edge Case EC-8. Test file has comment about requiring backend but no programmatic skip.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Quality eval tests depend on gate.yaml file existing — need to verify helper handles missing/malformed file
  evidence: Edge Case EC-9. Tests read live gate.yaml via _load_chat_gate() but no explicit missing-file handling visible.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Playwright data retention tests don't use try/finally for workspace cleanup — workspace leaks if test fails mid-execution
  evidence: Edge Case EC-12. Cleanup only at end of test body, not in finally block.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Sampler test session context manager doesn't handle exceptions in __aexit__ — DB state may corrupt on test failure
  evidence: Edge Case EC-4. _SessionCM.__aexit__ returns None without rollback.

- source_spec: `_bmad-output/implementation-artifacts/spec-review-test-gaps.md`
  summary: Revalidation failure test doesn't assert mock executor was called — test passes even if code path doesn't reach executor
  evidence: Edge Case EC-15. AsyncMock with side_effect but no call_count assertion.

## Deferred from: code review of 9-3-latency-budget-state-a-b-gate (2026-08-08)

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: KB fallback cost hardcoded to 0 — executor.py:863-864 hardcodes kb_fallback_embedding_cost_micros=0 and kb_fallback_search_cost_micros=0. No actual billing impact (0+0=0) but KB fallback costs are never measured.
  evidence: Blind Hunter BH-3. Future enhancement to measure KB embedding/search costs.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Redis event bus subscribe failure state leak — on subscribe timeout, channel stays in subscribers but Redis subscription failed. Cross-replica delivery fails silently.
  evidence: Blind Hunter BH-4. Pre-existing v1 pattern in events_redis.py.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Agent rate limiting per-worker in-memory fallback without coordination — when Redis down, each worker maintains own counter. Defense-in-depth, not primary security.
  evidence: Blind Hunter BH-5. Architectural, not introduced by this story.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Migration 185 no backfill for existing rows — new columns (e2e_ms, ttfb_ms, resolved_mode, mode_requested) are nullable, existing rows have NULL. Admin route handles via COALESCE.
  evidence: Blind Hunter BH-10 + Edge EC-14. Nullable columns intentional.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Notification lacks idempotency guard — _notify_terminal could create duplicate notifications if called multiple times. Best-effort notification, not critical.
  evidence: Blind Hunter BH-11. Best-effort path.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Deliverable race condition on concurrent requests — two concurrent POST /deliverable could both pass existing is None check. Low probability, JSONB query.
  evidence: Blind Hunter BH-12. Low probability edge case.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Redis publish/listener/backoff issues (3 merged) — publish failure silently drops cross-replica events; 1-second backoff window loses events; no exponential backoff on connection failures.
  evidence: Edge Case EC-4, EC-5, EC-11. Pre-existing v1 pattern in events_redis.py.

- source_spec: `_bmad-output/implementation-artifacts/9-3-latency-budget-state-a-b-gate.md`
  summary: Platform billing changes (VN_BDS) outside story scope — billing.py includes VN_BDS_AGGREGATE_QUERY, BATDONGSAN_ITEM, CHOTOT_BDS_ITEM, MUABAN_BDS_ITEM changes that belong to Story 10.x.
  evidence: Acceptance Auditor AA-8. Scope creep but not harmful.

## Tech Debt Stories (created 2026-08-08 — Winston backlog audit)

The following 4 deferred items have been promoted to dedicated tech-debt stories in `sprint-status.yaml` under the `tech-debt` epic. Story files to be created when promoted to `ready-for-dev`.

### td-1: Idempotency key for POST /automations/{id}/run
- **Source:** 7-7 code review defer
- **Issue:** Double-submit on `POST /automations/{id}/run` — no idempotency key; two concurrent POSTs create two PENDING runs. Pre-existing pattern (Telegram `/run` has same gap).
- **Fix:** Add idempotency key or dedup lock (Redis SETNX or DB unique constraint on `(automation_id, idempotency_key)`).
- **Priority:** P2 — low probability but creates duplicate runs.

### td-2: Redis event bus subscribe failure state leak
- **Source:** 9-3 code review defer
- **Issue:** On subscribe timeout, channel stays in `subscribers` dict but Redis subscription failed. Cross-replica delivery fails silently.
- **Fix:** Remove channel from `subscribers` on subscribe failure; add retry with exponential backoff.
- **Priority:** P2 — pre-existing v1 pattern in `events_redis.py`.

### td-3: Storage sum does not reconcile deleted backend files
- **Source:** 8-12 code review defer
- **Issue:** `sum_storage_bytes` sums `DocumentFile.size_bytes` from DB rows. If a storage backend file is deleted without deleting the `DocumentFile` row (or vice versa), the metric drifts.
- **Fix:** Add reconciliation job that compares DB rows vs storage backend; or add `ON DELETE CASCADE` + storage backend webhook.
- **Priority:** P2 — storage limits are soft/exploratory in Story 8.12.

### td-4: Concurrent notification preference merge race condition
- **Source:** 11-1 code review defer
- **Issue:** Concurrent `PATCH /users/me/notification-preferences` updates can lose keys because `_merge_notification_preferences` reads the user row, merges in memory, and overwrites the whole JSONB column.
- **Fix:** Use `SELECT FOR UPDATE` on the user row, or optimistic lock on `updated_at`, or PostgreSQL `jsonb_set` for atomic merge.

### td-5: title_gen.py lacks timeout/retry on litellm.acompletion
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `app/tasks/chat/streaming/flows/new_chat/title_gen.py` calls `litellm.acompletion()` without explicit `timeout` or `num_retries`, using LiteLLM defaults (60s+ timeout, 2 retries). Same class of bug as the infinite-save fix — can hang chat title generation for 120s+ on slow/flaky models.
- **Fix:** Add `timeout=15.0, num_retries=1` to the `acompletion` call.
- **Priority:** P1 — affects chat UX on slow models.

### td-6: verify_chat_image_capability.py lacks num_retries
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `scripts/verify_chat_image_capability.py` calls `litellm.acompletion` and `litellm.aimage_generation` with explicit timeouts (60s, 120s) but no `num_retries`, using LiteLLM default 2 retries. Diagnostic script could hang in CI.
- **Fix:** Add `num_retries=1` to both calls.
- **Priority:** P3 — diagnostic script, not production code.
