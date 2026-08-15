# Story 21.15: Unified Multi-Source AI Lead Generation Orchestrator & Universal Scraper Adapters

Status: done

<!-- Note: Governed by epics.md (FR-85, AD-31, AD-37, AD-44) & 5 Architectural Invariants -->

## Story

As an active sales rep or researcher,
I want to describe my target prospect in natural language in the chat,
So that Nowing's AI Orchestrator automatically plans and triggers parallel searches across ALL available scrapers (Batdongsan, Chợ Tốt, TopCV, ITviec, Masothue, Mua Sắm Công, Facebook Groups, Twitter, Telegram, Google SERP), deduplicates results, enriches verified phone numbers, and streams a structured Lead Table in real-time.

## Acceptance Criteria

1. **Given** the multi-source scraper ecosystem, **When** `LeadSourceAdapter` abstract base class is defined, **Then** it enforces 3 standardized methods: `search_leads(workspace_id, query, filters, limit)`, `normalize_lead(raw_record)`, and `extract_contact_candidates(raw_record)`.
2. **Given** existing implemented scrapers, **When** retrofitted, **Then** 5 concrete adapters are implemented and registered into `LeadSourceAdapterRegistry`:
   - `BatdongsanLeadAdapter` (Batdongsan.com.vn & Muaban.net BĐS)
   - `ChototLeadAdapter` (Chợ Tốt Nhà, BĐS, Xe, Đồ điện tử)
   - `JobMarketLeadAdapter` (TopCV & ITviec recruitment postings)
   - `EnterpriseProcurementLeadAdapter` (Masothue & Cổng Mua Sắm Công)
   - `SocialLeadAdapter` (Facebook Groups & Twitter Feed via XActions)
3. **Given** a chat prompt (e.g. *"Tìm 30 công ty IT tại Hà Nội và 20 môi giới BĐS Cầu Giấy"*), **When** `LeadGenOrchestrator` executes, **Then** it decomposes the query into sub-tasks and invokes all relevant scraper adapters concurrently via `asyncio.gather(..., return_exceptions=True)` bounded by `asyncio.Semaphore(5)` with a 12s per-adapter timeout.
4. **Given** raw multi-source streams, **When** ingested, **Then** `EntityDeduplicationService` unifies duplicates by Phone HMAC, Tax ID, Email, and Canonical Domain, updating `confidence_score` and merging missing attributes into standard `Lead` records.
5. **Given** any individual adapter experiencing Cloudflare challenge, 429 rate-limit, or timeout, **When** caught, **Then** the adapter retries at most once and falls back gracefully (`status: "degraded"`), ensuring the remaining adapters stream their leads successfully and the chat turn never crashes or returns empty text (AD-19.1).
6. **Given** lead creation, **When** persisted to PostgreSQL, **Then** Zero-cache (`zero.nowing.net`) streams rows directly into the active Table tab with cell highlight animation (`.cell-pulse`) sub-100ms.

## Tasks / Subtasks

- [x] Task 1: Universal LeadSourceAdapter ABC & Registry (AC: 1, 2)
  - [x] 1.1 Tạo `nowing_backend/app/lead_intelligence/adapters/base.py` (`LeadSourceAdapter`, `RawLeadRecord`, `NormalizedLead`, `ContactCandidate`).
  - [x] 1.2 Tạo `nowing_backend/app/lead_intelligence/adapters/registry.py` (`LeadSourceAdapterRegistry`, dynamic discovery & category routing).
  - [x] 1.3 Định nghĩa Pydantic DTOs trong `nowing_backend/app/lead_intelligence/schemas.py`.
- [x] Task 2: Retrofit 5 Concrete Scraper Adapters (AC: 2, 5)
  - [x] 2.1 Xây dựng `BatdongsanLeadAdapter` (`app/lead_intelligence/adapters/batdongsan.py`) bọc `fetch_web_listings` và mobile unmasker.
  - [x] 2.2 Xây dựng `ChototLeadAdapter` (`app/lead_intelligence/adapters/chotot.py`) bọc `chotot/fetch.py` và `parsers.py`.
  - [x] 2.3 Xây dựng `JobMarketLeadAdapter` (`app/lead_intelligence/adapters/job_market.py`) bọc TopCV & ITviec platform fetchers.
  - [x] 2.4 Xây dựng `EnterpriseProcurementLeadAdapter` (`app/lead_intelligence/adapters/enterprise.py`) bọc Masothue & Cổng Mua Sắm Công.
  - [x] 2.5 Xây dựng `SocialLeadAdapter` (`app/lead_intelligence/adapters/social.py`) bọc XActions Facebook Groups & Twitter posts.
- [x] Task 3: Entity Deduplication & DNC Pipeline Service (AC: 4, 6)
  - [x] 3.1 Xây dựng `nowing_backend/app/lead_intelligence/services/deduplication_service.py` (`EntityDeduplicationService` với Phone HMAC, TaxID, Canonical Domain matching).
  - [x] 3.2 Tích hợp `DncComplianceService` lọc in-stream trước khi persist vào DB.
  - [x] 3.3 Đảm bảo atomic upsert `INSERT ... ON CONFLICT (workspace_id, client_id, ...) DO UPDATE` trong database layer.
- [x] Task 4: LeadGenOrchestrator & Agent Tool Bridge (AC: 3, 5, 6)
  - [x] 4.1 Xây dựng `LeadGenOrchestrator` trong `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (`execute_multi_source_lead_gen(workspace_id, query, table_id)` với `Semaphore(5)` và circuit breaker).
  - [x] 4.2 Xây dựng Structured Agent Tool `multi_source_lead_gen` trong `nowing_backend/app/capabilities/leads/orchestrator_tool.py` cho phép Chat Agent kích hoạt trực tiếp từ câu lệnh người dùng.
  - [x] 4.3 Đăng ký capability vào `app/capabilities/leads/__init__.py` và `app/capabilities/leads/orchestrator/definition.py`.
- [x] Task 5: Testing & Quality Verification (AC: 1-6)
  - [x] 5.1 Unit tests: `tests/unit/lead_intelligence/test_lead_source_adapters.py` (Mock 100% 5 adapters, test 403 fallback, test ReDoS safe phone regex).
  - [x] 5.2 Unit tests: `tests/unit/lead_intelligence/test_entity_deduplication_service.py` (Test 4-key collision resolution and confidence merging).
  - [x] 5.3 Integration tests: `tests/integration/lead_intelligence/test_lead_gen_orchestrator.py` (Test parallel execution, timeout isolation, atomic upsert).
  - [x] 5.4 Linter & Typecheck: `uv run ruff check` & `uv run ruff format` (0 errors, all passed).

## Dev Notes

- **5 Mandatory Invariants:**
  1. *Adapter Isolation:* Scrapers do NOT write directly to DB.
  2. *Anti-Loop & Graceful Degradation:* Max 1 retry, fail-soft without 500 or empty text (AD-19.1).
  3. *Zero-PII Hashing:* Deduplication via `phone_hmac` Keyed SHA-256 (Decree 13/2023/NĐ-CP).
  4. *Bounded Concurrency:* Max 5 concurrent tasks via `asyncio.Semaphore`.
  5. *Zero-Cache Schema Conformity:* Stream rows directly into `leads` table linked to `table_id`.
- **Zero Regression:** All existing standalone scraper endpoints and capabilities remain 100% functional.

### Review Findings

- [x] [Review][Patch] Fix Database ORM model conformity and VerifiedContact association in LeadGenOrchestrator.execute_and_persist [app/lead_intelligence/services/lead_gen_orchestrator.py:255-310]
- [x] [Review][Patch] Expand Vietnamese phone area codes & prefix regex in base.py [app/lead_intelligence/adapters/base.py:87-125]
- [x] [Review][Patch] Fix Deduplication Attribute Priority Inversion in _merge_cluster [app/lead_intelligence/services/deduplication_service.py:165-200]
- [x] [Review][Patch] Sanitize Markdown output in Chat Agent Tool against pipe/XSS breaking [app/capabilities/leads/orchestrator_tool.py:75-105]
- [x] [Review][Patch] Fix Double-Retry in Orchestrator & Prevent Timeout Doubling [app/lead_intelligence/services/lead_gen_orchestrator.py:130-180]
- [x] [Review][Patch] Expand Free/Public Email Domain Blacklist in Deduplication [app/lead_intelligence/services/deduplication_service.py:80-87]
- [x] [Review][Patch] Case-insensitive adapter lookup & strip diacritics in Intent Matcher [app/lead_intelligence/adapters/registry.py:58-150]
- [x] [Review][Defer] Connect Scraper Adapter fetchers to live proprietary crawler/Playwright platform services [app/lead_intelligence/adapters/] — deferred, pre-existing integration under Epic 10 & 21.8/21.9

### ATDD Artifacts
- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-21-15-unified-multi-source-ai-lead-generation-orchestrator.md`
- **Unit Tests (Adapters):** `nowing_backend/tests/unit/lead_intelligence/test_lead_source_adapters.py`
- **Unit Tests (Deduplication):** `nowing_backend/tests/unit/lead_intelligence/test_entity_deduplication_service.py`
- **Unit Tests (Orchestrator):** `nowing_backend/tests/unit/lead_intelligence/test_lead_gen_orchestrator.py`
- **Integration Tests:** `nowing_backend/tests/integration/lead_intelligence/test_lead_gen_orchestrator.py`

### References
- [Architecture Spine: epic21-architecture-update.md (AD-31, AD-37, AD-44)]
- [PRD Requirement: epics.md FR-85]
- [Architect Review: Winston System Architecture Review 2026-08-16]
