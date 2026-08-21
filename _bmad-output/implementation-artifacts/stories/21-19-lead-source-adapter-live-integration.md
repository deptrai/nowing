# Story 21.19: Lead Source Adapter Live Data Integration & Persistence

Status: review

Story ID: 21.19
Epic: Epic 21 — Lead Gen Intelligence & Social Graph
Baseline: develop @ 5389b0697 (post-implementation; additional uncommitted fixes on top)

## Story

As a sales rep or real estate broker in Vietnam,
I want to describe my target prospects in natural language in chat and get a live multi-source lead table,
So that I can immediately see, persist, and act on verified BĐS, recruitment, and company leads without manual scraping.

## Acceptance Criteria

1. **Given** a chat prompt like "Tìm 20 nhà đất Hà Nội giá dưới 5 tỷ" or "Tìm công ty logistics tuyển dụng tại TP.HCM", **when** the user sends it, **then** the main agent can trigger `multi_source_lead_gen` and receive a formatted markdown table. `[BUILT]`
2. **Given** the `multi_source_lead_gen` capability or chat tool, **when** executed, **then** it calls `LeadGenOrchestrator` which resolves adapters from `LeadSourceAdapterRegistry` (batdongsan, chotot, job_market, enterprise, social, telegram) concurrently with `asyncio.Semaphore(5)` and a per-adapter 12s timeout. `[BUILT]`
3. **Given** each live adapter, **when** it runs, **then** it calls the existing live scraper function and returns `RawLeadRecord`s with data shapes the `normalize_lead` method can consume. `[BUILT — batdongsan, chotot, job_market, enterprise; PARTIAL — social/telegram return empty]`
4. **Given** normalized leads, **when** persistence is triggered, **then** `LeadBatchService.ingest_batch` is used to create `Lead` and `VerifiedContact` rows with correct `value_hmac`, DNC filtering, and PII encryption. `[BUILT]`
5. **Given** a lead with phone or email, **when** persisted, **then** `VerifiedContact` is created with `verification_status="verified"`, `consent=True`, `legal_basis="legitimate_interest"`. `[BUILT]`
6. **Given** job-market leads without direct contact, **when** persisted, **then** `Lead` is still created using `company_name` for `value_hmac` and no `VerifiedContact` is created. `[BUILT]`
7. **Given** `multi_source_lead_gen` with a `table_id`, **when** it persists, **then** the `table_id` is converted to UUID and stored on `Lead.table_id`, and the chat response links to the table. `[BUILT]`
8. **Given** the chat tool wrapper, **when** it succeeds, **then** the DB session is committed so leads are actually persisted. `[BUILT — explicit commit added to lead_generation.py after initial testing]`
9. **Given** the feature, **when** `ruff check` and `pytest` run, **then** lint/type errors are 0 and relevant tests pass. `[BUILT]`

## Known Gaps / Post-Implementation Reality (needs follow-up)

- **`BatdongsanLeadAdapter` ignores query/filters:** it only passes `max_items=min(limit,20)` to `BatdongsanScrapeInput` and does not map the natural-language `query` or `filters["locations"]`/`price` into `city`, `min_price`, `max_price`, or `listing_type`. User price/location constraints are therefore not enforced at the scraper level. `[GAP]`
- **`ChototLeadAdapter` is BĐS-only and location-only:** it hard-codes `category="bds"`, `max_pages=5`, and only uses `filters["locations"][0]` (with a default of "Hà Nội"). Price, area, and district are not parsed from the query. `[GAP]`
- **`JobMarketLeadAdapter` ignores `locations`:** it passes `query` as `keyword` to TopCV/ITviec but does not forward `filters["locations"]`. `[GAP]`
- **`EnterpriseProcurementLeadAdapter` ignores `locations`:** it passes `query` as `keyword` to Masothue but does not parse location filters. `[GAP]`
- **System prompt / routing oversell the source list:** `description.md` and `routing.md` mention `muaban_bds`, `vn_jobs`, `VietnamWorks`, `Mua Sắm Công` as sources covered by `multi_source_lead_gen`. The actual implementation only dispatches the six registered adapters; `muaban_bds`/`vn_jobs`/`VietnamWorks` are not wired. This creates a prompt-LLM / code mismatch. `[GAP]`
- **Social & Telegram adapters are registered but not live:** `SocialLeadAdapter._search_social_feeds` returns `[]`; `TelegramLeadAdapter._execute_search_query` returns `[]`. Both are present in `LeadSourceAdapterRegistry` and can be matched by intent, but they will always produce zero results. `[GAP]`
- **Deduplication DNC stub:** `EntityDeduplicationService.apply_dnc_compliance` is a stub (`_check_dnc_batch` always returns `False`). Real DNC filtering is delegated to `LeadBatchService.ingest_batch`. `[BUILT — delegated]`
- **No explicit rollback on persistence failure:** `LeadGenOrchestrator.execute_and_persist` catches exceptions and returns `status="degraded"`, but it does not roll back the SQLAlchemy session. Because the chat tool commits after the call, a failed `ingest_batch` could still leave partial writes unless the caller rolls back. `[REVIEW FINDING]`

## Tasks / Subtasks

- [x] Wire `BatdongsanLeadAdapter` to `scrape_batdongsan`
- [x] Wire `ChototLeadAdapter` to `scrape_chotot`
- [x] Wire `JobMarketLeadAdapter` to `scrape_topcv`/`scrape_itviec`
- [x] Wire `EnterpriseProcurementLeadAdapter` to `scrape_masothue`
- [x] Refactor `execute_and_persist` to use `LeadBatchService`
- [x] Update `MultiSourceLeadGenTool` and `leads.multi_source_gen` capability executor
- [x] Register `multi_source_lead_gen` in main agent tool registry
- [x] Add `multi_source_lead_gen` prompt fragments (`description.md`, `example.md`, `__init__.py`)
- [x] Update `core_behavior.md` / `routing.md` to use `multi_source_lead_gen` first
- [x] Update tests for encrypted contacts and new flow
- [x] ruff + pytest + smoke

## Dev Notes

- Reuse existing scrapers and `LeadBatchService`; do not reinvent.
- PII handling (HMAC, DNC, encryption) is delegated to `LeadBatchService`.
- Social/Telegram live integration is out of scope for 21.19 (deferred to 21.20 / 22.3).
- Billing for `leads.multi_source_gen` remains `None`; scraper-level billing is unchanged.
- Mark intentional simplifications with a `ponytail:` comment.
- The chat tool wrapper (`lead_generation.py`) creates a fresh `async_session_maker()` session per call and explicitly commits; the capability executor (`leads/multi_source_gen`) relies on the framework to commit the `CapabilityContext` session.
- `LeadBatchService.ingest_batch` requires at least one of `phone`, `email`, `domain`, or `company_name`; `execute_and_persist` maps `company_name` from `lead.company_name or lead.title or "Doanh nghiệp"` to satisfy this.
- `LeadBatchService._build_contacts_upsert_stmt` intentionally does not update `updated_at` because that column is not present in the current `VerifiedContact` model; if the model later gains `updated_at`, this upsert must be updated.
- `LeadGenOrchestrator` also exposes a non-blocking `dispatch_scrape_job` method for Celery-based background scraping, but the chat/capability path currently uses the synchronous-in-async `execute_multi_source_lead_gen` path.

## References

- `app/lead_intelligence/adapters/__init__.py`
- `app/lead_intelligence/adapters/base.py`
- `app/lead_intelligence/adapters/batdongsan.py`
- `app/lead_intelligence/adapters/chotot.py`
- `app/lead_intelligence/adapters/job_market.py`
- `app/lead_intelligence/adapters/enterprise.py`
- `app/lead_intelligence/adapters/social.py`
- `app/lead_intelligence/adapters/telegram.py`
- `app/lead_intelligence/adapters/registry.py`
- `app/lead_intelligence/services/lead_gen_orchestrator.py`
- `app/lead_intelligence/services/deduplication_service.py`
- `app/lead_intelligence/schemas.py`
- `app/services/lead_batch_service.py`
- `app/capabilities/leads/orchestrator_tool.py`
- `app/capabilities/leads/orchestrator/executor.py`
- `app/capabilities/leads/orchestrator/definition.py`
- `app/agents/chat/multi_agent_chat/main_agent/tools/index.py`
- `app/agents/chat/multi_agent_chat/main_agent/tools/registry.py`
- `app/agents/chat/multi_agent_chat/main_agent/tools/lead_generation.py`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/__init__.py`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/description.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/example.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/core_behavior.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md`
- `tests/unit/lead_intelligence/test_lead_source_adapters.py`
- `tests/integration/lead_intelligence/test_lead_gen_orchestrator.py`

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Plan: `~/.devin/plans/plan-e78a36d939cec910.md`

### Completion Notes List

- Wired `BatdongsanLeadAdapter` to `scrape_batdongsan` via `BatdongsanScrapeInput(max_items=min(limit,20))`; schema mapping uses `to_output()`.
- Wired `ChototLeadAdapter` to `scrape_chotot` for `category="bds"` with a city fallback from `filters["locations"]`.
- Wired `JobMarketLeadAdapter` to `scrape_topcv` and `scrape_itviec` with keyword search.
- Wired `EnterpriseProcurementLeadAdapter` to `scrape_masothue` with keyword search and exposed `tax_id` from `tax_code`.
- Refactored `LeadGenOrchestrator.execute_and_persist` to use `LeadBatchService.ingest_batch` for DNC filtering, deduplication, HMAC, and PII encryption.
- Updated `MultiSourceLeadGenTool` and `leads.multi_source_gen` capability executor to call `execute_and_persist`.
- Registered `multi_source_lead_gen` in the main agent tool registry (`index.py`, `registry.py`, and the new `lead_generation.py` factory).
- Added `multi_source_lead_gen` system-prompt fragments.
- Updated `core_behavior.md` and `routing.md` to recommend `multi_source_lead_gen` as the first tool and to avoid parallel `task` dispatches for the same lead query.
- Fixed `LeadBatchService._build_contacts_upsert_stmt` to not reference the non-existent `verified_contacts.updated_at` column.
- Allowed `_reject_degenerate_leads` to accept `company_name` and added `table_id`/`client_id` to `_prepare_lead_record`.
- Updated integration tests to decrypt `VerifiedContact.phone` and supply `WorkspaceTable` FK for `table_id`.
- Fixed `test_signal_detection.py` and `test_leads_routes.py` fixture issues surfaced during verification.
- Added `estimated_units` to `muaban_bds.scrape.ScrapeInput` to fix a `TypeError` surfaced during E2E smoke; this is a cross-cutting fix, not strictly inside 21.19.
- `ruff check`, `ruff format`, `pytest` (246 unit + 3 integration tests), and `app import OK` smoke all pass.

### File List

- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/stories/21-19-lead-source-adapter-live-integration.md`
- `nowing_backend/app/lead_intelligence/adapters/__init__.py`
- `nowing_backend/app/lead_intelligence/adapters/base.py`
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py`
- `nowing_backend/app/lead_intelligence/adapters/chotot.py`
- `nowing_backend/app/lead_intelligence/adapters/job_market.py`
- `nowing_backend/app/lead_intelligence/adapters/enterprise.py`
- `nowing_backend/app/lead_intelligence/adapters/social.py`
- `nowing_backend/app/lead_intelligence/adapters/telegram.py`
- `nowing_backend/app/lead_intelligence/adapters/registry.py`
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`
- `nowing_backend/app/lead_intelligence/services/deduplication_service.py`
- `nowing_backend/app/lead_intelligence/schemas.py`
- `nowing_backend/app/services/lead_batch_service.py`
- `nowing_backend/app/capabilities/leads/orchestrator_tool.py`
- `nowing_backend/app/capabilities/leads/orchestrator/executor.py`
- `nowing_backend/app/capabilities/leads/orchestrator/definition.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/lead_generation.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/__init__.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/description.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/example.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/core_behavior.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md`
- `nowing_backend/app/capabilities/muaban_bds/scrape/schemas.py` (cross-cutting fix)
- `nowing_backend/tests/integration/lead_intelligence/test_lead_gen_orchestrator.py`
- `nowing_backend/tests/unit/lead_intelligence/test_signal_detection.py` (regression fix)
- `nowing_backend/tests/unit/routes/test_leads_routes.py` (regression fix)

### Review Findings (2026-08-21)

Review approach: manual 3-layer review (adversarial + edge-case + acceptance audit). Subagent review layers could not be launched due to Devin weekly usage quota exhaustion; findings were derived by direct code inspection and verified with targeted tests.

#### decision-needed → resolved

- [x] [Review][Decision→Defer] Align `multi_source_lead_gen` source list with actual implementation — prompt/routing list `muaban_bds`, `vn_jobs`, `VietnamWorks`, `Mua Sắm Công` as covered, but only `batdongsan`, `chotot`, `job_market` (topcv/itviec), `enterprise` (masothue), `social`, `telegram` are wired. **Resolution: create follow-up story 21.20 to implement the missing adapters.** [high] [routing.md:67-69, description.md:1-8]
- [x] [Review][Decision→Patch] How to map natural-language `query` constraints (location, price, listing type) to `BatdongsanScrapeInput` / `ChototScrapeInput`. **Resolution: implement a hybrid parser that extracts city/price/type from the Vietnamese query and also respects explicit `filters` / tool parameters as overrides.** [high] [batdongsan.py:46-47, chotot.py:43-53]

#### patch

- [x] [Review][Patch] `BatdongsanLeadAdapter` always uses default `city="HN"` and ignores `filters["locations"]`/`price`, so any BĐS prompt returns Hà Nội listings regardless of user intent. [high] [batdongsan.py:46-47]
- [x] [Review][Patch] `ChototLeadAdapter._query_chotot_api` indexes `filters["locations"][0]` without checking for an empty list; the capability executor passes `filters={"locations": []}` when `req.locations` is empty, causing `IndexError`. [high] [chotot.py:44, capabilities/leads/orchestrator/executor.py:39]
- [x] [Review][Patch] Adapters swallow scraper exceptions and return `[]` with `last_execution_status="ok"`; `LeadGenOrchestrator` then reports `completed` with 0 leads instead of `degraded`. Affects batdongsan, enterprise, social, telegram. [high] [batdongsan.py:68-70, enterprise.py:59-61, social.py:72-78, telegram.py:41-55]
- [x] [Review][Patch] `ChototLeadAdapter` ignores `scrape_chotot` output `degraded` flag and `degradation_reason`, so bot/rate-limit conditions are not surfaced. [medium] [chotot.py:54-55]
- [x] [Review][Patch] `JobMarketLeadAdapter` and `EnterpriseProcurementLeadAdapter` internal fetch methods catch exceptions and return `[]`; their `search_leads` only sets `degraded` when an exception bubbles, not when the helper degrades internally. [medium] [job_market.py:97-104, 143-148; enterprise.py:59-61]
- [x] [Review][Patch] `LeadBatchService._build_batch_upsert_stmt` overwrites `Lead.status` with `stmt.excluded.status` unconditionally, which can reset an existing `blacklisted` or `withdrawn` lead back to `new`. [high] [lead_batch_service.py:117-131]
- [x] [Review][Patch] `LeadBatchService._build_batch_upsert_stmt` does not update `table_id`, `client_id`, or `source_url` on conflict, so a lead re-ingested to a different table stays in the original table. [medium] [lead_batch_service.py:117-131]
- [x] [Review][Patch] `EntityDeduplicationService.apply_dnc_compliance` is a stub (returns all leads as compliant), but `LeadGenOrchestrator` reports `dnc_suppressed_count` from it, so the summary always says 0 suppressed. [medium] [deduplication_service.py:270-286, lead_gen_orchestrator.py:281-283]
- [x] [Review][Patch] `LeadGenOrchestrator.execute_and_persist` returns `search_result` from `execute_multi_source_lead_gen` without updating `total_deduplicated` or `leads` with the actual `LeadBatchService` result, so the chat response may over/under-report persisted leads. [medium] [lead_gen_orchestrator.py:396-398]
- [x] [Review][Patch] `lead_generation.py` catches all exceptions but does not explicitly call `session.rollback()`, relying on `__aexit__` behavior; partial writes could be committed if an exception occurs after some operations. [medium] [lead_generation.py:45-57]
- [x] [Review][Patch] `TelegramLeadAdapter.normalize_lead` uses `object.__setattr__` to bypass Pydantic validation and inject extra fields (`source`, `source_record_id`, `price_vnd`, etc.); this is brittle and can break serialization. [low] [telegram.py:115-120]
- [x] [Review][Patch] `SocialLeadAdapter` and `TelegramLeadAdapter` are registered and matched by intent but always return `[]` without marking `last_execution_status` as `degraded`, misleading the orchestrator. [medium] [social.py:41-78, telegram.py:31-55]

#### defer

- [x] [Review][Defer] `EntityDeduplicationService` uses a hard-coded default HMAC secret (`nowing_default_lead_secret`) instead of a per-workspace key; HMAC-based cluster keys could theoretically be correlated across workspaces if exposed. Pre-existing; out of 21.19 scope. [low] [deduplication_service.py:39-49]
- [x] [Review][Defer] `LeadGenOrchestrator._assign_new_leads` falls back to an in-memory round-robin cursor when `redis` is `None`; not distributed across workers. Pre-existing assignment limitation. [low] [lead_gen_orchestrator.py:287-320]

**Review completion note:** all 12 patch findings were applied on 2026-08-21. `ruff check`, `pytest` unit + integration, and `app import OK` smoke all pass. The source-list gap is deferred to Story 21.20.
