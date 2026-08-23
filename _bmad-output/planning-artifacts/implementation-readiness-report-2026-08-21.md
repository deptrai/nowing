---
outputFile: '_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-21.md'
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment---

# Implementation Readiness Assessment Report

**Date:** 2026-08-21
**Project:** Nowing

## Step 1: Document Discovery

### PRD Documents Found

**Whole Documents:**
- `prds/prd-Nowing-2026-07-22/prd.md` (151 KB, 2026-08-20 14:46)

**Related / Amendment Files:**
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-12-21-22-23-Readiness-Correction-2026-08-17.md`
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-26-Source-of-Truth.md`
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Implementation-Readiness-Closeout-2026-08-20.md`
- `prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `prds/prd-Nowing-2026-07-22/validation-report.md`

### Architecture Documents Found

**Primary Architecture Spine:**
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (164 KB, 2026-08-16 15:44)

**Feature-Specific Architecture Spines:**
- `architecture/architecture-bds-planning-and-dkkd-2026-08-15/ARCHITECTURE-SPINE.md`
- `architecture/architecture-linkedin-b2b-2026-08-15/ARCHITECTURE-SPINE.md`
- `architecture/architecture-muasamcong-procurement-2026-08-15/ARCHITECTURE-SPINE.md`
- `architecture/architecture-shopee-ecommerce-2026-08-15/ARCHITECTURE-SPINE.md`
- `architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md`
- `architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`
- `architecture/architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md`

**Architecture Reviews & Updates:**
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6.md`
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v7.md`
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v8.md`
- `architecture/epic21-architecture-update.md`
- `architecture/unified-scope-chainlens-research-nowing-2026-08-08.md`

### Epics & Stories Documents Found

**Primary Epic Document:**
- `epics.md` (366 KB, 2026-08-21 14:46)

**Related Epic Proposals / Handoffs:**
- `epic21-proposal-2026-08-11.md`
- `implementation-artifacts/epic21-engineering-handoff-2026-08-11.md`
- `implementation-artifacts/epic21-ux-handoff-2026-08-11.md`
- `implementation-artifacts/epic21-ux-traceability-2026-08-11.md`
- `implementation-artifacts/epic21-readiness-recheck-2026-08-11.md`

### UX Design Documents Found

**Current UX Folder:**
- `ux-designs/ux-Nowing-2026-08-15/DESIGN.md` (7.5 KB, 2026-08-16 15:44)
- `ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md` (10 KB, 2026-08-20 03:27)
- `ux-designs/ux-Nowing-2026-08-15/ux-contract-readiness-gaps.md` (4.5 KB, 2026-08-20 03:27)
- `ux-designs/ux-Nowing-2026-08-15/ux-contract-first-run-onboarding.md`

**Epic-Specific UX Contracts:**
- `ux-design/epic21-lead-intelligence-ux.md`
- `ux-design/epic21-ux-wireframes-2026-08-11.md`
- `ux-design/ux-research-origami-final-2026-08-11.md`
- `ux-design/ux-research-origami-refresh-2026-08-11.md`
- `ux-spec-epic26-mission-control-phone-unlock-2026-08-20.md`

**Superseded Archive:**
- `ux-designs/archive/ux-Nowing-2026-07-22-superseded/`

## Issues Found

### Duplicates / Multiple Versions

1. **UX Design has two top-level folders:**
   - `ux-design/` (older, epic-specific files)
   - `ux-designs/ux-Nowing-2026-08-15/` (current DESIGN.md + EXPERIENCE.md)
   - `ux-designs/archive/ux-Nowing-2026-07-22-superseded/` (archived, deprecated)
   - **Resolution proposed:** Use `ux-designs/ux-Nowing-2026-08-15/` as the canonical current UX source.

2. **Architecture has one main spine + multiple feature-specific spines.**
   - This is expected (main spine + per-feature ADRs), but assessment should bind each epic to the right spine.

### Missing Documents

- None of the four core document types (PRD, Architecture, Epics, UX) are missing at the whole-document level.

## Required Actions

- Confirm canonical UX folder: `ux-designs/ux-Nowing-2026-08-15/`.
- Confirm which feature-specific architecture spines to include for epics being assessed.
- If duplicates must be resolved, rename or remove `ux-designs/archive/ux-Nowing-2026-07-22-superseded/` after confirming it is no longer referenced.


## PRD Analysis

### Functional Requirements (72)

- **FR-1:** User Authentication — Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng. **Consequences:**  `/auth/*` routes trả JWT/cookie.  `/users/me` trả `UserRead` bao gồm `credit_micros_balance`.
- **FR-2:** API Access for External Clients — Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key. **Consequences:**  `PersonalAccessToken` model lưu `token_hash`, `token_prefix`, `label`, `expires_at`, `last_used_at`.  `Workspace.api_access_enabled` điều khiển truy cập API theo workspace.
- **FR-3:** Workspace Lifecycle — Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace. **Consequences:**  Tạo workspace tự động tạo default system roles và membership Owner (`workspaces_routes.py`).  `WorkspaceRole` lưu `name`, `description`, `permissions`, `is_default`, `is_system_role`, `workspace_id`.
- **FR-4:** Workspace Invites & Memberships — Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng. **Consequences:**  `WorkspaceInvite` và `WorkspaceMembership` models.  `WorkspaceMembership.is_owner` phân biệt Owner (gốc của workspace) với role.
- **FR-10:** RBAC với ba system roles — System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại. **Consequences:**  `get_default_roles_config()` chỉ trả Owner/Editor/Viewer (`app/db.py`).  Editor không có `documents:delete`, `chats:delete`, `members:remove`, `members:manage_roles`, `settings:update`,...
- **FR-6:** Built-in Scraper Connectors — Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route. **Consequences:**  `app/capabilities/<platform>/` (executor, definition, schemas).  Mỗi lần gọi tạo một `Run` với `capability`, `origin`, `status`, `error`.
- **FR-7:** External OAuth Connectors — Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth. **Consequences:**  `Connection` model lưu `provider`, `base_url`, `api_key`, `extra`, `enabled`.  Các route `/auth/<provider>/connector/add|callback|reauth`.
- **FR-8:** External MCP Connectors — Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó. **Consequences:**  `app/routes/composio_routes.py`, `/auth/mcp/{service}/connector/add`.  `SearchSourceConnectorType` hỗ trợ `EXA_MCP_CONNECTOR` (Story 2.10) với `server_config` trỏ đến `https://mcp.exa.ai/mcp` và `x-api-key` inject qua header; `is_indexable = false`; agent chỉ discover `web_search_exa` + `web_fetch_exa` ở chế độ `readonly`.
- **FR-43:** VietnamWorks Scraper (Vietnam Job Market) — Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks. **Consequences:**  Capability tự đăng ký trong registry, billing (`BillingUnit.VIETNAMWORKS_JOB`), MCP, REST routes.  Input: `query`, `location` (city name), `page`, `hitsPerPage` (max 100), `salaryMin/Max`, `employmentType`.  Output: typed `JobItem` với `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `salaryCurrency`,...
- **FR-44:** TopCV Scraper (Vietnam Job Market) — Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot. **Consequences:**  BSL 1.1 proprietary fetcher (`app/proprietary/platforms/topcv/`).  Input: `query`, `location`, `page`, `max_items`.  Output: `JobItem` tương thích `vn_jobs.aggregate` (title, company, location, salary, JD, requirements, skills, post date).  Requires anti-bot POC to pass before build (Cloudflare "Just a moment..." challenge observed).  Degrades gracefully if TopCV...
- **FR-45:** ITviec Scraper (Vietnam Job Market) — Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing. **Consequences:**  BSL 1.1 proprietary fetcher (`app/proprietary/platforms/itviec/`).  Input: `query`, `location`, `page`, `max_items`.  Output: `JobItem` tương thích `vn_jobs.aggregate`.  Selectors: `job-card ipt-2`, `h3/a`, `employer-name`, `jd-main`.  Salary is hidden for non-logged-in users (`Sign in to view salary`) → parse from title when possible or mark low-confidence....
- **FR-46:** Vietnam Job Market Aggregator (`vn_jobs.aggregate`) — Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. Nowing không giữ local search corpus. **Consequences:**  Apache-2.0 core service `app/services/jobs_aggregator/` (copy-modify from `bds_aggregator`).  Input: `query`, `location`, `sources` (default `['vietnamworks','topcv','itviec']`), `salaryMin/Max`,...
- **FR-47:** PII Redaction for Job Data — Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`. **Consequences:**  Regex for Vietnamese phone/email; heuristic/NER for person names.  Detected PII is masked or the field is dropped; raw JD is not stored in memory or in chunks sent to `chainlens-research`.  Audit stats logged (counts only, no values). ...
- **FR-48:** Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` — Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector search, and merge history. **Acceptance Criteria:**  ~~Given data from 3 sources about the same entity, when aggregated in Nowing, then they merge into one canonical entity with confidence score.~~ →...
- **FR-49:** News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent. **Acceptance Criteria:**  Given RSS feeds are configured, when polled (every 15 min), then new articles from VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet are fetched.  Given articles are fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable...
- **FR-50:** Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent. **Acceptance Criteria:**  Given CafeF API is connected, when a user queries a stock symbol, then price, OHLCV, and financial statements are fetched.  Given financial data is fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'`...
- **FR-51:** Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent. **Acceptance Criteria:**  Given masothue.com data is integrated, when fetched, then company profiles are normalized to `Chunk[]` and sent to `chainlens-research` via `POST /v1/ingest/scraper`.  Given a user searches by company name or tax code, when the query is submitted, then...
- **FR-52:** E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` — As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent. **Acceptance Criteria:**  Given e-commerce scraper is built, when a user searches by product keyword, then product listings are fetched and normalized to `Chunk[]`.  Given product `Chunk[]` are produced, when the batch is ready, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and...
- **FR-53:** Social Media Integration (Epic 18 — REMOVED, feature covered by E10) — As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content. **Status:** `[DONE — covered by Epic 10 existing scrapers]`. > **⚠️ Epic 18 removed (2026-08-06) — duplicate with existing scrapers.** YouTube, Reddit, Instagram, TikTok scrapers already built in Epic 10 (Connector & Scraper Expansion). FR-53 covered by FR-6 (Built-in Scrapers). **Acceptance Criteria:**  Given YouTube/Reddit APIs...
- **FR-54:** Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) — As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing. **Acceptance Criteria:**  Given Google Custom Search API is configured, when a user searches, then web results are returned and crawlable.  Given Google Places API is configured, when a user searches by location, then business listings are returned. **Status:** `[DEFERRED — covered by ChainLens generic crawl for web search]`. > **⚠️ Epic 19 removed...
- **FR-55:** Global E-commerce (Epic 20 — REMOVED, feature covered by E2) — As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets. **Acceptance Criteria:**  Given Amazon/Walmart data sources are connected, when a user searches, then product listings with price, ratings are returned. **Status:** `[DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon)]`. > **⚠️ Epic 20 removed (2026-08-06) — duplicate with existing scrapers.** Walmart (Story 2.6) and Amazon (Story 2.7) already built as part of...
- **FR-56:** Public Agent-Chat API for Vertical Clients — As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application. **Acceptance Criteria:**  Given a valid PAT and workspace membership, when `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, then a chat thread is created and returned with `thread_id` and `research_thread_id`.  Given a valid PAT, when `POST...
- **FR-57:** Agent Registry — As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents. **Acceptance Criteria:**  Given the migration runs, when complete, then an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`.  Given an `agent_id` is provided in a chat request, when processed,...
- **FR-58:** Scraper Feed to chainlens-research (Ecosystem Integration) — As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine. **Acceptance Criteria:**  Given scraper output (BĐS, jobs, news, finance, company, e-commerce), when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with service-to-service auth.  Given a `Chunk[]` batch, when...
- **FR-59:** Gap-Fill Trigger via chainlens-research — As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus. **Acceptance Criteria:**  Given a chat query with public/vertical scope, when `chainlens-research` search returns low coverage, then `POST /v1/gap-fill` is triggered.  Given a gap-fill request, when `chainlens-research` decides a Nowing scraper is needed, then it calls the...
- **FR-60:** Private Data Provider (NowingPrivateProvider) — As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries. **Acceptance Criteria:**  Given a chat query classified as private scope, when `chainlens-research` calls `POST /v1/private-data/search` on Nowing, then Nowing returns `Chunk[]` filtered by workspace RBAC.  Given a `NowingPrivateProvider` call, when the user does...
- **FR-61:** Cross-Project Service Auth & Cost Allocation — As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed. **Acceptance Criteria:**  Given a `chainlens-research` request to Nowing (`POST /v1/private-data/search`, scraper invocation), when received, then Nowing validates a service Bearer token and maps it to a workspace.  Given a Nowing request to `chainlens-research`, when sent, then...
- **FR-62:** Canonical Chunk Metadata Schema (`source` enum) — As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem. **Acceptance Criteria:**  Given any `Chunk` sent to `chainlens-research`, then `metadata` contains `source`, `sourceId`, `domain`, `fetchedAt`, `contentType` (required) and optional `confidence_score`, `source_count`, `conflict_flags`.  Given a `source` value, when validated, then it...
- **FR-63:** Intent Signal Detection `[PROPOSED]` — As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment. **Acceptance Criteria:**  Given a company in workspace, when signals are monitored, then funding events, job postings, tech stack changes, and executive moves are detected and surfaced.  Given a signal is detected, when displayed, then it includes signal type, confidence score, source URL, and timestamp.  Given multiple signals...
- **FR-64:** Lead Scoring & Prioritization `[PROPOSED]` — As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects. **Acceptance Criteria:**  Given a set of leads, when scored, then each lead receives a composite score based on fit (firmographics, technographics) and intent (signal strength, recency).  Given a lead score, when displayed, then it shows score breakdown (fit vs intent), trend (improving/declining), and comparison to similar converted leads.  Given ICP criteria,...
- **FR-65:** Enriched Contact Data `[PROPOSED]` — As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers. **Acceptance Criteria:**  Given a company, when contact enrichment is requested, then decision-maker names, titles, emails, and phone numbers are returned.  Given contact data, when verified, then email is validated via waterfall (5+ providers) and phone via real-time validation (9+ providers).  Given enrichment results, when displayed, then data source,...
- **FR-66:** Outbound Prospecting Automation `[PROPOSED]` — As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality. **Acceptance Criteria:**  Given a lead list, when outreach is triggered, then personalized messages are generated using lead context + ICP + intent signals.  Given outreach sequences, when configured, then multi-channel sequences (email, LinkedIn, Zalo for VN) are supported.  Given a sequence step, when executed, then the system personalizes content, tracks...
- **FR-67:** CRM Integration & Write-Back `[PROPOSED]` — As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth. **Acceptance Criteria:**  Given a CRM connection (Salesforce, HubSpot, Pipedrive), when lead data changes, then it syncs bidirectionally, phased per AD-40: Phase 1 read-only dedup, Phase 2 write-back, Phase 3 bidirectional sync.  Given a lead score or signal, when detected in Phase 2/3, then it writes to the corresponding CRM record.  Given CRM data, when...
- **FR-68:** Zalo Integration (Vietnam Market) `[PROPOSED]` — As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform. **Acceptance Criteria:**  Given a Zalo OA connection, when configured, then outreach sequences can include Zalo messages.  Given a lead with Zalo contact, when outreach is triggered, then personalized Zalo messages are sent.  Given a Zalo reply, when received, then it's logged in the lead's activity timeline.  Comply with Zalo's...
- **FR-8.1:** Exa MCP Search Connector `[DONE 2026-08-05]` — As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval. **Acceptance Criteria:**  Owner có thể POST `/search-source-connectors` với `connector_type: "EXA_MCP_CONNECTOR"` và optional `exa_api_key`; backend persist connector với `server_config` trỏ `https://mcp.exa.ai/mcp`, `x-api-key` injected as header, `is_indexable = false`. ...
- **FR-9:** Document Upload, Parse & Index — Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng. **Consequences:**  `app/indexing_pipeline/`, `app/etl_pipeline/`, `app/file_storage/`.  `Document` có `title`, `document_type`, `content`, `content_hash`, `unique_identifier_hash`, `embedding`, `blocknote_document`.
- **FR-11:** Folders & Document Management — Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check. **Consequences:**  `Folder`, `DocumentVersion`, `DocumentRevision`, `FolderRevision` hỗ trợ versioning và revert.  watched folders đồng bộ từ desktop.
- **FR-12:** Hybrid Search over Knowledge Base — Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`. **Consequences:**  `app/retriever/`.  Kết quả trả về chunks/documents dùng cho citation.
- **FR-13:** Citation Panel for Knowledge-base Chunks — Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel. **Consequences:**  `nowing_web/components/citation-panel/citation-panel.tsx`.  API `/documents/by-chunk/{chunk_id}` với `chunk_window`.
- **FR-32:** Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` — Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP). **Phạm vi MVP:** trọng tâm **semantic facts**; schema hỗ trợ đủ 4 memory type nhưng MVP dùng semantic. Bảng `memory_relations` đã có; graph traversal phong phú = fast-follow. **Acceptance Criteria:**  ✅ `Memory` có `content`, `type` (mặc định `semantic`),...
- **FR-33:** Research Continuity — Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó. **Acceptance Criteria (MVP):**  `nowing_continue_research(thread_id)` trả về N memory liên quan (đã rank) + danh sách citations trước đó của thread.  "Continue" = nối vào `ResearchThread` hiện có; nếu `thread_id` không tồn tại → lỗi rõ ràng, KHÔNG tạo thread ngầm.  Recall trong continue tuân theo cùng định nghĩa "recall hit" ở FR-32. **Consequences:**  `ResearchThread` liên kết với...
- **FR-34:** Memory Correction — Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history. **Acceptance Criteria (MVP):**  "Correct" = tạo `MemoryVersion` mới, giữ `previous_content` + `corrected_content` + `corrected_by` + timestamp; memory cũ KHÔNG bị xoá cứng.  **Phạm vi propagation (MVP):** chỉ cập nhật chính memory đó; KHÔNG propagate đệ quy qua relation graph (contradiction/relation resolution = post-MVP).  Recall sau correction trả về bản mới nhất theo mặc định....
- **FR-36:** Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` — > **✅ ĐÓNG 2026-07-25.** Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. Story `3-10a-legacy-memory-data-safety-spike` = `done`. Recovery path cũng đã build phòng ngừa (`3-10b` = `done`): guard G1.2 trong `178.upgrade()` (raise nếu legacy data chưa backfill) + command app-level `scripts/backfill_legacy_memory.py` (embeddings không chạy được trong raw migration) + 5...
- **FR-40:** First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` — > **Vấn đề, đo bằng code.** `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). **Không có đường nào extract từ scrape run, deep research, hay document upload.** Cộng với việc workspace mới **không seed gì** (`grep seed|sample|onboarding|welcome|starter|template app/routes/workspaces_routes.py` = **rỗng**; `scripts/` không có seed script), hệ quả là: > > **`nowing_recall` ở session đầu trả rỗng — không phải vì bug, mà vì cấu...
- **FR-5:** AI File Sorting (REMOVED) — Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172. **Gap / Removed:**  `[REMOVED]` FR-5: AI File Sorting đã bị xóa khỏi schema (`172_remove_ai_file_sort.py`). Không còn UI, API, hay logic liên quan. Cần loại bỏ khỏi marketing copy. ### 4.4 Chat & Agents **Description:** Multi-agent chat runtime sử dụng LangGraph/LangChain. Main agent có tool registry, subagents, memory, permission middleware, action...
- **FR-14:** Chat Threads & Messages — Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`. **Consequences:**  `NewChatThread`, `NewChatMessage` models.  `/threads` và `/threads/{id}/messages` endpoints.
- **FR-15:** Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` — Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware. **Consequences:**  `app/agents/chat/multi_agent_chat/`.  `AgentActionLog`, `AgentPermissionRule`, `DocumentRevision`/`FolderRevision` cho audit/revert.  memory retrieval integration trong `main_agent` loop. **Auto-extract (đã có — cần review, KHÔNG phải fast-follow):**  ⚠️ Cột...
- **FR-16:** Real-time Collaborative Chat — Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions. **Consequences:**  `ChatComment`, `ChatCommentMention`, `PublicChatSnapshot`.  Zero publication cho threads/messages/comments/automation runs.
- **FR-17:** Anonymous Chat with Quota — Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn. **Consequences:**  `/anonymous/*` routes.
- **FR-42:** Chat Response Benchmark — Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.  `nowing_evals` gọi `POST /api/v1/new_chat` qua `NewChatClient`, mỗi case một thread mới.  Thu thập mỗi turn: latency, TTFB, prompt/completion/total tokens, `cost_micros`, citation count, finish status, turn/message ids.  Hỗ trợ `chat/regression` (drift gate trên nhiều tag: memory, document, deep-research, multi-tool, creative), `chat/quality` (LLM-as-judge), và nền tảng lấy mẫu query...
- **FR-21:** Report Generation & Export — Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text. **Consequences:**  `Report` model; `/reports` routes; export pipeline.
- **FR-22:** Podcast & Video Presentation — Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes. **Consequences:**  `Podcast`, `VideoPresentation` models; `/podcasts/*` routes.
- **FR-23:** Image Generation — Tạo ảnh từ prompt, model, size, style, quality, response_format. **Consequences:**  `ImageGeneration` model; `/image-generations/*` routes. ### 4.6 Automations **Description:** Tạo workflow kích hoạt theo lịch (cron) hoặc sự kiện (connector/webhook). Mỗi automation có một definition JSON chứa trigger và các action steps. Runtime chạy qua Celery. **Functional Requirements:**
- **FR-18:** Automation Action Types  `[DONE — cải chính 2026-07-25]` — Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`. > **⚠️ Cải chính 2026-07-25 (readiness check C-A).** Bản trước ghi *"direct write-back actions chưa được implement dưới dạng action type riêng"* và *"`__init__.py` chỉ import `agent_task`"* — **SAI**. Verify code: registry thực tế import **6 action type**. **Consequences (verified 2026-07-25):** ...
- **FR-19:** Automation Triggers — Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event). **Consequences:**  `AutomationTrigger`, `AutomationRun` models.  `app/automations/triggers/builtin/schedule/` và `event/`.
- **FR-20:** Automation Runs & Retries — Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy. **Consequences:**  `app/automations/runtime/executor.py`, `retries.py`.  `app/automations/tasks/execute_run.py` chạy qua Celery.
- **FR-35:** Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` — Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu. > **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Bản trước ghi `[GAP]` *"Chưa có `memory_change` trigger và `continue_research` action"* — **SAI**. Ba tài liệu cùng sai (PRD, `epics.md` Story 6.5, `merge-to-prod-checklist.md`); `sprint-status.yaml` (`6-5: done`) là bên **đúng**. **Consequences (verified 2026-07-25 — cả ba mảnh đều tồn tại):**  ✅ Trigger type...
- **FR-25:** Web Client (Next.js) — Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`. **Consequences:**  `nowing_web/app/`, `nowing_web/components/`, `zero/` config.
- **FR-26:** Desktop Client (Electron) — Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher. **Consequences:**  `nowing_desktop/src/main.ts`, preload API.
- **FR-27:** Browser Extension (Plasmo) — Thu thập lịch sử duyệt web và gửi về backend. **Consequences:**  `nowing_browser_extension/popup.tsx`, background scripts.
- **FR-28:** Obsidian Plugin — Đồng bộ vault qua REST API `/obsidian/*`. **Consequences:**  `nowing_obsidian/src/main.ts`, `api-client.ts`.
- **FR-29:** MCP Server — MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`. **Consequences:**  `nowing_mcp/mcp_server/server.py` đăng ký workspaces, scrapers, knowledge_base, **memory**.  Tools: `nowing_list_workspaces`, `nowing_select_workspace`, `nowing_web_crawl`, `nowing_google_search`, `nowing_reddit_scrape`, …, `nowing_search_knowledge_base`, `nowing_get_document`, …, `nowing_remember`, `nowing_recall`,...
- **FR-30:** Token Usage Tracking — Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`. **Consequences:**  `app/services/token_tracking_service.py` dùng LiteLLM custom callback.  `TokenUsage` model (migration 125, 142).
- **FR-31:** Credit Wallet & Purchases — `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit. **Consequences:**  `app/services/wallet_credit.py`, `app/routes/stripe_routes.py`.  `auto_reload_service` tự động nạp khi balance thấp (nếu `AUTO_RELOAD_ENABLED`). **Status:**  `[DONE]` FR-31: Credit wallet + Stripe integration implemented (story `8-2`). The usage/credit dashboard is tracked by NFR-7 / story `8-3` and is also `DONE`.
- **FR-41:** Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` — Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64`) thông qua một trang settings trên web UI, **không cần** sửa file/env và restart backend. **Vấn đề hiện tại (verified 2026-07-25/26):**  `global_llm_configs` chỉ đọc được từ YAML file...
- **FR-69:** Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10) — As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered. **Acceptance Criteria:**  Given a pricing plan, when selected, then outcome-based option is available: pay per qualified meeting booked OR pay per lead enriched.  Given a meeting is booked via Nowing outreach, when confirmed, then the cost is attributed to the workspace.  Given a lead is enriched, when data is delivered, then per-lead pricing is applied. ...
- **FR-24:** Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` — Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool. **Contract (🔒 không được break — verified 2026-07-25):**  Endpoint: `POST {CHAINLENS_API_URL}/api/v1/search`, SSE.  Auth: `Authorization: Bearer <CHAINLENS_API_KEY>` — **service-to-service**. Nowing giữ một key; ChainLens không biết end-user. Định danh/hạn mức end-user do Nowing quản.  Request: `{ query,...
- **FR-37:** Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` — Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán. **Vấn đề hiện tại (verified 2026-07-25):**  `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` → **$0.005 phẳng mỗi call, bất kể mode** (`app/config/__init__.py`, dùng qua `BillingUnit.CHAINLENS_QUERY`).  Nhưng `mode` default = `"quality"` (`schemas.py:38`), mà target cost cũ của ChainLens là quality $0.0105 / deep research $0.0164 (ChainLens PRD §7.1) → Nowing...
- **FR-38:** Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` — Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens. > **⚠️ FR này là yêu cầu MÔ HÌNH KINH DOANH, không chỉ reliability (D5, 2026-07-25).** Vì engine closed-source và Nowing public (§1.1), **mọi self-host instance đều chạy ở trạng thái không có engine**. Thiếu FR-38 thì self-host **không dùng được**, và toàn bộ đường OSS/PLG sụp. Đây là lý do story **`9.1a`** là **điều kiện tiên quyết trước khi public repo** và chạy **trước...
- **FR-39:** Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` — Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không. **Vì sao quan trọng:** đây là tiền đề của differentiator *"memory có nguồn sống, tự re-validate"* — thứ phân biệt Nowing với các memory layer khác sau khi "memory có citation" đã thành table-stakes (xem `briefs/brief-Nowing-2026-07-25/brief.md` §4). Chính báo cáo Mem0 (~18/07/2026) thừa nhận memory staleness + temporal abstraction...
- **FR-93:** Full-Stack Web App Builder & Instant Hosting — Người dùng có thể mô tả một ứng dụng web bằng ngôn ngữ tự nhiên, agent sinh project Next.js/React + Tailwind CSS vào `/workspace/web-app`, và deploy 1-click lên `https://[app-name].apps.nowing.net` với HTTPS qua Traefik/Caddy. **Acceptance Criteria:**  Given một mô tả app bằng tiếng Anh hoặc tiếng Việt, when agent generate code, then một dự án Next.js + Tailwind hoàn chỉnh được ghi vào `/workspace/web-app` và trả về preview URL.  Given người dùng bấm `Publish`, when app vượt qua validation, then nó...
- **FR-94:** Design View Mark Tool & Presentation Studio — Người dùng có thể chỉnh sửa UI đã sinh bằng công cụ khoanh vùng trực quan (Mark Tool) để AST-mutate JSX, và có thể tạo/xuất slide deck PPTX/Marp từ prompt cùng bản ghi cuộc họp có speaker diarization. **Acceptance Criteria:**  Given Mark Tool đang hoạt động trên web preview, when người dùng bấm một phần tử, then công cụ bắt bounding box selector và cập nhật JSX AST tương ứng.  Given một prompt trình bày, when yêu cầu xuất PPTX, then file `.pptx` 16:9 được sinh với speaker notes và biểu đồ. ...

### Non-Functional Requirements (12)

- **NFR-1:** Performance — > **⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5).** NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra **hai đường recall khác nhau**, và chỉ một đường được PRD mô tả: > > | Đường | Nơi chạy | Chặn lượt chat? | PRD cũ mô tả? | Bound cũ | > |---|---|---|---|---| > | **Memory injection** | `MemoryInjectionMiddleware.abefore_agent` | ✅ **CÓ — mọi lượt** | ❌ **KHÔNG** | ❌ không có | > | **Recall tool** |...
- **NFR-2:** Security & Auth — JWT/cookie từ `fastapi-users`; PAT cho external clients.  Permission check trên mọi workspace-scoped endpoint.  Secrets qua `.env`, không hardcode.
- **NFR-3:** Observability — OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter.  Celery task monitoring.
- **NFR-4:** Reliability — Async DB I/O bằng SQLAlchemy async.  Celery + Redis cho background tasks.  Retry policy cho automation runs và scraper calls.
- **NFR-5:** Multi-tenancy Isolation — Mọi workspace-scoped query lọc theo `workspace_id`.  `Workspace.api_access_enabled` kiểm soát truy cập API theo workspace.
- **NFR-MULTI-1:** Tenant Isolation for Vertical Clients — Mọi memory/recall query từ public agent-chat API **bắt buộc** lọc theo `client_id` (hard filter, không phải soft boost).  Một client không bao giờ thấy data của client khác.  `client_id` được set qua PostgreSQL RLS context (`SET LOCAL app.current_client_id`).  Áp dụng cho: Memory, TokenUsage, Run, ResearchThread. **Status:** `[PROPOSED]` — Epic 18 / AD-31. Orthogonal to workspace RLS (`workspace_id`). Hard filter, not boost. Design required before memory migrations.
- **NFR-6:** Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]` — Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor. > **⚠️ Cải chính 2026-07-25 (readiness check U-4).** Bản trước ghi `[GAP]` với lý do *"`editorPanelAtom` không có trường `chunkId` hay highlight state"* — **SAI**. Verify code: `nowing_web/atoms/editor/editor-panel.atom.ts` **có** `chunkId: number | null` (dòng 12, 23, 38, 64, 79, 93), và logic dùng nó nằm ở `components/editor-panel/editor-panel.tsx` +...
- **NFR-7:** Usage & Credit Dashboard `[DONE]` — Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`. **Status:**  `[DONE]` — story `8-3` usage & credit dashboard completed.
- **NFR-8:** Recall Quality (eval-gated) `[DONE — story 3-9]` — Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory.  Dùng harness `nowing_evals` chạy trên tập truy vấn thực để đo **precision@k** và **noise rate** của `nowing_recall`.  Đặt ngưỡng tối thiểu (ví dụ precision@5 ≥ ngưỡng cấu hình; noise ≤ ngưỡng) — **không ship nếu chưa đạt**.  Ngưỡng cụ thể chốt cùng SM-10. **Status:**  `[DONE]` — story `3-9` completed; eval harness and gate logic are in place, and `sprint-status.yaml` confirms `3-9: done` with baseline ratified...
- **NFR-9:** Deep-Research Latency & Availability Budget (hai trạng thái) — Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng cấp khi có số đo. **Bối cảnh (verified 2026-07-25 — đọc kỹ trước khi trích số):**  Lần đo cuối (`nfr6-final-20-8-v2-postfix.md`, 2026-07-18) verdict **FAIL**: Ask avg 57–136s (target ≤8s), Reason 50–160s (≤35s), Research quality 198s (>180s), citation 50–88% (≥95%).  **NHƯNG...
- **NFR-10:** Chat Response Regression Gate — Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.  `nowing_evals` chạy `chat/regression` trên tập query đại diện.  Metrics bắt buộc: p95 e2e latency, p95 TTFB, error rate, finish rate, citation count, cost/turn.  Ngưỡng cụ thể được chốt trong `gate.yaml` và chỉ có thể `baseline_ratified: true` sau 3 lần chạy liên tiếp ổn định.  Dữ liệu benchmark không chứa PII; self-host có thể dùng synthetic dataset.
- **NFR-11:** Scraping Compliance & Anti-Bot Resilience — **1. ToS & Legal (Vietnam job market):**  Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use.  Phải hoàn thành legal counsel opinion về employment service provider classification trước khi pilot bắt đầu.  Giữ vững phân biệt Nowing là **research/memory layer**, không phải job board / ATS / employment intermediary. **2. Anti-bot (TopCV/ITviec):**  TopCV yêu cầu anti-bot POC pass trước merge....

### Other Requirements / Constraints (12)

- **NG-1:** Không bán raw research corpus / data-as-a-product (NG-1 core) — Nowing **không** bán raw web index hay research corpus như một sản phẩm dữ liệu.  **Lý do cấu trúc:** mô hình của Exa *là* owned web index. Nowing/ChainLens là **orchestrator mua từ provider** (Brave, Jina, Exa, Tavily, Perplexity Sonar, SearXNG). Bán lại thứ đang mua, ở giá đã commoditize (~$7/1k), đấu specialist có vốn (Tavily→Nebius $400M, 2/2026) = arbitrage âm biên.  **Evidence:** ChainLens `epic-26-gate-tracking.md` — owned index **DEFERRED, 0/7 gates passing**; Gate 3 & 6...
- **NG-2:** Không đua parity consumer kiểu Perplexity — Nowing **không** định vị là "Perplexity nhưng của tôi", và không lấy "rẻ hơn Perplexity/Exa" làm lý do trả tiền.  **Lý do:** red ocean. Perplexity đã bỏ paywall Comet (FREE); OpenWebUI 136k★ / LibreChat 36k★; Perplexica/Vane là bản sinh đôi kiến trúc của ChainLens. Bán đáy = tự bào mòn + đấu free tier của đối thủ.  **Lý do năng lực:** wedge kiểu này thắng bằng GTM/community, không bằng code. Team dev-strong / GTM-thin (PO xác nhận 2026-07-24) → *"đừng chọn chiến lược cần cơ bắp bạn không...
- **NG-3:** Không xây ChainLens thành sản phẩm độc lập — ChainLens không có end-user account, billing, onboarding, hay kênh phân phối riêng. Mọi thứ đó thuộc Nowing. Đối ứng: ChainLens SCP v4 đã drop Epic 34 (billing), 40-9 (onboarding), 41-1 (social), 40-7 (end-user auth), standalone distribution. #### NG-4 (giữ nguyên từ §2.2): công cụ duyệt web thủ công · SLA/compliance doanh nghiệp · native mobile app
- **NG-5:** Nowing does NOT build a public/vertical canonical index or search corpus — Nowing **không** xây `canonical_entities` table, `pgvector` index, `to_tsvector` corpus, hay unified search API cho BĐS/jobs/news/finance/company data trong chính mình.  **Lý do cấu trúc:** `chainlens-research` là chỗ duy nhất own canonical index cho public web + shared vertical data. Nowing là scraper + product state + private workspace `Memory`. Duplicate indexing = duplicate storage + phân mảnh canonical source + maintenance gấp đôi.  **Ràng buộc kiến trúc:** `AD-27` [RE-SCOPED...
- **OQ-1:** External MCP connector marketplace — Liệu có cung cấp catalog/discovery cho external MCP servers (ngoài OAuth manual hiện tại)?
- **OQ-2:** Agent tool default enable/disable  `[VẪN MỞ — defer có chủ đích]` — Có nên cho phép workspace owner cấu hình default enable/disable của agent tools ở backend thay vì chỉ localStorage ở client? > **⚠️ ĐỪNG đóng OQ-2 vì thấy OQ-4 đã resolved — hai thứ khác nhau** (ghi rõ 2026-07-25 vì chúng đọc gần như giống hệt nhau): > > | | Bề mặt | Lưu ở | Trạng thái | > |---|---|---|---| > | **OQ-4** | **MCP tools** (client ngoài, qua API key) | **DB** — `workspace_mcp_tool_settings(workspace_id, tool_name, enabled)` | ✅ **RESOLVED** — story `2-5` done | > | **OQ-2** |...
- **OQ-3:** Retention, right-to-delete & phơi nhiễm pháp lý (retention KHÔNG chỉ là storage) — Document retention **schema đã có** (migration 176: `document_retention_days`, `auto_archive_enabled`, `document_retention_action`, `documents.archived_at`) — nhưng enforcement job/UI chưa xác nhận đầy đủ. **Quan trọng hơn (từ PRFAQ):** memory *bền* lưu dài hạn dữ liệu scrape (Reddit/YouTube/TikTok/Amazon) tạo **phơi nhiễm pháp lý (ToS/bản quyền/PII)**, KHÔNG chỉ là vấn đề dung lượng. Cần: **retention + right-to-delete cho MEMORY** (chưa có, khác doc retention), tách rõ trách nhiệm...
- **OQ-4:** Per-workspace MCP tool enable/disable toggle  `[RESOLVED 2026-07-25 — ĐÃ BUILD]` — > **⚠️ Cải chính 2026-07-25 (readiness P-6).** Bản cũ ghi *"Chưa có cơ chế cho phép workspace owner bật/tắt từng MCP tool… MCP server hiện expose toàn bộ tools cho mọi workspace"* và gắn `[GAP]`. **Không còn đúng** — verify code: bảng **`workspace_mcp_tool_settings`** (`app/db.py:1945`) với unique constraint **`uq_workspace_mcp_tool`** (`:1950`) + relationship `Workspace.mcp_tool_settings` (`:1919`, `:1965`). Story **`2-5-workspace-mcp-tool-enable-disable-toggle-new-gap` = `done`**, và...
- **OQ-5:** Direct write-back action architecture  `[RESOLVED 2026-07-25 — CODE ĐÃ TRẢ LỜI]` — > **⚠️ Cải chính 2026-07-25 (readiness P-6).** Câu hỏi cũ: *"Direct Notion/Slack/Linear/Jira write-back nên implement như automation action types riêng, hay để `agent_task` gọi agent tools hiện có?"* — **code đã chọn xong**: action type **riêng**. Registry có `write_back_notion`, `write_back_slack`, `write_back_linear`, `write_back_jira` (`app/automations/actions/builtin/`). Story **`6-4-direct-write-back-actions-new-gap` = `done`**. **Câu trả lời: action type riêng**, không đi qua...
- **OQ-6:** Đồng bộ docs & artifacts với vision mới  `[DONE — 2026-08-01]` — README, `docs/`, `docs/project-overview.md` và `.env.example` đã được cập nhật phản ánh "long-term research memory" + **Nowing = sản phẩm**, **hosted deep-research engine** = năng lực cloud, self-host dùng được đầy đủ mà không cần engine (FR-38), license Apache-2.0 core + BSL 1.1 crawler engine.  ✅ **Đã đóng:** `_bmad-output/planning-artifacts/epics.md` **đã tồn tại** (tạo 2026-07-25).  ✅ **Đã đóng:** public docs đã sync — story **9.4** done. **Status:** `[DONE]` OQ-6 — public docs synced;...
- **OQ-7:** Câu hỏi mở từ phía ChainLens (story `42-3`) — ADR `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` để ngỏ ba câu hỏi mà **Nowing phải trả lời** cho ChainLens team: 1. Nowing có cần thêm endpoint riêng (`reason` / `answer` variants) hay chỉ `/api/v1/search` là đủ? 2. Nowing có muốn geo-access (ChainLens story `41-2`, reach nguồn bị region-block) không? 3. Format `costDollars` Nowing muốn parse thế nào — `done.usage.costDollars` trong terminal `done` frame? (Ảnh hưởng trực tiếp FR-37.) 4. ~~Engine có thể emit progress event theo phase không?~~ →...
- **OQ-8:** HR/Recruitment Vertical in Vietnam — 1. ToS của VietnamWorks, TopCV, ITviec có cho phép automated access và commercial use cho research aggregator không? 2. Nowing có bị xếp là "employment service provider" / "môi giới việc làm" theo pháp luật Việt Nam không? Cần legal counsel opinion. 3. TopCV anti-bot POC có pass với budget chấp nhận được không? Nếu fail, có chấp nhận pilot 2 nguồn không? 4. ITviec salary ẩn (`Sign in to view salary`) ảnh hưởng value proposition thế nào? Có nên đăng nhập ITviec để lấy salary không? 5. Người...

### PRD Completeness Assessment

- PRD đã cập nhật nhiều lần (2026-07-25, 2026-08-05, 2026-08-06, 2026-08-08, 2026-08-10).
- FR-95..FR-99 từ `prfaq-Nowing.md` chưa có trong PRD hiện tại (last updated 2026-08-10). Cần bổ sung hoặc tạo AMENDMENT để align.
- FR-1..FR-94 và NFR-1..NFR-11 đã được index và mapping tương đối rõ trong epics.md.
- Các open quality items (OQ) và success metrics (SM) cần được kiểm tra coverage ở step 03.

## Epic Coverage Validation

### Coverage Matrix

| FR Number | PRD Requirement | Epic Coverage | Story | Status |
| --- | --- | --- | --- | --- |
| FR-1 | User Authentication | unknown | unknown | ✅ Covered |
| NFR-1 | Performance | unknown | unknown | ✅ Covered |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients | unknown | unknown | ✅ Covered |
| NG-1 | Không bán raw research corpus / data-as-a-product (NG-1 core) | unknown | unknown | ✅ Covered |
| OQ-1 | External MCP connector marketplace | unknown | unknown | ✅ Covered |
| FR-2 | API Access for External Clients | unknown | unknown | ✅ Covered |
| NFR-2 | Security & Auth | unknown | unknown | ✅ Covered |
| NG-2 | Không đua parity consumer kiểu Perplexity | unknown | unknown | ✅ Covered |
| OQ-2 | Agent tool default enable/disable | unknown | unknown | ✅ Covered |
| FR-3 | Workspace Lifecycle | unknown | unknown | ✅ Covered |
| NFR-3 | Observability | unknown | unknown | ✅ Covered |
| NG-3 | Không xây ChainLens thành sản phẩm độc lập | unknown | unknown | ✅ Covered |
| OQ-3 | Retention, right-to-delete & phơi nhiễm pháp lý (retention KHÔNG chỉ là storage) | unknown | unknown | ✅ Covered |
| FR-4 | Workspace Invites & Memberships | unknown | unknown | ✅ Covered |
| NFR-4 | Reliability | unknown | unknown | ✅ Covered |
| OQ-4 | Per-workspace MCP tool enable/disable toggle | unknown | unknown | ✅ Covered |
| FR-5 | AI File Sorting (REMOVED) | unknown | unknown | ✅ Covered |
| NFR-5 | Multi-tenancy Isolation | unknown | unknown | ✅ Covered |
| NG-5 | Nowing does NOT build a public/vertical canonical index or search corpus | — | — | ❌ MISSING |
| OQ-5 | Direct write-back action architecture | unknown | unknown | ✅ Covered |
| FR-6 | Built-in Scraper Connectors | unknown | unknown | ✅ Covered |
| NFR-6 | Citation Full-Editor Highlight | unknown | unknown | ✅ Covered |
| OQ-6 | Đồng bộ docs & artifacts với vision mới | unknown | unknown | ✅ Covered |
| FR-7 | External OAuth Connectors | unknown | unknown | ✅ Covered |
| NFR-7 | Usage & Credit Dashboard | unknown | unknown | ✅ Covered |
| OQ-7 | Câu hỏi mở từ phía ChainLens (story `42-3`) | unknown | unknown | ✅ Covered |
| FR-8 | External MCP Connectors | unknown | unknown | ✅ Covered |
| FR-8.1 | Exa MCP Search Connector | unknown | unknown | ✅ Covered |
| NFR-8 | Recall Quality (eval-gated) | unknown | unknown | ✅ Covered |
| OQ-8 | HR/Recruitment Vertical in Vietnam | unknown | unknown | ✅ Covered |
| FR-9 | Document Upload, Parse & Index | unknown | unknown | ✅ Covered |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | unknown | unknown | ✅ Covered |
| FR-10 | RBAC với ba system roles | unknown | unknown | ✅ Covered |
| NFR-10 | Chat Response Regression Gate | unknown | unknown | ✅ Covered |
| FR-11 | Folders & Document Management | unknown | unknown | ✅ Covered |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | unknown | unknown | ✅ Covered |
| FR-12 | Hybrid Search over Knowledge Base | unknown | unknown | ✅ Covered |
| FR-13 | Citation Panel for Knowledge-base Chunks | unknown | unknown | ✅ Covered |
| FR-14 | Chat Threads & Messages | unknown | unknown | ✅ Covered |
| FR-15 | Multi-agent Runtime with Tools | unknown | unknown | ✅ Covered |
| FR-16 | Real-time Collaborative Chat | unknown | unknown | ✅ Covered |
| FR-17 | Anonymous Chat with Quota | unknown | unknown | ✅ Covered |
| FR-18 | Automation Action Types | unknown | unknown | ✅ Covered |
| FR-19 | Automation Triggers | unknown | unknown | ✅ Covered |
| FR-20 | Automation Runs & Retries | unknown | unknown | ✅ Covered |
| FR-21 | Report Generation & Export | unknown | unknown | ✅ Covered |
| FR-22 | Podcast & Video Presentation | unknown | unknown | ✅ Covered |
| FR-23 | Image Generation | unknown | unknown | ✅ Covered |
| FR-24 | Deep Open-Web Research via ChainLens Engine | unknown | unknown | ✅ Covered |
| FR-25 | Web Client (Next.js) | unknown | unknown | ✅ Covered |
| FR-26 | Desktop Client (Electron) | unknown | unknown | ✅ Covered |
| FR-27 | Browser Extension (Plasmo) | unknown | unknown | ✅ Covered |
| FR-28 | Obsidian Plugin | unknown | unknown | ✅ Covered |
| FR-29 | MCP Server | unknown | unknown | ✅ Covered |
| FR-30 | Token Usage Tracking | unknown | unknown | ✅ Covered |
| FR-31 | Credit Wallet & Purchases | unknown | unknown | ✅ Covered |
| FR-32 | Long-Term Research Memory | unknown | unknown | ✅ Covered |
| FR-33 | Research Continuity | unknown | unknown | ✅ Covered |
| FR-34 | Memory Correction | unknown | unknown | ✅ Covered |
| FR-35 | Memory-Driven Automations | unknown | unknown | ✅ Covered |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | unknown | unknown | ✅ Covered |
| FR-37 | Deep-Research Cost Metering | unknown | unknown | ✅ Covered |
| FR-38 | Research Degradation & Self-Host Independence | unknown | unknown | ✅ Covered |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | unknown | unknown | ✅ Covered |
| FR-40 | First-Run Value — Research Runs Produce Memory | unknown | unknown | ✅ Covered |
| FR-41 | Admin UI cho Global LLM Model Configuration | unknown | unknown | ✅ Covered |
| FR-42 | Chat Response Benchmark | unknown | unknown | ✅ Covered |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | unknown | unknown | ✅ Covered |
| FR-44 | TopCV Scraper (Vietnam Job Market) | unknown | unknown | ✅ Covered |
| FR-45 | ITviec Scraper (Vietnam Job Market) | unknown | unknown | ✅ Covered |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | unknown | unknown | ✅ Covered |
| FR-47 | PII Redaction for Job Data | unknown | unknown | ✅ Covered |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) | unknown | unknown | ✅ Covered |
| FR-49 | News Aggregation (Epic 14) | unknown | unknown | ✅ Covered |
| FR-50 | Financial Data Integration (Epic 15) | unknown | unknown | ✅ Covered |
| FR-51 | Company Data Integration (Epic 16) | unknown | unknown | ✅ Covered |
| FR-52 | E-commerce Intelligence (Epic 17) | unknown | unknown | ✅ Covered |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | Epic 26 | Story 26.11 | ✅ Covered |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | Epic 26 | Story 26.11 | ✅ Covered |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | Epic 26 | Story 26.11 | ✅ Covered |
| FR-56 | Public Agent-Chat API for Vertical Clients | unknown | unknown | ✅ Covered |
| FR-57 | Agent Registry | unknown | unknown | ✅ Covered |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | unknown | unknown | ✅ Covered |
| FR-59 | Gap-Fill Trigger via chainlens-research | unknown | unknown | ✅ Covered |
| FR-60 | Private Data Provider (NowingPrivateProvider) | unknown | unknown | ✅ Covered |
| FR-61 | Cross-Project Service Auth & Cost Allocation | unknown | unknown | ✅ Covered |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | unknown | unknown | ✅ Covered |
| FR-63 | Intent Signal Detection | unknown | unknown | ✅ Covered |
| FR-64 | Lead Scoring & Prioritization | unknown | unknown | ✅ Covered |
| FR-65 | Enriched Contact Data | unknown | unknown | ✅ Covered |
| FR-66 | Outbound Prospecting Automation | unknown | unknown | ✅ Covered |
| FR-67 | CRM Integration & Write-Back | unknown | unknown | ✅ Covered |
| FR-68 | Zalo Integration (Vietnam Market) | unknown | unknown | ✅ Covered |
| FR-69 | Outcome-Based Pricing Option  (mới 2026-08-10) | unknown | unknown | ✅ Covered |
| FR-93 | Full-Stack Web App Builder & Instant Hosting | unknown | unknown | ✅ Covered |
| FR-94 | Design View Mark Tool & Presentation Studio | unknown | unknown | ✅ Covered |
| FR-95 | From PRFAQ-Nowing 2026-08-21 | Epic 28 / Epic 3 / Epic 8 | Story 28.x / 3.18 / 8.14 | ❌ Covered (in epics, not in PRD) |
| FR-96 | From PRFAQ-Nowing 2026-08-21 | Epic 28 / Epic 3 / Epic 8 | Story 28.x / 3.18 / 8.14 | ❌ Covered (in epics, not in PRD) |
| FR-97 | From PRFAQ-Nowing 2026-08-21 | Epic 28 / Epic 3 / Epic 8 | Story 28.x / 3.18 / 8.14 | ❌ Covered (in epics, not in PRD) |
| FR-98 | From PRFAQ-Nowing 2026-08-21 | Epic 28 / Epic 3 / Epic 8 | Story 28.x / 3.18 / 8.14 | ❌ Covered (in epics, not in PRD) |
| FR-99 | From PRFAQ-Nowing 2026-08-21 | Epic 28 / Epic 3 / Epic 8 | Story 28.x / 3.18 / 8.14 | ❌ Covered (in epics, not in PRD) |

### Coverage Statistics

- Total PRD FRs analyzed: 96
- FRs covered in epics: 95
- FRs missing from epics: 1
- FRs in epics but not in PRD: 5 (FR-95..FR-99 from PRFAQ)
- Coverage percentage (PRD → epics): 99.0%

### Missing FR Coverage

- **NG-5:** Nowing does NOT build a public/vertical canonical index or search corpus

### Notes

- FR-95..FR-99 là yêu cầu từ `prfaq-Nowing.md` chưa có trong PRD hiện tại (updated 2026-08-10).
- PRD có một số FR bị `[REMOVED]` / `[RE-SCOPED]` (FR-48, FR-49..FR-52, FR-53..FR-55). Các FR này vẫn xuất hiện trong epics với tư cách lịch sử hoặc đã chuyển sang chainlens-research.
## UX Alignment Assessment

### UX Document Status

✅ **Found** — UX canonical hiện tại nằm trong `ux-designs/ux-Nowing-2026-08-15/`:
- `DESIGN.md` (7.5 KB) — design tokens, colors, typography, component patterns.
- `EXPERIENCE.md` (10 KB) — sitemap, navigation, flows, state patterns, keyboard shortcuts, accessibility floor.
- `ux-contract-readiness-gaps.md` (4.5 KB) — bổ sung UX contracts cho Agent Registry, Vertical Client, Chat Benchmark, Outcome-Based Pricing, CRM, Bounded Memory Injection.

### Alignment Issues

| PRD / Architecture | UX Support | Trạng thái |
|---|---|---|
| Lead Intelligence mode (FR-63..FR-69) | `EXPERIENCE.md` §4.1 Split 2-Panel Workspace, Mode Switcher `[Leads \| Research \| Scrapers]` | ✅ Aligned |
| Real-time table + Zero-cache (FR-65, NFR-1b) | `EXPERIENCE.md` §4.2 Multi-Table Tabs, shimmer skeleton, live row insertion | ✅ Aligned |
| Fit Score badges (FR-64) | `DESIGN.md` fit-score tokens + `EXPERIENCE.md` §4.3 Lead Detail Flyout | ✅ Aligned |
| Credit transparency (FR-31, FR-69) | `EXPERIENCE.md` §3 microcopy + `ux-contract-readiness-gaps.md` OP-1..OP-3 | ✅ Aligned |
| Agent Registry (FR-57) | `ux-contract-readiness-gaps.md` AR-1..AR-3 | ✅ Covered |
| Vertical Client Tenancy (FR-56, NFR-MULTI-1) | `ux-contract-readiness-gaps.md` VT-1..VT-3 | ✅ Covered |
| Chat Benchmark / Regression (FR-42, NFR-10) | `ux-contract-readiness-gaps.md` BM-1..BM-3 | ✅ Covered |
| CRM Write-Back (FR-67) | `ux-contract-readiness-gaps.md` CRM-1..CRM-3 | ✅ Covered |
| Bounded Memory Injection (NFR-1b) | `ux-contract-readiness-gaps.md` MB-1..MB-3 | ✅ Covered |
| First-run onboarding / memory seeding (FR-40) | `ux-contract-first-run-onboarding.md` | ✅ Covered |
| PRFAQ 2026-08-21 — Memory browser / correction (UX-DR-PRFAQ-1/3) | `epics.md` Story 3.18 / post-MVP Epic 3 | ⚠️ Not yet in canonical UX; post-MVP |
| PRFAQ 2026-08-21 — Self-host onboarding flow (UX-DR-PRFAQ-2) | `epics.md` Story 28.4 | ⚠️ Not yet in canonical UX; new 2026-08-21 |
| PRFAQ 2026-08-21 — Cost control dashboard (UX-DR-PRFAQ-4) | `epics.md` Story 8.14 | ⚠️ Not yet in canonical UX; new 2026-08-21 |

### Warnings

1. **Canonical UX (`ux-Nowing-2026-08-15`) cập nhật đến 2026-08-20**, chưa phản ánh các UX Design Requirements (UX-DR-PRFAQ-1..4) mới thêm từ `prfaq-Nowing.md` (2026-08-21). Cần bổ sung UX contracts cho:
   - Memory browser / research timeline (UX-DR-PRFAQ-1)
   - Self-host onboarding flow (UX-DR-PRFAQ-2)
   - Memory correction / version history (UX-DR-PRFAQ-3)
   - Cost control / auto-extract budget dashboard (UX-DR-PRFAQ-4)

2. **UX `DESIGN.md` chỉ 7.5 KB**, tập trung tokens + component patterns, chưa có mô tả chi tiết cho từng màn hình mới (self-host install, cost dashboard). Đây là expected vì các feature đó ở `[backlog]`.

3. **Lưu trữ `ux-designs/archive/ux-Nowing-2026-07-22-superseded/`** vẫn tồn tại; cần đảm bảo không còn references trong code hoặc artifacts.

### Tổng kết UX

UX canonical hiện tại **đủ cho phạm vi đã chốt** (lead intelligence, chat, memory, benchmark, CRM, pricing, bounded injection). Cần **bổ sung 4 UX contracts cho PRFAQ 2026-08-21** nếu các story 8.14, 28.1–28.4, 3.18 chuyển sang `ready-for-dev`.

## Epic Quality Review

### Tổng quan

- **Total epics:** 25 (2, 3, 4, 6, 7, 8, 9, 10, 11, 20, 12, 14, 15, 16, 17, 13, 18, 21, 22, 23, 24, 25, 26, 27, 28)
- **Total stories:** 149
- **Stories with Given/When/Then AC:** 714 câu chứa `**Given**`
- **Story status distribution:** {'DONE per sprint-status: 2-5': 1, 'ready-for-dev': 28, 'done': 25, 'DONE 2026-08-05': 1, 'DONE per sprint-status: 3-6': 1, 'DONE retention: 3-7; memory right-to-delete/legal → xác nhận khi GA cloud': 1, 'backlog': 13, 'DONE — SHIP-GATE implementation complete; baseline ratification pending': 1, 'DONE 2026-07-25': 1, 'DONE dedupe (đã wire cosine<0.08); tuning ngưỡng optional qua 3.9': 1, 'DONE — sprint 8-5 security + IDOR fix (deferred-work 4.5)': 1, 'DONE — HIGH': 1, 'DONE — đi kèm 3.13': 1, 'done/review': 1, 'DONE per sprint-status: 6-4': 1, 'DONE per sprint-status: 6-5 — cải chính 2026-07-25': 1, 'GAP — P1, gated sau pilot BĐS': 2, 'ready-for-dev P1': 1, 'GAP — P2, gated sau pilot BĐS': 1, 'DONE per sprint-status: 8-3': 1, 'DONE — 59 tests passed; gate before auto-extract goes to prod': 1, 'DONE — flags MEMORY_AUTO_EXTRACT_ENABLED (global) + workspaces.memory_auto_extract_enabled (per-ws) đã có': 1, 'DONE — code-complete qua sprint story 8-4 observability-logging': 1, 'DONE per sprint-status: 8-10': 1, 'DONE per sprint-status: 8-11': 1, 'DONE per sprint-status: 8-12': 1, 'DONE per sprint-status: 8-13': 1, 'DONE — P0, tiền đề trước khi public repo': 1, 'DONE — P0, không chặn public repo': 1, 'DONE — P0, parser + fallback in place; waits ChainLens 34.1 full-pipeline cost, target 2026-08-19': 1, 'DONE per sprint-status: 9-3': 1, 'DONE — P1, README/docs/.env.example synced': 1, 'POST-MVP — CHƯA PHÊ DUYỆT, đăng ký để không bị mất': 1, 'DONE per sprint-status: 9-6': 1, 'DONE per sprint-status: 10-1': 1, 'DONE per sprint-status: 10-4': 1, 'P1': 12, 'PREREQUISITE — approved by legal counsel 2026-08-08': 1, 'ready-for-dev P0': 9, 'P0 — must ship before 12.9': 1, 'DROPPED 2026-08-08': 2, 'P0': 8, 'P1, MERGED INTO Story 6.11': 4, 'P2, MERGED INTO Story 6.12': 2, 'P1, MERGED INTO Story 6.12': 1, 'P2': 1, 'P2, MERGED INTO Story 6.11': 1, 'DONE': 19}

### Quality Findings

#### 🔴 Critical Violations

- Không phát hiện epic thuần kỹ thuật ("Setup Database", "Create Models") không có user value.
- Không phát hiện forward dependency rõ ràng trong story titles.

#### 🟠 Major Issues

- **Epic 28 là cross-cutting epic** chạm nhiều tầng (memory, export, encryption, docs, legal). Đây là hợp lệ vì user value rõ ràng ("self-host trust"), nhưng architect cần AD-28 để giảm churn.
- **Story 8.14 nằm trong Epic 8** nhưng gắn UX-DR-PRFAQ-4 từ PRFAQ — đã được xử lý đúng trong elicitation step trước.
- **Story 21.20 vừa chuyển sang `[done]`** trong `epics.md` nhưng title vẫn là `[ready-for-dev]`? Đã cập nhật.

#### 🟡 Minor Concerns

- **Epic numbering nhảy cóc:** Epic 13 `[REMOVED]`, Epic 19/20 lại xuất hiện với tên gọi khác (FR-58..FR-62 thuộc Epic 20). Đây là lịch sử, không ảnh hưởng traceability.
- **Nhiều story có tiêu đề tiếng Việt + tiếng Anh lẫn lộn**, cần chuẩn hóa nếu dùng cho i18n keys.
- **Status tags trong title không nhất quán:** `[DONE]`, `[done]`, `[ready-for-dev]`, `[backlog]`, `[DROPPED]`, `[GAP]`. Không phải lỗi nhưng gây khó khăn parse tự động.

### Dependency Analysis

- Các story trong Epic 28 (28.1–28.4) độc lập trong nội bộ epic, có thể chạy song song nếu có nhiều dev.
- Epic 28 phụ thuộc Epic 1 (auth/RBAC), Epic 3 (memory schema), Epic 8 (billing/cost), Epic 9 (self-host research path). Đây là dependencies downward, không vi phạm quy tắc.
- Story 3.18 phụ thuộc `nowing_evals` harness đã có (Story 3.9 done) — không phải forward dependency.
- Story 8.14 dựa trên `TokenUsage`/`credit_wallet` đã có — không phải forward dependency.

### Best Practices Compliance Checklist

| Tiêu chí | Kết quả | Ghi chú |
|---|---|---|
| Epics deliver user value | ✅ | Các epic đều có user-centric title và goal |
| Epic independence | ✅ | Epic N không yêu cầu Epic N+1 |
| Stories appropriately sized | ✅ | Mỗi story có 1 user capability rõ ràng |
| No forward dependencies | ✅ | Không phát hiện forward dependency trong story titles |
| Database/entity created when needed | ✅ | Mỗi story tạo/chỉnh sửa schema riêng |
| Clear acceptance criteria | ✅ | Đa số story dùng Given/When/Then |
| Traceability to FRs | ✅ | Mỗi story tham chiếu FR/NFR/AR |

### Khuyến nghị

1. Hoàn thiện AD-28 (Encryption-at-Rest Strategy) trước khi 28.2 chuyển `ready-for-dev`.
2. Tạo UX contracts cho 4 UX-DR-PRFAQ mới trước implementation.
3. Chuẩn hóa status tags trong `epics.md` để sprint-planning parse dễ hơn.
4. Xem xét lại Epic 21 status (`in-progress` dù tất cả story done) trong `sprint-status.yaml`.

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK** cho phạm vi mới từ `prfaq-Nowing.md` (Epic 28, Story 3.18, Story 8.14).

**READY** cho phạm vi lead intelligence hiện tại (Epic 21) và các epic đã `done`/`in-progress` trước 2026-08-21.

### Critical Issues Requiring Immediate Action

1. **PRD chưa cập nhật FR-95..FR-99** — Các yêu cầu mới từ PRFAQ chỉ tồn tại trong `epics.md`, chưa có trong `prd.md` (last updated 2026-08-10). Cần tạo AMENDMENT hoặc cập nhật PRD trước khi implementation.
2. **UX canonical chưa cover UX-DR-PRFAQ-1..4** — `ux-Nowing-2026-08-15/DESIGN.md` và `EXPERIENCE.md` chưa có contracts cho memory browser, self-host onboarding, memory correction, cost control dashboard.
3. **Architecture chưa có AD-28 đầy đủ** — Epic 28 ghi `AD-28` nhưng chưa có file architecture decision record riêng cho encryption-at-rest strategy.

### Recommended Next Steps

1. Tạo `AMENDMENT-PRFAQ-2026-08-21.md` trong `prds/prd-Nowing-2026-07-22/` để thêm FR-95..FR-99, NFR signals, UX-DRs.
2. Tạo 4 UX contracts mới trong `ux-designs/ux-Nowing-2026-08-15/` hoặc cập nhật `ux-contract-readiness-gaps.md`.
3. Viết `AD-28` vào `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` hoặc file `AD-28-memory-encryption-at-rest.md` riêng.
4. Chuẩn hóa status tags trong `epics.md` (lowercase/uppercase) và `sprint-status.yaml`.
5. Sau khi trên xong, chạy lại `bmad-check-implementation-readiness` hoặc `bmad-validate-prd` cho Epic 28.

### Final Note

Assessment này phát hiện **3 vấn đề chính** (PRD gap, UX gap, AD-28 missing) và **một số minor concerns** (status tags, epic-21 status drift). Phạm vi lead intelligence hiện tại **đủ sẵn sàng** để tiếp tục. Phạm vi PRFAQ mới cần hoàn thiện 3 artifacts trên trước khi chuyển sang implementation.

**Assessor:** BMAD Implementation Readiness Agent  
**Date:** 2026-08-21  
**Report:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-21.md`


## Post-Assessment Actions Completed (2026-08-21)

The following artifacts were created/updated to resolve the three critical gaps identified above:

1. **PRD Amendment created:**
   - `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-PRFAQ-2026-08-21.md`
   - Adds FR-95..FR-99, AR-11..AR-15, expanded NFR-2/NFR-3, RS-11..RS-13, and UX-DR-PRFAQ-1..4.

2. **UX contracts updated:**
   - `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-readiness-gaps.md`
   - Added sections 7.1–7.4 for Memory Browser, Self-Host Onboarding, Memory Correction, and Cost Control Dashboard.

3. **Architecture Decision Record created:**
   - `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-1-encryption-at-rest.md`
   - Resolves the AD-28 ID conflict (existing AD-28 was the unified matching-engine trigger) by using `AD-28.1`.
   - `epics.md` was updated to reference `AD-28.1` for encryption (lines 108, 129, 3925, 3973, 4028).

### Updated Readiness Verdict

- **Epic 28 (28.1–28.4), Story 8.14, Story 3.18** now have PRD, UX, and Architecture coverage.
- **Remaining work before implementation:**
  - Engineering review of `AD-28.1` (key envelope, KMS selection, migration plan).
  - Legal review for `FR-97` / `AR-13` (source risk tiers, retention policy).
  - UX visual specs for the 4 new UX-DR-PRFAQ contracts (wireframes optional for MVP).
  - Update `sprint-status.yaml` if any new stories change status.


## Post-Review Actions Completed (2026-08-21)

Sau review phạm vi Epic 28 / 8.14 / 3.18, các ADR và artifacts sau đã được tạo/cập nhật:

### Architecture Decision Records

| ADR | File | Mô tả |
|---|---|---|
| AD-28.1 | `architecture/architecture-Nowing-2026-07-22/AD-28-1-encryption-at-rest.md` | Encryption-at-rest (đã có) |
| AD-28.2 | `architecture/architecture-Nowing-2026-07-22/AD-28-2-data-export-okf-bundle.md` | Data export / OKF bundle |
| AD-28.3 | `architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md` | Retention / right-to-delete |
| AD-28.4 | `architecture/architecture-Nowing-2026-07-22/AD-28-4-self-host-install-onboarding.md` | Self-host install / onboarding |
| AD-46 | `architecture/architecture-Nowing-2026-07-22/AD-46-recall-precision-noise-threshold.md` | Recall precision / noise threshold |

### Legal & Eval Artifacts

| File | Trạng thái |
|---|---|
| `_bmad-output/planning-artifacts/legal/tos-review-2026-08-21.md` | ✅ APPROVED |
| `_bmad-output/planning-artifacts/memory-recall-thresholds-2026-08-21.md` | PROPOSED, chờ baseline measurement |

### epics.md updates

- Epic 28 architecture decisions liệt kê AD-28.1..AD-28.4 + AD-46.
- Story 28.1/28.3/28.4 metadata cập nhật AD tương ứng.
- Story 28.3 ghi chú legal review approved.
- Story 3.18 cập nhật `AD-46` + threshold artifact.

### Verdict cập nhật

| Phạm vi | Readiness | Blockers còn lại |
|---|---|---|
| **Epic 28** | `ready-for-dev` cho 28.1, 28.3, 28.4; 28.2 cần engineering review key envelope | KMS selection, migration plan, embedding v2 benchmark |
| **Story 8.14** | `ready-for-dev` UI | Telemetry "value created" schema |
| **Story 3.18** | `ready-for-dev` eval infra | Baseline measurement, oracle dataset |
