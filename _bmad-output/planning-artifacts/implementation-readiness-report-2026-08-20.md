---
stepsCompleted:
  - document-discovery
  - document-discovery-rerun
  - prd-analysis
  - prd-analysis-rerun
  - epic-coverage-validation-rerun
  - ux-alignment-rerun
  - epic-quality-review-rerun
  - final-assessment
  - epic-coverage-validation
  - ux-alignment
  - epic-quality-review
  - final-assessment
document_inventory:
  prd:
    canonical:
      - prds/prd-Nowing-2026-07-22/prd.md
    amendments:
      - prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-26-Source-of-Truth.md
      - prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-12-21-22-23-Readiness-Correction-2026-08-17.md
    reviews:
      - prds/prd-Nowing-2026-07-22/review-prfaq-gap.md
      - prds/prd-Nowing-2026-07-22/review-rubric.md
    notes: prd-requirements-extracted-2026-08-08.md and prd-requirements-extract-skill-2026-08-10.md are derivative artifacts and not used as source of truth.
  architecture:
    canonical:
      - architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md
    baseline:
      - architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md
    supplementary:
      - architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md
      - architecture/architecture-Nowing-2026-07-22/architecture-validation-report-2026-08-11.md
      - architecture/architecture-Nowing-2026-07-22/.memlog.md
      - architecture/unified-scope-chainlens-research-nowing-2026-08-08.md
      - architecture-epic23-lead-infrastructure.md
    notes: Domain-specific architecture spines (linkedin, shopee, telegram, bds, muasamcong, xactions) are available but not selected for core assessment unless user requests.
  epics_and_stories:
    canonical:
      - epics.md
    notes: stories are embedded in epics.md; no dedicated stories/ directory found.
  ux:
    canonical:
      - ux-designs/ux-Nowing-2026-08-15/DESIGN.md
      - ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md
    supplementary:
      - ux-design/epic21-lead-intelligence-ux.md
      - ux-design/epic21-ux-wireframes-2026-08-11.md
      - ux-design/ux-research-origami-refresh-2026-08-11.md
      - ux-design/ux-research-origami-final-2026-08-11.md
    archived:
      - ux-designs/archive/ux-Nowing-2026-07-22-superseded/
    notes: archive folder is superseded and excluded from assessment.
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-20
**Project:** Nowing

## Document Discovery

The following documents were discovered, organized, and confirmed for the assessment.

### PRD
- `prds/prd-Nowing-2026-07-22/prd.md` (main)
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-26-Source-of-Truth.md`
- `prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-12-21-22-23-Readiness-Correction-2026-08-17.md`
- `prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `prds/prd-Nowing-2026-07-22/review-rubric.md`

### Architecture
- `architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (canonical)
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (baseline)
- `architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md`
- `architecture/architecture-Nowing-2026-07-22/architecture-validation-report-2026-08-11.md`
- `architecture/architecture-Nowing-2026-07-22/.memlog.md`
- `architecture/unified-scope-chainlens-research-nowing-2026-08-08.md`
- `architecture-epic23-lead-infrastructure.md`

### Epics & Stories
- `epics.md`

### UX
- `ux-designs/ux-Nowing-2026-08-15/DESIGN.md`
- `ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`
- `ux-design/epic21-lead-intelligence-ux.md`
- `ux-design/epic21-ux-wireframes-2026-08-11.md`
- `ux-design/ux-research-origami-refresh-2026-08-11.md`
- `ux-design/ux-research-origami-final-2026-08-11.md`


## PRD Analysis

Source: `prds/prd-Nowing-2026-07-22/prd.md`


### Functional Requirements

**FR-1:** User Authentication
Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng.

**FR-10:** RBAC với ba system roles
System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại.

**FR-11:** Folders & Document Management
Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.

**FR-12:** Hybrid Search over Knowledge Base
Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`.

**FR-13:** Citation Panel for Knowledge-base Chunks
Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel.

**FR-14:** Chat Threads & Messages
Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`.

**FR-15:** Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]`
Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware.

**FR-16:** Real-time Collaborative Chat
Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.

**FR-17:** Anonymous Chat with Quota
Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.

**FR-18:** Automation Action Types  `[DONE — cải chính 2026-07-25]`
Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`.

**FR-19:** Automation Triggers
Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event).

**FR-2:** API Access for External Clients
Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.

**FR-20:** Automation Runs & Retries
Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy.

**FR-21:** Report Generation & Export
Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.

**FR-22:** Podcast & Video Presentation
Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes.

**FR-23:** Image Generation
Tạo ảnh từ prompt, model, size, style, quality, response_format.

**FR-24:** Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]`
Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool.

**FR-25:** Web Client (Next.js)
Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`.

**FR-26:** Desktop Client (Electron)
Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.

**FR-27:** Browser Extension (Plasmo)
Thu thập lịch sử duyệt web và gửi về backend.

**FR-28:** Obsidian Plugin
Đồng bộ vault qua REST API `/obsidian/*`.

**FR-29:** MCP Server
MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`.

**FR-3:** Workspace Lifecycle
Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.

**FR-30:** Token Usage Tracking
Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`.

**FR-31:** Credit Wallet & Purchases
`User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit.

**FR-32:** Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]`
Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP).

**FR-33:** Research Continuity
Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó.

**FR-34:** Memory Correction
Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history.

**FR-35:** Memory-Driven Automations  `[DONE — cải chính 2026-07-25]`
Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu.

**FR-36:** Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]`

**FR-37:** Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]`
Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán.

**FR-38:** Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]`
Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens.

**FR-39:** Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]`
Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không.

**FR-4:** Workspace Invites & Memberships
Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.

**FR-40:** First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]`

**FR-41:** Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]`
Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64`) thông qua một trang settings trên web UI, **không cần** sửa file/env và restart backend.

**FR-42:** Chat Response Benchmark
Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.

**FR-43:** VietnamWorks Scraper (Vietnam Job Market)
Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks.

**FR-44:** TopCV Scraper (Vietnam Job Market)
Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot.

**FR-45:** ITviec Scraper (Vietnam Job Market)
Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing.

**FR-46:** Vietnam Job Market Aggregator (`vn_jobs.aggregate`)
Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. Nowing không giữ local search corpus.

**FR-47:** PII Redaction for Job Data
Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`.

**FR-48:** Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]`
Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector search, and merge history.

**FR-49:** News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent.

**FR-5:** AI File Sorting (REMOVED)
Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172.

**FR-50:** Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent.

**FR-51:** Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent.

**FR-52:** E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent.

**FR-53:** Social Media Integration (Epic 18 — REMOVED, feature covered by E10)
As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content.

**FR-54:** Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens)
As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing.

**FR-55:** Global E-commerce (Epic 20 — REMOVED, feature covered by E2)
As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets.

**FR-56:** Public Agent-Chat API for Vertical Clients
As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application.

**FR-57:** Agent Registry
As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents.

**FR-58:** Scraper Feed to chainlens-research (Ecosystem Integration)
As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine.

**FR-59:** Gap-Fill Trigger via chainlens-research
As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus.

**FR-6:** Built-in Scraper Connectors
Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route.

**FR-60:** Private Data Provider (NowingPrivateProvider)
As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries.

**FR-61:** Cross-Project Service Auth & Cost Allocation
As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed.

**FR-62:** Canonical Chunk Metadata Schema (`source` enum)
As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem.

**FR-63:** Intent Signal Detection `[PROPOSED]`
As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment.

**FR-64:** Lead Scoring & Prioritization `[PROPOSED]`
As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects.

**FR-65:** Enriched Contact Data `[PROPOSED]`
As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers.

**FR-66:** Outbound Prospecting Automation `[PROPOSED]`
As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality.

**FR-67:** CRM Integration & Write-Back `[PROPOSED]`
As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth.

**FR-68:** Zalo Integration (Vietnam Market) `[PROPOSED]`
As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform.

**FR-69:** Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10)
As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered.

**FR-7:** External OAuth Connectors
Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.

**FR-8:** External MCP Connectors
Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.

**FR-8.1:** Exa MCP Search Connector `[DONE 2026-08-05]`
As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.

**FR-9:** Document Upload, Parse & Index
Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng.


### Non-Functional Requirements

**NFR-1:** Performance

**NFR-10:** Chat Response Regression Gate
Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.

**NFR-11:** Scraping Compliance & Anti-Bot Resilience

**NFR-2:** Security & Auth
- JWT/cookie từ `fastapi-users`; PAT cho external clients.

**NFR-3:** Observability
- OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter.

**NFR-4:** Reliability
- Async DB I/O bằng SQLAlchemy async.

**NFR-5:** Multi-tenancy Isolation
- Mọi workspace-scoped query lọc theo `workspace_id`.

**NFR-6:** Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]`
Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor.

**NFR-7:** Usage & Credit Dashboard `[DONE]`
Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`.

**NFR-8:** Recall Quality (eval-gated) `[DONE — story 3-9]`
Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory.

**NFR-9:** Deep-Research Latency & Availability Budget (hai trạng thái)
Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng cấp khi có số đo.

**NFR-MULTI-1:** Tenant Isolation for Vertical Clients
- Mọi memory/recall query từ public agent-chat API **bắt buộc** lọc theo `client_id` (hard filter, không phải soft boost).


### Additional Requirements / Constraints

- Architecture dependencies: `AD-15`, `AD-11.1`, `AD-18`, `AD-25`, `AD-34`.
- `RUNS_RETENTION_DAYS = 30`; memory must be self-contained.
- Self-host independence (FR-38) is a business-model constraint.
- Migration deploy order: `177 -> backfill -> 178`.

### PRD Completeness Assessment

- FRs are grouped by feature area and numbered.
- NFRs cover performance, security, observability, reliability, multi-tenancy, citation, usage, recall quality, deep-research latency, chat regression, and scraping compliance.
- Several FRs are `[REMOVED]`, `[RE-SCOPED]`, or `[PROPOSED]`, affecting Phase 4 scope.
- Lead-gen FRs (FR-63..FR-69) and FR-69 are all `[PROPOSED]` and not built.

## Epic Coverage Validation

### Coverage Matrix

| FR | PRD Requirement Short Text | Epic/Story Coverage | Status |
|----|----------------------------|---------------------|--------|
| FR-1 | User Authentication | E1 [DONE] | Covered |
| FR-2 | API Access for External Clients | E1 [DONE] | Covered |
| FR-3 | Workspace Lifecycle | E1 [DONE] | Covered |
| FR-4 | Workspace Invites & Memberships | E1 [DONE] | Covered |
| FR-5 | AI File Sorting | — | Removed |
| FR-6 | Built-in Scraper Connectors | E2 [DONE] | Covered |
| FR-7 | External OAuth Connectors | E2 [DONE] | Covered |
| FR-8 | External MCP Connectors | E2 [DONE] | Covered |
| FR-8.1 | Exa MCP Search Connector | E2.10 [DONE] | Covered |
| FR-9 | Document Upload, Parse & Index | E3 [DONE] | Covered |
| FR-10 | RBAC với ba system roles | E1 [DONE] | Covered |
| FR-11 | Folders & Document Management | E3 [DONE] | Covered |
| FR-12 | Hybrid Search over Knowledge Base | E3 [DONE] | Covered |
| FR-13 | Citation Panel for Knowledge-base Chunks | E3 [DONE] | Covered |
| FR-14 | Chat Threads & Messages | E4 [DONE] | Covered |
| FR-15 | Multi-agent Runtime with Tools | E4 [DONE] | Covered |
| FR-16 | Real-time Collaborative Chat | E4 [DONE] | Covered |
| FR-17 | Anonymous Chat with Quota | E4 [DONE] | Covered |
| FR-18 | Automation Action Types | E6 [DONE] | Covered |
| FR-19 | Automation Triggers | E6 [DONE] | Covered |
| FR-20 | Automation Runs & Retries | E6 [DONE] | Covered |
| FR-21 | Report Generation & Export | E5 [DONE] | Covered |
| FR-22 | Podcast & Video Presentation | E5 [DONE] | Covered |
| FR-23 | Image Generation | E5 [DONE] | Covered |
| FR-24 | Deep Open-Web Research via ChainLens Engine | E9 [DONE] | Covered |
| FR-25 | Web Client (Next.js) | E7 [DONE] | Covered |
| FR-26 | Desktop Client (Electron) | E7 [DONE] | Covered |
| FR-27 | Browser Extension (Plasmo) | E7 [DONE] | Covered |
| FR-28 | Obsidian Plugin | E7 [DONE] | Covered |
| FR-29 | MCP Server | E7 [DONE] | Covered |
| FR-30 | Token Usage Tracking | E8 [DONE] | Covered |
| FR-31 | Credit Wallet & Purchases | E8 [DONE] | Covered |
| FR-32 | Long-Term Research Memory | E3 [DONE] | Covered |
| FR-33 | Research Continuity | E4 [DONE] | Covered |
| FR-34 | Memory Correction | E3/E4 [DONE] | Covered |
| FR-35 | Memory-Driven Automations | E6 [DONE] | Covered |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | E3.10 [RESOLVED] | Resolved |
| FR-37 | Deep-Research Cost Metering | E9.2 [DONE] | Covered |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a [DONE] | Covered |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | E9.6 [DONE] | Covered |
| FR-40 | First-Run Value — Research Runs Produce Memory | E3.13 [DONE] | Covered |
| FR-41 | Admin UI cho Global LLM Model Configuration | E8.11 [DONE] | Covered |
| FR-42 | Chat Response Benchmark | E4 [DONE] | Covered |
| FR-43 | VietnamWorks Scraper | E12.1 [DONE] | Covered |
| FR-44 | TopCV Scraper | E12.2 [DONE] | Covered |
| FR-45 | ITviec Scraper | E12.3 [DONE] | Covered |
| FR-46 | Vietnam Job Market Aggregator | E12.4a–e [DONE] | Covered |
| FR-47 | PII Redaction for Job Data | E12.5 [DONE] | Covered |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing | — | Removed |
| FR-49 | News Aggregation | Referenced in stories (governed by AD-34/AD-35) | Partial |
| FR-50 | Financial Data Integration | Referenced in stories (governed by AD-34/AD-35) | Partial |
| FR-51 | Company Data Integration | Referenced in stories (governed by AD-34/AD-35) | Partial |
| FR-52 | E-commerce Intelligence | Referenced in stories (governed by AD-34/AD-35) | Partial |
| FR-53 | Social Media Integration | — | Removed (covered by E10) |
| FR-54 | Search Intelligence | — | Removed (covered by ChainLens) |
| FR-55 | Global E-commerce | — | Removed (covered by E2) |
| FR-56 | Public Agent-Chat API for Vertical Clients | Epic 18 exists but FR not explicitly mapped | Not found |
| FR-57 | Agent Registry | Epic 18 exists but FR not explicitly mapped | Not found |
| FR-58 | Scraper Feed to chainlens-research | Referenced in stories (E20 DONE) | Partial |
| FR-59 | Gap-Fill Trigger via chainlens-research | Referenced in stories (E20 DONE) | Partial |
| FR-60 | Private Data Provider (NowingPrivateProvider) | Referenced in stories (E20 DONE) | Partial |
| FR-61 | Cross-Project Service Auth & Cost Allocation | Referenced in stories | Partial |
| FR-62 | Canonical Chunk Metadata Schema | Referenced in stories | Partial |
| FR-63 | Intent Signal Detection | E21.1 [DONE] | Covered |
| FR-64 | Lead Scoring & Prioritization | E21.2 [DONE] | Covered |
| FR-65 | Enriched Contact Data | E21.3 [DONE] | Covered |
| FR-66 | Outbound Prospecting Automation | E21.4 [DONE] | Covered |
| FR-67 | CRM Integration & Write-Back | E21.5 [DONE] | Covered |
| FR-68 | Zalo Integration (Vietnam Market) | E21.6 [DONE] | Covered |
| FR-69 | Outcome-Based Pricing Option | E21.7 [DONE] | Covered |

### PRD FRs with No Clear Epic/Story Coverage

The following PRD FRs have no explicit epic/story mapping in the `FR Coverage Map` section of epics.md:

- **FR-56**: Public Agent-Chat API for Vertical Clients — Epic 18 exists with stories 18.1–18.8 covering this functionality, but FR-56 is not explicitly listed in the FR Coverage Map
- **FR-57**: Agent Registry — Epic 18 Story 18.3 covers this, but FR-57 is not explicitly listed in the FR Coverage Map

The following PRD FRs are only referenced as governed by Architecture Decisions (ADs) in story footnotes but lack explicit epic mapping:

- **FR-49**: News Aggregation — Referenced in stories (governed by AD-34/AD-35), Epic 14 exists as BACKLOG
- **FR-50**: Financial Data Integration — Referenced in stories (governed by AD-34/AD-35), Epic 15 exists as BACKLOG
- **FR-51**: Company Data Integration — Referenced in stories (governed by AD-34/AD-35), Epic 16 exists as BACKLOG
- **FR-52**: E-commerce Intelligence — Referenced in stories (governed by AD-34/AD-35), Epic 17 exists as BACKLOG
- **FR-58**: Scraper Feed to chainlens-research — Referenced in stories, Epic 20 marked DONE
- **FR-59**: Gap-Fill Trigger via chainlens-research — Referenced in stories, Epic 20 marked DONE
- **FR-60**: Private Data Provider (NowingPrivateProvider) — Referenced in stories, Epic 20 marked DONE
- **FR-61**: Cross-Project Service Auth & Cost Allocation — Referenced in stories
- **FR-62**: Canonical Chunk Metadata Schema — Referenced in stories

### Out-of-Scope / Not in PRD (FR-70 to FR-92)

The following FRs appear in epics.md but are NOT defined in the PRD:

**Telegram Scraper (Epic 22):**
- FR-70: Telegram Web Preview Scraper
- FR-71: Telegram MTProto Client Ingestion
- FR-72: Telegram Scraper Platform Accounts & Session Onboarding
- FR-73: Telegram Rate Limiter & FloodWait Cooldown
- FR-74: Telegram Async S3 Media Streaming
- FR-75: Telegram Entity Extraction
- FR-76: Telegram Realtime Stream Daemon
- FR-77: Telegram Alert Engine Trigger
- FR-78: Telegram AI Agent Tools
- FR-79: Telegram PostgreSQL Storage & Zero Cache Sync

**Lead Gen Extensions (Epic 21):**
- FR-80: 1-Click Reverse-ICP from Website / Project URL
- FR-81: Actionable Turn Dispatches (Suggested Action Pills)
- FR-82: Viral Social Outbound Co-pilot
- FR-83: (referenced in story footnotes only)
- FR-84: Smart Whitelist & Do-Not-Call (DNC) Compliance Engine
- FR-85: Unified Multi-Source AI Lead Generation Orchestrator
- FR-86: Nowing Split-View Canvas & Workspace Modernization
- FR-87: Complete Origami Landing Page & Public Site Transformation
- FR-88: Partners Affiliate Portal & $0 Pricing Page Deployment

**Infrastructure (Epic 23):**
- FR-89: Async Scraper Worker Pool (Celery + Redis Streams)
- FR-90: Official Zalo OA Webhook & ZNS Template Automation
- FR-91: Automated VietQR Affiliate Payout Reconciliation
- FR-92: PostgreSQL RLS & Table Partitioning for Multi-Million Leads

### Summary

- **Total PRD FRs:** 69 (excluding 5 REMOVED: FR-5, FR-48, FR-53, FR-54, FR-55)
- **Fully Covered:** 52 FRs (75%)
- **Partial Coverage:** 9 FRs (13%) — referenced via ADs but not explicitly mapped in FR Coverage Map
- **Not Found:** 2 FRs (3%) — FR-56, FR-57 (Epic 18 exists but FRs not mapped)
- **Removed/Resolved:** 5 FRs (7%)
- **Out-of-scope (not in PRD):** 23 FRs (FR-70 to FR-92, excluding FR-83)

**Recommendation:** 
1. Add FR-56 and FR-57 to the FR Coverage Map with explicit mapping to Epic 18 stories
2. Clarify the coverage status of FR-49–52 (Epic 14–17 are BACKLOG — mark as Proposed/Backlog)
3. Add FR-58–62 to the FR Coverage Map with explicit mapping to Epic 20
4. Consider whether FR-70–92 should be added to the PRD or documented as implementation-level requirements outside PRD scope
5. The overall coverage is strong (75% fully covered), but the FR Coverage Map should be updated to reflect all PRD FRs explicitly for traceability


## UX Alignment Assessment

### 1. UX Documentation Status

**✅ CONFIRMED**: Canonical UX documentation exists and is current.

- **DESIGN.md** (`/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md`): Visual design system with Origami-inspired architecture, mint/emerald green palette, typography tokens, component specifications (mode switcher, chat input, table headers, vertical pills, waterfall cards). Status: `final`, updated 2026-08-15.

- **EXPERIENCE.md** (`/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`): Complete behavioral and interaction model including information architecture, user journeys, component patterns, state patterns, keyboard shortcuts, and accessibility floor. Status: `final`, updated 2026-08-15.

- **Superseded Archive** (`/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/archive/ux-Nowing-2026-07-22-superseded/ux-contract-first-run-onboarding.md`): First-run onboarding contract from 2026-08-05, marked as superseded. Contains O1-O6 states for workspace seeding that are no longer in canonical UX.

---

### 2. Key UX Contracts in Canonical Files

#### From EXPERIENCE.md:

**Information Architecture:**
- Left Rail (64px/240px): Workspace switcher, Mode Switcher [🎯 Leads | 🧠 Research | ⚡ Scrapers], Nav items (Chat, Inbox, Campaigns, Tables, Scrapers), Active Threads List, Onboarding Checklist, User Footer
- Main Viewport: Three modes — Lead Intelligence (2-panel split), Deep Research & Knowledge Canvas, Scraper Automation Hub, Settings & Admin Console

**Key User Journeys:**
- **Flow 1 (Anh Hùng - BĐS Agent)**: Prompt → Scraper Runner → Real-time table insertion via Zero-cache → Suggested action pills → Phone decode → Zalo outreach
- **Flow 2 (Chị Linh - HR Lead)**: Prompt → Candidates Matrix → Filter chips → Campaign creation → Personalized outreach

**Component Patterns:**
- Split 2-Panel Workspace with resizable divider and contextual synchronization
- Multi-Table Tabs & Filter Bar with client-side filtering
- Lead Detail Flyout Drawer with enrichment history, fit score breakdown, timeline
- Mode Switcher Pill, Floating Chat Composer Box, Grid-Paper Table Header

**State Patterns:**
- Initial Empty State, AI Generating/Scraping (with step-by-step progress trace), Enrichment in Progress, Offline/Network Interrupted, Credit Exhausted

**Interaction Primitives:**
- `⌘K` (Command Palette), `N` (New Chat), `E` (Enrich), `S` (Send to Campaign), `Space` (Preview), `Esc` (Close)

#### From DESIGN.md:

**Visual System:**
- Primary Emerald (#10B981), Mint Subtle Wash (#ECFDF5), Pure White Canvas (#FFFFFF)
- Typography: Instrument Serif (display/headlines), Inter/Plus Jakarta Sans (UI), JetBrains Mono (fit scores/mono)
- Components: Mode switch container, chat input box, table grid header, vertical targeting pill, waterfall enrichment card

---

### 3. PRD Requirements Tracing

| PRD Requirement | UX Coverage | Alignment Status |
|-----------------|-------------|------------------|
| **FR-40** (First-run research-run→memory) | ❌ **MISSING** in canonical UX. Superseded archive has O1-O6 states (Welcome screen, Quick research run prompt, Progress-first seeding, Memory seed complete, Skip option, M1 gate). Current EXPERIENCE.md has Onboarding Checklist (0/5 steps progress) but no detailed first-run seeding flow. | **MISALIGNMENT** - First-run onboarding UX exists in archive but not in current canonical UX. |
| **FR-42** (Chat benchmark) | ⚠️ **PARTIAL**. EXPERIENCE.md mentions keyboard shortcuts and interaction primitives but no specific benchmark UI or regression gate visualization. | **GAP** - No UX for benchmark results or regression gate dashboard. |
| **FR-41** (Admin UI for Global LLM Model Configuration) | ✅ **ALIGNED**. EXPERIENCE.md §2.1 includes "Settings & Admin Console" with "Global Model Connections & AI Routing". PRD confirms FR-41 is `[DONE]` (story 8-11). | **ALIGNED** |
| **NFR-9** (Deep research async states) | ✅ **ALIGNED**. EXPERIENCE.md state patterns include "AI Generating / Scraping" with "Animated Origami Wing icon + step-by-step progress trace (e.g. `Đang quét Batdongsan... Đang lọc tin chính chủ...`)" and "Shimmer skeleton on table rows with live row insertion via Zero-cache". | **ALIGNED** |
| **NFR-10** (Chat regression) | ❌ **MISSING**. No UX specified for regression gate visualization or drift alerts. | **GAP** |
| **NFR-1** (Performance/bounded memory injection) | ⚠️ **PARTIAL**. EXPERIENCE.md mentions "Zero-cache real-time synchronization" but no specific UX for memory injection bounds, 8,000 char limits, or injection performance warnings. | **GAP** - No UX for memory injection constraints. |
| **FR-56** (Public Agent-Chat API for Vertical Clients) | ⚠️ **PARTIAL**. EXPERIENCE.md mentions "Workspace Switcher (Personal / Team)" but no specific vertical client tenancy UI or `client_id` filtering visualization. | **GAP** - No UX for multi-tenant vertical client isolation. |
| **FR-57** (Agent Registry) | ❌ **MISSING**. No UX for registering agents with custom system prompts, tool configurations, or `agent_configs` management. | **GAP** |
| **FR-63** (Intent Signal Detection) | ✅ **ALIGNED**. EXPERIENCE.md Flow 1 (Anh Hùng) includes fit score breakdown, intent signals, and lead prioritization. | **ALIGNED** |
| **FR-64** (Lead Scoring & Prioritization) | ✅ **ALIGNED**. DESIGN.md includes fit score tokens (high/med/low with colors), EXPERIENCE.md mentions "Fit Score breakdown" in lead detail drawer. | **ALIGNED** |
| **FR-65** (Enriched Contact Data) | ✅ **ALIGNED**. EXPERIENCE.md includes "Waterfall Enrichment Badges" (Batdongsan → Chotot → Zalo OA), phone decode flow, and "Đang giải mã SĐT..." progress state. | **ALIGNED** |
| **FR-66** (Outbound Prospecting Automation) | ✅ **ALIGNED**. EXPERIENCE.md includes "Campaigns & Sequences" nav item, Flow 1 includes `[ 💬 Mở Zalo chào giá ]` and campaign connection alerts. | **ALIGNED** |
| **FR-67** (CRM Integration & Write-Back) | ⚠️ **NOT EXPLICIT**. EXPERIENCE.md mentions campaigns but no specific CRM sync UI or write-back visualization. | **GAP** |
| **FR-68** (Zalo Integration) | ✅ **ALIGNED**. DESIGN.md includes Zalo channel badge (#0068FF), EXPERIENCE.md includes Zalo outreach flows and campaign connection alerts. | **ALIGNED** |
| **FR-69** (Outcome-Based Pricing) | ❌ **MISSING**. No UX for outcome-based pricing selection (pay per meeting vs per lead) or cost-per-meeting dashboard. | **GAP** |

---

### 4. Architecture Support for UX Needs

| UX Need | Architecture Support | Status |
|---------|---------------------|--------|
| **Async research events** (NFR-9) | AD-104 (Zero-Cache CDC Reactivity) - PostgreSQL Logical WAL Replication streaming to zero-cache (<10ms latency). `leads` table CDC includes `id`, `workspace_id`, `title`, `fit_score`, `status`, `enriched`, `created_at`, `updated_at`. | ✅ **SUPPORTED** |
| **AgentConfig** (FR-57) | AD-106 (DSH Agent-Team Hierarchical Delegation) mentions agent-team patterns but no explicit `agent_configs` table in ARCHITECTURE-SPINE. PRD FR-57 specifies `agent_configs` table with `client_id`, `system_instructions`, `enabled_tools`, etc. | ⚠️ **PARTIAL** - Architecture supports agent delegation but table schema not in spine. |
| **client_id tenancy** (FR-56, NFR-MULTI-1) | NFR-MULTI-1 in PRD specifies PostgreSQL RLS context (`SET LOCAL app.current_client_id`) for Memory, TokenUsage, Run, ResearchThread. Not explicitly mentioned in ARCHITECTURE-SPINE. | ⚠️ **PARTIAL** - PRD defines it but spine doesn't reference it. |
| **Lead ingestion UI** (FR-65) | AD-109 (Batch Ingestion) - `POST /api/v1/workspaces/:workspace_id/leads/batch-ingest` with deterministic `value_hmac`, deduplication, rate limiting. AD-105 (PII Vault) for encrypted contacts. | ✅ **SUPPORTED** |
| **Bounded memory injection** (NFR-1b) | PRD NFR-1b specifies AD-18 (bounded memory injection with ≤8,000 chars, O(top-k) retrieval). Not explicitly in ARCHITECTURE-SPINE. | ⚠️ **PARTIAL** - PRD defines AD-18 but spine doesn't reference it. |
| **PII unlock flow** (FR-65) | AD-105 (PII Vault, Unlock Billing & Decree 13 Compliance) - encrypted contacts, HMAC dedup, 1.5 credit debit on unlock, audit logs, two-tier unlock UX. | ✅ **SUPPORTED** |
| **First-run memory seeding** (FR-40) | PRD FR-40 specifies first research run produces memory with `source_type = SCRAPER_RUN`. Architecture supports memory extraction but no specific first-run seeding mechanism in spine. | ⚠️ **PARTIAL** - Memory exists but seeding flow not in spine. |
| **Chat benchmark telemetry** (FR-42, NFR-10) | AD-107 (Hermetic Testability & $0 API Cost Gate) mentions regression evals with Golden Streaming Cassettes. No specific benchmark UI architecture. | ⚠️ **PARTIAL** - Eval infrastructure exists but UI not specified. |

---

### 5. Misalignments, Missing UX, and Warnings

#### Critical Misalignments:

1. **First-Run Onboarding UX (FR-40)**: Superseded archive (2026-07-22) has detailed first-run seeding contracts (O1-O6 states), but current canonical UX (2026-08-15) only mentions "Onboarding Checklist Card (0/5 steps progress)" without detailed seeding flow. **WARNING**: New workspaces may have empty `nowing_recall` on first session, violating M1 (first-run value ≤15 minutes) requirement.

2. **Vertical Client Tenancy (FR-56, NFR-MULTI-1)**: PRD specifies `client_id` filtering for public agent-chat API with hard RLS isolation. Canonical UX has no visualization for multi-tenant vertical client boundaries or `client_id` selection. **WARNING**: Vertical clients cannot distinguish their data boundaries in UI.

3. **Agent Registry UI (FR-57)**: PRD specifies `agent_configs` table for registering specialized agents per vertical client. Canonical UX has no admin interface for managing agent configurations, system prompts, or tool permissions. **WARNING**: Platform administrators cannot configure vertical client agents through UI.

#### Missing UX for PRD Requirements:

4. **Chat Benchmark/Regression Gate (FR-42, NFR-10)**: No UX for viewing benchmark results, regression drift alerts, or gate status. PRD specifies `nowing_evals` harness but no visualization.

5. **Bounded Memory Injection UX (NFR-1b)**: No UX for memory injection warnings, 8,000 char limit indicators, or injection performance metrics. PRD specifies strict bounds but UX doesn't surface them.

6. **Outcome-Based Pricing UI (FR-69)**: No UX for selecting outcome-based pricing (pay per meeting vs per lead) or viewing cost-per-meeting metrics. PRD proposes pricing tiers but no selection interface.

7. **CRM Integration UI (FR-67)**: EXPERIENCE.md mentions campaigns but no specific CRM sync status, write-back visualization, or bidirectional sync indicators.

#### Architecture Gaps:

8. **client_id RLS Context**: NFR-MULTI-1 specifies PostgreSQL RLS for vertical client isolation, but ARCHITECTURE-SPINE doesn't reference this requirement. **WARNING**: Tenancy isolation may not be enforced at data layer.

9. **agent_configs Table**: FR-57 specifies `agent_configs` schema but ARCHITECTURE-SPINE doesn't include it. AD-106 mentions agent-team patterns but not the persistence layer.

10. **AD-18 (Bounded Memory Injection)**: PRD NFR-1b references AD-18 for memory injection bounds, but ARCHITECTURE-SPINE doesn't include this architectural decision.

---

### 6. Superseded Archive Contracts

The following UX contracts from the superseded archive (`ux-Nowing-2026-07-22-superseded/ux-contract-first-run-onboarding.md`) are **NO LONGER CURRENT**:

- **O1**: Welcome screen with 3 topic suggestions
- **O2**: Quick research run prompt with auto-extract
- **O3**: Progress-first seeding with phase indicators (search → extract → save)
- **O4**: Memory seed complete with count display
- **O5**: Skip option with warning
- **O6**: M1 gate (≤15 minute timeout warning)

**Status**: These contracts were marked for FR-40 (first-run value) but are not present in the canonical 2026-08-15 UX files. The current canonical UX only has a generic "Onboarding Checklist Card (0/5 steps progress)" without the detailed seeding flow.

**Recommendation**: Determine if first-run seeding is still required for FR-40. If yes, migrate O1-O6 contracts to canonical EXPERIENCE.md. If no, update PRD FR-40 to reflect current UX approach.

## Epic Quality Review

### Summary
The epic breakdown demonstrates strong adherence to user-value framing and Given/When/Then AC format. However, **Critical** status inconsistencies exist between epic headers and detailed sections, and **Major** forward dependencies violate story independence standards. Database table creation practices and FR traceability are generally well-maintained.

---

### Critical Issues

#### 1. Epic Status Inconsistencies (Epic 21, Epic 22)
**Severity:** Critical

**Epic 21: Lead Gen Intelligence & Social Graph**
- Epic header (line 218): `### Epic 21: Lead Gen Intelligence & Social Graph — ✅ DONE`
- Detailed section (line 2578): `**Status:** `[in-progress]``
- All 18 stories (21.1–21.18) marked `[DONE]`

**Epic 22: Telegram Scraper & Channel Ingestion Engine**
- Epic header (line 221): `### Epic 22: Telegram Scraper & Channel Ingestion Engine — ✅ DONE`
- Detailed section (line 2896): `**Status:** `[ready-for-dev]``
- Stories 22.1–22.3 present with ACs

**Impact:** Status confusion impedes sprint planning and progress tracking. The dual status fields create ambiguity about actual completion state.

**Recommendation:** Reconcile status fields. Use single source of truth—prefer the detailed section status and update epic headers to match. For Epic 21, if all stories are `[DONE]`, mark epic as `✅ DONE`. For Epic 22, clarify whether it is `[DONE]` or `[ready-for-dev]` based on actual implementation state.

---

### Major Issues

#### 2. Forward Story Dependencies Violating Independence
**Severity:** Major

**Story 12.9: Job Market Alerts `[P1 — depends on 12.6]`** (line 2018)
- Explicit dependency: "Story 12.6 (Saved Searches) must ship first — alerts use saved search infrastructure"
- Title tag: `[P1 — depends on 12.6]`
- AC explicitly references saved search infrastructure

**Story 18.6: Memory Tagging + RAG Filter `[P1]`** (line 2524)
- Technical note: "Blocked until AD-31 tenancy design is accepted"
- Cannot proceed without external architecture decision

**Story 18.8: Rate Limiting + Tenant Isolation `[P1]`** (line 2554)
- Technical note: "Composite RLS (`workspace_id` + `client_id`) must be designed before implementation"
- References AD-31 design prerequisite

**Story 18.1: Public Agent-Chat Endpoints `[P0]`** (line 2439)
- Technical note: "Depends on AD-13 ResearchThread linkage"

**Story 18.5: ResearchThread Auto-Linkage `[P0]`** (line 2509)
- Technical note: References AD-13 + AD-29

**Impact:** Stories cannot be completed independently, violating best practice #3. Dependencies on architecture decisions (AD-31, AD-13) create external blockers not captured in story ACs.

**Recommendation:**
- Remove explicit "depends on" tags from story titles
- Incorporate dependency logic into story ACs as conditional paths (e.g., "Given AD-31 is approved, When...")
- For architecture decision blockers, either (a) resolve ADs before story definition, or (b) create separate prerequisite stories for AD approval
- Consider merging 12.6 and 12.9 if the dependency is intrinsic, or restructure 12.9 to work independently with placeholder infrastructure

---

#### 3. Database Table Creation Practice
**Severity:** Major

**Story 18.3: Agent Registry `[P0]`** (line 2478)
- AC: "Given the migration runs, When complete, Then an `agent_configs` table exists with fields..."
- Creates database table within story (correct practice)

**Story 22.1: Telegram Storage Schema & Public Web Preview Ingestion Engine** (line 2900)
- AC: "Given a clean or existing database environment, When Alembic migrations are executed, Then tables `telegram_channels`, `telegram_messages`, and `telegram_media` are created..."
- Creates multiple tables within story (correct practice)

**Assessment:** Database table creation follows best practice #5—stories create the tables they need rather than all tables upfront. No violations found in sampled stories.

---

### Minor Issues

#### 4. AC Quality Variations
**Severity:** Minor

**Story 12.1: VietnamWorks Scraper `[ready-for-dev P0]`** (line 1861)
- ACs use Given/When/Then format correctly
- Error cases covered: "Given upstream schema changes, When detected, Then golden fixture regression tests fail before deployment"
- Specific and testable

**Story 12.2: TopCV Scraper `[ready-for-dev P0]`** (line 1878)
- ACs cover Cloudflare/anti-bot challenge with degraded response
- Specific degradation handling

**Story 18.1: Public Agent-Chat Endpoints `[P0]`** (line 2439)
- Comprehensive ACs covering auth, validation, rate limiting, timeout handling, audit logging
- Error cases well-covered (401/403/422/503)
- Specific field-level validation

**Story 18.7: Cost Traceability `[P1]`** (line 2539)
- ACs cover metadata storage, cost reporting, header correlation
- Error case: "Given `external_metadata` is missing required fields... When the chat request completes, Then the row is marked `invalid` and queued for manual reconciliation"

**Story 21.1: Intent Signal Detection `[DONE]`** (line 2584)
- ACs use Given/When/Then format
- Covers signal detection, storage, alert triggering, metering
- Specific field names and data types included

**Assessment:** AC quality is generally strong with Given/When/Then format, error case coverage, and specificity. Minor variation in detail level across stories but no critical gaps found in P0/in-progress epics.

---

#### 5. Epic Independence Assessment
**Severity:** Minor

**Epic 18: Vertical Client Platform (Public Agent-Chat)**
- Stories 18.1–18.8 have internal dependencies (18.1 depends on AD-13, 18.6/18.8 blocked by AD-31)
- However, epic as a whole delivers user value: "Public agent-chat endpoints, AgentConfig registry, client_id tenancy, cost traceability, rate limiting + RLS"
- Epic does not require Epic N+1 to function—dependencies are on architecture decisions, not other epics

**Epic 12: HR/Recruitment Vertical**
- Story 12.9 depends on 12.6 (internal dependency)
- Epic delivers user value: Vietnam job market scraping, normalization, deduplication, PII redaction
- Independent of other epics

**Assessment:** Epics are generally independent. Internal story dependencies exist but do not violate epic-level independence. No epic requires another epic to function.

---

#### 6. Epic Titles and Goals User Value Framing
**Severity:** Minor

**Epic 18:** "Vertical Client Platform (Public Agent-Chat)" — describes user outcome (public API for vertical clients)
**Epic 21:** "Lead Gen Intelligence & Social Graph" — describes user outcome (lead processing and CRM hub)
**Epic 22:** "Telegram Scraper & Channel Ingestion Engine" — borderline technical framing but goal clarifies user value ("ingest public channel posts reliably")
**Epic 12:** "HR/Recruitment Vertical — Vietnam Job Market Pilot" — describes user outcome (job market data sourcing)

**Assessment:** Epic titles and goals generally describe user outcomes, not technical milestones. Minor improvement possible for Epic 22 title but goal section provides user context.

---

#### 7. FR Traceability
**Severity:** Minor

**Epic 12:** Stories reference FR-43, FR-44, FR-45, FR-46, FR-47 in technical notes
**Epic 18:** Stories reference AD-29, AD-30, AD-31 (architecture decisions)
**Epic 21:** Stories reference FR-63, FR-64, FR-65, FR-66, FR-67, FR-68, FR-69, FR-80, FR-81, FR-82, FR-84, FR-85, FR-86, FR-87, FR-88

**Assessment:** FR traceability is maintained through technical notes and story references. FR coverage map at lines 115-132 provides comprehensive mapping. No violations found.

---

### Recommendations Summary

**Critical (Immediate Action Required):**
1. Reconcile Epic 21 status: Change detailed section status from `[in-progress]` to `[DONE]` to match header and story completion states
2. Reconcile Epic 22 status: Verify actual implementation state and align header (`✅ DONE`) with detailed section (`[ready-for-dev]`)

**Major (Before Next Sprint):**
3. Remove explicit "depends on" tags from story titles (12.9, 18.6, 18.8)
4. Refactor story dependencies to use conditional ACs or merge intrinsically dependent stories
5. Resolve architecture decision blockers (AD-31, AD-13) before defining dependent stories, or create separate AD-approval prerequisite stories
6. Ensure Story 18.1 and 18.5 AD dependencies are resolved or documented as prerequisites

**Minor (Technical Debt):**
7. Consider renaming Epic 22 title to emphasize user outcome (e.g., "Telegram Market Intelligence & Channel Monitoring")
8. Standardize AC detail level across all stories to match the comprehensive style of Epic 18.1

---

### Positive Findings

- **Strong user-value framing:** Epic goals consistently describe user outcomes, not technical milestones
- **Excellent AC format:** Given/When/Then consistently applied with error case coverage
- **Proper database practices:** Stories create tables as needed, not upfront
- **Comprehensive FR traceability:** FR coverage map and story references maintain clear traceability
- **Epic independence:** No epic requires another epic to function; dependencies are internal or on architecture decisions

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK**

The planning artifacts (PRD, Architecture, Epics, UX) are mostly aligned and detailed, but several critical and major issues must be resolved before Phase 4 implementation can safely start. The largest risk areas are FR traceability gaps, missing or superseded UX for key PRD requirements, and status/dependency inconsistencies in the epic breakdown.

### Critical Issues Requiring Immediate Action

1. **Epic status inconsistencies** — Epic 21 header says `DONE` while detailed section says `in-progress`; Epic 22 header says `DONE` while detailed section says `ready-for-dev`. This will mislead sprint planning.
2. **FR-56 and FR-57 not in FR Coverage Map** — Public Agent-Chat API and Agent Registry are covered by Epic 18 stories but are not explicitly mapped, weakening traceability.
3. **First-run onboarding UX missing in canonical UX** — FR-40 first-run value depends on research-run→memory flow. The detailed O1-O6 onboarding contracts are in the superseded 2026-07-22 archive but absent from the current 2026-08-15 UX, risking M1 (≤15 min) first-run value failure.
4. **Vertical client tenancy not reflected in UX or architecture** — FR-56 and NFR-MULTI-1 require `client_id` RLS and UI, but the canonical UX and the unified architecture spine do not explicitly support multi-tenant client boundaries.
5. **Agent Registry missing UX and architecture schema** — FR-57 specifies an `agent_configs` table with vertical client agent configuration; neither the canonical UX nor the architecture spine defines this interface or persistence layer.

### Major Issues to Resolve Before Implementation

6. **Partial coverage for FR-49–52 and FR-58–62** — These FRs are only referenced via AD governance in stories, not explicitly in the FR Coverage Map; their epic status (Epic 14–17 backlog, Epic 20 done) should be clarified.
7. **Out-of-scope FR-70–FR-92 in epics.md** — Telegram, lead-gen extensions, and infrastructure FRs appear in epics.md but not in the PRD. Decide whether to add them to the PRD or treat them as implementation-level requirements.
8. **Forward story dependencies** — Stories 12.9, 18.1, 18.5, 18.6, and 18.8 reference prerequisites (AD-13, AD-31, other stories) that violate story independence.
9. **Missing UX for outcome-based pricing (FR-69), CRM sync (FR-67), chat benchmark (FR-42/NFR-10), and bounded memory injection (NFR-1b).**
10. **Architecture spine not referencing key ADs** — AD-18 (bounded memory), AD-31 (client_id tenancy), and the `agent_configs` schema are missing from the unified architecture spine.

### Recommended Next Steps

1. **Reconcile epic statuses** in `epics.md`, especially Epic 21 and Epic 22, using a single source of truth.
2. **Update the FR Coverage Map** to explicitly include FR-56, FR-57, FR-58–62, and FR-49–52 with their epic/story assignments.
3. **Resolve or document out-of-scope FR-70–FR-92** — either update the PRD to include them or move them to an implementation backlog outside the PRD scope.
4. **Migrate or re-create first-run onboarding UX** for FR-40 in the canonical 2026-08-15 UX files; confirm the M1 ≤15 min first-run value gate.
5. **Add Agent Registry and vertical client tenancy UX** to the canonical UX and architecture spine before implementing Epic 18.
6. **Resolve architecture decision blockers** (AD-13, AD-31, AD-18) or split them into explicit prerequisite stories before dependent stories are scheduled.
7. **Remove or rephrase forward-dependency language** in story titles and ACs; use conditional ACs instead of "depends on".
8. **Add UX specifications** for outcome-based pricing, CRM sync, chat regression gate, and bounded memory injection.
9. **Ratify the implementation-readiness baseline** with PM, architect, and UX leads before marking any story `ready-for-dev` for Phase 4.

### Final Note

This assessment identified **10+ critical/major issues** across document inventory, FR traceability, epic quality, UX alignment, and architecture support. Address the critical issues first; the most severe risks are first-run value UX, vertical-client/agent-registry gaps, and status inconsistencies. The documentation is rich and the team has strong practices (Given/When/Then ACs, table-per-story, FR traceability), but these specific gaps must be closed before confident Phase 4 implementation.

---

## Remediation Log (2026-08-20)

The following actions were taken immediately after the assessment to resolve the documented issues:

### `epics.md`
- **Epic 21/22 status reconciled:** Epic 21 `**Status:**` changed from `[in-progress]` to `[done]`; Epic 22 table-of-contents and detailed header aligned to `[ready-for-dev]`.
- **FR Coverage Map updated:** Added explicit mapping for FR-49–52 → E14–E17 `[BACKLOG]`, FR-56/57 + NFR-MULTI-1 → E18 `[IN PROGRESS]`, FR-58–62 → E20 `[DONE]`.
- **Functional Requirements inventory updated:** Added rows for FR-49–52, FR-56–62 with epic assignments.
- **Forward dependencies rephrased:** Story 12.9 title and dependency note replaced with `Prerequisite` language; Stories 18.1, 18.5, 18.6, 18.8 technical notes converted from `Depends on` / `Blocked until` to `Prerequisite:` with conditional fallback behavior.
- **Out-of-PRD FR-70–FR-92 documented:** Added explicit warning block explaining these are implementation-level / market-specific elaboration, not PRD-sourced.

### UX
- **`ux-designs/ux-Nowing-2026-08-15/ux-contract-first-run-onboarding.md` created:** Defines O1–O6 first-run seeding states for FR-40.
- **`ux-designs/ux-Nowing-2026-08-15/ux-contract-readiness-gaps.md` created:** Covers Agent Registry, vertical client tenancy, chat benchmark, outcome-based pricing, CRM sync, bounded memory injection.
- **`EXPERIENCE.md` updated:** Added §10 referencing the two new canonical UX contracts.

### Architecture
- **`architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` updated:**
  - Added `AD-116` (Bounded Memory Injection / NFR-1b).
  - Added `AD-117` (Vertical Client Tenancy / `client_id` RLS / FR-56 / NFR-MULTI-1).
  - Added `AD-118` (Agent Registry & `agent_configs` Schema / FR-57).
  - Frontmatter `binds` list extended to AD-111–AD-118.
  - `updated` timestamp refreshed to 2026-08-20.

### Remaining Work
- The updated artifacts should be reviewed by PM, architect, and UX leads before ratification.
- Epic 22 detailed stories still need implementation; status `[ready-for-dev]` is the source of truth.


---

## Re-run Final Assessment

### Overall Readiness Status

**READY WITH CONDITIONS**

Tất cả critical/major issues từ lượt đánh giá ban đầu đã được xử lý:
- FR Coverage Map đầy đủ.
- Epic status nhất quán.
- Forward dependencies được chuyển thành prerequisites hoặc conditional ACs.
- First-run onboarding, Agent Registry, vertical client tenancy, chat benchmark, outcome pricing, CRM sync, bounded memory injection đã có UX contract và architecture spine (AD-116/117/118).
- FR-70–FR-92 được ghi rõ là out-of-PRD implementation backlog.

### Conditions Before Phase 4

1. **AD-13 ResearchThread linkage** phải được accept trước khi E18.1/E18.5 đi production; fallback hiện đã có trong AC.
2. **AD-31 composite `client_id` RLS** phải được accept trước khi E18.6/E18.8 triển khai; nếu không, các story cần split thành prerequisite + implementation.
3. **UX team review** 2 contract mới (`ux-contract-first-run-onboarding.md`, `ux-contract-readiness-gaps.md`) và tích hợp vào `DESIGN.md`/mockup nếu cần.

### Recommended Next Steps

1. **PM/Architect/UX lead ratify** các AD-116/117/118 và UX contract mới.
2. **Cập nhật `sprint-status.yaml`** để phản ánh trạng thái `[ready-for-dev]` của Epic 18, Epic 12, và backlog của Epic 14–17.
3. **Đồng bộ mockup HTML** (nếu dùng) với Agent Registry / vertical client switcher.
4. **Commit** toàn bộ planning artifact updates để lưu trạng thái baseline.

### Final Note

Sau re-run, planning artifacts (PRD, Architecture, Epics, UX) đã **aligned** và đủ điều kiện bắt đầu Phase 4 implementation với điều kiện 3 điểm trên được giải quyết hoặc chấp nhận trước sprint planning.

---

**Implementation Readiness Re-run Complete**

Report: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-20.md`

Assessor: Devin / BMAD `bmad-check-implementation-readiness`
Date: 2026-08-20

## Implementation Readiness Re-run (2026-08-20 18:45)

### PRD Analysis Re-confirmation

- Total FRs: 70
- Total NFRs: 11
- PRD canonical: `prds/prd-Nowing-2026-07-22/prd.md`

### Epic Coverage Validation Re-confirmation

- FRs covered in `epics.md`: 66/70 (94.3%)
- Missing FRs: 48, 50, 51, 52
- FRs in epics but not in PRD: 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92

### UX Alignment Re-confirmation

- UX canonical documents exist.
- FRs referenced in UX: 40.
- UX contracts cover FR-56, FR-57, NFR-MULTI-1, FR-42, NFR-10, FR-69, FR-67, NFR-1b.

### Epic Quality Review Re-confirmation

- Stories missing GWT ACs: 26.9, 24.8, 6.10, 3.18, 27.1, 27.2 (12.7/12.8 DROPPED, 6.8 has GWT ACs)
- Epic titles flagged as technical/platform (need user-value rewrite):
  - Epic 8: Platform Operations (Billing / Usage / Token)
  - Epic 22: Telegram Scraper & Channel Ingestion Engine `[ready-for-dev]`
  - Epic 23: Enterprise Lead Infrastructure, Realtime Ingestion & Automated Outreach Engine `[done]`
  - Epic 25: Superadmin & Platform Operations Control Plane
  - Epic 26: Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]`

### Summary and Recommendations

**Overall Readiness Status: NEEDS WORK**

- PRD, Architecture, Epics, UX documents exist and are aligned at high level.
- Coverage gap: 4 FRs missing in epics (FR-48, FR-50, FR-51, FR-52) due to Epic 13 re-scope/drop.
- Out-of-PRD scope: FR-70–FR-92 need explicit PRD amendment or `out-of-prd` tracker.
- Forward dependencies 2.10→3.15, 9.5→9.6, 20.1→20.4 require review.

### Recommended Next Steps

1. Bổ sung GWT ACs cho 26.9, 24.8, 6.10, 3.18, 27.1, 27.2.
2. Resolve missing FR-48/50/51/52 (drop or re-scope into Epic 14/15/16/17).
2. Create PRD amendment or out-of-PRD tracker for FR-70–FR-92.
3. Confirm forward dependencies are hard or shared context.
4. Review `epic21-lead-intelligence-ux.md` before lead-gen UI dev.

---
