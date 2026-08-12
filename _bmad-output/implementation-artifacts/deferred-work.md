## Deferred from: code review of story-12-4a-4b-normalize-dedupe-conflict round 2 (2026-08-13)

- **Finding:** Location filter fallback for unknown cities — when `resolve_city_code` returns None for both input and item, comparison falls back to raw lowercased strings.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** Only affects cities not in the 64-province table. Revisit if users query by district/ward level.

- **Finding:** New city codes (DNA/HAN/HOB/QNA/TNI/VP) in shared `location_normalize` module visible to BĐS aggregator.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** These are valid Vietnamese provinces; BĐS queries benefit. No regression — only new matches.

- **Finding:** Salary period inference missing English abbreviations ("hrly", "daily", "wkly", "mo", "yr", "annum").
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** All 3 VN job sources use full forms or Vietnamese. Revisit if a new source uses abbreviations.

- **Finding:** Unknown degradation reasons default to SOURCE_FAILED.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** Raw reason available in `source_breakdown[source].degradation_reason`. Revisit if monitoring needs finer granularity.

- **Finding:** No min<=max validation on salary values in `_salary_values`.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** Scraper responsibility. Revisit if scrapers send untrusted data.

- **Finding:** O(n²) dedupe within large company groups.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** Ponytail comment documents ceiling + upgrade path (sort by posted_at + windowing). Revisit if a single company exceeds 100+ listings per query.

## Deferred from: code review of story-12-4a-4b-normalize-dedupe-conflict (2026-08-12)

- **Finding:** Union-find path compression in `_union_find()` is not reused by the manual root-finding traversal at `dedupe.py:271-273`.
  - **Action:** Marked `[x] [Review][Defer]` in `12-4a-4b-normalize-dedupe-conflict.md`.
  - **Reason / when to revisit:** Negligible impact since n ≤ 20 per coarse group and traversal happens once per element. Revisit if dedupe scales to 1000+ listings per company.

## Deferred from: code review of 20-3-nowing-private-provider (2026-08-11)

- **Finding:** Typo `ChucksHybridSearchRetriever` in `app/retriever/chunks_hybrid_search.py` propagated to `private_provider.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `20-3-nowing-private-provider.md`.
  - **Reason / when to revisit:** Pre-existing class name; rename the retriever itself if a refactor pass touches it.

- **Finding:** Workspace access check fetches workspace then calls `check_workspace_access` non-atomically.
  - **Action:** Marked `[x] [Review][Defer]` in `20-3-nowing-private-provider.md`.
  - **Reason / when to revisit:** Same pattern used across many routes; revisit with a broader `get_workspace_with_membership` helper or row-level advisory lock.

## Resolved from: code review of 18-3-agent-registry (2026-08-10)

- **[x] Frontend admin agent-registry UI page**
  - Implemented `nowing_web/app/admin/agent-registry/page.tsx` with list, create, edit, delete, and client filter.
  - Added `contracts/types/admin-agent-registry.types.ts` and `lib/apis/admin-agent-registry-api.service.ts`.

- **[x] README / ops runbook seed command documentation**
  - Added `nowing_backend/README.md` with dev setup, test commands, seed instructions, and admin API table.
  - Added `_bmad-output/operations-artifacts/runbooks/agent-registry.md` ops runbook.

- **[x] Test coverage expansion**
  - Added PATCH, duplicate slug/name 409, unknown tool, unregistered client, soft-delete, list filter, and invalid-agent chat 404 tests.

- **[x] AgentConfig tool list catalog reconciliation**
  - Write-time validation now accepts the union of `MAIN_AGENT_NOWING_TOOL_NAMES` and `TOOL_CATALOG`.
  - The main chat runtime continues to build only main-agent tools; subagent/MCP dispatch is still environment-driven.

- **[x] Foreign key `agent_configs.client_id -> vertical_clients.client_id`**
  - Added `ForeignKey` on `AgentConfig.client_id` in `app/db.py`.
  - Added migration `2c422d15105e_add_agent_configs_client_id_fk.py`.

## Deferred from: code review of 18-2-newchatrequest-extension (2026-08-10)

- **Finding:** `_bounded_chat_metadata` list cap missing in reviewed diff but `MAX_PLATFORM_METADATA_LIST_LENGTH` already in HEAD (`37b3fe505`).
  - **Action:** Marked `[x] [Review][Defer]` in `18-2-newchatrequest-extension.md`.
  - **Reason / when to revisit:** The reviewed diff is not the final code; the list cap was added in a later review fix. No action needed unless a future review resets to the older diff.

- **Finding:** `regenerate`/`resume` session close — diff-only concern.
  - **Action:** Marked `[x] [Review][Defer]` in `18-2-newchatrequest-extension.md`.
  - **Reason / when to revisit:** Current code now commits/closes before streaming; verify in the next chunk review (orchestrator/input_state).

- **Finding:** Whitespace-only `client_id`/`agent_id` produces overlapping field/model errors.
  - **Action:** Marked `[x] [Review][Defer]` in `18-2-newchatrequest-extension.md`.
  - **Reason / when to revisit:** Cosmetic; the field-level `pattern`/`min_length` error is authoritative. Revisit if UX feedback says the double error is confusing.

- **Finding:** `AgentChatMessageCreate` conflates `external_metadata` and `platform_metadata` validators.
  - **Action:** Marked `[x] [Review][Defer]` in `18-2-newchatrequest-extension.md`.
  - **Reason / when to revisit:** Defer until product confirms whether `external_metadata` must stay flat for `TokenUsage`/`NewChatMessage` consumers or can adopt the nested `_bounded_chat_metadata` shape.

- **Finding:** `platform_metadata` persistence / `ResumeRequest` field gaps are tracked as decision-needed items.
  - **Action:** Resolved in `18-2-newchatrequest-extension.md` patch findings P-RESUME-FIELDS / P-METADATA-PERSIST.
  - **Reason / when to revisit:** `ResumeRequest` now exposes `client_id`/`agent_id`/`platform_metadata`; `platform_metadata` is persisted on `NewChatThread` (last-turn mirror) and `NewChatMessage` rows.

## Deferred from: code review of 18-8-rate-limiting-tenant-isolation (2026-08-10)

- **Finding:** Thiếu L2/L3/L5 tests theo threat model.
  - **Action:** Marked `[x] [Review][Defer]` in `spec-18-8-rate-limiting-tenant-isolation.md`.
  - **Reason / when to revisit:** Threat model §4.1 yêu cầu L1+L2+L3 cho CI gate và L4/L5 trước production; chỉ L1 được implement trong story. Bổ sung khi Epic 18 đạt production-readiness.

- **Finding:** `memory_relations` và `memory_versions` chưa có RLS/GUC.
  - **Action:** Marked `[x] [Review][Defer]` in `spec-18-8-rate-limiting-tenant-isolation.md`.
  - **Reason / when to revisit:** Các bảng phụ thuộc `memories` nhưng không có cột `client_id`/`workspace_id` và chưa có policy. Cần epic-level quyết định về tenant inheritance hoặc thêm RLS riêng khi mở rộng scope.

## Deferred from: code review of 12-2-topcv-scraper (2026-08-10)

- **Finding:** PII redaction tại scraper (AC-7).
  - **Action:** Marked `[x] [Review][Defer]` in `12-2-topcv-scraper.md`.
  - **Reason / when to revisit:** PII pipeline chưa tồn tại; xử lý tại Story 12.5 / Epic 20.1 (`to_chunks` + redactor) hoặc `app/services/jobs_aggregator/orchestrator.py`.

- **Finding:** `to_chunks()` helper (AC-8).
  - **Action:** Marked `[x] [Review][Defer]` in `12-2-topcv-scraper.md`.
  - **Reason / when to revisit:** `app/services/scraper_chunks/` chưa có; thuộc Epic 20.1 / AD-34.

- **Finding:** Capability registration MCP/REST/Billing (AC-9).
  - **Action:** Marked `[x] [Review][Defer]` in `12-2-topcv-scraper.md`.
  - **Reason / when to revisit:** Đã có sẵn trong skeleton (`definition.py`, `BillingUnit.TOPCV_JOB`, `app/capabilities/__init__.py`); không thuộc diff chunk 1.

- **Finding:** Location filter `location` (AC-1).
  - **Action:** Marked `[x] [Review][Defer]` in `12-2-topcv-scraper.md`.
  - **Reason / when to revisit:** TopCV dùng city IDs (`?locations=l1_l8`) và slug path `tim-viec-lam-<keyword>-tai-<city>-kl<id>`; cần mapping city→ID. Cần thu thập thêm từ TopCV hoặc product trước khi implement.

## Deferred from: code review of 18-1-public-agent-chat-endpoints (2026-08-09)

- **Finding:** `GET /threads/{thread_id}` / `agent_chat:thread:read` endpoint.
  - **Action:** Marked `[x] [Review][Defer]` in `18-1-public-agent-chat-endpoints.md`.
  - **Reason / when to revisit:** Not in 18.1 ACs; permission vocabulary `agent_chat:thread:read` hints at future scope. Revisit in Story 18.4+ when read surface is defined.

# Deferred Work

## Deferred from: code review of 12-1-vietnamworks-scraper (2026-08-10)

- **Finding:** `posted_at` full-ISO datetime không tương thích với `app/services/jobs_aggregator/normalize.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Cần cập nhật normalizer để parse full ISO datetime hoặc đổi scraper trả `datetime`; thuộc scope aggregator story 12.4.

- **Finding:** `salary_period_id:1` của VietnamWorks bị `normalize.py` map thành "hour" thay vì "month".
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** `_SALARY_PERIOD_MAP` chung cho nhiều nguồn, cần map theo nguồn hoặc sửa semantics; thuộc 12.4.

- **Finding:** Aggregate billing gate reserve base fee `VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY` nhưng charge path không cộng base fee.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Base fee chưa được cộng vào `cost_micros`; cần sửa orchestrator hoặc `_charge_vn_jobs_aggregate`; thuộc 12.4/12.5.

- **Finding:** `vn_jobs` subagent `load_tools` không validate `workspace_id` có thể `None`.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Thêm guard `workspace_id` hoặc fail fast khi build subagent; thuộc 12.4.

- **Finding:** `_gate_vn_jobs_aggregate` under-reserve cho child sources bill per page, `sources=[]` mặc định all sources, fallback `max_items_per_source=10` khác schema default 50.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Cần điều chỉnh gating logic cho aggregate job; thuộc 12.4/12.5.

- **Finding:** `_charge_vn_jobs_aggregate` có thể charge khi child output `degraded`.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Bổ sung kiểm tra `output.degraded` trước khi debit; thuộc 12.4/12.5.

- **Finding:** `PII_REDACTION_MIN_CONFIDENCE` config tồn tại nhưng chưa có logic sử dụng.
  - **Action:** Marked `[x] [Review][Defer]` in `12-1-vietnamworks-scraper.md`.
  - **Reason / when to revisit:** Gắn với PII redaction pipeline khi implement 12.5.

## Deferred from: code review of 10-5-anti-bot-captcha-screenshot-escalation (2026-08-09)

- **Finding:** Billing tracking cho screenshot storage — cần quyết định PM/Architect về billing unit; chưa có trong token_tracking_service.
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Defer sang epic cost tracking hoặc khi product yêu cầu charge storage.

- **Finding:** Hardcoded TTL 30 giây và SHA256 cache key cho anti-bot cache.
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Chuyển vào config hoặc dùng hash đơn giản hơn nếu cache hit/miss metrics cho thấy overhead đáng kể.

- **Finding:** Inconsistent `next_action` pattern giữa platform executors (batdongsan/chotot/muaban inline string, itviec/topcv dùng helper).
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Style cleanup khi refactor executor base.

- **Finding:** Missing rate limiting trên admin anti-bot escalation endpoints.
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Apply platform-wide rate limiting policy, không riêng story này.

- **Finding:** Workspace/Run cascade delete không xóa screenshot trong storage.
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Cần trigger hoặc cleanup job chung cho storage lifecycle.

- **Finding:** `escalation_metadata` alias `metadata` gây confusion giữa model, schema và DB column.
  - **Action:** Marked `[x] [Review][Defer]` in `10-5-anti-bot-captcha-screenshot-escalation.md`.
  - **Reason / when to revisit:** Naming cleanup khi refactor schema/model.

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

## Deferred from: code review of 18-6-memory-tagging-rag-filter (2026-08-11)

- ~~**Finding:** `MemoryRelation` has no `client_id` and `MemoryRepository.add_relation` does not set tenant GUCs, so a workspace member could create a relation that spans clients.~~
  - **Resolution (2026-08-11):** Added `client_id` to `MemoryRelation`, composite index, RLS policies in migration `b8b3fae31175`, and hardened `MemoryRepository.add_relation` to derive scope from the source memory, set tenant GUCs, and reject cross-workspace/cross-client targets.

- ~~**Finding:** `Memory.source_uuid` and `Memory.source_entity_type` exist in `app/db.py` but no migration adds them, and the Postgres `memory_source_type` enum has not been updated.~~
  - **Resolution (2026-08-11):** Added migration `e5b50d5e687e` to create `source_uuid` and `source_entity_type` columns with the required index.

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

### td-7: No unit test coverage for test_model function
- **Source:** code review of fix-model-test-infinite-save (2026-08-08)
- **Issue:** `tests/unit/services/test_model_connections.py` only tests resolver functions (`to_litellm`, `strip_version_suffix`), not `test_model()` itself. Integration tests mock `test_model` entirely. The timeout/retry parameters passed to `litellm.acompletion` are never verified.
- **Fix:** Add a unit test that mocks `litellm.acompletion` and asserts `num_retries=0` and `timeout=TEST_TIMEOUT_SECONDS` are passed correctly.
- **Priority:** P2 — test gap for P0-adjacent function (model routing).

## Deferred from: code review of 7-4-dedicated-connectors-layout (2026-08-08)

- **Finding:** Thay đổi mở document thành tab trong `DocumentsSidebar` chưa có test — `DocumentsSidebar.tsx:354, 1123-1126`.
- **Action:** Marked `[x] [Review][Defer]` in `7-4-dedicated-connectors-layout.md`.
- **Reason / when to revisit:** Behavior change từ `openEditorPanel` sang `openDocumentTab` nằm ngoài scope rõ ràng của Story 7.4; cần xử lý khi test khung tab/document được triển khai hoặc khi refactor DocumentsSidebar.

## Tech-debt: Epic 13 code deprecation (2026-08-08)

- **Source:** SCP `sprint-change-proposal-2026-08-08-remove-duplicate-index.md` adopted.
- **Issue:** `canonical_entities` tables, migrations, merge logic, and search surfaces (Stories 13.1–13.3, Epic 13) are now out of scope because `chainlens-research` owns the canonical index. Keeping the code in `develop` risks future features coupling to a deprecated local index.
- **Fix:** Schedule a cleanup story to:
  1. Identify all Epic 13 tables/columns/migrations (`canonical_entities`, merge history, `pgvector`/`to_tsvector` corpus if any).
  2. Mark them deprecated with runtime warnings.
  3. Remove unused REST/MCP endpoints and UI routes.
  4. Drop tables after all dependent code is removed.
- **Priority:** P2 — not blocking integration work, but should run before Phase 1 GA to avoid data-migration pain.
- **When to revisit:** After `NowingIngestService` and `chainlens-research` `POST /v1/ingest/scraper` are in production and no live call path touches Epic 13 tables.

## Deferred from: code review of 7-7-mcp-server-tool-expansion (2026-08-09)

Reconfirmed in fresh 3-layer review; see 2026-08-05 section above for full rationale. These remain pre-existing/cross-cutting and are not introduced by 7.7.

- **Finding:** `RunService.launch` maps `DispatchError` to HTTP 404/400 by substring `"not found"`.
  - **Action:** Marked `[x] [Review][Defer]` in `7-7-mcp-server-tool-expansion.md`.
  - **Reason / when to revisit:** Fragile classification; replace with error-kind dispatch or an exception class hierarchy when `app/automations/dispatch` is refactored.

- **Finding:** `nowing_chat` busy-retry uses deterministic exponential backoff without jitter.
  - **Action:** Marked `[x] [Review][Defer]` in `7-7-mcp-server-tool-expansion.md`.
  - **Reason / when to revisit:** Thundering-herd risk when multiple callers hit a busy thread; add jitter and/or circuit-breaker in a chat robustness pass.

- **Finding:** `NowingClient.stream_sse()` has only a 600s total timeout, no per-event/idle timeout.
  - **Action:** Marked `[x] [Review][Defer]` in `7-7-mcp-server-tool-expansion.md`.
  - **Reason / when to revisit:** A stalled SSE stream hangs for up to 600s; introduce `httpx.Timeout(..., read=60.0)` and/or application-level idle timer.

- **Finding:** `POST /automations/{id}/run` has no idempotency key, so two concurrent POSTs create two PENDING runs.
  - **Action:** Marked `[x] [Review][Defer]` in `7-7-mcp-server-tool-expansion.md`.
  - **Reason / when to revisit:** Same pattern as Telegram `/run`; add idempotency key or workspace+automation dedup lock when manual-run endpoint is hardened.

- **Finding:** Celery `apply_async` failure after `launch_run` commits leaves a run stuck PENDING forever.
  - **Action:** Marked `[x] [Review][Defer]` in `7-7-mcp-server-tool-expansion.md`.
  - **Reason / when to revisit:** Pre-existing `launch_run` commit-before-enqueue pattern; fix by rolling back or retrying enqueue.

## Deferred from: quick-dev review of 12-2-topcv-scraper (2026-08-10)

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Detail-page anti-bot blocks are swallowed without per-run degradation threshold.
  evidence: `_fetch_detail_page` returns `{}` after all retries when it sees a non-`RATE_LIMITED` block; the scrape loop keeps requesting detail pages from a blocked domain. A threshold (e.g., N consecutive detail anti-bot failures) is needed before whole-run degradation.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Partial degraded runs return items but the billing service may not charge.
  evidence: `_scrape` can return `degraded=True` with `items` and a non-zero `cost_micros`, but `_charge_platform_meter` debits zero when `degraded=True`. The cost-vs-degraded contract needs cross-story billing alignment.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: No unit tests for retry, exponential backoff, circuit breaker, or anti-bot detection paths.
  evidence: `tests/unit/proprietary/platforms/topcv/test_scraper.py` covers happy-path and one fake `ValueError`; the new `_fetch_search_page` retry/circuit logic and `_validate_search_page` branches are untested.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: User-Agent rotation is not wired to detail-page fetches.
  evidence: `_fetch_detail_page` calls `WebCrawlerConnector.crawl_url()`, which does not accept a `useragent` kwarg. Refactor of the connector or extra-headers support is needed to pass a rotated UA to detail requests.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Anti-bot screenshot escalation is gated on `ctx.run_id`, which is `None` in sync REST/agent paths.
  evidence: `app/capabilities/topcv/scrape/executor.py` only triggers `capture_platform_anti_bot_screenshot_task` when `ctx.run_id` is set; sync capability callers create `CapabilityContext` without a `run_id`. This is a pre-existing executor pattern also seen in `itviec`.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Module-level circuit-breaker globals are shared across concurrent `topcv.scrape` calls.
  evidence: `_consecutive_failures` and `_circuit_open_until` are mutated by every concurrent coroutine; while `asyncio` is single-threaded, interleaving can cause false circuit trips or suppress real ones. A per-domain/per-call circuit instance is the eventual fix.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Legal/ToS block decision is a static config flag, not a runtime legal-service hook.
  evidence: `TOPCV_ENABLED` is read from env and checked at call time; there is no runtime integration with a legal/TOS service because Story 12.0 produced a manual decision and no service exists to consume it.

## Deferred from: code review of 12-2-topcv-scraper — bmad-code-review (2026-08-10)

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Partial degraded billing may not charge when `degraded=True`.
  evidence: `_scrape` can return `degraded=True` with `items` and a non-zero `cost_micros`, but the billing path may skip debit on degraded output. The cost-vs-degraded contract needs cross-story billing alignment.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: User-Agent rotation is not wired to detail-page fetches.
  evidence: `_fetch_detail_page` calls `WebCrawlerConnector.crawl_url()`, which does not accept a `useragent` kwarg. Refactor of the connector or extra-headers support is needed to pass a rotated UA to detail requests.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Anti-bot screenshot escalation is gated on `ctx.run_id`, which is `None` in sync REST/agent paths.
  evidence: `app/capabilities/topcv/scrape/executor.py` only triggers `capture_platform_anti_bot_screenshot_task` when `ctx.run_id` is set; sync capability callers create `CapabilityContext` without a `run_id`. This is a pre-existing executor pattern also seen in `itviec`.

- source_spec: `_bmad-output/implementation-artifacts/stories/12-2-topcv-scraper.md`
  summary: Legal/ToS block decision is a static config flag, not a runtime legal-service hook.
  evidence: `TOPCV_ENABLED` is read from env and checked at call time; there is no runtime integration with a legal/TOS service because Story 12.0 produced a manual decision and no service exists to consume it.

## Deferred from: code review of 18-3-agent-registry deferred resolution (2026-08-10)

- Tool catalog tools stored in `AgentConfig` may still be ignored by the main-agent runtime because subagent/MCP dispatch is environment-driven.
- Admin `PATCH` has no optimistic locking (`updated_at` comparison) — acceptable last-write-wins for the current admin surface.
- Frontend does not pre-validate `client_id` against `vertical_clients` before submit; API already fails fast, but a UX pass should add a dropdown or pre-check.
- UI for soft-deleted/inactive agents and a system-instructions character counter are not aligned with the (missing) `ux-contract-agent-registry.md`.
- Max-length boundary tests and tests for enabled/disabled tool overlap are out of scope for this chunk.
- `enabled_tools` / `disabled_tools` are not validated as disjoint and are not de-duplicated; currently harmless.

## Deferred from: code review of 18-4-agentconfig-prompt-injection (2026-08-10)

- OpenTelemetry metrics for agent prompt/tool filter usage are not added; audit logs cover the merge event.
- `enabled_tools` / `disabled_tools` overlap and duplicate-name validation is not enforced in the schema.
- Thread `platform_metadata` persistence does not log changes or serialize concurrent updates.
- No dedicated `tests/integration/api/test_agent_chat_pat_matrix.py` was created; existing tests cover critical paths.
- Prompt render-time size check for the `platform_metadata` wrapper is not explicit.
