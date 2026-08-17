# Implementation Readiness Assessment Report

**Date:** 2026-08-17
**Project:** Nowing

---

## Step 1: Document Discovery

### PRD Documents Found

- `_bmad-output/planning-artifacts/prd-requirements-extracted-2026-08-08.md`
- `_bmad-output/planning-artifacts/implementation-readiness/prd-requirements-extract-skill-2026-08-10.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/.memlog.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/review-rubric.md`
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/validation-report.md`

### Architecture Documents Found

- `_bmad-output/planning-artifacts/architecture-epic23-lead-infrastructure.md`
- `_bmad-output/planning-artifacts/architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6.md`
- `_bmad-output/planning-artifacts/architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v7.md`
- `_bmad-output/planning-artifacts/architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v8.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/architecture-validation-report-2026-08-11.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/reviews/review-adversarial.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/reviews/review-reality-check.md`
- `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/UNIT-ECONOMICS-HYPOTHESIS.md`
- `_bmad-output/planning-artifacts/architecture/architecture-bds-planning-and-dkkd-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-linkedin-b2b-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-muasamcong-procurement-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-shopee-ecommerce-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md`
- `_bmad-output/planning-artifacts/architecture/unified-scope-chainlens-research-nowing-2026-08-08.md`
- `_bmad-output/planning-artifacts/epic-11-architecture-review-2026-08-03.md`
- `_bmad-output/planning-artifacts/research/technical-ai-lead-intelligence-origami-architecture-research-2026-08-10.md`

### Epics & Stories Documents Found

- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/epic-11-architecture-review-2026-08-03.md`
- `_bmad-output/planning-artifacts/epic21-proposal-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic-duplicate-analysis-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-engineering-handoff-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-readiness-recheck-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-ux-handoff-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-artifacts/epic21-ux-traceability-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-15-epic22.md`
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md`
- `_bmad-output/planning-artifacts/implementation-readiness-report-epic10-chotot-2026-08-11.md`
- `_bmad-output/planning-artifacts/implementation-readiness/epic-fr-coverage-skill-2026-08-10.md`
- `_bmad-output/planning-artifacts/implementation-readiness/epic-quality-review-skill-2026-08-10.md`

### UX Design Documents Found

- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/*.md` (nhiều UX contracts)
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`
- `_bmad-output/planning-artifacts/ux-design/epic21-lead-intelligence-ux.md`
- `_bmad-output/planning-artifacts/ux-design/epic21-ux-wireframes-2026-08-11.md`
- `_bmad-output/planning-artifacts/ux-design/ux-research-origami-final-2026-08-11.md`
- `_bmad-output/planning-artifacts/ux-design/ux-research-origami-refresh-2026-08-11.md`

---

## Issues Found

### ⚠️ Multiple Architecture Sources

Có 3 architecture spine đáng kể:
1. `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — architecture cũ của Nowing.
2. `architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` — architecture final sau sprint change proposal (ChainLens = engine).
3. Các `architecture-*.md` 2026-08-15 cho từng vertical (BDS, LinkedIn, Shopee, Telegram, v.v.).

**Cần quyết định:** dùng spine nào làm source-of-truth cho readiness check. Đề xuất: `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` vì đã final và sync với story 26.1.

### ⚠️ Multiple UX Sources

Có 2 bộ UX:
1. `ux-designs/ux-Nowing-2026-07-22/` — nhiều UX contracts.
2. `ux-designs/ux-Nowing-2026-08-15/` — `DESIGN.md` + `EXPERIENCE.md`.

**Cần quyết định:** dùng bộ UX nào. Có thể `2026-08-15` là mới nhất nhưng `2026-07-22` chi tiết hơn.

### ✅ No Sharded Document Duplicates

Không tìm thấy `index.md` sharded versions nào cho PRD/Architecture/Epics/UX, nên không có conflict whole-vs-sharded.

---

## Required Actions

- Xác nhận architecture spine và UX source-of-truth.
- Nếu có duplicates cần xóa/rename, làm trước khi continue.

**Document Discovery complete. Ready to proceed?**

**Select an Option:** [C] Continue to File Validation


## Step 2: PRD Analysis

### Source PRD
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`

### Functional Requirements Extracted

- **FR-1:** User Authentication — Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng.
- **FR-2:** API Access for External Clients — Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.
- **FR-3:** Workspace Lifecycle — Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.
- **FR-4:** Workspace Invites & Memberships — Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.
- **FR-10:** RBAC với ba system roles — System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại.
- **FR-6:** Built-in Scraper Connectors — Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route.
- **FR-7:** External OAuth Connectors — Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.
- **FR-8:** External MCP Connectors — Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.
- **FR-43:** VietnamWorks Scraper (Vietnam Job Market) — Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks.
- **FR-44:** TopCV Scraper (Vietnam Job Market) — Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot.
- **FR-45:** ITviec Scraper (Vietnam Job Market) — Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing.
- **FR-46:** Vietnam Job Market Aggregator (`vn_jobs.aggregate`) — Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. Nowing không giữ local search corpus.
- **FR-47:** PII Redaction for Job Data — Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`.
- **FR-48:** Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` — Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector search, and merge history. **Acceptance Criteria:** - ~~Given data from 3 sources about the same entity, when aggregated in Nowing, then they merge into one canonical entity with confidence score.~~ → `chainlens-research` canonical index. - ~~Given a canonical entity, when displayed, then it shows source count, conflict flags, and merge history.~~ → `chainlens-research` response. - ~~Given a merge, when admin reverts, then entity returns to pre-merge state.~~ → `chainlens-research` merge history. - Given canonical data contains PII, before indexing, then AD-25 redaction applies (in Nowing before ingest). **Status:** `[REMOVED 2026-08-08 — moved to chainlens-research; Epic 13 dropped]`.
- **FR-49:** News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent. **Acceptance Criteria:** - Given RSS feeds are configured, when polled (every 15 min), then new articles from VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet are fetched. - Given articles are fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`. - Given a user searches for news, when the query is submitted, then `chainlens-research` `POST /api/v1/search` returns indexed news articles with citations. - Given duplicate articles (syndicated across portals), when detected, then `chainlens-research` canonical index handles deduplication. **Status:** `[PROPOSED] — re-scoped to feed chainlens-research; no local Nowing news index.`
- **FR-50:** Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent. **Acceptance Criteria:** - Given CafeF API is connected, when a user queries a stock symbol, then price, OHLCV, and financial statements are fetched. - Given financial data is fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`. - Given financial data is indexed, when a user queries, then `chainlens-research` `POST /api/v1/search` returns results with citations. **Status:** `[PROPOSED] — re-scoped to feed chainlens-research; no local Nowing financial index.`
- **FR-51:** Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent. **Acceptance Criteria:** - Given masothue.com data is integrated, when fetched, then company profiles are normalized to `Chunk[]` and sent to `chainlens-research` via `POST /v1/ingest/scraper`. - Given a user searches by company name or tax code, when the query is submitted, then `chainlens-research` `POST /api/v1/search` returns the company profile. - Given company data contains PII, before ingest, then AD-25 redaction applies. **Status:** `[PROPOSED] — re-scoped to feed chainlens-research; no local Nowing company index.`
- **FR-52:** E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent. **Acceptance Criteria:** - Given e-commerce scraper is built, when a user searches by product keyword, then product listings are fetched and normalized to `Chunk[]`. - Given product `Chunk[]` are produced, when the batch is ready, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`. - Given products from multiple platforms, when indexed, then `chainlens-research` canonical index handles deduplication. **Status:** `[PROPOSED] — re-scoped to feed chainlens-research; no local Nowing product index.`
- **FR-53:** Social Media Integration (Epic 18 — REMOVED, feature covered by E10) — As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content. **Status:** `[DONE — covered by Epic 10 existing scrapers]`. > **⚠️ Epic 18 removed (2026-08-06) — duplicate with existing scrapers.** YouTube, Reddit, Instagram, TikTok scrapers already built in Epic 10 (Connector & Scraper Expansion). FR-53 covered by FR-6 (Built-in Scrapers). **Acceptance Criteria:** - Given YouTube/Reddit APIs are connected, when a user searches, then video/posts data is returned. - Given social data is stored, when PII is detected, then AD-25 redaction applies.
- **FR-54:** Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) — As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing. **Acceptance Criteria:** - Given Google Custom Search API is configured, when a user searches, then web results are returned and crawlable. - Given Google Places API is configured, when a user searches by location, then business listings are returned. **Status:** `[DEFERRED — covered by ChainLens generic crawl for web search]`. > **⚠️ Epic 19 removed (2026-08-06) — duplicate with existing scrapers.** Google Custom Search trùng với ChainLens generic web crawl (FR-24, already built). Google Places data có thể complement BĐS data nhưng cần scope rõ ràng. **Potential conflict:** AD-DEFER-7 (no owned web index). Xem xét sau khi platform (E13) ship — nên dùng ChainLens thay vì build scraper riêng.
- **FR-55:** Global E-commerce (Epic 20 — REMOVED, feature covered by E2) — As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets. **Acceptance Criteria:** - Given Amazon/Walmart data sources are connected, when a user searches, then product listings with price, ratings are returned. **Status:** `[DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon)]`. > **⚠️ Epic 20 removed (2026-08-06) — duplicate with existing scrapers.** Walmart (Story 2.6) and Amazon (Story 2.7) already built as part of Epic 2 (Connectors).
- **FR-56:** Public Agent-Chat API for Vertical Clients — As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application. **Acceptance Criteria:** - Given a valid PAT and workspace membership, when `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, then a chat thread is created and returned with `thread_id` and `research_thread_id`. - Given a valid PAT, when `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called, then the message is processed by the chat agent and a response is returned. - Given an invalid PAT or non-member, when any public endpoint is called, then 401/403 is returned. - Given a `client_id` in the request, when the chat processes, then all data access is filtered by `client_id` (NFR-MULTI-1). - Given rate limit is exceeded, when the endpoint is called, then 429 is returned with `Retry-After` header. **Status:** `[PROPOSED]` — Epic 18 (Vertical Client Platform).
- **FR-57:** Agent Registry — As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents. **Acceptance Criteria:** - Given the migration runs, when complete, then an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`. - Given an `agent_id` is provided in a chat request, when processed, then the system loads the corresponding `AgentConfig` or returns 404 if not found. - Given a chat request with `agent_id`, when the chat flow starts, then `AgentConfig.system_instructions` is prepended to the default system prompt. **Status:** `[PROPOSED]` — Epic 18 (Vertical Client Platform).
- **FR-58:** Scraper Feed to chainlens-research (Ecosystem Integration) — As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine. **Acceptance Criteria:** - Given scraper output (BĐS, jobs, news, finance, company, e-commerce), when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with service-to-service auth. - Given a `Chunk[]` batch, when sent, then the request is idempotent keyed by `sourceId` and returns `ingestJobId`. - Given PII in the batch, before ingest, then AD-25 redaction is applied.
- **FR-59:** Gap-Fill Trigger via chainlens-research — As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus. **Acceptance Criteria:** - Given a chat query with public/vertical scope, when `chainlens-research` search returns low coverage, then `POST /v1/gap-fill` is triggered. - Given a gap-fill request, when `chainlens-research` decides a Nowing scraper is needed, then it calls the registered Nowing scraper and ingests the result. - Given gap-fill completion, when results are indexed, then the chat agent resumes with the updated corpus. **Status:** `[PROPOSED]` — depends on `chainlens-research` gap-fill engine (Epic 47).
- **FR-60:** Private Data Provider (NowingPrivateProvider) — As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries. **Acceptance Criteria:** - Given a chat query classified as private scope, when `chainlens-research` calls `POST /v1/private-data/search` on Nowing, then Nowing returns `Chunk[]` filtered by workspace RBAC. - Given a `NowingPrivateProvider` call, when the user does not have access to a document, then it is not returned. - Given private chunks, when returned, then `chainlens-research` merges them into its ranked result set without storing them. **Status:** `[PROPOSED]` — governed by `AD-15`, `AD-35`.
- **FR-61:** Cross-Project Service Auth & Cost Allocation — As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed. **Acceptance Criteria:** - Given a `chainlens-research` request to Nowing (`POST /v1/private-data/search`, scraper invocation), when received, then Nowing validates a service Bearer token and maps it to a workspace. - Given a Nowing request to `chainlens-research`, when sent, then Nowing includes a workspace-scoped Bearer token and correlation id. - Given a cross-project call, when completed, then `TokenUsage` records the cost with `usage_type` and workspace attribution. **Status:** `[PROPOSED]` — Epic 47.
- **FR-62:** Canonical Chunk Metadata Schema (`source` enum) — As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem. **Acceptance Criteria:** - Given any `Chunk` sent to `chainlens-research`, then `metadata` contains `source`, `sourceId`, `domain`, `fetchedAt`, `contentType` (required) and optional `confidence_score`, `source_count`, `conflict_flags`. - Given a `source` value, when validated, then it matches the canonical enum defined in `chainlens-research`: `public_crawl`, `nowing_scraper`, `brave`, `searxng`, `jina`, `exa`, `tavily`, `perplexity`, `private_provider`. - Given missing required fields, when validated, then the request is rejected with a typed error. **Status:** `[PROPOSED]` — governed by `AD-34`.
- **FR-63:** Intent Signal Detection `[PROPOSED]` — As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment. **Acceptance Criteria:** - Given a company in workspace, when signals are monitored, then funding events, job postings, tech stack changes, and executive moves are detected and surfaced. - Given a signal is detected, when displayed, then it includes signal type, confidence score, source URL, and timestamp. - Given multiple signals for the same company, when aggregated, then a composite lead score is calculated. - Signals are sourced from: Crunchbase, LinkedIn, company websites, job boards, news. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence).
- **FR-64:** Lead Scoring & Prioritization `[PROPOSED]` — As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects. **Acceptance Criteria:** - Given a set of leads, when scored, then each lead receives a composite score based on fit (firmographics, technographics) and intent (signal strength, recency). - Given a lead score, when displayed, then it shows score breakdown (fit vs intent), trend (improving/declining), and comparison to similar converted leads. - Given ICP criteria, when updated, then lead scores are recalculated for all leads in workspace. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence).
- **FR-65:** Enriched Contact Data `[PROPOSED]` — As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers. **Acceptance Criteria:** - Given a company, when contact enrichment is requested, then decision-maker names, titles, emails, and phone numbers are returned. - Given contact data, when verified, then email is validated via waterfall (5+ providers) and phone via real-time validation (9+ providers). - Given enrichment results, when displayed, then data source, verification status, and confidence are shown. - Zero-bounce validation for emails; real-time validation for phones. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence).
- **FR-66:** Outbound Prospecting Automation `[PROPOSED]` — As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality. **Acceptance Criteria:** - Given a lead list, when outreach is triggered, then personalized messages are generated using lead context + ICP + intent signals. - Given outreach sequences, when configured, then multi-channel sequences (email, LinkedIn, Zalo for VN) are supported. - Given a sequence step, when executed, then the system personalizes content, tracks delivery, and logs responses. - Given response detection, when a lead replies, then the sequence pauses and alerts the assigned rep. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence).
- **FR-67:** CRM Integration & Write-Back `[PROPOSED]` — As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth. **Acceptance Criteria:** - Given a CRM connection (Salesforce, HubSpot, Pipedrive), when lead data changes, then it syncs bidirectionally, phased per AD-40: Phase 1 read-only dedup, Phase 2 write-back, Phase 3 bidirectional sync. - Given a lead score or signal, when detected in Phase 2/3, then it writes to the corresponding CRM record. - Given CRM data, when imported, then it enriches Nowing's lead profiles. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence).
- **FR-68:** Zalo Integration (Vietnam Market) `[PROPOSED]` — As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform. **Acceptance Criteria:** - Given a Zalo OA connection, when configured, then outreach sequences can include Zalo messages. - Given a lead with Zalo contact, when outreach is triggered, then personalized Zalo messages are sent. - Given a Zalo reply, when received, then it's logged in the lead's activity timeline. - Comply with Zalo's business messaging policies and Decree 356. **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence). > **FR-24 đã chuyển sang §4.9.** ChainLens Research **không phải** một connector/scraper. Nó là Deep-Research Engine — dependency kiến trúc hạng nhất, governed by `AD-15` (không còn `AD-3`). Xem **§4.9**.
- **FR-8.1:** Exa MCP Search Connector `[DONE 2026-08-05]` — As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval. **Acceptance Criteria:** - Owner có thể POST `/search-source-connectors` với `connector_type: "EXA_MCP_CONNECTOR"` và optional `exa_api_key`; backend persist connector với `server_config` trỏ `https://mcp.exa.ai/mcp`, `x-api-key` injected as header, `is_indexable = false`. - Multi-agent chat discover chỉ `web_search_exa` và `web_fetch_exa`, đánh dấu `readonly` để không hiện HITL prompt.
- **FR-9:** Document Upload, Parse & Index — Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng.
- **FR-11:** Folders & Document Management — Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.
- **FR-12:** Hybrid Search over Knowledge Base — Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`.
- **FR-13:** Citation Panel for Knowledge-base Chunks — Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel.
- **FR-32:** Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` — Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP). **Phạm vi MVP:** trọng tâm **semantic facts**; schema hỗ trợ đủ 4 memory type nhưng MVP dùng semantic. Bảng `memory_relations` đã có; graph traversal phong phú = fast-follow. **Acceptance Criteria:** - ✅ `Memory` có `content`, `type` (mặc định `semantic`), `source_type`/`source_id`, `tags`, `confidence` (REAL, mặc định 1.0), `embedding`, `workspace_id` — **đã có** (migration 177; ORM `app/db.py`). - ⚠️ **Dedupe (primitive ĐÃ CÓ):** `repository.py` merge khi cosine distance `<=>` < 0.08 (~similarity > 0.92) + `update_on_duplicate`, tách scope user vs workspace. Open: **validate/tune ngưỡng qua eval** (AR-3) + phủ path auto-extract. - ⚠️ **Recall hit** = memory trong top_k (mặc định ≤5) đã rank hybrid, vượt ngưỡng similarity — endpoint `/memories/search` tồn tại; ranking + ngưỡng cần verify + gate (NFR-8). - 🔴 **Vế "vượt ngưỡng similarity" HIỆN KHÔNG ÁP ĐƯỢC (verify 2026-07-25).** `search.py:97` tính RRF score rồi `return [row[0] for row in rows]` bỏ đi; `memories_routes.py:117` hardcode `score=0.0`. Eval buộc chạy `required_oracle_mode: rank_only`. ⇒ **FR-32 hiện định nghĩa một thứ code không làm được.** Việc expose score từng hoãn sang `3-11` nhưng `3-11` đã `done` mà không làm ⇒ **đã giao lại cho `3-14`**. Xem NFR-1c. - Không `Memory` nào ghi mà thiếu `source_type`/`confidence`.
- **FR-33:** Research Continuity — Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó. **Acceptance Criteria (MVP):**
- **FR-34:** Memory Correction — Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history. **Acceptance Criteria (MVP):** - "Correct" = tạo `MemoryVersion` mới, giữ `previous_content` + `corrected_content` + `corrected_by` + timestamp; memory cũ KHÔNG bị xoá cứng. - **Phạm vi propagation (MVP):** chỉ cập nhật chính memory đó; KHÔNG propagate đệ quy qua relation graph (contradiction/relation resolution = post-MVP). - Recall sau correction trả về bản mới nhất theo mặc định.
- **FR-36:** Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` — > **✅ ĐÓNG 2026-07-25.** Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. Story `3-10a-legacy-memory-data-safety-spike` = `done`. Recovery path cũng đã build phòng ngừa (`3-10b` = `done`): guard G1.2 trong `178.upgrade()` (raise nếu legacy data chưa backfill) + command app-level `scripts/backfill_legacy_memory.py` (embeddings không chạy được trong raw migration) + 5 integration test xanh. **Deploy-order bắt buộc: mig177 → backfill → mig178.** Phần mô tả rủi ro dưới đây giữ lại làm ngữ cảnh lịch sử. Migration `177_add_research_memory_tables` tạo bảng `memories` NHƯNG **không backfill** dữ liệu markdown cũ; `178_drop_legacy_memory_columns` sau đó **DROP** `user.memory_md` và `workspaces.shared_memory_md`. Grep toàn `nowing_backend` **không thấy migration nào chuyển `memory_md` → `memories`**. ⇒ Memory markdown cũ của user/team **có khả năng đã bị xoá mà không được migrate** (không phải rủi ro tương lai — có thể đã xảy ra). **Acceptance Criteria:** - Xác định **178 đã apply trên prod chưa** (kiểm tra `alembic_version` prod / lịch sử deploy). - Nếu **đã apply**: đánh giá phạm vi mất dữ liệu; nếu cần, khôi phục từ backup DB → parse `memory_md`/`shared_memory_md` → `memories` (`source_type='manual'`, `confidence` mặc định) qua `MemoryRepository`. - Nếu **chưa apply**: viết migration backfill `memory_md` → `memories` và chèn TRƯỚC 178 (hoặc hoãn 178) rồi mới drop. - Nếu mất dữ liệu không hồi được: thông báo user hiện hữu (ảnh hưởng niềm tin "pivot lần 2").
- **FR-40:** First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` — > **Vấn đề, đo bằng code.** `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). **Không có đường nào extract từ scrape run, deep research, hay document upload.** Cộng với việc workspace mới **không seed gì** (`grep seed|sample|onboarding|welcome|starter|template app/routes/workspaces_routes.py` = **rỗng**; `scripts/` không có seed script), hệ quả là: > > **`nowing_recall` ở session đầu trả rỗng — không phải vì bug, mà vì cấu trúc.** Memory chỉ tồn tại sau khi người dùng đã chat. Người dùng mới không có gì để recall, kết luận sản phẩm không chạy, và bỏ đi **trước** khi tới giá trị thật ở session 2. Đây là **M1 (first-run value ≤ 15 phút)** — hiện **không tồn tại**. > > **Và nó làm câu định vị của brief thành không đúng.** Brief §1: *"it remembers what it went and found, not just what you told it."* Code hiện tại **chỉ** làm nửa sau (`what you told it`). Nửa trước — `what it went and found` — **chưa có writer nào**. **Quyết định (2026-07-25): làm cho hành động research ĐẦU TIÊN sinh ra memory. KHÔNG seed dữ liệu mẫu.** | Phương án | Phán quyết | Lý do | |---|---|---| | **(a) Research run → memory** | ✅ **CHỌN** | Chứng minh đúng cái differentiator; recall có nội dung sau **một** hành động, không cần chat trước | | (b) Seed sample workspace | ❌ Loại | Memory giả dạy sai mental model ("nó biết vì được nhồi" thay vì "nó tự đi tìm"); và sẽ **đổ thêm rác vào đường inject chưa có chặn trên** (NFR-1b) | | (c) Onboarding tour thuần UI | ❌ Loại | Không tạo memory ⇒ recall **vẫn** rỗng. Chữa triệu chứng, không chữa nguyên nhân | **Ba thứ (a) đóng cùng lúc:** 1. **M1 first-run value** — mục tiêu adoption chính. 2. **`MemorySourceType.SCRAPER_RUN`** khai báo ở `app/db.py:572` **chưa có writer nào**. FR-40 chính là writer đó — enum cho việc này **đã tồn tại sẵn**. 3. Câu headline của brief trở thành **đúng**. **Acceptance:** - **Given** người dùng mới vừa tạo workspace, **When** chạy **một** research/scrape run bất kỳ (8 platform / 14 verb sẵn có, hoặc deep research), **Then** run đó sinh ra memory có `source_type = SCRAPER_RUN` + provenance, **không** cần chat trước. - **Given** run vừa xong, **When** gọi `nowing_recall`, **Then** trả về fact **có citation trỏ về run gốc** (không phải rỗng). - **Given** một người dùng mới hoàn toàn, **When** đo từ signup → run đầu → recall có nội dung, **Then** **≤ 15 phút** (M1). - **And** memory sinh ra tuân **NFR-1b** (đếm vào ngân sách 8.000 chars ở đường đọc — đây chính là lý do loại phương án (b)). - **And** tôn trọng kill-switch sẵn có (`MEMORY_AUTO_EXTRACT_ENABLED` global + `workspaces.memory_auto_extract_enabled` per-workspace, story `8-8` = done) và spend cap `8-7`. **Phụ thuộc:** provenance đầy đủ cần `9-6a` (`AD-11.1`: `source_capability` + `source_input` + soft `source_run_id`). **Nhưng không hard-block:** bản tối thiểu (`source_type = SCRAPER_RUN` + `source_run_id`) chạy độc lập được, nên `3-13` khởi động không cần chờ `9-6a`. **Cảnh báo retention:** `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) — memory phải **tự chứa** đủ ngữ cảnh, vì `Run` gốc sẽ bị xoá sau 30 ngày. Đây đúng là lý do `AD-11.1` tồn tại. Ghi chú schema: `Memory.source_id` là `Integer` (`app/db.py:2077`) còn `Run.id` là **UUID** (`app/db.py:3155`) ⇒ **không dùng được `source_id` cho run**, phải đi qua trường `source_run_id` của `AD-11.1`. **Truy vết:** brief §9 H-4 → FR-40 → story `3-13`. **Status:**
- **FR-5:** AI File Sorting (REMOVED) — Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172.
- **FR-14:** Chat Threads & Messages — Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`.
- **FR-15:** Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` — Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware.
- **FR-16:** Real-time Collaborative Chat — Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.
- **FR-17:** Anonymous Chat with Quota — Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.
- **FR-42:** Chat Response Benchmark — Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.
- **FR-21:** Report Generation & Export — Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.
- **FR-22:** Podcast & Video Presentation — Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes.
- **FR-23:** Image Generation — Tạo ảnh từ prompt, model, size, style, quality, response_format.
- **FR-18:** Automation Action Types  `[DONE — cải chính 2026-07-25]` — Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`. > **⚠️ Cải chính 2026-07-25 (readiness check C-A).** Bản trước ghi *"direct write-back actions chưa được implement dưới dạng action type riêng"* và *"`__init__.py` chỉ import `agent_task`"* — **SAI**. Verify code: registry thực tế import **6 action type**. **Consequences (verified 2026-07-25):**
- **FR-19:** Automation Triggers — Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event).
- **FR-20:** Automation Runs & Retries — Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy.
- **FR-35:** Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` — Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu. > **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Bản trước ghi `[GAP]` *"Chưa có `memory_change` trigger và `continue_research` action"* — **SAI**. Ba tài liệu cùng sai (PRD, `epics.md` Story 6.5, `merge-to-prod-checklist.md`); `sprint-status.yaml` (`6-5: done`) là bên **đúng**. **Consequences (verified 2026-07-25 — cả ba mảnh đều tồn tại):** - ✅ Trigger type `memory_change` — `app/automations/triggers/builtin/memory_change/` (`params.py`, `selector.py`; docstring tham chiếu AC-2 → build từ story có AC). Đăng ký trong `triggers/builtin/__init__.py`: `from . import event, memory_change, schedule`. - ✅ Action `continue_research` — `app/automations/actions/builtin/continue_research/`, đăng ký trong `actions/builtin/__init__.py`. - ✅ `AutomationRun.research_thread_id` — `app/db.py:712` + relationship (`app/db.py:746`); resolve qua `app/automations/dispatch/launch.py:44` (`resolve_research_thread_id`). - Guard chống vòng lặp: `selector.py` nêu rõ *"a memory-writing automation cannot re-fire a matching `memory_change` trigger"*. **Status:** `[DONE]` — story `6-5-memory-driven-automations` = `done`. **Không còn là post-MVP.**
- **FR-25:** Web Client (Next.js) — Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`.
- **FR-26:** Desktop Client (Electron) — Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.
- **FR-27:** Browser Extension (Plasmo) — Thu thập lịch sử duyệt web và gửi về backend.
- **FR-28:** Obsidian Plugin — Đồng bộ vault qua REST API `/obsidian/*`.
- **FR-29:** MCP Server — MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`.
- **FR-30:** Token Usage Tracking — Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`.
- **FR-31:** Credit Wallet & Purchases — `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit.
- **FR-41:** Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` — Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64`) thông qua một trang settings trên web UI, **không cần** sửa file/env và restart backend. **Vấn đề hiện tại (verified 2026-07-25/26):**
- **FR-69:** Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10) — As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered. **Acceptance Criteria:** - Given a pricing plan, when selected, then outcome-based option is available: pay per qualified meeting booked OR pay per lead enriched. - Given a meeting is booked via Nowing outreach, when confirmed, then the cost is attributed to the workspace. - Given a lead is enriched, when data is delivered, then per-lead pricing is applied. - Given usage, when tracked, then the dashboard shows cost-per-meeting and cost-per-lead metrics. - Outcome pricing works alongside existing seat-based pricing (users can choose). **Pricing Tiers (proposed):** | Model | Entry | Growth | Enterprise | |-------|-------|--------|------------| | **Seat-based** | $29/mo (5 users) | $99/mo (unlimited) | Custom | | **Outcome-based** | $50/meeting booked | $30/meeting (volume) | Custom | | **Lead enrichment** | $0.50/lead | $0.20/lead (volume) | Custom | **Status:** `[PROPOSED]` — Epic 21 (Lead Gen Intelligence). Depends on FR-66 (outbound automation).
- **FR-24:** Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` — Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool. **Contract (🔒 không được break — verified 2026-07-25):** - Endpoint: `POST {CHAINLENS_API_URL}/api/v1/search`, SSE. - Auth: `Authorization: Bearer <CHAINLENS_API_KEY>` — **service-to-service**. Nowing giữ một key; ChainLens không biết end-user. Định danh/hạn mức end-user do Nowing quản. - Request: `{ query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId? }` — `tier: "research"` và `stream: true` là một phần của contract (đã thêm từ 9.1a). - Response: data-only SSE frames (`data: <json>\n\n`); `type` nằm trong JSON payload (`type:block` / `type:updateBlock` RFC6902 patch, `type:done`, `type:error`); terminal thật là `{"type":"done", "chatId": ..., "webUrl": ...}` — **không** có dòng `event:` hay sentinel `data:[DONE]`. - Contract này **versioned + regression-guarded** ở phía Nowing (story **9.1b**) và phía ChainLens (`42-2`). **Acceptance Criteria:** - Query được kiểm soát bởi Pydantic `ResearchInput.query` (`min_length=1`, `max_length=500`) với `field_validator("query", mode="before")` `_strip_query`; query > 500 ký tự, rỗng, hoặc toàn khoảng trắng sau strip bị từ chối trước khi gọi engine. Executor không clamp thêm. - Mọi câu trả lời có `sources[]` giữ nguyên thứ tự trích dẫn để map về citation UI. - **Mode default = `balanced`** (D3, 2026-07-25). `quality` là **opt-in tường minh** — khi user/agent yêu cầu deep-research hoặc deliverable. Lý do: theo ChainLens `report-per-mode.md` (2026-08-02, `tier=research`), `quality` = **$0.0671** / call vs `balanced` = **$0.0482** / call (~**1.4×**), và trước 2026-07-25 Nowing âm thầm gọi `quality` cho **mọi** call (`schemas.py:38`). Story 9.3 validate chất lượng trên `nowing_evals` trước khi khoá; reversible qua env. - Contract regression test tồn tại và chạy trong CI bằng marker `contract: contract regression tests for ChainLens integration` trong `pyproject.toml`; target `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`. - Fixture SSE regression được đồng bộ với ChainLens 42-2 qua local copy `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và drift test `tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
- **FR-37:** Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` — Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán. **Vấn đề hiện tại (verified 2026-07-25):**
- **FR-38:** Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` — Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens. > **⚠️ FR này là yêu cầu MÔ HÌNH KINH DOANH, không chỉ reliability (D5, 2026-07-25).** Vì engine closed-source và Nowing public (§1.1), **mọi self-host instance đều chạy ở trạng thái không có engine**. Thiếu FR-38 thì self-host **không dùng được**, và toàn bộ đường OSS/PLG sụp. Đây là lý do story **`9.1a`** là **điều kiện tiên quyết trước khi public repo** và chạy **trước `9.1b`/`9.2`** — dù `9.2` có giá trị tài chính trực tiếp hơn. **Vấn đề hiện tại (verified 2026-07-25):** `executor.py:192-198` chỉ raise `CHAINLENS_TIMEOUT` sau `CHAINLENS_REQUEST_TIMEOUT_SECONDS` (default **300s**). Không có fallback, dù chính Nowing đã có hybrid search (FR-12). **Acceptance Criteria:** - ChainLens timeout / 5xx / không cấu hình (`CHAINLENS_API_KEY` rỗng) → Nowing **degrade** sang hybrid search trên KB và trả trạng thái tường minh: `partial` (có evidence một phần) hoặc `engine_unavailable` (không có). - Trạng thái degrade hiển thị được cho user/agent — **không** giả vờ là câu trả lời đầy đủ, và **không** bịa citation. - Self-host không cấu hình ChainLens: mọi tính năng khác của Nowing hoạt động bình thường; deep research trả `engine_unavailable` với hướng dẫn cấu hình. - Fallback rate được đo (nối vào SM-11). - Có test cho cả ba nhánh: success / timeout-degrade / unconfigured.
- **FR-39:** Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` — Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không. **Vì sao quan trọng:** đây là tiền đề của differentiator *"memory có nguồn sống, tự re-validate"* — thứ phân biệt Nowing với các memory layer khác sau khi "memory có citation" đã thành table-stakes (xem `briefs/brief-Nowing-2026-07-25/brief.md` §4). Chính báo cáo Mem0 (~18/07/2026) thừa nhận memory staleness + temporal abstraction là bài toán chưa ai giải. Nowing có lợi thế cấu trúc vì **sở hữu đường ingest** — nhưng lợi thế đó hiện chưa dùng được. **Vấn đề hiện tại (verified 2026-07-25):** | # | Vấn đề | Bằng chứng | |---|---|---| | 1 | **Lệch kiểu:** không lưu được id của `Run` vào `Memory` | `Run.id` = `UUID` (`app/db.py:3155`) · `Memory.source_id` = `Integer` (`app/db.py:2077`) | | 2 | **Không có writer:** `MemorySourceType.SCRAPER_RUN` khai báo rồi bỏ đó | `grep -rn "SCRAPER_RUN"` chỉ khớp khai báo enum `app/db.py:572` | | 3 | **Run bị xoá sau 30 ngày** → re-validate hỏng sau một tháng dù đã nối được | `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) | **Nền tảng đã có (không phải xây lại):** `Run` lưu `capability` (ví dụ `reddit.scrape`) **và `input` JSONB** (`app/db.py:3155-3170`) — đủ để **re-execute chính xác truy vấn cũ**. Đây là phần đắt nhất, và nó đã tồn tại. > **✅ Phương án đã chốt — `AD-11.1` (2026-07-25).** Bản trước để ngỏ *"chọn một: retention có điều kiện HOẶC sao `capability`+`input`"* — quyết định kiến trúc nằm trong AC nên không testable (readiness Q-2). Nay chốt: **`Memory` tự chứa recipe, KHÔNG dùng retention có điều kiện cho `runs`.** Lý do: cleanup `runs` là cơ hội (~1% insert) nên thêm điều kiện biến nó thành truy vấn có khoá; `runs.output_text` (JSONL) giữ vô hạn là đắt sai chỗ — cần *recipe* chứ không cần *payload*; và AD-11 đã định nghĩa memory là first-class persistence layer nên nó không được phụ thuộc lifecycle của bảng log. **Acceptance Criteria:**

**Total FRs:** 70

### Non-Functional Requirements Extracted

- **NFR-1:** Performance — > **⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5).** NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra **hai đường recall khác nhau**, và chỉ một đường được PRD mô tả: > > | Đường | Nơi chạy | Chặn lượt chat? | PRD cũ mô tả? | Bound cũ | > |---|---|---|---|---| > | **Memory injection** | `MemoryInjectionMiddleware.abefore_agent` | ✅ **CÓ — mọi lượt** | ❌ **KHÔNG** | ❌ không có | > | **Recall tool** | `nowing_recall` · `/memories/search` | chỉ khi agent gọi | ✅ FR-32 (top_k ≤5 hybrid) | ✅ top_k | > > Đường thứ nhất là đường **nóng nhất** và **không có trong PRD**. Nó chạy `SELECT` mọi `Memory` row của workspace `ORDER BY created_at`, **không LIMIT**, **bỏ qua cả hai index chuyên dụng** (`ix_memories_embedding` HNSW + `ix_memories_content_search` GIN) đã tồn tại sẵn trong schema. Xem `AD-18`. > > **Đồng thời sửa một tiền đề SAI của P-5:** P-5 ghi *"auto-extract cộng latency **mỗi turn**"*. **Không đúng.** Caller duy nhất của `extract_from_turn` là `app/tasks/celery_tasks/memory_extraction_task.py` → chạy **trên Celery, ngoài request**. Auto-extract **không** nằm trên critical path. Nửa còn lại của P-5 (thiếu bound cho `recall`) **đúng**, và đúng nặng hơn dự kiến. **NFR-1a — CRUD & scraper (giữ nguyên)** - API response p95 < 500ms cho CRUD; scraper call có thể mất vài giây nhưng streaming updates qua SSE. - Hybrid search trên pgvector với limit phù hợp. **NFR-1b — Memory injection (CHẶN mọi lượt chat)** `[DONE — story 3-14]` - DB time p95 **≤ 150ms**, độc lập với số memory row của workspace (⇒ **O(top-k), không O(N)**). - Tổng ký tự memory được inject **≤ 8.000 chars**, **enforce ở đường ĐỌC**. Hiện `MEMORY_HARD_LIMIT = 25.000` chỉ validate **một** `content` ở đường **GHI** (`validate_memory_size`), nên với N fact thì aggregate **không có chặn trên** — middleware chỉ *báo* `chars=` cho LLM và nhờ nó tự consolidate. - Phanh duy nhất hiện tại là `<memory_warning>` ở `MEMORY_SOFT_LIMIT = 18.000` — một vòng lặp **phụ thuộc LLM hợp tác**. Nó không thể đóng được lỗ này vì auto-extract (Celery) ghi thêm row mà LLM chưa từng consolidate. - Fail-soft hiện tại (`except → return None`) **được giữ**, nhưng phải phát **counter** khi rơi vào nhánh đó — hiện chỉ có `logger.exception`, nên recall vắng mặt là **im lặng**. - Đã có sẵn hook đo: `_perf_log.info("[memory_injection] ... db=%.3fs total=%.3fs")`. ⇒ Việc còn lại là **chốt ngân sách + assert**, không phải dựng instrumentation. **NFR-1c — Recall tool (`nowing_recall`, `/memories/search`)** `[DONE — story 3-14]` - Giữ đúng định nghĩa FR-32: top_k ≤ 5, đã rank hybrid, vượt ngưỡng similarity. - p95 **≤ 300ms**. > **🔴 TỰ CẢI CHÍNH 2026-07-25 — vế "vượt ngưỡng similarity" HIỆN KHÔNG ĐẠT ĐƯỢC.** Bản đầu của NFR-1c (do chính lượt này viết) nhắc lại định nghĩa FR-32 mà **không verify nó có implement được không**. Verify sau đó cho thấy **không**: > - `app/services/memory/search.py:97` tính RRF score và `order_by(text("score DESC"))` — score **có** tồn tại > - nhưng cùng file `return [row[0] for row in rows]` → **bỏ score đi** > - `app/routes/memories_routes.py:117` hardcode **`score=0.0`** > > ⇒ **Không client nào — kể cả eval harness — nhìn thấy được similarity.** `nowing_evals/.../memory/recall/gate.yaml` phải đặt `required_oracle_mode: rank_only` và ghi thẳng lý do. `deferred-work.md:35` xác nhận: *"clause `min_similarity` của oracle AC-3 không bao giờ áp được, eval chỉ chấm theo rank"*. > > **Dependency treo:** `gate.yaml` hoãn việc expose score sang **story `3-11`**, nhưng `3-11` đã `done` (*"dedupe đã wire; tuning ngưỡng optional qua 3-9"*) và **không expose score**. Hai note trỏ vòng vào nhau: `3-11` chỉ sang `3-9`, `3-9` chỉ sang `3-11`. **Việc này mất chủ.** > > **Đã giao chủ: `3-14`.** Lý do gộp vào đó chứ không mở story mới: `3-14` đã sửa đúng `search.py` + đường recall (`AD-18` rule 1 — bounded top-k retrieval **buộc** phải làm việc với score), và NFR-1c phụ thuộc trực tiếp. > > **Hệ quả với NFR-8, nặng hơn vẻ ngoài:** oracle `rank_only` chỉ hỏi *"có nằm trong top 5 không"*, **không** hỏi *"có thật sự đủ giống không"*. Gate có thể **PASS** với kết quả rác chỉ vì nó tình cờ rank top-5. ⇒ Đây là **lý do thứ hai** để `3-14` chạy **trước khi chốt số SM-10** của `3-9` — bên cạnh lý do O(N) ở `AD-18` rule 6. Đo baseline dưới oracle bị làm yếu thì con số chốt ra sẽ dễ hơn thực tế. **NFR-1d — Auto-extract (Celery, KHÔNG chặn lượt chat)** `[DONE — story 3-14]` - **Bất biến:** auto-extract **không được** nằm trên critical path của lượt chat. Cần **regression test** khoá bất biến này (hiện đúng nhờ Celery, nhưng không có test nào giữ). - Freshness: memory mới khả dụng cho recall p95 **≤ 60s** sau khi lượt chat kết thúc. - Ngân sách chi phí do story `8-7` phủ (spend cap). **Truy vết:** NFR-1b + NFR-1c + NFR-1d → `AD-18` → story `3-14`. NFR-1b là điều kiện tiên quyết của **NFR-8** (recall quality): không thể đo chất lượng recall khi lượng inject phụ thuộc N. **Status:**
- **NFR-2:** Security & Auth — - JWT/cookie từ `fastapi-users`; PAT cho external clients. - Permission check trên mọi workspace-scoped endpoint. - Secrets qua `.env`, không hardcode.
- **NFR-3:** Observability — - OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter. - Celery task monitoring.
- **NFR-4:** Reliability — - Async DB I/O bằng SQLAlchemy async. - Celery + Redis cho background tasks. - Retry policy cho automation runs và scraper calls.
- **NFR-5:** Multi-tenancy Isolation — - Mọi workspace-scoped query lọc theo `workspace_id`.
- **NFR-6:** Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]` — Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor. > **⚠️ Cải chính 2026-07-25 (readiness check U-4).** Bản trước ghi `[GAP]` với lý do *"`editorPanelAtom` không có trường `chunkId` hay highlight state"* — **SAI**. Verify code: `nowing_web/atoms/editor/editor-panel.atom.ts` **có** `chunkId: number | null` (dòng 12, 23, 38, 64, 79, 93), và logic dùng nó nằm ở `components/editor-panel/editor-panel.tsx` + `components/editor/plugins/citation-kit.tsx`. > > Đây là bất nhất **4 chiều** đã được phân xử bằng code: `ARCHITECTURE-SPINE` `AD-DEFER-1` nói DEFERRED · PRD nói `[GAP]` · `epics.md` nói `[DONE]` · `sprint-status.yaml` `3-6` nói `done`. **Code xác nhận đã xong** → `AD-DEFER-1` đã được đóng cùng lượt này. **Status:** `[DONE]` — story `3-6-citation-scroll-to-highlight-in-full-document-editor` = `done`.
- **NFR-7:** Usage & Credit Dashboard `[DONE]` — Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`. **Status:**
- **NFR-8:** Recall Quality (eval-gated) `[DONE — story 3-9]` — Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory. - Dùng harness `nowing_evals` chạy trên tập truy vấn thực để đo **precision@k** và **noise rate** của `nowing_recall`. - Đặt ngưỡng tối thiểu (ví dụ precision@5 ≥ ngưỡng cấu hình; noise ≤ ngưỡng) — **không ship nếu chưa đạt**. - Ngưỡng cụ thể chốt cùng SM-10. **Status:**
- **NFR-9:** Deep-Research Latency & Availability Budget (hai trạng thái) — Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng cấp khi có số đo. **Bối cảnh (verified 2026-07-25 — đọc kỹ trước khi trích số):** - Lần đo cuối (`nfr6-final-20-8-v2-postfix.md`, 2026-07-18) verdict **FAIL**: Ask avg 57–136s (target ≤8s), Reason 50–160s (≤35s), Research quality 198s (>180s), citation 50–88% (≥95%). - **NHƯNG con số đó có thể đã stale.** `technical-deep-research-quality-latency-roadmap-2026-07-25.md` §0: *"ChainLens ĐÃ tối ưu latency rất nhiều nhưng CHƯA đo kết quả"* — `ADR-DEEP-RESEARCH-SPEED` phases 1-7 **done** (budget tuning −37%, pipeline parallelization, speculative prefetch, race Crawl4AI+Jina, precompute embeddings, cache TTL) nhưng story `20-0`/`20-8` = backlog. - → Trạng thái đúng là **"chưa biết"**, không phải "chậm". Vì vậy ChainLens đặt `43-1 eval-harness` làm **GATE 0**. - Lộ trình giảm latency phía ChainLens (Epic 43): `43-2` planner-DAG parallel sub-research (*lever lớn nhất*), `43-5` semantic cache hit-rate >60%, `43-4` multi-stage rerank; cộng `29-5` cost routing (done). **Ba đòn bẩy này không phụ thuộc owned index.** Đòn bẩy "index search" thuộc Epic 26 — DEFERRED 0/7 gates, **không near-term**, và trùng NG-1/`AD-DEFER-7`. **State A — mặc định hôm nay (bắt buộc):** - Nowing **phải** có đường **async deliverable** cho deep research: submit → progress → notify → deliverable. Không block một chat turn. - **✅ Cải chính 2026-07-25 (`AD-17`):** hạ tầng async **đã tồn tại end-to-end**, không phải xây mới — `?mode=async` → 202 + `X-Run-Id`, SSE `GET .../runs/{id}/events`, ring buffer replay 500 event, cancel, history; web đã có typed client; `chainlens.research` đã nằm sau door đó. **Ba việc còn thiếu thật:** (1) `run_event_bus` hiện **single-process** → cần Redis pub/sub sau cùng interface trước khi bật trên nhiều replica; (2) **agent door đang sync** → đây mới là chỗ block chat turn; (3) không có `Notification` khi `run.finished` và kết quả chỉ nằm trong `runs.output_text` (TTL 30 ngày), chưa thành deliverable hạng nhất. Delivery **đi SSE**, **không** thêm `runs` vào `ZERO_PUBLICATION` (`AD-5` giữ nguyên). - Lý do chọn A làm sàn: **async là superset của sync.** Xây async rồi latency giảm mạnh → vẫn đúng, chỉ trả về nhanh hơn. Xây *chỉ* sync rồi latency không giảm → sản phẩm vỡ. A là lựa chọn không cược vào giả định nào. - Nowing đo **p50/p95 per mode từ phía mình** (không chờ engine tự báo). - Availability: engine unavailable → FR-38 degradation. Fallback rate đo được (SM-11). **State B — mở khoá sau (sync chat-mode):** - Điều kiện: ChainLens `43-1` (GATE 0 eval-harness) land → `43-2` + `43-5` land **và có số đo**; Nowing story `9.3` xác nhận p95 vượt ngưỡng do Nowing đặt. - Khi đủ điều kiện: bật sync chat-mode **sau feature flag**, giữ nguyên đường async. - **Không** phụ thuộc Epic 26 / owned index. **Baseline từ ChainLens (2026-08-01, non-search, n=57, model `agy/gemini-3.6-flash-*`):** | Mode | p50 | p95 | Target p95 | Kết luận | |---|---|---|---|---| | speed | 24,189 ms | 34,964 ms | ≤ 30,000 ms | ❌ p95 vượt 30s | | balanced | 30,681 ms | 69,888 ms | ≤ 30,000 ms | ❌ p95 vượt 30s | | deep | 42,922 ms | 114,513 ms | ≤ 60,000 ms | ❌ p95 vượt 60s | - HTTP success 100%; fail/degraded do SearXNG CAPTCHA/rate-limit.
- **NFR-10:** Chat Response Regression Gate — Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.
- **NFR-11:** Scraping Compliance & Anti-Bot Resilience — **1. ToS & Legal (Vietnam job market):** - Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use. - Phải hoàn thành legal counsel opinion về employment service provider classification trước khi pilot bắt đầu. - Giữ vững phân biệt Nowing là **research/memory layer**, không phải job board / ATS / employment intermediary. **2. Anti-bot (TopCV/ITviec):** - TopCV yêu cầu anti-bot POC pass trước merge. - ITviec hiện chưa gặp Cloudflare, nhưng phải có rate-limit + user-agent rotation + circuit-breaker. - Không lưu raw challenge/CAPTCHA tokens, không bypass Cloudflare bằng exploit. **3. PII (all job sources):** - PII detection phải chạy trước khi lưu `jobDescription` / `jobRequirement` vào memory. - Không lưu phone, email, person names chưa mask; audit chỉ log counts. - PII detection coverage ≥95% of obvious PII. **4. Reliability:**

**Total NFRs:** 11

### PRD Completeness Assessment

- PRD contains full sections for FR and NFR.
- Several FRs marked `[PROPOSED]`, `[REMOVED]`, `[RE-SCOPED]`, or `[DONE]`; these should be validated against epics for coverage.
- FR-24 / FR-37 / FR-38 / FR-39 / NFR-9 are directly related to ChainLens integration and should be checked against architecture-unified-nowing-chainlens-dsh-2026-08-17.

---

## PROCEEDING TO EPIC COVERAGE VALIDATION

PRD analysis complete. Ready to load `./step-03-epic-coverage-validation.md`.


## Step 3: Epic Coverage Validation

### Source Epics Document
- `_bmad-output/planning-artifacts/epics.md`

### Epic FR Coverage Map (from epics.md lines 115-124)

| FR(s) | Epic(s) | Status |
| --- | --- | --- |
| FR-1/2/3/4/10 | E1 | DONE |
| FR-6/7/8 | E2 | DONE |
| FR-9/11/12/13 | E3 | DONE |
| FR-14/15/16/17/42 | E4 | DONE |
| FR-21/22/23 | E5 | DONE |
| FR-19/20 | E6 | DONE |
| FR-25/26/27/28/29 | E7 | DONE |
| FR-30 | E8 | DONE |
| FR-41 | E8.11 | DONE |
| FR-18 | E6.4 | DONE |
| FR-31/NFR-7 | E8.3 | DONE |
| FR-35 | E6.5 | DONE |
| FR-32 | E3 (3.8/3.9/3.11) | DONE |
| FR-33 | E4 (4.6) | DONE |
| FR-34 | E3/E4 | DONE |
| FR-36 | E3.10 | RESOLVED |
| FR-24/37/38/39/NFR-9 | E9 | DONE |
| FR-40 | E3.13 | DONE |
| NFR-1b/1c/1d | E3.14 | DONE |
| NFR-2/3/4/5/6/8/10/11 | E3.6, E4, E3.9 | DONE/PARTIAL |
| FR-43/44/45/46/47 | E12 | PROPOSED |
| FR-63/64/65/66/68/80-87 | E21 | DONE/READY |
| FR-67 | E21.5 | REVIEW |
| FR-69/88 | E21.7/21.18 | READY |
| FR-70-79 | E22 | READY |
| FR-89-92 | E23 | READY |

### Coverage Analysis

**Covered in PRD + Epics:** 60+ FRs/NFRs have traceable epic/story assignment.

**Gaps / Warnings:**

1. **PRD `prd-Nowing-2026-07-22/prd.md` predates Epic 26 and several new epics.** It does not contain:
   - **Epic 26** (FastMCP batch lead ingestion, stateless ChainLens pipeline, PII vault) — Story `26.1` is finalized in `ARCHITECTURE-SPINE.md` but **not** in PRD.
   - **FR-70–FR-92** (Telegram, Zalo, async scraper worker, RLS/partitioning, etc.) — added in epics after PRD freeze.
   - **NFR-9 / FR-37/38** appear in PRD but were re-bound to **Epic 9** via sprint change proposal 2026-07-25; PRD section may still reference old Epic 2.

2. **NFR-1 Performance** is marked `[PARTIAL]` in epics (bounds mơ hồ, no epic owner for base performance). This is a readiness risk.

3. **FR-67 (CRM Integration)** is in `REVIEW`, not `DONE`/`READY`.

4. **FR-43–FR-47 (Vietnam job market scrapers)** are `PROPOSED`; they have epics but not yet ready-for-dev.

### Coverage Statistics

- Total PRD FRs: 70
- Total PRD NFRs: 11
- FRs with epic coverage in epics.md: ~64
- FRs missing or outdated in epic coverage: ~6 (FR-5 removed, NFR-1 partial, plus Epic 26 not in PRD)
- New FRs in epics.md not in PRD: ~22 (FR-70–FR-92)

**Conclusion:** PRD và epics đã **không còn đồng bộ** — PRD cũ hơn epics. Cần either (a) cập nhật PRD để bao gồm Epic 26 và các FR mới, hoặc (b) chấp nhận architecture/spine mới làm source-of-truth cho Epic 26.

---

## PROCEEDING TO UX ALIGNMENT

Epic coverage validation complete. Ready to load `./step-04-ux-alignment.md`.


## Step 4: UX Alignment

### UX Documents Found

**UX 2026-07-22 (behavior contracts):**
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md` — NFR-9 State A
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-admin-global-model-config.md` — FR-41
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-chat-benchmark.md` — FR-42/NFR-10
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-usage-dashboard.md` — FR-31/NFR-7
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-sync-offline-indicator.md` — FR-38/NFR-9
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-first-run-onboarding.md` — FR-40
- (17 other contracts in same folder)

**UX 2026-08-15 (newer):**
- `ux-designs/ux-Nowing-2026-08-15/DESIGN.md`
- `ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`

### Alignment Issues

1. **Two UX sources not merged.** `2026-07-22` has many fine-grained contracts; `2026-08-15` is a newer design/experience doc. Không rõ cái nào là canonical. Cần hợp nhất hoặc chọn một.

2. **No UX contract for Epic 26 / Story 26.1.** Batch lead ingestion, ChainLens chunk ingestion, PII vault, Two-Tier Unlock UI, and opt-out/deletion workflow do not have explicit UX contracts. UI là implied (dashboard lead matrix, contact unlock button, opt-out form) nhưng chưa được spec.

3. **PII unlock UX (AD-105/AD-110) is specified in architecture but not in UX docs.** The Two-Tier Unlock (masked string → click → debit 1.5 credits → reveal) needs a UX contract to align with `is_unlocked`, `credit_micros_balance`, and `BillingEvent` flow.

4. **NFR-9 State A (async deliverable for deep research)** has a UX contract in 2026-07-22 (`ux-contract-async-deep-research.md`) — this aligns with architecture §3.5 / NFR-9.

### Warnings

- UX for Epic 26 is **implied but not specified**. Before UI build, need a UX contract for:
  - Lead batch matrix / Kanban after ingestion.
  - Contact unlock button + credit confirmation.
  - Blacklist/opt-out form for PII suppression.
- `ux-Nowing-2026-08-15` should be treated as the newest source, but must be reconciled with 2026-07-22 contracts.

---

## PROCEEDING TO EPIC QUALITY REVIEW

UX alignment assessment complete. Ready to load `./step-05-epic-quality-review.md`.


## Step 5: Epic Quality Review

### Scope

Đánh giá tập trung vào **Epic 26** và **Story 26.1** vì đây là epic đang được chuẩn bị cho implementation. Các epic khác đã được review trong các báo cáo trước (`epic-26-architecture-review-2026-08-17-v5.md`).

### Epic 26 — "Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure"

**Source:** `epics.md` + `26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`

#### User Value Focus

- Epic title mô tả kết quả cho người dùng/workspace (autonomous lead missions, unified ingestion).
- Story 26.1 có user value rõ: backend platform engineer có thể ingest batch leads và ChainLens chunks vào PostgreSQL với PII an toàn.
- Epic có phần technical infrastructure (FastMCP/DSH/ChainLens) nhưng được frame là enabler cho user outcome.

#### Independence

- Epic 26 phụ thuộc vào **ChainLens engine** (external) và **DSH sidecar** (AD-102). Đây là dependency hợp lệ (không phải forward dependency trong Nowing) nhưng cần contract ổn định.
- Không có forward dependency sang Epic 27+; Story 26.1 tự hoàn thành được với mock/fake ChainLens.

#### Story 26.1 Quality

| AC | Format | Testable | Specific | Notes |
| -- | ------ | -------- | -------- | ----- |
| AC-1 Batch lead ingestion | BDD Given/When/Then | Yes | Yes | Endpoint, schema, rate limit, HMAC, DNC, Fernet, response JSON |
| AC-2 Deterministic sorting & deadlock | BDD | Yes | Yes | `value_hmac` NOT NULL/UNIQUE, sort by `value_hmac ASC`, 20-thread concurrency test |
| AC-3 ChainLens chunk ingestion | BDD | Yes | Yes | API key auth, UUIDv5, 1536-dim embedding, `ON CONFLICT`, job status |
| AC-4 Zero-Cache CDC | BDD | Yes | Yes | Column list, `chunks` excluded |
| AC-5 Hermetic testing | BDD | Yes | Yes | $0 cost, ruff, test coverage |

- Các AC đều có Given/When/Then, testable, và specific.
- Task 1–7 rõ ràng, không chứa "setup all models" hay technical milestone.
- **Task 7 Contact Unlock Billing** nằm trong Story 26.1 về ingestion — có thể tách thành story riêng `26.2` cho đúng sizing. Tuy nhiên nó là một acceptance path của AC-1 PII encryption nên giữ lại cũng hợp lý.

#### Dependency Analysis

- Within-epic: Task 1 schema -> Task 2 service -> Task 3/4 route -> Task 5 ChainLens -> Task 6 tests -> Task 7 unlock. Không có forward reference.
- AC-3 references `ChainLensServiceAuth` (see OQ-7 / Story 39-1). Cần xác minh Story 39-1 đã done trước khi implement AC-3.

#### Best Practices Compliance Checklist

- [x] Epic delivers user value
- [x] Epic can function independently (with external ChainLens contract)
- [x] Stories appropriately sized
- [x] No forward dependencies
- [x] Database tables created when needed (migration in Task 1)
- [x] Clear acceptance criteria
- [x] Traceability to FRs maintained (FR-84, FR-85, FR-89, FR-92 — lead generation / lead infrastructure)

### Quality Findings

#### Minor Concerns

1. **Task 7 in Story 26.1** — contact unlock billing có thể là story riêng. Không phải blocker.
2. **AC-3 ChainLens auth dependency** — cần xác nhận Story 39-1 / OQ-7 đã done.
3. **Epic 26 title technical sound** — có thể reframe thành "Batch Lead Ingestion & Deep-Research Engine Integration" để rõ user value hơn.

#### No Critical/Major Issues

Epic 26 và Story 26.1 đạt tiêu chuẩn implementation readiness.

---

## PROCEEDING TO FINAL ASSESSMENT

Epic quality review complete. Ready to load `./step-06-final-assessment.md`.


## Step 6: Final Assessment

### Overall Readiness Status

**Epic 26: READY FOR DEV**

Architecture spine final, Story 26.1 đã đồng bộ, lint PASS, không còn BLOCKER/HIGH. Có thể chuyển giao cho dev.

**Overall Product (Nowing): NEEDS WORK**

PRD `prd-Nowing-2026-07-22/prd.md` đã lỗi thời so với epics; UX tồn tại ở 2 bộ source chưa hợp nhất; nhiều FR mới (FR-70–FR-92, Epic 26) chưa vào PRD.

### Critical Issues Requiring Immediate Action

1. **PRD drift:** ✅ **Đã xử lý bằng amendment** — `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-26-Source-of-Truth.md` chấp nhận `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` là source-of-truth cho Epic 26 và các FR mới không có trong PRD gốc.
2. **UX merge:** ✅ **Đã tạo UX contract cho Epic 26** — `ux-designs/ux-Nowing-2026-07-22/ux-contract-epic-26-lead-batch-ingestion.md`. Hợp nhất toàn bộ hai bộ UX (2026-07-22 vs 2026-08-15) là công việc riêng, ngoài phạm vi Epic 26.
3. **NFR-1 / FR-67:** ✅ **Đã ghi deferral** — `DEFERRALS-NFR1-FR67-2026-08-17.md`; không chặn Epic 26.

### Recommended Next Steps

1. **Chuyển Epic 26 sang dev** — architecture, story, và UX contract đã sẵn sàng.
2. **Cập nhật PRD gốc** nếu muốn merge amendment vào `prd.md` thay vì để nó standalone.
3. **Hợp nhất UX** toàn bộ khi có bandwidth (chọn canonical giữa 2026-07-22 và 2026-08-15).
4. **Chạy `bmad-spec` hoặc `bmad-create-story`** cho UI stories 26.2/26.3/26.4 sau khi backend 26.1 bắt đầu.

### Final Note

This assessment identified **7 issues** across **4 categories**. **Tất cả critical issues đã được xử lý hoặc ghi deferral.** Epic 26 READY FOR DEV.

**Assessor:** Devin Agent
**Date:** 2026-08-17

---

**Implementation Readiness Assessment Complete**

Report generated: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17.md`

The assessment found 7 issues requiring attention. Review the detailed report for specific findings and recommendations.
