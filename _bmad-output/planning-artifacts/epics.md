---
stepsCompleted:
  - step-01-validate-prerequisites.md
  - step-02-design-epics.md
  - step-03-create-stories.md
  - epic-07-chainlens-deep-research
  - epic-00-crypto-foundation
  - epic-09-advanced-crypto-agents
  - step-04-final-validation.md
lastEdited: '2026-04-23'
editHistory:
  - date: '2026-04-23'
    changes: '🚨 REALITY SYNC: Code audit phát hiện Epic 0 (Crypto Tool Infrastructure + 4 Base Sub-Agents) CHƯA được implement — `subagents/crypto/` directory rỗng, các tools `defillama.py`/`crypto_sentiment.py`/`crypto_news.py`/`contract_analysis.py` chưa tồn tại, `chat_deepagent.py:472` chỉ có `general_purpose_spec`. Update Epic 8 description (bỏ claim "document hóa implementation đã hoàn thành"). Thêm Epic 0 làm prerequisite chính thức cho Epic 8 + Epic 9. Update sprint plan Phase 1 dependency: Epic 0 phải xong TRƯỚC Epic 8 và Phase 1.'
  - date: '2026-04-23'
    changes: 'ALIGN với PRD v2026-04-23: (1) Renumber FR mapping cho Epic 9 sub-agents để khớp PRD (FR27-FR32 cho 6 sub-agents, FR33-FR35 cho orchestration meta). (2) Đổi Epic 8 testing FRs sang FR-T1/T2/T3 (testing prefix — không thuộc product FR sequence). (3) Thêm NFR-Q1-Q4 (Quality Gates: accuracy <3%, hallucination <1%, graceful degradation >98%, speed <90s P95). (4) Update Epic 8 + Epic 9 headers với NFRs covered. (5) Thêm Quality Gate ACs vào Story 8.2 (parallelism ratio < 1.3x), 8.3 (degradation rate > 98%), và Epic 9 stories (system prompt token check, hallucination check). Source: prd.md v2026-04-23 + product-brief-epic9-crypto-orchestra.md v2.'
  - date: '2026-04-23'
    changes: 'Thêm Epic 8 (Crypto Sub-Agents Integration Testing) và Epic 9 (Advanced Crypto Agents Batch 2): FR27-FR35, NFR-CS1-NFR-CS4, 9 stories (8.1-8.3, 9.1-9.6). Document hóa lại implementation đã hoàn thành từ crypto-subagents-guide.md.'
  - date: '2026-04-19'
    changes: 'Sync Epic 7 ACs với architecture.md để fix drift: (1) File path chuẩn (chainlens_research_service.py, app/agents/new_chat/tools/chainlens_research.py), (2) Story 7.1 bỏ "expose endpoint health" — Nowing chỉ consume Chainlens GET /api/v1/b2b/health, (3) Cache là in-process class variable (bỏ Redis option), (4) Timeout client 125s (buffer 5s cho NFR-P4 120s), (5) research() return dict (không phải string), (6) Story 7.2 fallback qua return tag {"status": "fallback"} cho LLM tự pick generate_report (không gọi trực tiếp), (7) Story 7.3 clarify intent detection qua LLM tool-calling (không phải explicit router).'
  - date: '2026-04-19'
    changes: 'Thêm Epic 7 Chainlens Deep Research Integration: FR24-FR26, NFR-P4, 4 stories (7.1-7.4) với đầy đủ Acceptance Criteria. Sync từ architecture.md 2026-04-18.'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
---

# Nowing - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Nowing, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Người dùng có thể tải lên các tệp tài liệu (PDF, TXT) vào không gian làm việc của họ.
FR2: Người dùng có thể xem lại danh sách các tài liệu đã tải lên trước đó.
FR3: Người dùng có thể xem được trạng thái tiến trình trích xuất (Đang đợi, Đang xử lý, Hoàn thành, Lỗi) của một tài liệu.
FR4: Người dùng có thể xóa một tài liệu khỏi không gian làm việc của họ.
FR5: Người dùng có thể tạo một phiên hỏi đáp (Chat Session) mới.
FR6: Người dùng có thể gửi câu hỏi dạng văn bản vào một phiên chat.
FR7: Người dùng có thể nhận được các luồng phản hồi trực tiếp (Streaming responses) từ AI bot theo thời gian thực.
FR8: Người dùng có thể xem lại danh sách các phiên trò chuyện trong quá khứ.
FR9: Người dùng có thể đọc lại toàn bộ nội dung tin nhắn của một phiên trò chuyện cụ thể.
FR10: Người dùng có thể đọc danh sách tài liệu và nội dung các khung chat cũ ngay cả khi ngắt kết nối hoàn toàn với internet.
FR11: Người dùng có thể nhận biết được trạng thái đồng bộ dữ liệu hiện tại của hệ thống (Ví dụ: Offline, Đang đồng bộ, Đã cập nhật xong).
FR12: Hệ thống có khả năng tự động bóc tách văn bản và tạo Vector Embeddings một cách bất đồng bộ ngầm khi tài liệu mới được tải lên.
FR13: Hệ thống có khả năng chặn yêu cầu (Rate Limit) nếu người dùng sử dụng vượt mức Token cho phép hoặc tải file quá quy định.
FR14: Người dùng có thể xác thực (Authentication) để đăng nhập và bảo vệ dữ liệu thuộc private workspace của họ.
FR15: Người dùng có thể xem bảng giá và các gói cước (Free, Pro) với quyền lợi tương ứng.
FR16: Người dùng có thể thanh toán an toàn qua Stripe Checkout để nâng cấp lên gói trả phí.
FR17: Hệ thống tự động cập nhật trạng thái Subscription khi Stripe gửi Webhook (thanh toán thành công/hủy/gia hạn).
FR18: Người dùng có thể mua một gift code tặng gói PRO cho người khác thông qua Stripe one-time payment.
FR19: Hệ thống tự động tạo gift code định dạng GIFT-XXXX-XXXX-XXXX sau khi payment thành công.
FR20: Người nhận quà có thể nhập gift code trên trang /redeem để kích hoạt subscription.
FR21: Hệ thống gia hạn subscription của người nhận theo công thức: max(current_period_end, now) + duration_months.
FR22: Hệ thống hỗ trợ luồng admin-approval fallback khi Stripe checkout thất bại: user tạo GiftRequest chờ duyệt, admin (superuser) có UI `/admin/gift-requests` để approve/reject — khi approve hệ thống tự động mint gift code và link vào request.
FR23: Người mua quà có thể xem lịch sử các gift codes đã mua của mình.

### NonFunctional Requirements

NFR-P1 (Time to First Token - TTFT): Hệ thống bắt buộc phải phản hồi ký tự đầu tiên từ AI Agent thông qua SSE dưới 1.5 giây kể từ khi user nhấn Submit.
NFR-P2 (Sync Latency): Thời gian bộ nhớ đệm Zero-cache đồng bộ thay đổi trạng thái từ Remote DB về Local IndexedDB không được vượt quá 3 giây.
NFR-P3 (Background Processing): Tác vụ bóc tách văn bản và tạo Vector Embeddings cho file <5MB phải xong trên Celery Queue dưới 30 giây.
NFR-P4 (Deep Research Timeout): Phản hồi tính năng deep research (qua Chainlens hoặc fallback) phải được deliver hoàn toàn trong vòng tối đa 120 giây. Nếu vượt timeout, hệ thống trả về thông báo lỗi thân thiện và gợi ý thử lại.
NFR-S1 (Data Segregation): RLS bắt buộc áp dụng. User ID không có quyền truy vấn dữ liệu tài khoản khác.
NFR-S2 (Local Storage Security): Dữ liệu Zero-cache bị xóa hoàn toàn khi "Log Out".
NFR-SC1 (Worker Scalability): Celery Worker phải "Stateless", có thể add thêm n-Workers mà code không can thiệp.
NFR-R1 (Offline Tolerance): Giao diện không trắng xoá khi mất mạng, đọc cache mượt như đang online.

### Additional Requirements

- Tận dụng Starter Template đã chọn: Official Next.js CLI & Custom Fast-Modern Async API (Cần lưu ý cho Epic 1 Story 1).
- Cấu trúc hệ thống Monorepo dùng Docker-compose để boot Postgres, Redis, Zero Server và Backend.
- Database Postgres sử dụng extension pgvector 0.8.2. Backend Python dùng SQLModel.
- Đồng bộ Realtime Local-first với rocicorp/zero 1.1.1 (truyền JWT từ API gateway sang bộ zero-client).
- Backend FastAPI phải trả về các REST API được bọc response chuẩn: `{ "data": ..., "error": ..., "meta": ... }`.
- Naming convention: FastAPI dùng snake_case nhưng output Pydantic phải set `by_alias=True` để convert ra camelCase phục vụ cho TypeScript Client. Database strictly snake_case.
- State Management: Sử dụng Zustand cho Global UI state, form xử lý với react-hook-form. Mọi fetch data chính từ Zero hook thay vì REST API. 
- API Streaming: Thực thi Server-Sent Events cho luồng trả lời Chatbot RAG.

### UX Design Requirements

UX-DR1: Triển khai Design System từ shadcn/ui & Tailwind CSS. Base color là Zinc/Slate (Dark mode #09090b); màu nhấn Accent là Indigo/Teal chuyên dùng cho button và thẻ citation. Typography với font Inter/Geist Sans và JetBrains Mono.
UX-DR2: Ràng buộc Transition/Animation thời gian đáp ứng cực ngắn (<150ms) đáp ứng trải nghiệm Khởi tác Tức thì trên toàn ứng dụng.
UX-DR3: Cấu trúc Layout đặc thù Tách viền (Dynamic Split-Pane) – phân bổ màn hình hiển thị cả khu vực dòng Chat và Trình đọc/view Document đồng thời; cần implement thư viện như `react-resizable-panels`.
UX-DR4: Action "Interactive Citation" – Khi người dùng click hoặc tương tác thẻ citation, hệ thống phải liên kết điều khiển panel Document auto-scroll hoặc highlight sang đúng vị trí đoạn text gốc mà không cần refresh.
UX-DR5: Xây dựng System Indicators mượt mà (Micro-Sync Indicator) - chấm vàng góc màn hình thể hiện Syncing, thanh process bar nhỏ đính kèm các file list đang được upload (Index ẩn). Không dùng blocking modal spinners chặn màn hình.
UX-DR6: Hiển thị giao diện "Graceful Degradation" linh hoạt khi Offline: tự chuyển các nút/icon qua xám muted, duy trì trải nghiệm đọc danh sách và chat history trong trạng thái mất kết nối mạng.

### FR Coverage Map

FR1: Epic 2 - Tải tài liệu lên workspace
FR2: Epic 2 - Xem danh sách tài liệu đã tải
FR3: Epic 2 - Theo dõi trạng thái tiến trình trích xuất
FR4: Epic 2 - Xoá tài liệu khỏi workspace
FR5: Epic 3 - Tạo phiên chat mới
FR6: Epic 3 - Gửi câu hỏi vào chat
FR7: Epic 3 - Nhận phản hồi Streaming tức thì
FR8: Epic 4 - Xem danh sách phiên chat cũ
FR9: Epic 4 - Đọc nội dung tin nhắn cũ
FR10: Epic 4 - Đọc tài liệu/chat khi ngắt mạng (Offline mode)
FR11: Epic 4 - Nhận biết trạng thái đồng bộ Zero-sync (Online/Offline/Syncing)
FR12: Epic 2 - Tiến trình nhúng Vector bất đồng bộ ngầm
FR13: Epic 2 - Chặn yêu cầu nếu vượt mức cho phép (Rate Limit)
FR14: Epic 1 - Xác thực và bảo vệ dữ liệu (Workspace)
FR15: Epic 5 - Xem bảng giá và lựa chọn gói cước
FR16: Epic 5 - Thanh toán qua Stripe Checkout
FR17: Epic 5 - Cập nhật trạng thái Subscription qua Webhook
FR18: Epic 6 - Gift purchase flow (Stripe one-time checkout)
FR19: Epic 6 - Gift code generation (GIFT-XXXX-XXXX-XXXX format)
FR20: Epic 6 - Gift code redemption endpoint
FR21: Epic 6 - Subscription extension formula
FR22: Epic 6 - Admin-approval fallback (GiftRequest)
FR23: Epic 6 - Gift purchase history endpoint
FR24: Epic 7 - Deep research trigger từ chat (keyword intent detection → chainlens_deep_research tool)
FR25: Epic 7 - Chainlens B2B API primary engine + auto-fallback generate_report(report_style="deep_research")
FR26: Epic 7 - Feature flag CHAINLENS_RESEARCH_ENABLED (admin enable/disable, no redeploy)
FR27: Epic 9 - tokenomics_analyst sub-agent: supply schedule, vesting, distribution, inflation/deflation
FR28: Epic 9 - whale_tracker sub-agent: large wallet movements, accumulation/distribution phases
FR29: Epic 9 - token_unlock_scheduler sub-agent: upcoming vesting events, selling pressure assessment
FR30: Epic 9 - yield_optimizer sub-agent: yield filter by risk, IL analysis, protocol security check
FR31: Epic 9 - governance_analyst sub-agent: DAO proposals, voting outcomes, governance health
FR32: Epic 9 - technical_analyst sub-agent: chart patterns, MA/RSI/MACD, support/resistance levels
FR33: Epic 9 - Parallel orchestration: main agent spawn multiple crypto sub-agents trong cùng 1 LangGraph ToolNode
FR34: Epic 9 - Smart agent selection: main agent chọn subset agents phù hợp (không spawn cả 10 khi không cần)
FR35: Epic 9 - Graceful degradation: 1+ agents fail nhưng main agent vẫn tổng hợp response từ agents thành công
FR-T1: Epic 0 - Test API integration: DeFiLlama, CoinGecko, GoPlus, CryptoPanic trả về data hợp lệ
FR-T2: Epic 0 - Test parallel execution: 4 sub-agents đồng thời, total time ≈ max(individual)
FR-T3: Epic 0 - Test error handling & fallback: rate limit / timeout → graceful degradation

### Crypto Sub-Agents NonFunctional Requirements

NFR-CS1 (Sub-agent token budget): System prompts cho mỗi sub-agent phải < 500 tokens để tiết kiệm cost khi spawn song song.
NFR-CS2 (Parallel execution): LangGraph ToolNode thực thi tất cả `task()` calls đồng thời trong 1 graph step — không tuần tự.
NFR-CS3 (API rate awareness): Tools phải handle CoinGecko 30 req/min, GoPlus 2000 req/day, CryptoPanic public tier gracefully.
NFR-CS4 (Stateless tools): Tất cả crypto tools có `requires=[]` — không phụ thuộc DB, không cần session state.

### Quality Gates (Epic 9 — North Star Metrics)

NFR-Q1 (Accuracy): Factual error rate cho crypto research responses (sample QA vs raw API ground truth) phải < 3%. Đo bằng manual QA + automated cross-check trên random sample 100 full-analysis queries mỗi 2 tuần production.
NFR-Q2 (Hallucination Rate): % responses chứa số liệu không xuất phát từ tool output (fabricated numbers) phải < 1%. Đo bằng pattern check + sample QA.
NFR-Q3 (Graceful Degradation): % requests có ≥ 1 sub-agent error nhưng main agent vẫn trả response đúng cấu trúc và mention nguồn unavailable phải > 98%. Degradation ladder gồm **3 tiers** (xem Story 0.6 / 0.6b): Tier 1 parallel (6 agents), Tier 2 natural sequential (1 agent/turn, khi có 429 trong cooldown), Tier 3 paced sequential (sleep 7s giữa agents + retry synthesis khi 3+ lần 429 liên tiếp). Tier 3 đảm bảo hoàn thành cho provider có RPM strict (ví dụ 10 RPM) — tradeoff latency ~42-50s cho 6 agents.
NFR-Q4 (Speed): P95 response time cho full-suite analysis (6+ agents spawned) phải < 90s — relaxed so với NFR-P1 vì cho phép Chainlens 125s timeout, tận dụng parallelism.

## Epic List

### Epic 1: Thiết lập Không gian riêng tư & Xác thực người dùng (User Workspace & Authentication)
Người dùng có thể đăng ký, đăng nhập và sở hữu một vùng không gian thao tác hoàn toàn tách biệt, bảo mật tuyệt đối cho dữ liệu cá nhân của họ. Epic này đặt nền móng hạ tầng (Next.js, FastAPI, Database) cho các tính năng tiếp theo.
**FRs covered:** FR14

#### Story 1.1: Khởi tạo Hạ tầng Dự án & Cơ sở Dữ liệu (Project Infrastructure & Database Init)
As a Kỹ sư Hệ thống,
I want thiết lập bộ khung Next.js, FastAPI, và cấu hình Docker-compose cho Postgres/Redis/ZeroServer,
So that toàn bộ nền tảng có thể khởi chạy môi trường phát triển (Dev Environment) một cách nhất quán cho tất cả các team.

**Acceptance Criteria:**
**Given** môi trường dự án mới
**When** chạy lệnh `docker-compose -f docker/docker-compose.dev.yml up -d`
**Then** các containers Postgres 16 (với pgvector), Redis, Zero-Server, FastAPI, và Next.js khởi tạo thành công
**And** database tự động migrate được schema ban đầu bao gồm bảng `users` với quy tắc `snake_case`.

#### Story 1.2: Triển khai Backend API Xác thực & JWT (Backend Auth API & JWT)
As a Người dùng,
I want gọi API an toàn để tạo tài khoản, đăng nhập và lấy mã Token (JWT),
So that hệ thống xác thực được danh tính của tôi và kích hoạt RLS (Row-level Security) bảo vệ dữ liệu trên Database Postgres.

**Acceptance Criteria:**
**Given** thông tin đăng nhập hợp lệ
**When** gửi request tới endpoint liên quan `/api/v1/auth/login`
**Then** hệ thống trả về mã JWT chứa userID hợp lệ, bọc trong cấu trúc Wrapper chuẩn `{ "data": {"token": "xxx"}, "error": null, "meta": null }`
**And** Cấu hình Row-Level Security (RLS) cơ bản cho bảng dữ liệu (người này không query được dữ liệu của người kia).

#### Story 1.3: Giao diện Đăng nhập & Tích hợp Token vào Zero-Client (Frontend Auth UI)
As a Người dùng,
I want sử dụng giao diện trơn tru để đăng ký/đăng nhập,
So that tôi nhận được Token và ngay lập tức kết nối tới hệ thống dữ liệu Local-first an toàn qua Zero Client.

**Acceptance Criteria:**
**Given** tôi đang ở trạng thái khách (Guest) trên UI
**When** tôi điền form đăng nhập thành công
**Then** giao diện lưu token vào cục bộ và tự động khởi tạo instance `ZeroClient` để bắt đầu mở cầu nối WebSockets.
**And** khi tôi nhấn nút "Đăng xuất" (Log Out), hàm `onLogout()` tự động thực thi dọn dẹp sạch (purge) toàn bộ IndexedDB, chặn bảo mật.
**And** Giao diện (Form đăng nhập, nút bấm) ứng dụng quy chuẩn UX-DR1 (Màu Base Zinc/Accent Indigo, font Inter).

### Epic 2: Quản lý Kho kiến thức & Trích xuất tự động (Knowledge Base Management & Ingestion)
Người dùng dễ dàng kéo thả các tệp PDF/TXT lên hệ thống; hệ thống tự động bóc tách dữ liệu mượt mà trong nền mà không làm gián đoạn công việc. Họ nắm rõ tiến độ nạp file và làm chủ khối lượng tài liệu của mình.
**FRs covered:** FR1, FR2, FR3, FR4, FR12, FR13

#### Story 2.1: Khởi tạo Kiến trúc Tác vụ nền & Xử lý PDF (Celery Worker & PDF Parser)
As a Kỹ sư Hệ thống,
I want xây dựng hệ thống worker bất đồng bộ (Celery + Redis) để bóc tách văn bản và tạo Vector Embeddings,
So that hệ thống API chính không bị nghẽn khi người dùng upload file, và có thể scale linh hoạt số lượng worker.

**Acceptance Criteria:**
**Given** phần mềm nhận một file PDF/TXT được đẩy vào hàng đợi (Queue)
**When** worker được phân công thực thi tác vụ
**Then** tiến trình phân giải text và nạp Vector qua pgvector hoàn thành dưới 30s (đối với file <5MB)
**And** trạng thái bản ghi tài liệu trên Database được cập nhật tuần tự (Processing -> Completed hoặc Error).

#### Story 2.2: Triển khai API Tải lên & Giới hạn Rate Limit (Upload API & Rate Limiting)
As a Kỹ sư Backend,
I want xây dựng endpoint FastAPI cho việc upload tài liệu kèm cơ chế Rate Limit,
So that server tiếp nhận an toàn và ngăn chặn upload spam quá mức hệ thống cho phép.

**Acceptance Criteria:**
**Given** người dùng đăng nhập hợp lệ
**When** đính kèm file và gửi POST tới `/api/v1/documents`
**Then** hệ thống check user token, lưu file vô Storage, tạo record ở DB với status 'Queue', và trigger đẩy task vào Celery
**And** nếu user push liên tục quá mức quy định (token/hạn mức tải), API sẽ trả về lỗi `429 Too Many Requests` bọc trong error format chuẩn.

#### Story 2.3: Giao diện Quản lý Tài liệu & Chỉ báo Syncing Khớp nối (Knowledge Base UI & Micro-Sync Indicators)
As a Người dùng,
I want thấy ngay lập tức danh sách tài liệu đang có và dễ dàng tải file mới lên,
So that tôi biết file nào đã sẵn sàng để chat, file nào đang chạy nền mà không bị gián đoạn thao tác chuột.

**Acceptance Criteria:**
**Given** người dùng ở giao diện không gian làm việc (Workspace)
**When** có một tài liệu đang được tải lên hoặc xử lý (Processing)
**Then** UX hiển thị thanh tiến trình nhỏ ở góc trên màn hình / cạnh danh sách (Micro-Sync Indicator) và không được chặn màn hình (UX-DR5)
**And** danh sách tài liệu được lấy thông qua Zero-client tự động update state realtime khi worker xử lý xong (FR2, FR3).

#### Story 2.4: API và Giao diện Xóa tài liệu khỏi Workspace (Delete Document Flow)
As a Người dùng,
I want chọn một tài liệu cũ và xóa hoàn toàn,
So that không gian lưu trữ được dọn dẹp và AI sẽ không bao giờ truy cập nội dung đó nữa.

**Acceptance Criteria:**
**Given** người dùng đang có tài liệu hiển thị trên danh sách
**When** người dùng click icon "Xoá" file
**Then** dữ liệu tài liệu lập tức bị loại bỏ khỏi giao diện UI do cơ chế optimism update của Zero
**And** trên Database, bản ghi bị xoá hoặc mark deleted, kèm theo việc dọn dẹp các Vectors rác liên quan trong background.

### Epic 3: Trò chuyện AI Hiện đại & Nguồn trích dẫn (AI Interactive Chat & Streaming Responses)
Người dùng có trải nghiệm truy vấn kho tài liệu "không độ trễ" (Instant Action) thông qua chat. Kết quả được stream về theo thời gian thực như một trợ lý xịn, tích hợp hệ thống Split-pane tinh tế để đối chiếu thẳng với Nguồn trích dẫn.
**FRs covered:** FR5, FR6, FR7

#### Story 3.1: API Tạo & Quản lý Phiên Chat (Chat Session API)
As a Người dùng,
I want tạo một phiên trò chuyện (chat session) mới với AI,
So that tôi có thể bắt đầu một định mức hội thoại mới, tách bạch hoàn toàn với các chủ đề cũ.

**Acceptance Criteria:**
**Given** cửa sổ Chat
**When** tôi chọn lệnh "New Chat" hoặc nhập thẳng vào input đầu tiên
**Then** hệ thống tạo một "Session" ID mới trên Database và lưu tin nhắn đầu tiên của user (FR5, FR6)
**And** trả về data qua REST API theo wrapper chuẩn để client chốt phiên làm việc.

#### Story 3.2: Khối RAG Engine & Cổng trả Streaming SSE (RAG Engine & SSE Endpoint)
As a Kỹ sư Backend,
I want xây dựng khối RAG query bằng pgvector và đẩy dữ liệu về dạng Server-Sent Events (SSE),
So that AI có thể phản hồi từng chữ một (streaming) ngay khi lấy được ngữ cảnh, và đảm bảo chuẩn NFR-P1 (< 1.5s).

**Acceptance Criteria:**
**Given** backend nhận một câu hỏi của user và Session ID
**When** gọi tới Model AI (ví dụ OpenAI/Gemini) với ngữ cảnh lấy từ VectorDB
**Then** API `/api/v1/chat/stream` trả dòng response trả về dưới định dạng sự kiện SSE (text/event-stream) (FR7)
**And** ký tự đầu tiên (First token) về tới client dưới 1.5s
**And** ở cuối luồng stream trả về đính kèm bộ Metadata (Array các id/đoạn trích dẫn được dùng).

#### Story 3.3: Giao diện Khung Chat & Tiếp nhận Streaming (Chat UI & SSE Client)
As a Người dùng,
I want thấy AI gõ từng chữ một vào màn hình chat kèm format Markdown đàng hoàng,
So that tôi không phải mòn mỏi nhìn biểu tượng Loading như các web đời cũ.

**Acceptance Criteria:**
**Given** tôi vừa bấm gửi câu hỏi "Ping"
**When** Next.js client mở luồng SSE kết nối về FastAPI
**Then** tin nhắn được append dần lên UI mượt mà với hoạt ảnh <150ms
**And** render được định dạng Markdown cơ bản (Bold, List, Code block) một cách trơn tru, không xộc xệch nhảy dòng khó chịu.

#### Story 3.4: Kiến trúc Split-Pane & Tương tác Trích dẫn (Split-Pane Layout & Interactive Citation)
As a Người dùng,
I want đọc khung chat ở một bên và văn bản gốc ở bên cạnh trên cùng 1 màn hình, bấm vào thẻ [1] ở chat là bên kia nhảy text tương ứng,
So that tôi có thể đối chiếu thông tin AI "bịa" hay "thật" ngay lập tức mà không phải tìm mỏi mắt.

**Acceptance Criteria:**
**Given** UI chia 2 bên (Split-Pane - bằng react-resizable-panels) - Chat trái, Doc phải (UX-DR3)
**When** AI trả lời xong có đính kèm cite `[1]`, tôi click vào `[1]`
**Then** bảng Document tự động đổi sang file tương ứng và auto-scroll + highlight dải vàng đúng dòng text đó (UX-DR4).

#### Story 3.5: Lựa chọn Mô hình LLM dựa trên Subscription (Model Selection via Quota)
As a Người dùng,
I want chọn cấu hình mô hình trí tuệ nhân tạo (VD: Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn mà không cần điền API key cá nhân,
So that tôi có thể dùng trực tiếp và chi phí sử dụng được trừ thẳng vào số Token thuộc gói cước của tôi.

**Acceptance Criteria:**
**Given** tôi đang trong giao diện Chat
**When** tôi bấm vào Dropdown "LLM Model"
**Then** hệ thống liệt kê các tùy chọn model do Nowing hỗ trợ kèm chi phí token mỗi lần gọi
**And** tuyệt đối không hiển thị ô nhập "Your API Key"
**And** nếu user dùng hết quota của Subscription khi gọi model cao cấp, hệ thống tự động chặn và bật thông báo Upgrade.

### Epic 4: Trải nghiệm Truy xuất Offline & Đồng bộ Local-First (Local-First & Offline Experience)
Người dùng tự do lướt xem danh sách tài liệu và đọc lịch sử chat ngay cả khi nằm ngoài vùng phủ sóng internet. Hệ thống cung cấp chỉ báo trạng thái rõ ràng (Syncing, Offline) giúp họ luôn an tâm về dữ liệu.
**FRs covered:** FR8, FR9, FR10, FR11

#### Story 4.1: Đồng bộ Danh sách Phiên Chat & Lịch sử Tin nhắn (Chat History Sync)
As a Người dùng,
I want danh sách lịch sử các phiên chat và tin nhắn bên trong tự động đồng bộ xuống máy tôi qua Zero-client,
So that tôi mở app lên là thấy ngay lập tức lịch sử cũ (FR8, FR9) và đọc liên tiếp không cần chờ load từ internet (FR10).

**Acceptance Criteria:**
**Given** thiết bị của tôi đã từng kết nối mạng trước đó
**When** tôi chọn một Session cũ (như hôm qua) trong Sidebar
**Then** hệ thống query trực tiếp từ IndexedDB cục bộ qua thư viện `@rocicorp/zero` và móc lên UI
**And** thời gian data mới từ server đẩy cập nhật xuống dưới Local Storage luôn đảm bảo dưới 3s (NFR-P2).

#### Story 4.2: Giao diện Phân rã Ân hạn khi ngắt mạng (Graceful Degradation Offline UI)
As a Người dùng,
I want hệ thống tự động khóa các tính năng cần internet như "Chat/Gửi tin/Upload" khi tôi mất wifi,
So that tôi không bị văng lỗi hay hiện màn hình đơ cứng, thay vào đó vẫn thong dong đọc nội dung cũ (NFR-R1).

**Acceptance Criteria:**
**Given** người dùng cấu hình ngắt mạng cố ý hoặc đột ngột mất wifi
**When** họ đang mở app
**Then** giao diện tự động bật mode Graceful Degradation: Input chat bị disable, nút Upload file bị mờ (muted xám)
**And** người dùng vẫn có thể click đọc văn bản trên màn Split-Pane thoăn thoắt không trễ (UX-DR6).

#### Story 4.3: Tích hợp Chỉ báo Trạng thái Mạng Toàn Cục (Global Network & Sync Indicators)
As a Người dùng,
I want thấy một icon nhỏ hoặc dải màu trực quan cho biết App đang Online, Offline, hay Syncing,
So that tôi chủ động biết ứng dụng có đang "sống" và "khớp nối" dữ liệu với đám mây hay không (FR11).

**Acceptance Criteria:**
**Given** app đang khởi chạy bình thường
**When** trạng thái kết nối mạng của Zero Client hoặc Browser thay đổi
**Then** Header hoặc góc dưới màn hình cập nhật icon (Xanh: Connected / Vàng: Syncing / Đỏ/Xám: Offline)
**And** thiết kế phải hòa hợp với bộ màu ZinC/Slate đã chọn, tuyệt đối không dùng thông báo (alert) nhảy ập vào mặt người dùng.

### Epic 5: Quản lý Gói cước, Thanh toán & Hạn mức Sử dụng (Subscription, Billing & Usage Management)
Hệ thống biến từ một ứng dụng tĩnh thành một nền tảng SaaS thương mại thông qua tích hợp thanh toán Stripe. Người dùng có thể xem bảng giá, chọn gói cước phù hợp, thanh toán an toàn và hệ thống tự động kiểm soát quota sử dụng dựa trên gói đăng ký, đảm bảo mô hình kinh doanh bền vững.
**FRs covered:** FR15, FR16, FR17

#### Story 5.1: Giao diện Bảng giá & Lựa chọn Gói Cước (Pricing & Plan Selection UI)
As a Khách hàng tiềm năng,
I want xem một bảng giá rõ ràng về các gói cước (ví dụ: Free, Pro, Team) với quyền lợi tương ứng,
So that tôi biết chính xác số lượng file/tin nhắn mình nhận được trước khi quyết định nâng cấp.

**Acceptance Criteria:**
**Given** tôi đang ở trang Pricing hoặc Modal nâng cấp tài khoản
**When** tôi lướt xem các tùy chọn gói cước
**Then** UI hiển thị các mức giá (monthly/yearly) rõ ràng cùng các bullets tính năng (FR15)
**And** thiết kế áp dụng chuẩn UX-DR1 (Dark mode, Accent Indigo) và có hiệu ứng hover mượt mà cho các pricing cards (<150ms).

#### Story 5.2: Tích hợp Stripe Checkout (Stripe Payment Integration)
As a Người dùng,
I want bấm "Nâng cấp" và được chuyển tới trang thanh toán an toàn,
So that tôi có thể điền thông tin thẻ tín dụng mà không sợ bị lộ dữ liệu trên máy chủ của Nowing.

**Acceptance Criteria:**
**Given** tôi chọn một gói cước trả phí ở Story 5.1
**When** tôi click nút "Nâng cấp qua Stripe"
**Then** hệ thống gọi API backend lấy `sessionId` của Stripe Checkout
**And** tôi được điều hướng (redirect) an toàn sang trang thanh toán chính thức do Stripe cung cấp (FR16, NFR-S1).

#### Story 5.3: Webhook & Cập nhật Trạng thái Gói cước (Stripe Webhook Sync)
As a Kỹ sư Hệ thống,
I want backend tự động hứng Webhook từ Stripe mỗi khi có thanh toán thành công, gia hạn, hoặc hủy gói,
So that database được cập nhật trạng thái Subscription của user (Active/Canceled) mà không cần can thiệp thủ công.

**Acceptance Criteria:**
**Given** hệ thống Stripe bắn ra một event (ví dụ `checkout.session.completed` hoặc `customer.subscription.updated`)
**When** endpoint `/api/v1/stripe/webhook` tiếp nhận sự kiện
**Then** hệ thống verify chữ ký bảo mật từ Stripe (Stripe-Signature) để đảm bảo không bị giả mạo
**And** cập nhật trường `subscription_status` và `plan_id` tương ứng của User trong Database (FR17).

#### Story 5.4: Hệ thống Khóa Tác vụ dựa trên Hạn Mức (Usage Tracking & Rate Limit Enforcement)
As a Kỹ sư Hệ thống,
I want những người dùng hết quota (vượt quá file upload hoặc số lượng tin nhắn) bị từ chối dịch vụ cho đến khi nâng cấp,
So that mô hình kinh doanh không bị lỗ do chi phí LLM và Storage, áp dụng theo FR13.

**Acceptance Criteria:**
**Given** người dùng ở gói miễn phí (Ví dụ: giới hạn 5 file)
**When** họ cố gắng upload file thứ 6
**Then** API `/api/v1/documents` từ chối xử lý và trả về lỗi `403/429` (Quota Exceeded)
**And** UI nhận phản hồi từ API và hiển thị một thông báo / Modal nhỏ để up-sell giới thiệu họ lên gói Pro để tải file tiếp.

### Epic 6: Tặng Gói Cước & Mua Quà (Gift Subscription)
Người dùng có thể mua gói PRO tặng cho người khác thông qua gift code sinh tự động sau Stripe payment. Người nhận quà vào trang /redeem để kích hoạt — tạo kênh acquisition organic không cần marketing, đồng thời hỗ trợ admin-approval fallback khi Stripe gặp sự cố.
**FRs covered:** FR18, FR19, FR20, FR21, FR22, FR23

#### Story 6.1: Database Migration — Bảng Gift Codes & Gift Requests
As a Kỹ sư Hệ thống,
I want tạo migration Alembic số 128 để thêm bảng `gift_codes` và `gift_requests` vào Postgres,
So that hệ thống có đủ cấu trúc dữ liệu để lưu trữ gift code và luồng admin-approval fallback mà không ảnh hưởng các bảng hiện có.

**Acceptance Criteria:**

**Given** môi trường backend đang chạy
**When** chạy `alembic upgrade head`
**Then** bảng `gift_codes` được tạo với các cột: `id UUID`, `code VARCHAR(16) UNIQUE`, `plan_id`, `duration_months`, `amount_paid`, `purchaser_id FK users`, `stripe_payment_intent_id`, `redeemer_id FK users`, `status VARCHAR(20) DEFAULT 'active'`, `expires_at`, `created_at`, `redeemed_at`
**And** bảng `gift_requests` được tạo với các cột: `id UUID`, `user_id FK users`, `plan_id`, `duration_months`, `status VARCHAR(20) DEFAULT 'pending'`, `gift_code_id FK gift_codes`, `created_at`, `updated_at`
**And** downgrade migration hoạt động sạch (drop cả 2 bảng)
**And** không có thay đổi nào đến các bảng hiện có (`users`, `subscription_requests`, v.v.)

#### Story 6.2: Backend API — Endpoint Tạo Gift Checkout
As a Người dùng đã đăng nhập,
I want gọi API để tạo Stripe Checkout session cho việc mua gift,
So that tôi được redirect sang trang thanh toán Stripe an toàn để hoàn tất việc mua quà.

**Acceptance Criteria:**

**Given** người dùng đã xác thực (JWT hợp lệ)
**When** gửi `POST /api/v1/stripe/create-gift-checkout` với body `{"plan_id": "pro_monthly", "duration_months": 3}`
**Then** backend tạo Stripe Checkout Session với `mode="payment"`, `price_data` động từ `GIFT_PRICING` config, `metadata.purchase_type="gift"`, `metadata.duration_months`, `metadata.purchaser_id`
**And** response trả về `{"data": {"checkout_url": "https://checkout.stripe.com/..."}, "error": null}` theo wrapper chuẩn
**And** nếu `plan_id` hoặc `duration_months` không hợp lệ, API trả về `400 Bad Request` với error message rõ ràng
**And** giá được tính đúng theo `GIFT_PRICING` (khớp với subscription pricing):
  - Pro: 1 tháng=$12, 3 tháng=$36, 6 tháng=$72, 12 tháng=$96 (annual rate, tiết kiệm $48)
  - Max: 1 tháng=$100, 3 tháng=$300, 6 tháng=$600, 12 tháng=$960 (annual rate, tiết kiệm $240)

#### Story 6.3: Backend Webhook — Fulfillment Gift Code sau Payment
As a Kỹ sư Hệ thống,
I want webhook handler tự động tạo gift code sau khi Stripe xác nhận thanh toán gift thành công,
So that purchaser nhận được code ngay lập tức mà không cần can thiệp thủ công từ admin.

**Acceptance Criteria:**

**Given** Stripe gửi event `checkout.session.completed` tới `/api/v1/stripe/webhook`
**When** `session.metadata.purchase_type == "gift"`
**Then** hàm `_fulfill_gift_purchase()` được gọi: generate code format `GIFT-XXXX-XXXX-XXXX` bằng `secrets.choice(ascii_uppercase + digits)`, tạo record trong bảng `gift_codes` với `status='active'`, `expires_at = now() + 1 year`
**And** code được đính kèm vào response email hoặc trả về trong session success URL
**And** nếu tạo code bị lỗi DB, hệ thống log error và KHÔNG mark Stripe payment là failed (idempotency)
**And** các webhook branch khác (`"subscription"`, `"token_topup"`) vẫn hoạt động bình thường — không bị ảnh hưởng

#### Story 6.4: Backend API — Endpoint Redeem Gift Code
As a Người dùng nhận quà,
I want gọi API để redeem gift code và gia hạn subscription của mình,
So that gói PRO được kích hoạt ngay lập tức theo công thức extension mà không cần liên hệ support.

**Acceptance Criteria:**

**Given** người dùng đã đăng nhập và có gift code hợp lệ
**When** gửi `POST /api/v1/stripe/redeem-gift` với body `{"code": "GIFT-ABCD-EFGH-IJKL"}`
**Then** backend verify: code tồn tại trong `gift_codes`, `status == 'active'`, `expires_at` chưa qua, `redeemer_id IS NULL`
**And** nếu hợp lệ: tính `new_expiry = max(current_period_end, now()) + timedelta(days=30 * duration_months)`, update `users.subscription_current_period_end = new_expiry`, update `users.plan_id = gift.plan_id`, đánh dấu `gift_codes.status = 'redeemed'`, ghi `redeemed_at = now()`
**And** response trả về `{"data": {"new_expiry": "2026-07-16T...", "plan_id": "pro_monthly"}, "error": null}`
**And** nếu code không tồn tại hoặc đã redeemed: trả về `400` với message "Gift code không hợp lệ hoặc đã được sử dụng"
**And** nếu code hết hạn (`expires_at` đã qua): trả về `400` với message "Gift code đã hết hạn"

#### Story 6.5: Backend API — Gift History & Admin Fallback
As a Người dùng & Admin,
I want API lấy danh sách gift codes đã mua và cơ chế tạo GiftRequest khi Stripe thất bại,
So that purchaser có thể tra cứu lịch sử quà đã mua, và admin có thể duyệt thủ công khi cần.

**Acceptance Criteria:**

**Given** người dùng đã đăng nhập
**When** gửi `GET /api/v1/stripe/gift-codes`
**Then** trả về danh sách tất cả gift codes mà `purchaser_id = current_user.id`, bao gồm các trường: `code`, `plan_id`, `duration_months`, `status`, `created_at`, `redeemed_at`, sắp xếp theo `created_at DESC`
**And** response tuân theo wrapper chuẩn `{"data": [...], "error": null, "meta": {"count": N}}`

**Given** người dùng gặp lỗi khi Stripe Checkout không khả dụng
**When** frontend gọi `POST /api/v1/stripe/request-gift` với body `{"plan_id": "pro_monthly", "duration_months": 3}`
**Then** hệ thống tạo record `gift_requests` với `status='pending'`, trả về `{"data": {"request_id": "...", "message": "Yêu cầu của bạn đang chờ admin xử lý."}, "error": null}`
**And** khi admin approve: tạo `gift_codes` record và gán `gift_requests.gift_code_id`, cập nhật `status='approved'`

#### Story 6.6: Frontend — Trang Mua Gift `/dashboard/[id]/gift`
As a Người dùng,
I want truy cập trang mua gift trong dashboard để chọn plan và thời hạn tặng,
So that tôi có thể mua gift cho bạn bè/đồng nghiệp một cách dễ dàng và được redirect sang Stripe để thanh toán.

**Acceptance Criteria:**

**Given** người dùng đã đăng nhập và truy cập `/dashboard/[search_space_id]/gift`
**When** trang load
**Then** hiển thị UI chọn plan (PRO Monthly) và duration (1 tháng / 3 tháng / 6 tháng / 12 tháng) với giá hiển thị rõ ($20 / $54 / $96 / $168)
**And** có nút "Mua Gift" khi click gọi `createGiftCheckout(plan_id, duration_months)` từ stripe API service
**And** sau khi nhận `checkout_url` từ API, tự động redirect sang Stripe Checkout
**And** nếu API lỗi, hiển thị toast error không làm crash trang
**And** UI áp dụng chuẩn design system (Zinc/Slate dark mode, Accent Indigo, font Inter) theo UX-DR1

**Given** người dùng quay lại sau khi thanh toán thành công (Stripe redirect về `/purchase-success`)
**When** trang success load
**Then** hiển thị thông báo thành công và hướng dẫn chia sẻ gift code (hoặc link đến `/dashboard/[id]/user-settings` để xem code)

#### Story 6.7: Frontend — Trang Redeem Gift `/redeem`
As a Người nhận quà,
I want truy cập trang public `/redeem`, nhập gift code và kích hoạt subscription,
So that tôi có thể nhận gói PRO được tặng mà không cần hiểu về Stripe hay billing.

**Acceptance Criteria:**

**Given** người nhận quà (có thể chưa đăng nhập) truy cập `/redeem`
**When** trang load
**Then** hiển thị form nhập gift code với placeholder "GIFT-XXXX-XXXX-XXXX" và nút "Kích hoạt"
**And** nếu chưa đăng nhập: hiển thị prompt "Đăng nhập để sử dụng gift code" với link đến trang login, sau khi đăng nhập redirect về `/redeem`

**Given** người dùng đã đăng nhập và nhập gift code hợp lệ
**When** click "Kích hoạt"
**Then** frontend gọi `POST /api/v1/stripe/redeem-gift`, hiển thị loading state
**And** khi thành công: hiển thị confirmation card với "🎉 Subscription đã được gia hạn đến [ngày]" và nút "Vào Dashboard"
**And** khi thất bại (code sai/hết hạn): hiển thị error message inline dưới input, không redirect

**Given** người dùng đã redeem thành công
**When** họ quay lại trang dashboard
**Then** sidebar hiển thị plan và ngày hết hạn subscription mới (cập nhật từ API user profile)

#### Story 6.8: Backend API — Admin Approve/Reject Gift Request
As a Superuser (admin),
I want có endpoint backend để liệt kê, duyệt (approve) và từ chối (reject) các `gift_requests` pending,
So that khi Stripe checkout gặp sự cố (admin-approval fallback), tôi có thể xử lý thủ công và cấp phát gift code cho người mua qua cơ chế admin-gated, đồng thời audit được ai đã approve/reject.

**Acceptance Criteria:**

**Given** admin (superuser) đã đăng nhập
**When** gọi `GET /api/v1/admin/gift-requests?status=pending` (JWT required, `is_superuser=True`)
**Then** trả về list `GiftRequestItem` gồm `id`, `user_id`, `user_email`, `plan_id`, `duration_months`, `status`, `gift_code_id`, `created_at`, `updated_at` sắp xếp theo `created_at DESC`
**And** query param `status` hợp lệ: `pending | approved | rejected | all` (default `pending`)
**And** user không phải superuser nhận `403 Forbidden`

**Given** admin duyệt một gift request
**When** gọi `POST /api/v1/admin/gift-requests/{request_id}/approve` (JWT required, `is_superuser=True`)
**Then** backend lock row `gift_requests` với `SELECT ... FOR UPDATE`, kiểm tra `status=pending`
**And** tạo `gift_codes` record mới (code unique, `status=active`, `plan_id`, `duration_months`, `amount_paid=GIFT_PRICING[plan_id][duration_months]`, `purchaser_id=gift_request.user_id`, `stripe_payment_intent_id=NULL`, `expires_at=now + 1 năm`)
**And** cập nhật `gift_request.status=approved`, `gift_request.gift_code_id=<new_gift_code_id>`, `gift_request.updated_at=now`
**And** response trả về `{"request_id": "...", "gift_code": "GIFT-XXXX-XXXX-XXXX", "plan_id": "...", "duration_months": N}`
**And** nếu `status != pending` → trả về `409 Conflict` với detail `"Request is already <status>."`
**And** nếu không tìm thấy request → `404 Not Found`

**Given** admin từ chối một gift request
**When** gọi `POST /api/v1/admin/gift-requests/{request_id}/reject` với body `{"reason": "..."}` (optional)
**Then** backend cập nhật `gift_request.status=rejected`, `gift_request.updated_at=now`
**And** không tạo gift code
**And** response trả về `GiftRequestItem` cập nhật (để UI refresh)
**And** nếu `status != pending` → `409 Conflict`

#### Story 6.9: Frontend — Admin Gift Requests UI `/admin/gift-requests`
As a Superuser (admin),
I want trang admin `/admin/gift-requests` để xem danh sách gift request chờ duyệt và approve/reject từng request,
So that khi user bấm "Yêu cầu gift" ở fallback mode, tôi có dashboard để xử lý nhanh và lấy được gift code để gửi cho người mua.

**Acceptance Criteria:**

**Given** admin (superuser) truy cập `/admin/gift-requests`
**When** trang load
**Then** hiển thị table gift requests gồm cột: Email user, Plan, Duration, Status, Created At, Actions (Approve/Reject)
**And** filter theo `status` (tabs: Pending / Approved / Rejected / All), default Pending
**And** sort mặc định theo `created_at DESC`

**Given** admin click nút **Approve** trên một row
**When** confirm dialog hiện ra và admin xác nhận
**Then** gọi `POST /api/v1/admin/gift-requests/{id}/approve`, disable nút trong lúc loading
**And** khi thành công: hiển thị toast success với gift code, copy gift code vào clipboard tự động, refresh table
**And** UI hiển thị cột `gift_code_id` và cho phép xem gift code qua modal chi tiết sau khi approved

**Given** admin click nút **Reject** trên một row
**When** confirm dialog hỏi "Reason (optional)" và admin submit
**Then** gọi `POST /api/v1/admin/gift-requests/{id}/reject` với body `{reason}`
**And** khi thành công: refresh table, hiển thị toast info

**Given** user thường (không phải superuser) truy cập `/admin/gift-requests`
**When** page load
**Then** middleware/layout redirect về `/dashboard` hoặc hiển thị 403 page (theo pattern `/admin/subscription-requests`)

### Epic 7: Nghiên cứu Chuyên sâu qua Chainlens (Chainlens Deep Research Integration)
Người dùng có thể kích hoạt luồng nghiên cứu web chuyên sâu trực tiếp từ chat bằng từ khóa tự nhiên; hệ thống sử dụng Chainlens B2B API làm engine chính với auto-fallback graceful khi không khả dụng, và DevOps có thể bật/tắt toàn bộ tính năng qua feature flag mà không cần deploy lại code.
**FRs covered:** FR24, FR25, FR26
**NFRs:** NFR-P4

#### Story 7.1: Backend Service Layer — ChainlensResearchService & Health Check
As a Kỹ sư Backend,
I want xây dựng `ChainlensResearchService` với các method `is_available()` và `research()` để **consume** Chainlens B2B API (Nowing là client, không expose endpoint mới),
So that các layer phía trên (LangGraph tool ở Story 7.2) có thể gọi service một cách đáng tin cậy và biết trạng thái Chainlens API mọi lúc.

**Acceptance Criteria:**
**Given** file `nowing_backend/app/services/chainlens_research_service.py` được tạo (~100 LOC)
**When** `ChainlensResearchService.is_available()` được gọi
**Then** method kiểm tra env var `CHAINLENS_RESEARCH_ENABLED` trước — nếu `false`/unset trả về `False` ngay lập tức (không có network call)
**And** nếu flag bật, gọi `GET {CHAINLENS_RESEARCH_API_URL}/api/v1/b2b/health` (timeout 3s) và trả về `True` chỉ khi HTTP 200

**Given** `CHAINLENS_RESEARCH_API_URL` và `CHAINLENS_RESEARCH_API_KEY` được set trong env
**When** `ChainlensResearchService.research(query: str, sources: list[str] | None = None)` được gọi
**Then** method gửi `POST {URL}/api/v1/b2b/research` với header `Authorization: Bearer {CHAINLENS_RESEARCH_API_KEY}` và body `{"query": query, "sources": sources or ["web"], "stream": false}`
**And** timeout client là **125 giây** (buffer 5s cho server-side timeout 120s theo NFR-P4)
**And** nếu HTTP 200 → trả về `dict` gồm 2 fields chính `{"message": str, "sources": list}` (parse trực tiếp từ `resp.json()`)

**Given** kết quả health check vừa được fetch
**When** lần gọi `is_available()` tiếp theo trong khoảng `CHAINLENS_HEALTH_CACHE_TTL` (default 30s)
**Then** trả về cached value, KHÔNG thực hiện network call
**And** cache được lưu **in-process class variable** (không dùng Redis) — pattern `_health_cache: tuple[bool, float]` với `time.monotonic()`

**Given** Chainlens API trả về lỗi (non-200, timeout, exception mạng)
**When** `research()` hoặc health check gặp lỗi
**Then** invalidate health cache ngay lập tức
**And** raise `ChainlensUnavailableError` với message ngắn gọn (không expose stack trace)
**And** log **warning** server-side (không log error)

**Given** `CHAINLENS_RESEARCH_API_URL` không được set hoặc rỗng
**When** `ChainlensResearchService` được import/khởi tạo
**Then** không raise exception — chỉ log warning một lần (startup warning); `is_available()` trả về `False` ngay không thực hiện network call

#### Story 7.2: LangGraph Tool — `chainlens_deep_research` + Fallback Logic
As a Kỹ sư AI/Backend,
I want tạo LangGraph tool `chainlens_deep_research` và đăng ký vào `BUILTIN_TOOLS`, tích hợp fallback tự động sang `generate_report(report_style="deep_research")`,
So that Agent graph có thể thực thi deep research một cách minh bạch bất kể trạng thái Chainlens API.

**Acceptance Criteria:**
**Given** file `nowing_backend/app/agents/new_chat/tools/chainlens_research.py` được tạo (~60 LOC)
**When** tool `chainlens_deep_research` được Agent invoke
**Then** tool gọi `ChainlensResearchService.is_available()` trước
**And** nếu `True`: gọi `ChainlensResearchService.research(query, sources)` và trả về `{"status": "success", "provider": "chainlens", "message": ..., "sources": ...}`
**And** nếu `False`: tool trả về `{"status": "fallback", "provider": "nowing", "message": "use generate_report..."}` để Agent tự động chọn `generate_report(report_style="deep_research", source_strategy="kb_search")` ở turn tiếp theo (không raise exception, không log error user-facing)

**Given** Chainlens API đang available nhưng trả về lỗi HTTP (5xx, timeout)
**When** `research()` raise `ChainlensUnavailableError`
**Then** tool catch exception, log warning ở server-side, trả về `{"status": "fallback", ...}` một cách im lặng
**And** user nhận được kết quả từ fallback mà không thấy thông báo lỗi liên quan đến Chainlens

**Given** tool `chainlens_deep_research` được định nghĩa
**When** module `nowing_backend/app/agents/new_chat/tools/registry.py` được load
**Then** tool xuất hiện trong `BUILTIN_TOOLS` dưới dạng `ToolDefinition(name="chainlens_deep_research", factory=lambda deps: create_chainlens_research_tool(), requires=[], enabled_by_default=True)`
**And** system prompt `_TOOL_INSTRUCTIONS["chainlens_deep_research"]` bao gồm mô tả khi nào dùng tool + hướng dẫn fallback handling
**And** system prompt `_TOOL_EXAMPLES["chainlens_deep_research"]` bao gồm ít nhất 2 example invocations
**And** `_ALL_TOOL_NAMES_ORDERED` được update để include `"chainlens_deep_research"` (sau `"web_search"`)

**Given** cả Chainlens và fallback `generate_report` đều fail
**When** exception xảy ra ở cả hai path
**Then** tool trả về error message thân thiện: "Không thể thực hiện nghiên cứu chuyên sâu lúc này. Vui lòng thử lại sau." (không expose stack trace)

**Note (UX clarification):** Trong tool có thể `dispatch_custom_event("research_status", ...)` để FE hiển thị loading indicator (Story 7.3), nhưng message phải **neutral** (vd: "Researching...") — KHÔNG mention "Chainlens unavailable" để giữ FR25 silent fallback.

#### Story 7.3: Agent Integration — Intent Detection & Streaming Deep Research Response
As a Người dùng,
I want gõ câu hỏi kèm từ khóa trigger ("deep research về X", "thorough investigation of Y") trong chat,
So that LangGraph Agent tự động nhận diện intent (qua **LLM tool-calling** dựa vào tool description trong system prompt) và kích hoạt tool `chainlens_deep_research`, streaming kết quả về giao diện trong vòng tối đa 120 giây.

**Implementation note:** Intent detection KHÔNG phải explicit regex router — dựa hoàn toàn vào LLM quyết định gọi tool dựa trên `_TOOL_INSTRUCTIONS["chainlens_deep_research"]` đã đăng ký ở Story 7.2. Story 7.3 tập trung vào **streaming UX + timeout handling** ở agent layer.

**Acceptance Criteria:**
**Given** người dùng gửi message chứa từ khóa trigger (ví dụ: "deep research", "thorough investigation", "nghiên cứu chuyên sâu")
**When** LangGraph Agent xử lý message
**Then** LLM dựa trên `_TOOL_INSTRUCTIONS` chọn tool `chainlens_deep_research` thay vì các tool RAG thông thường
**And** Agent bắt đầu stream kết quả về client qua SSE trong khi tool đang chạy (không block response)

**Given** tool `chainlens_deep_research` đang thực thi (có thể mất đến 120 giây)
**When** user nhìn vào chat UI
**Then** hiển thị indicator "Đang thực hiện nghiên cứu chuyên sâu..." (loading state khác biệt với streaming RAG thông thường) — emit qua `dispatch_custom_event("research_status", ...)` với message neutral
**And** kết quả stream về từng phần khi Chainlens trả về data (hoặc toàn bộ một lần nếu API không support streaming)

**Given** deep research vượt quá 120 giây (NFR-P4 timeout)
**When** request timeout
**Then** hệ thống trả về message thân thiện: "Nghiên cứu mất quá nhiều thời gian. Vui lòng thử câu hỏi ngắn hơn hoặc thử lại sau."
**And** SSE stream đóng sạch, không để connection treo

**Given** không có từ khóa trigger trong message
**When** Agent xử lý message bình thường
**Then** LLM KHÔNG chọn `chainlens_deep_research` — flow RAG thông thường hoạt động như cũ (không có regression)

#### Story 7.4: Feature Flag & Configuration — Admin Control không cần Redeploy
As a Admin/DevOps,
I want bật hoặc tắt tích hợp Chainlens bằng cách thay đổi biến môi trường `CHAINLENS_RESEARCH_ENABLED` và restart service (không cần rebuild/redeploy code),
So that có thể phản ứng nhanh khi Chainlens API có vấn đề hoặc cần rollback.

**Acceptance Criteria:**
**Given** `CHAINLENS_RESEARCH_ENABLED=false` (hoặc biến không tồn tại)
**When** user trigger deep research từ chat
**Then** hệ thống fallback sang `generate_report(report_style="deep_research")` hoàn toàn tự động
**And** không có log error, không có UI error — user chỉ thấy kết quả từ fallback

**Given** `CHAINLENS_RESEARCH_ENABLED=true` và đầy đủ `CHAINLENS_RESEARCH_API_URL` + `CHAINLENS_RESEARCH_API_KEY`
**When** service restart
**Then** `ChainlensResearchService.is_available()` trả về `True` và tool sử dụng Chainlens API làm primary

**Given** 4 env vars được document: `CHAINLENS_RESEARCH_API_URL`, `CHAINLENS_RESEARCH_API_KEY`, `CHAINLENS_RESEARCH_ENABLED`, `CHAINLENS_HEALTH_CACHE_TTL`
**When** DevOps đọc file `.env.example` hoặc deployment guide
**Then** tất cả 4 biến có giá trị mặc định an toàn (ví dụ: `CHAINLENS_RESEARCH_ENABLED=false`, `CHAINLENS_HEALTH_CACHE_TTL=30`) và comment giải thích mục đích

**Given** `CHAINLENS_RESEARCH_ENABLED=true` nhưng `CHAINLENS_RESEARCH_API_KEY` bị thiếu
**When** service khởi động
**Then** log warning rõ ràng: "CHAINLENS_RESEARCH_ENABLED=true nhưng CHAINLENS_RESEARCH_API_KEY chưa được cấu hình — feature sẽ fallback"
**And** `is_available()` trả về `False`, hệ thống hoạt động bình thường với fallback

---

### Epic 0: Crypto Foundation (Tool Infrastructure + Base Sub-Agents + Testing)
**Prerequisite cho Epic 9.** Triển khai 4 tool files + 4 base sub-agents đã được document trong `nowing_backend/docs/crypto-subagents-guide.md` nhưng chưa thực sự implement vào code (audit 2026-04-23). Bao gồm cả integration testing (Stories 0.4-0.6) để validate quality gates trước Phase 1.

> 🆕 **Added 2026-04-23 sau code audit** — không phải Epic mới product-wise, mà là "retroactive implementation" để close drift giữa documentation và code reality. Stories 0.4-0.6 (testing) được merge vào đây từ Epic 8 vì test là phần của foundation — không phải epic riêng.

**Blocks:** Epic 9 Phase 1
**NFRs:** NFR-CS1, NFR-CS2, NFR-CS3, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4

#### Story 0.1: Core Crypto Tool Infrastructure
📄 **Story file**: [`stories/0-1-crypto-tool-infrastructure.md`](./stories/0-1-crypto-tool-infrastructure.md)
As a backend developer,
I want 4 new crypto tool files registered in the tool registry,
So that sub-agents có thể query DeFiLlama, sentiment sources, news APIs, và contract analysis services.

**Files to create:**
- `nowing_backend/app/agents/new_chat/tools/defillama.py` — 5 tools: `get_defillama_protocol`, `get_defillama_tvl_overview`, `get_defillama_yields`, `get_defillama_stablecoins`, `get_defillama_bridges`
- `nowing_backend/app/agents/new_chat/tools/crypto_sentiment.py` — 2 tools: `get_cmc_sentiment` (Fear & Greed), `get_reddit_crypto_sentiment`
- `nowing_backend/app/agents/new_chat/tools/crypto_news.py` — 2 tools: `get_crypto_news` (CryptoPanic), `get_coingecko_token_info`
- `nowing_backend/app/agents/new_chat/tools/contract_analysis.py` — 2 tools: `get_contract_info`, `check_token_security` (GoPlus)

**Files to modify:**
- `nowing_backend/app/agents/new_chat/tools/registry.py` — register all 11 new tools dưới dạng `ToolDefinition` với `requires=[]`

**Reference:** `nowing_backend/docs/crypto-subagents-guide.md` có full code blueprint.

**Acceptance Criteria:**

**Given** 4 tool files được tạo
**When** inspect `BUILTIN_TOOLS` trong `registry.py`
**Then** có 11 new `ToolDefinition` entries (5 DeFiLlama + 2 sentiment + 2 news + 2 contract)
**And** mỗi entry có `requires=[]` (NFR-CS4)
**And** mỗi entry dùng `factory=lambda deps: create_xyz_tool()` pattern

**Given** tools được instantiate
**When** gọi từng tool với valid input (`get_defillama_protocol(protocol_slug="uniswap")`, `get_coingecko_token_info(coin_id="bitcoin")`, `check_token_security(token_address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", chain="ethereum")`, `get_crypto_news(currencies="BTC", limit=10)`)
**Then** trả về expected data structure theo guide
**And** handle rate limit / timeout / API unavailable gracefully (trả về `{"error": "..."}`)
**And** response time < 10s cho DeFiLlama `/protocols`, < 5s cho các endpoints khác

---

#### Story 0.2: Base Sub-Agents Implementation & Wiring
📄 **Story file**: [`stories/0-2-base-sub-agents.md`](./stories/0-2-base-sub-agents.md)
As a main agent,
I want 4 base crypto sub-agents registered (defillama_analyst, sentiment_analyst, news_analyst, smart_contract_analyst),
So that I can spawn specialists in parallel qua `task()` tool.

**Files to create:**
- `nowing_backend/app/agents/new_chat/subagents/crypto/__init__.py`
- `nowing_backend/app/agents/new_chat/subagents/crypto/defillama_spec.py`
- `nowing_backend/app/agents/new_chat/subagents/crypto/sentiment_spec.py`
- `nowing_backend/app/agents/new_chat/subagents/crypto/news_spec.py`
- `nowing_backend/app/agents/new_chat/subagents/crypto/smart_contract_spec.py`

Mỗi spec file export 3 constants: `{NAME}_NAME`, `{NAME}_DESCRIPTION`, `{NAME}_PROMPT` (theo pattern Story 9.1).

**Files to modify:**
- `chat_deepagent.py` (~line 450-472) — import 4 specs, build scoped tool lists, register vào `SubAgentMiddleware`

**Acceptance Criteria:**

**Given** 4 spec files được tạo
**When** inspect module exports
**Then** mỗi spec export đủ 3 constants (NAME/DESCRIPTION/PROMPT)
**And** mỗi PROMPT < 500 tokens — unit test verify bằng `tiktoken` (NFR-CS1)

**Given** `chat_deepagent.py` build sub-agent list
**When** server khởi động
**Then** `SubAgentMiddleware` register đúng 5 sub-agents: `general_purpose` + 4 crypto specialists
**And** mỗi crypto agent có scoped tool list (không phải toàn bộ tools)
**And** mỗi agent dùng shared `gp_middleware` stack

**Given** main agent nhận câu "Phân tích DeFi TVL của Uniswap"
**When** main agent gọi `task(agent="defillama_analyst", ...)`
**Then** sub-agent spawn successfully
**And** sub-agent chỉ có access DeFiLlama tools + supplementary (không có contract/news/sentiment tools)
**And** response trả về đúng structure theo system prompt

**Given** main agent nhận câu "Phân tích toàn diện $UNI"
**When** main agent orchestrate
**Then** main agent gọi parallel `task()` cho ít nhất 3 agents trong cùng 1 LangGraph ToolNode step (verify qua trace logs)
**And** total_time ≈ max(individual_times) — NFR-CS2 parallelism ratio < 1.3x

---

#### Story 0.3: Main Agent Orchestration Prompt Update
📄 **Story file**: [`stories/0-3-main-agent-prompt.md`](./stories/0-3-main-agent-prompt.md)
As a main agent,
I want clear instructions on when and how to spawn crypto sub-agents in parallel,
So that I can coordinate multiple specialists efficiently.

**Files to modify:**
- `nowing_backend/app/agents/new_chat/system_prompt.py` — thêm crypto section với lookup table + orchestration examples

**Acceptance Criteria:**

**Given** user yêu cầu "Phân tích toàn diện token $X"
**When** main agent xử lý request
**Then** system prompt có instruction gọi đồng thời 3-4 agents phù hợp (defillama + sentiment + news + smart_contract)
**And** có lookup table format: `agent_name | chuyên môn | trigger keywords`
**And** có ví dụ cụ thể về parallel task() calls

**Given** user hỏi câu đơn giản "Giá $BTC hôm nay?"
**When** main agent xử lý
**Then** main agent KHÔNG spawn multi-agent (chỉ gọi `get_live_token_data` trực tiếp)
**And** response nhanh, không overhead parallel spawn

---

#### Story 0.4: API Integration Tests
📄 **Story file**: [`stories/0-4-api-integration-tests.md`](./stories/0-4-api-integration-tests.md)
As a developer,
I want to verify each crypto tool connects to its API correctly,
So that I know the integration works before production deployment.

**Acceptance Criteria:**

**Given** DeFiLlama API available
**When** gọi `get_defillama_tvl_overview(limit=5)`
**Then** trả về ít nhất 5 protocols (`top_protocols`) với `tvl_usd > 0`
**And** response time < 10 giây (endpoint `/protocols` payload lớn)

**Given** CoinGecko API available (không bị rate limit)
**When** gọi `get_coingecko_token_info(coin_id="bitcoin")`
**Then** trả về `name="Bitcoin"`, `symbol="BTC"`, `price_usd > 0`

**Given** GoPlus API available
**When** gọi `analyze_token_security(token_address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", chain="ethereum")`
**Then** trả về `risk_level IN ["SAFE", "LOW", "MEDIUM", "HIGH"]`, `chain_id="1"` (mapped internal)
**And** response có các fields: `is_open_source`, `buy_tax_pct`, `sell_tax_pct`, `holder_count`

**Given** CryptoPanic public API available
**When** gọi `get_crypto_news(currencies="BTC", limit=10)`
**Then** trả về ít nhất 1 article trong `articles` với `title`, `published_at`, `source`, `votes`

---

#### Story 0.5: Parallel Execution Validation
📄 **Story file**: [`stories/0-5-parallel-execution-validation.md`](./stories/0-5-parallel-execution-validation.md)
As a developer,
I want to verify multiple sub-agents run truly in parallel,
So that full analysis doesn't take N times longer than a single agent.

**Acceptance Criteria:**

**Given** main agent nhận yêu cầu full analysis
**When** spawn 4 agents đồng thời: defillama_analyst, sentiment_analyst, news_analyst, smart_contract_analyst
**Then** tất cả 4 agents start trong cùng 1 LangGraph ToolNode (parallel batch)
**And** total execution time ≈ max(individual times), không phải sum của tất cả
**And** kết quả của tất cả 4 agents được tổng hợp trước khi trả lời user

**Given** trace logs từ 100 full-suite production queries
**When** tính tỷ số `total_time / max(individual_time)` cho mỗi query
**Then** tỷ số trung bình **< 1.3x** (NFR-Q2 parallelism gate, tương đương NFR-CS2)
**And** P95 response time của full-suite analysis (6+ agents) **< 90 giây** (NFR-Q4 speed gate)
**And** dashboard telemetry hiển thị 2 metrics này realtime cho ops team monitor

---

#### Story 0.6: Error Handling & Fallback Validation
📄 **Story file**: [`stories/0-6-error-handling-fallback.md`](./stories/0-6-error-handling-fallback.md)
As a developer,
I want to verify graceful degradation when APIs fail,
So that partial failures don't break the entire analysis.

**Acceptance Criteria:**

**Given** CoinGecko trả về 429 rate limit
**When** `get_coingecko_info` được gọi
**Then** trả về `{"error": "CoinGecko rate limit reached, try again in 1 minute"}`
**And** news_analyst fallback sang `web_search` để tìm thông tin thay thế

**Given** GoPlus API unavailable (timeout)
**When** `check_token_security` được gọi
**Then** trả về `{"error": "GoPlus API unavailable"}`
**And** smart_contract_analyst tiếp tục với `get_contract_info` + `web_search` — không crash

**Given** tất cả crypto sub-agents trả về kết quả (bao gồm partial errors)
**When** main agent tổng hợp
**Then** main agent vẫn trả về comprehensive analysis dựa trên dữ liệu available
**And** mention rõ nguồn nào unavailable trong response

**Given** sample 100 full-suite production queries trong 2 tuần
**When** tính % requests có ≥ 1 sub-agent error nhưng main agent vẫn trả response đúng cấu trúc
**Then** tỷ lệ **> 98%** (NFR-Q3 graceful degradation gate)
**And** dashboard có cột "degradation_rate" theo dõi metric này weekly

---

### Epic 9: Advanced Crypto Agents — Batch 2 (Crypto Orchestra)
Triển khai 6 sub-agents chuyên biệt bổ sung để hoàn thiện crypto analysis coverage: tokenomics, whale tracking, token unlocks, yield optimization, governance, và technical analysis. **Phased rollout** (Phase 1 Tokenomics+Yield → Phase 2 Whale+Governance → Phase 3 Unlock+TA), **Quality-first** (4 gates).
**FRs covered:** FR27, FR28, FR29, FR30, FR31, FR32, FR33, FR34, FR35
**NFRs:** NFR-CS1, NFR-CS4, NFR-Q1 (accuracy <3%), NFR-Q2 (hallucination <1%), NFR-Q3 (graceful degradation >98%), NFR-Q4 (speed <90s P95)

**Phase 1 Launch Criteria (Mary's decision — required before Phase 2):**
- 🎯 NFR-Q1 Accuracy < 3% (sample 100 queries, 2 weeks production)
- 🎵 NFR-Q2 Parallelism `total_time / max(individual_time)` < 1.3x
- 🔥 NFR-Q3 Graceful degradation > 98%
- 🧠 NFR-Q4 Hallucination rate < 1%

If any gate fails → rollback Phase 1, improve prompt/tool, không có hard deadline (quality-first).

**Common AC for ALL Stories 9.1-9.6:**

**Given** sub-agent được spawn
**When** đo system prompt token count
**Then** prompt < 500 tokens (NFR-CS1)
**And** tool registry entry có `requires=[]` (NFR-CS4)

**Given** 100 production responses của agent này
**When** QA sample factual claims vs raw tool output
**Then** factual error rate < 3% (NFR-Q1)
**And** số liệu fabricated (không có trong tool output) < 1% (NFR-Q2)
**And** agent luôn cite source từ tool output (không dựa trên parametric knowledge)

#### Story 9.1: Tokenomics Analyst Sub-Agent
📄 **Story file**: [`stories/9-1-tokenomics-analyst.md`](./stories/9-1-tokenomics-analyst.md) | **Phase 1**
As a crypto investor,
I want a specialist agent that analyzes token economics deeply,
So that I can evaluate long-term value accrual and inflation risks.

**Acceptance Criteria:**

**Given** user hỏi về tokenomics của token X
**When** main agent spawn `tokenomics_analyst`
**Then** agent phân tích: circulating supply vs total vs max supply, vesting schedule, token distribution (team/investors/community/treasury)
**And** đánh giá: inflation/deflation mechanics, token utility và demand drivers, buy pressure vs sell pressure
**And** tools được scope: `get_coingecko_info`, `chainlens_deep_research` (CryptoRank, Messari, official docs)
**And** system prompt < 500 tokens (NFR-CS1)

---

#### Story 9.2: Whale Tracker Sub-Agent
📄 **Story file**: [`stories/9-2-whale-tracker.md`](./stories/9-2-whale-tracker.md) | **Phase 2**
As a crypto trader,
I want to track large wallet movements and smart money flows,
So that I can identify accumulation/distribution phases early.

**Acceptance Criteria:**

**Given** user hỏi về whale activity cho token X
**When** main agent spawn `whale_tracker`
**Then** agent identify: known whale wallets (exchanges, funds, insiders), inflow/outflow patterns
**And** phân biệt: accumulation phase vs distribution phase dựa trên on-chain flow data
**And** tools: `chainlens_deep_research` (Arkham Intelligence, Nansen, Etherscan token holders)
**And** response bao gồm: net_flow_7d, large_transfers_24h, smart_money_signal

---

#### Story 9.3: Token Unlock Scheduler Sub-Agent
📄 **Story file**: [`stories/9-3-token-unlock-scheduler.md`](./stories/9-3-token-unlock-scheduler.md) | **Phase 3 (needs spike)**
As a crypto investor,
I want to know upcoming token unlock events,
So that I can anticipate selling pressure before it happens.

**Acceptance Criteria:**

**Given** user hỏi về vesting/unlock schedule của token X
**When** main agent spawn `token_unlock_scheduler`
**Then** agent trả về: upcoming unlock dates trong 30/90 ngày tới, % supply được unlock, cliff vs linear vesting
**And** historical price action sau các unlock events lớn trong quá khứ
**And** risk_assessment cho short-term holds dựa trên unlock magnitude (% of circulating supply)
**And** tools: `chainlens_deep_research` (TokenUnlocks.app, Vesting.is, CryptoRank) — *blocked on inline spike, see story file*

---

#### Story 9.4: Yield Optimizer Sub-Agent
📄 **Story file**: [`stories/9-4-yield-optimizer.md`](./stories/9-4-yield-optimizer.md) | **Phase 1**
As a DeFi investor,
I want personalized yield recommendations based on my risk tolerance,
So that I can maximize returns on idle capital safely.

**Acceptance Criteria:**

**Given** user có capital nhàn rỗi và risk preference (conservative/moderate/aggressive)
**When** main agent spawn `yield_optimizer`
**Then** agent filter DeFiLlama yields phù hợp risk level (stablecoins only cho conservative, LP farms cho aggressive)
**And** tính impermanent loss risk cho mỗi LP position recommendation
**And** so sánh protocol security score trước khi recommend (dùng GoPlus nếu available)
**And** tools: `get_defillama_yields`, `get_defillama_protocol`, `check_token_security`, `chainlens_deep_research` (fallback cho protocol context)

---

#### Story 9.5: Governance Analyst Sub-Agent
📄 **Story file**: [`stories/9-5-governance-analyst.md`](./stories/9-5-governance-analyst.md) | **Phase 2**
As a DAO participant,
I want to track active governance proposals and voting outcomes,
So that I can participate in protocol decisions and assess governance health.

**Acceptance Criteria:**

**Given** user hỏi về governance của protocol X
**When** main agent spawn `governance_analyst`
**Then** agent trả về: active proposals với deadline, vote outcomes (for/against/abstain), quorum status
**And** governance participation rate trend (increasing/decreasing), treasury size và management quality
**And** flag: controversial decisions, failed proposals, governance attacks, centralization risks
**And** tools: `chainlens_deep_research` (Snapshot.org, Tally, Commonwealth, protocol forum, governance forum)

---

#### Story 9.6: Technical Analysis Sub-Agent
📄 **Story file**: [`stories/9-6-technical-analyst.md`](./stories/9-6-technical-analyst.md) | **Phase 3 (needs spike)**
As a crypto trader,
I want chart pattern analysis and technical indicator signals,
So that I can time my entries and exits more effectively.

**Acceptance Criteria:**

**Given** user yêu cầu technical analysis cho token X
**When** main agent spawn `technical_analyst`
**Then** agent phân tích: key support/resistance levels, 50MA/200MA relationship, RSI (overbought >70/oversold <30), MACD signal line cross
**And** identify chart patterns nếu có: head & shoulders, cup & handle, double bottom/top, bull/bear flag
**And** đưa ra short-term outlook (bullish/bearish/neutral) với key levels cần watch
**And** tools: `get_live_token_data` (DexScreener price feed), `chainlens_deep_research` (TradingView analysis, CoinGecko charts) — *blocked on inline spike for OHLCV/TA tooling*
