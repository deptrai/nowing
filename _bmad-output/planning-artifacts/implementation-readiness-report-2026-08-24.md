---
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
date: 2026-08-24
project: Nowing
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-24
**Project:** Nowing

## 1. Document Inventory

Các tài liệu chuẩn (canonical) được dùng để đánh giá:

- **PRD:** `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (toàn bộ, 1.569 dòng) + phụ lục `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`.
- **Architecture:** `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (đang active, được các story Epic 27 tham chiếu).
- **Epics:** `_bmad-output/planning-artifacts/epics.md`.
- **UX:** `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md`, `EXPERIENCE.md`.
- **Story liên quan Epic 27:**
  - `_bmad-output/implementation-artifacts/stories/27-2b-speaker-diarization-meeting-minutes.md` (vừa cập nhật)
  - `_bmad-output/implementation-artifacts/stories/27-2a-manus-slides-presentation-studio-chat.md`
  - `_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md`
- **Lưu ý:** các tệp trong `archive/` và `implementation-readiness/` là tài liệu lịch sử/đã thay thế.

---

## 2. PRD Analysis

### 2.1 Functional Requirements

PRD `prd-Nowing-2026-07-22/prd.md` chứa **72 FR** (theo khẳng định của Amendment §4). Các FR được liệt kê theo số hiệu, kèm câu mô tả đầu tiên, trạng thái và phân hệ/Epic.

#### §4.1 Identity, Auth & Workspace RBAC

- **FR-1: User Authentication**
  - Trạng thái: —
  - Mô tả: Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng.
  - Phân hệ: §4.1 Identity, Auth & Workspace RBAC.

- **FR-2: API Access for External Clients**
  - Trạng thái: —
  - Mô tả: Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.
  - Phân hệ: §4.1.

- **FR-3: Workspace Lifecycle**
  - Trạng thái: —
  - Mô tả: Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.
  - Phân hệ: §4.1.

- **FR-4: Workspace Invites & Memberships**
  - Trạng thái: —
  - Mô tả: Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.
  - Phân hệ: §4.1.

- **FR-10: RBAC với ba system roles**
  - Trạng thái: `[REMOVED]`
  - Mô tả: System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại.
  - Phân hệ: §4.1.

#### §4.2 Connectors / Ecosystem Integration

- **FR-6: Built-in Scraper Connectors**
  - Trạng thái: —
  - Mô tả: Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route.
  - Phân hệ: §4.2 Connectors.

- **FR-7: External OAuth Connectors**
  - Trạng thái: —
  - Mô tả: Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.
  - Phân hệ: §4.2.

- **FR-8: External MCP Connectors**
  - Trạng thái: —
  - Mô tả: Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.
  - Phân hệ: §4.2.

- **FR-43: VietnamWorks Scraper (Vietnam Job Market)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks.
  - Phân hệ: §4.2 / Epic 12 (HR & Recruitment Intelligence).

- **FR-44: TopCV Scraper (Vietnam Job Market)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot.
  - Phân hệ: §4.2 / Epic 12.

- **FR-45: ITviec Scraper (Vietnam Job Market)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing.
  - Phân hệ: §4.2 / Epic 12.

- **FR-46: Vietnam Job Market Aggregator (`vn_jobs.aggregate`)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper` để indexing và search. Nowing không giữ local search corpus.
  - Phân hệ: §4.2 / Epic 12.

- **FR-47: PII Redaction for Job Data**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: Pipeline xử lý dữ liệu từ job scrapers trước khi gửi `Chunk[]` tới `chainlens-research` (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`.
  - Phân hệ: §4.2 / Epic 12.

- **FR-48: Canonical Entity Storage & Multi-Domain Indexing (Epic 13)**
  - Trạng thái: `[REMOVED 2026-08-08 — moved to chainlens-research]`
  - Mô tả: Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector search, and merge history.
  - Phân hệ: §4.2 / Epic 13 (đã bỏ).

- **FR-49: News Aggregation (Epic 14)**
  - Trạng thái: `[PROPOSED] — re-scoped to feed chainlens-research`
  - Mô tả: As a researcher, I want news from major Vietnamese portals available in my workspace, So that I can search and reference news articles via the Nowing chat agent.
  - Phân hệ: §4.2 / Epic 14.

- **FR-50: Financial Data Integration (Epic 15)**
  - Trạng thái: `[PROPOSED] — re-scoped to feed chainlens-research`
  - Mô tả: As an investment researcher, I want stock prices, financial statements, and market news from CafeF and Vietstock, So that I can analyze company fundamentals via the Nowing chat agent.
  - Phân hệ: §4.2 / Epic 15.

- **FR-51: Company Data Integration (Epic 16)**
  - Trạng thái: `[PROPOSED] — re-scoped to feed chainlens-research`
  - Mô tả: As a business researcher, I want access to 2M+ Vietnamese company profiles with tax codes and registration data, So that I can verify business partners and research market players via the Nowing chat agent.
  - Phân hệ: §4.2 / Epic 16.

- **FR-52: E-commerce Intelligence (Epic 17)**
  - Trạng thái: `[PROPOSED] — re-scoped to feed chainlens-research`
  - Mô tả: As a product researcher, I want product data from Lazada and Shopee Vietnam, So that I can perform pricing analysis and competitor tracking via the Nowing chat agent.
  - Phân hệ: §4.2 / Epic 17.

- **FR-53: Social Media Integration (Epic 18)**
  - Trạng thái: `[DONE — covered by Epic 10 existing scrapers]`
  - Mô tả: As a social media analyst, I want public content data from YouTube, Reddit, Instagram, and TikTok, So that I can track sentiment, trends, and influencer content.
  - Phân hệ: §4.2 / Epic 18 (đã bỏ vì trùng Epic 10).

- **FR-54: Search Intelligence (Epic 19)**
  - Trạng thái: `[DEFERRED — covered by ChainLens generic crawl for web search]`
  - Mô tả: As a researcher, I want Google Search and Maps data integrated, So that I can search the web and find local businesses within Nowing.
  - Phân hệ: §4.2 / Epic 19 (đã bỏ).

- **FR-55: Global E-commerce (Epic 20)**
  - Trạng thái: `[DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon)]`
  - Mô tả: As a product researcher, I want product data from Amazon and Walmart, So that I can perform product research on global markets.
  - Phân hệ: §4.2 / Epic 20 (đã bỏ vì trùng Epic 2).

- **FR-56: Public Agent-Chat API for Vertical Clients**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a vertical client, I want to create chat threads and send messages via public API with PAT authentication, So that I can integrate Nowing chat into my application.
  - Phân hệ: §4.2 / Epic 18 (Vertical Client Platform).

- **FR-57: Agent Registry**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a platform administrator, I want to register agents with custom system prompts and tool configurations, So that different vertical clients can have specialized chat agents.
  - Phân hệ: §4.2 / Epic 18.

- **FR-58: Scraper Feed to chainlens-research (Ecosystem Integration)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a platform engineer, I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint, So that public/vertical search data is indexed in a single canonical index owned by the research engine.
  - Phân hệ: §4.2 / Epic 47.

- **FR-59: Gap-Fill Trigger via chainlens-research**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a workspace user, I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query, So that the system can fetch missing data on-demand without building a local search corpus.
  - Phân hệ: §4.2 / Epic 47.

- **FR-60: Private Data Provider (NowingPrivateProvider)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a workspace user, I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`, So that private data stays in Nowing but can still answer cross-corpus queries.
  - Phân hệ: §4.2 / governed by `AD-15`, `AD-35`.

- **FR-61: Cross-Project Service Auth & Cost Allocation**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a platform operator, I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered, So that cost and usage can be attributed correctly and the services cannot be spoofed.
  - Phân hệ: §4.2 / Epic 47.

- **FR-62: Canonical Chunk Metadata Schema (`source` enum)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a platform engineer, I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`, So that ingestion, search, and citation are consistent across the ecosystem.
  - Phân hệ: §4.2 / governed by `AD-34`.

- **FR-8.1: Exa MCP Search Connector**
  - Trạng thái: `[DONE 2026-08-05]`
  - Mô tả: As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.
  - Phân hệ: §4.2 / Story 2.10.

#### §4.10 Lead Gen Intelligence (mới 2026-08-10)

- **FR-63: Intent Signal Detection**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment.
  - Phân hệ: §4.10 / Epic 21 (Lead Gen Intelligence).

- **FR-64: Lead Scoring & Prioritization**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects.
  - Phân hệ: §4.10 / Epic 21.

- **FR-65: Enriched Contact Data**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers.
  - Phân hệ: §4.10 / Epic 21.

- **FR-66: Outbound Prospecting Automation**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality.
  - Phân hệ: §4.10 / Epic 21.

- **FR-67: CRM Integration & Write-Back**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth.
  - Phân hệ: §4.10 / Epic 21.

- **FR-68: Zalo Integration (Vietnam Market)**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform.
  - Phân hệ: §4.10 / Epic 21.

#### §4.3 Knowledge Base

- **FR-9: Document Upload, Parse & Index**
  - Trạng thái: —
  - Mô tả: Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng.
  - Phân hệ: §4.3 Knowledge Base.

- **FR-11: Folders & Document Management**
  - Trạng thái: —
  - Mô tả: Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.
  - Phân hệ: §4.3.

- **FR-12: Hybrid Search over Knowledge Base**
  - Trạng thái: —
  - Mô tả: Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`.
  - Phân hệ: §4.3.

- **FR-13: Citation Panel for Knowledge-base Chunks**
  - Trạng thái: —
  - Mô tả: Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel.
  - Phân hệ: §4.3.

- **FR-32: Long-Term Research Memory**
  - Trạng thái: `[DONE — story 3-14; baseline ratified 2026-08-04]`
  - Mô tả: Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP).
  - Phân hệ: §4.3 / Epic 3.

- **FR-33: Research Continuity**
  - Trạng thái: `[BUILT]` (chất lượng recall `[PARTIAL]`, phụ thuộc NFR-8)
  - Mô tả: Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó.
  - Phân hệ: §4.3.

- **FR-34: Memory Correction**
  - Trạng thái: `[BUILT]` (propagate qua relation graph `[GAP]` post-MVP)
  - Mô tả: Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history.
  - Phân hệ: §4.3.

- **FR-36: Legacy Memory Data-Loss Assessment & Recovery**
  - Trạng thái: `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]`
  - Mô tả: ✅ ĐÓNG 2026-07-25. Ops đã verify: migration 178 chưa apply trên prod (`alembic_version` = 174), `memory_md`/`shared_memory_md` rỗng, snapshot đã tạo → không có dữ liệu nào bị mất.
  - Phân hệ: §4.3.

- **FR-40: First-Run Value — Research Runs Produce Memory**
  - Trạng thái: `[DONE — story 3-13]`
  - Mô tả: MemoryExtractionService chỉ có một hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). Không có đường nào extract từ scrape run, deep research, hay document upload. Cộng với việc workspace mới không seed gì, hệ quả là `nowing_recall` ở session đầu trả rỗng — không phải vì bug, mà vì cấu trúc.
  - Phân hệ: §4.3.

- **FR-5: AI File Sorting (REMOVED)**
  - Trạng thái: `[REMOVED]`
  - Mô tả: Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172.
  - Phân hệ: §4.3.

#### §4.4 Chat & Agents

- **FR-14: Chat Threads & Messages**
  - Trạng thái: —
  - Mô tả: Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`.
  - Phân hệ: §4.4 Chat & Agents.

- **FR-15: Multi-agent Runtime with Tools**
  - Trạng thái: `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]`
  - Mô tả: Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware.
  - Phân hệ: §4.4.

- **FR-16: Real-time Collaborative Chat**
  - Trạng thái: —
  - Mô tả: Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.
  - Phân hệ: §4.4.

- **FR-17: Anonymous Chat with Quota**
  - Trạng thái: —
  - Mô tả: Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.
  - Phân hệ: §4.4.

- **FR-42: Chat Response Benchmark**
  - Trạng thái: —
  - Mô tả: Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.
  - Phân hệ: §4.4.

#### §4.5 Deliverables

- **FR-21: Report Generation & Export**
  - Trạng thái: —
  - Mô tả: Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.
  - Phân hệ: §4.5 Deliverables.

- **FR-22: Podcast & Video Presentation**
  - Trạng thái: —
  - Mô tả: Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes.
  - Phân hệ: §4.5.

- **FR-23: Image Generation**
  - Trạng thái: —
  - Mô tả: Tạo ảnh từ prompt, model, size, style, quality, response_format.
  - Phân hệ: §4.5.

#### §4.6 Automations

- **FR-18: Automation Action Types**
  - Trạng thái: `[DONE — cải chính 2026-07-25]`
  - Mô tả: Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), direct write-back actions riêng cho Notion/Slack/Linear/Jira, và `continue_research`.
  - Phân hệ: §4.6 Automations.

- **FR-19: Automation Triggers**
  - Trạng thái: —
  - Mô tả: Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event).
  - Phân hệ: §4.6.

- **FR-20: Automation Runs & Retries**
  - Trạng thái: —
  - Mô tả: Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy.
  - Phân hệ: §4.6.

- **FR-35: Memory-Driven Automations**
  - Trạng thái: `[DONE — cải chính 2026-07-25]`
  - Mô tả: Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu.
  - Phân hệ: §4.6.

#### §4.7 Multi-surface Clients

- **FR-25: Web Client (Next.js)**
  - Trạng thái: —
  - Mô tả: Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`.
  - Phân hệ: §4.7 Multi-surface Clients.

- **FR-26: Desktop Client (Electron)**
  - Trạng thái: —
  - Mô tả: Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.
  - Phân hệ: §4.7.

- **FR-27: Browser Extension (Plasmo)**
  - Trạng thái: —
  - Mô tả: Thu thập lịch sử duyệt web và gửi về backend.
  - Phân hệ: §4.7.

- **FR-28: Obsidian Plugin**
  - Trạng thái: —
  - Mô tả: Đồng bộ vault qua REST API `/obsidian/*`.
  - Phân hệ: §4.7.

- **FR-29: MCP Server**
  - Trạng thái: `[BUILT]` (4 memory tools)
  - Mô tả: MCP server expose scraper, KB, memory, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`.
  - Phân hệ: §4.7.

#### §4.8 Billing, Credits & Usage

- **FR-30: Token Usage Tracking**
  - Trạng thái: —
  - Mô tả: Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`.
  - Phân hệ: §4.8 Billing, Credits & Usage.

- **FR-31: Credit Wallet & Purchases**
  - Trạng thái: `[DONE]`
  - Mô tả: `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit.
  - Phân hệ: §4.8.

- **FR-41: Admin UI cho Global LLM Model Configuration**
  - Trạng thái: `[DONE — story 8-11]`
  - Mô tả: Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các global chat model thông qua một trang settings trên web UI, không cần sửa file/env và restart backend.
  - Phân hệ: §4.8.

- **FR-69: Outcome-Based Pricing Option**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered.
  - Phân hệ: §4.8 / Epic 21.

#### §4.9 Deep-Research Engine Integration (ChainLens)

- **FR-24: Deep Open-Web Research via ChainLens Engine**
  - Trạng thái: `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]`
  - Mô tả: Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp có trích dẫn, qua cả REST capability và MCP tool.
  - Phân hệ: §4.9 / Epic 9.

- **FR-37: Deep-Research Cost Metering**
  - Trạng thái: `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]`
  - Mô tả: Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo cost thật do engine báo về, không theo giá phẳng phỏng đoán.
  - Phân hệ: §4.9 / Epic 9.

- **FR-38: Research Degradation & Self-Host Independence**
  - Trạng thái: `[DONE — P0, tiền đề trước khi public repo]`
  - Mô tả: Nowing không được hard-fail khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens.
  - Phân hệ: §4.9 / Epic 9.

- **FR-39: Memory → Scraper-Run Provenance & Source Re-Validation**
  - Trạng thái: `[DONE — story 9-6]`
  - Mô tả: Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về đúng lần scrape đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không.
  - Phân hệ: §4.9 / Epic 9.

#### §4.10 Autonomous Workstation & Creative Studio (Manus-like)

- **FR-93: Full-Stack Web App Builder & Instant Hosting**
  - Trạng thái: `[BACKLOG]` — story `27.1` ready for development after this amendment.
  - Mô tả: Người dùng có thể mô tả một ứng dụng web bằng ngôn ngữ tự nhiên, agent sinh project Next.js/React + Tailwind CSS vào `/workspace/web-app`, và deploy 1-click lên `https://[app-name].apps.nowing.net` với HTTPS qua Traefik/Caddy.
  - Phân hệ: §4.10 / Epic 27 — Story 27.1.

- **FR-94: Design View Mark Tool & Presentation Studio**
  - Trạng thái: `[BACKLOG]` — story `27.2` ready for development after this amendment.
  - Mô tả: Người dùng có thể chỉnh sửa UI đã sinh bằng công cụ khoanh vùng trực quan (Mark Tool) để AST-mutate JSX, và có thể tạo/xuất slide deck PPTX/Marp từ prompt cùng bản ghi cuộc họp có speaker diarization.
  - Phân hệ: §4.10 / Epic 27 — Story 27.2.

**Tổng số FR trong PRD: 72.**

---

### 2.2 Non-Functional Requirements

PRD §5 liệt kê **11 NFR** (kể cả `NFR-MULTI-1`).

- **NFR-1: Performance**
  - Trạng thái: `[DONE]` (NFR-1b, NFR-1c, NFR-1d), với ghi chú về vế "vượt ngưỡng similarity" chưa expose score.
  - Mô tả đầu tiên: ⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5). NFR-1 cũ chỉ có "CRUD < 500ms" — không có bound nào cho memory, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra hai đường recall khác nhau, và chỉ một đường được PRD mô tả.

- **NFR-2: Security & Auth**
  - Trạng thái: —
  - Mô tả: JWT/cookie từ `fastapi-users`; PAT cho external clients. Permission check trên mọi workspace-scoped endpoint. Secrets qua `.env`, không hardcode.

- **NFR-3: Observability**
  - Trạng thái: —
  - Mô tả: OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter. Celery task monitoring.

- **NFR-4: Reliability**
  - Trạng thái: —
  - Mô tả: Async DB I/O bằng SQLAlchemy async. Celery + Redis cho background tasks. Retry policy cho automation runs và scraper calls.

- **NFR-5: Multi-tenancy Isolation**
  - Trạng thái: —
  - Mô tả: Mọi workspace-scoped query lọc theo `workspace_id`. `Workspace.api_access_enabled` kiểm soát truy cập API theo workspace.

- **NFR-MULTI-1: Tenant Isolation for Vertical Clients**
  - Trạng thái: `[PROPOSED]` — Epic 18 / AD-31.
  - Mô tả: Mọi memory/recall query từ public agent-chat API bắt buộc lọc theo `client_id` (hard filter, không phải soft boost). Một client không bao giờ thấy data của client khác. `client_id` được set qua PostgreSQL RLS context (`SET LOCAL app.current_client_id`). Áp dụng cho: Memory, TokenUsage, Run, ResearchThread.

- **NFR-6: Citation Full-Editor Highlight**
  - Trạng thái: `[DONE — cải chính 2026-07-25]`
  - Mô tả: Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor.

- **NFR-7: Usage & Credit Dashboard**
  - Trạng thái: `[DONE]`
  - Mô tả: Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`.

- **NFR-8: Recall Quality (eval-gated)**
  - Trạng thái: `[DONE — story 3-9]`
  - Mô tả: Chất lượng recall phải được đo và đạt ngưỡng trước khi ship lớp memory. Dùng harness `nowing_evals` chạy trên tập truy vấn thực để đo precision@k và noise rate của `nowing_recall`. Đặt ngưỡng tối thiểu — không ship nếu chưa đạt. Ngưỡng cụ thể chốt cùng SM-10.

- **NFR-9: Deep-Research Latency & Availability Budget (hai trạng thái)**
  - Trạng thái: State A `[DONE — implementation]`; State B `[PENDING RATIFICATION]` (cần ChainLens 34.1 + Nowing e2e p95 `balanced` ≤ 30s).
  - Mô tả: Latency của Deep-Research Engine là ràng buộc bên ngoài với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái chưa biết, và định nghĩa cổng để nâng cấp khi có số đo.

- **NFR-10: Chat Response Regression Gate**
  - Trạng thái: —
  - Mô tả: Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.

- **NFR-11: Scraping Compliance & Anti-Bot Resilience**
  - Trạng thái: `[PROPOSED]`
  - Mô tả: 1. ToS & Legal (Vietnam job market): Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use. Phải hoàn thành legal counsel opinion về employment service provider classification trước khi pilot bắt đầu. Giữ vững phân biệt Nowing là research/memory layer, không phải job board / ATS / employment intermediary.

**Tổng số NFR trong PRD: 11.**

---

### 2.3 Additional Requirements / Constraints

Các ràng buộc, giả định và phạm vi ngoài/tách biệt PRD đáng chú ý:

1. **FR-70 – FR-92 nằm ngoài PRD backlog.** Theo Amendment §3, `epics.md` vẫn giữ FR-70–FR-92 là out-of-PRD implementation backlog (Telegram Stream Daemon, Enterprise Lead Infrastructure, …).
2. **FR-95 – FR-99 không có trong PRD này.** Mặc dù bảng tổng hợp Amendment nêu "Enterprise Readiness & Compliance" *(Amendment 4 & 5)* với FR-95..FR-99, các FR này không xuất hiện dưới dạng heading `#### FR-95...` trong `prd.md`. Chúng nằm ở tài liệu phụ lục riêng hoặc chưa được hợp nhất vào PRD canonical.
3. **FR-48 – FR-55 bị re-scope/loại.** FR-48 chuyển sang `chainlens-research`; FR-49–52 re-scoped feed `chainlens-research`; FR-53–55 loại vì trùng với Epic 2/Epic 10/ChainLens.
4. **FR-5, FR-10 đã bị xóa khỏi sản phẩm.** FR-5 (AI File Sorting) gỡ migration 172; FR-10 (Admin role) gỡ migration 72.
5. **Non-Goals vĩnh viễn (§2.4 / §6.2):**
   - NG-1: Không bán raw research corpus / data-as-a-product. Không xây owned web index (ChainLens Epic 26 DEFERRED 0/7 gates).
   - NG-2: Không định vị parity consumer kiểu Perplexity.
   - NG-3: ChainLens không là sản phẩm độc lập.
   - NG-4: Không làm công cụ duyệt web thủ công / SLA/compliance doanh nghiệp / native mobile app.
   - NG-5: Nowing không xây public/vertical canonical index (`canonical_entities`, `pgvector` corpus, …); việc này thuộc `chainlens-research`.
6. **Deep research conditional:** State B (sync chat-mode) chỉ mở khóa khi ChainLens `43-1` → `43-2` + `43-5` land và story `9.3` xác nhận p95 `balanced` ≤ 30s. Self-host deep research Phase 2 là post-MVP.
7. **HR/Recruitment vertical gates (OQ-8):** Cần ToS review, legal counsel, TopCV anti-bot POC, ITviec salary visibility, PII pipeline ≥95%.
8. **Scraper budget gate:** Mọi built-in scraper mới phải qua gate (cap 30–50 scrapers) và anti-bot/ToS/cost POC trước khi P0.
9. **Memory / scraped-data retention `[GAP]` (OQ-3):** Chưa có retention + right-to-delete cho `memories`; cần chốt trước GA cloud.
10. **FR-93/FR-94 đã in-PRD và sẵn sàng phát triển** theo Amendment, dù trạng thái trong PRD vẫn ghi `[BACKLOG]`.

---

### 2.4 PRD Completeness Assessment

#### Đánh giá tổng quan

PRD `prd-Nowing-2026-07-22/prd.md` là bản hợp nhất (canonical) gồm 72 FR và 11 NFR, bao gồm cả hai FR của Epic 27 (FR-93, FR-94) nhờ Amendment 2026-08-20. PRD phân định rõ ranh giới giữa Nowing, ChainLens-Research và XActions, định nghĩa non-goals và các ràng buộc kiến trúc quan trọng. Tuy nhiên, có một số điểm cần lưu ý trước khi coi PRD là hoàn chỉnh cho Epic 27.

#### Độ đầy đủ cho Epic 27

- **FR-93 (Web App Builder) và FR-94 (Mark Tool & Presentation Studio)** đã được đưa vào PRD §4.10 dưới dạng mô tả cấp cao và acceptance criteria cơ bản. Cả hai đều liên kết với Epic 27, story 27.1 và 27.2.
- **Amendment** xác nhận FR-93/94 là `in-PRD`, `sprint-status.yaml` nâng `epic-27`, `27-1`, `27-2` lên `ready-for-dev`, và `epics.md` đã cập nhật.
- Các story thực thi (`27-1a`, `27-2a`, `27-2b`) cung cấp chi tiết kỹ thuật (chat mode, artifact kind, DB model, deployment Option A, async processing, v.v.) mà PRD không có. Như vậy, **PRD đủ để xác định phạm vi và acceptance criteria Epic 27, nhưng cần story + architecture spine để triển khai.**

#### FR-93 và FR-94 có rõ ràng không?

- **FR-93:** Mô tả cao cấp rõ ràng (mô tả bằng ngôn ngữ tự nhiên → sinh Next.js + Tailwind → deploy 1-click lên `*.apps.nowing.net`). Tuy nhiên, PRD thiếu các chi tiết: cơ chế chat mode (`platform_metadata.web_builder_mode`), gating plan, `WorkspaceApp`/`WebBuilderService`, publish Option A (backend wildcard host route) so với Docker container, custom CNAME scope, cost tracking `usage_type`, slug disambiguation, v.v. Các chi tiết này nằm trong `27-1a` story.
- **FR-94:** Mô tả tổng hợp Mark Tool + PPTX/Marp + speaker diarization. Tuy nhiên, đây là ba tính năng khác biệt (AST mutation, slide deck, meeting minutes) được gộp chung vào một FR; story `27-2a` (PPTX/Marp) và `27-2b` (speaker diarization) tách ra rõ ràng hơn. PRD không đề cập async Celery worker, `pyannote.audio` dependency, `MeetingMinutes` table, `SlidePresentation` table, `ArtifactKind` mapping, v.v.
- **Tính nhất quán với stories:** Stories `27-1a`, `27-2a`, `27-2b` đều cập nhật mới và trạng thái `ready-for-dev`/`done`, có acceptance criteria chi tiết. Điều này bổ sung đáng kể cho PRD.

#### Trạng thái (status) có chính xác không?

- **FR-93/FR-94 trong PRD ghi `[BACKLOG]`**, trong khi Amendment §4 ghi `ready-for-dev` và `sprint-status.yaml` cũng nâng lên `ready-for-dev`. Đây là **mâu thuẫn nhỏ** cần cập nhật PRD hoặc ít nhất ghi chú rõ ràng.
- **FR-8.1** ghi `[DONE 2026-08-05]`; cần verify migration `190_add_exa_mcp_connector.py` đã apply và `SearchSourceConnectorType` wiring đầy đủ.
- **FR-32** ghi `[DONE]`, nhưng PRD tự ghi nhận `search.py:97` bỏ score và `memories_routes.py:117` hardcode `score=0.0` ⇒ vế "vượt ngưỡng similarity" không thực hiện được. Đây là **mâu thuẫn giữa trạng thái DONE và thực tế code**, được chuyển cho story `3-14`.
- **NFR-1c** cũng ghi nhận vấn đề tương tự (score không expose), ảnh hưởng NFR-8 (recall quality gate).
- **FR-24** ghi `[DONE]` nhưng vẫn còn gap `mode default quality→balanced` (story 9.3) và Nowing parser đang bỏ 6 loại SSE event (`progress`, `insufficientEvidence`, `partial`, `synthesizing`, `heartbeat`, `noop`) — cần story `9.3` / `9.1a`.
- **FR-41** ghi `[DONE — story 8-11]`; tuy nhiên PRD vẫn nêu "khái niệm platform admin mới" mặc dù `User.is_superuser` đã tồn tại.

#### Các chi tiết còn thiếu hoặc mâu thuẫn

1. **Trùng lặp số hiệu mục lục:** `### 4.10 Lead Gen Intelligence` và `### 4.10 Autonomous Workstation & Creative Studio` đều dùng `§4.10`, gây nhầm lẫn. Cần đánh số lại (ví dụ §4.10 Lead Gen, §4.11 Autonomous Workstation) hoặc dùng tên rõ ràng.
2. **FR-95–FR-99 và FR-70–FR-92:** Không xuất hiện dưới dạng heading `#### FR-XX` trong PRD, mặc dù bảng tổng hợp Amendment liệt kê. Cần xác nhận chúng nằm ở phụ lục nào hoặc chưa được hợp nhất.
3. **MVP Scope vs. Epic 27:** `§6.1 In Scope` không liệt kê rõ Epic 27 (web builder/presentation studio) là in-scope MVP, dù Amendment đã đưa vào PRD. Điều này có thể gây tranh luận về mức độ ưu tiên.
4. **FR-93/94 missing technical depth:** Như đã nêu, PRD cần thêm cross-reference đến `AD-113`, `AD-114`, `AD-112`, `AD-115` và các story `27-1a`, `27-2a`, `27-2b` trong phần Consequences hoặc Acceptance Criteria.
5. **NFR-9 State B pending:** Chưa có số e2e Nowing chứng minh p95 `balanced` ≤ 30s; phụ thuộc ChainLens 34.1 (target 2026-08-19). Đây là dependency ngoài cần theo dõi.
6. **OQ-3 memory retention:** Là rào cản pháp lý trước GA cloud, chưa phải là FR/NFR cụ thể trong PRD.

#### Kết luận

PRD đã **đủ để xác định phạm vi Epic 27** ở cấp độ cao và đã ghi nhận FR-93/94 là in-PRD. Tuy nhiên, để **sẵn sàng triển khai (implementation-ready)**, cần:

- Cập nhật trạng thái FR-93/94 từ `[BACKLOG]` thành `ready-for-dev` trong PRD.
- Sửa trùng lặp số hiệu `§4.10`.
- Bổ sung cross-reference đến architecture spine (`AD-113`, `AD-114`, `AD-112`, `AD-115`) và các story `27-1a`, `27-2a`, `27-2b`.
- Xác nhận vị trí của FR-70–FR-92 và FR-95–FR-99 (out-of-PRD backlog hay cần đưa vào PRD).
- Giải quyết mâu thuẫn FR-32 / NFR-1c (similarity score chưa expose) trước khi chốt NFR-8 baseline.

Nếu chỉ xét **Step 02 — PRD Analysis**, tài liệu đáp ứng yêu cầu để chuyển sang Step 03 với điều kiện các gap trên được ghi nhận và theo dõi.

## 3. Epic Coverage Validation

Tất cả **72 FR** được trích xuất từ PRD canonical đã được đối chiếu với `epics.md` (Epic overview, Requirements Inventory, từng section epic) và các story liên quan Epic 27 (`27-1a`, `27-2a`, `27-2b`).

**Chú thích trạng thái:**
- **✓ Covered**: FR đã được epic/story trong `epics.md` bao phủ đầy đủ và nằm trong phạm vi thực hiện.
- **⚠ PARTIAL**: Có epic/story liên quan nhưng PRD ghi `[PROPOSED]` (không thuộc MVP), bị `re-scoped` sang `chainlens-research`, hoặc chỉ còn phần feed/cơ sở hạ tầng; cần xác nhận lại phạm vi.
- **❌ MISSING**: Không tìm thấy epic/story nào trong `epics.md` bao phủ FR.
- **🚫 REMOVED/OUT-OF-SCOPE**: FR đã bị loại bỏ, chuyển sang `chainlens-research`, hoặc deferred không còn thuộc phạm vi Nowing.

#### Identity, Auth & Workspace RBAC

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | User Authentication | Epic 1 | ✓ |
| FR-2 | API Access for External Clients | Epic 1 | ✓ |
| FR-3 | Workspace Lifecycle | Epic 1 | ✓ |
| FR-4 | Workspace Invites & Memberships | Epic 1 | ✓ |
| FR-10 | RBAC với ba system roles | Epic 1 (FR-10 đã bị loại; RBAC hiện tại chỉ Owner/Editor/Viewer) | 🚫 |

#### Connectors / Ecosystem Integration

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-6 | Built-in Scraper Connectors | Epic 2 | ✓ |
| FR-7 | External OAuth Connectors | Epic 2 | ✓ |
| FR-8 | External MCP Connectors | Epic 2 | ✓ |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | Epic 12 / Story 12.1 (PRD: [PROPOSED]) | ⚠ |
| FR-44 | TopCV Scraper (Vietnam Job Market) | Epic 12 / Story 12.2 (PRD: [PROPOSED]) | ⚠ |
| FR-45 | ITviec Scraper (Vietnam Job Market) | Epic 12 / Story 12.3 (PRD: [PROPOSED]) | ⚠ |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | Epic 12 / Stories 12.4a–e (PRD: [PROPOSED]) | ⚠ |
| FR-47 | PII Redaction for Job Data | Epic 12 / Story 12.5 (PRD: [PROPOSED]) | ⚠ |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing | Epic 13 (đã bỏ) / chuyển sang `chainlens-research` | 🚫 |
| FR-49 | News Aggregation (Epic 14) | Epic 14 (re-scoped feed `chainlens-research`) | ⚠ |
| FR-50 | Financial Data Integration (Epic 15) | Epic 15 (re-scoped feed `chainlens-research`) | ⚠ |
| FR-51 | Company Data Integration (Epic 16) | Epic 16 (re-scoped feed `chainlens-research`) | ⚠ |
| FR-52 | E-commerce Intelligence (Epic 17) | Epic 17 (re-scoped feed `chainlens-research`) | ⚠ |
| FR-53 | Social Media Integration | Epic 2 / Epic 10 (scraper hiện có) | ✓ |
| FR-54 | Search Intelligence | Không có epic Nowing (deferred sang ChainLens generic crawl) | 🚫 |
| FR-55 | Global E-commerce | Epic 2 / Stories 2.6 (Walmart), 2.7 (Amazon) | ✓ |
| FR-56 | Public Agent-Chat API for Vertical Clients | Epic 18 (PRD: [PROPOSED]) | ⚠ |
| FR-57 | Agent Registry | Epic 18 (PRD: [PROPOSED]) | ⚠ |
| FR-58 | Scraper Feed to `chainlens-research` | Epic 20 (PRD: [PROPOSED]) | ⚠ |
| FR-59 | Gap-Fill Trigger via `chainlens-research` | Epic 20 (PRD: [PROPOSED]) | ⚠ |
| FR-60 | Private Data Provider (`NowingPrivateProvider`) | Epic 20 (PRD: [PROPOSED]) | ⚠ |
| FR-61 | Cross-Project Service Auth & Cost Allocation | Epic 20 (PRD: [PROPOSED]) | ⚠ |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | Epic 20 (PRD: [PROPOSED]) | ⚠ |
| FR-8.1 | Exa MCP Search Connector | Epic 2 / Story 2.10 (DONE 2026-08-05) | ✓ |

#### Lead Gen Intelligence

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-63 | Intent Signal Detection | Epic 21 / Story 21.1 (PRD: [PROPOSED]) | ⚠ |
| FR-64 | Lead Scoring & Prioritization | Epic 21 / Story 21.2 (PRD: [PROPOSED]) | ⚠ |
| FR-65 | Enriched Contact Data | Epic 21 / Story 21.3 (PRD: [PROPOSED]) | ⚠ |
| FR-66 | Outbound Prospecting Automation | Epic 21 / Story 21.4 (PRD: [PROPOSED]) | ⚠ |
| FR-67 | CRM Integration & Write-Back | Epic 21 / Story 21.5 (PRD: [PROPOSED]) | ⚠ |
| FR-68 | Zalo Integration (Vietnam Market) | Epic 21 / Story 21.6 (PRD: [PROPOSED]) | ⚠ |

#### Knowledge Base

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-9 | Document Upload, Parse & Index | Epic 3 | ✓ |
| FR-11 | Folders & Document Management | Epic 3 | ✓ |
| FR-12 | Hybrid Search over Knowledge Base | Epic 3 | ✓ |
| FR-13 | Citation Panel for Knowledge-base Chunks | Epic 3 | ✓ |
| FR-32 | Long-Term Research Memory | Epic 3 / Story 3.14 | ✓ |
| FR-33 | Research Continuity | Epic 3 | ✓ |
| FR-34 | Memory Correction | Epic 3 | ✓ |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | Epic 3 / Stories 3.10a, 3.10b | ✓ |
| FR-40 | First-Run Value — Research Runs Produce Memory | Epic 3 / Story 3.13 | ✓ |
| FR-5 | AI File Sorting | — (đã bị loại ở migration 172) | 🚫 |

#### Chat & Agents

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-14 | Chat Threads & Messages | Epic 4 | ✓ |
| FR-15 | Multi-agent Runtime with Tools | Epic 4 | ✓ |
| FR-16 | Real-time Collaborative Chat | Epic 4 | ✓ |
| FR-17 | Anonymous Chat with Quota | Epic 4 | ✓ |
| FR-42 | Chat Response Benchmark | Epic 4 / Stories 4.8a–4.8g | ✓ |

#### Deliverables

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-21 | Report Generation & Export | Epic 5 | ✓ |
| FR-22 | Podcast & Video Presentation | Epic 5 | ✓ |
| FR-23 | Image Generation | Epic 5 | ✓ |

#### Automations

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-18 | Automation Action Types | Epic 6 / Story 6.4 | ✓ |
| FR-19 | Automation Triggers | Epic 6 | ✓ |
| FR-20 | Automation Runs & Retries | Epic 6 | ✓ |
| FR-35 | Memory-Driven Automations | Epic 6 / Story 6.5 | ✓ |

#### Multi-surface Clients

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-25 | Web Client (Next.js) | Epic 7 | ✓ |
| FR-26 | Desktop Client (Electron) | Epic 7 | ✓ |
| FR-27 | Browser Extension (Plasmo) | Epic 7 | ✓ |
| FR-28 | Obsidian Plugin | Epic 7 | ✓ |
| FR-29 | MCP Server | Epic 7 | ✓ |

#### Billing, Credits & Usage

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-30 | Token Usage Tracking | Epic 8 | ✓ |
| FR-31 | Credit Wallet & Purchases | Epic 8 / Story 8-3 | ✓ |
| FR-41 | Admin UI cho Global LLM Model Configuration | Epic 8 / Story 8-11 | ✓ |
| FR-69 | Outcome-Based Pricing Option | Epic 21 / Story 21.7 (PRD: [PROPOSED]) | ⚠ |

#### Deep-Research Engine Integration (ChainLens)

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-24 | Deep Open-Web Research via ChainLens Engine | Epic 9 / Stories 9.1b, 9.3 | ✓ |
| FR-37 | Deep-Research Cost Metering | Epic 9 / Story 9.2 | ✓ |
| FR-38 | Research Degradation & Self-Host Independence | Epic 9 / Story 9.1a | ✓ |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | Epic 9 / Story 9.6 | ✓ |

#### Autonomous Workstation & Creative Studio

| FR Number | PRD Requirement (short) | Epic Coverage | Status |
|---|---|---|---|
| FR-93 | Full-Stack Web App Builder & Instant Hosting | Epic 27 / Story 27.1a (PRD: [BACKLOG]; epics.md/sprint-status: `ready-for-dev`) | ✓ |
| FR-94 | Design View Mark Tool & Presentation Studio | Epic 27 / Stories 27.2a, 27.2b (PRD: [BACKLOG]; epics.md/sprint-status: `ready-for-dev`) | ✓ |

### Missing FR Coverage

Các FR sau **không được bao phủ đầy đủ** hoặc **nằm ngoài phạm vi Nowing**, kèm tác động và khuyến nghị:

1. **FR-43 – FR-47 (Vietnam Job Market scrapers / PII)** — Epic 12 có story P0, nhưng PRD ghi `[PROPOSED]`. *Impact:* nếu đưa vào MVP, cần hoàn tất ToS/legal review, anti-bot/PII gate; nếu không, cập nhật PRD gỡ hoặc đánh dấu backlog.
2. **FR-49 – FR-52 (News / Financial / Company / E-commerce Intelligence)** — `re-scoped` sang `chainlens-research` qua `NowingIngestService`. Chỉ còn feed/crawl trong Epic 14–17/Epic 20; UI/search thuộc về `chainlens-research`. *Impact:* cần xác nhận PRD muốn Nowing làm vertical search UI hay chỉ feed.
3. **FR-54 (Search Intelligence)** — deferred sang ChainLens generic crawl, **không có epic Nowing**. *Impact:* nếu Nowing cần Google Search/Maps scraper riêng, phải tạo Epic 19 tracking story; nếu ChainLens đảm nhận, ghi rõ trong PRD.
4. **FR-56 – FR-57 (Public Agent-Chat API / Agent Registry)** — Epic 18 in-progress nhưng PRD ghi `[PROPOSED]`. *Impact:* cần PRD quyết định MVP cho vertical client.
5. **FR-58 – FR-62 (Ecosystem Integration / `chainlens-research` feed, auth, schema)** — Epic 20 đã done nhưng PRD ghi `[PROPOSED]`. *Impact:* PRD cần cập nhật trạng thái nếu đây là P0; nếu không, chuyển sang backlog.
6. **FR-63 – FR-69 (Lead Gen Intelligence + Outcome-Based Pricing)** — Epic 21 in-progress/done nhưng PRD ghi `[PROPOSED]`. *Impact:* PRD cần cập nhật hoặc tách thành epic/FR riêng; FR-69 nằm trong §4.8 Billing nhưng map sang Epic 21, cần xem xét lại phân hệ.
7. **FR-5 (AI File Sorting)** — đã bị loại bỏ (migration 172). *Impact:* không cần hành động; PRD nên xóa.
8. **FR-10 (RBAC ba system roles)** — đã bị loại (Admin role). *Impact:* PRD nên cập nhật để loại bỏ FR này.
9. **FR-48 (Canonical Entity Storage & Multi-Domain Indexing)** — chuyển sang `chainlens-research`. *Impact:* PRD cần đánh dấu removed và tham chiếu Epic 13 dropped.

### Coverage Statistics

- **Tổng số FR trong PRD:** 72
- **✓ Covered:** 45 (62,5%)
- **⚠ PARTIAL:** 23 (31,9%)
- **🚫 REMOVED/OUT-OF-SCOPE:** 4 (5,6%)
- **❌ MISSING:** 0

Tỷ lệ cover có cam kết (loại trừ REMOVED/OUT-OF-SCOPE): **45 / 68 ≈ 66,2%**.

> **Ghi chú về FR ngoài PRD:** FR-70–FR-92 (Telegram/Lead-gen infrastructure) và FR-95–FR-99 (PRFAQ-derived enterprise/self-host) xuất hiện trong consolidated matrix của `epics.md` nhưng **không có dưới dạng heading `#### FR-XX` trong `prd-Nowing-2026-07-22/prd.md`**. Các FR này được ghi nhận là **`not in PRD`**. FR-99 (recall precision/noise gate) được theo dõi trong Epic 3 / Story 3.18 nhưng nguồn gốc là PRFAQ, không phải PRD canonical.

## 4. UX Alignment Assessment

### UX Document Status

- **UX master docs tồn tại:**
  - `ux-designs/ux-Nowing-2026-08-15/DESIGN.md`
  - `ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md`
  - `ux-designs/ux-Nowing-2026-08-15/ux-contract-first-run-onboarding.md`
  - `ux-designs/ux-Nowing-2026-08-15/ux-contract-readiness-gaps.md`
- **UX docs thiếu / chưa tìm thấy:**
  - Không có UX contract hoặc wireframe chuyên biệt cho **Epic 27** (Web Builder, Presentation Studio, Speaker Diarization).
  - Không có `ux-contract-epic-27-*` trong `ux-designs/ux-Nowing-2026-08-15/`.

### UX ↔ PRD Alignment

- **FR-93 (Web App Builder)** yêu cầu: prompt → Next.js app → deploy → custom CNAME. UX chi tiết nằm trong `27-1a` story (chat flow, deliverable card, publish drawer, domain manager). Đây là user-facing flow, cần `DESIGN.md` cập nhật hoặc UX contract riêng.
- **FR-94 (Design View / Presentation Studio)** yêu cầu: canvas/mark tool, iframe preview, bounding box selector, PPTX/Marp, speaker diarization. UX chi tiết nằm trong `27-2a` và `27-2b` stories (chat prompt picker, artifact card, Zero-sync status, download). Thiếu wireframe/visual spec tổng hợp.
- Các `27-*` stories đã bao gồm các yếu tố UX như `ArtifactKind=meeting_minutes`, `ChatMode` registry, deliverable card, right-to-delete, nhưng chưa được trích xuất thành tài liệu UX chuẩn.

### UX ↔ Architecture Alignment

- Kiến trúc **Autonomous Workstation** (`architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md`) hỗ trợ UX Epic 27 qua các AD:
  - **AD-5 Zero sync** — real-time deliverable card updates.
  - **AD-21 Client tab state pointer-only** — `?mode=meeting_minutes` / `?mode=web_builder` qua URL.
  - **AD-113** (Full-Stack Web App Builder) và **AD-114** (Design View Mark Tool) — nền tảng kỹ thuật cho FR-93/94.
  - **AD-28.3 Retention + right-to-delete** — xóa audio/temp file, xóa meeting minutes.
- Không phát hiện xung đột kiến trúc với UX; các ràng buộc về quyền riêng tư, async, Zero sync đều được phản ánh trong stories.

### Warnings

- **⚠️ UX doc thiếu cho Epic 27:** PRD đã in-PRD FR-93/94, `epics.md` đã `ready-for-dev`, nhưng không có UX contract chính thức. Rủi ro: frontend implementation có thể diverge khỏi intent sản phẩm. Khuyến nghị: tạo `ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-27-autonomous-workstation.md` hoặc bổ sung section trong `DESIGN.md`/`EXPERIENCE.md`.
- **⚠️ Manus feature audit (`manus-nowing-feature-audit-2026-08-20.md`) liệt kê 4 gaps (AI Music, Mobile App, SEO, Team SSO)** không nằm trong PRD/epics; cần quyết định in-scope/out-of-scope để tránh scope creep trong Epic 27.

---

## 5. Epic Quality Review

This section evaluates `epics.md` and the relevant Epic 27 stories (`27-1`, `27-1a`, `27-2a`, `27-2b`) against the `create-epics-and-stories` quality criteria. A lightweight spot-check was also performed on other `ready-for-dev` / `in-progress` epics surfaced by `sprint-status.yaml` and the PRD coverage gaps in Section 3 (Epic 25, Epic 28, Epic 7, Epic 12/14–18/20/21).

### Methodology

For each story, the review assessed:

- **User value focus:** user-centric goal and clear “so that …” statement.
- **Epic independence:** no forward dependency on a later epic.
- **Story independence:** no forward dependency inside the epic; cross-cutting changes are isolated or sequenced.
- **Story sizing:** delivers meaningful user value and is not a “setup all models” or “login UI (depends on 1.3)” slice.
- **Acceptance criteria:** Given/When/Then or BDD style, testable, specific, and covering error/edge paths.
- **Database/entity creation timing:** tables created when first needed, not all upfront.
- **Traceability to FRs:** explicit FR (and where relevant AD) references.

### Critical Violations

#### C-1: Story 27.1 is a single mega-story bundling four sub-systems and is still in `review`

- **Example:** `stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md` status is `review` and lists 7 major gaps: LLM code generator, build/preview runner, Docker deploy, custom CNAME, Mark Tool, `WorkspaceApp` table, and frontend builder page. The story file itself warns it is the "scope lớn nhất trong roadmap — toàn bộ code mới" (`epics.md:3969`).
- **Impact:** Violates story sizing and independence. It cannot be completed in one iteration and mixes UI, code generation, container runtime, networking, and AST mutation. This is the core FR-93 deliverable, so Epic 27 cannot be considered implementation-ready while 27.1 remains unsplit.
- **Recommendation:** Split `27.1` into smaller, independently shippable stories before any further implementation:
  - `27.1b` — Next.js project generator + preview (no deploy).
  - `27.1c` — 1-click container deploy + `*.apps.nowing.net` Traefik/Caddy routing.
  - `27.1d` — Custom CNAME / domain connect.
  - `27.1e` — Mark Tool bounding-box selector + JSX AST mutation.
  Keep `27.1a` as the existing chat-first, sales/marketing, Option A slice; mark `27.1` as `split` or `backlog`.

#### C-2: Story 27.2b has a hard forward dependency on the `ChatMode` registry that does not exist

- **Example:** `stories/27-2b-speaker-diarization-meeting-minutes.md:63` states "add `meeting_minutes_mode` to the same `ChatMode` registry proposed in 27.2a". The `Alignment action items for 27.2b` (line 131) and AD-30 action item make the registry mandatory. `27.2a` is `ready-for-dev` and `27.1a` uses a hardcoded `web_builder_mode` block in `orchestrator.py`, so the registry does not yet exist.
- **Impact:** Directly violates "no forward dependencies within an epic". `27.2b` cannot be implemented without first building the `ChatMode` registry in `27.2a` (or in a preceding story). Parallelizing `27.2a` and `27.2b` would create duplicative or conflicting registry implementations.
- **Recommendation:** Create a `27.0` or `27.1a-followup` story "Chat-mode registry + artifact system extension" that lands before `27.2a` and `27.2b`. Both `27.2a` and `27.2b` should then be updated to depend only on that shared foundation.

#### C-3: Story 27.1a deployment Option A diverges from active AD-113 without an architecture amendment

- **Example:** `ARCHITECTURE-SPINE.md:331-334` (AD-113, `[ADOPTED]`) still mandates per-app Docker containers with Traefik/Caddy dynamic routing. `stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md:139` and `Technical Requirements` state that v1a uses **backend-served static HTML via wildcard host route** and that "real container runtime is deferred to Story 27.4".
- **Impact:** This is an architecture drift between an accepted AD and a `done` story. If `27.1a` is treated as complete, it does not satisfy AD-113; if the team follows AD-113, the `27.1a` static-host implementation must be re-done.
- **Recommendation:** Ratify the MVP exception in the architecture spine (e.g., `AD-113a` — "MVP static-hosting exception for sales/marketing single-page sites") before any Epic 27 code is considered production-ready, or move `27.1a` out of `done` until AD-113 is fully implemented.

### Major Issues

#### M-1: `27.2a` and `27.2b` both claim to be the "Step 0" artifact-system extension

- **Example:** `27-2a-manus-slides-presentation-studio-chat.md:59` says "Treat this as **Step 0** and land before the deliverable card." `27-2b-speaker-diarization-meeting-minutes.md:68` also says "Treat as **Step 0**." Both stories touch the same files: `features/chat-artifacts/model/artifact.ts`, `ARTIFACT_TOOL_KINDS`, `BODY_TOOLS`, `KIND_META`, `GROUP_ORDER`, `collect-artifacts.ts`, and `assistant-message.tsx`.
- **Impact:** Two stories independently define mutually-required changes to a cross-cutting system. This creates merge conflicts and makes neither story independently implementable. It also risks `ArtifactKind` value collisions (e.g., `video` renamed to "Video Presentations" in `27.2a` while `27.2b` adds `meeting_minutes` after "Slide Decks").
- **Recommendation:** Designate a single owner for the artifact-system extension. Either add it to the proposed `27.0` foundation story, or have `27.2a` own the extension and `27.2b` explicitly reuse it with a dependency note.

#### M-2: `27.2a` acceptance criteria omit mandatory architecture action items

- **Example:** The story’s `Architecture Alignment (Nowing Spine)` table flags `AD-4` (AgentActionLog + permission middleware), `AD-9` (RBAC via `require_workspace_member`), and `AD-30` (`ChatMode` registry) as ⚠️ required actions. However, none of these appear in the `Acceptance Criteria` section or in the task checklist.
- **Impact:** These are security/audit and correctness gates. Without explicit ACs or tasks, implementers may skip `AgentActionLog` writes, leave routes unauthenticated, or hardcode a new `if/elif` block in `orchestrator.py`.
- **Recommendation:** Add ACs to `27.2a`:
  - AC-6: All `presentation_routes.py` endpoints require `require_workspace_member`.
  - AC-7: `generate_presentation` tool call writes an `AgentActionLog` entry.
  - AC-8: No hardcoded `if is_presentation_studio_mode` block is added; mode uses the `ChatMode` registry.

#### M-3: `27.2b` has unpatched edge cases in its Challenge Log

- **Example:** `stories/27-2b-speaker-diarization-meeting-minutes.md:413-424` lists several `[ ]` unpatched edge cases: duration/file-size boundary (inclusive vs exclusive), zero/sub-second audio, `audio_url` empty/whitespace, `document_id` ≤ 0, concurrent double-click creating duplicate rows, duplicate public URL, `language="auto"` low probability, unsupported model size, and speaker count > cap. These are not reflected in acceptance criteria.
- **Impact:** Boundary, concurrency, and language gaps will likely surface as support tickets or flaky tests after implementation.
- **Recommendation:** Convert the unpatched `[ ]` Challenge Log items into ACs or sub-tasks before moving `27.2b` to `in-progress`.

#### M-4: `28.5` has a forward dependency on `28.3` for source-risk-tier logic

- **Example:** `stories/28-5-workspace-memory-storage-cap-and-retention.md:85-88` states that source risk tier (`memory_source_legal_tiers`) is **owned by Story 28.3** and that `28.5` does NOT create the table; if it exists, the retention task MAY use per-source defaults. Per `sprint-status.yaml`, `28-5` is `ready-for-dev` while `28-3` is `backlog`.
- **Impact:** Within-epic forward dependency. If `28.5` is implemented before `28.3`, it will ship with workspace-level defaults only, leaving the FR-97/ToS legal risk-tier requirement unfulfilled and potentially exposing high-risk scraped sources.
- **Recommendation:** Either move `28.3` ahead of `28.5`, or explicitly scope `28.5` to workspace-level retention and create a follow-up `28.5b` for per-source risk tiers after `28.3` lands.

#### M-5: Ready-for-dev stories `25-5`, `25-6`, and `7.8` exist only in `epics.md` without dedicated story files

- **Example:** `sprint-status.yaml` marks `25-5`, `25-6`, and `7-8` as `ready-for-dev`. `find_file_by_name` for `stories/25-5*.md`, `stories/25-6*.md`, and `stories/7-8*.md` returned no results; only `25-4` and `28-5` have dedicated story files. `epics.md:3606-3632` contains the ACs for `25.5` and `25.6`, and `epics.md:1059-1069` for `7.8`.
- **Impact:** Lack of story files means missing task lists, file lists, verification commands, architecture alignment, and challenge logs. This makes sprint planning and code review harder.
- **Recommendation:** Create story files for `25-5`, `25-6`, and `7.8` before they move to `in-progress`, or downgrade them to `backlog` until the create-story workflow is complete.

### Minor Concerns

#### m-1: `27.1a` story file contains two conflicting Review Findings sections

- **Example:** `stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md:212-237` includes a `bmad-code-review — chunk 1` section with many unchecked `[ ]` patches and decisions (e.g., permission model, CSP, UUID typing, host-header domain validation). A later `Review Findings` section (lines 410-423) marks the same issues as `[x]` resolved.
- **Impact:** The unchecked section can mislead future readers into thinking the story is not complete or that the patches are open.
- **Recommendation:** Remove or clearly annotate the older `chunk 1` section as superseded by the final `Dev Notes` Review Findings.

#### m-2: `27.2a` contradicts itself on `enabled_tools` for the chat mode

- **Example:** `stories/27-2a-manus-slides-presentation-studio-chat.md:134` says "set `enabled_tools=["generate_presentation"]"`. The `Architecture Review Notes` (line 58) say "Do not set `enabled_tools` exclusively; the mode should inject a system prompt and keep base tools available."
- **Impact:** Implementers may ship a single-tool thread that disables `memory`, `search`, etc., contrary to the architecture note.
- **Recommendation:** Resolve the contradiction: either explicitly decide on single-tool mode (and update the architecture note) or keep base tools enabled and add a nudge prompt.

#### m-3: `27.2b` AC-2 label format is inconsistent with the technical spec

- **Example:** `27.2b` AC-2 (line 290) expects transcript segments labeled **"Speaker A", "Speaker B"**, while the Technical Requirements and Edge Cases (lines 195, 358) use **"Speaker 1", "Speaker 2"** and cap labels at a configurable `MEETING_MINUTES_MAX_SPEAKER_LABELS`.
- **Impact:** Acceptance test ambiguity.
- **Recommendation:** Align AC-2 with the "Speaker 1..N" convention and add a max-speaker boundary.

#### m-4: `27.2b` dependency compatibility claim needs validation before implementation

- **Example:** The story relies on `pyannote.audio>=4.0.0` as an optional extra and claims compatibility with the repo’s pinned `torch==2.11.0`. The Verification Commands (line 377) include `uv run uv lock --extra meeting-minutes --extra cpu`, but the story is `ready-for-dev` without recorded evidence.
- **Impact:** A dependency conflict could block implementation immediately.
- **Recommendation:** Run the lock command and record the result in the story’s Dev Agent Record before marking `27.2b` as ready to start.

#### m-5: `25-4` does not explicitly trace to a PRD FR

- **Example:** `stories/25-4-realtime-llm-token-cost-proxy-health-celery-queue-telemetry.md` references `INV-25.5`, `INV-25.6`, `INV-25.8`, and existing services, but does not map to a specific PRD FR. Epic 25 itself does not list FRs in `epics.md`.
- **Impact:** Weak traceability back to product requirements; a reviewer cannot confirm which PRD section is being satisfied.
- **Recommendation:** Add an FR mapping (e.g., FR-30/31 for token/credit telemetry, FR-41 for admin UI, or PRFAQ-derived AR/RS) to the story frontmatter.

#### m-6: `7.8` and `25-5`/`25-6` ACs lack explicit error-state coverage

- **Example:** `epics.md:1065-1069` for `7.8` covers happy-path locale switching but does not state behavior for unsupported locales or missing translations. `epics.md:3606-3617` for `25.5` does not cover non-superadmin 403 or invalid selector syntax errors.
- **Impact:** Edge/error cases may be implemented inconsistently.
- **Recommendation:** Add error/edge ACs before implementation: unsupported locale fallback, 403 authz, ReDoS > 50ms rejection, emergency circuit-breaker confirmation.

### Spot-Check of Other In-Progress / Ready-for-Dev Epics

A lightweight review was performed on the epics flagged by `sprint-status.yaml` and Section 3 coverage gaps. Key observations:

- **Epic 12 (HR/Recruitment):** Stories `12.1–12.5` are `done`. The epic remains `in-progress` because FR-43–FR-47 are `[PROPOSED]` in the PRD, which is a PRD ↔ epic status mismatch, not a story-quality issue. Recommendation: update PRD status or move stories to `backlog` until the ToS/anti-bot/PII gates are ratified.
- **Epic 14–17 (News/Financial/Company/E-commerce):** All active stories are `done` and feed `chainlens-research` via `NowingIngestService`. They satisfy traceability (FR-49–FR-52 re-scoped) and table-per-need. No story-quality violations found.
- **Epic 18 (Vertical Client Platform):** All stories are `done`. No story-quality issues; the open question is PRD status (`[PROPOSED]` for FR-56/57), which was already noted in Section 3.
- **Epic 20 (Ecosystem Integration):** Marked `done`. Stories cover FR-58–FR-62 and use `NowingIngestService`. Good traceability and sizing.
- **Epic 21 (Lead Gen):** Heavily complete; the only remaining question is PRD `[PROPOSED]` status for several FR-63–FR-69, already covered in Section 3.
- **Epic 25 (Platform Administration):** `25-4` is well-sized and uses G/W/T ACs; `25-5` and `25-6` lack dedicated story files and detailed verification commands (see M-5/m-6).
- **Epic 28 (Self-Host Trust):** `28-1`–`28-4` are `backlog` and have clear G/W/T ACs. `28-5` is `ready-for-dev` but has the forward-dependency on `28.3` (see M-4).

### Epic 27 Readiness Verdict

**Verdict: Conditionally ready for development — the P1 slices (`27.2a` and `27.2b`) should not be started until a shared foundation story is created and the parent `27.1` is split.**

- **27.1a** is `done` as a sales/marketing chat-first slice, but it carries an **architecture drift with AD-113** (static Option A vs. per-app container) and its parent story `27.1` is still an oversized, un-split epic-level story in `review`.
- **27.2a** and **27.2b** are well-scoped user-value stories and use good G/W/T acceptance criteria, but they are **not independent**: both depend on a `ChatMode` registry that does not yet exist, both require the same cross-cutting `ArtifactKind` extension, and `27.2b` still has unpatched edge cases in its Challenge Log.
- **27.2a** also has **missing security/audit ACs** (`AgentActionLog`, `require_workspace_member`, `ChatMode` registry) despite being flagged as required in the architecture alignment table.

**Recommended next steps before pulling Epic 27 into the next sprint:**

1. Split `27.1` into smaller stories (deploy, custom CNAME, Mark Tool) or move it to `backlog`; keep `27.1a` as the MVP slice.
2. Create a `27.0` / `27.1a-followup` foundation story for the generic `ChatMode` registry and the unified `ArtifactKind` extension.
3. Update `27.2a` and `27.2b` to depend on that foundation story; add the missing auth/audit ACs to `27.2a`; patch the remaining `[ ]` edge cases in `27.2b`.
4. Ratify an `AD-113a` amendment (or update `ARCHITECTURE-SPINE.md`) to make the `27.1a` static-hosting exception canonical.

Once these items are resolved, Epic 27’s chat-first P1 slices will be implementation-ready.

## 6. Final Assessment

### Overall Readiness Status

**NEEDS WORK** — Project-wide implementation readiness is blocked by PRD ↔ epic status drift, missing UX contracts for Epic 27, and story-dependency/quality issues inside Epic 27. Epic 27 specifically is **conditionally ready** only if the foundation story and architecture drift are resolved first.

### Critical Issues Requiring Immediate Action

1. **PRD status mismatch (FR-43–47, FR-49–52, FR-56–62, FR-63–69, FR-93/94):** nhiều FR được ghi `[PROPOSED]` trong PRD nhưng `epics.md`/`sprint-status.yaml` đã `ready-for-dev`, `in-progress` hoặc `done`. Cần cập nhật PRD hoặc di chuyển các epic tương ứng sang đúng trạng thái.
2. **FR-54 (Search Intelligence) không có epic trong `epics.md`:** PRD vẫn giữ FR-54 nhưng không có owner. Cần quyết định giao cho Epic 19/ChainLens hoặc đánh dấu removed.
3. **Thiếu UX contract cho Epic 27:** FR-93/94 là user-facing nhưng không có `ux-contract-epic-27-*`. Rủi ro frontend diverge khỏi product intent.
4. **Story 27.1 oversized:** bundle 4 subsystem và vẫn `review`, trong khi `27.1a` đã `done`. Cần split hoặc chuyển thành epic-level container.
5. **Forward dependency `ChatMode` registry:** `27.2a` và `27.2b` đều phụ thuộc registry chưa tồn tại. Cần tạo story nền tảng `27.0` trước.
6. **Architecture drift AD-113 vs `27.1a`:** `27.1a` dùng static-hosting Option A, `ARCHITECTURE-SPINE.md` vẫn yêu cầu per-app Docker/Traefik. Cần phê duyệt exception `AD-113a`.
7. **`27.2b` còn edge cases chưa cập nhật vào ACs:** các mục Challenge Log Q3/Q4 còn `[ ]` cần đưa vào Acceptance Criteria hoặc test skeleton.

### Recommended Next Steps

1. **Sửa PRD + `sprint-status.yaml`:** ratify FR-93/94 và các FR đã in-progress/done; loại bỏ FR-10/FR-48; gán FR-54.
2. **Tạo foundation story `27.0` hoặc `27.1a-followup`:** generic `ChatMode` registry + `ArtifactKind`/`BODY_TOOLS`/`GROUP_ORDER` extension.
3. **Cập nhật `27.2a` và `27.2b`:** thêm dependency vào foundation story, bổ sung `AgentActionLog`/`require_workspace_member` ACs cho `27.2a`, patch edge cases `27.2b`.
4. **Tạo UX contract cho Epic 27:** wireframe/chat flow cho Web Builder, Presentation Studio, Speaker Diarization.
5. **Ratify `AD-113a`:** ghi nhận static-hosting exception hoặc revert `27.1a` về per-app container.
6. **Chạy `bmad-test-first-atdd` cho `27.2b`:** spec đã đủ chi tiết, cần viết test skeleton theo ACs.

### Final Note

Đánh giá này xác định **7 vấn đề nghiêm trọng** trải dài 4 nhóm: PRD traceability, UX alignment, Epic/story quality, và Architecture alignment. Epic 27 có tiềm năng `ready-for-dev` cho các slice P1 (`27.2a`, `27.2b`) sau khi giải quyết phụ thuộc `ChatMode` registry và drift kiến trúc. Các epic khác (14–21) chủ yếu cần cập nhật trạng thái PRD, không có vấn đề chất lượng story nghiêm trọng.

---

## 7. Re-check After Remediation (2026-08-24)

Focused re-assessment of the 7 critical issues from Section 6 after `bmad-prd`, `bmad-architecture`, `bmad-ux`, and the recent code patches to `web_builder_routes.py`, `schemas.py`, `build_web_app.py`, and `new_chat_routes.py`.

### 7.1 Status of previous 7 critical issues

| # | Issue | Current status | Evidence / Notes |
|---|---|---|---|
| 1 | **PRD status mismatch (FR-43–47, 49–52, 56–62, 63–69, 93/94)** | **RESOLVED** | The 2026-08-25 `bmad-prd` ratification pass updated `prd-Nowing-2026-07-22/prd.md` and `AMENDMENT-PRD-Status-Ratification-2026-08-25.md`. FR-43–47 are now `[DONE]`; FR-93/94 are now `[IN-PROGRESS]` with correct child-story references (27.1 `backlog`, 27.1a `done`, 27.1b/c/d `backlog`, 27.2a/27.2b `ready-for-dev`); FR-49–52 remain `[RE-SCOPED]`; FR-56–62 and FR-63–69 match `epics.md` and `sprint-status.yaml`. `epics.md` and `sprint-status.yaml` were updated to match. |
| 2 | **FR-54 no epic** | **RESOLVED** | PRD `FR-54` is now `[REMOVED]` (ChainLens-only, no Nowing epic). `epics.md` has no Epic 19 and line 3839 explicitly notes FR-54 deferred to ChainLens. |
| 3 | **Missing UX contract for Epic 27** | **RESOLVED** | `ux-contract-epic-27-autonomous-workstation.md` exists and covers FR-93/94 user flows (Web Builder, Presentation Studio, Meeting Minutes), screens, state patterns, and open questions. |
| 4 | **Story 27.1 oversized** | **RESOLVED** | `27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md` has been rewritten as a `backlog` parent/tracking story and split into `27-1b-web-app-build-preview-runner.md`, `27-1c-web-app-container-deploy-cname.md`, `27-1d-web-app-mark-tool-ast-mutator.md` (all `backlog`, with scoped ACs and file lists). `sprint-status.yaml` lines 301–305 reflect the new hierarchy; 27.1a remains `done`. |
| 5 | **Forward dependency `ChatMode` registry** | **RESOLVED** | `app/tasks/chat/streaming/flows/new_chat/chat_modes.py` created with `ChatMode` dataclass and registry for `web_builder`, `presentation_studio`, `meeting_minutes`, and `default`. `orchestrator.py` refactored to resolve the mode from `platform_metadata`, load `Workspace`, and apply per-workspace/global gating, system-prompt nudge, and optional tool allow-list. `new_chat_routes.py` also uses the registry. `PRESENTATION_STUDIO_ENABLED` and `MEETING_MINUTES_ENABLED` added to `app/config/__init__.py`. |
| 6 | **Architecture drift AD-113 vs 27.1a** | **RESOLVED** | `ARCHITECTURE-SPINE.md` §8 now contains `AD-113a` (ratified 2026-08-24), explicitly permitting the static-snapshot hosting exception for 27.1a. Code uses `WEB_BUILDER_PUBLIC_APPS_PATH` (e.g., `deploy_service.py:65`, `web_builder_routes.py:446`). |
| 7 | **27.2b unpatched edge cases** | **RESOLVED** | Story `27-2b-speaker-diarization-meeting-minutes.md` now has **AC-6: Edge Cases & Degradation** (lines 334–413) covering all Q3/Q4 rows. Challenge Log Q3 (lines 495–508) and Q4 (lines 512–523) are marked `[x] (covered by AC-6)`. The spec is ready for ATDD. |

### 7.2 New / emergent blockers from code and UX contract review

1. ~~`connect-src 'self'` CSP blocks external fetches in generated web apps.~~ **RESOLVED** — `preview_renderer.py` and `web_builder_routes.py` now use a shared `WEB_BUILDER_CSP` constant with `connect-src 'self' https:;` so generated apps can post lead-capture forms, load analytics, and call external HTTPS endpoints.

2. ~~Per-workspace `web_builder_enabled` not enforced in the chat-turn orchestrator.~~ **RESOLVED** — `orchestrator.py` now loads the `Workspace` and uses `is_chat_mode_enabled()` to enforce both the global feature flag and the per-workspace `Workspace.web_builder_enabled` field before entering any chat mode. `new_chat_routes.py` also uses the registry for thread-creation gating.

3. ~~`ChatMode` registry is architecture-only; 27.2a/27.2b have no code footprint.~~ **RESOLVED (registry) / NEXT STEP (tools)** — `app/tasks/chat/streaming/flows/new_chat/chat_modes.py` implements the generic registry. `PRESENTATION_STUDIO_ENABLED` and `MEETING_MINUTES_ENABLED` are in `app/config/__init__.py`, and `orchestrator.py`/`new_chat_routes.py` gate these modes. The `generate_presentation` and `generate_meeting_minutes` tools themselves are intentionally out of scope for this readiness pass; they will be registered in `main_agent/tools/index.py` and `registry.py` as part of implementing 27.2a and 27.2b.

4. ~~27.2a story still omits auth/audit from acceptance criteria.~~ **RESOLVED** — `27-2a-manus-slides-presentation-studio-chat.md` now has **AC-5: Auth, Audit, and Workspace Scoping** (lines 204–216) requiring `require_workspace_member` on all `presentation_routes.py` endpoints and `AgentActionLog` for `generate_presentation` tool calls.

### 7.3 Final Verdict

**CONDITIONALLY READY**

The Epic 27 planning artifacts are now implementation-ready for the current P1 slice (27.1a) and the 27.2a/27.2b foundations:

- `ChatMode` registry (`AD-120`) is implemented and wired into `orchestrator.py` and `new_chat_routes.py`.
- Story 27.1 has been split into a parent/tracking story plus `27-1a` (done), `27-1b/c/d` (backlog).
- 27.2a and 27.2b have complete acceptance criteria, including auth/audit (27.2a) and edge-case/degradation coverage (27.2b).
- CSP `connect-src` and per-workspace `web_builder_enabled` gating are now enforced.
- PRD/epic/sprint traceability has been reconciled in `epics.md` and `sprint-status.yaml`.

Remaining conditions before full implementation of 27.2a/27.2b:
1. Register `generate_presentation` and `generate_meeting_minutes` tools in `main_agent/tools/index.py` + `registry.py` as part of 27.2a/27.2b.

### 7.4 Recommended next steps

1. **Run `bmad-test-first-atdd`** for 27.2a and 27.2b; the specs are now ready and the `ChatMode` registry is in place.
2. **Implement 27.2a / 27.2b tools** — register `generate_presentation` and `generate_meeting_minutes` in `main_agent/tools/index.py` + `registry.py` and build their services, then flip `ChatMode.enabled_tools` if a tool-allowlist is desired.
3. **Address remaining UX contract open questions** (Mark Tool application surface, artifact group naming, CDN fallback allow-list) before final design sign-off.

### 7.5 Readiness remediation log (this session, 2026-08-24)

This section records the specific artifact changes made to address the Section 6 blockers.

#### 27.1 split into parent + child stories

- `stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md` was rewritten as a `backlog` parent/tracking story (frontmatter `status: backlog`, line 7; body line 12) with a child-story table (lines 34–39) and aggregated ACs (lines 43–49).
- New child stories created:
  - `stories/27-1b-web-app-build-preview-runner.md` — LLM project generation, `next build`/preview runner, workspace app registry, cost tracking (`status: backlog`).
  - `stories/27-1c-web-app-container-deploy-cname.md` — Docker container deploy, Traefik/Caddy dynamic host, custom CNAME (`status: backlog`).
  - `stories/27-1d-web-app-mark-tool-ast-mutator.md` — Mark Tool, iframe selector, DOM-to-JSX mapping, AST mutation (`status: backlog`).
- `sprint-status.yaml` lines 301–305 updated: `27-1: backlog`, `27-1a: done`, `27-1b/c/d: backlog`, `27-2: split`, `27-2a/27.2b: ready-for-dev`.
- `epics.md` Epic 27 story list (lines 3972–3978) now describes 27.1 as the parent tracking story with child links and marks 27.2a/27.2b as `[ready-for-dev]`.

#### 27.2a auth/audit and workspace scoping

- `stories/27-2a-manus-slides-presentation-studio-chat.md` now contains:
  - **AC-5: Auth, Audit, and Workspace Scoping** (lines 204–216) requiring `require_workspace_member` on all `presentation_routes.py` endpoints, `AgentActionLog` entries for `generate_presentation` tool calls, and workspace RBAC for list/download/preview/delete operations.
  - **AC-6: Feature Gating** (lines 218–222) for `PRESENTATION_STUDIO_ENABLED=false`.

#### 27.2b Challenge Log Q3/Q4 coverage

- `stories/27-2b-speaker-diarization-meeting-minutes.md` now contains:
  - **AC-6: Edge Cases & Degradation** (lines 334–413) with G/W/T criteria for audio duration/file-size boundaries, zero/sub-second audio, empty/invalid `audio_url`/`document_id`, concurrent double-click, language auto-detection fallback, unsupported model size, speaker count cap, audio download failures, GPU OOM, `pyannote.audio` import failure, `record_token_usage` failure, and user-deleted rows.
  - Challenge Log Q3 (lines 495–508) and Q4 (lines 512–523) rows are marked `[x] (covered by AC-6)`.
  - Triage conclusion (line 532) now reads: "Spec is ready for test-first ATDD."

#### PRD ↔ sprint-status.yaml ↔ epics.md reconciliation

- `epics.md` top-level Requirements Inventory (lines 46–64) and Epic overview sections updated:
  - FR-43–47 → `DONE` (Epic 12) with a reconciliation note (line 52).
  - FR-49–52 → `RE-SCOPED` (Epics 14–17).
  - FR-56–57 → `DONE` (Epic 18).
  - FR-63–69 → `IN-PROGRESS` (Epic 21).
- `sprint-status.yaml` updated to match: `epic-12: in-progress` with 12-1–12-5 `done`; `epic-14/15/16/17: re-scoped`; `epic-18: done`; `epic-21: in-progress`.

#### Code-side blockers resolved

- `ChatMode` registry implemented in `app/tasks/chat/streaming/flows/new_chat/chat_modes.py`; `orchestrator.py` and `new_chat_routes.py` now resolve mode, system prompt, `enabled_tools`, and per-workspace/global gating via the registry. Modes `web_builder`, `presentation_studio`, and `meeting_minutes` are supported with `PRESENTATION_STUDIO_ENABLED` and `MEETING_MINUTES_ENABLED` config.
- CSP `connect-src` expanded to `connect-src 'self' https:;` via a shared `WEB_BUILDER_CSP` constant in `preview_renderer.py` and `web_builder_routes.py` (preview + hosted snapshot endpoints).
- Per-workspace `web_builder_enabled` gating now enforced inside the chat-turn orchestrator by loading `Workspace` and calling `is_chat_mode_enabled()`.

#### Remaining blockers

- **27.2a/27.2b tool registration:** `generate_presentation` and `generate_meeting_minutes` LangChain tools must be created and registered in `main_agent/tools/index.py` and `registry.py` as part of their respective stories. The registry already supports these modes; no further architectural foundation is needed.

#### PRD status tag ratification completed

- The 2026-08-25 `bmad-prd` pass updated `prd-Nowing-2026-07-22/prd.md`: FR-43–47 → `[DONE]`; FR-93/94 → `[IN-PROGRESS]` with correct child-story references.
- `epics.md` updated: FR-93/94 and Epic 27 → `IN-PROGRESS`; reconciliation note for FR-43–47 marked resolved.
- `sprint-status.yaml` top comment updated to reflect 27.1 parent/children backlog.
- New amendment `AMENDMENT-PRD-Status-Ratification-2026-08-25.md` created; previous 2026-08-24 amendment marked superseded for the changed FRs.
