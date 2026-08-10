# PRD Requirements Extract

Source: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`

## Functional Requirements

- **FR-1: User Authentication** — Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth.
- **FR-2: API Access for External Clients** — Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.
- **FR-3: Workspace Lifecycle** — Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.
- **FR-4: Workspace Invites & Memberships** — Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.
- **FR-10: RBAC với ba system roles** — System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**.
- **FR-6: Built-in Scraper Connectors** — Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl.
- **FR-7: External OAuth Connectors** — Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.
- **FR-8: External MCP Connectors** — Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.
- **FR-43: VietnamWorks Scraper (Vietnam Job Market)** — Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks. [PROPOSED]
- **FR-44: TopCV Scraper (Vietnam Job Market)** — Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot. [PROPOSED]
- **FR-45: ITviec Scraper (Vietnam Job Market)** — Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing. [PROPOSED]
- **FR-46: Vietnam Job Market Aggregator (`vn_jobs.aggregate`)** — Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. [PROPOSED]
- **FR-47: PII Redaction for Job Data** — Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`. [PROPOSED]
- **FR-48: Canonical Entity Storage & Multi-Domain Indexing (Epic 13)** — Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. [REMOVED 2026-08-08 — moved to chainlens-research; Epic 13 dropped]
- **FR-49: News Aggregation (Epic 14)** — As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent. [RE-SCOPED 2026-08-08 — feed to chainlens-research] [PROPOSED]
- **FR-50: Financial Data Integration (Epic 15)** — As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent. [RE-SCOPED 2026-08-08 — feed to chainlens-research] [PROPOSED]
- **FR-51: Company Data Integration (Epic 16)** — As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent. [RE-SCOPED 2026-08-08 — feed to chainlens-research] [PROPOSED]
- **FR-52: E-commerce Intelligence (Epic 17)** — As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent. [RE-SCOPED 2026-08-08 — feed to chainlens-research] [PROPOSED]
- **FR-53: Social Media Integration (Epic 18 — REMOVED, feature covered by E10)** — As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content. [DONE — covered by Epic 10 existing scrapers]
- **FR-54: Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens)** — As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing. [DEFERRED — covered by ChainLens generic crawl for web search]
- **FR-55: Global E-commerce (Epic 20 — REMOVED, feature covered by E2)** — As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets. [DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon)]
- **FR-56: Public Agent-Chat API for Vertical Clients** — As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application. [PROPOSED]
- **FR-57: Agent Registry** — As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents. [PROPOSED]
- **FR-58: Scraper Feed to chainlens-research (Ecosystem Integration)** — As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine. [PROPOSED]
- **FR-59: Gap-Fill Trigger via chainlens-research** — As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus. [PROPOSED]
- **FR-60: Private Data Provider (NowingPrivateProvider)** — As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries. [PROPOSED]
- **FR-61: Cross-Project Service Auth & Cost Allocation** — As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed. [PROPOSED]
- **FR-62: Canonical Chunk Metadata Schema (`source` enum)** — As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem. [PROPOSED]
- **FR-63: Intent Signal Detection** — As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment. [PROPOSED]
- **FR-64: Lead Scoring & Prioritization** — As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects. [PROPOSED]
- **FR-65: Enriched Contact Data** — As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers. [PROPOSED]
- **FR-66: Outbound Prospecting Automation** — As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality. [PROPOSED]
- **FR-67: CRM Integration & Write-Back** — As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth. [PROPOSED]
- **FR-68: Zalo Integration (Vietnam Market)** — As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform. [PROPOSED]
- **FR-8.1: Exa MCP Search Connector** — As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval. [DONE 2026-08-05]
- **FR-9: Document Upload, Parse & Index** — Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`.
- **FR-11: Folders & Document Management** — Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.
- **FR-12: Hybrid Search over Knowledge Base** — Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion.
- **FR-13: Citation Panel for Knowledge-base Chunks** — Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel.
- **FR-32: Long-Term Research Memory** — Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. [DONE — story 3-14; baseline ratified 2026-08-04]
- **FR-33: Research Continuity** — Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó. [BUILT] [PARTIAL]
- **FR-34: Memory Correction** — Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history. [BUILT] [GAP]
- **FR-36: Legacy Memory Data-Loss Assessment & Recovery** — Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. [RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]
- **FR-40: First-Run Value — Research Runs Produce Memory** — `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). [DONE — story 3-13]
- **FR-5: AI File Sorting** — Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172. [REMOVED]
- **FR-14: Chat Threads & Messages** — Người dùng tạo thread, gửi message, nhận streaming response.
- **FR-15: Multi-agent Runtime with Tools** — Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware. [BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]
- **FR-16: Real-time Collaborative Chat** — Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.
- **FR-17: Anonymous Chat with Quota** — Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.
- **FR-42: Chat Response Benchmark** — Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.
- **FR-21: Report Generation & Export** — Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.
- **FR-22: Podcast & Video Presentation** — Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes.
- **FR-23: Image Generation** — Tạo ảnh từ prompt, model, size, style, quality, response_format.
- **FR-18: Automation Action Types** — Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`. [DONE — cải chính 2026-07-25]
- **FR-19: Automation Triggers** — Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event).
- **FR-20: Automation Runs & Retries** — Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy.
- **FR-35: Memory-Driven Automations** — Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu. [DONE — cải chính 2026-07-25]
- **FR-25: Web Client (Next.js)** — Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs).
- **FR-26: Desktop Client (Electron)** — Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.
- **FR-27: Browser Extension (Plasmo)** — Thu thập lịch sử duyệt web và gửi về backend.
- **FR-28: Obsidian Plugin** — Đồng bộ vault qua REST API `/obsidian/*`.
- **FR-29: MCP Server** — MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. [BUILT]
- **FR-30: Token Usage Tracking** — Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`.
- **FR-31: Credit Wallet & Purchases** — `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. [DONE]
- **FR-41: Admin UI cho Global LLM Model Configuration** — Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64`) thông qua một trang settings trên web UI, **không cần** sửa file/env và restart backend. [DONE — story 8-11]
- **FR-69: Outcome-Based Pricing Option (mới 2026-08-10)** — As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered. [PROPOSED]
- **FR-24: Deep Open-Web Research via ChainLens Engine** — Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool. [DONE — contract + regression guard in place; mode default quality→balanced còn 9.3] [BUILT] [GAP]
- **FR-37: Deep-Research Cost Metering** — Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán. [DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]
- **FR-38: Research Degradation & Self-Host Independence** — Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. [DONE — P0, tiền đề trước khi public repo]
- **FR-39: Memory → Scraper-Run Provenance & Source Re-Validation** — Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không. [DONE — story 9-6]

## Non-Functional Requirements

- **NFR-1: Performance** — NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. [DONE]
- **NFR-2: Security & Auth** — JWT/cookie từ `fastapi-users`; PAT cho external clients.
- **NFR-3: Observability** — OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter.
- **NFR-4: Reliability** — Async DB I/O bằng SQLAlchemy async.
- **NFR-5: Multi-tenancy Isolation** — Mọi workspace-scoped query lọc theo `workspace_id`.
- **NFR-MULTI-1: Tenant Isolation for Vertical Clients** — Mọi memory/recall query từ public agent-chat API **bắt buộc** lọc theo `client_id` (hard filter, không phải soft boost). [PROPOSED]
- **NFR-6: Citation Full-Editor Highlight** — Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor. [DONE — cải chính 2026-07-25]
- **NFR-7: Usage & Credit Dashboard** — Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`. [DONE]
- **NFR-8: Recall Quality (eval-gated)** — Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory. [DONE — story 3-9]
- **NFR-9: Deep-Research Latency & Availability Budget (hai trạng thái)** — Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. [DONE — implementation] [PENDING RATIFICATION]
- **NFR-10: Chat Response Regression Gate** — Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.
- **NFR-11: Scraping Compliance & Anti-Bot Resilience** — Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use. [PROPOSED]

**Total: 70 Functional Requirements and 12 Non-Functional Requirements.**
