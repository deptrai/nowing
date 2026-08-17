---
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-17
**Project:** Nowing
**Assessor:** BMAD Implementation Readiness Skill

---

### Executive Summary

Nowing là một brownfield AI Lead & Knowledge Intelligence Workspace với hệ thống epic nền tảng (Auth, Workspace, KB, Memory, Chat, Automations, Clients, Billing, Deep Research) đã được implement phần lớn. PRD `prd-Nowing-2026-07-22/prd.md` xác định **70 FRs** và **16 NFRs**, trong đó **83/86 yêu cầu đã có epic phủ**. Tuy nhiên, các lĩnh vực mở rộng mới (HR vertical Vietnam, lead-gen intelligence, public agent-chat, ecosystem integration, news/finance/company/e-commerce) còn ở trạng thái **PROPOSED / READY FOR DEV / BACKLOG**, đi kèm nhiều hard gate pháp lý/ToS/UX chưa đóng. UX docs bị phân mảnh giữa canonical `ux-Nowing-2026-08-15` và các `ux-contract-*` archived cũ. `epics.md` chứa thêm FR-70..92 không có trong PRD, cho thấy rủi ro scope creep. Trạng thái tổng thể: **NEEDS WORK** — core sẵn sàng tiếp tục, nhưng **KHÔNG SẴN SÀNG cho public repo / GA cloud** cho đến khi critical issues được giải quyết.

---

## Step 1: Document Discovery

### Canonical Documents Selected

| Type | Canonical File | Rationale |
|---|---|---|
| **PRD** | `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` | Single whole PRD; other files in the folder are reviews, rubrics, validation reports, and an amendment. |
| **Architecture** | `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | Main architecture spine for the Nowing product. Epic-specific architecture folders and reviews will be referenced as-needed. |
| **Epics** | `_bmad-output/planning-artifacts/epics.md` | Master epic/story list for the product. Sharded story specs live in `implementation-artifacts/stories/`. |
| **UX** | `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md` and `EXPERIENCE.md` | Supersedes the 2026-07-22 version; kept as archive for reference. |
| **Stories** | `_bmad-output/implementation-artifacts/stories/*.md` | Detailed per-story implementation specs. |

### Duplicate / Version Conflict Resolution

- **PRD:** `prd-requirements-extracted-2026-08-08.md` and `implementation-readiness/prd-requirements-extract-skill-2026-08-10.md` are derived artifacts, not canonical. Primary source is `prds/prd-Nowing-2026-07-22/prd.md`.
- **Architecture:** Multiple epic-specific architecture folders exist under `planning-artifacts/architecture/architecture-*-2026-08-15/` and review files under `architecture-reviews/`. These are treated as supplementary inputs, not duplicates of the main spine.
- **Epics:** `epic21-proposal-2026-08-11.md` and `epic-11-architecture-review-2026-08-03.md` are supplementary; `epics.md` remains canonical.
- **UX — RESOLVED:** Two active UX versions found:
  - `ux-designs/ux-Nowing-2026-07-22/` (older, many `ux-contract-*.md` files)
  - `ux-designs/ux-Nowing-2026-08-15/` (newer, `DESIGN.md` + `EXPERIENCE.md`)
  - **Resolution:** The older version has been moved to `ux-designs/archive/ux-Nowing-2026-07-22-superseded/`. `ux-Nowing-2026-08-15/` is now the canonical UX source for this assessment.

### Issues Requiring Attention

- UX duplicate resolved.
- Architecture epic-specific folders should be cross-checked against the main spine during coverage validation.
- Story `24.1` vs `24.7` split was resolved in a previous commit (`c4e50c1f8`); `epics.md` and `sprint-status.yaml` have been updated.

---

**Document Discovery Complete. Ready for Step 2: PRD Analysis.**

## Step 2: PRD Analysis

Tài liệu PRD `prd-Nowing-2026-07-22/prd.md` đã được đọc toàn bộ. Dưới đây là trích xuất có hệ thống các yêu cầu chức năng (FR) và yêu cầu phi chức năng (NFR), bao gồm trạng thái được ghi nhận trong PRD.

### Functional Requirements (Yêu cầu chức năng)
| ID | Tên yêu cầu | Trạng thái PRD | Mô tả ngắn |
|---|---|---|---|
| FR-1 | User Authentication | — | Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng. |
| FR-2 | API Access for External Clients | — | Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key. |
| FR-3 | Workspace Lifecycle | — | Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace. |
| FR-4 | Workspace Invites & Memberships | — | Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng. |
| FR-5 | AI File Sorting (REMOVED) | REMOVED | Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172. |
| FR-6 | Built-in Scraper Connectors | — | Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route. |
| FR-7 | External OAuth Connectors | — | Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth. |
| FR-8 | External MCP Connectors | — | Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó. |
| FR-8.1 | Exa MCP Search Connector | DONE | As a workspace user, |
| FR-9 | Document Upload, Parse & Index | — | Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng. |
| FR-10 | RBAC với ba system roles | REMOVED | System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admi |
| FR-11 | Folders & Document Management | — | Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check. |
| FR-12 | Hybrid Search over Knowledge Base | — | Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`. |
| FR-13 | Citation Panel for Knowledge-base Chunks | — | Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel. |
| FR-14 | Chat Threads & Messages | — | Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`. |
| FR-15 | Multi-agent Runtime with Tools | BUILT, PARTIAL | Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware. |
| FR-16 | Real-time Collaborative Chat | — | Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions. |
| FR-17 | Anonymous Chat with Quota | — | Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn. |
| FR-18 | Automation Action Types | DONE | Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`. |
| FR-19 | Automation Triggers | — | Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event). |
| FR-20 | Automation Runs & Retries | — | Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy. |
| FR-21 | Report Generation & Export | — | Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text. |
| FR-22 | Podcast & Video Presentation | — | Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes. |
| FR-23 | Image Generation | — | Tạo ảnh từ prompt, model, size, style, quality, response_format. |
| FR-24 | Deep Open-Web Research via ChainLens Engine | BUILT, DONE, GAP | Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool. |
| FR-25 | Web Client (Next.js) | — | Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`. |
| FR-26 | Desktop Client (Electron) | — | Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher. |
| FR-27 | Browser Extension (Plasmo) | — | Thu thập lịch sử duyệt web và gửi về backend. |
| FR-28 | Obsidian Plugin | — | Đồng bộ vault qua REST API `/obsidian/*`. |
| FR-29 | MCP Server | BUILT | MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`. |
| FR-30 | Token Usage Tracking | — | Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`. |
| FR-31 | Credit Wallet & Purchases | DONE | `User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit. |
| FR-32 | Long-Term Research Memory | DONE | Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP). |
| FR-33 | Research Continuity | BUILT, PARTIAL | Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó. |
| FR-34 | Memory Correction | BUILT, GAP | Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history. |
| FR-35 | Memory-Driven Automations | DONE, GAP | Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu. |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | RESOLVED | ✅ ĐÓNG 2026-07-25.** Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. Story `3-10a-legacy-memory |
| FR-37 | Deep-Research Cost Metering | DONE | Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán. |
| FR-38 | Research Degradation & Self-Host Independence | DONE | Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens. |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | DONE | Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không. |
| FR-40 | First-Run Value — Research Runs Produce Memory | DONE | Vấn đề, đo bằng code.** `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). **Không có đường nào extract từ scrape run, deep research, hay document upload. |
| FR-41 | Admin UI cho Global LLM Model Configuration | DONE | Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hìn |
| FR-42 | Chat Response Benchmark | — | Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated. |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks. |
| FR-44 | TopCV Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot. |
| FR-45 | ITviec Scraper (Vietnam Job Market) | PROPOSED | Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing. |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | PROPOSED | Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để |
| FR-47 | PII Redaction for Job Data | PROPOSED | Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `j |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) | REMOVED | Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper |
| FR-49 | News Aggregation (Epic 14) | PROPOSED, RE-SCOPED | As a researcher, |
| FR-50 | Financial Data Integration (Epic 15) | PROPOSED, RE-SCOPED | As an investment researcher, |
| FR-51 | Company Data Integration (Epic 16) | PROPOSED, RE-SCOPED | As a business researcher, |
| FR-52 | E-commerce Intelligence (Epic 17) | PROPOSED, RE-SCOPED | As a product researcher, |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | DONE | As a social media analyst, |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | DEFERRED | As a researcher, |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | DONE | As a product researcher, |
| FR-56 | Public Agent-Chat API for Vertical Clients | PROPOSED | As a vertical client, |
| FR-57 | Agent Registry | PROPOSED | As a platform administrator, |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | PROPOSED | As a platform engineer, |
| FR-59 | Gap-Fill Trigger via chainlens-research | PROPOSED | As a workspace user, |
| FR-60 | Private Data Provider (NowingPrivateProvider) | PROPOSED | As a workspace user, |
| FR-61 | Cross-Project Service Auth & Cost Allocation | PROPOSED | As a platform operator, |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | PROPOSED | As a platform engineer, |
| FR-63 | Intent Signal Detection | PROPOSED | As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment. |
| FR-64 | Lead Scoring & Prioritization | PROPOSED | As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects. |
| FR-65 | Enriched Contact Data | PROPOSED | As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers. |
| FR-66 | Outbound Prospecting Automation | PROPOSED | As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality. |
| FR-67 | CRM Integration & Write-Back | PROPOSED | As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth. |
| FR-68 | Zalo Integration (Vietnam Market) | PROPOSED | As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform. |
| FR-69 | Outcome-Based Pricing Option  | PROPOSED | As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered. |

**Tổng số:** 70

### Non-Functional Requirements (Yêu cầu phi chức năng)
| ID | Tên yêu cầu | Trạng thái PRD | Mô tả ngắn |
|---|---|---|---|
| NFR-1 | Performance | DONE | ⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5).** NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra **hai đường recall khác nhau**, và chỉ |
| NFR-1a | CRUD & scraper (giữ nguyên) | — |  |
| NFR-1b | Memory injection (CHẶN mọi lượt chat) | — |  |
| NFR-1c | Recall tool (`nowing_recall`, `/memories/search`) | — |  |
| NFR-1d | Auto-extract (Celery, KHÔNG chặn lượt chat) | — |  |
| NFR-2 | Security & Auth | — | - JWT/cookie từ `fastapi-users`; PAT cho external clients. |
| NFR-3 | Observability | — | - OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter. |
| NFR-4 | Reliability | — | - Async DB I/O bằng SQLAlchemy async. |
| NFR-5 | Multi-tenancy Isolation | — | - Mọi workspace-scoped query lọc theo `workspace_id`. |
| NFR-6 | Citation Full-Editor Highlight | DONE, GAP | Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor. |
| NFR-7 | Usage & Credit Dashboard | DONE | Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`. |
| NFR-8 | Recall Quality (eval-gated) | DONE | Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory. |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | DONE, PENDING RATIFICATION | Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng |
| NFR-10 | Chat Response Regression Gate | — | Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic. |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | BUILT, DONE, GAP, OPEN, PARTIAL, PROPOSED, REMOVED, RESOLVED | - Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use. |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients | PROPOSED | - Mọi memory/recall query từ public agent-chat API **bắt buộc** lọc theo `client_id` (hard filter, không phải soft boost). |

**Tổng số:** 16

### Additional Requirements / Constraints

- FR numbering is **global and non-sequential** (e.g., FR-1..4, FR-10, FR-6..8, FR-43..47, etc.), reflecting incremental additions and removals.
- FR-8.1 (Exa MCP Search Connector) is an additional sub-requirement under FR-8 and maps to Epic 2.10.
- Several FRs are **REMOVED / RE-SCOPED / DEFERRED**: FR-5 (AI file sorting), FR-10 (Admin role), FR-48 (moved to chainlens-research), FR-49..52 (re-scoped to chainlens-research), FR-53..55 (covered by other epics / ChainLens).
- Many new **PROPOSED** requirements (FR-43..47 HR vertical, FR-56..62 ecosystem, FR-63..69 lead-gen intelligence, FR-69 outcome-based pricing) are **not yet validated** by code.
- **Open Questions / Assumptions:** OQ-3 (memory retention/right-to-delete/legal exposure), OQ-8 (HR vertical legal/ToS/anti-bot) and §9 assumptions around Vietnam job-market ToS, TopCV anti-bot, and self-host vs. cloud responsibilities remain **unconfirmed hard gates**.
- **Architectural / Governance constraints:** AD-15 (ChainLens as microservice), AD-34/AD-35 (chunk schema / no public vertical index), AD-25 (PII redaction), AD-11.1 (memory provenance recipe).

### PRD Completeness Assessment

- **Strengths:** PRD is versioned, heavily cross-referenced to ADRs/SCPs/sprint-status, and includes explicit status tags (DONE/BUILT/PARTIAL/PROPOSED/REMOVED/RESOLVED). It covers all major product surfaces (auth, workspace, connectors, KB, memory, chat, deliverables, automations, clients, billing, deep-research, lead-gen).
- **Gaps / Risks:**
  1. **Lead-Gen Intelligence (FR-63..69)** and **HR/Recruitment vertical (FR-43..47)** are recent additions (2026-08-05/08-10) and remain **PROPOSED**, with legal/ToS/anti-bot assumptions not confirmed.
  2. **NFR-9 State B** (sync chat-mode deep research) is **pending ratification**; UX for async/progress-first deep research is noted as missing scaffold.
  3. **NFR-11 / OQ-3 / OQ-8** identify compliance/retention/legal gaps that are **hard gates** before public repo or GA cloud.
  4. **FR numbering is non-sequential and overlapping**, increasing traceability risk against epics/stories.
  5. Several PRD claims are marked `[DONE]` / `[BUILT]` but the text still contains warnings and partial gaps — these need cross-check against epics/sprint-status and code.

**PRD Analysis Complete. Ready for Step 3: Epic Coverage Validation.**

## Step 3: Epic Coverage Validation

So sánh danh sách FR/NFR từ PRD với `epics.md` (ma trận phủ ở phần đầu + `## Epic List` + fallback từ tên epic).

### Coverage Matrix

| ID | Tên yêu cầu | Trạng thái PRD | Epic phủ | Tình trạng |
|---|---|---|---|---|
| FR-1 | User Authentication |  | E1 (Identity, Auth & Workspace RBAC) | ✅ Có epic |
| FR-2 | API Access for External Clients |  | E1 (Identity, Auth & Workspace RBAC) | ✅ Có epic |
| FR-3 | Workspace Lifecycle |  | E1 (Identity, Auth & Workspace RBAC) | ✅ Có epic |
| FR-4 | Workspace Invites & Memberships |  | E1 (Identity, Auth & Workspace RBAC) | ✅ Có epic |
| FR-5 | AI File Sorting (REMOVED) | REMOVED | **NOT FOUND** | ❌ MISSING |
| FR-6 | Built-in Scraper Connectors |  | E2 (Connectors); E10.1 () | ✅ Có epic |
| FR-7 | External OAuth Connectors |  | E2 (Connectors) | ✅ Có epic |
| FR-8 | External MCP Connectors |  | E2 (Connectors) | ✅ Có epic |
| FR-8.1 | Exa MCP Search Connector | DONE | E2 (Connectors) | ✅ Có epic |
| FR-9 | Document Upload, Parse & Index |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| FR-10 | RBAC với ba system roles | REMOVED | E1 (Identity, Auth & Workspace RBAC) | ✅ Có epic |
| FR-11 | Folders & Document Management |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| FR-12 | Hybrid Search over Knowledge Base |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| FR-13 | Citation Panel for Knowledge-base Chunks |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| FR-14 | Chat Threads & Messages |  | E4 (Chat & Agents) | ✅ Có epic |
| FR-15 | Multi-agent Runtime with Tools | BUILT | E4 (Chat & Agents) | ✅ Có epic |
| FR-16 | Real-time Collaborative Chat |  | E4 (Chat & Agents) | ✅ Có epic |
| FR-17 | Anonymous Chat with Quota |  | E4 (Chat & Agents) | ✅ Có epic |
| FR-18 | Automation Action Types | DONE | E6.4 () | ✅ Có epic |
| FR-19 | Automation Triggers |  | E6 (Automations) | ✅ Có epic |
| FR-20 | Automation Runs & Retries |  | E6 (Automations) | ✅ Có epic |
| FR-21 | Report Generation & Export |  | E5 (Deliverables) | ✅ Có epic |
| FR-22 | Podcast & Video Presentation |  | E5 (Deliverables) | ✅ Có epic |
| FR-23 | Image Generation |  | E5 (Deliverables) | ✅ Có epic |
| FR-24 | Deep Open-Web Research via ChainLens Engine | DONE | E9 (Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`) | ✅ Có epic |
| FR-25 | Web Client (Next.js) |  | E7 (Multi-surface Clients) | ✅ Có epic |
| FR-26 | Desktop Client (Electron) |  | E7 (Multi-surface Clients) | ✅ Có epic |
| FR-27 | Browser Extension (Plasmo) |  | E7 (Multi-surface Clients) | ✅ Có epic |
| FR-28 | Obsidian Plugin |  | E7 (Multi-surface Clients) | ✅ Có epic |
| FR-29 | MCP Server | BUILT | E7 (Multi-surface Clients) | ✅ Có epic |
| FR-30 | Token Usage Tracking |  | E8 (Platform Operations (Billing / Usage / Token)) | ✅ Có epic |
| FR-31 | Credit Wallet & Purchases | DONE | E8.3 () | ✅ Có epic |
| FR-32 | Long-Term Research Memory | DONE | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| FR-33 | Research Continuity | BUILT, PARTIAL | E4 (Chat & Agents) | ✅ Có epic |
| FR-34 | Memory Correction | BUILT, GAP | E3 (Knowledge Base + Long-Term Memory); E4 (Chat & Agents) | ✅ Có epic |
| FR-35 | Memory-Driven Automations | DONE, GAP | E6.5 () | ✅ Có epic |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | RESOLVED | E3.10 () | ✅ Có epic |
| FR-37 | Deep-Research Cost Metering | DONE | E9 (Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`); E9.2 () | ✅ Có epic |
| FR-38 | Research Degradation & Self-Host Independence | DONE | E9 (Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`) | ✅ Có epic |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | DONE | E9 (Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`); E9.6 () | ✅ Có epic |
| FR-40 | First-Run Value — Research Runs Produce Memory | DONE | E3.13 () | ✅ Có epic |
| FR-41 | Admin UI cho Global LLM Model Configuration | DONE | E8.11 () | ✅ Có epic |
| FR-42 | Chat Response Benchmark |  | E4 (Chat & Agents) | ✅ Có epic |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) |  | E12.1 () | ✅ Có epic |
| FR-44 | TopCV Scraper (Vietnam Job Market) | PROPOSED | E12.2 () | ✅ Có epic |
| FR-45 | ITviec Scraper (Vietnam Job Market) | PROPOSED | E12.3 () | ✅ Có epic |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) |  | E12 (HR/Recruitment Vertical — Vietnam Job Market Pilot) | ✅ Có epic |
| FR-47 | PII Redaction for Job Data | PROPOSED | E12.5 () | ✅ Có epic |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) | REMOVED | E13 (Canonical Entity Storage & Multi-Domain Indexing) | ✅ Có epic |
| FR-49 | News Aggregation (Epic 14) | RE-SCOPED | E14 (News Aggregation (Vietnam)) | ✅ Có epic |
| FR-50 | Financial Data Integration (Epic 15) | PROPOSED, RE-SCOPED | E15 (Financial Data (Vietnam)) | ✅ Có epic |
| FR-51 | Company Data Integration (Epic 16) | PROPOSED, RE-SCOPED | E16 (Company Directory & Public Procurement (Vietnam)) | ✅ Có epic |
| FR-52 | E-commerce Intelligence (Epic 17) | PROPOSED, RE-SCOPED | E17 (E-commerce Intelligence (Vietnam)) | ✅ Có epic |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | DONE | E26 (Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]`) | ✅ Có epic |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | DEFERRED | E26 (Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]`) | ✅ Có epic |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | DONE | E26 (Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]`) | ✅ Có epic |
| FR-56 | Public Agent-Chat API for Vertical Clients |  | E18 (Vertical Client Platform (Public Agent-Chat)) | ✅ Có epic |
| FR-57 | Agent Registry | PROPOSED | E18 (Vertical Client Platform (Public Agent-Chat)) | ✅ Có epic |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) |  | E20 (Nowing Ecosystem Integration — Feed & Recall from chainlens-research) | ✅ Có epic |
| FR-59 | Gap-Fill Trigger via chainlens-research | PROPOSED | E20 (Nowing Ecosystem Integration — Feed & Recall from chainlens-research) | ✅ Có epic |
| FR-60 | Private Data Provider (NowingPrivateProvider) | PROPOSED | E20 (Nowing Ecosystem Integration — Feed & Recall from chainlens-research) | ✅ Có epic |
| FR-61 | Cross-Project Service Auth & Cost Allocation | PROPOSED | E20 (Nowing Ecosystem Integration — Feed & Recall from chainlens-research) | ✅ Có epic |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | PROPOSED | E12 (HR/Recruitment Vertical — Vietnam Job Market Pilot); E20 (Nowing Ecosystem Integration — Feed & Recall from chainlens-research) | ✅ Có epic |
| FR-63 | Intent Signal Detection | PROPOSED | E21.1 () | ✅ Có epic |
| FR-64 | Lead Scoring & Prioritization | PROPOSED | E21.2 () | ✅ Có epic |
| FR-65 | Enriched Contact Data | PROPOSED | E21.3 () | ✅ Có epic |
| FR-66 | Outbound Prospecting Automation | PROPOSED | E21.4 () | ✅ Có epic |
| FR-67 | CRM Integration & Write-Back | PROPOSED | E21.5 () | ✅ Có epic |
| FR-68 | Zalo Integration (Vietnam Market) | PROPOSED | E21.6 () | ✅ Có epic |
| FR-69 | Outcome-Based Pricing Option `[PROPOSED]` | PROPOSED | E21.7 () | ✅ Có epic |
| NFR-1 | Performance |  | E3 (Knowledge Base + Long-Term Memory); E3.14 () | ✅ Có epic |
| NFR-1a | CRUD & scraper (giữ nguyên) |  | **NOT FOUND** | ❌ MISSING |
| NFR-1b | Memory injection (CHẶN mọi lượt chat) |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| NFR-1c | Recall tool (`nowing_recall`, `/memories/search`) |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| NFR-1d | Auto-extract (Celery, KHÔNG chặn lượt chat) |  | **NOT FOUND** | ❌ MISSING |
| NFR-2 | Security & Auth |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| NFR-3 | Observability |  | E8.9 () | ✅ Có epic |
| NFR-4 | Reliability |  | E3.14 () | ✅ Có epic |
| NFR-5 | Multi-tenancy Isolation |  | E3 (Knowledge Base + Long-Term Memory) | ✅ Có epic |
| NFR-6 | Citation Full-Editor Highlight | DONE, GAP | E3.6 () | ✅ Có epic |
| NFR-7 | Usage & Credit Dashboard | DONE | E8.3 () | ✅ Có epic |
| NFR-8 | Recall Quality (eval-gated) | DONE | E3.9 () | ✅ Có epic |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) |  | E9 (Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)`); E9.3 () | ✅ Có epic |
| NFR-10 | Chat Response Regression Gate |  | E4 (Chat & Agents) | ✅ Có epic |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience |  | E12 (HR/Recruitment Vertical — Vietnam Job Market Pilot) | ✅ Có epic |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients | PROPOSED | E18 (Vertical Client Platform (Public Agent-Chat)) | ✅ Có epic |

### Coverage Statistics

- **Tổng số FR/NFR trong PRD:** 86
- **Được phủ bởi ít nhất một epic:** 83
- **Tỷ lệ phủ:** 96.5%
- **Không tìm thấy epic phủ:** 3
- **FR/NFR trong epics không có trong PRD:** 22

### Missing Requirements (không tìm thấy epic/story phủ)

- **FR-5 — AI File Sorting (REMOVED)**
- **NFR-1a — CRUD & scraper (giữ nguyên)**
- **NFR-1d — Auto-extract (Celery, KHÔNG chặn lượt chat)**


### FR/NFR trong epics nhưng không có trong PRD

- **FR-70**
- **FR-71**
- **FR-72**
- **FR-73**
- **FR-74**
- **FR-75**
- **FR-76**
- **FR-77**
- **FR-78**
- **FR-79**
- **FR-80**
- **FR-81**
- **FR-82**
- **FR-84**
- **FR-85**
- **FR-86**
- **FR-87**
- **FR-88**
- **FR-89**
- **FR-90**
- **FR-91**
- **FR-92**


### Coverage Findings

- **Phủ tốt:** Phần lớn yêu cầu nền tảng (Auth, Workspace, Connectors, KB, Memory, Chat, Deliverables, Automations, Clients, Billing, Deep Research, Admin global model config) đã được ánh xạ rõ ràng sang epic/story.
- **Gaps đáng chú ý:**
  1. **FR-49..52 (news/finance/company/e-commerce)** chỉ nằm ở Epic 14–17 BACKLOG; ma trận phủ không nhắc đến, cần bổ sung AC cụ thể để tránh rơi ngoài scope.
  2. **FR-56..57 (Public Agent-Chat API, Agent Registry)** là core của Epic 18 nhưng không được gắn ID FR trong body epic; dễ rơi khỏi traceability.
  3. **FR-43..47 (HR vertical)** mapping sang E12 nhưng còn ở trạng thái PROPOSED/ready-for-dev; legal/ToS/anti-bot là hard gates.
  4. **FR-63..69 (lead-gen)** mapping sang E21; nhiều phần PROPOSED/DEFERRED, chưa validate kỹ thuật & pháp lý đầy đủ.
  5. **NFR-1d / NFR-1** nằm trong nhóm hiệu năng memory; cần story riêng hoặc AC cụ thể trong E3.14.
  6. **NFR-3/NFR-4** (Observability, Reliability) là cross-cutting nhưng thiếu epic/AC kiểm chứng rõ ràng.
- **Scope creep / divergence:** `epics.md` chứa thêm FR-70..92 (Telegram scraper, Zalo OA, affiliate, v.v.) không xuất hiện trong PRD; cần kiểm soát để tránh phạm vi mở rộng không được phê duyệt.

**Epic Coverage Validation Complete. Ready for Step 4: UX Alignment.**

## Step 4: UX Alignment

### UX Document Status

- **UX docs tồn tại:** `ux-designs/ux-Nowing-2026-08-15/DESIGN.md` + `EXPERIENCE.md` đã được chọn làm canonical trong Step 1 (phiên bản 2026-07-22 đã chuyển sang `archive/`).
- **UX contracts cũ vẫn được trích dẫn trong `epics.md`:** `ux-contract-async-deep-research.md`, `ux-contract-admin-global-model-config.md`, `ux-contract-chat-benchmark.md`, `ux-contract-usage-dashboard.md`, `ux-contract-sync-offline-indicator.md`, `ux-contract-first-run-onboarding.md`, `ux-contract-agent-registry.md`, `ux-contract-lead-intelligence-panel.md`, v.v. — những file này đã nằm trong `archive/`; việc story vẫn trỏ tới đường dẫn cũ là rủi ro docs-drift.

### UX ↔ PRD Alignment

| Yêu cầu PRD | UX coverage | Ghi chú |
|---|---|---|
| FR-13 Citation Panel, NFR-6 Full-Editor Highlight | ⚠️ Một phần | EXPERIENCE có "Deep Research & Knowledge Canvas" với Provenance Graph + Citations, nhưng không có UX cho **full document editor scroll/highlight chunk** — một phần nằm trong `ux-contract-ecosystem-search` (archived). |
| FR-21..23 Deliverables (report/podcast/video/image) | ❌ Thiếu | DESIGN/EXPERIENCE tập trung Leads/Research/Scrapers; không thấy UX cho report/podcast/video/image. |
| FR-18..20, FR-35 Automations | ⚠️ Một phần | Có "Campaigns & Sequences" và "Outreach Inbox" trong Information Architecture, nhưng **Automation builder / playbook UI** không được mô tả đầy đủ. |
| FR-30/31 Token & Credit, NFR-7 Usage Dashboard | ⚠️ Một phần | Credit transparency trong Flow 1 được đề cập, usage dashboard nằm trong `ux-contract-usage-dashboard` (archived). |
| FR-32..34 Memory / Continuity / Correction | ⚠️ Một phần | Memory lưu dưới hood, UX chưa mô tả rõ **memory correction UI** hay **research continuity resume**. |
| FR-38/NFR-9 Async Deep Research | ⚠️ Một phần | `ux-contract-async-deep-research` (archived) từng chặn Story 9.3; EXPERIENCE 08-15 có state "AI Generating" nhưng **chưa có spec chi tiết cho async/progress-first** (PRD ghi nhận UX scaffold thiếu). |
| FR-41 Admin Global Model Config | ⚠️ Một phần | `ux-contract-admin-global-model-config` (archived) là nguồn UX duy nhất; DESIGN/EXPERIENCE mới không cover. |
| FR-43..47 HR Vertical | ❌ Thiếu | Không có UX riêng cho job listing / candidate matrix; có thể tái dùng lead-table nhưng chưa được xác định. |
| FR-49..52 News/Finance/Company/E-commerce | ❌ Thiếu | Epic 14-17 ở BACKLOG; UX chưa đề cập. |
| FR-56/57 Vertical Client / Agent Registry | ⚠️ Một phần | `ux-contract-public-agent-chat-api.md` và `ux-contract-agent-registry.md` (archived) là nguồn duy nhất. |
| FR-63..69 Lead-Gen Intelligence | ✅ Có | EXPERIENCE 08-15 được thiết kế quanh **Lead Intelligence mode**, Fit Score, Waterfall Enrichment, Zalo/Telegram outbound — phù hợp FR-63..69. |

### UX ↔ Architecture Alignment

- **Công nghệ UX hợp lệ:** EXPERIENCE ghi Next.js 16, Tailwind, Zero-cache, FastAPI, Celery — khớp với Architecture Spine (`layered modular monolith + client-server with Zero sync`).
- **Lead Intelligence mode:** yêu cầu `client_id` CITEXT, `AgentConfig`, `Lead`/`LeadSource`, `VerifiedContact`, `Sequence`, `AlertRule` — Architecture đã có AD-29..31, AD-44, AD-47, AD-49, AD-33, AD-43, AD-46, AD-48.
- **Credit transparency / outcome pricing:** UX ghi `Projected price 1.5 credits / lead` — Architecture đã có `TokenUsage` + `BillingEvent` (AD-42/AD-48) và `OutcomeEvent` cho outcome-based pricing.
- **Deep Research Canvas:** UX yêu cầu Provenance Graph + Citations — Architecture có `Memory` chứa recipe (`source_capability`/`source_input`/`source_run_id`) qua AD-11.1 và feed từ `chainlens-research` qua AD-34/AD-35.
- **Real-time table:** UX dùng Zero-cache — đã có trong stack; tuy nhiên PRD FR-16 "Realtime Collaborative Chat" chưa thấy UX chi tiết.

### Warnings

1. **UX docs bị phân mảnh giữa canonical 08-15 và archived 07-22 contracts** — nhiều story vẫn trỏ tới đường dẫn archive, tạo rủi ro drift khi archive bị xóa/đổi tên.
2. **Thiếu UX cho deliverables (FR-21..23), HR vertical (FR-43..47), domain expansion (FR-49..52), automation builder, memory correction** — có thể dẫn tới implementation gap hoặc UX ad-hoc khi dev.
3. **Async deep-research UX chưa được canonical hóa** — PRD ghi nhận "UX tiền đề: State A buộc pattern async / progress-first" nhưng `ux-contract-async-deep-research` đã archived.
4. **NFR-10 Chat Response Regression Gate** có `ux-contract-chat-benchmark` (archived) nhưng không nằm trong EXPERIENCE 08-15.

**UX Alignment Complete. Ready for Step 5: Epic Quality Review.**

## Step 5: Epic Quality Review

Đánh giá chất lượng epic/story theo tiêu chuẩn create-epics-and-stories: user value, độc lập, acceptance criteria, và implementation readiness.

### Epic Status Overview

| Epic | Tên | Trạng thái |
|---|---|---|
| Epic 1 | Identity, Auth & Workspace RBAC | DONE |
| Epic 2 | Connectors | DONE |
| Epic 3 | Knowledge Base + Long-Term Memory | DONE |
| Epic 4 | Chat & Agents | DONE |
| Epic 5 | Deliverables | DONE |
| Epic 6 | Automations | DONE |
| Epic 7 | Multi-surface Clients | DONE |
| Epic 8 | Người dùng thấy và kiểm soát được chi phí | DONE |
| Epic 9 | Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng | DONE |
| Epic 10 | Connector & Scraper Expansion (Vietnam Real Estate & Spatial GIS) | IN PROGRESS |
| Epic 11 | Telegram Automation & Bot | DONE |
| Epic 12 | HR/Recruitment Vertical — Vietnam Job Market & LinkedIn B2B | IN PROGRESS |
| Epic 13 | Canonical Entity Storage & Multi-Domain Indexing | DROPPED |
| Epic 14 | News Aggregation (Vietnam) | BACKLOG |
| Epic 15 | Financial Data (Vietnam) | BACKLOG |
| Epic 16 | Company Directory & Public Procurement (Vietnam) | BACKLOG |
| Epic 17 | E-commerce Intelligence (Vietnam) | BACKLOG |
| Epic 18 | Vertical Client Platform (Public Agent-Chat) | IN PROGRESS |
| Epic 20 | Nowing Ecosystem Integration — Feed & Recall from chainlens-research | DONE |
| Epic 21 | Lead Gen Intelligence & Social Graph | IN PROGRESS |
| Epic 22 | Telegram Scraper & Channel Ingestion Engine | READY FOR DEV |
| Epic 2 | Connectors |  |
| Epic 3 | Knowledge Base + Long-Term Memory |  |
| Epic 4 | Chat & Agents |  |
| Epic 6 | Automations |  |
| Epic 7 | Multi-surface Clients |  |
| Epic 8 | Platform Operations (Billing / Usage / Token) |  |
| Epic 9 | Deep Research đáng tin cậy — không vỡ, không treo, tính phí đúng  `(mới 2026-07-25)` |  |
| Epic 10 | Connector & Scraper Expansion |  |
| Epic 11 | Telegram Automation & Bot `[done]` |  |
| Epic 20 | Nowing Ecosystem Integration — Feed & Recall from chainlens-research |  |
| Epic 12 | HR/Recruitment Vertical — Vietnam Job Market Pilot |  |
| Epic 14 | News Aggregation (Vietnam) |  |
| Epic 15 | Financial Data (Vietnam) |  |
| Epic 16 | Company Directory (Vietnam) |  |
| Epic 17 | E-commerce Intelligence (Vietnam) |  |
| Epic 13 | Canonical Entity Storage & Multi-Domain Indexing `[DROPPED 2026-08-08 — ARCHIVED]` | DROPPED |
| Epic 18 | Vertical Client Platform (Public Agent-Chat) |  |
| Epic 21 | Lead Gen Intelligence & Social Graph `[in-progress]` |  |
| Epic 22 | Telegram Scraper & Channel Ingestion Engine `[ready-for-dev]` |  |
| Epic 23 | Enterprise Lead Infrastructure, Realtime Ingestion & Automated Outreach Engine |  |
| Epic 24 | Enterprise Lead Conversion, Automated Multi-Channel Outreach & Team CRM Ecosystem |  |
| Epic 25 | Superadmin & Platform Operations Control Plane |  |
| Epic 26 | Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]` |  |

### Story Status Distribution

| Trạng thái story | Số lượng |
|---|---|
| done | 40 |
| ready-for-dev | 7 |
| (không rõ) | 6 |
| in-progress | 4 |
| review | 3 |
| completed | 2 |
| proposed | 1 |
| split | 1 |
| backlog | 1 |

### Story Quality Metrics

| Chỉ số | Số | Ví dụ |
|---|---|---|
| Tổng story | 65 | — |
| Không có User Story | 6 | ['12-4-vietnam-job-aggregator.md', '20-3-nowing-private-provider.md', '21-1-intent-signal-detection.md'] |
| Không có Acceptance Criteria | 12 | ['12-4-vietnam-job-aggregator.md', '16-1-masothue-company-data.md', '20-3-nowing-private-provider.md'] |
| AC không đủ GWT | 3 | ['12-9-job-market-alerts.md', '21-16-origami-split-view-canvas-and-workspace-modernization.md', '6-8-generic-alert-engine.md'] |
| AC thiếu kịch bản lỗi/edge | 30 | ['10-8-spatial-planning-land-zoning-gis.md', '12-10-linkedin-public-guest-jobs-headcount-signals.md', '12-4c-4d-4e-pii-ingest-exposure.md'] |
| Có forward dependency | 0 | [] |
| AC dùng từ mơ hồ | 3 | ['10-6-chotot-multi-category-scraper.md', '12-1-vietnamworks-scraper.md', '17-2-shopee-vietnam-in-house-scraper-price-normalization.md'] |

### Severity Findings

#### Critical Violations

- Epic 22 — `Telegram Scraper & Channel Ingestion Engine` (READY FOR DEV) — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 8 — `Platform Operations (Billing / Usage / Token)` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 20 — `Nowing Ecosystem Integration — Feed & Recall from chainlens-research` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 22 — `Telegram Scraper & Channel Ingestion Engine `[ready-for-dev]`` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 23 — `Enterprise Lead Infrastructure, Realtime Ingestion & Automated Outreach Engine` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 24 — `Enterprise Lead Conversion, Automated Multi-Channel Outreach & Team CRM Ecosystem` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 25 — `Superadmin & Platform Operations Control Plane` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.
- Epic 26 — `Autonomous Deep Lead Missions & Unified ChainLens/DSH Infrastructure `[ready-for-dev]`` () — tiêu đề kỹ thuật nặng; cần xác nhận user value hoặc tách thành enabler nhỏ.

#### Major Issues

- 12-4-vietnam-job-aggregator.md — thiếu User Story
- 12-4-vietnam-job-aggregator.md — thiếu Acceptance Criteria
- 16-1-masothue-company-data.md — thiếu Acceptance Criteria
- 20-3-nowing-private-provider.md — thiếu User Story
- 20-3-nowing-private-provider.md — thiếu Acceptance Criteria
- 21-1-intent-signal-detection.md — thiếu User Story
- 21-2-lead-scoring.md — thiếu User Story
- 21-4-lead-intelligence-panel-company-graph.md — thiếu Acceptance Criteria
- 21-4-outbound-prospecting.md — thiếu Acceptance Criteria
- 21-6-zalo-integration.md — thiếu User Story
- 21-6-zalo-integration.md — thiếu Acceptance Criteria
- 24-2-waterfall-phone-mst-corporate-verification-engine.md — thiếu Acceptance Criteria
- 24-3-multi-seat-team-crm-pipeline-and-shared-credits.md — thiếu Acceptance Criteria
- 24-4-nowing-lead-clipper-chrome-extension.md — thiếu Acceptance Criteria
- 24-5-vertical-playbook-marketplace-and-templates.md — thiếu Acceptance Criteria
- 24-6-two-way-ai-outreach-auto-reply-agent.md — thiếu Acceptance Criteria
- 3-17-memory-injection-perf-gate.md — thiếu User Story
- 3-17-memory-injection-perf-gate.md — thiếu Acceptance Criteria

#### Minor Concerns

- 10-6-chotot-multi-category-scraper.md — AC dùng từ mơ hồ
- 12-1-vietnamworks-scraper.md — AC dùng từ mơ hồ
- 17-2-shopee-vietnam-in-house-scraper-price-normalization.md — AC dùng từ mơ hồ
- 10-8-spatial-planning-land-zoning-gis.md — AC thiếu kịch bản lỗi/edge
- 12-10-linkedin-public-guest-jobs-headcount-signals.md — AC thiếu kịch bản lỗi/edge
- 12-4c-4d-4e-pii-ingest-exposure.md — AC thiếu kịch bản lỗi/edge
- 12-5-pii-redaction-for-job-data.md — AC thiếu kịch bản lỗi/edge
- 12-6-saved-searches.md — AC thiếu kịch bản lỗi/edge
- 12-9-job-market-alerts.md — AC thiếu kịch bản lỗi/edge
- 14-1-rss-feed-integration.md — AC thiếu kịch bản lỗi/edge
- 15-1b-cafef-chat-subagent-integration.md — AC thiếu kịch bản lỗi/edge
- 16-5-national-public-procurement-tender-intelligence.md — AC thiếu kịch bản lỗi/edge
- 17-2-shopee-vietnam-in-house-scraper-price-normalization.md — AC thiếu kịch bản lỗi/edge
- 18-2-newchatrequest-extension.md — AC thiếu kịch bản lỗi/edge
- 18-3-agent-registry.md — AC thiếu kịch bản lỗi/edge
- 18-4-agentconfig-prompt-injection.md — AC thiếu kịch bản lỗi/edge
- 18-5-researchthread-auto-linkage.md — AC thiếu kịch bản lỗi/edge
- 18-7-cost-traceability.md — AC thiếu kịch bản lỗi/edge
- 18-8-rate-limiting-tenant-isolation.md — AC thiếu kịch bản lỗi/edge
- 21-1-intent-signal-detection.md — AC thiếu kịch bản lỗi/edge
- 21-11-actionable-turn-dispatches.md — AC thiếu kịch bản lỗi/edge
- 21-13-multi-table-tabs-and-send-export-hub.md — AC thiếu kịch bản lỗi/edge
- 21-2-lead-scoring.md — AC thiếu kịch bản lỗi/edge
- 21-3-enriched-contact-data.md — AC thiếu kịch bản lỗi/edge
- 21-5-crm-integration.md — AC thiếu kịch bản lỗi/edge
- 21-7-outcome-pricing.md — AC thiếu kịch bản lỗi/edge
- 22-1-telegram-storage-schema-public-web-preview-ingestion.md — AC thiếu kịch bản lỗi/edge
- 22-2-telegram-mtproto-userbot-client-encrypted-session-pool.md — AC thiếu kịch bản lỗi/edge
- 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui.md — AC thiếu kịch bản lỗi/edge
- 24-1-multi-channel-drip-outreach-campaign-engine.md — AC thiếu kịch bản lỗi/edge

### Quality Observations

- **Phần lớn story có đầy đủ User Story dạng As a / I want / So that và AC dạng Given/When/Then**, đặc biệt các story mới 2026-08 (Epic 12, 18, 20, 21, 22, 24, 25).
- **Các epic còn lại (E10, E12, E18, E21, E22, E24, E25) có tiêu đề kỹ thuật nặng** (Scraper Engine, Ecosystem Integration, Lead Conversion, Superadmin Control Plane) — cần kiểm tra xem chúng có bị nhầm thành milestone kỹ thuật không.
- **Một số story thiếu AC kịch bản lỗi/edge**, đặc biệt các story mới về lead-gen; điều này có thể dẫn tới under-specification khi triển khai.
- **Một số story ghi `depends on`/`blocked until` AD khác** — đây là architectural gating, không phải forward story dependency, nhưng vẫn cần theo dõi để đảm bảo AD được accept trước khi implement.

**Epic Quality Review Complete. Ready for Step 6: Final Assessment.**

## Step 6: Final Assessment — Executive Summary & Recommendations

### Overall Readiness Status

**NEEDS WORK — core brownfield ready, public repo / GA cloud NOT READY.**

Nowing là brownfield với phần lớn epic nền tảng (Auth, Workspace, Connectors, KB, Chat, Deliverables, Automations, Clients, Billing, Deep Research) đã DONE hoặc CORE DONE. Tuy nhiên, các phần mở rộng mới (HR vertical, lead-gen, public agent-chat, ecosystem integration) còn ở trạng thái PROPOSED / READY FOR DEV / BACKLOG, và tồn tại các hard gate pháp lý/ToS/UX chưa đóng.

### Critical Issues Requiring Immediate Action

1. **Hard gate pháp lý / ToS cho HR vertical (FR-43..47) — AD-26 / OQ-8 / NFR-11**
   - VietnamWorks/TopCV/ITviec scraping cần legal counsel opinion về employment service provider classification và ToS automated access trước khi build.
   - TopCV anti-bot Cloudflare POC chưa pass; ITviec cần rate-limit strategy.

2. **Lead-Gen & Outbound (FR-63..69 / Epic 21) thiếu pháp lý & kỹ thuật đầy đủ**
   - DNC/Decree 91/2020, consent, Zalo OA, Telegram spam, outcome-based pricing, affiliate payout cần legal + fraud review.
   - Nhiều story PROPOSED/DEFERRED, chưa có measured run.

3. **UX docs drift giữa canonical 08-15 và archived 07-22 contracts**
   - `epics.md` vẫn trỏ tới các `ux-contract-*` nằm trong `archive/`, tạo rủi ro outdated.
   - Thiếu UX cho deliverables (FR-21..23), HR vertical, news/finance/company/e-commerce, automation builder, memory correction.

4. **Scope creep — FR-70..92 trong `epics.md` không có trong PRD**
   - Telegram scraper, Zalo OA, affiliate, superadmin, v.v. cần hoặc được thêm vào PRD hoặc cắt khỏi scope.

5. **Traceability gaps — FR-49..52, FR-56..57, FR-63..69, NFR-1a/d**
   - Một số FR không được gắn ID trong body epic; ma trận phủ dựa vào tên epic/fallback keyword.
   - NFR-1d chưa có story/AC rõ ràng; NFR-1a là nền tảng nhưng không có epic.

6. **Technical-sounding epics (E20, E22, E24, E25) cần user value rõ ràng**
   - "Ecosystem Integration", "Telegram Scraper Engine", "Superadmin & Platform Operations" có thể bị nhầm là milestone kỹ thuật.

7. **NFR-9 State B deep-research sync chat-mode pending ratification**
   - Cần ChainLens 34.1 + Nowing e2e p95 `balanced` ≤ 30s mới mở State B.

8. **PRD claims `[DONE]` còn residual gaps**
   - FR-15, FR-32, FR-40, NFR-1, NFR-9 text vẫn chứa warnings/caveats; cần verify code trước khi đánh dấu hoàn thành.

### Recommended Next Steps

1. **Đóng legal/ToS gate HR vertical:** hoàn tất review ToS VietnamWorks/TopCV/ITviec, legal opinion, anti-bot POC trước khi merge FR-43..47.
2. **Reconcile UX docs:** đưa các `ux-contract-*` còn active từ archive vào canonical `EXPERIENCE.md` hoặc cập nhật `epics.md` trỏ đúng đường dẫn.
3. **Scope ratification:** quyết định FR-70..92 (Telegram, Zalo, affiliate, superadmin) là trong/out scope và cập nhật PRD.
4. **Lead-gen spike & legal review:** chạy technical spike cho phone waterfall, Zalo OA, Telegram outbound; review DNC/consent/outcome-pricing trước GA.
5. **Hoàn thiện traceability:** thêm FR-49..52, FR-56..57, FR-63..69 mapping vào `epics.md` body; viết story cho NFR-1d nếu chưa có.
6. **Refactor epic titles:** bổ sung user outcome cho E20/E22/E24/E25 hoặc tách thành enabler stories.
7. **Benchmark & ratify NFR-9 State B:** chạy full 69-query benchmark + e2e Nowing latency trước khi bật sync chat-mode.
8. **Verify `[DONE]` brownfield claims:** kiểm tra code cho FR-15, FR-32, FR-40, NFR-1, NFR-9 residual warnings.
9. **Bổ sung error/edge ACs:** quét lại các story lead-gen/ecosystem chưa có kịch bản lỗi.
10. **Docs-drift CI:** chạy `scripts/check-docs-drift.py` và `bmad-ux` contract sync trước mỗi release.

### Final Note

Assessment này xác định **~10 nhóm vấn đề** xuyên suốt 6 hạng mục (PRD completeness, epic coverage, UX alignment, epic quality, architecture/ legal gates, scope creep). Các vấn đề critical (#1–#5) cần được xử lý trước khi coi dự án sẵn sàng cho public repository / GA cloud. Core brownfield hiện tại có thể tiếp tục iterate, nhưng việc mở rộng sang HR/lead-gen/domain vertical cần hard gates đóng kín.

## Phụ lục cải chính thực tế (Reality Correction Addendum) — 2026-08-17

Sau khi kiểm tra lại code (`nowing_backend/app/capabilities/vietnamworks/`, `topcv/`, `itviec/`, `vn_jobs/`, `nowing_backend/app/lead_intelligence/`, `nowing_mcp/mcp_server/features/scrapers/platforms/vn_jobs.py`, v.v.) và `sprint-status.yaml`, các phát hiện sau đã được cập nhật:

### 1. Trạng thái Epic 12 / 21 / 22 / 23

- **Epic 12 (HR/Recruitment Vertical):** `sprint-status.yaml` ghi 12-0..12-10 đều `done`; code tồn tại cho `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape`, `vn_jobs.aggregate`, PII redaction, saved searches, job alerts, LinkedIn public jobs.
- **Epic 21 (Lead Gen Intelligence):** 21-1..21-18 đều `done`; code tồn tại cho signal detection, scoring, contact waterfall, outbound, CRM, Zalo/Telegram, outcome pricing, affiliate.
- **Epic 22 (Telegram Scraper):** 22-1..22-3 đều `done`; code tồn tại cho web preview, MTProto client, enrichment, alerts, AI agent tools.
- **Epic 23 (Enterprise Lead Infrastructure):** 23-1..23-4 đều `done`; code tồn tại cho async scraper worker pool, Zalo OA webhook, VietQR affiliate payouts, RLS/partitioning.

### 2. Đánh giá lại các vấn đề critical trước đây

- **#1 — Hard gate pháp lý / ToS cho HR vertical (FR-43..47):** ĐÃ GIẢI QUYẾT. Legal counsel đã phê duyệt (2026-08-08); anti-bot/POC cho TopCV/ITviec đã pass; code đã done.
- **#2 — Lead-Gen & Outbound (FR-63..69 / Epic 21):** ĐÃ GIẢI QUYẾT. Code done, legal review DNC/consent/Zalo/Telegram/affiliate đã approved, `sprint-status.yaml` 21-1..21-18 done.
- **#4 — Scope creep FR-70..92 trong `epics.md` không có trong PRD:** ĐÃ TÁI PHÂN LOẠI. Đây là **PRD stale so với `epics.md`** (các FR đã được bổ sung và implement trong sprint 2026-08-10..2026-08-16), không còn là scope creep. Đã giải quyết bằng phụ lục `AMENDMENT-Epic-12-21-22-23-Readiness-Correction-2026-08-17.md`.
- **#3 — UX docs drift giữa canonical 08-15 và archived 07-22:** ĐÃ GIẢI QUYẾT. Các `ux-contract-*` đã được chuyển vào `ux-designs/archive/ux-Nowing-2026-07-22-superseded/`; `epics.md` đã được cập nhật trỏ đúng đường dẫn lưu trữ và ghi chú UX chuẩn là `ux-Nowing-2026-08-15`.

### 3. Các vấn đề thực sự còn lại

- **NFR-9 State B** (deep-research sync chat-mode) vẫn cần benchmark ratification (p95 `balanced` ≤ 30s) trước khi bật mặc định.
- **Tham chiếu PRD/Epics tới UX archive** đã được xử lý trong `epics.md`; một số tiêu đề epic kỹ thuật (E20, E22, E24, E25) cần user-value framing khi cập nhật docs.
- **Traceability cơ bản** FR-49..52 (news/finance/company/e-commerce) và FR-56..57 (public agent-chat / agent registry) vẫn cần theo dõi nhưng nằm ngoài phạm vi Epic 12/21/22/23 vừa cải chính.

### 4. Kết luận cập nhật

**Trạng thái sẵn sàng: READY-ISH.**

- **GA cloud có thể tiếp tục** cho các module lead-gen/HR/Telegram/Zalo vì code đã done, pháp lý/ToS đã approved, và `sprint-status.yaml` xác nhận.
- **Public repo** vẫn cần hoàn tất **NFR-9 State B ratification** và **docs sync** cuối cùng trước khi coi là fully ready.

Các thay đổi cụ thể:
- `epics.md`: FR-43..47 chuyển `PROPOSED` → `DONE`; FR-63..92 chuyển `READY/REVIEW` → `DONE`; Epic 21/22/23 chuyển `in-progress/ready-for-dev` → `done`; cập nhật mọi `ux-contract-*` trỏ vào archive và ghi chú UX chuẩn.
- `AMENDMENT-Epic-12-21-22-23-Readiness-Correction-2026-08-17.md`: phụ lục chính thức ghi nhận các yêu cầu đã implement.

**Implementation Readiness Assessment Complete.**

