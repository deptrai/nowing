# Story 21.19: Lead Source Adapter Live Data Integration & Persistence

Status: done

## Story

As a sales rep or real estate broker in Vietnam,
I want to describe my target prospects in natural language in chat and get a live multi-source lead table,
So that I can immediately see, persist, and act on verified BĐS, recruitment, and company leads without manual scraping.

## Acceptance Criteria

1. Given a chat prompt like "Tìm 20 nhà đất Hà Nội giá dưới 5 tỷ" or "Tìm công ty logistics tuyển dụng tại TP.HCM", when the user sends it, then the main agent can trigger `multi_source_lead_gen` and receive a formatted markdown table.
2. Given the `multi_source_lead_gen` capability, when executed, then it calls `LeadGenOrchestrator` which dispatches the right adapters (`batdongsan`, `chotot`, `topcv`, `itviec`, `enterprise`) concurrently with `asyncio.Semaphore(5)` and 12s timeout.
3. Given each adapter, when it runs, then it calls the existing live scraper function and returns `RawLeadRecord`s with data shapes the `normalize_lead` method can consume.
4. Given normalized leads, when persistence is triggered, then `LeadBatchService.ingest_batch` is used to create `Lead` and `VerifiedContact` rows with correct `value_hmac`, DNC filtering, and PII encryption.
5. Given a lead with phone or email, when persisted, then `VerifiedContact` is created with `verification_status="verified"`, `consent=True`, `legal_basis="legitimate_interest"`.
6. Given job-market leads without direct contact, when persisted, then `Lead` is still created using `company_name` for `value_hmac` and no `VerifiedContact` is created.
7. Given the feature, when `ruff check` and `pytest` run, then lint/type errors are 0 and relevant tests pass.

## Tasks / Subtasks

- [x] Task 1: Reopen Epic 21 planning artifacts
- [x] Task 2: Fix `BatdongsanLeadAdapter` schema mapping
- [x] Task 3: Wire `ChototLeadAdapter` to `scrape_chotot`
- [x] Task 4: Wire `JobMarketLeadAdapter` to `scrape_topcv`/`scrape_itviec`
- [x] Task 5: Fix `EnterpriseProcurementLeadAdapter` tax_code mapping
- [x] Task 6: Refactor `execute_and_persist` to use `LeadBatchService`
- [x] Task 7: Update `MultiSourceLeadGenTool` and capability executor to persist
- [x] Task 8: Register `multi_source_lead_gen` in main agent tool registry
- [x] Task 9: Update tests for encrypted contacts and new flow
- [x] Task 10: ruff + pytest + smoke

## Dev Notes

- Reuse existing scrapers and `LeadBatchService`; do not reinvent.
- PII handled by `LeadBatchService` (HMAC, DNC, encryption).
- Social/Telegram live integration out of scope (deferred to 21.20).
- Billing for `leads.multi_source_gen` remains `None`; scraper-level billing unchanged.
- Use `ponytail` comments for any intentional simplifications (e.g., city default, contact-less leads).

## References

- `app/lead_intelligence/adapters/batdongsan.py`
- `app/lead_intelligence/adapters/chotot.py`
- `app/lead_intelligence/adapters/job_market.py`
- `app/lead_intelligence/adapters/enterprise.py`
- `app/lead_intelligence/services/lead_gen_orchestrator.py`
- `app/services/lead_batch_service.py`
- `app/capabilities/leads/orchestrator_tool.py`
- `app/capabilities/leads/orchestrator/executor.py`
- `app/agents/chat/multi_agent_chat/main_agent/tools/registry.py`
- `app/agents/chat/multi_agent_chat/main_agent/tools/index.py`

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Plan: `~/.devin/plans/plan-e78a36d939cec910.md`

### Completion Notes List

- Wired `BatdongsanLeadAdapter` to `scrape_batdongsan` using `BatdongsanListing.to_output()` and mapped real fields.
- Wired `ChototLeadAdapter` to `scrape_chotot` for `bds` category with city fallback.
- Wired `JobMarketLeadAdapter` to `scrape_topcv` and `scrape_itviec` with keyword search.
- Fixed `EnterpriseProcurementLeadAdapter` to expose `tax_id` from `tax_code`.
- Refactored `LeadGenOrchestrator.execute_and_persist` to use `LeadBatchService.ingest_batch` for DNC filtering, deduplication, HMAC, and PII encryption.
- Updated `MultiSourceLeadGenTool` and `leads.multi_source_gen` capability executor to call `execute_and_persist`.
- Registered `multi_source_lead_gen` in main agent tool registry (`index.py` + `registry.py` + new `lead_generation.py`).
- Fixed `LeadBatchService._build_contacts_upsert_stmt` to not reference non-existent `verified_contacts.updated_at`.
- Allowed `_reject_degenerate_leads` to accept `company_name` and added `table_id`/`client_id` to `_prepare_lead_record`.
- Updated integration tests to decrypt `VerifiedContact.phone` and supply `WorkspaceTable` FK for `table_id`.
- Fixed `test_signal_detection.py` and `test_leads_routes.py` fixture issues surfaced during verification.
- `ruff check`, `ruff format`, `pytest` (246 unit + 3 integration tests), and `app import OK` smoke all pass.

### File List

- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/implementation-artifacts/stories/21-19-lead-source-adapter-live-integration.md`
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py`
- `nowing_backend/app/lead_intelligence/adapters/chotot.py`
- `nowing_backend/app/lead_intelligence/adapters/job_market.py`
- `nowing_backend/app/lead_intelligence/adapters/enterprise.py`
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`
- `nowing_backend/app/capabilities/leads/orchestrator_tool.py`
- `nowing_backend/app/capabilities/leads/orchestrator/executor.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/lead_generation.py`
- `nowing_backend/app/services/lead_batch_service.py`
- `nowing_backend/tests/integration/lead_intelligence/test_lead_gen_orchestrator.py`
- `nowing_backend/tests/unit/lead_intelligence/test_signal_detection.py`
- `nowing_backend/tests/unit/routes/test_leads_routes.py`
