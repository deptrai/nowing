---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-11
**Project:** Nowing

## Step 1 — Document Discovery

### Canonical documents selected for assessment

| Type | Canonical document | Path |
|---|---|---|
| PRD | PRD: Nowing | `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` |
| Architecture | ARCHITECTURE-SPINE | `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` |
| Epics & Stories | Epics | `_bmad-output/planning-artifacts/epics.md` |
| UX | UX contract folder | `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/` |

### All documents found

#### PRD
- `prds/prd-Nowing-2026-07-22/prd.md` (canonical)
- `prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `prds/prd-Nowing-2026-07-22/review-rubric.md`
- `prds/prd-Nowing-2026-07-22/validation-report.md`
- `prd-requirements-extracted-2026-08-08.md`
- `implementation-readiness/prd-requirements-extract-skill-2026-08-10.md`

#### Architecture
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (canonical)
- `architecture/architecture-Nowing-2026-07-22/architecture-validation-report-2026-08-11.md`
- `architecture/architecture-Nowing-2026-07-22/reviews/review-adversarial.md`
- `architecture/architecture-Nowing-2026-07-22/reviews/review-reality-check.md`
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6.md`
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v7.md`
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v8.md`
- `architecture/epic21-architecture-update.md`
- `architecture/unified-scope-chainlens-research-nowing-2026-08-08.md`
- `epic-11-architecture-review-2026-08-03.md`

#### Epics & Stories
- `epics.md` (canonical)
- `implementation-artifacts/epic21-engineering-handoff-2026-08-11.md`
- `implementation-artifacts/epic21-ux-handoff-2026-08-11.md`
- `implementation-artifacts/epic21-readiness-recheck-2026-08-11.md`
- `implementation-artifacts/epic21-ux-traceability-2026-08-11.md`
- `implementation-artifacts/epic-duplicate-analysis-2026-08-11.md`
- `implementation-readiness/epic-fr-coverage-skill-2026-08-10.md`
- `implementation-readiness/epic-quality-review-skill-2026-08-10.md`
- `legal/tos-legal-epic-12-hr-vertical-2026-08-05.md`
- `legal/tos-review-memo-epic-12-2026-08-08.md`
- `reviews/epic-12-review-2026-08-05.md`

#### UX
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-lead-intelligence-panel.md` (canonical, Epic 21 panel)
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-positive-reply-notifications.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-sidebar-onboarding.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-workspace-mode-switch.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-tables-directory.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-public-agent-chat-api.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-service-auth-cost.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-fit-score-badge.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-usage-dashboard.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-first-run-onboarding.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-private-data-provider.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-sync-offline-indicator.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-admin-global-model-config.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-agent-registry.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-ecosystem-search.md`
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-vn-jobs-copy.md`
- `ux-designs/ux-Nowing-2026-07-22/archive/ux-contract-canonical-entity.md`
- `ux-design/epic21-lead-intelligence-ux.md`
- `ux-design/epic21-ux-wireframes-2026-08-11.md`
- `ux-design/ux-research-origami-final-2026-08-11.md`
- `ux-design/ux-research-origami-refresh-2026-08-11.md`

### Duplicates / issues flagged

1. **PRD requirement extracts** — `prd-requirements-extracted-2026-08-08.md` and `implementation-readiness/prd-requirements-extract-skill-2026-08-10.md` are derivative extracts; canonical PRD is `prds/prd-Nowing-2026-07-22/prd.md`.
2. **Architecture review versions** — `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6/v7/v8.md`; using **v8** as latest.
3. **Output file naming** — default `implementation-readiness-report-2026-08-11.md` already exists, so this report is saved as `implementation-readiness-report-2026-08-11-2.md`.

## PRD Analysis

### Functional Requirements

| ID | Requirement | Status | Notes |
|---|---|---|---|
| FR-1 | User Authentication | — | Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng. |
| FR-2 | API Access for External Clients | — | Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key. |
| FR-3 | Workspace Lifecycle | — | Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace. |
| FR-4 | Workspace Invites & Memberships | — | Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng. |
| FR-5 | AI File Sorting (REMOVED) | — | Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172. |
| FR-6 | Built-in Scraper Connectors | — | Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route. |
| FR-7 | External OAuth Connectors | — | Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth. |
| FR-8 | External MCP Connectors | — | Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó. |
| FR-8.1 | Exa MCP Search Connector `[DONE 2026-08-05]` | DONE 2026-08-05 | As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval. |
| FR-9 | Document Upload, Parse & Index | — | Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng. |
| FR-10 | RBAC với ba system roles | — | System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại. |
| FR-11 | Folders & Document Management | — | Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check. |
| FR-12 | Hybrid Search over Knowledge Base | — | Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`. |
| FR-13 | Citation Panel for Knowledge-base Chunks | — | Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel. |
| FR-14 | Chat Threads & Messages | — | Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`. |
| FR-15 | Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` | BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract | Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware. |
| FR-16 | Real-time Collaborative Chat | — | Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions. |
| FR-17 | Anonymous Chat with Quota | — | Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn. |
| FR-18 | Automation Action Types  `[DONE — cải chính 2026-07-25]` | DONE — cải chính 2026-07-25 | Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`. |
| FR-19 | Automation Triggers | — | Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event). |
| FR-20 | Automation Runs & Retries | — | Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy. |
| FR-21 | Report Generation & Export | — | Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text. |
| FR-22 | Podcast & Video Presentation | — | Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes. |
| FR-23 | Image Generation | — | Tạo ảnh từ prompt, model, size, style, quality, response_format. |
| FR-24 | Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` | DONE — contract + regression guard in place; mode default quality→balanced còn 9.3 | Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool. |
| FR-25 | Web Client (Next.js) | — | Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`. |
| FR-26 | Desktop Client (Electron) | — | Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher. |
| FR-27 | Browser Extension (Plasmo) | — | Thu thập lịch sử duyệt web và gửi về backend. |
| FR-28 | Obsidian Plugin | — | Đồng bộ vault qua REST API `/obsidian/*`. |
| FR-29 | MCP Server | BUILT | MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`. |
| FR-30 | Token Usage Tracking | — | Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`. |
| FR-31 | Credit Wallet & Purchases | DONE | `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit. |
| FR-32 | Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` | DONE — story 3-14; baseline ratified 2026-08-04 | Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP). |
| FR-33 | Research Continuity | BUILT | Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó. |
| FR-34 | Memory Correction | BUILT | Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history. |
| FR-35 | Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` | DONE — cải chính 2026-07-25 | Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu. |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` | RESOLVED 2026-07-25 — KHÔNG mất dữ liệu | > **✅ ĐÓNG 2026-07-25.** Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. Story `3-10a-legacy-memory-data-safety-spike` = `done`. Recovery path cũng đã build phòng ngừa (`3-10b |
| FR-37 | Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` | DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02 | Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán. |
| FR-38 | Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` | DONE — P0, tiền đề trước khi public repo | Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens. |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` | DONE — story 9-6 | Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không. |
| FR-40 | First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` | DONE — story 3-13 | > **Vấn đề, đo bằng code.** `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). **Không có đường nào extract từ scrape run, deep research, hay document upload.** Cộng với việc workspace mới **không seed gì** (`grep seed|sample|onboardi |
| FR-41 | Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` | DONE — story 8-11 | Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64` |
| FR-42 | Chat Response Benchmark | — | Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated. |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks. |
| FR-44 | TopCV Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot. |
| FR-45 | ITviec Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing. |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | PROPOSED | Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. Nowing không giữ local search corpus. |
| FR-47 | PII Redaction for Job Data | PROPOSED | Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`. |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` | REMOVED 2026-08-08 — moved to chainlens-research | Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector searc |
| FR-49 | News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | RE-SCOPED 2026-08-08 — feed to chainlens-research | As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent. |
| FR-50 | Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | RE-SCOPED 2026-08-08 — feed to chainlens-research | As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent. |
| FR-51 | Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | RE-SCOPED 2026-08-08 — feed to chainlens-research | As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent. |
| FR-52 | E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | RE-SCOPED 2026-08-08 — feed to chainlens-research | As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent. |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | DONE — covered by Epic 10 existing scrapers | As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content. |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | DEFERRED — covered by ChainLens generic crawl for web search | As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing. |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon) | As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets. |
| FR-56 | Public Agent-Chat API for Vertical Clients | PROPOSED | As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application. |
| FR-57 | Agent Registry | PROPOSED | As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents. |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | PROPOSED | As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine. |
| FR-59 | Gap-Fill Trigger via chainlens-research | PROPOSED | As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus. |
| FR-60 | Private Data Provider (NowingPrivateProvider) | PROPOSED | As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries. |
| FR-61 | Cross-Project Service Auth & Cost Allocation | PROPOSED | As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed. |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | PROPOSED | As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem. |
| FR-63 | Intent Signal Detection `[PROPOSED]` | PROPOSED | As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment. |
| FR-64 | Lead Scoring & Prioritization `[PROPOSED]` | PROPOSED | As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects. |
| FR-65 | Enriched Contact Data `[PROPOSED]` | PROPOSED | As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers. |
| FR-66 | Outbound Prospecting Automation `[PROPOSED]` | PROPOSED | As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality. |
| FR-67 | CRM Integration & Write-Back `[PROPOSED]` | PROPOSED | As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth. |
| FR-68 | Zalo Integration (Vietnam Market) `[PROPOSED]` | PROPOSED | As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform. |
| FR-69 | Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10) | PROPOSED | As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered. |

**Total FRs:** 70

### Non-Functional Requirements

| ID | Requirement | Status | Notes |
|---|---|---|---|
| NFR-1 | Performance | DONE | > **⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5).** NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra **hai đường recall khác nhau**, và chỉ một đường được PRD mô tả: > > | Đường | Nơi chạy | Chặn lượt chat? | PRD cũ |
| NFR-2 | Security & Auth | — | - JWT/cookie từ `fastapi-users`; PAT cho external clients. - Permission check trên mọi workspace-scoped endpoint. - Secrets qua `.env`, không hardcode. |
| NFR-3 | Observability | — | - OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter. - Celery task monitoring. |
| NFR-4 | Reliability | — | - Async DB I/O bằng SQLAlchemy async. - Celery + Redis cho background tasks. - Retry policy cho automation runs và scraper calls. |
| NFR-5 | Multi-tenancy Isolation | — | - Mọi workspace-scoped query lọc theo `workspace_id`. - `Workspace.api_access_enabled` kiểm soát truy cập API theo workspace. |
| NFR-6 | Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]` | DONE — cải chính 2026-07-25 | Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor. |
| NFR-7 | Usage & Credit Dashboard `[DONE]` | DONE | Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`. |
| NFR-8 | Recall Quality (eval-gated) `[DONE — story 3-9]` | DONE — story 3-9 | Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory. - Dùng harness `nowing_evals` chạy trên tập truy vấn thực để đo **precision@k** và **noise rate** của `nowing_recall`. - Đặt ngưỡng tối thiểu (ví dụ precision@5 ≥ ngưỡng cấu hình; noise ≤ ngưỡng) — **không ship nếu chưa đạt* |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | — | Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng cấp khi có số đo. |
| NFR-10 | Chat Response Regression Gate | — | Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic. |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | PROPOSED | **1. ToS & Legal (Vietnam job market):** - Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use. - Phải hoàn thành legal counsel opinion về employment service provider classification trước khi pilot |

**Total NFRs:** 11

### PRD Completeness Assessment

The canonical PRD contains 70 FRs and 11 NFRs. FR-8.1 is separate from FR-8. FR-48, FR-53, FR-54, FR-55, FR-5 are removed/deferred/re-scoped. Lead-gen FRs (FR-63..FR-69) are `[PROPOSED]` and gated by Epic 21 architecture. FR-32, FR-37, FR-38, FR-39, FR-41 are marked `[DONE]` or `[BUILT]`. FR-56..FR-62 are ecosystem/proposed. NFR-9 State B pending ratification. NFR-11 proposed.

## Epic Coverage Validation

### FR Coverage Matrix

| FR Number | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | User Authentication | Epic Intro; Epic 1 | ✓ Covered |
| FR-2 | API Access for External Clients | Epic Intro; E3 3.12 | ✓ Covered |
| FR-3 | Workspace Lifecycle | Epic Intro; E8 8.12; E8 8.13 | ✓ Covered |
| FR-4 | Workspace Invites & Memberships | Epic Intro | ✓ Covered |
| FR-5 | AI File Sorting (REMOVED) | Epic Intro; E3 3.12 | ✓ Covered |
| FR-6 | Built-in Scraper Connectors | Epic Intro; Epic 2; E2 2.6 (+9) | ✓ Covered |
| FR-7 | External OAuth Connectors | Epic Intro; E8 8.3; E7 7.4 (+1) | ✓ Covered |
| FR-8 | External MCP Connectors | Epic Intro; E2 2.10; E3 3.9 (+2) | ✓ Covered |
| FR-8.1 | Exa MCP Search Connector `[DONE 2026-08-05]` | Epic Intro; E2 2.10 | ✓ Covered |
| FR-9 | Document Upload, Parse & Index | Epic Intro; Epic 3; Epic 9 (+1) | ✓ Covered |
| FR-10 | RBAC với ba system roles | Epic Intro; E8 8.11; Epic 4 (+7) | ✓ Covered |
| FR-11 | Folders & Document Management | Epic Intro; Epic 12; E12 12.0 (+1) | ✓ Covered |
| FR-12 | Hybrid Search over Knowledge Base | Epic Intro | ✓ Covered |
| FR-13 | Citation Panel for Knowledge-base Chunks | Epic Intro; E3 3.15 | ✓ Covered |
| FR-14 | Chat Threads & Messages | Epic Intro; Epic 4; E4 4.7 | ✓ Covered |
| FR-15 | Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` | Epic Intro; E8 8.8 | ✓ Covered |
| FR-16 | Real-time Collaborative Chat | Epic Intro | ✓ Covered |
| FR-17 | Anonymous Chat with Quota | Epic Intro; E8 8.7 | ✓ Covered |
| FR-18 | Automation Action Types  `[DONE — cải chính 2026-07-25]` | Epic Intro; Epic 6; E6 6.4 (+1) | ✓ Covered |
| FR-19 | Automation Triggers | Epic Intro; Epic 6 | ✓ Covered |
| FR-20 | Automation Runs & Retries | Epic Intro; Epic 6 | ✓ Covered |
| FR-21 | Report Generation & Export | Epic Intro; Epic 5; E7 7.7 | ✓ Covered |
| FR-22 | Podcast & Video Presentation | Epic Intro | ✓ Covered |
| FR-23 | Image Generation | Epic Intro | ✓ Covered |
| FR-24 | Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` | Epic Intro; Epic 2; Epic 9 (+3) | ✓ Covered |
| FR-25 | Web Client (Next.js) | Epic Intro; Epic 7; E7 7.4 | ✓ Covered |
| FR-26 | Desktop Client (Electron) | Epic Intro | ✓ Covered |
| FR-27 | Browser Extension (Plasmo) | Epic Intro | ✓ Covered |
| FR-28 | Obsidian Plugin | Epic Intro | ✓ Covered |
| FR-29 | MCP Server | Epic Intro; E7 7.7 | ✓ Covered |
| FR-30 | Token Usage Tracking | Epic Intro; Epic 8; E8 8.12 | ✓ Covered |
| FR-31 | Credit Wallet & Purchases | Epic Intro; Epic 8; E8 8.3 | ✓ Covered |
| FR-32 | Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` | Epic Intro; Epic 3; E3 3.14 (+4) | ✓ Covered |
| FR-33 | Research Continuity | Epic Intro | ✓ Covered |
| FR-34 | Memory Correction | Epic Intro; E9 9.6 | ✓ Covered |
| FR-35 | Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` | Epic Intro; Epic 6; E6 6.5 | ✓ Covered |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` | Epic Intro; E3 3.10 | ✓ Covered |
| FR-37 | Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` | Epic Intro; Epic 9; E9 9.2 (+3) | ✓ Covered |
| FR-38 | Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` | Epic Intro; Epic 9; E9 9.1a (+2) | ✓ Covered |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` | Epic Intro; Epic 9; E3 3.15 (+4) | ✓ Covered |
| FR-40 | First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` | Epic Intro; Epic 3; E3 3.13 | ✓ Covered |
| FR-41 | Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` | Epic Intro; Epic 8; E8 8.11 | ✓ Covered |
| FR-42 | Chat Response Benchmark | Epic Intro; Epic 4; E4 4.8a (+6) | ✓ Covered |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | Epic Intro; Epic 12; E12 12.0 (+1) | ✓ Covered |
| FR-44 | TopCV Scraper (Vietnam Job Market) | Epic Intro; Epic 12; E12 12.2 | ✓ Covered |
| FR-45 | ITviec Scraper (Vietnam Job Market) | Epic Intro; Epic 12; E12 12.3 | ✓ Covered |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | Epic Intro; Epic 12; E12 12.4 (+1) | ✓ Covered |
| FR-47 | PII Redaction for Job Data | Epic Intro; Epic 12; E12 12.0 (+2) | ✓ Covered |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` | Epic 13 | ✓ Covered |
| FR-49 | News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | Epic 14 | ✓ Covered |
| FR-50 | Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | Epic 15 | ✓ Covered |
| FR-51 | Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | Epic 16 | ✓ Covered |
| FR-52 | E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | Epic 17 | ✓ Covered |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | E18 18.8 | ✓ Covered |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | E18 18.8 | ✓ Covered |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | E18 18.8 | ✓ Covered |
| FR-56 | Public Agent-Chat API for Vertical Clients | Epic 18 | ✓ Covered |
| FR-57 | Agent Registry | Epic 18 | ✓ Covered |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | Epic 20; E20 20.2 | ✓ Covered |
| FR-59 | Gap-Fill Trigger via chainlens-research | Epic 20; E20 20.3 | ✓ Covered |
| FR-60 | Private Data Provider (NowingPrivateProvider) | Epic 20; E20 20.4 | ✓ Covered |
| FR-61 | Cross-Project Service Auth & Cost Allocation | Epic 20; E20 20.1 | ✓ Covered |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | Epic 20; E20 20.2 | ✓ Covered |
| FR-63 | Intent Signal Detection `[PROPOSED]` | Epic Intro; Epic 21; E21 21.1 (+1) | ✓ Covered |
| FR-64 | Lead Scoring & Prioritization `[PROPOSED]` | Epic Intro; Epic 21; E21 21.2 | ✓ Covered |
| FR-65 | Enriched Contact Data `[PROPOSED]` | Epic Intro; Epic 21; E21 21.3 | ✓ Covered |
| FR-66 | Outbound Prospecting Automation `[PROPOSED]` | Epic Intro; Epic 21; E21 21.4 (+1) | ✓ Covered |
| FR-67 | CRM Integration & Write-Back `[PROPOSED]` | Epic Intro; Epic 21; E21 21.5 | ✓ Covered |
| FR-68 | Zalo Integration (Vietnam Market) `[PROPOSED]` | Epic Intro; Epic 21; E21 21.6 | ✓ Covered |
| FR-69 | Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10) | Epic Intro; Epic 21; E21 21.7 | ✓ Covered |

### Missing FR Coverage

No missing FRs.

### Coverage Statistics

- **Total PRD FRs:** 70
- **FRs covered in epics:** 70
- **Missing:** 0 (0.0%)
- **Extra in epics not in PRD:** 0

## UX Alignment Assessment

### UX Document Status

UX contracts found in `ux-designs/ux-Nowing-2026-07-22/` (23 files) plus Epic 21 UX design artifacts.

### UX Files by FR/story coverage

| FR / Story | PRD Requirement | UX contracts |
|---|---|---|
| FR-1 | User Authentication | — |
| FR-2 | API Access for External Clients | — |
| FR-3 | Workspace Lifecycle | — |
| FR-4 | Workspace Invites & Memberships | — |
| FR-5 | AI File Sorting (REMOVED) | — |
| FR-6 | Built-in Scraper Connectors | ux-contract-lead-intelligence-panel.md, ux-contract-lead-intelligence-panel.md |
| FR-7 | External OAuth Connectors | ux-contract-usage-dashboard.md, ux-contract-usage-dashboard.md |
| FR-8 | External MCP Connectors | — |
| FR-8.1 | Exa MCP Search Connector `[DONE 2026-08-05]` | — |
| FR-9 | Document Upload, Parse & Index | ux-contract-sync-offline-indicator.md, ux-contract-async-deep-research.md (+2) |
| FR-10 | RBAC với ba system roles | ux-contract-chat-benchmark.md, ux-contract-chat-benchmark.md |
| FR-11 | Folders & Document Management | ux-contract-vn-jobs-copy.md, ux-contract-tables-directory.md |
| FR-12 | Hybrid Search over Knowledge Base | — |
| FR-13 | Citation Panel for Knowledge-base Chunks | — |
| FR-14 | Chat Threads & Messages | ux-contract-positive-reply-notifications.md, ux-contract-sidebar-onboarding.md |
| FR-15 | Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` | ux-contract-sidebar-onboarding.md |
| FR-16 | Real-time Collaborative Chat | — |
| FR-17 | Anonymous Chat with Quota | — |
| FR-18 | Automation Action Types  `[DONE — cải chính 2026-07-25]` | — |
| FR-19 | Automation Triggers | — |
| FR-20 | Automation Runs & Retries | — |
| FR-21 | Report Generation & Export | — |
| FR-22 | Podcast & Video Presentation | — |
| FR-23 | Image Generation | — |
| FR-24 | Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` | — |
| FR-25 | Web Client (Next.js) | — |
| FR-26 | Desktop Client (Electron) | — |
| FR-27 | Browser Extension (Plasmo) | — |
| FR-28 | Obsidian Plugin | — |
| FR-29 | MCP Server | — |
| FR-30 | Token Usage Tracking | — |
| FR-31 | Credit Wallet & Purchases | ux-contract-usage-dashboard.md, ux-contract-usage-dashboard.md |
| FR-32 | Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` | — |
| FR-33 | Research Continuity | — |
| FR-34 | Memory Correction | — |
| FR-35 | Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` | — |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` | — |
| FR-37 | Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` | ux-contract-usage-dashboard.md, ux-contract-usage-dashboard.md (+1) |
| FR-38 | Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` | ux-contract-sync-offline-indicator.md, ux-contract-sync-offline-indicator.md (+5) |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` | — |
| FR-40 | First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` | ux-contract-first-run-onboarding.md, ux-contract-first-run-onboarding.md (+2) |
| FR-41 | Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` | ux-contract-admin-global-model-config.md, ux-contract-admin-global-model-config.md (+1) |
| FR-42 | Chat Response Benchmark | ux-contract-chat-benchmark.md, ux-contract-chat-benchmark.md |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | ux-contract-vn-jobs-copy.md |
| FR-44 | TopCV Scraper (Vietnam Job Market) | — |
| FR-45 | ITviec Scraper (Vietnam Job Market) | — |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | — |
| FR-47 | PII Redaction for Job Data | — |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` | — |
| FR-49 | News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | — |
| FR-50 | Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | — |
| FR-51 | Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | — |
| FR-52 | E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` | — |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | — |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | — |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | — |
| FR-56 | Public Agent-Chat API for Vertical Clients | ux-contract-public-agent-chat-api.md, ux-contract-public-agent-chat-api.md |
| FR-57 | Agent Registry | ux-contract-agent-registry.md, ux-contract-agent-registry.md (+1) |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | ux-contract-ecosystem-search.md, ux-contract-ecosystem-search.md |
| FR-59 | Gap-Fill Trigger via chainlens-research | ux-contract-ecosystem-search.md, ux-contract-ecosystem-search.md |
| FR-60 | Private Data Provider (NowingPrivateProvider) | ux-contract-private-data-provider.md, ux-contract-private-data-provider.md |
| FR-61 | Cross-Project Service Auth & Cost Allocation | ux-contract-service-auth-cost.md, ux-contract-service-auth-cost.md |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | ux-contract-ecosystem-search.md |
| FR-63 | Intent Signal Detection `[PROPOSED]` | ux-contract-lead-intelligence-panel.md, ux-contract-lead-intelligence-panel.md (+2) |
| FR-64 | Lead Scoring & Prioritization `[PROPOSED]` | ux-contract-lead-intelligence-panel.md, ux-contract-fit-score-badge.md (+1) |
| FR-65 | Enriched Contact Data `[PROPOSED]` | ux-contract-lead-intelligence-panel.md, ux-contract-lead-intelligence-panel.md |
| FR-66 | Outbound Prospecting Automation `[PROPOSED]` | ux-contract-epic21-addendum-2026-08-11.md, ux-contract-lead-intelligence-panel.md (+1) |
| FR-67 | CRM Integration & Write-Back `[PROPOSED]` | — |
| FR-68 | Zalo Integration (Vietnam Market) `[PROPOSED]` | ux-research-origami-final-2026-08-11.md |
| FR-69 | Outcome-Based Pricing Option `[PROPOSED]` (mới 2026-08-10) | ux-contract-epic21-addendum-2026-08-11.md, ux-contract-lead-intelligence-panel.md (+5) |

### Alignment Issues

- Many foundational FRs (FR-1..FR-4, FR-6..FR-8, FR-9..FR-13, etc.) do not have dedicated UX contracts; UX is implied through web/desktop/extension UI and is covered by implementation code, not standalone UX docs.
- Epic 21 lead-gen FRs (FR-63..FR-69) are actively supported by dedicated UX contracts: `ux-contract-lead-intelligence-panel.md`, `ux-contract-sidebar-onboarding.md`, `ux-contract-workspace-mode-switch.md`, `ux-contract-tables-directory.md`, `ux-contract-positive-reply-notifications.md`, `ux-contract-fit-score-badge.md`, plus `epic21-lead-intelligence-ux.md` and `epic21-ux-wireframes-2026-08-11.md`.
- FR-21 (Report export), FR-22 (Podcast/Video), FR-23 (Image generation) have no dedicated UX contract found; likely legacy UI already implemented.
- FR-24/FR-37/FR-38 deep-research UX is partially covered by `ux-contract-async-deep-research.md`.
- Architecture decisions AD-15 (ChainLens external engine), AD-11 (Memory first-class), AD-8 (credit wallet), AD-31 (client_id) directly support the UX contracts for lead intelligence, deep-research async, and memory.

### Warnings

- No UX contract found for FR-21/FR-22/FR-23 (deliverables); verify with product/UX team if these surfaces need explicit contracts before Phase 4.
- `ux-contract-async-deep-research.md` is listed as scaffold/empty per NFR-9 note in PRD — needs UX spec before State B sync chat-mode.


# Nowing — Epic Quality Review & Implementation Readiness Assessment

**Artifact reviewed:** `_bmad-output/planning-artifacts/epics.md` (2,654 lines, updated 2026-08-11)  
**Reviewer:** Product Manager — Epic Quality Review  
**Date:** 2026-08-11  
**Scope:** All epics and stories in `epics.md` evaluated against create-epics-and-stories best practices.

---

## 1. Executive Summary

Bản phân rã epic/story của Nowing phản ánh đúng trạng thái brownfield (nhiều phần done) và có sự điều chỉnh liên tục theo sprint. Tuy nhiên, tính **độc lập của epic** bị phá vỡ nghiêm trọng ở các epic dữ liệu dọc Việt Nam (12, 14, 15, 16, 17) khi chúng phụ thuộc vào **Epic 20** và **AD-33 Generic Alert Engine** — những building block chưa hoàn thành hoặc chưa được định nghĩa thành story. Điều này khiến nhiều story P0/P1 bị đánh dấu `ready-for-dev` nhưng thực tế không thể triển khai song song. Ngoài ra, một số story mới (đặc biệt Epic 18) dùng persona hệ thống, AC chưa chuyển hết sang tiếng Anh GWT, và Epic 21 còn ở dạng đề xuất với quá nhiều entity mới chưa có kiến trúc.

**Verdict:** **Conditional / Not Ready** for full implementation of the post-done backlog until the cross-cutting dependencies and Epic-21 governance gates are resolved.

| Severity | Count | Key Story/EPIC IDs |
|----------|-------|--------------------|
| Critical | 3 | Epic 12/14-17 → Epic 20/AD-33; Epic 20 placement; Epic 21 |
| Major | 8 | 12.4, 4.8a-g, 3.9, 18.2/4/6/8, AD-33, mixed-language ACs, document structure, Epic 21 entity model |
| Minor | 5 | vague ACs, tech-debt follow-ups, implementation details in ACs, epic headers, dropped/proposed content |

---

## 2. Assessment Criteria

The review used the following best-practice rules:

1. **Epics deliver user value** — not purely technical milestones.
2. **Epics are independent** — Epic N should not require Epic N+1.
3. **Stories are user-centric & independently completable** — proper `As a / I want / So that` and Given/When/Then ACs.
4. **No forward dependencies** — a story should not depend on a later story/epic.
5. **Database/entity creation happens when first needed** — not all upfront.
6. **Acceptance criteria are testable, specific, and complete** — including error paths and no placeholders.

---

## 3. Critical Findings

### C1. Forward cross-epic dependencies on Epic 20 and AD-33 block P0/P1 vertical stories

- **Epic/Story IDs:** 12.4, 12.6, 12.9, 14.1, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 16.1, 16.2, 16.3, 16.4, 17.1, 17.2, 17.3, 17.4; prerequisites: 20.1–20.4 and AD-33.
- **Lines:** 2081–2087, 2342, 2627–2654.
- **Violation:** Epics 12, 14, 15, 16, and 17 are numbered before Epic 20 but their alert/ingest stories cannot be scheduled until `NowingIngestService` (20.2), `ChainLensServiceAuth` (20.1), and the **AD-33 Generic Alert Engine** are complete.
- **Why it is a problem:** This is a direct breach of “No forward dependencies” and “Epics should be independent.” Marking these stories `[ready-for-dev]` is misleading; engineering will hit blockers immediately and the vertical epics cannot be worked in parallel.
- **Concrete remediation:**
  1. Re-order `epics.md` so **Epic 20** and a new **AD-33 implementation story** appear *before* Epic 12/14–17.
  2. Convert AD-33 from an architecture-only note into a real user story (e.g., in Epic 6 or Epic 20) with its own migration, tests, and acceptance criteria.
  3. Do not mark any consumer story `[ready-for-dev]` until 20.2 and the AD-33 story are in `done` or at least `in-progress` with a stable contract.

### C2. Epic 20 is positioned after the consumer epics that depend on it

- **Epic ID:** Epic 20 (`Nowing Ecosystem Integration — Feed & Recall from chainlens-research`).
- **Lines:** 2330–2475.
- **Violation:** Epic 20 appears *after* Epics 12/14–17 in the document and has a technical title; its user-value sentence is at line 2331 but is buried under a platform-framing title.
- **Why it is a problem:** Readers planning implementation from top to bottom will encounter vertical stories before they see the shared platform prerequisite. It creates a false impression that the vertical epics are self-contained.
- **Concrete remediation:**
  1. Move Epic 20 (and the new AD-33 story) to a position before Epic 12, or renumber the epics to reflect dependency order.
  2. Rename Epic 20 to a user-value title, e.g., *“Chat answers can use fresh web/vertical data without building a public search corpus.”*
  3. Ensure stories 20.1 and 20.3 have user-centric personas (not only “As a platform engineer” / “As a chat user”).

### C3. Epic 21 is PROPOSED but already contains detailed, P0/P1-ish stories and premature UX contracts

- **Epic/Story IDs:** Epic 21, 21.1–21.7, plus `Epic 21 UX Contract Traceability` (lines 2602–2624).
- **Lines:** 2477–2624.
- **Violation:**
  - Line 2490 states *“Epic 21 is `PROPOSED` and cannot be moved to `ready-for-dev` until the governance gates below close.”*
  - Yet the document already contains 7 detailed stories, UX wireframes, and 8 UX patterns mapped to FRs.
  - The stories assume 6+ new tables (`SignalEvent`, `LeadScore`, `EnrichmentRequest`, `VerifiedContact`, `Sequence*`, `BillingEvent`, `OutcomeEvent`, `PricingPlan`, `CrmConnection`) and unaccepted ADs (AD-31, AD-33, AD-37–AD-42).
- **Why it is a problem:** It bloats the implementation artifact with unvalidated scope, risks accidental scheduling, and introduces a new business domain (outbound sales / lead gen) before the core platform is stable.
- **Concrete remediation:**
  1. Move Epic 21 and its UX contracts to a separate `roadmap/lead-gen-proposal-2026-08-11.md`.
  2. Keep only a one-line placeholder in `epics.md` until the governance gates (legal/ToS, vendor POC, PII pipeline, CRM scope, outcome pricing, Zalo/LinkedIn deferral) are closed.
  3. Before scheduling, create a single “Lead-Gen Data Model” story that owns `BillingEvent`, tenant `client_id` semantics, and the shared `Sequence`/`Signal` schema.

---

## 4. Major Findings

### M1. Story 12.4 (Vietnam Job Aggregator) is too large and not independently completable

- **Story ID:** 12.4.
- **Lines:** 1633–1654.
- **Violation:** 12 ACs cover source fan-out, normalization, deduplication, conflict detection, PII redaction, chunking, `NowingIngestService`, dead-letter queue, retries, and REST/MCP/chat exposure in a single P0 story.
- **Why it is a problem:** It cannot be completed in one sprint, cannot be parallelized, and hides delivery risk. It also depends on 12.1–12.3 and 20.2.
- **Concrete remediation:** Split into 5 focused stories:
  1. **12.4a** — normalize `VnJobListing` from the three sources.
  2. **12.4b** — deduplication, confidence scoring, and conflict flags.
  3. **12.4c** — PII redaction pipeline (shared with 12.5).
  4. **12.4d** — `NowingIngestService` hand-off and dead-letter queue.
  5. **12.4e** — REST/MCP/chat agent exposure.

### M2. Benchmark stories 4.8a–4.8g are marked done but lack proper Given/When/Then ACs

- **Story IDs:** 4.8a, 4.8b, 4.8c, 4.8e, 4.8f, 4.8g.
- **Lines:** 1122–1179.
- **Violation:** Acceptance criteria are one-line `_AC:` lists without `Given/When/Then`, no error paths, and no specific thresholds (e.g., lines 1124, 1129, 1134, 1168, 1173, 1178).
- **Why it is a problem:** The documented convention at line 111 requires English GWT ACs. “Done” stories without testable ACs cannot be verified or safely refactored.
- **Concrete remediation:** For each story, rewrite ACs in English `Given/When/Then` format, add error/edge cases (empty dataset, judge unavailable, CI failure, CAPTCHA rate-limit), and cross-check against existing tests in `nowing_evals/`.

### M3. Story 3.9 contains a placeholder ship-gate threshold

- **Story ID:** 3.9.
- **Line:** 295.
- **Violation:** AC states *“precision@5 ≥ X, noise ≤ Y”* despite the same line saying *“cấm placeholder `≥X%`”*.
- **Why it is a problem:** A ship-gate cannot block or release a build if the threshold is not a concrete number.
- **Concrete remediation:** Replace `X` and `Y` with ratified baseline numbers (e.g., `precision@5 ≥ 0.80`, `noise ≤ 0.10`), document the Wilson CI, and update `nowing_evals/.../gate.yaml`.

### M4. Epic 18 stories use system/platform personas and have architecture prerequisites

- **Story IDs:** 18.2, 18.4, 18.6, 18.8; and 18.3 database scope.
- **Lines:** 1727, 1759, 1789, 1819; 1748; 1799, 1828.
- **Violation:**
  - 18.2 and 18.4 start with *“As a chat system”*; 18.6 and 18.8 start with *“As a platform”* — these are not human users.
  - 18.6 is blocked until AD-31 is accepted; 18.8 requires composite RLS design before implementation.
- **Why it is a problem:** User stories should describe value for a human user; architecture blockers make the P0 schedule dependent on ADs not yet ratified.
- **Concrete remediation:**
  1. Rewrite personas to *“As a vertical client”* or *“As a platform operator”*.
  2. Create an explicit AD-31 tenant-tag story (add `client_id` to `Memory`, `TokenUsage`, `Run`, `AgentConfig`) before 18.6/18.8.
  3. Move 18.6–18.8 to P1 or split out the tenant/RLS work into a prerequisite story.

### M5. AD-33 Generic Alert Engine is a prerequisite but not an implementation story

- **Story IDs:** 12.6, 12.9, 14.3, 14.4, 15.3, 15.4, 16.3, 17.3, 17.4.
- **Lines:** 2081, 2627–2654.
- **Violation:** A shared alert engine is referenced as an architecture decision only. Line 2654 says *“If no dedicated implementation story exists, treat it as a prerequisite work package”* — but no such work package exists.
- **Why it is a problem:** Cannot be estimated, assigned, or tracked. It is also an example of “database/entity creation all upfront” in disguise because the alert-engine schema is implied but not owned.
- **Concrete remediation:** Create story **6.8** or **20.5**: *“As an automation builder, I want to define reusable alert rules so that scheduled checks trigger notifications.”* Add GWT ACs for `AlertRule` CRUD, `new_items` diff, and notification dispatch. Schedule before any alert consumer.

### M6. Mixed-language acceptance criteria in new ready-for-dev stories

- **Story IDs:** 3.15 (line 428), 3.16 (line 454), 18.2 (line 1736), 18.4 (line 1767), 18.5 (line 1782), 18.6 (line 1797), 18.7 (line 1812).
- **Lines:** 428, 454, 1736–1812.
- **Violation:** The documented convention at line 111 states *“ACs MUST use English with Given/When/Then format”*; new ready-for-dev stories still contain Vietnamese `Given/When/Then` clauses.
- **Why it is a problem:** Bilingual ACs slow automated test conversion, create ambiguity for non-Vietnamese engineers, and violate the project’s own documentation standard.
- **Concrete remediation:** Translate all ACs in `[ready-for-dev]`, `[P0]`, and `[P1]` stories to English GWT before development starts. Keep Vietnamese context in `Kỹ thuật` or `Ghi chú` sections.

### M7. Epic/section ordering and the Epic List are incomplete and confusing

- **Epic IDs:** All epics after 9.
- **Lines:** 109–153 (Epic List only shows 1–9), 1676–1684 (dropped Epic 13), 1687 (Epic 18 between 12 and 14), 2073 (second `## Epic 12` heading).
- **Violation:**
  - The `## Epic List` section stops at Epic 9.
  - Epic 18 is inserted between Epic 12 and 14.
  - Epic 12 appears twice with different sub-titles.
  - Dropped Epic 13 and dropped stories 12.7/12.8 remain in the document.
- **Why it is a problem:** It is hard to navigate, obscures dependency order, and increases the chance of accidentally scheduling dropped work.
- **Concrete remediation:**
  1. Rebuild the `Epic List` to include all 21 epics and proposed/roadmap epics.
  2. Re-order sections by dependency: platform enablers (Epic 20 / AD-33) before vertical data epics (12, 14–17).
  3. Merge the two `## Epic 12` sections or rename the second to `Epic 12 (Extended)`.
  4. Move dropped/proposed epics to an appendix.

### M8. Epic 21 assumes new shared tables that are never created in a schema story

- **Story IDs:** 21.1, 21.2, 21.3, 21.4, 21.5, 21.7.
- **Lines:** 2508, 2522, 2537–2538, 2551, 2555, 2567–2568, 2595.
- **Violation:** Stories specify writing rows to `SignalEvent`, `LeadScore`, `EnrichmentRequest`, `VerifiedContact`, `Sequence*`, `BillingEvent`, `OutcomeEvent`, `PricingPlan`, `CrmConnection`, but no story owns creating these tables/migrations.
- **Why it is a problem:** Violates “database/entity creation happens when first needed.” If multiple stories need the same table, a schema story must come first.
- **Concrete remediation:** Add a **Lead-Gen Data Foundation** story (or split into `BillingEvent` and `Tenant/Client Tag` stories) before any lead-gen behavior story. Define each table, its relationship to existing `TokenUsage`/`Memory`, and the `client_id` tenant semantics.

---

## 5. Minor Findings

### m1. Some acceptance criteria are unquantified or vague

- **Story IDs:** 4.8h (lines 1187, 1191), 3.17 (lines 467–473), 8.12 (line 692).
- **Violation:** Phrases like *“speed-mode latency gate”*, *“balanced-mode budget”*, *“reaches a limit”* lack concrete numbers or environment assumptions.
- **Concrete remediation:** Move the numbers from implementation hints into the AC or add explicit thresholds (e.g., speed mode ≤ 15s, balanced p95 cost ≤ 100k micros, free plan max 5 members / 100 documents).

### m2. Tech-debt follow-ups are written as user stories

- **Story IDs:** 3.7-followup (line 339), 4.8c-followup (line 1196), 4.8d-followup (line 1208), 4.8h-followup (line 1218), 8.11-followup (line 713), 9.6-followup (line 1062).
- **Violation:** These are implementation hardening tasks, not user-value stories.
- **Concrete remediation:** Move to a tech-debt register or JIRA backlog; keep only user-value stories in the epic document.

### m3. Implementation details leak into acceptance criteria

- **Story IDs:** 2.10 (lines 237–239), 10.1 (line 1296), 18.x (multiple `Kỹ thuật` lines intermixed with AC).
- **Violation:** ACs mention specific migration file names, internal maps, or decode pipelines.
- **Concrete remediation:** Keep migration names, file paths, and solution details in `Kỹ thuật` sections; ACs should describe observable behavior.

### m4. Core epic headers lack explicit user-value statements

- **Epic IDs:** 1, 2, 3, 4, 6, 8.
- **Lines:** 121, 125, 129, 133, 140, 151.
- **Violation:** They are capability/technical buckets with no *“As a … I want … so that …”* sentence.
- **Concrete remediation:** Add a one-line user-value statement to each epic header (e.g., *“As a workspace user, I want secure access and RBAC so that my data is isolated.”*).

### m5. DROPPED / PROPOSED content remains in the active implementation document

- **Epic/Story IDs:** Epic 13 (lines 1676–1684), 12.7 (line 2130), 12.8 (line 2136), 21.6 (lines 2571–2584).
- **Violation:** Dropped and deferred scope still occupies the main artifact.
- **Concrete remediation:** Move to an appendix or a `roadmap.md` file; keep the active backlog clean.

---

## 6. Epic Quality Review (Đánh giá tổng quan chất lượng Epic)

**Bối cảnh (Context):** `epics.md` là artifact tổng hợp cho một hệ thống brownfield đã chạy production. Nhiều epic ghi nhận lại công việc đã hoàn thành (`[DONE]`) nên tiêu chuẩn AC nghiêm ngặt không thể áp hết về quá khứ. Tuy nhiên, các story mới (`[ready-for-dev]`, `[P0]`, `[P1]`) **phải** tuân thủ `Given/When/Then` bằng tiếng Anh theo convention dòng 111. Đánh giá này tập trung vào khả năng triển khai (implementation readiness) của phần còn lại.

**Điểm mạnh (Strengths):**
- Epic 9 đã được tách khỏi Epic 2 và diễn đạt rõ user value: *“không vỡ, không treo, tính phí đúng.”*
- Hầu hết các story mới trong Epic 12, 20, và 21 (khi loại bỏ phần governance) có persona rõ ràng.
- Các AC của story 9.1a, 9.2, 12.1–12.3, 20.2–20.4 có error path cụ thể và đo được.

**Điểm yếu nghiêm trọng (Critical Weaknesses):**
1. **Dependency inversion giữa các epic dọc (vertical) và platform.** Epic 12, 14, 15, 16, 17 đều cần `NowingIngestService` (Epic 20) và `Generic Alert Engine` (AD-33). Đây là anti-pattern cơ bản: epic số nhỏ phụ thuộc epic số lớn hơn. Nếu không sửa, sprint planning sẽ bị “false start” — engineer pick story 12.4 nhưng phải đợi 20.2.
2. **AD-33 chưa là story.** Architecture Decision là ràng buộc, không phải deliverable có thể estimate. Mọi alert story (saved search, job alert, stock alert, v.v.) bị treo trên một prerequisite vô hình.
3. **Epic 21 quá sớm trong artifact triển khai.** Dù ghi `PROPOSED`, nó đã có UX contracts, wireframes, và 7 stories chi tiết. Điều này gây áp lực lịch trình và rủi ro scope creep.

**Khuyến nghị chiến lược (Strategic Recommendations):**
- **Bước 1 — Sửa cấu trúc epic:** Đưa Epic 20 và AD-33 story lên trước Epic 12/14–17. Renumber hoặc ít nhất reorder sections.
- **Bước 2 — Làm nhỏ (split) story 12.4** và các alert story để mỗi story độc lập hoàn thành trong 1 sprint.
- **Bước 3 — Dịch AC tiếng Việt còn lại** trong `[ready-for-dev]` sang tiếng Anh GWT.
- **Bước 4 — Tách Epic 21 ra proposal riêng** và chỉ merge lại khi governance gates (legal, PII, CRM, pricing, vendor POC) đóng.
- **Bước 5 — Viết lại AC cho 4.8a–4.8g** dù chúng đã done, để bảo vệ regression testing.

**Implementation Readiness Verdict:**
> **Conditional / Not Ready** for the post-`[DONE]` backlog. The platform enablers (Epic 20, AD-33) and the cross-tenant data model (AD-31) must be delivered or at least ratified before the vertical/lead-gen epics can move into `ready-for-dev`. The core product epics (1–11) and Epic 9 are in good shape. Chỉ khi các ràng buộc chéo (cross-cutting dependencies) được giải quyết, kế hoạch mới đạt trạng thái *Ready to Implement*.

---

## 7. Top 5 Issues to Resolve Before Implementation

1. **Cross-epic forward dependencies on Epic 20 / AD-33** — re-order and create the missing AD-33 story.
2. **Epic 21 is a proposal, not a backlog item** — move it out of the implementation artifact.
3. **Story 12.4 is too large and cross-cutting** — split into smaller, independently completable stories.
4. **4.8a–4.8g done stories lack testable GWT ACs** — rewrite their acceptance criteria.
5. **Epic 18 stories use system personas and depend on unaccepted AD-31** — rewrite personas and resolve tenant/RLS design first.

---

## 8. File Reference

- **Reviewed file:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md`
- **This report:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11-2_epic_quality_review.md`

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK** — The PRD, Architecture, and Epic 21 UX contracts are directionally aligned and the PRD itself is complete (70 FRs, 11 NFRs). However, `epics.md` contains structural dependency violations, unaccepted governance gates, and story-quality issues that must be resolved before Phase 4 implementation starts.

### Critical Issues Requiring Immediate Action

1. **Forward cross-epic dependencies on Epic 20 / AD-33** — Epics 12 and 14–17 assume `NowingIngestService`, service auth, and the generic Alert Engine that are not yet built or ratified. These consumer epics cannot be scheduled in parallel until the shared platform stories land.
2. **Epic 21 is `PROPOSED` but already over-detailed** — Lead Gen Intelligence has 7 stories, wireframes, and UX contracts despite open legal/vendor/PII/consent/CRM gates. Move it to a separate proposal document until the architecture and business gates close.
3. **Epic 20 placement and framing** — It appears after the epics that depend on it and uses a platform-centric title. Reposition/rename it to reflect user value and dependency order.
4. **Story 12.4 is epic-sized** — 12 ACs covering scraping, normalization, dedupe, PII, chunking, ingest, dead-letter, REST/MCP/chat in one story. Split into 5 independently completable stories.
5. **Benchmark / AC quality gaps** — Stories 4.8a–g are `done` but use one-line `_AC:` lists without Given/When/Then; Story 3.9 still has placeholder `precision@5 ≥ X`; Epic 18 mixes Vietnamese/English and system personas.

### Recommended Next Steps

1. **Re-sequence `epics.md`**: Move Epic 20 and a concrete AD-33 implementation story before Epics 12/14–17; do not mark consumer stories `ready-for-dev` until the prerequisites are `in-progress` or `done`.
2. **Convert AD-33 into a real implementation story** with migrations, tests, and acceptance criteria; place it in Epic 6 or Epic 20.
3. **Extract Epic 21 to a separate proposal artifact** and keep only a one-line placeholder in `epics.md` until governance gates close.
4. **Split Story 12.4** into 12.4a–e (normalization, dedupe/conflict, PII, ingest/DLQ, exposure).
5. **Rewrite acceptance criteria** for 4.8a–g, 3.9, and Epic 18 stories in English Given/When/Then with error paths and ratified thresholds.
6. **Run a focused architecture readiness check** on the new `Sequence`, `SignalEvent`, `LeadScore`, `VerifiedContact`, and `BillingEvent` entities before any Epic 21 implementation.

### Final Note

This assessment identified **16 issues** across **4 categories** (document inventory/duplicates, PRD traceability, UX alignment, epic quality). The codebase and architecture are further along than the backlog organization suggests, but the planning artifacts currently contain dependency and quality debt that will block parallel execution. Address the critical issues above before proceeding to implementation.

---

**Report generated:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11-2.md`  
**Assessor:** Implementation Readiness workflow (bmad-check-implementation-readiness)  
**Date:** 2026-08-11

---

## Addendum — Planning Cleanup Completed (2026-08-11)

The following critical issues from this report have been addressed in a follow-up cleanup:

1. **Epic dependency order fixed**: `epics.md` reordered so `Epic 20` and the new `Story 6.8 Generic Alert Engine` appear before consumer epics `12/14–17`.
2. **AD-33 converted to implementation story**: `Story 6.8 Generic Alert Engine` added to `Epic 6` with full ACs, diff strategies, and table schema.
3. **Story 12.4 split**: Replaced with `12.4a–e` covering normalization, dedupe/conflict, PII, ingest, and exposure.
4. **Epic 21 extracted**: Full scope moved to `epic21-proposal-2026-08-11.md`; `epics.md` now has a PROPOSED placeholder with governance gates.
5. **AC quality improved**: `4.8a–g`, `3.9`, `Epic 18`, `3.15`, and `3.16` acceptance criteria rewritten in English Given/When/Then with explicit error paths.
6. **Placeholder threshold removed**: `3.9` now uses concrete `precision@5 ≥ 0.80, noise ≤ 0.10` SM-10 numbers.
7. **Sprint status updated**: `sprint-status.yaml` tracks `6-8` and `12-4a–e`.

Commit: `aa5dc178c`

The report remains a useful record of the original assessment; a full re-run of the implementation-readiness workflow is recommended before the next planning gate to refresh the verdict.
