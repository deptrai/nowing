---
title: Nowing
status: approved
created: 2026-07-21
updated: 2026-08-25
canonical: true
---

# PRD: Nowing
## AI Gen Leads Enterprise
*Nowing (now + knowing) — Nền Tảng AI Săn Lead Doanh Nghiệp (AI Gen Leads Enterprise).*

> **👑 CANONICAL ECOSYSTEM DIRECTION (2026-08-23) — NGUỒN CHÂN LÝ TỐI THƯỢNG:**  
> Ranh giới trách nhiệm, luồng giao tiếp và phân định hệ sinh thái 3 dự án được chuẩn hóa bởi **`_bmad-output/planning-artifacts/prds/PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md`** (TRINITY-1 đến TRINITY-10).
> 
> * **🔵 Nowing (Product & CRM Hub):** AI Gen Leads Enterprise — Sở hữu User, Auth, Billing, Lead CRM, PII Vault AES-256 (Nghị định 13/2023), Confidence Gate (Story 21.21), Drip Outbound (Zalo OA/Telegram/Email), và Autonomous Workstation UI.
> * **🟢 ChainLens-Research (Strategy Brain & Market GPS):** Động cơ nghiên cứu sâu/rộng (Deep/Wide Research), phân tích thị trường và phát hiện phân khúc ICP trước khi xuất quân săn lead; cung cấp Search & Citation API độc lập (Exa-like).
> * **🟣 XActions Microservice (Tactical Execution Engine):** Chuyên trách 100% cào dữ liệu thô, vượt rào cản kỹ thuật (Anti-bot, WAF, Captcha, Signer `a_bogus`/`msToken`, SocksNode Proxy Pool) và phát dữ liệu qua MCP Daemon Port 3001 & Redis Stream.

---

## 0. Mục Đích Tài Liệu & Ma Trận Hợp Nhất Các Phụ Lục (Consolidated Amendments Matrix)

Tài liệu này là **Bản PRD Hợp Nhất (Canonical PRD)** tích hợp toàn bộ các phân hệ tính năng từ 5 bản Amendment chính thức:

| Phân hệ / Phụ lục (Amendment) | Mã Yêu Cầu Chức Năng (FRs) | Trọng Tâm Nghiệp Vụ | Trạng Thái Triển Khai |
|---|:---:|---|:---:|
| **Nền tảng Cốt lõi & Workspace** | **FR-1 .. FR-42** | Auth, RBAC, Connectors, Memory (HNSW), Chat Citations, Deliverables, Automations, Clients | `[DONE / STABLE]` |
| **HR & Recruitment Intelligence** *(Amendment 1)* | **FR-43 .. FR-47** | Cào tuyển dụng TopCV, VietnamWorks, ITviec, bóc tách lương, PII Redaction (Epic 12) | `[DONE]` |
| **Multi-Domain Market Scrapers** *(Amendment 1)* | **FR-49 .. FR-55** | BĐS Batdongsan/Chotot, E-com Shopee/TikTok Shop, Đăng ký kinh doanh, Đấu thầu (Epics 14–20) | `[DONE / DELEGATED TO XACTIONS]` |
| **Lead Gen Intelligence & Outbound** *(Amendment 1)* | **FR-63 .. FR-69** | Intent Signals, Phone Waterfall 3 tầng, Zalo OA / Telegram Outbound, Credit Unlock (Epic 21) | `[IN-PROGRESS / S21.21 ACTIVE]` |
| **Telegram Stream Daemon & Bot** *(Amendment 1)* | **FR-70 .. FR-79** | Telegram MTProto Stream, Checkpoint Bot, 3s Inline Callbacks (Epic 22) | `[DONE]` |
| **Enterprise Lead Infrastructure** *(Amendment 1)* | **FR-89 .. FR-92** | Celery Worker Pool, Zalo OA ZNS, VietQR Affiliate Payout, Lead Partitioning & RLS (Epic 23) | `[DONE]` |
| **Autonomous Deep Lead Missions (DSH)** *(Amendment 2)* | **Epic 26 (AD-101..119)** | LangGraph Supervisor Loop, Multi-Tier LLM Router, $0 Token Gate, Distributed DLQ Worker | `[DONE]` |
| **Autonomous Workstation Studio** *(Amendment 3)* | **FR-93 .. FR-94** | Web App Builder & Traefik Hosting, Design View Mark Tool & AST Mutator (Epic 27) | `[IN-PROGRESS]` |
| **Enterprise Readiness & Compliance** *(Amendment 4 & 5)* | **FR-95 .. FR-99** | OKF Data Portability, Encryption-at-Rest BYOK, ToS Legal Compliance, OSS Onboarding | `[IN-PROGRESS]` |

---

## 1. Tầm Nhìn Sản Phẩm (Vision & Value Proposition)

Nowing là **Nền Tảng AI Săn Lead Doanh Nghiệp (AI Gen Leads Enterprise)** — giải quyết bài toán cốt lõi: **"Biến dữ liệu thô trên Internet thành danh sách khách hàng doanh nghiệp chất lượng cao với chi phí tối thiểu và tỷ lệ chuyển đổi cao nhất."**

```
❌ MÔ HÌNH CÀO TRUYỀN THỐNG (Cào bừa & Tốn kém):
Gõ từ khóa ──► Cào mù quáng hàng ngàn tin ──► Đốt hàng trăm ngàn token để lọc ──► Lead rác nhiều, chuyển đổi < 1%.

─────────────────────────────────────────────────────────────────────────────────────────

✅ MÔ HÌNH RESEARCH-FIRST CỦA NOWING:

[BƯỚC 1: MARKET GPS (ChainLens Deep/Wide Research)]
Phân tích tin tức thị trường, chính sách, đối thủ ──► Nhận diện phân khúc ICP & Bộ từ khóa chuẩn xác.
        │
        ▼ (Tọa độ săn lead chính xác)
[BƯỚC 2: PRECISION HARVESTING (XActions Engine)]
Chỉ cào đúng các hội nhóm/sàn mục tiêu ──► Tiết kiệm 80% chi phí cào và token.
        │
        ▼ (Raw Data đúng tệp 100%)
[BƯỚC 3: ZERO-TOKEN DATA GATE (Story 21.21)]
Pass 1 Regex lọc sạch 85%+ record (0 token) ──► Pass 2 Micro-LLM bổ sung SĐT với Phone F1 >= 95%.
        │
        ▼ (Clean Leads & PII Vault AES-256)
[BƯỚC 4: HYPER-PERSONALIZED OUTREACH (Nowing CRM)]
Kích hoạt tin nhắn Zalo OA / Telegram / Email Drip được cá nhân hóa sâu theo insight thị trường.
```

### 1.1 Ba Trụ Cột Giá Trị Cốt Lõi (The 3 Moats)

1. 🧠 **Market GPS & Trí Não Chiến Lược (Powered by ChainLens):**
   * Không bắt đầu bằng việc cào bừa bãi. Nowing phân tích bức tranh vĩ mô và vi mô của thị trường, bóc tách chân dung khách hàng tiềm năng cao nhất (ICP), từ đó lập kế hoạch săn lead với độ chính xác tuyệt đối.
2. 🎯 **Săn Lead & Dữ Liệu Sạch $0 Token COGS (Powered by XActions + Story 21.21):**
   * Thu thập dữ liệu đa kênh (Facebook Groups, Chợ Tốt, Shopee, TopCV, Đăng ký kinh doanh) qua XActions.
   * Lọc sạch dữ liệu bằng **Confidence Gate** (Pass 1 Deterministic 0 token + Pass 2 Selective Micro-LLM) để đạt độ chính xác SĐT $\ge 95\%$.
   * Bảo mật PII theo tiêu chuẩn Nghị định 13/2023/NĐ-CP với mã hóa AES-256 Fernet và HMAC-SHA256 deduplication.
3. 💬 **Trạm Làm Việc Bán Hàng & Chốt Sales Đa Kênh (In-house Nowing):**
   * Không gian làm việc Origami Split-Canvas (quản lý bảng dữ liệu, Kanban, chi tiết lead song song).
   * Kịch bản Drip Campaign tự động qua Zalo OA, Telegram Checkpoint Bot và Email.

---

## 2. Đối Tượng Người Dùng Mục Tiêu (Target ICP Personas)

### 2.1 Các Nhóm Người Dùng Trọng Tâm (Primary ICPs)

1. **B2B Sales Teams & Business Development Reps (SDRs):**
   * *Nhu cầu:* Tìm kiếm doanh nghiệp mới thành lập (ĐKKD), người đại diện pháp luật, số điện thoại giám đốc để chào dịch vụ B2B, phần mềm, kế toán, văn phòng.
   * *Giá trị nhận được:* Lead tươi cập nhật hàng ngày, SĐT thật đã qua xác thực, 1-click gửi tin nhắn Zalo/Email.
2. **Môi Giới & Nhà Đầu Tư Bất Động Sản:**
   * *Nhu cầu:* Săn tin rao nhà đất chính chủ giá ngợp trên Batdongsan, Chợ Tốt, Facebook; loại bỏ tin môi giới ảo/tin rác; trích xuất SĐT chủ nhà.
   * *Giá trị nhận được:* Báo cáo biến động giá theo khu vực (nhờ ChainLens), bóc tách SĐT chính chủ không bị che `***`, so sánh giá thị trường.
3. **Headhunters & HR Tech Recruiters:**
   * *Nhu cầu:* Thu thập nhu cầu tuyển dụng từ TopCV, VietnamWorks, ITviec, LinkedIn để tìm kiếm khách hàng doanh nghiệp cần tuyển dụng (B2B HR Services).
4. **Chủ Doanh Nghiệp & Market Researchers:**
   * *Nhu cầu:* Nghiên cứu đối thủ cạnh tranh, phân tích xu hướng tiêu dùng trên MXH/Sàn TMĐT trước khi tung sản phẩm mới.

### 2.2 Người Dùng Không Phục Vụ (Non-Users trong v1)
* Người dùng chỉ tìm kiếm một công cụ duyệt web thủ công (Nowing là Agent Workstation, không phải web browser).
* Người dùng cá nhân tìm kiếm chatbot trò chuyện phiếm (Nowing tập trung 100% vào Business Intelligence & Lead Generation).

### 2.3 Key User Journeys
- **UJ-1. Agent builder gọi Reddit scraper qua MCP.**
  - Đã xác thực bằng `NOWING_API_KEY`; chọn workspace với `nowing_select_workspace`.
  - Gọi `nowing_reddit_scrape` với query, community, sort, time_filter.
  - Nhận kết quả JSON gồm posts/comments, có URL gốc; nếu cần chi tiết hơn gọi `nowing_get_scraper_run`.
- **UJ-2. Researcher upload tài liệu và hỏi chat có trích dẫn.**
  - Vào workspace, upload PDF/doc; hệ thống parse/chunk/embed.
  - Hỏi câu hỏi, agent trả lời với citation badge số.
  - Click citation mở right panel hiển thị chunk được trích dẫn và các chunk lân cận.
- **UJ-3. Team mời thành viên vào workspace.**
  - Owner tạo invite; người được mời join.
  - Workspace có Owner/Editor/Viewer với quyền hạn phân tách; Owner có full access.
- **UJ-4. Người dùng lên lịch automation.**
  - Tạo automation với trigger schedule hoặc event, action `agent_task`.
  - Automation chạy một chat turn; kết quả có thể được agent tự viết vào nơi khác, nhưng không có action riêng để ghi trực tiếp Notion/Slack/Linear/Jira.
- **UJ-5. Self-hoster triển khai nền tảng.**
  - Chạy install script Docker Compose; backend + web + MCP + Zero sync hoạt động.
  - Cấu hình LLM/embedding tùy ý qua model connections.
- **UJ-6. AI agent builder dùng Nowing như memory layer qua MCP.**
  - Cài `nowing_mcp` vào Claude Code / Cursor / OpenCode.
  - Agent gọi `nowing_remember` để lưu fact/decision sau mỗi session.
  - Ở session sau, agent gọi `nowing_recall` để truy xuất context mà không cần đọc lại toàn bộ file.
- **UJ-7. Team tiếp tục research đã bắt đầu.**
  - User mở workspace, thấy danh sách “research threads” đang mở.
  - Chọn một thread, agent tự động recall các facts/quyết định/citations liên quan.
  - Team tiếp tục hỏi, agent trả lời dựa trên memory + internal docs + live data.

### 2.4 Non-Goals (đóng vĩnh viễn — positioning freeze lifted 2026-08-10 per SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`; NG-1 updated with exception)

Các hướng dưới đây **đã được soi bằng evidence và loại**. Ghi tường minh để không phải tranh luận lại; muốn mở lại phải qua SCP mới.

#### NG-1: Không bán raw research corpus / data-as-a-product (NG-1 core)
Nowing **không** bán raw web index hay research corpus như một sản phẩm dữ liệu.
- **Lý do cấu trúc:** mô hình của Exa *là* owned web index. Nowing/ChainLens là **orchestrator mua từ provider** (Brave, Jina, Exa, Tavily, Perplexity Sonar, SearXNG). Bán lại thứ đang mua, ở giá đã commoditize (~$7/1k), đấu specialist có vốn (Tavily→Nebius $400M, 2/2026) = arbitrage âm biên.
- **Evidence:** ChainLens `epic-26-gate-tracking.md` — owned index **DEFERRED, 0/7 gates passing**; Gate 3 & 6 *"infrastructure doesn't exist"*. `chainlens-direction-decision-brief-2026-07-24.md` §11 — corpus moat không đáng xây (Stack Overflow pay-per-crawl 2/2026 với rủi ro retroactive; a16z *"Empty Promise of Data Moats"*).
- **Ràng buộc kiến trúc:** `AD-DEFER-7` — owned web index / crawl-at-scale OUT of scope Nowing.
- **Biến thể đã phê duyệt (SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`):** bán **research output/deliverable đã cấu trúc** cho vertical B2B sales / lead intelligence tại Vietnam thông qua FR-65 (Enriched Contact Data) và FR-69 (Outcome-Based Pricing), với điều kiện:
  - Không bán raw web index hay research corpus (NG-1 core vẫn hiệu lực).
  - Chỉ bán verified contacts khi có legal basis, consent mechanism, và audit log.
  - PII pipeline cho lead data phân tách với HR/job data (FR-47/AD-25).
  - ToS/legal review cho Zalo OA, LinkedIn, và enrichment providers phải pass trước GA cloud.

#### NG-2: Không đua parity consumer kiểu Perplexity
Nowing **không** định vị là "Perplexity nhưng của tôi", và không lấy "rẻ hơn Perplexity/Exa" làm lý do trả tiền.
- **Lý do:** red ocean. Perplexity đã bỏ paywall Comet (FREE); OpenWebUI 136k★ / LibreChat 36k★; Perplexica/Vane là bản sinh đôi kiến trúc của ChainLens. Bán đáy = tự bào mòn + đấu free tier của đối thủ.
- **Lý do năng lực:** wedge kiểu này thắng bằng GTM/community, không bằng code. Team dev-strong / GTM-thin (PO xác nhận 2026-07-24) → *"đừng chọn chiến lược cần cơ bắp bạn không có"*.
- **Evidence:** `chainlens-direction-decision-brief-2026-07-24.md` §9–§10 (decision matrix: Option B "OSS + hosted" thắng 3.75; Option D "VN dev/researcher web-research" loại 2.95).
- **Lưu ý phân biệt:** UI chat có citations kiểu Perplexity **vẫn là tính năng của Nowing** (FR-13/FR-14, đã có). NG-2 loại **cách định vị và cách bán**, không loại tính năng.

#### NG-3: Không xây ChainLens thành sản phẩm độc lập
ChainLens không có end-user account, billing, onboarding, hay kênh phân phối riêng. Mọi thứ đó thuộc Nowing. Đối ứng: ChainLens SCP v4 đã drop Epic 34 (billing), 40-9 (onboarding), 41-1 (social), 40-7 (end-user auth), standalone distribution.

#### NG-4 (giữ nguyên từ §2.2): công cụ duyệt web thủ công · SLA/compliance doanh nghiệp · native mobile app

#### NG-5: Nowing does NOT build a public/vertical canonical index or search corpus
Nowing **không** xây `canonical_entities` table, `pgvector` index, `to_tsvector` corpus, hay unified search API cho BĐS/jobs/news/finance/company data trong chính mình.
- **Lý do cấu trúc:** `chainlens-research` là chỗ duy nhất own canonical index cho public web + shared vertical data. Nowing là scraper + product state + private workspace `Memory`. Duplicate indexing = duplicate storage + phân mảnh canonical source + maintenance gấp đôi.
- **Ràng buộc kiến trúc:** `AD-27` [RE-SCOPED 2026-08-08] — Nowing scraper output feeds `chainlens-research`; `AD-28` [RE-SCOPED 2026-08-08] — unified domain engine belongs in `chainlens-research`; `AD-34` (scraper feed contract); `AD-35` (Nowing does not build public/vertical search corpus). Xem SCP `sprint-change-proposal-2026-08-08-remove-duplicate-index.md`.
- **Phạm vi:** Các aggregator (BĐS, jobs) vẫn chạy normalize/dedupe/conflict detection trong Nowing, nhưng output cuối là `Chunk[]` gửi `chainlens-research` qua `POST /v1/ingest/scraper`; Nowing không expose REST/MCP search endpoint riêng cho aggregated listings.

## 3. Glossary
- **Workspace** — không gian nghiên cứu; trước đây gọi `searchspace`, migration 170 đổi tên. Chứa documents, chats, connectors, automations, members.
- **Connector** — nguồn dữ liệu hoặc công cụ bên ngoài: built-in scrapers (Reddit, YouTube, …), OAuth connectors (Google Drive, Notion, Slack, Linear, Jira, …), external MCP connectors.
- **Capability** — module scraper backend trong `app/capabilities/<platform>/` đăng ký route động qua `build_capabilities_router()`.
- **MCP server** — Model Context Protocol server (`nowing_mcp`) expose tools cho Claude/Cursor/any MCP client, gọi backend qua REST.
- **Chunk** — đơn vị nội dung canonical gửi giữa Nowing và `chainlens-research`. Mỗi `Chunk` có `content` (string) + `metadata` (bắt buộc: `source`, `sourceId`, `domain`, `fetchedAt`, `contentType`). Nowing scraper/aggregator output `Chunk[]` và gọi `POST /v1/ingest/scraper` trên `chainlens-research`.
- **Citation** — badge số trong câu trả lời chat liên kết đến chunk gốc. Panel hiển thị chunk window (±N chunk) với chunk được trích dẫn highlight.
- **Automation** — workflow gồm trigger + action; action hiện chỉ có `agent_task`.
- **Credit (micros)** — ví tín dụng thống nhất, 1_000_000 micros = $1. `user.credit_micros_balance` và `TokenUsage.cost_micros` theo dõi chi phí.
- **Memory** — một fact, decision, observation, hoặc kết quả research được lưu trữ lâu dài trong workspace, có embedding, metadata, và relation đến documents/chats/scraper runs. Bảng `memories`/`memory_versions`/`memory_relations`/`research_threads` tạo ở migration 177 (head hiện tại = 179).
- **Research Thread** — một dòng nghiên cứu kéo dài nhiều session/chat, có memory context riêng và có thể được continue/resume.
- **Memory Type** — phân loại memory: episodic (sự kiện/session), semantic (fact/knowledge), procedural (quy trình/preference), working (context hiện tại).
- **MCP Memory Tools** — các tool `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact` expose qua MCP server.
- **Role / Permission** — `WorkspaceRole` lưu danh sách permission; system roles mặc định gồm Owner, Editor, Viewer.
- **Deep-Research Engine (ChainLens)** — microservice ngoài cung cấp năng lực deep multi-step open-web research (classifier → planner → researcher → writer → reflection + citations). Nowing gọi qua `POST /api/v1/search` (SSE, Bearer service key). **Không** phải scraper capability, **không** phải sản phẩm độc lập — xem §4.9, `AD-15`, NG-3.
- **Research Degradation** — hành vi khi Deep-Research Engine không khả dụng (timeout / 5xx / chưa cấu hình): Nowing **degrade** sang hybrid search trên knowledge base của chính mình và trả về trạng thái tường minh (`partial` / `engine_unavailable`), thay vì hard-fail. Xem FR-38.
- **Deep-Research Deliverable** — kết quả deep research trả về theo đường **async** (submit → progress → notify → deliverable), không block một chat turn. Là State A của NFR-9.
- **State A / State B (NFR-9)** — hai trạng thái latency của deep research. **State A** = mặc định hôm nay, latency chưa validated → bắt buộc đường async deliverable. **State B** = mở khoá sync chat-mode sau feature flag, khi p95 đo được vượt ngưỡng. Xem NFR-9.

## 4. Features

> **Chỉ mục FR (theo số):** FR-1..4, FR-10 (Auth/RBAC §4.1) · FR-6,7,8,**43..47,49..52,58..62** (Connectors / Ecosystem §4.2) · FR-9,11,12,13,32,33,34,36,5 (Knowledge Base & Memory §4.3) · FR-14,15,16,17,42 (Chat §4.4) · FR-21,22,23 (Deliverables §4.5) · FR-18,19,20,35 (Automations §4.6) · FR-25,26,27,28,29 (Clients §4.7) · FR-30,31,**41,69** (Billing §4.8) · **FR-24,37,38,39 (Deep-Research Engine & Provenance §4.9)** · **FR-56,57 (Vertical Client Platform)** · **FR-63..68,85 (Lead Gen Intelligence §4.10)**. *(ID toàn cục, không tuần tự theo section.)*
>
> **⚠️ Thay đổi 2026-07-26:** **FR-41 mới** — Admin UI cho Global LLM Model Configuration (§4.8). Global model config hiện chỉ sửa được qua YAML/env + restart; chưa có UI admin.
>
> **⚠️ Thay đổi 2026-07-25:** **FR-24 đã rời §4.2 Connectors sang §4.9 Deep-Research Engine Integration.** ChainLens không còn được coi là một connector/scraper ngang hàng Reddit — nó là dependency kiến trúc hạng nhất (`AD-15`). FR-37 và FR-38 là mới.
>
> **⚠️ Thay đổi 2026-08-04:** **FR-42 mới** — Chat Response Benchmark (§4.4) · **NFR-10 mới** — Chat Response Regression Gate (§5). Nguồn chân lý tiến độ cho epics là `sprint-status.yaml`; Epic 4 = `done` (bao gồm 4.8a–4.8g chat benchmark & regression gate), Epic 8 = `done` (8.12 workspace limits + 8.13 PostHog analytics đã hoàn thành).

### 4.1 Identity, Auth & Workspace RBAC
**Description:** Người dùng đăng ký/đăng nhập qua email/password hoặc Google OAuth (`fastapi-users`). Mỗi workspace có Owner và các system roles; quyền kiểm tra qua `WorkspaceRole.permissions` và `has_permission`. Hỗ trợ custom roles do Owner/admin role tạo.

**Functional Requirements:**

#### FR-1: User Authentication
Người dùng có thể đăng ký, đăng nhập, refresh/revoke token, logout-all, và dùng Google OAuth. Desktop có endpoint session riêng.

**Consequences:**
- `/auth/*` routes trả JWT/cookie.
- `/users/me` trả `UserRead` bao gồm `credit_micros_balance`.

#### FR-2: API Access for External Clients
Desktop, browser extension, Obsidian plugin, MCP server xác thực bằng Personal Access Token (`nw_pat_...`) hoặc API key.

**Consequences:**
- `PersonalAccessToken` model lưu `token_hash`, `token_prefix`, `label`, `expires_at`, `last_used_at`.
- `Workspace.api_access_enabled` điều khiển truy cập API theo workspace.

#### FR-3: Workspace Lifecycle
Người dùng có thể tạo, liệt kê, xem, cập nhật (tên, mô tả, `citations_enabled`, `qna_custom_instructions`), và xóa workspace.

**Consequences:**
- Tạo workspace tự động tạo default system roles và membership Owner (`workspaces_routes.py`).
- `WorkspaceRole` lưu `name`, `description`, `permissions`, `is_default`, `is_system_role`, `workspace_id`.

#### FR-4: Workspace Invites & Memberships
Owner/Editor có quyền mời thành viên; membership gắn với `WorkspaceRole`; invite có mã, hạn, số lần dùng.

**Consequences:**
- `WorkspaceInvite` và `WorkspaceMembership` models.
- `WorkspaceMembership.is_owner` phân biệt Owner (gốc của workspace) với role.

#### FR-10: RBAC với ba system roles
System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; migration downgrade có thể tạo lại nhưng production không chạy downgrade. Role Admin không còn tồn tại trong danh sách system roles hiện tại.

**Consequences:**
- `get_default_roles_config()` chỉ trả Owner/Editor/Viewer (`app/db.py`).
- Editor không có `documents:delete`, `chats:delete`, `members:remove`, `members:manage_roles`, `settings:update`, `settings:delete`.
- Viewer có read + comments create.

**Gap / Removed:**
- `[REMOVED]` FR-10: Admin system role đã bị xóa khỏi RBAC (migration `72_simplify_rbac_roles.py`). README/public docs vẫn còn đề cập “Owner/Admin/Editor/Viewer” cần cập nhật.

### 4.2 Connectors
**Description:** Nowing kết nối với nhiều nguồn dữ liệu: built-in scrapers, OAuth connectors cho cloud apps, và external MCP connectors. Các scraper cũng được expose qua MCP server.

**Functional Requirements:**

#### FR-6: Built-in Scraper Connectors
Backend cung cấp các endpoint scraper cho Reddit, YouTube, Instagram, TikTok, Google Search, Google Maps, Amazon, web crawl. Mỗi scraper là một capability tự đăng ký route.

**Consequences:**
- `app/capabilities/<platform>/` (executor, definition, schemas).
- Mỗi lần gọi tạo một `Run` với `capability`, `origin`, `status`, `error`.

#### FR-7: External OAuth Connectors
Người dùng có thể thêm connector Notion, Slack, Linear, Jira, Google Drive/Calendar/Gmail, Dropbox, OneDrive, Confluence, ClickUp, Airtable, Discord, Luma, … qua OAuth.

**Consequences:**
- `Connection` model lưu `provider`, `base_url`, `api_key`, `extra`, `enabled`.
- Các route `/auth/<provider>/connector/add|callback|reauth`.

#### FR-8: External MCP Connectors
Người dùng có thể thêm MCP server bên ngoài vào workspace thông qua OAuth/composio, cho phép agent sử dụng tool của MCP server đó.

**Consequences:**
- `app/routes/composio_routes.py`, `/auth/mcp/{service}/connector/add`.
- `SearchSourceConnectorType` hỗ trợ `EXA_MCP_CONNECTOR` (Story 2.10) với `server_config` trỏ đến `https://mcp.exa.ai/mcp` và `x-api-key` inject qua header; `is_indexable = false`; agent chỉ discover `web_search_exa` + `web_fetch_exa` ở chế độ `readonly`.

#### FR-43: VietnamWorks Scraper (Vietnam Job Market)
Cung cấp capability `vietnamworks.scrape` gọi `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no auth) để lấy job postings từ VietnamWorks.

**Consequences:**
- Capability tự đăng ký trong registry, billing (`BillingUnit.VIETNAMWORKS_JOB`), MCP, REST routes.
- Input: `query`, `location` (city name), `page`, `hitsPerPage` (max 100), `salaryMin/Max`, `employmentType`.
- Output: typed `JobItem` với `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `salaryCurrency`, `salaryPeriodId`, `jobDescription`, `jobRequirement`, `jobFunction`, `yearsOfExperience`, `createdOn`, `approvedOn`, `expiredOn`, `isActive`, `typeWorkingId`, `skills`, `benefits`.
- Handles pagination (`page` 1-based, `hitsPerPage`), rate-limit (429), circuit-breaker, golden fixture regression tests.

**Status:** `[DONE]` — Epic 12 / Story 12.1 `done`; ToS/legal review approved 2026-08-08; VietnamWorks public-API spike passed; code merged and `bmad-code-review` passed.

#### FR-44: TopCV Scraper (Vietnam Job Market)
Cung cấp capability `topcv.scrape` để lấy job postings từ `https://www.topcv.vn` qua HTML scraping + anti-bot.

**Consequences:**
- BSL 1.1 proprietary fetcher (`app/proprietary/platforms/topcv/`).
- Input: `query`, `location`, `page`, `max_items`.
- Output: `JobItem` tương thích `vn_jobs.aggregate` (title, company, location, salary, JD, requirements, skills, post date).
- Requires anti-bot POC to pass before build (Cloudflare "Just a moment..." challenge observed).
- Degrades gracefully if TopCV is unavailable or blocked.

**Status:** `[DONE]` — Epic 12 / Story 12.2 `done`; Cloudflare/anti-bot POC passed 2026-08-12; code merged and `bmad-code-review` passed.

#### FR-45: ITviec Scraper (Vietnam Job Market)
Cung cấp capability `itviec.scrape` để lấy job postings từ `https://itviec.com` qua HTML server-rendered parsing.

**Consequences:**
- BSL 1.1 proprietary fetcher (`app/proprietary/platforms/itviec/`).
- Input: `query`, `location`, `page`, `max_items`.
- Output: `JobItem` tương thích `vn_jobs.aggregate`.
- Selectors: `job-card ipt-2`, `h3/a`, `employer-name`, `jd-main`.
- Salary is hidden for non-logged-in users (`Sign in to view salary`) → parse from title when possible or mark low-confidence.

**Status:** `[DONE]` — Epic 12 / Story 12.3 `done`; HTML server-rendered parsing spike passed; rate-limit + user-agent rotation implemented; code merged and `bmad-code-review` passed.

#### FR-46: Vietnam Job Market Aggregator (`vn_jobs.aggregate`)
Cung cấp capability `vn_jobs.aggregate` để gom dữ liệu từ FR-43, FR-44, FR-45, chuẩn hóa, dedupe, tính confidence score, phát hiện conflict, rồi **gửi `Chunk[]` tới `chainlens-research` qua `POST /v1/ingest/scraper`** để indexing và search. Nowing không giữ local search corpus.

**Consequences:**
- Apache-2.0 core service `app/services/jobs_aggregator/` (copy-modify from `bds_aggregator`).
- Input: `query`, `location`, `sources` (default `['vietnamworks','topcv','itviec']`), `salaryMin/Max`, `employmentType`, `experienceYears`, `maxItemsPerSource`, `minConfidence`.
- Output: `VnJobAggregateOutput` với `items` (`VnJobAggregatedListing[]`), `degraded`, `degradationReasons`, `sourceBreakdown`, `costMicros`, `ingestJobId`.
- Deduplication key: `company + title + location + postedAt`.
- Confidence score, source count, conflict flags: returned as `Chunk.metadata` to `chainlens-research`.
- PII redaction (FR-47) chạy trước khi gửi `Chunk[]`.
- Exposed via REST, MCP (`nowing_vn_jobs_aggregate`), and chat agent as a research-run that feeds the canonical index.

**Status:** `[DONE]` — Epic 12 / Stories 12.4a–e `done`; aggregator depends on FR-43–45 (now `DONE`), canonical `Chunk[]` schema (FR-62, AD-34), and `NowingIngestService` (Epic 20 done); PII redaction (FR-47) runs before ingest; code merged and `bmad-code-review` passed.

#### FR-47: PII Redaction for Job Data
Pipeline xử lý dữ liệu từ job scrapers **trước khi gửi `Chunk[]` tới `chainlens-research`** (hoặc lưu vào private `Memory`) để phát hiện và loại bỏ/mask thông tin cá nhân (phone, email, names) trong `jobDescription` / `jobRequirement`.

**Consequences:**
- Regex for Vietnamese phone/email; heuristic/NER for person names.
- Detected PII is masked or the field is dropped; raw JD is not stored in memory or in chunks sent to `chainlens-research`.
- Audit stats logged (counts only, no values).
- Applies to all job scrapers (FR-43, FR-44, FR-45) and the aggregator (FR-46) before ingest.

**Status:** `[DONE]` — Epic 12 / Story 12.5 `done`; shared PII redaction pipeline for job descriptions/requirements; runs before any `Chunk[]` ingest or `Memory` storage; code merged and `bmad-code-review` passed.

#### FR-48: Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]`
Canonical entity storage, multi-domain indexing, and unified search now belong to `chainlens-research`, not Nowing. Nowing domain scrapers/aggregators output `Chunk[]` to `chainlens-research` via `POST /v1/ingest/scraper`; `chainlens-research` handles deduplication, embedding, full-text/vector search, and merge history.

**Acceptance Criteria:**
- ~~Given data from 3 sources about the same entity, when aggregated in Nowing, then they merge into one canonical entity with confidence score.~~ → `chainlens-research` canonical index.
- ~~Given a canonical entity, when displayed, then it shows source count, conflict flags, and merge history.~~ → `chainlens-research` response.
- ~~Given a merge, when admin reverts, then entity returns to pre-merge state.~~ → `chainlens-research` merge history.
- Given canonical data contains PII, before indexing, then AD-25 redaction applies (in Nowing before ingest).

**Status:** `[REMOVED 2026-08-08 — moved to chainlens-research; Epic 13 dropped]`.

#### FR-49: News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a researcher,
I want news from major Vietnamese portals available in my workspace,
So that I can search and reference news articles via the Nowing chat agent.

**Acceptance Criteria:**
- Given RSS feeds are configured, when polled (every 15 min), then new articles from VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet are fetched.
- Given articles are fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`.
- Given a user searches for news, when the query is submitted, then `chainlens-research` `POST /api/v1/search` returns indexed news articles with citations.
- Given duplicate articles (syndicated across portals), when detected, then `chainlens-research` canonical index handles deduplication.

**Status:** `[RE-SCOPED]` — feed/crawl infrastructure in Nowing is done (Epic 14: Stories 14.1, 14.2a done; 14.2b blocked by `chainlens-research` entity-search contract). Nowing does not keep a local news index.

#### FR-50: Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As an investment researcher,
I want stock prices, financial statements, and market news from CafeF and Vietstock,
So that I can analyze company fundamentals via the Nowing chat agent.

**Acceptance Criteria:**
- Given CafeF API is connected, when a user queries a stock symbol, then price, OHLCV, and financial statements are fetched.
- Given financial data is fetched, when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`.
- Given financial data is indexed, when a user queries, then `chainlens-research` `POST /api/v1/search` returns results with citations.

**Status:** `[RE-SCOPED]` — feed/crawl infrastructure in Nowing is done (Epic 15: Stories 15.1, 15.1b, 15.2 done). Nowing does not keep a local financial index.

#### FR-51: Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a business researcher,
I want access to 2M+ Vietnamese company profiles with tax codes and registration data,
So that I can verify business partners and research market players via the Nowing chat agent.

**Acceptance Criteria:**
- Given masothue.com data is integrated, when fetched, then company profiles are normalized to `Chunk[]` and sent to `chainlens-research` via `POST /v1/ingest/scraper`.
- Given a user searches by company name or tax code, when the query is submitted, then `chainlens-research` `POST /api/v1/search` returns the company profile.
- Given company data contains PII, before ingest, then AD-25 redaction applies.

**Status:** `[RE-SCOPED]` — feed/crawl infrastructure partially done (Epic 16: Story 16.1 masothue and 16.5 public procurement done; 16.2 official business registry delegated to XActions). Nowing does not keep a local company index.

#### FR-52: E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]`
As a product researcher,
I want product data from Lazada and Shopee Vietnam,
So that I can perform pricing analysis and competitor tracking via the Nowing chat agent.

**Acceptance Criteria:**
- Given e-commerce scraper is built, when a user searches by product keyword, then product listings are fetched and normalized to `Chunk[]`.
- Given product `Chunk[]` are produced, when the batch is ready, then `POST /v1/ingest/scraper` on `chainlens-research` is called with `source: 'nowing_scraper'` and a stable `sourceId`.
- Given products from multiple platforms, when indexed, then `chainlens-research` canonical index handles deduplication.

**Status:** `[RE-SCOPED]` — feed/crawl infrastructure partially done (Epic 17: Story 17.2 Shopee done; 17.1 Lazada and 17.5 TikTok Shop blocked-by-external XActions). Nowing does not keep a local product index.

#### FR-53: Social Media Integration (Epic 18 — REMOVED, feature covered by E10)
As a social media analyst,
I want public content data from YouTube, Reddit, Instagram, and TikTok,
So that I can track sentiment, trends, and influencer content.

**Status:** `[DONE — covered by Epic 10 existing scrapers]`.

> **⚠️ Epic 18 removed (2026-08-06) — duplicate with existing scrapers.** YouTube, Reddit, Instagram, TikTok scrapers already built in Epic 10 (Connector & Scraper Expansion). FR-53 covered by FR-6 (Built-in Scrapers).

**Acceptance Criteria:**
- Given YouTube/Reddit APIs are connected, when a user searches, then video/posts data is returned.
- Given social data is stored, when PII is detected, then AD-25 redaction applies.


#### FR-54: Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens)
As a researcher,
I want Google Search and Maps data integrated,
So that I can search the web and find local businesses within Nowing.

**Acceptance Criteria:**
- Given Google Custom Search API is configured, when a user searches, then web results are returned and crawlable.
- Given Google Places API is configured, when a user searches by location, then business listings are returned.

**Status:** `[REMOVED]` — ChainLens-only; no Nowing epic (Epic 19 dropped). Google Search/Maps web search is handled by `chainlens-research` generic crawl and Exa MCP (FR-8.1).

> **⚠️ Epic 19 removed (2026-08-06) — duplicate with existing scrapers.** Google Custom Search trùng với ChainLens generic web crawl (FR-24, already built). Google Places data có thể complement BĐS data nhưng cần scope rõ ràng. **Potential conflict:** AD-DEFER-7 (no owned web index). Xem xét sau khi platform (E13) ship — nên dùng ChainLens thay vì build scraper riêng.

#### FR-55: Global E-commerce (Epic 20 — REMOVED, feature covered by E2)
As a product researcher,
I want product data from Amazon and Walmart,
So that I can perform product research on global markets.

**Acceptance Criteria:**
- Given Amazon/Walmart data sources are connected, when a user searches, then product listings with price, ratings are returned.

**Status:** `[DONE — covered by Stories 2.6 (Walmart) + 2.7 (Amazon)]`.

> **⚠️ Epic 20 removed (2026-08-06) — duplicate with existing scrapers.** Walmart (Story 2.6) and Amazon (Story 2.7) already built as part of Epic 2 (Connectors).

#### FR-56: Public Agent-Chat API for Vertical Clients
As a vertical client,
I want to create chat threads and send messages via public API with PAT authentication,
So that I can integrate Nowing chat into my application.

**Acceptance Criteria:**
- Given a valid PAT and workspace membership, when `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads` is called, then a chat thread is created and returned with `thread_id` and `research_thread_id`.
- Given a valid PAT, when `POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages` is called, then the message is processed by the chat agent and a response is returned.
- Given an invalid PAT or non-member, when any public endpoint is called, then 401/403 is returned.
- Given a `client_id` in the request, when the chat processes, then all data access is filtered by `client_id` (NFR-MULTI-1).
- Given rate limit is exceeded, when the endpoint is called, then 429 is returned with `Retry-After` header.

**Status:** `[DONE]` — Epic 18 / Story 18.1; public agent-chat endpoints and PAT auth implemented.

#### FR-57: Agent Registry
As a platform administrator,
I want to register agents with custom system prompts and tool configurations,
So that different vertical clients can have specialized chat agents.

**Acceptance Criteria:**
- Given the migration runs, when complete, then an `agent_configs` table exists with fields: `id`, `client_id`, `name`, `system_instructions`, `enabled_tools`, `disabled_tools`, `model_name`, `citations_enabled`, `is_active`.
- Given an `agent_id` is provided in a chat request, when processed, then the system loads the corresponding `AgentConfig` or returns 404 if not found.
- Given a chat request with `agent_id`, when the chat flow starts, then `AgentConfig.system_instructions` is prepended to the default system prompt.

**Status:** `[DONE]` — Epic 18 / Story 18.3; `agent_configs` table and `bdsai-listing-assistant` seed implemented.

#### FR-58: Scraper Feed to chainlens-research (Ecosystem Integration)
As a platform engineer,
I want every Nowing domain scraper and aggregator to feed `chainlens-research` via a canonical ingest endpoint,
So that public/vertical search data is indexed in a single canonical index owned by the research engine.

**Acceptance Criteria:**
- Given scraper output (BĐS, jobs, news, finance, company, e-commerce), when normalized to `Chunk[]`, then `POST /v1/ingest/scraper` on `chainlens-research` is called with service-to-service auth.
- Given a `Chunk[]` batch, when sent, then the request is idempotent keyed by `sourceId` and returns `ingestJobId`.
- Given PII in the batch, before ingest, then AD-25 redaction is applied.

**Consequences:**
- New `NowingIngestService` / adapter in `app/services/chainlens_ingest/`.
- All scrapers/aggregators implement `to_chunks()` conforming to `AD-34`.

**Status:** `[DONE]` — Epic 20 / Story 20.1; `NowingIngestService` and scraper `to_chunks()` feed `chainlens-research` via `POST /v1/ingest/scraper`.

#### FR-59: Gap-Fill Trigger via chainlens-research
As a workspace user,
I want the chat agent to trigger a gap-fill research run when the canonical index lacks data for my query,
So that the system can fetch missing data on-demand without building a local search corpus.

**Acceptance Criteria:**
- Given a chat query with public/vertical scope, when `chainlens-research` search returns low coverage, then `POST /v1/gap-fill` is triggered.
- Given a gap-fill request, when `chainlens-research` decides a Nowing scraper is needed, then it calls the registered Nowing scraper and ingests the result.
- Given gap-fill completion, when results are indexed, then the chat agent resumes with the updated corpus.

**Status:** `[DONE]` — Epic 20 / Story 20.2; gap-fill caller and cost allocation wired on the Nowing side.

#### FR-60: Private Data Provider (NowingPrivateProvider)
As a workspace user,
I want my private documents and connectors to be searchable by the chat agent without being pre-indexed in `chainlens-research`,
So that private data stays in Nowing but can still answer cross-corpus queries.

**Acceptance Criteria:**
- Given a chat query classified as private scope, when `chainlens-research` calls `POST /v1/private-data/search` on Nowing, then Nowing returns `Chunk[]` filtered by workspace RBAC.
- Given a `NowingPrivateProvider` call, when the user does not have access to a document, then it is not returned.
- Given private chunks, when returned, then `chainlens-research` merges them into its ranked result set without storing them.

**Status:** `[DONE]` — Epic 20 / Story 20.3; `NowingPrivateProvider` and `POST /v1/private-data/search` implemented.

#### FR-61: Cross-Project Service Auth & Cost Allocation
As a platform operator,
I want service-to-service calls between Nowing and `chainlens-research` to be authenticated and metered,
So that cost and usage can be attributed correctly and the services cannot be spoofed.

**Acceptance Criteria:**
- Given a `chainlens-research` request to Nowing (`POST /v1/private-data/search`, scraper invocation), when received, then Nowing validates a service Bearer token and maps it to a workspace.
- Given a Nowing request to `chainlens-research`, when sent, then Nowing includes a workspace-scoped Bearer token and correlation id.
- Given a cross-project call, when completed, then `TokenUsage` records the cost with `usage_type` and workspace attribution.

**Status:** `[DONE]` — Epic 20 / Story 20.4; service-to-service auth and cost ledger sync between Nowing and `chainlens-research` implemented.

#### FR-62: Canonical Chunk Metadata Schema (`source` enum)
As a platform engineer,
I want a strict `Chunk.metadata` schema and `source` enum shared between Nowing and `chainlens-research`,
So that ingestion, search, and citation are consistent across the ecosystem.

**Acceptance Criteria:**
- Given any `Chunk` sent to `chainlens-research`, then `metadata` contains `source`, `sourceId`, `domain`, `fetchedAt`, `contentType` (required) and optional `confidence_score`, `source_count`, `conflict_flags`.
- Given a `source` value, when validated, then it matches the canonical enum defined in `chainlens-research`: `public_crawl`, `nowing_scraper`, `brave`, `searxng`, `jina`, `exa`, `tavily`, `perplexity`, `private_provider`.
- Given missing required fields, when validated, then the request is rejected with a typed error.

**Status:** `[DONE]` — Epic 20 / Story 20.1; canonical `Chunk.metadata` schema and `source` enum (`nowing_scraper`, `private_provider`, etc.) shared with `chainlens-research` implemented.

### 4.10 Lead Gen Intelligence (mới 2026-08-10)

**Description:** Nowing cung cấp lead intelligence capabilities cho sales team / SDR — bao gồm intent signal detection, lead scoring, enriched contact data, và automated outreach. Đây là vertical expansion dựa trên market research (AI Lead Generation market $5.88B, Vietnam white space).

**Epic:** Epic 21 — Lead Gen Intelligence

**Functional Requirements:**

#### FR-63: Intent Signal Detection `[IN-PROGRESS]`
As a salesperson, I want to detect buying signals from companies (funding, hiring, tech stack changes, executive moves), so that I can reach out at the right moment.

**Acceptance Criteria:**
- Given a company in workspace, when signals are monitored, then funding events, job postings, tech stack changes, and executive moves are detected and surfaced.
- Given a signal is detected, when displayed, then it includes signal type, confidence score, source URL, and timestamp.
- Given multiple signals for the same company, when aggregated, then a composite lead score is calculated.
- Signals are sourced from: Crunchbase, LinkedIn, company websites, job boards, news.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.1 done; Epic 21 overall in-progress.

#### FR-64: Lead Scoring & Prioritization `[IN-PROGRESS]`
As a sales manager, I want leads scored and ranked by conversion likelihood, so that my team focuses on the highest-value prospects.

**Acceptance Criteria:**
- Given a set of leads, when scored, then each lead receives a composite score based on fit (firmographics, technographics) and intent (signal strength, recency).
- Given a lead score, when displayed, then it shows score breakdown (fit vs intent), trend (improving/declining), and comparison to similar converted leads.
- Given ICP criteria, when updated, then lead scores are recalculated for all leads in workspace.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.2 done; Epic 21 overall in-progress.

#### FR-65: Enriched Contact Data `[IN-PROGRESS]`
As an SDR, I want verified contact data (email, phone) for my target accounts, so that I can reach out to the right decision-makers.

**Acceptance Criteria:**
- Given a company, when contact enrichment is requested, then decision-maker names, titles, emails, and phone numbers are returned.
- Given contact data, when verified, then email is validated via waterfall (5+ providers) and phone via real-time validation (9+ providers).
- Given enrichment results, when displayed, then data source, verification status, and confidence are shown.
- Zero-bounce validation for emails; real-time validation for phones.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.3 done; 3-tier phone waterfall and PII vault in place. Epic 21 overall in-progress.

#### FR-66: Outbound Prospecting Automation `[IN-PROGRESS]`
As a sales team, I want to automate personalized outreach across channels, so that I can scale outbound without sacrificing quality.

**Acceptance Criteria:**
- Given a lead list, when outreach is triggered, then personalized messages are generated using lead context + ICP + intent signals.
- Given outreach sequences, when configured, then multi-channel sequences (email, LinkedIn, Zalo for VN) are supported.
- Given a sequence step, when executed, then the system personalizes content, tracks delivery, and logs responses.
- Given response detection, when a lead replies, then the sequence pauses and alerts the assigned rep.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.4 done; outbound sequence engine and split-view panel implemented. Epic 21 overall in-progress.

#### FR-67: CRM Integration & Write-Back `[IN-PROGRESS]`
As a sales operations manager, I want lead intelligence data synced with our CRM, so that reps work from a single source of truth.

**Acceptance Criteria:**
- Given a CRM connection (Salesforce, HubSpot, Pipedrive), when lead data changes, then it syncs bidirectionally, phased per AD-40: Phase 1 read-only dedup, Phase 2 write-back, Phase 3 bidirectional sync.
- Given a lead score or signal, when detected in Phase 2/3, then it writes to the corresponding CRM record.
- Given CRM data, when imported, then it enriches Nowing's lead profiles.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.5 done; Lark Base / Google Sheets / HubSpot/Salesforce/Pipedrive sync and read-first dedup implemented. Epic 21 overall in-progress.

#### FR-68: Zalo Integration (Vietnam Market) `[IN-PROGRESS]`
As a Vietnamese salesperson, I want to communicate with leads via Zalo, because 81% of Vietnamese professionals use Zalo as their primary messaging platform.

**Acceptance Criteria:**
- Given a Zalo OA connection, when configured, then outreach sequences can include Zalo messages.
- Given a lead with Zalo contact, when outreach is triggered, then personalized Zalo messages are sent.
- Given a Zalo reply, when received, then it's logged in the lead's activity timeline.
- Comply with Zalo's business messaging policies and Decree 356.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.6 done; Zalo OA deep-link, ZNS templates, and Telegram alerts implemented. Epic 21 overall in-progress.

> **FR-24 đã chuyển sang §4.9.** ChainLens Research **không phải** một connector/scraper. Nó là Deep-Research Engine — dependency kiến trúc hạng nhất, governed by `AD-15` (không còn `AD-3`). Xem **§4.9**.

#### FR-8.1: Exa MCP Search Connector `[DONE 2026-08-05]`
As a workspace user,
I want to connect the Exa AI MCP server as a first-class search connector,
So that the agent can answer questions with up-to-date web search and full-page fetch without human-in-the-loop approval.

**Acceptance Criteria:**
- Owner có thể POST `/search-source-connectors` với `connector_type: "EXA_MCP_CONNECTOR"` và optional `exa_api_key`; backend persist connector với `server_config` trỏ `https://mcp.exa.ai/mcp`, `x-api-key` injected as header, `is_indexable = false`.
- Multi-agent chat discover chỉ `web_search_exa` và `web_fetch_exa`, đánh dấu `readonly` để không hiện HITL prompt.
- `web_search_exa` trả về clean text từ top web results.
- `web_fetch_exa` trả về page content dạng clean markdown khi user cung cấp URL.
- Alembic migration `190_add_exa_mcp_connector.py` đã apply.
- Connector type wired vào `CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS`, `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`, `_CONNECTOR_TYPE_TO_SEARCHABLE`, `BASE_NAME_FOR_TYPE`, và connector config validation.

**Consequences:**
- `app/db.py` `SearchSourceConnectorType` thêm `EXA_MCP_CONNECTOR`.
- `app/services/connector/` maps và validation.
- `app/services/mcp/` discovery + `readonly_tools` filter.

### 4.3 Knowledge Base
**Description:** Workspace chứa documents, folders, versions và chunks. Upload qua REST, parse qua Docling/Unstructured/LlamaCloud, chunk + embed. Tìm kiếm hybrid semantic + full-text + reciprocal rank fusion. Trích dẫn liên kết về chunk gốc.

**Functional Requirements:**

#### FR-9: Document Upload, Parse & Index
Người dùng upload file hoặc URL; hệ thống parse, chunk, tạo embedding, lưu `Document`, `Chunk`, `DocumentVersion`, `DocumentFile`. Hỗ trợ 50+ định dạng.

**Consequences:**
- `app/indexing_pipeline/`, `app/etl_pipeline/`, `app/file_storage/`.
- `Document` có `title`, `document_type`, `content`, `content_hash`, `unique_identifier_hash`, `embedding`, `blocknote_document`.

#### FR-11: Folders & Document Management
Người dùng tạo/thư mục, di chuyển, đổi tên, xóa documents/folders với permission check.

**Consequences:**
- `Folder`, `DocumentVersion`, `DocumentRevision`, `FolderRevision` hỗ trợ versioning và revert.
- watched folders đồng bộ từ desktop.

#### FR-12: Hybrid Search over Knowledge Base
Workspace search kết hợp pgvector semantic, full-text, và reciprocal rank fusion. Có endpoint `/documents/search-semantic`.

**Consequences:**
- `app/retriever/`.
- Kết quả trả về chunks/documents dùng cho citation.

#### FR-13: Citation Panel for Knowledge-base Chunks
Click citation badge trong chat mở right panel hiển thị chunk được trích dẫn cùng chunk window (±5), chunk được highlight và auto-scroll trong panel.

**Consequences:**
- `nowing_web/components/citation-panel/citation-panel.tsx`.
- API `/documents/by-chunk/{chunk_id}` với `chunk_window`.

#### FR-32: Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]`
Workspace lưu trữ facts, decisions, observations, và kết quả research dưới dạng `Memory`, hỗ trợ hybrid search và truy xuất qua REST/MCP. Mỗi memory có lifecycle: create → update → correct → (decay/expire: post-MVP).

**Phạm vi MVP:** trọng tâm **semantic facts**; schema hỗ trợ đủ 4 memory type nhưng MVP dùng semantic. Bảng `memory_relations` đã có; graph traversal phong phú = fast-follow.

**Acceptance Criteria:**
- ✅ `Memory` có `content`, `type` (mặc định `semantic`), `source_type`/`source_id`, `tags`, `confidence` (REAL, mặc định 1.0), `embedding`, `workspace_id` — **đã có** (migration 177; ORM `app/db.py`).
- ⚠️ **Dedupe (primitive ĐÃ CÓ):** `repository.py` merge khi cosine distance `<=>` < 0.08 (~similarity > 0.92) + `update_on_duplicate`, tách scope user vs workspace. Open: **validate/tune ngưỡng qua eval** (AR-3) + phủ path auto-extract.
- ⚠️ **Recall hit** = memory trong top_k (mặc định ≤5) đã rank hybrid, vượt ngưỡng similarity — endpoint `/memories/search` tồn tại; ranking + ngưỡng cần verify + gate (NFR-8).
- 🔴 **Vế "vượt ngưỡng similarity" HIỆN KHÔNG ÁP ĐƯỢC (verify 2026-07-25).** `search.py:97` tính RRF score rồi `return [row[0] for row in rows]` bỏ đi; `memories_routes.py:117` hardcode `score=0.0`. Eval buộc chạy `required_oracle_mode: rank_only`. ⇒ **FR-32 hiện định nghĩa một thứ code không làm được.** Việc expose score từng hoãn sang `3-11` nhưng `3-11` đã `done` mà không làm ⇒ **đã giao lại cho `3-14`**. Xem NFR-1c.
- Không `Memory` nào ghi mà thiếu `source_type`/`confidence`.

**Consequences:**
- ✅ ORM `Memory`/`MemoryType`/`MemorySourceType`/`MemoryRelationType` (`app/db.py`); bảng ở migration 177.
- ✅ `app/services/memory/` (repository, service bridge markdown↔structured, parser, renderer, validation).
- ✅ Endpoints `POST /workspaces/{id}/memories`, `POST /workspaces/{id}/memories/search`, `PATCH /memories/{id}` (`memories_routes.py`); MCP `nowing_remember`/`nowing_recall`.
- ✅ Index HNSW (cosine) + GIN full-text trên `content` + GIN trên `tags`; quyền `memory:read/create/update/delete` (backfill 177).

**Status:**
- `[DONE]` — story `3-14` implemented bounded memory injection, recall, and auto-extract; story `3-9` recall-quality gate completed and baseline ratified 2026-08-04. Schema + endpoints + MCP tools + hybrid indexes + `confidence` + auto-extract are in place (migration 177/179). Dedupe primitive is present and wired (cosine<0.08, `update_on_duplicate`). Non-semantic memory types remain deferred.

#### FR-33: Research Continuity
Agent có thể tiếp tục một research thread đã có, tự động recall memory liên quan và citations trước đó.

**Acceptance Criteria (MVP):**
- `nowing_continue_research(thread_id)` trả về N memory liên quan (đã rank) + danh sách citations trước đó của thread.
- "Continue" = nối vào `ResearchThread` hiện có; nếu `thread_id` không tồn tại → lỗi rõ ràng, KHÔNG tạo thread ngầm.
- Recall trong continue tuân theo cùng định nghĩa "recall hit" ở FR-32.

**Consequences:**
- `ResearchThread` liên kết với `ChatThread` và `Memory`.
- MCP tool `nowing_continue_research(thread_id)`.

**Status:**
- `[BUILT]` `ResearchThread` (bảng `research_threads` + `new_chat_threads.research_thread_id`, migration 177); MCP tool `nowing_continue_research` (`features/memory/`).
- `[PARTIAL]` chất lượng recall trong continue (ranking/ngưỡng) phụ thuộc NFR-8.

#### FR-34: Memory Correction
Người dùng/agent có thể update hoặc flag một memory là sai/không còn đúng; hệ thống lưu version history.

**Acceptance Criteria (MVP):**
- "Correct" = tạo `MemoryVersion` mới, giữ `previous_content` + `corrected_content` + `corrected_by` + timestamp; memory cũ KHÔNG bị xoá cứng.
- **Phạm vi propagation (MVP):** chỉ cập nhật chính memory đó; KHÔNG propagate đệ quy qua relation graph (contradiction/relation resolution = post-MVP).
- Recall sau correction trả về bản mới nhất theo mặc định.

**Consequences:**
- `MemoryVersion` hoặc `MemoryCorrection` model.
- MCP tool `nowing_update_fact`.

**Status:**
- `[BUILT]` bảng `memory_versions` (`previous_content`/`corrected_content`/`corrected_by_id`, migration 177); `PATCH /memories/{id}`; MCP `nowing_update_fact`.
- `[GAP]` propagate correction qua relation graph = post-MVP (đúng như AC).

#### FR-36: Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]`

> **✅ ĐÓNG 2026-07-25.** Ops đã verify: **migration 178 chưa apply trên prod** (`alembic_version` = 174), `memory_md`/`shared_memory_md` **rỗng**, snapshot đã tạo → **không có dữ liệu nào bị mất**. Story `3-10a-legacy-memory-data-safety-spike` = `done`. Recovery path cũng đã build phòng ngừa (`3-10b` = `done`): guard G1.2 trong `178.upgrade()` (raise nếu legacy data chưa backfill) + command app-level `scripts/backfill_legacy_memory.py` (embeddings không chạy được trong raw migration) + 5 integration test xanh. **Deploy-order bắt buộc: mig177 → backfill → mig178.** Phần mô tả rủi ro dưới đây giữ lại làm ngữ cảnh lịch sử.
Migration `177_add_research_memory_tables` tạo bảng `memories` NHƯNG **không backfill** dữ liệu markdown cũ; `178_drop_legacy_memory_columns` sau đó **DROP** `user.memory_md` và `workspaces.shared_memory_md`. Grep toàn `nowing_backend` **không thấy migration nào chuyển `memory_md` → `memories`**. ⇒ Memory markdown cũ của user/team **có khả năng đã bị xoá mà không được migrate** (không phải rủi ro tương lai — có thể đã xảy ra).

**Acceptance Criteria:**
- Xác định **178 đã apply trên prod chưa** (kiểm tra `alembic_version` prod / lịch sử deploy).
- Nếu **đã apply**: đánh giá phạm vi mất dữ liệu; nếu cần, khôi phục từ backup DB → parse `memory_md`/`shared_memory_md` → `memories` (`source_type='manual'`, `confidence` mặc định) qua `MemoryRepository`.
- Nếu **chưa apply**: viết migration backfill `memory_md` → `memories` và chèn TRƯỚC 178 (hoặc hoãn 178) rồi mới drop.
- Nếu mất dữ liệu không hồi được: thông báo user hiện hữu (ảnh hưởng niềm tin "pivot lần 2").

**Consequences:**
- Có thể cần data-migration script mới + verify job đối chiếu số lượng trước/sau.

**Status:**
- `[RESOLVED]` FR-36 (2026-07-25): 178 chưa apply prod (alembic 174), `memory_md` rỗng, snapshot đã tạo → **không mất dữ liệu**. Guard + backfill command + tests đã build (`3-10a`, `3-10b` = done). Ràng buộc còn lại: **giữ deploy-order mig177 → backfill → mig178**. Crack đỏ #1 từ PRFAQ **đã đóng**.

#### FR-40: First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]`

> **Vấn đề, đo bằng code.** `MemoryExtractionService` chỉ có **một** hàm extract: `extract_from_turn` (`app/services/memory/extraction.py:118`). **Không có đường nào extract từ scrape run, deep research, hay document upload.** Cộng với việc workspace mới **không seed gì** (`grep seed|sample|onboarding|welcome|starter|template app/routes/workspaces_routes.py` = **rỗng**; `scripts/` không có seed script), hệ quả là:
>
> **`nowing_recall` ở session đầu trả rỗng — không phải vì bug, mà vì cấu trúc.** Memory chỉ tồn tại sau khi người dùng đã chat. Người dùng mới không có gì để recall, kết luận sản phẩm không chạy, và bỏ đi **trước** khi tới giá trị thật ở session 2. Đây là **M1 (first-run value ≤ 15 phút)** — hiện **không tồn tại**.
>
> **Và nó làm câu định vị của brief thành không đúng.** Brief §1: *"it remembers what it went and found, not just what you told it."* Code hiện tại **chỉ** làm nửa sau (`what you told it`). Nửa trước — `what it went and found` — **chưa có writer nào**.

**Quyết định (2026-07-25): làm cho hành động research ĐẦU TIÊN sinh ra memory. KHÔNG seed dữ liệu mẫu.**

| Phương án | Phán quyết | Lý do |
|---|---|---|
| **(a) Research run → memory** | ✅ **CHỌN** | Chứng minh đúng cái differentiator; recall có nội dung sau **một** hành động, không cần chat trước |
| (b) Seed sample workspace | ❌ Loại | Memory giả dạy sai mental model ("nó biết vì được nhồi" thay vì "nó tự đi tìm"); và sẽ **đổ thêm rác vào đường inject chưa có chặn trên** (NFR-1b) |
| (c) Onboarding tour thuần UI | ❌ Loại | Không tạo memory ⇒ recall **vẫn** rỗng. Chữa triệu chứng, không chữa nguyên nhân |

**Ba thứ (a) đóng cùng lúc:**
1. **M1 first-run value** — mục tiêu adoption chính.
2. **`MemorySourceType.SCRAPER_RUN`** khai báo ở `app/db.py:572` **chưa có writer nào**. FR-40 chính là writer đó — enum cho việc này **đã tồn tại sẵn**.
3. Câu headline của brief trở thành **đúng**.

**Acceptance:**
- **Given** người dùng mới vừa tạo workspace, **When** chạy **một** research/scrape run bất kỳ (8 platform / 14 verb sẵn có, hoặc deep research), **Then** run đó sinh ra memory có `source_type = SCRAPER_RUN` + provenance, **không** cần chat trước.
- **Given** run vừa xong, **When** gọi `nowing_recall`, **Then** trả về fact **có citation trỏ về run gốc** (không phải rỗng).
- **Given** một người dùng mới hoàn toàn, **When** đo từ signup → run đầu → recall có nội dung, **Then** **≤ 15 phút** (M1).
- **And** memory sinh ra tuân **NFR-1b** (đếm vào ngân sách 8.000 chars ở đường đọc — đây chính là lý do loại phương án (b)).
- **And** tôn trọng kill-switch sẵn có (`MEMORY_AUTO_EXTRACT_ENABLED` global + `workspaces.memory_auto_extract_enabled` per-workspace, story `8-8` = done) và spend cap `8-7`.

**Phụ thuộc:** provenance đầy đủ cần `9-6a` (`AD-11.1`: `source_capability` + `source_input` + soft `source_run_id`). **Nhưng không hard-block:** bản tối thiểu (`source_type = SCRAPER_RUN` + `source_run_id`) chạy độc lập được, nên `3-13` khởi động không cần chờ `9-6a`.
**Cảnh báo retention:** `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) — memory phải **tự chứa** đủ ngữ cảnh, vì `Run` gốc sẽ bị xoá sau 30 ngày. Đây đúng là lý do `AD-11.1` tồn tại. Ghi chú schema: `Memory.source_id` là `Integer` (`app/db.py:2077`) còn `Run.id` là **UUID** (`app/db.py:3155`) ⇒ **không dùng được `source_id` cho run**, phải đi qua trường `source_run_id` của `AD-11.1`.

**Truy vết:** brief §9 H-4 → FR-40 → story `3-13`.

**Status:**
- `[DONE]` — story `3-13` completed; first research/scrape run produces memory with `source_type = SCRAPER_RUN` and provenance, and `nowing_recall` returns non-empty results after the first run.

#### FR-5: AI File Sorting `[REMOVED]`
Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172.

**Gap / Removed:**
- `[REMOVED]` FR-5: AI File Sorting đã bị xóa khỏi schema (`172_remove_ai_file_sort.py`). Không còn UI, API, hay logic liên quan. Cần loại bỏ khỏi marketing copy.

### 4.4 Chat & Agents
**Description:** Multi-agent chat runtime sử dụng LangGraph/LangChain. Main agent có tool registry, subagents, memory, permission middleware, action log và revert. Hỗ trợ real-time comments, mentions, public sharing.

**Functional Requirements:**

#### FR-14: Chat Threads & Messages
Người dùng tạo thread, gửi message, nhận streaming response. Thread có `title`, `archived`, `visibility`, `workspace_id`, `created_by_id`.

**Consequences:**
- `NewChatThread`, `NewChatMessage` models.
- `/threads` và `/threads/{id}/messages` endpoints.

#### FR-15: Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]`
Main agent gọi tools (scraper, filesystem, memory, report, podcast, …); có subagents chuyên biệt (chainlens, …); recall workspace memory (agent gọi `nowing_recall`); dùng `AgentFeatureFlags` để bật/tắt middleware.

**Consequences:**
- `app/agents/chat/multi_agent_chat/`.
- `AgentActionLog`, `AgentPermissionRule`, `DocumentRevision`/`FolderRevision` cho audit/revert.
- memory retrieval integration trong `main_agent` loop.

**Auto-extract (đã có — cần review, KHÔNG phải fast-follow):**
- ⚠️ Cột `workspaces.memory_auto_extract_enabled` **đã tồn tại** (migration 179, **default TRUE**) → auto-extract là per-workspace và **đang bật mặc định** — trái với ghi chú trước ("chưa có/opt-in").
- Requirements review: default TRUE có thể phình chi phí (theo dõi SM-C2) → cân nhắc ngân sách token; **verify mức độ wiring** của `MemoryExtractionService` vào `main_agent` loop (chưa xác nhận đủ).
- `[PARTIAL]` auto-recall ngầm mỗi lượt (không cần agent gọi tool) — cần verify.

#### FR-16: Real-time Collaborative Chat
Nhiều người dùng cùng xem/cập nhật thread qua Zero sync; hỗ trợ comments, mentions.

**Consequences:**
- `ChatComment`, `ChatCommentMention`, `PublicChatSnapshot`.
- Zero publication cho threads/messages/comments/automation runs.

#### FR-17: Anonymous Chat with Quota
Người dùng chưa đăng nhập có thể chat với một document upload và quota giới hạn.

**Consequences:**
- `/anonymous/*` routes.

#### FR-42: Chat Response Benchmark
Hệ thống cung cấp benchmark trong `nowing_evals` để đo chat response với dữ liệu thực tế hoặc curated.

- `nowing_evals` gọi `POST /api/v1/new_chat` qua `NewChatClient`, mỗi case một thread mới.
- Thu thập mỗi turn: latency, TTFB, prompt/completion/total tokens, `cost_micros`, citation count, finish status, turn/message ids.
- Hỗ trợ `chat/regression` (drift gate trên nhiều tag: memory, document, deep-research, multi-tool, creative), `chat/quality` (LLM-as-judge), và nền tảng lấy mẫu query production đã anonymize.
- Dữ liệu mặc định là synthetic; trích xuất query thật từ production phải qua bước anonymize PII.

**Consequences:**
- `nowing_evals/src/nowing_evals/core/clients/new_chat.py` parse `data-token-usage`, `data-turn-info`.
- `nowing_evals/src/nowing_evals/suites/chat/regression/`.
- `nowing_evals/src/nowing_evals/suites/chat/quality/` (Phase 2).
- Admin/script sampler để trích xuất và anonymize query production.
- `gate.yaml`, sample dataset, báo cáo theo tag.
- CI / deploy gate (4.8e).

### 4.5 Deliverables
**Description:** Nowing tạo các deliverable từ nội dung workspace: report (markdown/Typst) export đa định dạng, podcast (transcript/audio TTS), video presentation (slides/scene codes), image generation.

**Functional Requirements:**

#### FR-21: Report Generation & Export
Tạo report từ document/folder; hỗ trợ export ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain text.

**Consequences:**
- `Report` model; `/reports` routes; export pipeline.

#### FR-22: Podcast & Video Presentation
Tạo podcast 2 host từ document/folder dưới 20 giây; tạo video presentation với slides/scenes.

**Consequences:**
- `Podcast`, `VideoPresentation` models; `/podcasts/*` routes.

#### FR-23: Image Generation
Tạo ảnh từ prompt, model, size, style, quality, response_format.

**Consequences:**
- `ImageGeneration` model; `/image-generations/*` routes.

### 4.6 Automations
**Description:** Tạo workflow kích hoạt theo lịch (cron) hoặc sự kiện (connector/webhook). Mỗi automation có một definition JSON chứa trigger và các action steps. Runtime chạy qua Celery.

**Functional Requirements:**

#### FR-18: Automation Action Types  `[DONE — cải chính 2026-07-25]`
Automation action registry có action `agent_task` (chạy một turn của multi_agent_chat), **direct write-back actions riêng cho Notion/Slack/Linear/Jira**, và `continue_research`.

> **⚠️ Cải chính 2026-07-25 (readiness check C-A).** Bản trước ghi *"direct write-back actions chưa được implement dưới dạng action type riêng"* và *"`__init__.py` chỉ import `agent_task`"* — **SAI**. Verify code: registry thực tế import **6 action type**.

**Consequences (verified 2026-07-25):**
- `app/automations/actions/builtin/__init__.py` import: `agent_task`, `continue_research`, `write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack` — mỗi cái một subpackage tự đăng ký.
- `ActionDefinition` có type cho từng action trên, không chỉ `agent_task`.

**Status:** `[DONE]` — story `6-4-direct-write-back-actions` = `done` trong `sprint-status.yaml`. Câu hỏi thiết kế ở **OQ-5** (action type riêng vs `agent_task` gọi agent tool) đã được trả lời trong thực thi: **chọn action type riêng**.

#### FR-19: Automation Triggers
Hỗ trợ trigger `schedule` (cron) và `event` (webhook/connector event).

**Consequences:**
- `AutomationTrigger`, `AutomationRun` models.
- `app/automations/triggers/builtin/schedule/` và `event/`.

#### FR-20: Automation Runs & Retries
Mỗi lần kích hoạt tạo `AutomationRun` với status, error, progress; có retry policy.

**Consequences:**
- `app/automations/runtime/executor.py`, `retries.py`.
- `app/automations/tasks/execute_run.py` chạy qua Celery.

#### FR-35: Memory-Driven Automations  `[DONE — cải chính 2026-07-25]`
Automation có thể kích hoạt khi memory thay đổi (ví dụ: có fact mới về competitor) hoặc tiếp tục một research thread đã lưu.

> **⚠️ Cải chính 2026-07-25 (readiness check C-B).** Bản trước ghi `[GAP]` *"Chưa có `memory_change` trigger và `continue_research` action"* — **SAI**. Ba tài liệu cùng sai (PRD, `epics.md` Story 6.5, `merge-to-prod-checklist.md`); `sprint-status.yaml` (`6-5: done`) là bên **đúng**.

**Consequences (verified 2026-07-25 — cả ba mảnh đều tồn tại):**
- ✅ Trigger type `memory_change` — `app/automations/triggers/builtin/memory_change/` (`params.py`, `selector.py`; docstring tham chiếu AC-2 → build từ story có AC). Đăng ký trong `triggers/builtin/__init__.py`: `from . import event, memory_change, schedule`.
- ✅ Action `continue_research` — `app/automations/actions/builtin/continue_research/`, đăng ký trong `actions/builtin/__init__.py`.
- ✅ `AutomationRun.research_thread_id` — `app/db.py:712` + relationship (`app/db.py:746`); resolve qua `app/automations/dispatch/launch.py:44` (`resolve_research_thread_id`).
- Guard chống vòng lặp: `selector.py` nêu rõ *"a memory-writing automation cannot re-fire a matching `memory_change` trigger"*.

**Status:** `[DONE]` — story `6-5-memory-driven-automations` = `done`. **Không còn là post-MVP.**

### 4.7 Multi-surface Clients
**Description:** Nowing được xây dựng multi-part: backend REST, web Next.js, desktop Electron, browser extension Plasmo, Obsidian plugin, MCP server. Các client đồng bộ qua backend và Zero (web ↔ desktop).

**Functional Requirements:**

#### FR-25: Web Client (Next.js)
Frontend chính: landing, dashboard, chat, connectors, settings, docs (Fumadocs). Server proxy tới backend qua `/api/v1/[...path]`.

**Consequences:**
- `nowing_web/app/`, `nowing_web/components/`, `zero/` config.

#### FR-26: Desktop Client (Electron)
Bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.

**Consequences:**
- `nowing_desktop/src/main.ts`, preload API.

#### FR-27: Browser Extension (Plasmo)
Thu thập lịch sử duyệt web và gửi về backend.

**Consequences:**
- `nowing_browser_extension/popup.tsx`, background scripts.

#### FR-28: Obsidian Plugin
Đồng bộ vault qua REST API `/obsidian/*`.

**Consequences:**
- `nowing_obsidian/src/main.ts`, `api-client.ts`.

#### FR-29: MCP Server
MCP server expose scraper, KB, **memory**, và research tools qua Model Context Protocol. Client gọi bằng `Authorization: Bearer <NOWING_API_KEY>`.

**Consequences:**
- `nowing_mcp/mcp_server/server.py` đăng ký workspaces, scrapers, knowledge_base, **memory**.
- Tools: `nowing_list_workspaces`, `nowing_select_workspace`, `nowing_web_crawl`, `nowing_google_search`, `nowing_reddit_scrape`, …, `nowing_search_knowledge_base`, `nowing_get_document`, …, `nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`.

**Status:**
- `[BUILT]` 4 memory tools trong `nowing_mcp/mcp_server/features/memory/` + `selfcheck.py` EXPECTED_TOOLS + tests (`tests/test_memory_tools.py`, e2e smoke).

### 4.8 Billing, Credits & Usage
**Description:** Ví tín dụng thống nhất (`credit_micros_balance`) dùng cho ETL pages, premium model calls, mua thêm qua Stripe, incentive tasks, auto-reload. `TokenUsage` ghi lại token/cost per turn. Self-hosted có thể tắt billing.

**Functional Requirements:**

#### FR-30: Token Usage Tracking
Mỗi assistant turn ghi `TokenUsage` với `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_micros`, `model_breakdown`, `usage_type`, `thread_id`, `message_id`, `workspace_id`, `user_id`.

**Consequences:**
- `app/services/token_tracking_service.py` dùng LiteLLM custom callback.
- `TokenUsage` model (migration 125, 142).

#### FR-31: Credit Wallet & Purchases
`User.credit_micros_balance` và `credit_micros_reserved` là ví tín dụng. `CreditPurchase` và `PagePurchase` theo dõi Stripe; `UserIncentiveTask` thưởng credit.

**Consequences:**
- `app/services/wallet_credit.py`, `app/routes/stripe_routes.py`.
- `auto_reload_service` tự động nạp khi balance thấp (nếu `AUTO_RELOAD_ENABLED`).

**Status:**
- `[DONE]` FR-31: Credit wallet + Stripe integration implemented (story `8-2`). The usage/credit dashboard is tracked by NFR-7 / story `8-3` and is also `DONE`.

#### FR-41: Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]`
Platform admin (không phải workspace Owner/Editor/Viewer — một vai trò mới, cấp toàn hệ thống) có thể xem, thêm, sửa, xoá, bật/tắt các **global chat model** (model dùng chung cho Auto mode/toàn platform, hiện chỉ cấu hình được qua `global_llm_config.yaml` hoặc biến môi trường `GLOBAL_LLM_CONFIG_B64`) thông qua một trang settings trên web UI, **không cần** sửa file/env và restart backend.

**Vấn đề hiện tại (verified 2026-07-25/26):**
- `global_llm_configs` chỉ đọc được từ YAML file (`app/config/global_llm_config.yaml`, gitignored) hoặc base64 trong `.env` (`GLOBAL_LLM_CONFIG_B64`) — parse **một lần lúc import module** `app/config/__init__.py` (`Config.GLOBAL_LLM_CONFIGS = load_global_llm_configs()`). Thêm/sửa model đòi hỏi: decode base64 → sửa YAML → encode lại → dán vào `.env` → restart process. Không có UI, không hot-reload cho phần này (khác với OpenRouter dynamic models, vốn *có* hot-reload qua `refresh_global_model_catalog()`).
- `GET /global-model-connections` đã tồn tại (read-only, `model_connections_routes.py`) nhưng **mọi** endpoint viết (`POST/PUT/DELETE /model-connections*`) tường minh chặn `scope == ConnectionScope.GLOBAL` với lỗi *"GLOBAL connections are YAML-only"*.
- Không có khái niệm "platform admin" trong hệ thống hiện tại — chỉ có role cấp-workspace (Owner/Editor/Viewer, FR-10). `User.is_superuser` (field có sẵn từ `fastapi-users`, đã lộ ra ở `nowing_web/contracts/types/user.types.ts`) hiện **không được dùng để gate bất kỳ route nào**.

**Acceptance Criteria:**
- Chỉ user có `is_superuser = true` mới gọi được các endpoint quản lý global model config; user thường (kể cả Workspace Owner) gọi thì nhận 403.
- Admin xem được danh sách global connection + model hiện có (nguồn YAML/env **và** nguồn DB-backed mới, xem Consequences), kèm trạng thái enabled/disabled, provider, base_url, model_name — **không** trả `api_key` thật về client (giữ nguyên pattern `has_api_key` boolean đã có ở `ConnectionRead`).
- Admin tạo được một global connection + model mới (provider, model_name, api_key, api_base, cost per 1k input/output tokens, rpm/tpm) qua form trên UI; model mới xuất hiện trong Auto mode pool **ngay lập tức, không cần restart backend**.
- Admin sửa được (đổi tên hiển thị, đổi giá, bật/tắt) và xoá được một global model đã tạo qua UI, hiệu lực ngay không cần restart.
- Admin có nút "Test connection" cho global model mới, tái dùng logic `verify_connection`/`test_model` đã có ở `model_connection_service.py`.
- Model global tạo qua UI (DB-backed) và model global đọc từ YAML/env (file-backed) cùng xuất hiện trong một danh sách hợp nhất, không phân biệt UX với người dùng cuối; UI có nhãn nhỏ phân biệt nguồn ("Managed" vs "From config file") để admin biết cái nào sẽ mất khi xoá `.env`.
- Model global do YAML/env quản lý vẫn **read-only** qua UI (đúng như thiết kế operator-owned hiện tại) — không cho sửa/xoá qua UI, chỉ cho xem + bật/tắt tạm thời (disable) nếu cần.

**Consequences:**
- Cần một khái niệm "platform admin" mới — đề xuất tái dùng `User.is_superuser` sẵn có, thêm dependency `require_superuser()` (song song `require_session_context`/`get_auth_context` hiện có trong `app/users.py`) — **không** cần bảng role mới, **không** đụng RBAC cấp workspace (FR-10 giữ nguyên 3 role Owner/Editor/Viewer).
- Cần mở write cho `Connection`/`Model` với `scope=GLOBAL` khi caller là platform admin — bảng đã có `ConnectionScope.GLOBAL` trong enum, chỉ cần bỏ chặn ở API layer cho riêng path admin (giữ chặn cho path người dùng thường).
- Cần hợp nhất nguồn GLOBAL model tại thời điểm materialize catalog: `materialize_global_model_catalog()` hiện chỉ nhận `chat_configs`/`image_configs` từ YAML/env; cần mở rộng để **cũng** query `Connection.scope == GLOBAL` từ DB và merge vào cùng danh sách `GLOBAL_CONNECTIONS`/`GLOBAL_MODELS`, tái dùng `refresh_global_model_catalog()` làm seam hot-reload sau mỗi lần admin CRUD (seam này đã tồn tại, hiện chỉ được gọi sau OpenRouter refresh).
- FE: trang settings mới tái dùng phần lớn component đã có ở `nowing_web/components/settings/model-connections/` (provider picker, connect form, model list) nhưng thêm route/guard riêng cho platform admin (không nằm trong `/dashboard/[workspace_id]/...` vì đây là cấu hình cấp platform, không thuộc một workspace).
- Billing/cost: model tạo qua UI phải set được `cost_per_1k_input_tokens`/`cost_per_1k_output_tokens` giống YAML, để `pricing_registration.py` đăng ký đúng giá cho LiteLLM (theo đúng cơ chế `AD-8` hiện có — không phải giá phẳng).

**Status:** `[DONE]` — story `8-11` implemented; admin global model config UI and API are complete.

_Trace: AD-8, AD-9 (mở rộng — không đổi 3 system role cấp workspace), `model_connections_routes.py`, `app/config/__init__.py` (`load_global_llm_configs`, `refresh_global_model_catalog`), `app/services/global_model_catalog.py`._

#### FR-69: Outcome-Based Pricing Option `[IN-PROGRESS]` (mới 2026-08-10)
As a sales team, I want to pay per qualified meeting booked (not just per seat), so that cost is tied to actual pipeline value delivered.

**Acceptance Criteria:**
- Given a pricing plan, when selected, then outcome-based option is available: pay per qualified meeting booked OR pay per lead enriched.
- Given a meeting is booked via Nowing outreach, when confirmed, then the cost is attributed to the workspace.
- Given a lead is enriched, when data is delivered, then per-lead pricing is applied.
- Given usage, when tracked, then the dashboard shows cost-per-meeting and cost-per-lead metrics.
- Outcome pricing works alongside existing seat-based pricing (users can choose).

**Pricing Tiers (proposed):**
| Model | Entry | Growth | Enterprise |
|-------|-------|--------|------------|
| **Seat-based** | $29/mo (5 users) | $99/mo (unlimited) | Custom |
| **Outcome-based** | $50/meeting booked | $30/meeting (volume) | Custom |
| **Lead enrichment** | $0.50/lead | $0.20/lead (volume) | Custom |

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.7 done; $0 chat/sequencer + pay-as-you-go credit ledger for verified leads and booked meetings implemented. Depends on FR-66 (outbound automation). Epic 21 overall in-progress.

#### FR-85: Unified Multi-Source AI Lead Generation Orchestrator `[IN-PROGRESS]` (mới 2026-08-10)
As an active sales rep or researcher,
I want to describe my target prospect in natural language in the chat,
So that Nowing's AI Orchestrator automatically plans and triggers parallel searches across all available scrapers, deduplicates results, enriches verified phone numbers, and streams a structured Lead Table in real-time.

**Acceptance Criteria:**
- Given a chat prompt containing seller intent (e.g., "tôi cần bán", "tìm khách mua", "ký gửi"), when `LeadGenOrchestrator.decompose_query` runs, then it returns `intent="sell"` and the adapter selection prioritizes buyer-demand sources or returns listings with a seller-framed summary.
- Given a chat prompt containing buyer intent (e.g., "tôi cần mua", "tìm nhà"), when `LeadGenOrchestrator.decompose_query` runs, then it returns `intent="buy"` and the adapter selection returns seller listings.
- Given `multi_source_lead_gen` returns BĐS listings (seller-side data), when the agent responds in chat, then it does not call them "khách hàng tiềm năng" unless the source is verified buyer-demand.
- Given the user intent is "sell" and the agent returns BĐS listings, when framing the result, then it describes them as "tin đăng bán tương tự / đối thủ cạnh tranh" and offers 1-click follow-up actions: (a) Tìm người mua, (b) Lấy SĐT chủ tin, (c) Phân tích giá.

**Status:** `[IN-PROGRESS]` — Epic 21 / Story 21.15 done; 2026-08-28 SCP amended with intent disambiguation + chat framing.

### 4.9 Deep-Research Engine Integration (ChainLens — Strategic Brain & Market GPS)

**Description:** Năng lực **deep multi-step open-web research** và **Market GPS** của Nowing được cung cấp bởi **ChainLens-Research** — microservice chuyên trách nghiên cứu thị trường, gọi qua `POST /api/v1/search` (SSE, `Authorization: Bearer <CHAINLENS_API_KEY>`). Đây là **dependency kiến trúc hạng nhất** theo quy chuẩn **`PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md` (Luồng B & TRINITY-10)**. 

ChainLens đóng 2 vai trò cốt lõi cho Nowing:
1. **Market GPS cho Lead Gen:** Phân tích thị trường, bóc tách chân dung ICP, xu hướng và đối thủ trước khi Nowing kích hoạt cào lead thô.
2. **Deep-Research Chat & Deliverables:** Cung cấp câu trả lời tổng hợp kèm trích dẫn nguồn (citations) minh bạch.

Retriever nội bộ của Nowing (hybrid search trên KB) và Deep-Research Engine bù trừ nhau: KB lo dữ liệu nội bộ đã ingest, ChainLens lo open-web research sâu. Governed by `AD-15` & `PRD-ECOSYSTEM-TRINITY-ALIGNMENT.md`.

**Epic:** Epic 9 — Deep Research đáng tin cậy: không vỡ, không treo, tính phí đúng.

**Functional Requirements:**

#### FR-24: Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]`
Người dùng và agent có thể chạy truy vấn deep research đa nguồn (web / discussions / academic) và nhận câu trả lời tổng hợp **có trích dẫn**, qua cả REST capability và MCP tool.

**Contract (🔒 không được break — verified 2026-07-25):**
- Endpoint: `POST {CHAINLENS_API_URL}/api/v1/search`, SSE.
- Auth: `Authorization: Bearer <CHAINLENS_API_KEY>` — **service-to-service**. Nowing giữ một key; ChainLens không biết end-user. Định danh/hạn mức end-user do Nowing quản.
- Request: `{ query, optimizationMode, tier, sources, history, stream, systemInstructions?, chatId? }` — `tier: "research"` và `stream: true` là một phần của contract (đã thêm từ 9.1a).
- Response: data-only SSE frames (`data: <json>\n\n`); `type` nằm trong JSON payload (`type:block` / `type:updateBlock` RFC6902 patch, `type:done`, `type:error`); terminal thật là `{"type":"done", "chatId": ..., "webUrl": ...}` — **không** có dòng `event:` hay sentinel `data:[DONE]`.
- Contract này **versioned + regression-guarded** ở phía Nowing (story **9.1b**) và phía ChainLens (`42-2`).

**Acceptance Criteria:**
- Query được kiểm soát bởi Pydantic `ResearchInput.query` (`min_length=1`, `max_length=500`) với `field_validator("query", mode="before")` `_strip_query`; query > 500 ký tự, rỗng, hoặc toàn khoảng trắng sau strip bị từ chối trước khi gọi engine. Executor không clamp thêm.
- Mọi câu trả lời có `sources[]` giữ nguyên thứ tự trích dẫn để map về citation UI.
- **Mode default = `balanced`** (D3, 2026-07-25). `quality` là **opt-in tường minh** — khi user/agent yêu cầu deep-research hoặc deliverable. Lý do: theo ChainLens `report-per-mode.md` (2026-08-02, `tier=research`), `quality` = **$0.0671** / call vs `balanced` = **$0.0482** / call (~**1.4×**), và trước 2026-07-25 Nowing âm thầm gọi `quality` cho **mọi** call (`schemas.py:38`). Story 9.3 validate chất lượng trên `nowing_evals` trước khi khoá; reversible qua env.
- Contract regression test tồn tại và chạy trong CI bằng marker `contract: contract regression tests for ChainLens integration` trong `pyproject.toml`; target `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.
- Fixture SSE regression được đồng bộ với ChainLens 42-2 qua local copy `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json` và drift test `tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py` so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.

**Consequences:**
- Backend capability `app/capabilities/chainlens/research/` (`definition.py`, `executor.py`, `schemas.py`) — module code giữ nguyên vị trí, nhưng **governance chuyển từ `AD-3` sang `AD-15`**.
- Subagent `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/`.
- MCP tool `nowing_chainlens_research` (`nowing_mcp/.../features/scrapers/platforms/chainlens.py`).
- Config: `CHAINLENS_API_URL`, `CHAINLENS_API_KEY`, `CHAINLENS_REQUEST_TIMEOUT_SECONDS` (`app/config/__init__.py:798-807`).
- Contract tests: `tests/unit/capabilities/chainlens/research/test_executor.py`, `tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py`, `tests/unit/capabilities/chainlens/research/fixtures/chainlens-sse-golden.json`; drift test so sánh với `CHAINLENS_REPO_PATH/apps/api/src/search/__tests__/fixtures/nowing-sse-parser.ts`.
- CI marker `contract: contract regression tests for ChainLens integration` trong `pyproject.toml`; command `pytest tests/unit/capabilities/chainlens/research/test_executor.py tests/unit/capabilities/chainlens/research/test_chainlens_fixture_drift.py -m contract -v`.

**Status:**
- `[BUILT]` capability + subagent + MCP tool + SSE parser. Story `2-4` đã done.
- `[DONE]` contract regression test (story **9.1b**): focused tests 25 passed/1 skipped. `[GAP]` mode default còn `quality` (story 9.3).

#### FR-37: Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]`
Chi phí mỗi lần gọi Deep-Research Engine phải được ghi nhận theo **cost thật do engine báo về**, không theo giá phẳng phỏng đoán.

**Vấn đề hiện tại (verified 2026-07-25):**
- `CHAINLENS_QUERY_MICROS_PER_CALL = 5000` → **$0.005 phẳng mỗi call, bất kể mode** (`app/config/__init__.py`, dùng qua `BillingUnit.CHAINLENS_QUERY`).
- Nhưng `mode` default = `"quality"` (`schemas.py:38`), mà target cost cũ của ChainLens là quality $0.0105 / deep research $0.0164 (ChainLens PRD §7.1) → Nowing **under-meter 2.1×–3.3×** trước đây.
- `grep -rn "costDollars\|cost_dollars" nowing_backend/` → **0 hits**: cost thật chưa được parse.

**Cập nhật 2026-08-05 (ChainLens phản hồi):**
- Parser Nowing đã đọc `costDollars` từ `done.usage` (Story 9.2 done).
- Parser Nowing đã đọc `done.usage.estimated` và `done.resolvedMode`.
- Cost thực tế quan sát được (tiêu biểu Nowing dùng `tier=research`):
  - speed: **$0.0353**
  - balanced: **$0.0482**
  - quality: **$0.0671**
  - trung bình toàn bộ benchmark: **$0.0519 / call**.
- Các số trên là **writer-only** từ ChainLens 42-1; Nowing đánh dấu `"estimated"` cho đến khi ChainLens 34.1 full-pipeline aggregation sẵn sàng.
- **ChainLens cam kết:** Story 34.1 promote in-progress, target hoàn thành **2026-08-19**; canonical contract `done.resolvedMode` (top-level, source of truth) + `done.usage.{promptTokens, completionTokens, totalTokens, model, costDollars, estimated}` (mirror/fallback); `estimated: false` khi full-pipeline.
- **Golden fixtures từ ChainLens (2026-08-05):** `sse-done-estimated-2026-08-05.json` và `sse-done-actual-2026-08-05.json` đã sao chép vào `nowing_backend/tests/unit/capabilities/chainlens/research/fixtures/`; Nowing regression guard parse đúng `costBasis`, `resolvedMode`, `promptTokens`, `completionTokens`, `totalTokens`, `model`.
- `CHAINLENS_QUERY_MICROS_PER_CALL` fallback đã nâng từ 5,000 ($0.005) → **60,000 micros (~$0.06)** để sát với cost thực tế khi engine không emit `costDollars`.
- `costDollars = 0` chỉ còn trong các benchmark sponsored runway cũ; production hiện nhận cost thực.

**Acceptance Criteria:**
- Executor parse `costDollars` từ SSE terminal event (ChainLens story `42-1`, *spec ready*) và ghi vào `TokenUsage` với `usage_type = "deep_research"`, kèm `workspace_id` / `user_id` / `thread_id`.
- Executor parse `done.usage.estimated` (boolean) và set `cost_basis` tương ứng (`"estimated"` / `"actual"`).
- Executor parse `done.resolvedMode` (canonical top-level) để biết mode thực tế engine resolve; `done.usage.resolvedMode` chỉ là mirror/fallback.
- Executor parse `done.usage.{promptTokens, completionTokens, totalTokens, model}` để ghi token/cost breakdown đầy đủ.
- Wallet debit dùng cost thật; flat `CHAINLENS_QUERY_MICROS_PER_CALL` **chỉ còn là fallback** khi engine không emit cost, và mỗi lần dùng fallback phải log warning (để đo tần suất).
- Cost per deep-research call đo được theo mode, xuất hiện trong aggregate (nối vào NFR-7 dashboard khi có).
- **Gate:** không chốt bất kỳ con số pricing/subscription nào trước khi FR-37 và story `8-7` (auto-extract spend cap) có số thật từ ChainLens 34.1.

**Consequences:**
- `app/capabilities/chainlens/research/executor.py` — parse usage event.
- `app/capabilities/core/billing.py` + `types.py` — `BillingUnit.CHAINLENS_QUERY` xuống hạng fallback.
- `app/services/token_tracking_service.py` — thêm `usage_type` mới.
- Phụ thuộc ngoài: ChainLens `42-1 costDollars-in-SSE`.

#### FR-38: Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]`
Nowing **không được hard-fail** khi Deep-Research Engine không khả dụng. Nowing phải dùng được mà không cần ChainLens.

> **⚠️ FR này là yêu cầu MÔ HÌNH KINH DOANH, không chỉ reliability (D5, 2026-07-25).** Vì engine closed-source và Nowing public (§1.1), **mọi self-host instance đều chạy ở trạng thái không có engine**. Thiếu FR-38 thì self-host **không dùng được**, và toàn bộ đường OSS/PLG sụp. Đây là lý do story **`9.1a`** là **điều kiện tiên quyết trước khi public repo** và chạy **trước `9.1b`/`9.2`** — dù `9.2` có giá trị tài chính trực tiếp hơn.

**Vấn đề hiện tại (verified 2026-07-25):** `executor.py:192-198` chỉ raise `CHAINLENS_TIMEOUT` sau `CHAINLENS_REQUEST_TIMEOUT_SECONDS` (default **300s**). Không có fallback, dù chính Nowing đã có hybrid search (FR-12).

**Acceptance Criteria:**
- ChainLens timeout / 5xx / không cấu hình (`CHAINLENS_API_KEY` rỗng) → Nowing **degrade** sang hybrid search trên KB và trả trạng thái tường minh: `partial` (có evidence một phần) hoặc `engine_unavailable` (không có).
- Trạng thái degrade hiển thị được cho user/agent — **không** giả vờ là câu trả lời đầy đủ, và **không** bịa citation.
- Self-host không cấu hình ChainLens: mọi tính năng khác của Nowing hoạt động bình thường; deep research trả `engine_unavailable` với hướng dẫn cấu hình.
- Fallback rate được đo (nối vào SM-11).
- Có test cho cả ba nhánh: success / timeout-degrade / unconfigured.

**Consequences:**
- `app/capabilities/chainlens/research/executor.py` — degradation path.
- `app/retriever/` — reuse cho fallback.
- `docker/`, `.env.example`, docs self-host — ghi rõ hành vi khi không có engine, **và ghi rõ deep research là năng lực cloud** (không để self-host tự phát hiện tính năng vỡ).

**Hai phase của deep research cho self-host (D5, 2026-07-25):**

| | Nội dung | Trạng thái |
|---|---|---|
| **Phase 1** | Cloud-only. Self-host gọi deep research → `engine_unavailable`, dùng phần còn lại. | **Trong scope MVP.** Không cần build gì mới ngoài chính FR-38 |
| **Phase 2** | Endpoint có metering cho self-host — trả tiền theo call để dùng deep research. Bịt lỗ self-hoster trả $0 mãi mãi. | **Post-MVP, chưa phê duyệt.** Mở khi có số self-host thật + `9.2` cho số cost |

**Ràng buộc kiến trúc cho Phase 2 (bắt buộc — governed by `AD-15`):**

```
self-host Nowing  →  Nowing Cloud API (metered, key theo account)  →  engine (vẫn 1 service key)
```

**KHÔNG** được làm `self-host → engine trực tiếp`. Cách đó phá `ADR-CHAINLENS-AS-NOWING-MICROSERVICE`: §4 chốt engine *"scale theo tải của Nowing (một consumer đáng tin cậy), KHÔNG phải public multi-tenant SaaS"*; §5 chốt Nowing giữ **một** service key và engine **không có end-user auth**. Hàng nghìn self-host instance cần key + quota + chống abuse chính là multi-tenant surface mà SCP v4 đã de-scope khỏi engine.

Đi qua Nowing Cloud thì engine vẫn có đúng một consumer, và Nowing Cloud làm đúng việc nó vốn đã làm — account + credit wallet (FR-30/31, `AD-8`).

**Đã loại (không mở lại mà không có SCP mới):** phát hành binary/Docker closed-source của engine cho self-host. Blob closed-source trong repo OSS là pattern bị ghét nhất trong cộng đồng OSS; engine gọi provider trả tiền nên self-hoster không có key của các provider đó thì chạy cũng ra rỗng; và doanh thu $0 kèm gánh nặng license enforcement.

#### FR-39: Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]`
Một `Memory` sinh ra từ dữ liệu scrape phải trỏ được về **đúng lần scrape** đã tạo ra nó, và hệ thống phải chạy lại được truy vấn đó để kiểm fact còn đúng không.

**Vì sao quan trọng:** đây là tiền đề của differentiator *"memory có nguồn sống, tự re-validate"* — thứ phân biệt Nowing với các memory layer khác sau khi "memory có citation" đã thành table-stakes (xem `briefs/brief-Nowing-2026-07-25/brief.md` §4). Chính báo cáo Mem0 (~18/07/2026) thừa nhận memory staleness + temporal abstraction là bài toán chưa ai giải. Nowing có lợi thế cấu trúc vì **sở hữu đường ingest** — nhưng lợi thế đó hiện chưa dùng được.

**Vấn đề hiện tại (verified 2026-07-25):**

| # | Vấn đề | Bằng chứng |
|---|---|---|
| 1 | **Lệch kiểu:** không lưu được id của `Run` vào `Memory` | `Run.id` = `UUID` (`app/db.py:3155`) · `Memory.source_id` = `Integer` (`app/db.py:2077`) |
| 2 | **Không có writer:** `MemorySourceType.SCRAPER_RUN` khai báo rồi bỏ đó | `grep -rn "SCRAPER_RUN"` chỉ khớp khai báo enum `app/db.py:572` |
| 3 | **Run bị xoá sau 30 ngày** → re-validate hỏng sau một tháng dù đã nối được | `RUNS_RETENTION_DAYS = 30` (`app/capabilities/core/runs.py:33`) |

**Nền tảng đã có (không phải xây lại):** `Run` lưu `capability` (ví dụ `reddit.scrape`) **và `input` JSONB** (`app/db.py:3155-3170`) — đủ để **re-execute chính xác truy vấn cũ**. Đây là phần đắt nhất, và nó đã tồn tại.

> **✅ Phương án đã chốt — `AD-11.1` (2026-07-25).** Bản trước để ngỏ *"chọn một: retention có điều kiện HOẶC sao `capability`+`input`"* — quyết định kiến trúc nằm trong AC nên không testable (readiness Q-2). Nay chốt: **`Memory` tự chứa recipe, KHÔNG dùng retention có điều kiện cho `runs`.** Lý do: cleanup `runs` là cơ hội (~1% insert) nên thêm điều kiện biến nó thành truy vấn có khoá; `runs.output_text` (JSONL) giữ vô hạn là đắt sai chỗ — cần *recipe* chứ không cần *payload*; và AD-11 đã định nghĩa memory là first-class persistence layer nên nó không được phụ thuộc lifecycle của bảng log.

**Acceptance Criteria:**
- `Memory` có **`source_capability`** (String), **`source_input`** (JSONB), **`source_run_id`** (UUID nullable, **không FK cứng** — `Run` được phép biến mất sau 30 ngày).
- `Memory.source_id` (Integer) **giữ nguyên** cho nguồn `document`/`chat_message` — không đổi kiểu cột đó. Không hồi quy hai nguồn cũ.
- Auto-extract từ kết quả scrape set `source_type = SCRAPER_RUN` + **sao chép** `capability` và `input` từ `Run` + ghi `source_run_id`.
- Cleanup `runs` **KHÔNG** được sửa thành có điều kiện; memory vẫn re-validate được sau khi `Run` bị xoá.
- Có API/hàm `revalidate(memory_id)`: đọc `source_capability` + `source_input` → chạy lại → so sánh → cập nhật `confidence` hoặc tạo `MemoryVersion` khi lệch. Không xoá cứng memory cũ (FR-34).
- `source_input` là **snapshot bất biến** — muốn đổi truy vấn thì tạo memory mới, không mutate.

**Consequences:**
- Migration cho `memories`: thêm `source_capability`, `source_input`, `source_run_id`.
- `app/services/memory/repository.py` + `MemoryExtractionService` — sao recipe khi extract từ scrape.
- `app/capabilities/core/runs.py` — **không đổi** (đây là điểm chính của quyết định).
- Governed by **`AD-11.1`**.

**Status:** `[DONE]` — story `9-6` implemented; provenance recipe and re-validation API are complete.

### 4.10 Autonomous Workstation & Creative Studio (Manus-like)

**Description:** Nowing là **Autonomous Workstation** — ngoài research/chat, nó sở hữu các công cụ sáng tạo tự hành (generative deliverables) và điều khiển trình duyệt/ngữ cảnh của người dùng. Phần này bao gồm hai cột mốc Manus-killer được architecture spine `AD-113`–`AD-114` phê duyệt.

**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio.

#### FR-93: Full-Stack Web App Builder & Instant Hosting

Người dùng có thể mô tả một ứng dụng web bằng ngôn ngữ tự nhiên, agent sinh project Next.js/React + Tailwind CSS vào `/workspace/web-app`, và deploy 1-click lên `https://[app-name].apps.nowing.net` với HTTPS qua Traefik/Caddy.

**Acceptance Criteria:**
- Given một mô tả app bằng tiếng Anh hoặc tiếng Việt, when agent generate code, then một dự án Next.js + Tailwind hoàn chỉnh được ghi vào `/workspace/web-app` và trả về preview URL.
- Given người dùng bấm `Publish`, when app vượt qua validation, then nó được deploy lên `https://[app-name].apps.nowing.net` với chứng chỉ SSL hợp lệ.
- Given user muốn dùng domain riêng, when cấu hình CNAME, then Traefik/Caddy route động ánh xạ domain về app container.

**Consequences:**
- `app/services/web_builder/` (LLM generator, project scaffold, file writer).
- `docker/web-app.Dockerfile` template.
- Traefik/Caddy dynamic config + `apps.nowing.net` wildcard DNS.
- Workspace-scoped app registry.

**Status:** `[IN-PROGRESS]` — in-PRD per `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`; 27.1a `done`; Story 27.1 parent/tracking `backlog` (children 27.1b/c/d `backlog`); 27.2a/27.2b `ready-for-dev`.

#### FR-94: Design View Mark Tool & Presentation Studio

Người dùng có thể chỉnh sửa UI đã sinh bằng công cụ khoanh vùng trực quan (Mark Tool) để AST-mutate JSX, và có thể tạo/xuất slide deck PPTX/Marp từ prompt cùng bản ghi cuộc họp có speaker diarization.

**Acceptance Criteria:**
- Given Mark Tool đang hoạt động trên web preview, when người dùng bấm một phần tử, then công cụ bắt bounding box selector và cập nhật JSX AST tương ứng.
- Given một prompt trình bày, when yêu cầu xuất PPTX, then file `.pptx` 16:9 được sinh với speaker notes và biểu đồ.
- Given một bản ghi cuộc họp, when yêu cầu diarization, then output chứa action items theo từng người nói và meeting minutes.

**Consequences:**
- `python-pptx` dependency, PPTX export route.
- Marp Markdown slide renderer.
- Speaker diarization extension (`pyannote.audio` hoặc `whisperx`) trong `stt_service.py`.

**Status:** `[IN-PROGRESS]` — in-PRD per `AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`; 27.2a/27.2b `ready-for-dev`; Mark Tool 27.1d and container deploy 27.1c `backlog`; Story 27.1 parent/tracking `backlog`.

## 5. Non-Functional Requirements

#### NFR-1: Performance
> **⚠️ Viết lại 2026-07-25 (readiness C-1 + P-5).** NFR-1 cũ chỉ có "CRUD < 500ms" — **không có bound nào cho memory**, trong khi memory là lõi sản phẩm. Việc verify code hôm nay tìm ra **hai đường recall khác nhau**, và chỉ một đường được PRD mô tả:
>
> | Đường | Nơi chạy | Chặn lượt chat? | PRD cũ mô tả? | Bound cũ |
> |---|---|---|---|---|
> | **Memory injection** | `MemoryInjectionMiddleware.abefore_agent` | ✅ **CÓ — mọi lượt** | ❌ **KHÔNG** | ❌ không có |
> | **Recall tool** | `nowing_recall` · `/memories/search` | chỉ khi agent gọi | ✅ FR-32 (top_k ≤5 hybrid) | ✅ top_k |
>
> Đường thứ nhất là đường **nóng nhất** và **không có trong PRD**. Nó chạy `SELECT` mọi `Memory` row của workspace `ORDER BY created_at`, **không LIMIT**, **bỏ qua cả hai index chuyên dụng** (`ix_memories_embedding` HNSW + `ix_memories_content_search` GIN) đã tồn tại sẵn trong schema. Xem `AD-18`.
>
> **Đồng thời sửa một tiền đề SAI của P-5:** P-5 ghi *"auto-extract cộng latency **mỗi turn**"*. **Không đúng.** Caller duy nhất của `extract_from_turn` là `app/tasks/celery_tasks/memory_extraction_task.py` → chạy **trên Celery, ngoài request**. Auto-extract **không** nằm trên critical path. Nửa còn lại của P-5 (thiếu bound cho `recall`) **đúng**, và đúng nặng hơn dự kiến.

**NFR-1a — CRUD & scraper (giữ nguyên)**
- API response p95 < 500ms cho CRUD; scraper call có thể mất vài giây nhưng streaming updates qua SSE.
- Hybrid search trên pgvector với limit phù hợp.

**NFR-1b — Memory injection (CHẶN mọi lượt chat)** `[DONE — story 3-14]`
- DB time p95 **≤ 150ms**, độc lập với số memory row của workspace (⇒ **O(top-k), không O(N)**).
- Tổng ký tự memory được inject **≤ 8.000 chars**, **enforce ở đường ĐỌC**. Hiện `MEMORY_HARD_LIMIT = 25.000` chỉ validate **một** `content` ở đường **GHI** (`validate_memory_size`), nên với N fact thì aggregate **không có chặn trên** — middleware chỉ *báo* `chars=` cho LLM và nhờ nó tự consolidate.
- Phanh duy nhất hiện tại là `<memory_warning>` ở `MEMORY_SOFT_LIMIT = 18.000` — một vòng lặp **phụ thuộc LLM hợp tác**. Nó không thể đóng được lỗ này vì auto-extract (Celery) ghi thêm row mà LLM chưa từng consolidate.
- Fail-soft hiện tại (`except → return None`) **được giữ**, nhưng phải phát **counter** khi rơi vào nhánh đó — hiện chỉ có `logger.exception`, nên recall vắng mặt là **im lặng**.
- Đã có sẵn hook đo: `_perf_log.info("[memory_injection] ... db=%.3fs total=%.3fs")`. ⇒ Việc còn lại là **chốt ngân sách + assert**, không phải dựng instrumentation.

**NFR-1c — Recall tool (`nowing_recall`, `/memories/search`)** `[DONE — story 3-14]`
- Giữ đúng định nghĩa FR-32: top_k ≤ 5, đã rank hybrid, vượt ngưỡng similarity.
- p95 **≤ 300ms**.

> **🔴 TỰ CẢI CHÍNH 2026-07-25 — vế "vượt ngưỡng similarity" HIỆN KHÔNG ĐẠT ĐƯỢC.** Bản đầu của NFR-1c (do chính lượt này viết) nhắc lại định nghĩa FR-32 mà **không verify nó có implement được không**. Verify sau đó cho thấy **không**:
> - `app/services/memory/search.py:97` tính RRF score và `order_by(text("score DESC"))` — score **có** tồn tại
> - nhưng cùng file `return [row[0] for row in rows]` → **bỏ score đi**
> - `app/routes/memories_routes.py:117` hardcode **`score=0.0`**
>
> ⇒ **Không client nào — kể cả eval harness — nhìn thấy được similarity.** `nowing_evals/.../memory/recall/gate.yaml` phải đặt `required_oracle_mode: rank_only` và ghi thẳng lý do. `deferred-work.md:35` xác nhận: *"clause `min_similarity` của oracle AC-3 không bao giờ áp được, eval chỉ chấm theo rank"*.
>
> **Dependency treo:** `gate.yaml` hoãn việc expose score sang **story `3-11`**, nhưng `3-11` đã `done` (*"dedupe đã wire; tuning ngưỡng optional qua 3-9"*) và **không expose score**. Hai note trỏ vòng vào nhau: `3-11` chỉ sang `3-9`, `3-9` chỉ sang `3-11`. **Việc này mất chủ.**
>
> **Đã giao chủ: `3-14`.** Lý do gộp vào đó chứ không mở story mới: `3-14` đã sửa đúng `search.py` + đường recall (`AD-18` rule 1 — bounded top-k retrieval **buộc** phải làm việc với score), và NFR-1c phụ thuộc trực tiếp.
>
> **Hệ quả với NFR-8, nặng hơn vẻ ngoài:** oracle `rank_only` chỉ hỏi *"có nằm trong top 5 không"*, **không** hỏi *"có thật sự đủ giống không"*. Gate có thể **PASS** với kết quả rác chỉ vì nó tình cờ rank top-5. ⇒ Đây là **lý do thứ hai** để `3-14` chạy **trước khi chốt số SM-10** của `3-9` — bên cạnh lý do O(N) ở `AD-18` rule 6. Đo baseline dưới oracle bị làm yếu thì con số chốt ra sẽ dễ hơn thực tế.

**NFR-1d — Auto-extract (Celery, KHÔNG chặn lượt chat)** `[DONE — story 3-14]`
- **Bất biến:** auto-extract **không được** nằm trên critical path của lượt chat. Cần **regression test** khoá bất biến này (hiện đúng nhờ Celery, nhưng không có test nào giữ).
- Freshness: memory mới khả dụng cho recall p95 **≤ 60s** sau khi lượt chat kết thúc.
- Ngân sách chi phí do story `8-7` phủ (spend cap).

**Truy vết:** NFR-1b + NFR-1c + NFR-1d → `AD-18` → story `3-14`. NFR-1b là điều kiện tiên quyết của **NFR-8** (recall quality): không thể đo chất lượng recall khi lượng inject phụ thuộc N.

**Status:**
- `[DONE]` — story `3-14` completed; bounded memory injection, recall, and auto-extract constraints implemented and asserted.

#### NFR-2: Security & Auth
- JWT/cookie từ `fastapi-users`; PAT cho external clients.
- Permission check trên mọi workspace-scoped endpoint.
- Secrets qua `.env`, không hardcode.

#### NFR-3: Observability
- OpenTelemetry trace; logs qua `Log` model; SlowAPI rate limiter.
- Celery task monitoring.

#### NFR-4: Reliability
- Async DB I/O bằng SQLAlchemy async.
- Celery + Redis cho background tasks.
- Retry policy cho automation runs và scraper calls.

#### NFR-5: Multi-tenancy Isolation
- Mọi workspace-scoped query lọc theo `workspace_id`.
- `Workspace.api_access_enabled` kiểm soát truy cập API theo workspace.

#### NFR-MULTI-1: Tenant Isolation for Vertical Clients
- Mọi memory/recall query từ public agent-chat API **bắt buộc** lọc theo `client_id` (hard filter, không phải soft boost).
- Một client không bao giờ thấy data của client khác.
- `client_id` được set qua PostgreSQL RLS context (`SET LOCAL app.current_client_id`).
- Áp dụng cho: Memory, TokenUsage, Run, ResearchThread.

**Status:** `[PROPOSED]` — Epic 18 / AD-31. Orthogonal to workspace RLS (`workspace_id`). Hard filter, not boost. Design required before memory migrations.

#### NFR-6: Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]`
Click citation trong chat scroll/highlight được đoạn snippet tương ứng trong full document editor.

> **⚠️ Cải chính 2026-07-25 (readiness check U-4).** Bản trước ghi `[GAP]` với lý do *"`editorPanelAtom` không có trường `chunkId` hay highlight state"* — **SAI**. Verify code: `nowing_web/atoms/editor/editor-panel.atom.ts` **có** `chunkId: number | null` (dòng 12, 23, 38, 64, 79, 93), và logic dùng nó nằm ở `components/editor-panel/editor-panel.tsx` + `components/editor/plugins/citation-kit.tsx`.
>
> Đây là bất nhất **4 chiều** đã được phân xử bằng code: `ARCHITECTURE-SPINE` `AD-DEFER-1` nói DEFERRED · PRD nói `[GAP]` · `epics.md` nói `[DONE]` · `sprint-status.yaml` `3-6` nói `done`. **Code xác nhận đã xong** → `AD-DEFER-1` đã được đóng cùng lượt này.

**Status:** `[DONE]` — story `3-6-citation-scroll-to-highlight-in-full-document-editor` = `done`.
- `[NOTE]` giữ nguyên nhận xét cũ: đây thực chất là feature (thuộc FR-13), không phải NFR. Cân nhắc gộp vào FR-13 ở lần dọn PRD tới.

#### NFR-7: Usage & Credit Dashboard `[DONE]`
Dashboard tổng hợp usage/credit theo workspace, model, connector, thời gian đã được implement ở story `8-3`.

**Status:**
- `[DONE]` — story `8-3` usage & credit dashboard completed.

#### NFR-8: Recall Quality (eval-gated) `[DONE — story 3-9]`
Chất lượng recall phải được đo và đạt ngưỡng **trước khi ship** lớp memory.
- Dùng harness `nowing_evals` chạy trên tập truy vấn thực để đo **precision@k** và **noise rate** của `nowing_recall`.
- Đặt ngưỡng tối thiểu (ví dụ precision@5 ≥ ngưỡng cấu hình; noise ≤ ngưỡng) — **không ship nếu chưa đạt**.
- Ngưỡng cụ thể chốt cùng SM-10.

**Status:**
- `[DONE]` — story `3-9` completed; eval harness and gate logic are in place, and `sprint-status.yaml` confirms `3-9: done` with baseline ratified 2026-08-04.

#### NFR-9: Deep-Research Latency & Availability Budget (hai trạng thái)
Latency của Deep-Research Engine là **ràng buộc bên ngoài** với Nowing. NFR này không giả định latency tốt cũng không giả định latency tệ — nó buộc Nowing thiết kế cho trạng thái **chưa biết**, và định nghĩa cổng để nâng cấp khi có số đo.

**Bối cảnh (verified 2026-07-25 — đọc kỹ trước khi trích số):**
- Lần đo cuối (`nfr6-final-20-8-v2-postfix.md`, 2026-07-18) verdict **FAIL**: Ask avg 57–136s (target ≤8s), Reason 50–160s (≤35s), Research quality 198s (>180s), citation 50–88% (≥95%).
- **NHƯNG con số đó có thể đã stale.** `technical-deep-research-quality-latency-roadmap-2026-07-25.md` §0: *"ChainLens ĐÃ tối ưu latency rất nhiều nhưng CHƯA đo kết quả"* — `ADR-DEEP-RESEARCH-SPEED` phases 1-7 **done** (budget tuning −37%, pipeline parallelization, speculative prefetch, race Crawl4AI+Jina, precompute embeddings, cache TTL) nhưng story `20-0`/`20-8` = backlog.
- → Trạng thái đúng là **"chưa biết"**, không phải "chậm". Vì vậy ChainLens đặt `43-1 eval-harness` làm **GATE 0**.
- Lộ trình giảm latency phía ChainLens (Epic 43): `43-2` planner-DAG parallel sub-research (*lever lớn nhất*), `43-5` semantic cache hit-rate >60%, `43-4` multi-stage rerank; cộng `29-5` cost routing (done). **Ba đòn bẩy này không phụ thuộc owned index.** Đòn bẩy "index search" thuộc Epic 26 — DEFERRED 0/7 gates, **không near-term**, và trùng NG-1/`AD-DEFER-7`.

**State A — mặc định hôm nay (bắt buộc):**
- Nowing **phải** có đường **async deliverable** cho deep research: submit → progress → notify → deliverable. Không block một chat turn.
- **✅ Cải chính 2026-07-25 (`AD-17`):** hạ tầng async **đã tồn tại end-to-end**, không phải xây mới — `?mode=async` → 202 + `X-Run-Id`, SSE `GET .../runs/{id}/events`, ring buffer replay 500 event, cancel, history; web đã có typed client; `chainlens.research` đã nằm sau door đó. **Ba việc còn thiếu thật:** (1) `run_event_bus` hiện **single-process** → cần Redis pub/sub sau cùng interface trước khi bật trên nhiều replica; (2) **agent door đang sync** → đây mới là chỗ block chat turn; (3) không có `Notification` khi `run.finished` và kết quả chỉ nằm trong `runs.output_text` (TTL 30 ngày), chưa thành deliverable hạng nhất. Delivery **đi SSE**, **không** thêm `runs` vào `ZERO_PUBLICATION` (`AD-5` giữ nguyên).
- Lý do chọn A làm sàn: **async là superset của sync.** Xây async rồi latency giảm mạnh → vẫn đúng, chỉ trả về nhanh hơn. Xây *chỉ* sync rồi latency không giảm → sản phẩm vỡ. A là lựa chọn không cược vào giả định nào.
- Nowing đo **p50/p95 per mode từ phía mình** (không chờ engine tự báo).
- Availability: engine unavailable → FR-38 degradation. Fallback rate đo được (SM-11).

**State B — mở khoá sau (sync chat-mode):**
- Điều kiện: ChainLens `43-1` (GATE 0 eval-harness) land → `43-2` + `43-5` land **và có số đo**; Nowing story `9.3` xác nhận p95 vượt ngưỡng do Nowing đặt.
- Khi đủ điều kiện: bật sync chat-mode **sau feature flag**, giữ nguyên đường async.
- **Không** phụ thuộc Epic 26 / owned index.

**Baseline từ ChainLens (2026-08-01, non-search, n=57, model `agy/gemini-3.6-flash-*`):**

| Mode | p50 | p95 | Target p95 | Kết luận |
|---|---|---|---|---|
| speed | 24,189 ms | 34,964 ms | ≤ 30,000 ms | ❌ p95 vượt 30s |
| balanced | 30,681 ms | 69,888 ms | ≤ 30,000 ms | ❌ p95 vượt 30s |
| deep | 42,922 ms | 114,513 ms | ≤ 60,000 ms | ❌ p95 vượt 60s |

- HTTP success 100%; fail/degraded do SearXNG CAPTCHA/rate-limit.
- `costDollars` = $0 trong benchmark này (sponsored runway) — không dùng để định giá.
- ChainLens khuyến nghị chạy lại khi SearXNG/Brave/proxy ổn định; benchmark mới 2026-08-02 (`report-per-mode.md`) đã ghi nhận cost thực tế.

**Baseline rerun từ ChainLens (2026-08-02, focused 6 query × 3 mode = 18 runs, sau khi ổn định SearXNG/Brave):**

| Mode | p95 | Target p95 | Kết luận |
|---|---|---|---|
| speed | 27.5 s | ≤ 30 s | ✅ PASS |
| balanced | 44.3 s | ≤ 30 s | ❌ FAIL |
| deep | 43.7 s | ≤ 60 s | ✅ PASS |

- `ask` tier ở `quality` vẫn vượt target 30 s của NFR-6.
- Full benchmark 69 query đang lên lịch để củng cố p95 trên mẫu lớn.

**Benchmark cost thực tế từ ChainLens (`report-per-mode.md`, 2026-08-02, 31 queries, tier/mode):**

| Mode | Tier | Avg Latency | Avg Cost |
|---|---|---|---|
| speed | ask | 21.8 s | $0.0258 |
| balanced | ask | 25.8 s | $0.0407 |
| quality | ask | 49.3 s | $0.1485 |
| speed | reason | 29.6 s | $0.0303 |
| balanced | reason | 47.7 s | $0.0507 |
| quality | reason | 49.9 s | $0.0750 |
| speed | research | 33.4 s | $0.0353 |
| balanced | research | 51.1 s | $0.0482 |
| quality | research | 49.1 s | $0.0671 |

- `costDollars` **không còn $0**; đây là chi phí thực tế mới nhất từ ChainLens.
- Nowing gọi `tier=research`, vì vậy cost tham chiếu chính là **speed $0.0353 / balanced $0.0482 / quality $0.0671**.
- Tổng trung bình toàn bộ benchmark: **$0.0519 / call**.
- Fallback `CHAINLENS_QUERY_MICROS_PER_CALL` đã cập nhật từ 5,000 ($0.005) → **60,000 micros (~$0.06)** để sát với cost thực tế.

**Quyết định ngưỡng A→B (2026-08-05 — phản hồi ChainLens):**
- **State A vẫn là mặc định.** `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = false`.
- **Sync chat-mode chỉ cho `speed` và `balanced`** với target ChainLens đề xuất: ask ≤ 60s, reason ≤ 90s, research ≤ 120s; Nowing e2e benchmark phải xác nhận p95 `balanced` ≤ 30s trước khi mở.
- **`quality` / `deep-research` / `deep-reasoning` = async-only trong chat.** `mode=auto` phải resolve rõ ràng; `resolvedMode` trong `done` frame cho Nowing biết request đã resolve thành mode nào.
- Cần full 69-query benchmark + e2e từ phía Nowing (bao gồm network + parse + charge) + full-pipeline cost telemetry (ChainLens 34.1) trước khi ratify State B.
- **ChainLens cam kết (2026-08-05):** Story 34.1 in-progress, target hoàn thành **2026-08-19**; rerun 29-5 với `deepseek-v3.2` sau 34.1; `DEEPSEEK_DIRECT_MODELS` default chỉ còn `deepseek-v3.2` (loại `v4-pro`, `v4-flash`).
- **Xác nhận canonical contract:** `done.resolvedMode` là **top-level required key**; `done.usage.resolvedMode` chỉ là mirror/fallback. Nowing parser ưu tiên top-level.
- **Model allow-list contract:** `chainlens-nowing-model-allow-list-2026-08-05.json` đã publish, liệt kê per-mode stack, sync/async gating, `deepseekDirect.defaultAllowList = ["deepseek-v3.2"]`, `excludedByDefault = ["deepseek-v4-pro", "deepseek-v4-flash"]`.

**Gap:**
- `[DONE — implementation]` State A async deliverable, mode default `balanced`, latency metrics, feature flag.
- `[PENDING RATIFICATION]` State B sync chat-mode: cần ChainLens 34.1 full-pipeline cost (target 2026-08-19) + rerun 29-5 + Nowing e2e chứng minh p95 `balanced` ≤ 30s. Story 9.3.
- `[NOTE]` UX tiền đề: State A buộc pattern **async / progress-first**. `ux-designs/` hiện chỉ có scaffold rỗng — cần UX spec trước khi build UI deep-research.

#### NFR-10: Chat Response Regression Gate
Mọi deploy production phải qua gate chat regression trước khi mở rộng traffic.

- `nowing_evals` chạy `chat/regression` trên tập query đại diện.
- Metrics bắt buộc: p95 e2e latency, p95 TTFB, error rate, finish rate, citation count, cost/turn.
- Ngưỡng cụ thể được chốt trong `gate.yaml` và chỉ có thể `baseline_ratified: true` sau 3 lần chạy liên tiếp ổn định.
- Dữ liệu benchmark không chứa PII; self-host có thể dùng synthetic dataset.

#### NFR-11: Scraping Compliance & Anti-Bot Resilience

**1. ToS & Legal (Vietnam job market):**
- Không được bắt đầu build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` cho đến khi ToS của từng nguồn cho phép automated access và commercial use.
- Phải hoàn thành legal counsel opinion về employment service provider classification trước khi pilot bắt đầu.
- Giữ vững phân biệt Nowing là **research/memory layer**, không phải job board / ATS / employment intermediary.

**2. Anti-bot (TopCV/ITviec):**
- TopCV yêu cầu anti-bot POC pass trước merge.
- ITviec hiện chưa gặp Cloudflare, nhưng phải có rate-limit + user-agent rotation + circuit-breaker.
- Không lưu raw challenge/CAPTCHA tokens, không bypass Cloudflare bằng exploit.

**3. PII (all job sources):**
- PII detection phải chạy trước khi lưu `jobDescription` / `jobRequirement` vào memory.
- Không lưu phone, email, person names chưa mask; audit chỉ log counts.
- PII detection coverage ≥95% of obvious PII.

**4. Reliability:**
- `vn_jobs.aggregate` phải trả về `degraded=true` với `degradationReasons` khi một nguồn fail.
- Mỗi scraper có circuit-breaker, retry policy, golden fixture regression tests.

**Status:** `[PROPOSED]`.

## 6. MVP Scope

### 6.1 In Scope
- Auth (email/Google OAuth, PAT, API access toggle).
- Workspace CRUD + RBAC Owner/Editor/Viewer + custom roles.
- Knowledge base upload/index/search + citation panel.
- **Long-term research memory (In Scope — ĐÃ BUILD):** schema + endpoints + 4 MCP tools + hybrid indexes + `confidence` đã có (migration 177–179; `memories_routes.py`; `features/memory/`). **Còn lại (open):** dedupe tuning qua eval; memory type ngoài semantic (defer). ~~đánh giá mất dữ liệu legacy (FR-36)~~ → **đã đóng 2026-07-25, không mất dữ liệu.** Auto-extract đã có (179, default true) — review chi phí/ngân sách, không phải "chưa build". **recall quality eval gate** (NFR-8, story `3-9`) = **done** (implementation complete; baseline ratification pending); **auto-extract spend cap** (story `8-7`) = **done** (59 tests passed).
- Multi-agent chat với tools, memory retrieval, subagents.
- Built-in scrapers (Reddit, YouTube, Instagram, TikTok, Google Search/Maps, Amazon, web crawl) qua REST và MCP.
- **Deep-Research Engine Integration (§4.9, Epic 9)** — ChainLens là engine deep-open-web-research phía sau Nowing, không phải một connector. In scope MVP: **FR-38** degradation + self-host independence (`[DONE]`, **P0 — tiền đề trước khi public repo**, story `9.1a`, chạy trước FR-24/FR-37); **FR-37** cost metering thật qua `costDollars` (`[DONE]`, P0, parser đã cập nhật cho `done.usage.costDollars`); **FR-24** contract + regression guard (`[DONE]`); **NFR-9 State A** đường async deliverable đã có, baseline ChainLens đã có (`[PARTIAL]` — State B chưa đạt ngưỡng, story 9.3). Mode default đổi `quality` → `balanced` (`[DONE]`).
- **Ranh giới OSS/Cloud — Phase 1 (D5):** deep research là **năng lực cloud**; self-host nhận mọi thứ khác. Phải ghi rõ trong docs/README, không để self-host tự phát hiện. Xem §1.1 + §4.9 FR-38.
- Deliverables: report, podcast, video presentation, image generation.
- Automations: schedule/event trigger + `agent_task` action.
- Web, desktop, extension, Obsidian, MCP clients.
- Credit wallet + Stripe purchases + token usage tracking (backend).

### 6.2 Out of Scope for MVP

**Non-goals vĩnh viễn (không phải "hoãn" — xem §2.4):**
- **[NON-GOAL NG-1 core]** Bán raw research corpus / data-as-a-product kiểu Exa. Không có owned index (ChainLens Epic 26: **0/7 gates**), và Nowing/ChainLens *mua* từ Exa/Tavily/Brave. Ràng buộc kiến trúc: `AD-DEFER-7`.
- **[NG-1 exception (SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`)]** Bán structured lead-enrichment deliverables cho B2B sales tại Vietnam qua FR-65/FR-69, với điều kiện legal basis, consent mechanism, audit log, và PII pipeline tách biệt với HR/job data.
- **[NON-GOAL NG-1b]** Owned web index / crawl-at-scale trong Nowing.
- **[NON-GOAL NG-2]** Định vị parity consumer kiểu Perplexity, và "rẻ hơn Perplexity/Exa" làm lý do trả tiền. *(UI chat có citations vẫn là tính năng — FR-13/14. NG-2 loại cách **định vị và bán**, không loại tính năng.)*
- **[NON-GOAL NG-3]** ChainLens thành sản phẩm độc lập (end-user account/billing/onboarding/distribution riêng).

**Hoãn có điều kiện (không phải non-goal):**
- **[STATE B]** Deep research như **chat turn đồng bộ**. Mở khoá khi ChainLens `43-1`→`43-2`+`43-5` land và story `9.3` xác nhận p95 vượt ngưỡng. MVP xây State A (async deliverable) làm sàn. Xem NFR-9.
- **[PHASE 2]** Deep research cho **self-host** qua endpoint có metering (self-host → Nowing Cloud API → engine). Mở khi có số self-host thật + `9.2` cho số cost. MVP là Phase 1 (cloud-only). Xem §1.1 + §4.9 FR-38.
- **[LOẠI]** Binary/Docker closed-source của engine cho self-host — đã loại, không mở lại mà không có SCP mới (§4.9 FR-38).
- **[SCRAPER BUDGET GATE]** Mọi built-in scraper mới (bao gồm TopCV / các nguồn lead gen) phải qua scraper budget gate (cap 30–50 built-in scrapers) và anti-bot/ToS/cost POC trước khi đưa vào P0. Ưu tiên dùng API/feed/waterfall thay vì built-in scraper cho Epic 21.
- **[TOPCV ANTI-BOT POC]** `topcv.scrape` P0 bị chặn cho đến khi anti-bot POC đạt ≥90% success với cost ≤$0.05/query equivalent; nếu không, drop TopCV khỏi P0 (xem `technical-spike-topcv-itviec-2026-08-05.md`).

**✅ Đã ra khỏi danh sách out-of-scope (cải chính 2026-07-25 — readiness check C-A/C-B/U-4):**
- ~~**[GAP]** Direct Notion/Slack/Linear/Jira write-back actions~~ → **DONE**, registry có 4 action riêng (FR-18)
- ~~**[GAP]** Citation click scroll/highlight trong full document editor~~ → **DONE**, `editorPanelAtom` có `chunkId` (NFR-6)
- ~~**[GAP]** Memory-driven automation triggers (`memory_change`, `continue_research`)~~ → **DONE**, cả trigger lẫn action đều đăng ký (FR-35)
- ~~**[GAP]** Per-workspace MCP tool enable/disable toggle~~ → **DONE**, story `2-5` = `done` (OQ-4)
- ~~**[GAP]** Usage/Credit dashboard~~ → **DONE**, story `8-3` = `done` (FR-31/NFR-7)

**Gap / removed như trước:**
- **[REMOVED]** AI File Sorting (`ai_file_sort_enabled` đã bị xóa migration 172) — không quay lại v1.
- **[REMOVED]** Admin system role (migration 72) — chỉ Owner/Editor/Viewer.
- **[PARTIAL]** Document retention: schema đã có (migration 176: `document_retention_days`/`auto_archive_enabled`/`document_retention_action`/`documents.archived_at`); enforcement job + UI + LEGAL policy (OQ-3) chưa đầy đủ.
- **[GAP]** Advanced memory lifecycle (decay, TTL, contradiction graph resolution) — dự kiến post-MVP.
- **[GAP]** UI memory browser / research timeline — có thể dùng chat/MCP trước, UI chuyên dụng post-MVP.
- **[BUILT/PARTIAL]** Auto-extract memory: cột `memory_auto_extract_enabled` đã có (179, **default true**); độ sâu wiring `MemoryExtractionService` + ngân sách token cần review (xem FR-15) — KHÔNG còn là "chưa có".
- **[GAP]** Relation graph traversal phong phú giữa memories — fast-follow (bảng `memory_relations` đã có ở 177; graph query phong phú chưa).

## 7. Success Metrics

**HR Pilot-specific (added 2026-08-05)**
- **SM-12**: Số aggregate query `vn_jobs.aggregate` thành công trong pilot (target ≥100/8 tuần).
- **SM-12a**: Số job listings indexed/ngày từ 3 nguồn (target ≥2,000).
- **SM-12b**: Số cross-source deduped listings/ngày (target ≥1,000).
- **SM-12c**: Dedupe accuracy (target ≥90%).
- **SM-12d**: Confidence score top 80% (target ≥0.6).
- **SM-12e**: PII detection coverage of obvious PII (target ≥95%).
- **SM-12f**: Customer discovery interviews (target ≥10).
- **SM-12g**: Active workspaces ≥3 days/week (target ≥10).

> **NOTE** SM-12 targets dùng để go/no-go pilot; không dùng làm SLA vĩnh viễn.

**Primary**
- **SM-1**: Số workspace active (≥1 chat/scraper run trong 7 ngày) — validates FR-3, FR-6.
- **SM-2**: Số scraper run thành công mỗi tuần — validates FR-6. *(Deep-research call của ChainLens đo riêng ở **SM-11** — không gộp vào scraper run nữa, vì FR-24 đã rời §4.2.)*
- **SM-3**: Tỷ lệ chat message có citation ≥ X% — validates FR-13.

**Secondary**
- **SM-4**: Số deliverables (report/podcast/video/image) được tạo — validates FR-21, FR-22, FR-23.
- **SM-5**: Số automation runs thành công — validates FR-19, FR-20.
- **SM-6**: Tỷ lệ invite được chấp nhận — validates FR-4.

**Counter-metrics (do not optimize)**
- **SM-C1**: Số scraper run failed — không tối ưu bằng cách giảm thử scraper khó; failed calls không tính phí.
- **SM-C2**: Average cost per chat turn — không giảm chất lượng để tiết kiệm token.

**Memory-specific**
- **SM-7**: Số memory operations (create/recall/update) mỗi tuần — validates FR-32, FR-34.
- **SM-8**: Tỷ lệ research threads được continue ≥ X% — validates FR-33.
- **SM-9**: Số MCP memory tool calls mỗi tuần — validates FR-29.
- **SM-10 (chất lượng, không phải volume)**: precision@k / noise rate của `nowing_recall` đo trên `nowing_evals` — validates NFR-8; là thước đo ship-gate, khác SM-7/8/9 (vốn chỉ đếm số lượng).

**Deep-Research Engine (dependency health — thêm 2026-07-25)**
- **SM-11**: Ba chỉ số về Deep-Research Engine, đo từ **phía Nowing** — validates FR-24, FR-37, FR-38, NFR-9:
  - **SM-11a — cost thật/deep-research call theo mode** (từ `costDollars`; kèm tỷ lệ phải dùng fallback flat-rate). Đây là **cost basis cho pricing**; không chốt giá trước khi có số này.
  - **SM-11b — p50/p95 latency per mode.** Cấp dữ liệu cho cổng chuyển NFR-9 State A → State B.
  - **SM-11c — fallback/degradation rate** (tỷ lệ request phải degrade sang hybrid search theo FR-38). Counter-metric: **không** tối ưu bằng cách nâng timeout để giấu lỗi.

> **[NOTE] Metrics targets là placeholder:** các ngưỡng "≥ X%" (SM-3, SM-8) và target số của SM-1/2/4/5/6/7/9 **chưa được định lượng**. Có thể instrument trước, nhưng phải chốt số trước khi dùng làm thước đo launch. SM-11 cố ý **chưa đặt ngưỡng** — story 9.3 đặt ngưỡng sau khi có baseline đo được (đặt ngưỡng trước khi đo là lặp lại đúng lỗi của NFR6 phía ChainLens).

## 8. Open Questions

#### OQ-1: External MCP connector marketplace
Liệu có cung cấp catalog/discovery cho external MCP servers (ngoài OAuth manual hiện tại)?

#### OQ-2: Agent tool default enable/disable  `[VẪN MỞ — defer có chủ đích]`
Có nên cho phép workspace owner cấu hình default enable/disable của agent tools ở backend thay vì chỉ localStorage ở client?

> **⚠️ ĐỪNG đóng OQ-2 vì thấy OQ-4 đã resolved — hai thứ khác nhau** (ghi rõ 2026-07-25 vì chúng đọc gần như giống hệt nhau):
>
> | | Bề mặt | Lưu ở | Trạng thái |
> |---|---|---|---|
> | **OQ-4** | **MCP tools** (client ngoài, qua API key) | **DB** — `workspace_mcp_tool_settings(workspace_id, tool_name, enabled)` | ✅ **RESOLVED** — story `2-5` done |
> | **OQ-2** | **Agent tools** (trong chat UI) | **localStorage của browser** — `nowing_web/atoms/agent-tools/agent-tools.atoms.ts` | 🟠 **VẪN MỞ** |
>
> Điểm cần chú ý: localStorage **đã** key theo `workspaceId`, nên "per-workspace" **không** phải phần còn thiếu. Phần còn thiếu là nó **không chia sẻ được** — mỗi user, mỗi browser một bản riêng, owner không đặt được default cho cả team, và xoá browser data là mất cấu hình. Đó mới là nội dung thật của OQ-2.

**Defer có chủ đích** (`epics.md`: *"OQ-1, OQ-2 → backlog"*).

#### OQ-3: Retention, right-to-delete & phơi nhiễm pháp lý (retention KHÔNG chỉ là storage)
**Document retention `[DONE]`** — migration 176 (`document_retention_days`, `auto_archive_enabled`, `document_retention_action`, `documents.archived_at`), Celery enforcement job (`app/tasks/celery_tasks/document_retention_task.py`), UI (`nowing_web/components/settings/data-retention-manager.tsx`), và tests (`tests/unit/tasks/test_document_retention_task.py`) đã implement.

**Memory / scraped-data retention `[GAP]`** — memory *bền* lưu dài hạn dữ liệu scrape (Reddit/YouTube/TikTok/Amazon) tạo **phơi nhiễm pháp lý (ToS/bản quyền/PII)**, KHÔNG chỉ là vấn đề dung lượng. Cần: **retention + right-to-delete cho MEMORY** (chưa có, khác doc retention), tách rõ trách nhiệm **self-host vs cloud**, và **chốt TRƯỚC GA cloud**.

**Gap:** `[GAP]` OQ-3 — Chưa có retention/right-to-delete cho `memories`; chưa tách trách nhiệm self-host vs cloud; chưa có đánh giá ToS/PII cho dữ liệu scrape lưu dài hạn. (Document retention `[DONE]`; memory / scraped-data retention `[GAP]`.)

#### OQ-4: Per-workspace MCP tool enable/disable toggle  `[RESOLVED 2026-07-25 — ĐÃ BUILD]`

> **⚠️ Cải chính 2026-07-25 (readiness P-6).** Bản cũ ghi *"Chưa có cơ chế cho phép workspace owner bật/tắt từng MCP tool… MCP server hiện expose toàn bộ tools cho mọi workspace"* và gắn `[GAP]`. **Không còn đúng** — verify code: bảng **`workspace_mcp_tool_settings`** (`app/db.py:1945`) với unique constraint **`uq_workspace_mcp_tool`** (`:1950`) + relationship `Workspace.mcp_tool_settings` (`:1919`, `:1965`). Story **`2-5-workspace-mcp-tool-enable-disable-toggle-new-gap` = `done`**, và `epics.md` coverage map đã tag `OQ-4 → E2.5 [DONE]`. Chỉ PRD còn sót.

**Câu trả lời:** có toggle per-workspace, lưu ở DB (không phải localStorage client). Đóng luôn `[ASSUMPTION]` *"MCP server không cần per-workspace tool toggle trong v1"* ở §9 — assumption đó **đã bị vượt qua**, không phải bị bác bỏ.

**Status:** `[RESOLVED]` OQ-4 → story `2-5` (done) · `AD-DEFER-3`.

#### OQ-5: Direct write-back action architecture  `[RESOLVED 2026-07-25 — CODE ĐÃ TRẢ LỜI]`

> **⚠️ Cải chính 2026-07-25 (readiness P-6).** Câu hỏi cũ: *"Direct Notion/Slack/Linear/Jira write-back nên implement như automation action types riêng, hay để `agent_task` gọi agent tools hiện có?"* — **code đã chọn xong**: action type **riêng**. Registry có `write_back_notion`, `write_back_slack`, `write_back_linear`, `write_back_jira` (`app/automations/actions/builtin/`). Story **`6-4-direct-write-back-actions-new-gap` = `done`**.

**Câu trả lời: action type riêng**, không đi qua `agent_task`. Lý do đúng như câu hỏi dự đoán — retry/audit/rollback cần một action có định danh riêng để retry được idempotent và audit trail chỉ tên đúng đích, chứ không lẫn vào một `agent_task` chung.

**Status:** `[RESOLVED]` OQ-5 → story `6-4` (done) · FR-18 · `AD-DEFER-2`. Ghi chú: `agent_task` **vẫn** làm được write-back, nên đây là nâng cấp chất lượng, không phải mở khoá năng lực mới.

#### OQ-6: Đồng bộ docs & artifacts với vision mới  `[DONE — 2026-08-01]`
README, `docs/`, `docs/project-overview.md` và `.env.example` đã được cập nhật phản ánh "long-term research memory" + **Nowing = sản phẩm**, **hosted deep-research engine** = năng lực cloud, self-host dùng được đầy đủ mà không cần engine (FR-38), license Apache-2.0 core + BSL 1.1 crawler engine.

- ✅ **Đã đóng:** `_bmad-output/planning-artifacts/epics.md` **đã tồn tại** (tạo 2026-07-25).
- ✅ **Đã đóng:** public docs đã sync — story **9.4** done.

**Status:** `[DONE]` OQ-6 — public docs synced; Story **9.4** (AR-10 mở rộng) done.

#### OQ-7: Câu hỏi mở từ phía ChainLens (story `42-3`)
ADR `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` để ngỏ ba câu hỏi mà **Nowing phải trả lời** cho ChainLens team:
1. Nowing có cần thêm endpoint riêng (`reason` / `answer` variants) hay chỉ `/api/v1/search` là đủ?
2. Nowing có muốn geo-access (ChainLens story `41-2`, reach nguồn bị region-block) không?
3. Format `costDollars` Nowing muốn parse thế nào — `done.usage.costDollars` trong terminal `done` frame? (Ảnh hưởng trực tiếp FR-37.)
4. ~~Engine có thể emit progress event theo phase không?~~ → **RÚT** (xem dưới).

**Status:** ✅ **ĐÃ TRẢ LỜI 2026-07-25, CẬP NHẬT 2026-08-04** — `oq7-answers-to-chainlens-2026-07-25.md` + `stories/42-3-verify-nowing-endpoint-needs.md` (verify code cả hai repo, **ba trong bốn câu lật so với giả định ban đầu**; cost contract được correct lại theo FR-37/Epic 9.2).

| Câu | Kết luận |
|---|---|
**(1)** endpoint riêng | **Không.** `/api/v1/search` là đủ — Nowing có runtime multi-agent riêng nên thêm `answer`/`reason` sẽ tạo **hai lớp reasoning xếp lên nhau** (đắt gấp đôi, khó truy nguyên citation). Cần độ sâu khác → thêm **giá trị `optimizationMode`**, không thêm endpoint. Giữ nguyên "một contract" của `AD-15`. |
**(2)** geo-access `41-2` | **Không phải bây giờ**, và **có trùng lặp**: Nowing đã có proxy registry + rotation + GeoIP match + WebRTC block + canvas hiding + DNS-over-HTTPS + CAPTCHA trong crawler BSL riêng (`app/proprietary/`, `app/utils/proxy/`). Phần không trùng là provider chain của engine. Chưa có khiếu nại cụ thể → **đừng build speculatively**. |
**(3)** format `costDollars` | ✅ **Chốt 2026-08-04**: `costDollars` nằm trong terminal `done` frame: `done.usage.costDollars` (USD float, toàn pipeline). Nowing parse thành `TokenUsage.cost_micros` (1 USD = 1_000_000 micros). Fallback 60k micros (~$0.06) khi field missing. Cần thêm **`resolvedMode`** (vì `auto` → SM-11a) và **`estimated: boolean`** (đo được vs ước lượng). Số thật 2026-08-02: speed $0.0353 · balanced $0.0482 · quality $0.0671. |
**(4)** progress theo phase | 🔄 **Nowing RÚT — lỗi ở phía Nowing.** ChainLens **đã emit** `progress` từ trước (`api.ts:414`, `:1298`, `:221` với `requestAcceptedAt`/`firstProgressAt`/`evidenceReadyAt`/`firstFactualChunkAt`) + `evidence_ready`. Parser Nowing chỉ dispatch 4 type (`error`/`done`/`block`/`updateBlock`) nên bỏ hết. Xem FR-38 và NFR-9 cho việc phải sửa. |

**Còn chặn gì:** chỉ **`42-1`** (`costDollars`) — chặn FR-37 / story `9.2` và việc chốt giá cloud. `42-3` đóng được sau khi ChainLens nhận bản trả lời.

**🔴 Ba phát hiện gửi ngược về backlog Nowing** (không phải việc của ChainLens):
1. **Nowing đang bỏ 6 loại SSE event** engine gửi: `progress`, `insufficientEvidence`, `partial`, `synthesizing`, `heartbeat`, `noop` → story `9.3` (progress) + `9.1a` (partial/insufficientEvidence).
2. **Nowing suy đoán lại thứ engine đã nói rõ.** Engine gửi `{type:'partial', state:'insufficient_evidence', reason}`; Nowing lại đoán bằng heuristic *"`if not answer and not sources: if saw_done → insufficient_evidence else → timeout`"* — gộp "không tìm ra bằng chứng" với "stream chết" vào một phép đoán. → story `9.1a`.
3. **Contract được document SAI trong tài liệu Nowing.** Docstring fixture của ChainLens ghi rõ *"NestJS `@Sse()` emits data-only frames — there is NO separate `event:` line"* và *"terminal marker là `{\"type\":\"done\"}`, KHÔNG phải `data: [DONE]`"*. PRD §4.9 FR-24, `AD-15`, SCP §3 đều mô tả `event:`/`data:` → sai. Nowing có nhánh xử lý `event:` **không bao giờ chạy**. → sửa trong story `9.1b`.

#### OQ-8: HR/Recruitment Vertical in Vietnam

1. ToS của VietnamWorks, TopCV, ITviec có cho phép automated access và commercial use cho research aggregator không?
2. Nowing có bị xếp là "employment service provider" / "môi giới việc làm" theo pháp luật Việt Nam không? Cần legal counsel opinion.
3. TopCV anti-bot POC có pass với budget chấp nhận được không? Nếu fail, có chấp nhận pilot 2 nguồn không?
4. ITviec salary ẩn (`Sign in to view salary`) ảnh hưởng value proposition thế nào? Có nên đăng nhập ITviec để lấy salary không?
5. Người dùng sẵn sàng trả bao nhiêu cho cross-platform job market research? Validate bằng customer interviews.
6. PII pipeline có đủ mạnh để xử lý phone/email/names trong JD của cả 3 nguồn không?

**Status:** `[OPEN]` — hard gates for P0 build.

## 9. Assumptions Index
- `[ASSUMPTION]` Self-hosted installs tắt billing theo mặc định (cloud dùng Stripe).
- `[SUPERSEDED 2026-07-25]` ~~MCP server không cần per-workspace tool toggle trong v1 vì workspace được chọn qua `nowing_select_workspace`.~~ → Đã build **rồi** (`workspace_mcp_tool_settings`, story `2-5` done). Assumption này bị **vượt qua**, không phải bị bác bỏ — chọn workspace và bật/tắt từng tool là hai việc khác nhau, và cái thứ hai hoá ra vẫn cần. Xem OQ-4.
- `[CORRECTED 2026-08-22]` ~~Agent có thể thực hiện write-back bằng cách gọi Notion/Linear/Slack/Jira tools trong `agent_task`, nên direct write-back action không cần thiết cho MVP.~~ → Direct write-back action type riêng đã được implement (`write_back_jira`, `write_back_linear`, `write_back_notion`, `write_back_slack`, `write_back_telegram` trong `app/automations/actions/builtin/`). `agent_task` vẫn là một lối tắt nhưng không phải primary path. FR-18 / OQ-5 `[DONE/RESOLVED]`.
- `[ASSUMPTION]` Citation highlight trong full editor có thể deferred vì citation panel đã cung cấp đủ context.
- `[CORRECTED 2026-07-24]` ~~Data retention có thể xử lý sau MVP vì storage chưa cấp bách.~~ → Retention là vấn đề **pháp lý** (ToS/bản quyền/PII cho dữ liệu scrape lưu dài hạn), **không** chỉ là dung lượng; phải chốt **retention + right-to-delete + self-host/cloud split TRƯỚC GA cloud** (xem OQ-3).
- `[CONFIRMED 2026-07-24]` Long-term memory lưu dưới dạng `Memory` rows + embedding `pgvector`, không graph database riêng — **đã đúng như vậy** (migration 177).
- `[CONFIRMED 2026-07-24]` 4 MCP memory tools (`nowing_remember`, `nowing_recall`, `nowing_continue_research`, `nowing_update_fact`) **đã được expose** cùng workspace context (`nowing_mcp/.../features/memory/`).
- `[CONFIRMED 2026-07-24]` Memory correction lưu `previous_content` + `corrected_content` (bảng `memory_versions`, migration 177); conflict resolution phức tạp deferred post-MVP.
- `[RESOLVED 2026-07-25]` ~~Migration 178 có thể đã xoá memory markdown cũ mà không backfill (FR-36).~~ → **Không mất dữ liệu**: 178 chưa apply prod (alembic 174), `memory_md` rỗng, snapshot đã tạo. Ràng buộc còn lại: giữ deploy-order mig177 → backfill → mig178.
- `[CORRECTED 2026-07-25]` ~~ChainLens Research là một connector/scraper ngang hàng Reddit/YouTube (FR-24 trong §4.2).~~ → ChainLens là **Deep-Research Engine**, dependency kiến trúc hạng nhất với contract riêng, cost accounting riêng, failure mode riêng. FR-24 chuyển sang **§4.9**, governed by `AD-15` (không còn `AD-3`).
- `[CORRECTED 2026-07-25]` ~~Chi phí ChainLens có thể tính theo giá phẳng $0.005/call.~~ → **Sai 2.1–3.3×**: `mode` default là `quality` (target cost $0.0105), deep research $0.0164; và các số đó tính trên DeepSeek stack chưa vào prod (prod = Gemini, đắt hơn ~3.5×). Phải meter theo `costDollars` thật — FR-37.
- `[CORRECTED 2026-07-25]` ~~Deep research latency = 57–136s (baseline FAIL 2026-07-18) là trạng thái hiện tại.~~ → Con số đó **có thể stale**: `ADR-DEEP-RESEARCH-SPEED` phases 1-7 đã ship nhưng `20-0`/`20-8` chưa đo lại. Trạng thái đúng = **"chưa biết"**. Nowing không giả định theo chiều nào — NFR-9 hai trạng thái A/B.
- `[ASSUMPTION 2026-07-25]` Giảm latency deep research **không cần owned index**. Ba đòn bẩy trên đường Epic 43 (`43-5` cache hit-rate, `43-2` planner-DAG parallel, `43-4` multi-stage rerank) + `29-5` cost routing là đủ để mở State B. "Index search" (Epic 26) là đòn bẩy thứ tư nhưng DEFERRED 0/7 gates và trùng NG-1 → **không tính vào kế hoạch**.
- `[ASSUMPTION 2026-07-25]` `balanced` mode đủ chất lượng cho phần lớn deep-research call, `quality` chỉ cần cho deliverable/deep request (D3). **Phải validate** trên `nowing_evals` ở story 9.3; nếu hồi quy đáng kể → revert về `quality` và ghi lại.
- `[ASSUMPTION 2026-07-25]` Nowing giữ **một** service API key cho ChainLens; ChainLens không cần biết end-user. Hạn mức/định danh end-user do Nowing quản (khớp `ADR-CHAINLENS-AS-NOWING-MICROSERVICE` §5).
- `[ASSUMPTION 2026-08-05]` ToS của VietnamWorks, TopCV, ITviec cho phép automated access và commercial use cho research aggregator. **Chưa xác nhận — hard gate.**
- `[ASSUMPTION 2026-08-05]` Pilot HR vertical không khiến Nowing bị xếp là employment service provider ở Việt Nam. **Chưa xác nhận — hard gate.**
- `[ASSUMPTION 2026-08-05]` TopCV anti-bot POC có thể pass bằng headless browser/residential proxy với cost ≤$0.05/job. **Chưa xác nhận.**
- `[ASSUMPTION 2026-08-05]` ITviec sẽ tiếp tục phục vụ HTML server-rendered không CAPTCHA ở production scale. **Chưa xác nhận.**
- `[ASSUMPTION 2026-08-05]` Lương từ title/salary range trên VietnamWorks đủ để tính `salary_consistency_score` mặc dù ITviec ẩn salary.
