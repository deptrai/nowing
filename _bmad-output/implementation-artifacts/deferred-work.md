## Deferred from: code review of 24-7-multi-channel-drip-outreach-campaign-engine (2026-08-22)

- **Finding:** Cross-cutting `billing_event_service.py` refund/relock code is pre-existing and not introduced by Story 24.7.
  - **Action:** Marked `[x] [Review][Defer]` in `24-7-multi-channel-drip-outreach-campaign-engine.md`.
  - **Reason / when to revisit:** Owned by contact-unlock/refund work (Story 26.x); revisit when that billing path is reviewed.

## Resolved from: code review of 24-6-two-way-ai-outreach-auto-reply-agent (2026-08-22)

- **Finding:** Zalo signature verification (INV-23.11) was deferred but is already fully implemented in `app/routes/outbound_routes.py:672`.
  - **Action:** Marked `[x] [Review][Dismissed]` in `24-6-two-way-ai-outreach-auto-reply-agent.md`.
  - **Resolution:** `zalo_inbound_webhook` calls `verify_zalo_signature` with `connection.webhook_secret` before processing; no code change needed.
- **Finding:** Human-in-the-Loop takeover from CRM not wired — AC-4 requires human rep message to set `auto_reply_paused`.
  - **Action:** Marked `[x] [Review][Resolved]` in `24-6-two-way-ai-outreach-auto-reply-agent.md`.
  - **Resolution:** Added `POST /api/v1/gateway/bindings/{binding_id}/send` in `app/routes/gateway_webhook_routes.py`; on success it calls `pause_auto_reply(str(binding.id))` for 24h. Unit test `tests/unit/gateway/test_webhook_routes.py::test_send_message_to_binding_pauses_auto_reply` passes.

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-21)

- **Finding:** `FakeAsyncSession` seam in `workspace_credit_service.py:141-146,322-328` (`_deduct_credits_fake`, `_record_spend_fake`) lets unit tests exercise fake paths instead of production `UPDATE ... WHERE ... RETURNING` SQL.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Pre-existing test architecture issue already recorded in `test-review-24-3.md`; revisit during 4.9/4.10 test review and mutation gate.
- **Finding:** `tests/integration/services/test_team_crm_pipeline.py` is a stub integration test.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Already in `test-review-24-3.md`; revisit during 4.9.
- **Finding:** `test_billing_event_service.py` and `test_billing.py` monkeypatch `WorkspaceCreditService.record_spend`.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Already in `test-review-24-3.md`; revisit during 4.9/4.10.
- **Finding:** Direct `wallet_credit.apply_debit` call sites in `phone_waterfall_service.py`, `outcome_pricing_service.py`, `etl_credit_service.py`, `zns_client.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py` bypass the per-seat spend-cap gate.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Pre-existing / owned by other stories; revisit when each service is reviewed.
- **Finding:** `MissionControlWidget.tsx:239` pre-existing TypeScript build fix.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Not in scope for Story 24.3; handle in its owning build-debt story.
- **Finding:** `.agents/skills/bmad-agent-e2e-tester/` and `_bmad/memory/bmad-agent-e2e-tester/` are a new XActions skill unrelated to Story 24.3.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Out of scope; route to the agent/skill story that owns it.

## Deferred from: code review of 26-7-hermetic-quality-gates-benchmark-anti-zombie (2026-08-19)

- **Finding:** Pre-compile regex token pattern at module level in `phone_extractor.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `26-7-hermetic-quality-gates-benchmark-anti-zombie.md`.
  - **Reason / when to revisit:** Pre-existing pattern in `xactions/phone_extractor.py`; not introduced by 26.7 diff. Revisit during phone extractor performance tuning.
- **Finding:** Validate `is_valid_vietnam_tax_code` against 100 known-good masothue fixtures before ratifying.
  - **Action:** Marked `[x] [Review][Defer]` in `26-7-hermetic-quality-gates-benchmark-anti-zombie.md`.
  - **Reason / when to revisit:** Fixtures not yet available; revisit when masothue fixture corpus is consolidated.
- **Finding:** Add FastMCP hermetic integration test for `dsh_worker` / `nowing_mcp` reusing `tests/e2e/fakes/mcp_runtime.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `26-7-hermetic-quality-gates-benchmark-anti-zombie.md`.
  - **Reason / when to revisit:** Out of scope for the `nowing_evals` cassette suite; revisit when AD-107 FastMCP transport is explicitly required for `dsh_worker`.

- **Finding:** Pre-compile regex token pattern at module level in `phone_extractor.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `26-7-hermetic-quality-gates-benchmark-anti-zombie.md`.
  - **Reason / when to revisit:** Pre-existing pattern in `xactions/phone_extractor.py`; not introduced by 26.7 diff. Revisit during phone extractor performance tuning.

## Deferred from: code review of 26-9b-pro-excel-formatter-daytona (2026-08-20)

- **Finding:** Hardcoded `filename == "wide_research_output.xlsx"` in `DshDeliverSubgraph` (`dsh_worker_deliver_subgraph.py:136`).
  - **Action:** Marked `[x] [Review][Defer]` in `26-9b-pro-excel-formatter-daytona.md`.
  - **Reason / when to revisit:** Pre-existing single-deliverable design; revisit when multi-deliverable support or versioned filenames are required.

## Deferred from: code review of 26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx (2026-08-21)

- **Finding:** Top-right credit badge is not refetched after unlock and already displays `credit_micros_balance / 1_000_000` as USD.
  - **Action:** Marked `[x] [Review][Defer]` in `26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx.md`.
  - **Reason / when to revisit:** Pre-existing `DynamicRightPanelCanvas` behavior; not part of 26.5 ACs.

- **Finding:** No new unit tests for the new components; Playwright E2E specs already exist.
  - **Action:** Marked `[x] [Review][Defer]` in `26-5-split-canvas-glass-box-mission-control-two-tier-phone-unlock-shimmer-influx.md`.
  - **Reason / when to revisit:** E2E coverage exists in `nowing_web/tests/leads`; add component/unit tests when the design stabilizes.

## Deferred from: code review of 26-2-dsh-worker-sidecar-redis-streams-and-task-resumption (2026-08-17)

- **Finding:** Missing structured mission-lifecycle observability.
  - **Action:** Marked `[x] [Review][Defer]` in `26-2-dsh-worker-sidecar-redis-streams-and-task-resumption.md`.
  - **Reason / when to revisit:** Functional logging exists; structured logs and metrics are a production-hardening follow-up, not a 26.2 launch blocker and not in the ACs.

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-21)

- **Finding:** `ImpersonationGuardMiddleware` and CORS regex for `chrome-extension://` origins were added in the 24.3 diff but belong to Story 25.1 / 24.5.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Code is functional and currently active (`app/app.py:790`). Revisit during Story 25.1 (admin impersonation hardening) and 24.5 (Clipper extension CORS) to ensure ownership and tests match.

- **Finding:** `GlobalDncRecord`, `AuditEvent`, `CreditTransaction` and `Lead` fields `tax_id` / `company_status` were added in the 24.3 diff but belong to Stories 24.2 / 24.4 / 25.2.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Fields are required downstream. Revisit during 24.2 (MST verification), 24.4 (Lead Clipper), and 25.2 (credit refund audit) to ensure proper migrations, indexes, and tests.

## Deferred from: code review of 25-1-multitenant-user-workspace-hub-scoped-impersonation (2026-08-17)

- **Finding:** E2E tests `nowing_web/tests/admin/impersonation.spec.ts` còn scaffold `test.fail`.
  - **Action:** Marked `[x] [Review][Defer]` in `25-1-multitenant-user-workspace-hub-scoped-impersonation.md`.
  - **Reason / when to revisit:** ATDD red-phase; implement khi UI impersonation hoàn thiện.

## Deferred from: code review of 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger (2026-08-16)

- **Finding:** Thiếu test AC-1 validation cho `reason` min length, `ticket_ref` missing, `workspace_id` format/negative, `amount_credits` zero/negative, `direction` invalid values.
  - **Action:** Marked `[x] [Review][Defer]` in `25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md`.
  - **Reason / when to revisit:** Pre-existing test coverage; not in the current test-additions diff.

- **Finding:** Thiếu test trực tiếp Redis Redlock / Postgres `FOR UPDATE` / `lock_timeout`.
  - **Action:** Marked `[x] [Review][Defer]` in `25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md`.
  - **Reason / when to revisit:** Implementation internals; revisit if concurrency lock contracts become externally observable.

- **Finding:** Thiếu test quota cho `DEBIT` và non-superuser role.
  - **Action:** Marked `[x] [Review][Defer]` in `25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md`.
  - **Reason / when to revisit:** Role-based staff infra not yet in place; story already documents decision to keep `require_superuser`.

- **Finding:** Thiếu test CSV export, aggregate stats cards, 36px row height.
  - **Action:** Marked `[x] [Review][Defer]` in `25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md`.
  - **Reason / when to revisit:** AC-4 UI tests; out of scope for the current backend test diff.

## Deferred from: code review of 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui (2026-08-16)

- **Finding:** Configure timeout and SSL options for smtplib.SMTP in alert notifications.
  - **Action:** Marked `[x] [Review][Defer]` in `22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui.md`.
  - **Reason / when to revisit:** Pre-existing notification service pattern. Revisit when alerting notification channel hardening is scheduled.

- **Finding:** Connect full TanStack Query API endpoints for Telegram Userbot / Channel list on Web Admin.
  - **Action:** Marked `[x] [Review][Defer]` in `22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui.md`.
  - **Reason / when to revisit:** Frontend UI contracts are in place; live backend scraper persistence APIs for accounts/channels are scheduled for next platform sprints.

## Deferred from: code review of 21-5-crm-integration (2026-08-16)


- **Finding:** Cross-source full CRM historical bi-directional backfill and deal pipeline sync.
  - **Action:** Marked `[x] [Review][Defer]` in `21-5-crm-integration.md`.
  - **Reason / when to revisit:** Out of scope for MVP (Spec line 468). Revisit when enterprise pipeline sync is scheduled.

- **Finding:** Dedicated CRM UI tabs in frontend.
  - **Action:** Marked `[x] [Review][Defer]` in `21-5-crm-integration.md`.
  - **Reason / when to revisit:** Frontend contracts and UI components are scoped to Story 21.6 (Zalo Integration) and Story 21.13 (Multi-Table Tabs).

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-17)

- **Finding:** Scope creep từ story khác trong diff 24.3: `ImpersonationGuardMiddleware` và chỉnh CORS regex trong `app/app.py` thuộc Story 25.1/24.5.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Nằm ngoài scope Story 24.3; đã hoặc sẽ được xử lý trong story tương ứng.

- **Finding:** Scope creep từ story khác trong diff 24.3: `GlobalDncRecord`, `AuditEvent`, `CreditTransaction` và các trường `tax_id`/`company_status` trên `Lead` trong `app/db.py` thuộc Story 24.2/24.4/25.2.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Nằm ngoài scope Story 24.3; đã hoặc sẽ được xử lý trong story tương ứng.

## Deferred from: code review of 10-7-chotot-multi-category-capability (2026-08-15)

- **Finding:** Inverted `district_id` guard in `app/proprietary/platforms/chotot/scraper.py:116-119` rejects every valid non-negative `district_id`.
  - **Action:** Marked `[x] [Review][Defer]` in `10-7-chotot-multi-category-capability.md`.
  - **Reason / when to revisit:** Pre-existing bug; the new `chotot` subagent prompt no longer advertises `district_id` once patched, so it is no longer user-facing through this route. Revisit when district-level filtering is explicitly required for Chợ Tốt multi-category scrapes.

## Deferred from: code review of story-15-2-vietstock-deep-financials (2026-08-15)

- **Finding:** CafeF financials do not currently go through `to_chunks()` / `NowingIngestService.ingest()`; true cross-source merge requires updating Story 15.1 or a follow-up story.
  - **Action:** Marked `[x] [Review][Defer]` in `15-2-vietstock-deep-financials.md`.
  - **Reason / when to revisit:** Pre-existing ingestion pipeline mismatch. Revisit when Story 15.1 financials are migrated to ChainLens ingest or a cross-source reconciliation story is scheduled.

- **Finding:** Per-request `httpx.AsyncClient` creation in `fetch.py`.
  - **Action:** Marked `[x] [Review][Defer]` in `15-2-vietstock-deep-financials.md`.
  - **Reason / when to revisit:** Minor performance hit, follows existing CafeF pattern. Revisit if profiling shows connection pooling matters for Vietstock throughput.

- **Finding:** `httpx.TimeoutException` / `ConnectError` mapped to `VietstockAccessBlockedError`.
  - **Action:** Marked `[x] [Review][Defer]` in `15-2-vietstock-deep-financials.md`.
  - **Reason / when to revisit:** Acceptable degradation behavior per spec. Revisit if observability needs distinguish network vs. server blocks.

- **Finding:** 5xx server errors raise immediately without bounded retry.
  - **Action:** Marked `[x] [Review][Defer]` in `15-2-vietstock-deep-financials.md`.
  - **Reason / when to revisit:** Spec only requires 429 retry. Revisit if live probes show transient 5xx from Vietstock.

- **Finding:** 20+ years of historical data is a data-availability goal, not a runtime validation requirement.
  - **Action:** Marked `[x] [Review][Defer]` in `15-2-vietstock-deep-financials.md`.
  - **Reason / when to revisit:** Data coverage depends on source API. Revisit if product requires a minimum period count guard.

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

## Deferred from: code review of story-12-9-job-market-alerts (2026-08-13)

- **Finding:** Large `degradation_reasons` array can produce a very long notification message (`nowing_backend/app/alerts/engine/notify.py:44-46`).
  - **Action:** Marked `[x] [Review][Defer]` in `12-9-job-market-alerts.md`.
  - **Reason / when to revisit:** UX polish; cap or truncate the reason list if real sources produce many reasons.

- **Finding:** Snapshot ID from a different alert rule in URL falls back silently (`nowing_web/app/dashboard/[workspace_id]/research/saved-searches/[alert_rule_id]/saved-search-detail-content.tsx:57-60`).
  - **Action:** Marked `[x] [Review][Defer]` in `12-9-job-market-alerts.md`.
  - **Reason / when to revisit:** Safe fallback; add a clearer message if UX feedback asks for it.

- **Finding:** Missing/invalid `alert_run_complete` metadata yields no UI fallback (`nowing_web/components/layout/ui/sidebar/NotificationsDropdown.tsx:269-279`).
  - **Action:** Marked `[x] [Review][Defer]` in `12-9-job-market-alerts.md`.
  - **Reason / when to revisit:** UX polish; render a generic alert message if metadata parsing fails.

- **Finding:** `_TICK_BATCH` batch limit can delay rules past the first 200 (`nowing_backend/app/alerts/engine/tick.py:25,117`).
  - **Action:** Marked `[x] [Review][Defer]` in `12-9-job-market-alerts.md`.
  - **Reason / when to revisit:** Known limitation; add metric/log if batch saturation is observed.

- **Finding:** Match count overflow in JavaScript for extremely large counts (`nowing_web/lib/alerts/group-inbox-notifications.ts:51`).
  - **Action:** Marked `[x] [Review][Defer]` in `12-9-job-market-alerts.md`.
  - **Reason / when to revisit:** Theoretical; real job alert counts will not approach `2^53`.

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

## Deferred from: code review of 24-3-multi-seat-team-crm-pipeline-and-shared-credits (2026-08-16)

- **Finding:** `pnpm tsc --noEmit` fails on `admin-users-api.service.ts:14` in `nowing_web/`.
  - **Action:** Marked `[x] [Review][Defer]` in `24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`.
  - **Reason / when to revisit:** Pre-existing TypeScript error unrelated to the 24.3 diff. Revisit when Story 25.1 (Multi-Tenant User & Workspace Hub) or the admin-users refactor is next reviewed.

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
- **2026-08-22 update:** Cleanup story added as `td-8` in `sprint-status.yaml`. Deprecation warning added to `nowing_backend/app/canonical/__init__.py`. Next: identify all live call paths, mark routes deprecated, then schedule table/column removal.

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

## Deferred from: code review of 14-1-rss-feed-integration (2026-08-13)

- ~~Feed pruning: articles that leave the RSS feed (rolling window) are never removed; unbounded document growth. No soft-delete state exists in DocumentStatus (only ready/pending/processing/failed) and no pruning job exists for any connector type — a retention design (window, hard vs soft delete, canonical last_seen_at handling) is required before implementing.~~ **RESOLVED (2026-08-13):** inline pruning in `index_rss_feeds` after `_persist_canonical_articles` — `RSS_RETENTION_DAYS=30` hard delete of docs not seen in the current poll and older than the window (using `Document.created_at` as last-seen proxy), plus canonical provenance + orphaned-entity sweep via `app/canonical/services/canonical_cleanup.py`. Only runs when the poll succeeded (seen_links non-empty), so transient fetch failures never wipe a feed. Verified by `tests/integration/news/test_rss_pruning.py`.
- ~~Canonical churn: upsert_canonical_entity unconditionally bumps version and records merge history even when the entity is unchanged; pre-existing behavior affecting all connectors, not RSS-specific.~~ **RESOLVED (2026-08-13):** `upsert_canonical_entity` now detects content unchanged (title, canonical_data, search_text, conflict_flags, confidence_score) + source moved; version bump, merge history and embedding backfill are skipped when nothing changed, while `last_seen_at`/`source_count` still refresh. Verified by `tests/unit/services/news/test_rss_indexer_units.py` and `tests/integration/news/test_rss_pruning.py`.
- Epoch sentinel: `_MISSING_PUB_DATE` (1970-01-01) surfaces in UI when pubDate is missing; deliberate deterministic design to avoid re-index churn, accepted at review. **RESOLVED (2026-08-13):** sentinel stays in canonical data/metadata (anti-churn); RSS source markdown now renders "Unknown" via `_format_pub_date` instead of the epoch value. No frontend renders `metadata.pubDate` directly (verified by grep).
- ~~Connector deletion orphans canonical entities: deleting a connector does not clean up its canonical entities; pre-existing general behavior for all connector types.~~ **RESOLVED (2026-08-13):** delete connector route collects document links during the batch deletion loop and then removes canonical sources by record_ids + sweeps orphaned `news_article` entities. Verified by `tests/integration/routes/test_search_source_connectors_routes.py`.

## Resolved/Dismissed from: code review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Redundant status fields in SocialMonitoredTarget — **DISMISSED:** pre-existing flexible schema; `is_active` and `status` are intentionally left for future target states.

- **Finding:** Confusing duplicate timing fields in SocialMonitoredTarget — Three timing-related fields: realtime_stream (bool), scrape_interval_minutes (default 15), and poll_interval_seconds (default 900). The last two are the same value in different units, creating confusion. (app/db.py:4882-4884)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Three timing-related fields: realtime_stream (bool), scrape_interval_minutes (default 15), and poll_interval_seconds (default 900). The last two are the same value in different units, creating confusion. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Redundant timestamp fields in SocialMonitoredTarget — Both last_polled_at and last_scraped_at exist with no clear distinction in purpose. Could lead to inconsistent tracking. (app/db.py:4886-4887)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Both last_polled_at and last_scraped_at exist with no clear distinction in purpose. Could lead to inconsistent tracking. Out-of-scope or future improvement for Story 21.8.

- **Finding:** SocialPost.target_id is nullable but has CASCADE relationship — target_id is nullable with a CASCADE foreign key. If a target is deleted, posts with NULL target_id would remain, but posts with a target_id would be deleted. This creates inconsistent behavior. (app/db.py:4910-4915)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** target_id is nullable with a CASCADE foreign key. If a target is deleted, posts with NULL target_id would remain, but posts with a target_id would be deleted. This creates inconsistent behavior. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation of account_id in proxy binding — The bind_account_proxy method accepts any account_id string without validation. No checks for format, length, or allowed characters. (app/proprietary/platforms/xactions/adapter.py:82-84)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The bind_account_proxy method accepts any account_id string without validation. No checks for format, length, or allowed characters. Out-of-scope or future improvement for Story 21.8.

- **Finding:** ReDoS timeout check placement allows partial execution — The timeout check is inside the loop, so if the first candidate is slow, it breaks. But if the regex itself is slow on the normalized string, it may still timeout after the loop. The timeout doesn't protect the normalization step itself. (app/proprietary/platforms/xactions/phone_extractor.py:118-121)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The timeout check is inside the loop, so if the first candidate is slow, it breaks. But if the regex itself is slow on the normalized string, it may still timeout after the loop. The timeout doesn't protect the normalization step itself. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Phone regex allows invalid Vietnamese prefixes — The regex allows 9\d which matches any digit 0-9 in the third position. Vietnamese mobile prefixes are more specific (e.g., 90, 91, 92, etc., not 93, 94, 95, 96, 97, 98, 99). (app/proprietary/platforms/xactions/phone_extractor.py:44-46)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The regex allows 9\d which matches any digit 0-9 in the third position. Vietnamese mobile prefixes are more specific (e.g., 90, 91, 92, etc., not 93, 94, 95, 96, 97, 98, 99). Out-of-scope or future improvement for Story 21.8.

- **Finding:** Token pattern may miss valid obfuscated phones — The token pattern requires 7-25 characters. A valid obfuscated phone like 'o9.123.456' (10 chars) would match, but edge cases might not. The pattern is complex and may have blind spots. (app/proprietary/platforms/xactions/phone_extractor.py:96)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The token pattern requires 7-25 characters. A valid obfuscated phone like 'o9.123.456' (10 chars) would match, but edge cases might not. The pattern is complex and may have blind spots. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Intent classification has keyword overlap — Keywords are checked sequentially without weighting. A post containing 'tìm việc để bán' (find job to sell) would be classified as 'hiring' (first match) rather than the more nuanced intent. No mechanism for mixed intents. (app/proprietary/platforms/xactions/phone_extractor.py:148-193)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Keywords are checked sequentially without weighting. A post containing 'tìm việc để bán' (find job to sell) would be classified as 'hiring' (first match) rather than the more nuanced intent. No mechanism for mixed intents. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Location extraction is hardcoded and incomplete — The location list is hardcoded with Vietnamese provinces/districts. It's incomplete, unmaintainable, and doesn't handle typos or abbreviations. (app/proprietary/platforms/xactions/phone_extractor.py:60-73)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The location list is hardcoded with Vietnamese provinces/districts. It's incomplete, unmaintainable, and doesn't handle typos or abbreviations. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Email regex is overly simplistic — The email regex doesn't validate TLDs properly and could match invalid emails like user@com or user@.com. (app/proprietary/platforms/xactions/phone_extractor.py:49-51)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The email regex doesn't validate TLDs properly and could match invalid emails like user@com or user@.com. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No dead letter queue for failed messages — Failed messages are logged but not moved to a dead letter queue. They're ACKed even on failure, so they're lost forever. (app/tasks/social_stream_worker.py:186-192)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Failed messages are logged but not moved to a dead letter queue. They're ACKed even on failure, so they're lost forever. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No rate limiting on stream consumer — The consumer has no rate limiting. If the stream has millions of messages, it could overwhelm the database. (app/tasks/social_stream_worker.py:142-197)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The consumer has no rate limiting. If the stream has millions of messages, it could overwhelm the database. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No pagination in search results — The query uses .limit(payload.limit) but has no offset/cursor. Users can only get the first N results, not page through them. (app/capabilities/social/search_leads/executor.py:59)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The query uses .limit(payload.limit) but has no offset/cursor. Users can only get the first N results, not page through them. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Test mocks don't validate SQL queries — The test mocks the database session but doesn't verify the SQL query is correct. It could pass even if the query has bugs. (tests/unit/capabilities/test_social_search_leads.py)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The test mocks the database session but doesn't verify the SQL query is correct. It could pass even if the query has bugs. Out-of-scope or future improvement for Story 21.8.

- **Finding:** ReDoS test has generous timeout — The test asserts duration < 0.10s (100ms) but the spec requires 50ms. This gives 2x headroom and could miss regressions. (tests/unit/platforms/test_phone_regex_redos_safety.py)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** The test asserts duration < 0.10s (100ms) but the spec requires 50ms. This gives 2x headroom and could miss regressions. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Integration test uses mock database — Despite being marked as an integration test, it mocks the database session. This doesn't test actual database persistence. (tests/integration/platforms/test_social_redis_stream.py)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Despite being marked as an integration test, it mocks the database session. This doesn't test actual database persistence. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No composite index on frequently queried columns — While there are indexes on platform, external_post_id, published_at, intent_tag, and raw_entities, there's no composite index on (platform, intent_tag, published_at) which the search capability likely needs. (app/db.py:4901-4907)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** While there are indexes on platform, external_post_id, published_at, intent_tag, and raw_entities, there's no composite index on (platform, intent_tag, published_at) which the search capability likely needs. Out-of-scope or future improvement for Story 21.8.

- **Finding:** XActions subprocess timeout hardcoded at 30s — Timeout hardcoded at 30s. No configurable timeout for different operations (scraping vs simple queries). Could be too short for large Facebook group scrapes. (app/proprietary/platforms/xactions/adapter.py:126)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Timeout hardcoded at 30s. No configurable timeout for different operations (scraping vs simple queries). Could be too short for large Facebook group scrapes. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Timeout breaks loop mid-processing without indication — Timeout breaks loop mid-processing, returning partial results. No indication to caller that results are incomplete due to timeout. Could miss valid phone numbers. (app/proprietary/platforms/xactions/phone_extractor.py:118-121)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Timeout breaks loop mid-processing, returning partial results. No indication to caller that results are incomplete due to timeout. Could miss valid phone numbers. Out-of-scope or future improvement for Story 21.8.

- **Finding:** Province regex may exceed engine limits — Regex built from 60+ province names. Sorted by length (reverse) to match longer names first, but still could have false positives on partial matches. No validation that regex doesn't exceed engine limits. (app/proprietary/platforms/xactions/phone_extractor.py:196-199)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Regex built from 60+ province names. Sorted by length (reverse) to match longer names first, but still could have false positives on partial matches. No validation that regex doesn't exceed engine limits. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for platform values in SocialMonitoredTarget — No validation that platform values are from allowed set ('facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'). Could insert invalid platform values. (app/db.py:4876)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that platform values are from allowed set ('facebook_group', 'facebook_page', 'twitter_keyword', 'twitter_user'). Could insert invalid platform values. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for interval values in SocialMonitoredTarget — No CHECK constraint to prevent negative values or unreasonably small intervals (e.g., 0 or 1 second). Could cause excessive polling and rate limiting issues. (app/db.py:4883-4884)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint to prevent negative values or unreasonably small intervals (e.g., 0 or 1 second). Could cause excessive polling and rate limiting issues. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for platform values in SocialPost — No CHECK constraint or enum to restrict platform to 'facebook' or 'twitter'. Could insert invalid platform values. (app/db.py:4916)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint or enum to restrict platform to 'facebook' or 'twitter'. Could insert invalid platform values. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No CHECK constraint for intent_tag values in SocialPost — No CHECK constraint or enum to restrict intent_tag to documented values. Could insert invalid intent tags. (app/db.py:4923)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No CHECK constraint or enum to restrict intent_tag to documented values. Could insert invalid intent tags. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation for raw_entities structure in SocialPost — No validation that raw_entities structure matches expected schema (phones, emails, prices, locations arrays). Could insert malformed JSON. (app/db.py:4928-4930)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that raw_entities structure matches expected schema (phones, emails, prices, locations arrays). Could insert malformed JSON. Out-of-scope or future improvement for Story 21.8.

- **Finding:** No validation for embedding dimension in SocialPost — No validation that embedding dimension matches configured model. If model changes, existing embeddings could become invalid or cause query errors. (app/db.py:4932)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** No validation that embedding dimension matches configured model. If model changes, existing embeddings could become invalid or cause query errors. Out-of-scope or future improvement for Story 21.8.

- **Finding:** CASCADE delete causes data loss if target deleted — CASCADE delete means if target is deleted, all associated posts are deleted. Could cause data loss if target is accidentally deleted. No soft delete or archival mechanism. (app/db.py:4910-4915)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** CASCADE delete means if target is deleted, all associated posts are deleted. Could cause data loss if target is accidentally deleted. No soft delete or archival mechanism. Out-of-scope or future improvement for Story 21.8.

## Resolved from: re-review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Email alert channel is still `pass` in `app/alerts/engine/notify.py:146-152` — `AlertEngine` is supposed to fire Telegram/Email, but the email branch is not implemented. (app/alerts/engine/notify.py:146-152)
  - **Resolution:** Implemented `_email` using `smtplib` + optional `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/SMTP_FROM/SMTP_TLS` env; logs a warning and skips if not configured.

- **Finding:** First-run alert rules suppress notification — existing alert-engine behavior stores a snapshot on the first run and does not notify. (app/alerts/engine/execute.py:113, 158-189, 210-225)
  - **Resolution:** Confirmed as intentional baseline behavior; added unit test `tests/unit/alerts/test_job_alert.py::test_job_alert_first_run_suppresses_notification` documenting the contract.

- **Finding:** `test_social_redis_stream.py` mocks DB and never touches Redis/Postgres — the integration test does not exercise real persistence. (tests/integration/platforms/test_social_redis_stream.py)
  - **Resolution:** Rewrote as a real integration test using a target fixture, Redis `xadd`, `run_social_stream_consumer`, and Postgres assertions; added `tests/integration/platforms/conftest.py` that skips when PostGIS is unavailable.

- **Finding:** No test for social post → alert-engine notification path — no test creates an `AlertRule` and asserts notification firing. (app/tasks/social_stream_worker.py:254-293)
  - **Resolution:** Added `tests/unit/tasks/test_social_stream_worker.py` covering `_evaluate_alerts_for_social_post` and duplicate lead guard.

- **Finding:** ReDoS timeout not enforced on initial `normalize_vietnamese_text` regex calls — the 50ms timer only checks inside the candidate loop, not the initial normalization regex. (app/proprietary/platforms/xactions/phone_extractor.py:76-145)
  - **Resolution:** Moved `start_time` before `normalize_vietnamese_text` and added a timeout check immediately after; added a 200k input-length cap as a secondary defense.

## Deferred from: code review of 21-8-social-ingress-via-xactions-integration (2026-08-15 second pass)

- **Finding:** No trigram/GIN index on social search keyword search — `content.ilike('%...%')` and `author_name.ilike('%...%')` will full-scan `social_posts` as the table grows. (app/capabilities/social/search_leads/executor.py:65-72; app/db.py:5067)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Query performance issue, not correctness. Add `pg_trgm` GIN index when search latency becomes a concern or as part of an NFR/performance pass.

- **Finding:** Model/migration index drift — SQLAlchemy model uses `ix_social_posts_target_id` while migration 204 creates `idx_social_posts_target_id`; `updated_at` is `index=True` in model but missing in migration; `published_at` index is `ASC` in model but `DESC` in migration. (app/db.py:5050-5120; alembic/versions/204_add_social_tables.py:78-89)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Duplicate or mismatched indexes waste space but do not affect correctness. Resolve in a future migration-hardening pass.

- **Finding:** `social_routes.py` only exposes target creation — no list, get, update, or delete endpoints. (app/routes/social_routes.py:52-103)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** CRUD completeness is out-of-scope for the MVP; add endpoints when the UI requires management screens.

- **Finding:** `target_url` and `proxy_url` are stored as arbitrary strings with no URL/scheme validation. (app/routes/social_routes.py:26-32, 79-91)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** SSRF risk is real but the URLs are consumed by the XActions scraper, which already has its own proxy parsing. Add `HttpUrl` validation in a hardening pass.

- **Finding:** Search/target input schemas lack enum validation for platform, intent, category, status and no bounds for keyword/offset. (app/capabilities/social/search_leads/schemas.py:11-13; app/routes/social_routes.py:22-32)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Typos produce empty results rather than data corruption. Add Pydantic enums/CHECK constraints in a future validation pass.

- **Finding:** Social search ordering places `NULL published_at` first. (app/capabilities/social/search_leads/executor.py:77)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Default `DESC NULLS FIRST` ordering may show undated posts above recent ones. Add `nulls_last` when UX confirms newest-first intent.

- **Finding:** `SocialMonitoredTarget.posts` and `Workspace` social relationships use `cascade="all, delete-orphan"` without `passive_deletes=True`. (app/db.py:5048-5051, 2110-2121)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** PostgreSQL FKs already have `ON DELETE CASCADE`; SQLAlchemy loads children on delete. Add `passive_deletes=True` in a performance pass.

- **Finding:** Redis consumer group starts at stream ID `0` and never reclaims pending messages from crashed consumers. (app/tasks/social_stream_worker.py:500-530)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** New group reading from beginning is recoverable, and `XAUTOCLAIM` is not required for the first release. Add when consumer durability is prioritized.

- **Finding:** `run_social_stream_consumer` runs a single `xreadgroup` batch and returns, not a continuous processing loop. (app/tasks/social_stream_worker.py:481-584)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Intended as a Celery-driven tick; if external scheduling is chosen, this is fine. Revisit when finalizing deployment/operations model.

- **Finding:** `published_at` parser is narrow and may corrupt RFC-2822/lowercase-z timestamps. (app/tasks/social_stream_worker.py:109-121)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Current XActions payloads use ISO-8601. Add broader parsing if Twitter timestamps remain unparsed in production.

- **Finding:** Engagement bonus thresholds are strict `>` (off-by-one) at 10 reactions / 5 comments. (app/tasks/social_stream_worker.py:150-151)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Boundary behavior is marginal; adjust to `>=` if product confirms inclusive thresholds.

- **Finding:** Facebook group ingest always passes `auth_cookie=None`; per-target cookie store not implemented. (app/tasks/celery_tasks/social_xactions_ingest.py:115-121)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Global env cookies are acceptable for the first release. Add per-target cookie column when multi-tenant Facebook scraping is required.

- **Finding:** Email channel lacks outbound metrics, partial SMTP credentials silently skip auth, and missing-SMTP_HOST warning is logged per subscriber. (app/alerts/engine/notify.py:125-137)
  - **Action:** Marked `[x] [Review][Defer]` in `21-8-social-ingress-via-xactions-integration.md`.
  - **Reason / when to revisit:** Operational observability improvements; add `record_gateway_outbound` and centralized env checks after core email path is stable.

## Resolved from: second pass code review of 21-8-social-ingress-via-xactions-integration (2026-08-15)

- **Finding:** Stream messages that fail validation or persistence are not ACKed or dead-lettered — bad messages remain in PEL. (app/tasks/social_stream_worker.py:579-625)
  - **Resolution:** `run_social_stream_consumer` now moves `None` returns to `stream:social:failed` and ACKs.

- **Finding:** `workspace_id` from stream payload is not validated against `SocialMonitoredTarget.workspace_id` — cross-tenant write possible. (app/tasks/social_stream_worker.py:389-426)
  - **Resolution:** Worker now resolves the target, compares `workspace_id`, and rejects mismatches.

- **Finding:** Per-target scheduler uses non-atomic `exists`/`delay` and overrides short `scrape_interval_minutes` with a 300s min TTL. (app/tasks/celery_tasks/social_xactions_ingest.py:31-70, 216-248)
  - **Resolution:** Added a 60s atomic per-target scheduling lock (`nx=True, ex=60`) and clamped intervals to `[1, 1440]`.

- **Finding:** Alert rule evaluation is not isolated and can abort all rules for a post. (app/tasks/social_stream_worker.py:325-380)
  - **Resolution:** Each rule is wrapped in `try/except`; `min_fit_score` and `keyword` are coerced/validated.

- **Finding:** Lead dedup by `source_url` matches all leads with NULL/empty `source_url`; `raw_entities` not shape-guarded. (app/tasks/social_stream_worker.py:203-242)
  - **Resolution:** Skip dedup when `source_url` is empty; coerce `raw_entities` values to string lists before indexing.

- **Finding:** `SMTP_PORT` parsing crashes on malformed/empty env. (app/config/__init__.py:1345)
  - **Resolution:** `SMTP_PORT = _env_int("SMTP_PORT", 587)`.

- **Finding:** Email channel unreachable because alert schema only allows `in_app`/`telegram`. (app/alerts/schemas.py:34)
  - **Resolution:** Added `email` to the allowed set.

- **Finding:** Email subject/body not UTF-8 safe and SMTP has no timeout/SSL. (app/alerts/engine/notify.py:116-145)
  - **Resolution:** Use `Header`/`MIMEText(..., "plain", "utf-8")`; 10s socket timeout; `SMTP_SSL` for port 465.

- **Finding:** `SocialSearchLeadsOutput.total` is page size; tenant filter is redundant. (app/capabilities/social/search_leads/executor.py:60-95)
  - **Resolution:** `total` is now `func.count()`; filter uses single `workspace_id` equality; `NULL published_at` last.

- **Finding:** `SocialPostItem` can fail on malformed `raw_entities`. (app/capabilities/social/search_leads/executor.py:88-95)
  - **Resolution:** Coerce `phones`/`emails`/`prices`/`locations` to `list[str]` and drop `None`.

- **Finding:** `create_db_and_tables` swallows schema-creation errors. (app/db.py:3910-3916)
  - **Resolution:** Removed the broad `try/except` around `Base.metadata.create_all` and `ensure_publication`.

- **Finding:** Integration test cannot persist because worker opens a separate session. (tests/integration/platforms/test_social_redis_stream.py:97-104)
  - **Resolution:** `run_social_stream_consumer` accepts a `session` parameter; the test passes `platform_db_session`.

- **Finding:** Unit test for search uses unconditional mock and would fail real SQL. (tests/unit/capabilities/test_social_search_leads.py:33-61)
  - **Resolution:** Fixture now distinguishes count vs SELECT and uses deterministic `MagicMock` results.

- **Finding:** `threshold_cross` first-run is suppressed. (app/alerts/engine/execute.py:158-174)
  - **Resolution:** Execute `diff_snapshots` with an empty previous snapshot for `threshold_cross`, so first-run threshold crossing fires.

- **Finding:** Stream consumer `run_social_stream_consumer` is not wired to Celery/beat. (app/tasks/social_stream_worker.py:481-584, app/celery_app.py:295-300)
  - **Resolution:** Added `consume_social_stream` Celery task and 5s beat schedule.

- **Finding:** Unique constraints on social tables are not workspace-scoped. (app/db.py:5009-5061; alembic/versions/211_social_unique_workspace_scoped.py)
  - **Resolution:** Model and migration `211` now use `(workspace_id, platform, target_id)` and `(workspace_id, platform, external_post_id)`.

- **Finding:** `social_search_posts` helper opens an unauthored session from raw `workspace_id`. (app/capabilities/social/search_leads/__init__.py:31-50)
  - **Resolution:** Helper now requires `CapabilityContext` and no longer accepts raw `workspace_id`.

- **Finding:** `published_at` parser replaces all `Z` and misses lowercase `z`. (app/tasks/social_stream_worker.py:109-121)
  - **Resolution:** Normalize only a trailing `Z`/`z` to `+00:00`.

- **Finding:** Engagement bonus thresholds are strict `>` (off-by-one). (app/tasks/social_stream_worker.py:150-151)
  - **Resolution:** Changed to `>=`.

## Deferred from: code review of 21-6-zalo-integration (2026-08-15)

- **Finding:** `leads_routes.py` awaits sync `has_permission` with 4 args (pre-existing 21.3 issue, unrelated to 21.6). (app/routes/leads_routes.py:640-645,691)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Fix when resolving phone-waterfall RBAC in Story 21.3; use `check_permission` or correct `has_permission` helper.

- **Finding:** Phone waterfall worker `asyncio.run` inside a sync Celery task and refund exception swallow. (app/tasks/phone_waterfall_worker.py:69,109-116)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Refactor to async Celery task or worker loop in Story 21.3.

- **Finding:** Missing migration for `VerifiedContact`/`PhoneWaterfallLog` model changes. (app/db.py)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Add companion migration in Story 21.3 to keep alembic in sync.

- **Finding:** `app/db.py` reintroduces top-level circular `SpatialPlanningZone` import. (app/db.py:4762)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Fix in Story 10.8 by moving import inside `create_db_and_tables`.

- **Finding:** SQLAlchemy `cascade="delete-orphan"` for `ZaloMessageLog` conflicts with migration `ON DELETE SET NULL`. (app/db.py:5157-5161,5222-5224)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Align ORM/migration delete semantics when finalizing 21.6 data model.

- **Finding:** `PhoneResolutionResponse` hard-codes 1.5 credits for async `pending` results. (app/routes/leads_routes.py:595-602)
  - **Action:** Marked `[x] [Review][Defer]` in `21-6-zalo-integration.md`.
  - **Reason / when to revisit:** Return 0/null for pending async results in Story 21.3.

## Deferred from: code review of 21-6-zalo-integration — second pass (2026-08-15)

- **Finding:** Story says "AI Draft" but the implementation is a hard-coded template, not actually LLM-generated. (app/gateway/zalo/client.py:69-152)
  - **Action:** Marked `[x] [Review][Resolved]` in `21-6-zalo-integration.md`.
  - **Resolution:** `generate_assisted_outbound_draft` now uses the `LLMRouterService` to generate a personalized Vietnamese Zalo outreach draft; falls back to the deterministic template when the LLM router is unavailable or fails. Token usage is recorded with `UsageType.ASSISTED_DRAFT` via `record_token_usage`. (app/gateway/zalo/client.py:67-207, app/services/token_tracking_service.py, tests/unit/gateway/test_zalo_gateway.py)

- **Finding:** `TelegramAlertRequest.chat_id` is not validated against workspace-owned chat bindings. (app/routes/outbound_routes.py:111-114,538-548)
  - **Action:** Marked `[x] [Review][Patch]` in `21-6-zalo-integration.md`.
  - **Resolution:** `send_telegram_lead_alert` now resolves only `ExternalChatBinding` with `state == BOUND` for the workspace; an explicit `target_chat_id` must match `external_thread_id` in that workspace or the alert is skipped with `reason: unauthorized_chat_id`. (app/gateway/zalo/telegram_alerts.py:23-96)

- **Finding:** ZNS send API exists but the frontend `zalo-outreach-button.tsx` only opens a deep-link; no component calls `sendZns`. (nowing_web/components/leads/zalo-outreach-button.tsx)
  - **Action:** Marked `[x] [Review][Patch]` in `21-6-zalo-integration.md`.
  - **Resolution:** Added `ZnsSendModal` component and a "ZNS" button in `zalo-outreach-button.tsx`; modal calls `leadsApiService.sendZns` with template ID/data, mode, OA ID, and explicit consent checkbox. (nowing_web/components/leads/zns-send-modal.tsx, nowing_web/components/leads/zalo-outreach-button.tsx)

- **Finding:** `ZaloMessageLog` stores raw `template_data` on outbound ZNS, which may contain PII. (app/routes/outbound_routes.py:341)
  - **Action:** Marked `[x] [Review][Patch]` in `21-6-zalo-integration.md`.
  - **Resolution:** `_redact_template_data` redacts values for PII-like keys (phone/email/name/address/cccd/cmnd/passport/identity/dob/birth/bank/card/salary) and any string matching email/phone/VN ID patterns before logging. (app/routes/outbound_routes.py:160-196, tests/unit/gateway/test_zalo_gateway.py)

## Deferred from: code review of 24-2-waterfall-phone-mst-corporate-verification-engine (2026-08-16)

- **Finding:** PII vault lacks key-rotation and encryption-failure handling. (nowing_backend/app/services/pii/verified_contact_encryption.py:40-55 and nowing_backend/app/services/phone_waterfall_service.py:692)
  - **Action:** Marked `[x] [Review][Defer]` in `24-2-waterfall-phone-mst-corporate-verification-engine.md`.
  - **Reason / when to revisit:** Verified-contact encryption relies on a single `SECRET_KEY` with no rotation plan, and `resolve_lead_phone` calls `encrypt()` without guarding against transient failures. This is a cross-cutting PII-vault concern and should be handled in a dedicated PII security story.

## Deferred from: code review of 24-2-waterfall-phone-mst-corporate-verification-engine (2026-08-17)

- **Finding:** PII vault lacks key-rotation and encryption-failure handling. (nowing_backend/app/services/pii/verified_contact_encryption.py:40-55 and nowing_backend/app/services/phone_waterfall_service.py:692)
  - **Action:** Marked `[x] [Review][Defer]` in `24-2-waterfall-phone-mst-corporate-verification-engine.md`.
  - **Reason / when to revisit:** Confirmed in chunk 1 backend review. Verified-contact encryption relies on a single `SECRET_KEY` with no rotation plan, and `resolve_lead_phone` calls `encrypt()` without guarding against transient failures. Cross-cutting PII-vault concern; revisit in a dedicated PII security story.

## Deferred from: code review of 26-4-pii-vault-hmac-deduplication-decree-13-opt-out (2026-08-19)

- **Finding:** `batch_ingest_leads` route returns without committing the session, so writes are rolled back on session close. (`nowing_backend/app/routes/lead_batch_routes.py:116`, `nowing_backend/app/db.py:4107-4109`)
  - **Action:** Marked `[x] [Review][Defer]` in `26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md`.
  - **Reason / when to revisit:** Pre-existing pattern in `lead_batch_routes.py`; the 26.4 diff does not introduce the missing `session.commit()` here. Fix when `batch_ingest_leads` persistence is addressed in a dedicated lead-ingest hardening pass or when the route is next touched.

- **Finding:** Global / superadmin PII opt-out endpoint is not exposed. (`nowing_backend/app/routes/lead_batch_routes.py:289`, `nowing_backend/app/services/pii/opt_out_service.py:309-320`)
  - **Action:** Marked `[x] [Review][Decision→Defer]` in `26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md`.
  - **Reason / when to revisit:** Current AC does not require cross-workspace purge. Implement when product requires global Right-to-be-Forgotten flow with proper superadmin permission, audit, and scope design.

- **Finding:** `BillingEvent` model has no `reason` column as suggested by AD-105 Rule 4. (`nowing_backend/app/db.py:4586-4627`, `nowing_backend/app/services/billing_event_service.py:78-89`)
  - **Action:** Marked `[x] [Review][Decision→Defer]` in `26-4-pii-vault-hmac-deduplication-decree-13-opt-out.md`.
  - **Reason / when to revisit:** BillingEvent `event_type` already distinguishes unlock/refund. Detailed reason stored in `pii_access_audit_logs`. Defer to a billing schema v2 epic if a dedicated `reason` column is needed.

## Deferred from: code review of 26-6-telegram-interactive-checkpoint-bot-1-click-auto-refund-dialog (Group 1 — 2026-08-19)

- **Finding:** `telegram_checkpoint_messages` migration lacks RLS / `apply_publication` reconciliation used by other workspace-scoped tables.
  - **Action:** Marked `[x] [Review][Defer]` in `26-6-telegram-interactive-checkpoint-bot-1-click-auto-refund-dialog.md`.
  - **Reason / when to revisit:** DSH routes currently do not call `set_request_tenant_context`, and `dsh_missions` does not have RLS either. Adding RLS now would break existing DSH read/write paths until tenant context is wired into the internal route + service. Defer to a DSH tenant-context hardening pass.

## Deferred from: code review of 21-20-extend-lead-source-adapters (2026-08-21)

- **Finding:**  un-diacritized output vs  may miss less common provinces.
  - **Action:** Marked  in .
  - **Reason / when to revisit:** Scraper normalizes input and common cities work; revisit when testing provinces beyond the top 8 in .

- **Finding:**  location filter not wired.
  - **Action:** Marked  in .
  - **Reason / when to revisit:** Spec explicitly defers location filter to v1+; revisit when  supports .

## Deferred from: code review of 21-20-extend-lead-source-adapters (2026-08-21)

- **Finding:** `resolve_muaban_bds_city` un-diacritized output vs `MuabanBdsScraper._CITY_ALIASES` may miss less common provinces.
  - **Action:** Marked `[x] [Review][Defer]` in `21-20-extend-lead-source-adapters.md`.
  - **Reason / when to revisit:** Scraper normalizes input and common cities work; revisit when testing provinces beyond the top 8 in `_CITY_ALIASES`.

- **Finding:** `VietnamWorks` location filter not wired.
  - **Action:** Marked `[x] [Review][Defer]` in `21-20-extend-lead-source-adapters.md`.
  - **Reason / when to revisit:** Spec explicitly defers location filter to v1+; revisit when `scrape_vietnamworks` supports `locationId`.
