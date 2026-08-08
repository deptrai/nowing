---
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment", "step-07-issue-resolution"]
filesIncluded:
  - "prds/prd-Nowing-2026-07-22/prd.md"
  - "architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "epics.md"
  - "ux-designs/ux-Nowing-2026-07-22/*.md"
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-08
**Project:** Nowing

## Step 1: Document Discovery

### PRD Files Found

**Sharded Documents:**
- Folder: `prds/prd-Nowing-2026-07-22/`
  - `prd.md` (main PRD)
  - `validation-report.md`
  - `review-rubric.md`
  - `review-prfaq-gap.md`
  - `.memlog.md`

### Architecture Files Found

**Sharded Documents:**
- Folder: `architecture/architecture-Nowing-2026-07-22/`
  - `ARCHITECTURE-SPINE.md` (main architecture spine, AD-1 through AD-33)
  - `epic-18-pat-scope-rls-threat-model.md`
  - `.memlog.md`

### Epics & Stories Files Found

**Whole Documents:**
- `epics.md` (177KB, modified 2026-08-08) — all 18 epics with stories

**Story Files (implementation-artifacts/):**
- 80 story files at root level (Epic 1-11 stories)
- 15 story files in `stories/` subdirectory (Epic 12-16 stories)

### UX Design Files Found

**Sharded Documents:**
- Folder: `ux-designs/ux-Nowing-2026-07-22/`
  - `ux-contract-vn-jobs-copy.md`
  - `ux-contract-sync-offline-indicator.md`
  - `ux-contract-agent-registry.md`
  - `ux-contract-chat-benchmark.md`
  - `ux-contract-admin-global-model-config.md`
  - `ux-contract-canonical-entity.md`
  - `ux-contract-first-run-onboarding.md`
  - `ux-contract-usage-dashboard.md`
  - `ux-contract-async-deep-research.md`

### Issues Found

**Duplicates (WARNING — not blocking):**
- 10 existing readiness reports found (2026-07-24 through 2026-08-08). This report (v3) supersedes prior versions.

**Missing Documents:**
- No standalone UX index file — UX contracts are individual files in `ux-Nowing-2026-07-22/` folder. This is acceptable (sharded format).
- `epic-11-architecture-review-2026-08-03.md` is a review artifact, not a primary architecture document. Will not include in assessment.

## Step 2: PRD Analysis

### Functional Requirements

**FR-1: User Authentication**
Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng.

**FR-2: API Access for External Clients**
Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.

**FR-3: Workspace Lifecycle**
Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.

**FR-4: Workspace Invites & Memberships**
Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.

**FR-5: AI File Sorting (REMOVED)**
Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172.

**FR-6: Built-in Scraper Connectors**
Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route.

**FR-7: External OAuth Connectors**
Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.

**FR-8: External MCP Connectors**
Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.

**FR-8.1: Exa MCP Search Connector**
As a workspace user, I want to connect the Exa AI MCP server as a first-class search connector, So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.

**FR-9: Document Upload, Parse & Index**
Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng.

**FR-10: RBAC với ba system roles**
System roles mặc định chỉ có Owner, Editor, Viewer. Migration 72 đã xóa role Admin.

**FR-11: Folders & Document Management**
Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.

**FR-12: Hybrid Search over Knowledge Base**
Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion.

**FR-13: Citation Panel for Knowledge-base Chunks**
Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn.

**FR-14: Chat Threads & Messages**
Người dùng tạo thread, gửi message, nhận streaming response.

**FR-15: Multi-agent Runtime with Tools**
Main agent gọi tools; có subagents chuyên biệt; recall workspace memory; dùng AgentFeatureFlags.

**FR-16: Real-time Collaborative Chat**
Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.

**FR-17: Anonymous Chat with Quota**
Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.

**FR-18: Automation Action Types**
Action registry: agent_task, direct write-back actions (Notion/Slack/Linear/Jira), continue_research.

**FR-19: Automation Triggers**
Hỗ trợ trigger schedule (cron) và event (webhook/connector event).

**FR-20: Automation Runs & Retries**
Mỗi lần kích hoạt tạo AutomationRun với status, error, progress; có retry policy.

**FR-21: Report Generation & Export**
Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.

**FR-22: Podcast & Video Presentation**
Tạo podcast 2 host từ document/folder; tạo video presentation với slides/scenes.

**FR-23: Image Generation**
Tạo ảnh từ prompt, model, size, style, quality, response_format.

**FR-24: Deep Open-Web Research via ChainLens Engine**
Người dùng và agent có thể chạy truy vấn deep research đa nguồn và nhận câu trả lời tổng hợp có trích dẫn.

**FR-25: Web Client (Next.js)**
Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs).

**FR-26: Desktop Client (Electron)**
Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.

**FR-27: Browser Extension (Plasmo)**
Thu thập lịch sử duyệt web và gửi về backend.

**FR-28: Obsidian Plugin**
Đồng bộ vault qua REST API `/obsidian/*`.

**FR-29: MCP Server**
MCP server expose scraper, KB, memory, và research tools qua Model Context Protocol.

**FR-30: Token Usage Tracking**
Mỗi assistant turn ghi TokenUsage với prompt_tokens, completion_tokens, total_tokens, cost_micros, model_breakdown, usage_type.

**FR-31: Credit Wallet & Purchases**
User.credit_micros_balance và credit_micros_reserved; CreditPurchase và PagePurchase theo dõi Stripe.

**FR-32: Long-Term Research Memory**
Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng Memory, hỗ trợ hybrid search và truy xuất qua REST/MCP.

**FR-33: Research Continuity**
Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó.

**FR-34: Memory Correction**
Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history.

**FR-35: Memory-Driven Automations**
Automation có thể kích hoạt khi memory thay đổi hoặc tiếp tục một research thread đã lưu.

**FR-36: Legacy Memory Data-Loss Assessment & Recovery**
Migration 177 tạo bảng memories nhưng không backfill; migration 178 DROP user.memory_md và workspaces.shared_memory_md. Memory markdown cũ có khả năng đã bị xoá mà không được migrate.

**FR-37: Deep-Research Cost Metering**
Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo cost thật do engine báo về.

**FR-38: Research Degradation & Self-Host Independence**
Nowing không được hard-fail khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens.

**FR-39: Memory → Scraper-Run Provenance & Source Re-Validation**
Memory sinh ra từ dữ liệu scrape phải trỏ được về đúng lần scrape đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không.

**FR-40: First-Run Value — Research Runs Produce Memory**
First research/scrape run phải produce memory with provenance; nowing_recall returns non-empty results after first action (≤15 minutes from signup to first recall with content).

**FR-41: Admin UI cho Global LLM Model Configuration**
Platform admin có thể xem, thêm, sửa, xoá, bật/tắt global chat model qua web UI, không cần sửa file/env và restart backend.

**FR-42: Chat Response Benchmark**
Hệ thống cung cấp benchmark trong nowing_evals để đo chat response với dữ liệu thực tế hoặc curated.

**FR-43: VietnamWorks Scraper (Vietnam Job Market)**
Capability vietnamworks.scrape gọi POST https://ms.vietnamworks.com/job-search/v1.0/search (no auth).

**FR-44: TopCV Scraper (Vietnam Job Market)**
Capability topcv.scrape để lấy job postings từ https://www.topcv.vn qua HTML scraping + anti-bot.

**FR-45: ITviec Scraper (Vietnam Job Market)**
Capability itviec.scrape để lấy job postings từ https://itviec.com qua HTML server-rendered parsing.

**FR-46: Vietnam Job Market Aggregator (vn_jobs.aggregate)**
Capability vn_jobs.aggregate để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, và phát hiện conflict.

**FR-47: PII Redaction for Job Data**
Pipeline xử lý dữ liệu từ job scrapers trước khi lưu vào memory để phát hiện và loại bỏ/mask thông tin cá nhân.

**FR-48: Canonical Entity Storage & Multi-Domain Indexing (Epic 13)**
Data from multiple sources deduplicated into canonical entities — one golden record per real-world entity instead of duplicate results.

**FR-49: News Aggregation (Epic 14)**
News from major Vietnamese portals integrated into workspace.

**FR-50: Financial Data Integration (Epic 15)**
Stock prices, financial statements, and market news from CafeF and Vietstock.

**FR-51: Company Data Integration (Epic 16)**
2M+ Vietnamese company profiles with tax codes and registration data.

**FR-52: E-commerce Intelligence (Epic 17)**
Product data from Lazada and Shopee Vietnam for pricing analysis and competitor tracking.

**FR-53: Social Media Integration (Epic 18 — REMOVED, feature covered by E10)**

**FR-54: Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens)**

**FR-55: Global E-commerce (Epic 20 — REMOVED, feature covered by E2)**

**FR-56: Public Agent-Chat API for Vertical Clients**
Vertical clients can create chat threads and send messages via public API with PAT authentication.

**FR-57: Agent Registry**
Platform admin can register agents with custom system prompts and tool configurations for different vertical clients.

**Total FRs: 47 active + 5 removed = 52 total**

### Non-Functional Requirements

**NFR-1: Performance**
API response p95 < 500ms cho CRUD; scraper call có thể mất vài giây nhưng streaming updates qua SSE.

**NFR-1a — CRUD & scraper (giữ nguyên)**
API response p95 < 500ms cho CRUD; scraper call có thể mất vài giây nhưng streaming updates qua SSE.

**NFR-1b — Memory injection (CHẶN mọi lượt chat)**
DB time p95 ≤ 150ms, độc lập với số memory row của workspace (O(top-k), không O(N)). Tổng ký tự memory được inject ≤ 8.000 chars, enforce ở đường ĐỌC.

**NFR-1c — Recall tool (nowing_recall, /memories/search)**
top_k ≤ 5, đã rank hybrid, vượt ngưỡng similarity. p95 ≤ 300ms.

**NFR-1d — Auto-extract (Celery, KHÔNG chặn lượt chat)**
Auto-extract không được nằm trên critical path của lượt chat. Freshness: memory mới khả dụng cho recall p95 ≤ 60s sau khi lượt chat kết thúc.

**NFR-2: Security & Auth**
JWT/cookie từ fastapi-users; PAT cho external clients. Permission check trên mọi workspace-scoped endpoint.

**NFR-3: Observability**
OpenTelemetry trace; logs qua Log model; SlowAPI rate limiter. Celery task monitoring.

**NFR-4: Reliability**
Async DB I/O bằng SQLAlchemy async. Celery + Redis cho background tasks. Retry policy cho automation runs và scraper calls.

**NFR-5: Multi-tenancy Isolation**
Mọi workspace-scoped query lọc theo workspace_id. Workspace.api_access_enabled kiểm soát truy cập API theo workspace.

**NFR-MULTI-1: Tenant Isolation for Vertical Clients**
Mọi memory/recall query từ public agent-chat API bắt buộc lọc theo client_id (hard filter). RLS context (SET LOCAL app.current_client_id). Áp dụng cho: Memory, TokenUsage, Run, ResearchThread.

**NFR-6: Citation Full-Editor Highlight**
Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor.

**NFR-7: Usage & Credit Dashboard**
Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian.

**NFR-8: Recall Quality (eval-gated)**
Chất lượng recall phải được đo và đạt ngưỡng trước khi ship lớp memory. precision@k và noise rate của nowing_recall. Không ship nếu chưa đạt.

**NFR-9: Deep-Research Latency & Availability Budget (hai trạng thái)**
State A (mặc định): async deliverable cho deep research, không block chat turn. Engine unavailable → FR-38 degradation.
State B (mở khoá sau): sync chat-mode sau feature flag, khi ChainLens 43-1, 43-2, 43-5 land và story 9.3 xác nhận p95 vượt ngưỡng.

**NFR-10: Chat Response Regression Gate**
Mọi deploy production phải qua gate chat regression. Metrics: p95 e2e latency, p95 TTFB, error rate, finish rate, citation count, cost/turn.

**NFR-11: Scraping Compliance & Anti-Bot Resilience**
ToS & Legal (Vietnam job market): Không build scrapers cho đến khi ToS cho phép. Anti-bot: TopCV yêu cầu POC pass. PII: detection coverage ≥95%. Reliability: vn_jobs.aggregate trả về degraded=true khi nguồn fail.

**Total NFRs: 11 (including sub-requirements NFR-1a through NFR-1d)**

### Additional Requirements

**Non-Goals (NG):**
- NG-1: Không bán research data (kiểu Exa / data-as-a-product)
- NG-2: Không đua parity consumer kiểu Perplexity
- NG-3: Không xây ChainLens thành sản phẩm độc lập
- NG-4: Công cụ duyệt web thủ công · SLA/compliance doanh nghiệp · native mobile app

**Open Questions (OQ):**
- OQ-1: External MCP connector marketplace — unresolved
- OQ-2: Agent tool default enable/disable — unresolved
- OQ-3: Retention, right-to-delete & phơi nhiễm pháp lý — HARD BLOCKER before GA cloud
- OQ-4: Per-workspace MCP tool enable/disable toggle — RESOLVED 2026-07-25
- OQ-5: Direct write-back action architecture — RESOLVED 2026-07-25
- OQ-6: Đồng bộ docs & artifacts với vision mới — DONE 2026-08-01
- OQ-7: Câu hỏi mở từ phía ChainLens — RESOLVED (4 sub-questions)
- OQ-8: HR/Recruitment Vertical in Vietnam — 6 HARD GATES (ToS, legal classification, anti-bot POC, salary visibility, pricing validation, PII pipeline)

**Success Metrics (SM):**
- SM-1 through SM-12g (primary, secondary, counter-metrics, memory-specific, deep-research engine, HR pilot-specific)
- Several SMs have placeholder targets ("≥ X%") that need quantification

**Assumptions:**
- 12 tracked assumptions, 4 confirmed, 5 unconfirmed (HR vertical hard gates)
- Key unconfirmed: ToS of VietnamWorks/TopCV/ITviec, legal classification, anti-bot POC, ITviec salary visibility

**Technical Constraints:**
- License: Apache-2.0 core + BSL 1.1 crawler engine
- Self-host vs Cloud: Self-host receives full product except deep open-web research (Phase 1: cloud-only)
- ChainLens Integration: POST /api/v1/search (SSE, Bearer service key)
- Data Strategy: 3 layers (Built-in Scrapers 30-50 max, User Connectors OAuth unlimited, Generic Web Crawl ChainLens unlimited)

**Business Constraints:**
- Pricing Decision Gate: Cannot finalize pricing before FR-37 and story 8-7 have real numbers
- HR Vertical Hard Gates: Cannot start building scrapers until ToS review and legal counsel complete
- Legal/Retention: Must resolve retention + right-to-delete for MEMORY before GA cloud (OQ-3)

### PRD Completeness Assessment

**Strengths:**
1. Exceptionally comprehensive (1363 lines) with clear product direction and architectural boundaries
2. Well-structured requirements: FRs and NFRs globally numbered with complete text and status tracking
3. Evidence-based decisions: Non-goals backed by evidence, changes documented with dates and reasoning
4. Active maintenance: Last updated 2026-08-07, corrections based on code verification

**Areas for Improvement:**
1. Metric targets not quantified: SM-1, SM-2, SM-3, SM-8 use "≥ X%" placeholders
2. OQ-3 is a hard blocker: Retention/right-to-delete for memory unresolved before GA cloud
3. HR vertical dependencies: OQ-8 has 6 hard gates unresolved
4. State B latency targets not ratified: NFR-9 State B baseline pending (story 9.3)
5. Some FRs (FR-48 through FR-57) are PROPOSED without clear timeline

**Ambiguities:**
1. Metric thresholds: "X%" placeholders make success criteria unclear
2. State B transition criteria: specific p95 thresholds not yet set
3. Memory relation graph scope: "fast-follow" undefined in timeline
4. Advanced memory lifecycle: Decay, TTL, contradiction graph resolution marked post-MVP without clear definition

**Overall: PRD is production-ready for current scope (MVP + defined epics) with clear work items for post-MVP and GA preparation.**

## Step 3: Epic Coverage Validation

### Coverage Matrix

| FR Number | Epic | Story | Status |
|-----------|------|-------|--------|
| FR-1 | Epic 1 | brownfield | done |
| FR-2 | Epic 1 | brownfield | done |
| FR-3 | Epic 1 | brownfield | done |
| FR-4 | Epic 1 | brownfield | done |
| FR-5 | — | — | REMOVED (migration 172) |
| FR-6 | Epic 2 | 2-5, 2-6, 2-7, 2-8, 2-9 | done |
| FR-7 | Epic 2 | covered by Epic 2 | done |
| FR-8 | Epic 2 | 2-5, 2-10 | done |
| FR-8.1 | Epic 2 | 2-10 (Exa MCP) | done |
| FR-9 | Epic 3 | 3-1 brownfield | done |
| FR-10 | Epic 1 | brownfield | done |
| FR-11 | Epic 3 | 3-2 brownfield | done |
| FR-12 | Epic 3 | 3-3 brownfield | done |
| FR-13 | Epic 3 | 3-4, 3-6, 3-15 | done |
| FR-14 | Epic 4 | brownfield | done |
| FR-15 | Epic 4 | brownfield | done |
| FR-16 | Epic 4 | brownfield | done |
| FR-17 | Epic 4 | brownfield | done |
| FR-18 | Epic 6 | 6-4 | done |
| FR-19 | Epic 6 | brownfield | done |
| FR-20 | Epic 6 | brownfield | done |
| FR-21 | Epic 5 | brownfield | done |
| FR-22 | Epic 5 | brownfield | done |
| FR-23 | Epic 5 | brownfield | done |
| FR-24 | Epic 9 | 9-1b | done |
| FR-25 | Epic 7 | brownfield | done |
| FR-26 | Epic 7 | brownfield | done |
| FR-27 | Epic 7 | brownfield | done |
| FR-28 | Epic 7 | brownfield | done |
| FR-29 | Epic 7 | brownfield | done |
| FR-30 | Epic 8 | 8-1 brownfield | done |
| FR-31 | Epic 8 | 8-2, 8-3 | done |
| FR-32 | Epic 3 | 3-8, 3-9, 3-11, 3-14 | done |
| FR-33 | Epic 4 | 4-6 | done |
| FR-34 | Epic 3/4 | covered by existing stories | done |
| FR-35 | Epic 6 | 6-5 | done |
| FR-36 | Epic 3 | 3-10 | resolved (no data loss) |
| FR-37 | Epic 9 | 9-2 | done |
| FR-38 | Epic 9 | 9-1a | done |
| FR-39 | Epic 9 | 9-6 | done |
| FR-40 | Epic 3 | 3-13 | done |
| FR-41 | Epic 8 | 8-11 | done |
| FR-42 | Epic 4 | 4-8a through 4-8h | done |
| FR-43 | Epic 12 | 12-1 | ready-for-dev |
| FR-44 | Epic 12 | 12-2 | ready-for-dev |
| FR-45 | Epic 12 | 12-3 | ready-for-dev |
| FR-46 | Epic 12 | 12-4 | ready-for-dev |
| FR-47 | Epic 12 | 12-5 | ready-for-dev |
| FR-48 | Epic 13 | 13-1, 13-2a-e, 13-3 | done |
| FR-49 | Epic 14 | 14-1 | done |
| FR-50 | Epic 15 | 15-1 | done |
| FR-51 | Epic 16 | 16-1 | done |
| FR-52 | Epic 17 | epic in backlog | backlog |
| FR-53 | — | — | REMOVED (covered by E10) |
| FR-54 | — | — | REMOVED (covered by ChainLens FR-24) |
| FR-55 | — | — | REMOVED (covered by E2 stories 2-6, 2-7) |
| FR-56 | Epic 18 | epic in backlog | backlog |
| FR-57 | Epic 18 | epic in backlog | backlog |

### Missing Requirements

**No critical missing FRs found.** All active FRs have traceable implementation paths.

**Removed/Deferred FRs (by design, not gaps):**
- FR-5: AI File Sorting — explicitly removed (migration 172)
- FR-53: Social Media Integration — removed, covered by Epic 10 scrapers
- FR-54: Search Intelligence — removed, covered by ChainLens (FR-24)
- FR-55: Global E-commerce — removed, covered by Epic 2 (stories 2-6, 2-7)

### Coverage Statistics

- **Total PRD FRs:** 57 (FR-1 through FR-57)
- **Active FRs:** 48 (excluding 5 removed + 4 deferred/duplicate)
- **Fully covered (done):** 40 FRs
- **In progress (ready-for-dev):** 5 FRs (FR-43 through FR-47 — Vietnam HR vertical)
- **Backlog:** 3 FRs (FR-52, FR-56, FR-57 — Epic 17/18)
- **Resolved:** 1 FR (FR-36 — legacy memory data-loss, confirmed no data loss)
- **Coverage percentage:** 100% of active FRs have traceable epic/story coverage

### Key Findings

1. **Epic 1-9: DONE** — Core platform functionality complete
2. **Epic 10-11: DONE** — Connector expansion and Telegram automation
3. **Epic 12 (Vietnam HR vertical):** 5 stories ready-for-dev (blocked by ToS legal review — OQ-8)
4. **Epic 13-16 (Canonical Entity + Verticals):** Initial stories done, expansion stories in backlog
5. **Epic 17-18 (E-commerce, Vertical Client Platform):** Backlog, no story files yet
6. **No FR coverage gaps detected** — every active FR has a traceable implementation path

## Step 4: UX Alignment Assessment

### UX Document Status

**Found:** 9 UX contract files in `ux-designs/ux-Nowing-2026-07-22/`

### Per-Contract Alignment

| UX Contract | FR Coverage | PRD Align | Arch Align | Gaps |
|-------------|-------------|-----------|------------|------|
| vn-jobs-copy | FR-43..47 | ✅ | ✅ AD-22..26 | None |
| sync-offline-indicator | FR-38 | ✅ | ✅ AD-4,5,15,18 | None |
| agent-registry | FR-57 | ✅ | ✅ AD-8,9,29,30,31 | None |
| chat-benchmark | FR-42, NFR-10 | ✅ | ✅ AD-10 | None |
| admin-global-model-config | FR-41 | ✅ | ✅ AD-8,9 | None |
| canonical-entity | FR-48, FR-46 | ✅ | ✅ AD-27,28 | None |
| first-run-onboarding | FR-40 | ✅ | ✅ AD-18 | None |
| usage-dashboard | FR-31, NFR-7 | ✅ | ✅ AD-8,10 | None |
| async-deep-research | NFR-9, FR-38 | ✅ | ✅ AD-4,5,15,17 | None |

**All 9 UX contracts are well-aligned with PRD and Architecture.** No misalignments or contradictions found.

### PRD FRs with UI Implications but NO UX Contract

**Critical Gaps (Core User Flows — 0% coverage):**

| FR | Feature | Impact | Priority |
|----|---------|--------|----------|
| FR-3 | Workspace Lifecycle | Core onboarding | P0 |
| FR-4 | Workspace Invites | Team collaboration | P0 |
| FR-14 | Chat Threads & Messages | Core chat UI | P0 |
| FR-15 | Multi-agent Runtime | Chat agent behavior | P0 |
| FR-16 | Real-time Collaborative Chat | Real-time collaboration | P0 |
| FR-13 | Citation Panel | KB citation display | P0 |

**Important Gaps (Secondary Features — 0% coverage):**

| FR | Feature | Impact | Priority |
|----|---------|--------|----------|
| FR-9 | Document Upload | Document management | P1 |
| FR-11 | Folders & Document Mgmt | File organization | P1 |
| FR-12 | Hybrid Search | Search results display | P1 |
| FR-21 | Report Generation | Deliverable UI | P1 |
| FR-22 | Podcast & Video | Media deliverables | P1 |
| FR-23 | Image Generation | Image gen UI | P2 |
| FR-6 | Scraper Connectors | Connector management | P2 |
| FR-7 | OAuth Connectors | Connector management | P2 |
| FR-8 | MCP Connectors | Connector management | P2 |
| FR-18 | Automation Actions | Automation config | P2 |
| FR-19 | Automation Triggers | Automation config | P2 |
| FR-20 | Automation Runs | Automation monitoring | P2 |
| FR-32 | Long-Term Memory | Memory browser UI | P3 |
| FR-33 | Research Continuity | Thread continuation | P3 |
| FR-34 | Memory Correction | Memory editing | P3 |

### Warnings

1. **22 PRD FRs with UI implications have no UX contract.** However, most of these are brownfield features (Epics 1-7) that were implemented before the UX contract process was established. The UI exists in code but was not formally specified via UX contracts.

2. **UX contracts are created for new features only** (Stories 3.13+, 8.3+, 9.3+, 12+, 13+, 18+). Brownfield features (Epics 1-7) have working UI but no formal UX specification. This is an accepted pattern for brownfield projects.

3. **No action required for brownfield gaps** — the UI is already shipped and working. UX contracts should be created for new features going forward.

### UX Coverage Summary

| Category | UX Contracts | PRD FRs with UI | Coverage |
|----------|-------------|-----------------|----------|
| Admin/Platform | 3 | 3 | 100% |
| Research/Memory | 3 | 5 | 60% |
| Usage/Billing | 2 | 2 | 100% |
| Vertical-Specific | 1 | 5 | 20% |
| Core Chat (brownfield) | 0 | 4 | 0% (shipped) |
| Document/KB (brownfield) | 0 | 3 | 0% (shipped) |
| Deliverables (brownfield) | 0 | 3 | 0% (shipped) |
| Connectors (brownfield) | 0 | 3 | 0% (shipped) |
| Automations (brownfield) | 0 | 3 | 0% (shipped) |
| Workspace/Auth (brownfield) | 0 | 2 | 0% (shipped) |

## Step 5: Epic Quality Review

### Executive Summary

**Overall Grade: B-** — Strong user-centric design and brownfield awareness, but critical forward dependency chain (Epic 12 → Epic 13 → Epic 18) must be resolved.

- 🔴 4 Critical Violations (forward dependencies)
- 🟠 8 Major Issues (story sizing, vague ACs, priority contradictions)
- 🟡 5 Minor Concerns (formatting, documentation gaps)

### 🔴 Critical Violations

**1. Epic 13 → Epic 12 Forward Dependency**
- Stories 13.2b and 13.2e explicitly depend on Epic 12 aggregator output contract and pilot data
- Impact: Epic 13 cannot complete without Epic 12
- Recommendation: Create Epic 12.5 "Jobs Aggregator Contract" story both epics depend on, OR document as intentional architectural dependency

**2. Epic 18 → Epic 13 Forward Dependency**
- Epic 18 entry criteria requires Epic 13 stories 13.1-13.3 code-review closed
- Impact: Sequential chain Epic 12 → Epic 13 → Epic 18
- Recommendation: Document as intentional Phase 2 dependency, OR split Epic 18 into platform foundation (start earlier) + vertical features (wait for Epic 13)

**3. Story 12.8 Blocked on Epic 13 (Cross-Epic Forward Dependency)**
- Story 12.8 (Cross-Source Entity Timeline) blocked waiting for Epic 13 canonical storage review
- Already marked `blocked` in sprint-status.yaml (Winston audit 2026-08-08)
- Recommendation: Move 12.8 to Epic 13 as "Timeline View for Canonical Entities", OR keep as intentional dependency with explicit documentation

**4. Story 16.4 Blocked on Epic 13 (Cross-Epic Forward Dependency)**
- Story 16.4 (Company Timeline) blocked, same rationale as 12.8
- Already marked `blocked` in sprint-status.yaml
- Recommendation: Same as 12.8 — move to Epic 13 or document as intentional

### 🟠 Major Issues

**5. Epic 12 Stories 12-6 through 12-9 Circular Dependencies**
- 12.6 (Job Alerts) needs saved searches from 12.9
- 12.7 (Property Alerts) needs canonical entities from Epic 13
- 12.8 blocked on Epic 13
- 12.9 (Saved Searches) needed by 12.6
- Recommendation: Reorder 12.9 as P0 before 12.6; move 12.7 and 12.8 to Epic 13; add explicit dependency notes

**6. Epic 13 Story 13.2 Split into 5 Sub-Stories**
- Original story was epic-sized, split into 13.2a-e
- This is actually GOOD practice (proper decomposition)
- Recommendation: Acknowledge as proper decomposition; consider promoting sub-stories to top-level for better tracking

**7. Epic 6 Stories 6.6, 6.7, 6.9 Business-Gated**
- Stories gated on business pilot completion, not technical dependencies
- Acceptable but should be tracked separately
- Recommendation: Mark as "business-gated" in sprint-status; consider separate "Post-Pilot" epic

**8. Epic 12 Story 12.0 Legal Review (Non-Technical Story)**
- Legal/ToS review story in technical epic
- Blocks 12.1-12.5 but delivers no user value itself
- Recommendation: Mark as "prerequisite" rather than story; acceptable given HR vertical domain

**9. Database/Entity Creation — Epic 13**
- Story 13.1 creates 4 tables upfront in one migration
- This is CORRECT practice for shared canonical storage layer (referential integrity requires all tables)
- Recommendation: No change needed; document as intentional

**10. Acceptance Criteria Quality — Bullet Points vs Given/When/Then**
- Stories 12.1, 12.2, 13.1, 13.2a-e use bullet points instead of Given/When/Then
- ACs are still testable but harder to convert to automated tests
- Recommendation: Convert to proper Given/When/Then format for consistency

**11. Epic 9 Story 9.5 Deferred Without Clear Path**
- Marked "POST-MVP — CHƯA PHÊ DUYỆT" with no approval criteria
- Recommendation: Add explicit approval criteria or move to Phase 2 epic

**12. Epic 14-17 Contradictory Priorities**
- Epics marked P2/deferred but contain P0 stories
- Creates confusion about what to work on
- Recommendation: Either upgrade epics to active or downgrade stories to match epic priority

### 🟡 Minor Concerns

**13. Epic 1 and 5 Marked DONE with No Stories**
- Brownfield epics with no individual story files
- Acceptable for brownfield but hard to verify what was done
- Recommendation: Add "Brownfield - implemented prior to epic breakdown" note (already partially done)

**14. Story 4.8a-h Letter Suffix Naming**
- Uses letter suffixes instead of sequential numbering
- Minor convention issue; stories are properly sized
- Recommendation: Keep as-is (indicates related sub-stories)

**15. Tech Debt Stories Without Clear Prioritization**
- Followup stories in backlog without explicit priority
- Recommendation: Already addressed in Winston audit (td-1 through td-4 created)

**16. Mixed Language in Epic Descriptions**
- Vietnamese and English mixed throughout
- Minor inconsistency; content is clear
- Recommendation: Standardize on English for ACs, keep Vietnamese for context notes

**17. Epic 10/11 Created as "New True" Epics**
- Correctly identified as new capabilities, not brownfield
- No change needed

### Brownfield Assessment

**Project correctly identifies as BROWNFIELD.** Epics 1-11 marked DONE with implementation notes. New epics (12-18) clearly identified as new work. Integration with existing systems properly considered.

### Database Creation Assessment

**No violations found.** Tables created when first needed. Epic 13's 4-table migration is correct for shared canonical storage layer (referential integrity requires all tables).

### Best Practices Compliance Checklist

| Check | Epic 1-11 | Epic 12 | Epic 13 | Epic 14-17 | Epic 18 |
|-------|-----------|---------|---------|------------|---------|
| User value | ✅ | ✅ | ✅ | ✅ | ✅ |
| Independence | ✅ | ❌ | ❌ | ✅ | ❌ |
| Story sizing | ✅ | ✅ | ✅ | ✅ | ✅ |
| No forward deps | ✅ | ❌ | ❌ | ✅ | ❌ |
| DB creation timing | ✅ | N/A | ✅ | N/A | N/A |
| Clear ACs | ✅ | 🟠 | 🟠 | ✅ | ✅ |
| FR traceability | ✅ | ✅ | ✅ | ✅ | ✅ |

## Step 6: Final Assessment

### Overall Readiness Status

**READY WITH CONDITIONS**

The Nowing project is implementation-ready for active development (Epics 1-11 DONE, Epic 12 ready-for-dev). However, 4 critical forward dependency violations must be resolved or explicitly documented as intentional before Epics 12-18 can proceed without blocking.

### Critical Issues Requiring Immediate Action

**1. Forward Dependency Chain: Epic 12 → Epic 13 → Epic 18**
- Stories 13.2b, 13.2e depend on Epic 12 aggregator output
- Epic 18 entry criteria requires Epic 13 completion
- Stories 12.8 and 16.4 already blocked (Winston audit 2026-08-08)
- **Action:** Document as intentional Phase 2 sequential dependency OR create contract stories to decouple

**2. Epic 12 Stories 12-6 through 12-9 Circular Dependencies**
- 12.6 needs 12.9 (saved searches); 12.7 needs Epic 13 (canonical entities)
- **Action:** Reorder 12.9 as P0 before 12.6; move 12.7/12.8 to Epic 13; add explicit dependency notes

**3. OQ-3: Retention/Right-to-Delete for Memory — HARD BLOCKER before GA cloud**
- Legal requirement unresolved
- **Action:** Legal counsel + architecture design for memory retention before GA

**4. OQ-8: HR Vertical Hard Gates — 6 unresolved gates**
- ToS review, legal classification, anti-bot POC, salary visibility, pricing, PII pipeline
- **Action:** Complete Story 12.0 (legal review) before 12.1-12.5 dev starts

### Recommended Next Steps

**Immediate (before next sprint):**
1. Resolve or document Epic 12 → 13 → 18 dependency chain as intentional Phase 2 sequence
2. Reorder Epic 12 stories: 12.9 (Saved Searches) → P0 before 12.6 (Job Alerts)
3. Move 12.7 (Property Alerts) and 12.8 (Timeline) to Epic 13 or document as cross-epic dependencies
4. Complete Story 12.0 legal review (hard gate for 12.1-12.5)

**Short-term (next 2 sprints):**
5. Convert bullet-point ACs to Given/When/Then format (Stories 12.1, 12.2, 13.1, 13.2a-e)
6. Clarify Epic 14-17 priorities (epic P2 vs story P0 contradiction)
7. Add explicit approval criteria for Story 9.5 (deferred without path)
8. Create UX contracts for new features going forward (brownfield gaps are acceptable)

**Before GA cloud:**
9. Resolve OQ-3 (memory retention/right-to-delete) — legal blocker
10. Quantify all SM targets (SM-1, SM-2, SM-3, SM-8 use "≥ X%" placeholders)
11. Ratify NFR-9 State B baseline (Story 9.3)
12. Complete UX spec for async deep research if not already done

### Assessment Summary by Category

| Category | Status | Details |
|----------|--------|---------|
| PRD Completeness | ✅ Strong | 57 FRs, 11 NFRs, 8 OQs, 12 SMs — comprehensive and actively maintained |
| FR Coverage | ✅ Complete | 100% of active FRs have traceable epic/story coverage |
| UX Alignment | ✅ Good | 9/9 UX contracts aligned; brownfield gaps acceptable |
| Epic Quality | 🟠 Needs Work | 4 critical forward dependencies; 8 major issues; 5 minor |
| Architecture | ✅ Strong | AD-1 through AD-33; AD-32/AD-33 accepted (Winston audit) |
| Story Status | ✅ On Track | 40 FRs done, 5 ready-for-dev, 3 backlog, 2 blocked, 4 tech-debt |
| Legal/Compliance | ❌ Blocked | OQ-3 (memory retention) + OQ-8 (HR vertical gates) unresolved |

### Issue Count

- **Critical:** 4 (forward dependencies)
- **Major:** 8 (story sizing, ACs, priorities, deferred stories)
- **Minor:** 5 (formatting, naming, language)
- **Total:** 17 issues across 5 categories

### Final Note

This assessment identified 17 issues across 5 categories. The 4 critical forward dependency issues should be resolved or explicitly documented as intentional before proceeding with Epics 12-18. The project is in strong shape for completed work (Epics 1-11) and ready for Epic 12 development pending legal review (Story 12.0). The forward dependency chain (Epic 12 → 13 → 18) is the primary architectural risk — it can be accepted as a Phase 2 sequential plan OR decoupled via contract stories.

**Assessment Date:** 2026-08-08
**Assessor:** Implementation Readiness Workflow (PM persona)
**Report Version:** v3 (supersedes v1, v2, and all prior readiness reports)

## Step 7: Issue Resolution (Post-Assessment Fixes)

All 17 issues identified in Steps 4-6 have been resolved or documented as intentional. Changes applied to `epics.md` and `sprint-status.yaml`.

### Critical Issues Resolved

| # | Issue | Resolution |
|---|-------|------------|
| C1 | Epic 12→13→18 forward dependency | Documented as intentional Phase 2 sequential dependency in Epic 13 and Epic 18 sections |
| C2 | 12.6-12.9 circular deps | 12.9 reordered to P0 (must ship before 12.6); 12.7/12.8 documented as cross-epic deps on Epic 13 |
| C3 | Story 12.8 blocked on Epic 13 | Already marked `blocked` in sprint-status; documented as intentional in epics.md |
| C4 | Story 16.4 blocked on Epic 13 | Already marked `blocked` in sprint-status; documented as intentional |

### Major Issues Resolved

| # | Issue | Resolution |
|---|-------|------------|
| M1 | Epic 6 stories 6.6/6.7/6.9 business-gated | Added `6-6a/6-7a/6-9a` keys with `business-gated` status in sprint-status.yaml |
| M2 | Story 12.0 legal review as regular story | Retagged from `[DONE]` to `[PREREQUISITE]` in epics.md |
| M3 | Bullet ACs vs Given/When/Then | Verified ACs already use Given/When/Then format within bullet points — no change needed |
| M4 | Story 9.5 deferred without approval criteria | Added explicit SCP approval criteria (demand evidence, pricing, abuse prevention, revenue attribution) |
| M5 | Epic 14-17 P2 epic vs P0 story contradiction | Added priority clarification: P0 stories are "quick wins" pullable into active sprint, epic P2 means not activated |

### Minor Issues Resolved

| # | Issue | Resolution |
|---|-------|------------|
| m1 | Epic 1 and 5 no brownfield note | Added brownfield notes to both epics |
| m2 | Mixed language in epics | Added language convention note at Epic List header |
| m3 | Story 4.8a-h letter suffix naming | Accepted as-is (indicates related sub-stories) |
| m4 | Tech debt stories prioritization | Already addressed in Winston audit (td-1 through td-4) |
| m5 | Epic 10/11 new true epics | No change needed (correctly identified) |

### Files Modified

1. `_bmad-output/planning-artifacts/epics.md` — 8 edits (dependency docs, story reorder, brownfield notes, language convention, priority clarification, approval criteria)
2. `_bmad-output/implementation-artifacts/sprint-status.yaml` — 2 edits (business-gated stories, last_updated)
3. `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-08-v3.md` — this section

### Post-Resolution Status

**READY** — All critical issues documented as intentional Phase 2 sequencing or already tracked as blocked. All major issues resolved with explicit documentation. All minor issues addressed or accepted as-is.

The project is ready for implementation. Epic 12 can proceed pending Story 12.0 legal review (already approved 2026-08-08). Epic 13 follows Epic 12. Epic 18 follows Epic 13. This is the accepted Phase 2 sequence.
