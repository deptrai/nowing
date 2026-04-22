---
stepsCompleted:
  - step-01-init.md
  - step-02-discovery.md
  - step-02b-vision.md
  - step-02c-executive-summary.md
  - step-03-success.md
  - step-04-journeys.md
  - step-05-domain.md
  - step-06-innovation.md
  - step-07-project-type.md
  - step-08-scoping.md
  - step-09-functional.md
  - step-10-nonfunctional.md
  - step-11-polish.md
  - step-12-complete.md
  - step-e-01-discovery
  - step-e-02-review
  - step-e-03-edit
lastEdited: '2026-04-23'
editHistory:
  - date: '2026-04-23'
    changes: 'Readiness fix M2: Split NFR-Q1 (Accuracy < 3% — factual error rate) and NFR-Q5 (Smart Selection Accuracy ≥ 90% — orchestrator routing). Architecture §6 reconciled. Resolves implementation-readiness-report-2026-04-23 issue M2.'
  - date: '2026-04-23'
    changes: '🚨 Reality sync: Code audit phát hiện Crypto Foundation (4 base sub-agents + 11 tools) CHƯA implement (subagents/crypto/ rỗng, các tool files chưa tồn tại). Add note vào Growth Features về Epic 0 prerequisite. Sequence: Epic 0 (Foundation, ~2-3 weeks) → Epic 8 (Testing, ~1 week) → Epic 9 Phase 1 (Tokenomics + Yield, 4 weeks). Total realistic timeline: ~7-8 weeks từ kick-off thay vì 4 weeks Phase 1 standalone.'
  - date: '2026-04-23'
    changes: 'Thêm Epic 9 Crypto Orchestra (Advanced Crypto Sub-Agents): User Journey #8 (Crypto Power User), FR27-FR35 (9 FRs cho 6 sub-agents: Tokenomics, Whale Tracker, Token Unlock, Yield Optimizer, Governance, Technical Analyst + parallel execution + Chainlens integration), NFR-CS1-CS4 (token budget, parallel execution, API rate awareness, stateless tools), update Growth Features section. Source: product-brief-epic9-crypto-orchestra.md v2 stakeholder-resolved. Strategy: Phased rollout (Phase 1 Tokenomics+Yield → Phase 2 Whale+Governance → Phase 3 Unlock+TA), Quality-first (accuracy <3%, parallelism <1.3x, reliability >98%, hallucination <1%), reuse chainlens_deep_research cho web research.'
  - date: '2026-04-19'
    changes: 'Thêm Chainlens Deep Research Integration (sync từ architecture.md 2026-04-18): User Journey #7, FR24-FR26, NFR-P4, update Integration Requirements & Growth Features'
  - date: '2026-04-16'
    changes: 'Thêm Gift Subscription feature: 2 User Journeys (#5 Gift Purchaser, #6 Gift Recipient), 6 FRs (FR18-FR23), Growth Features update, Journey Requirements Summary update, Business Success update'
classification:
  projectType: web_app/api_backend
  domain: scientific
  complexity: medium
  projectContext: brownfield
inputDocuments:
  - docs/index.md
  - docs/project-overview.md
  - docs/architecture-backend.md
  - docs/architecture-web.md
  - docs/data-models.md
  - docs/api-contracts.md
  - docs/source-tree-analysis.md
  - docs/component-inventory.md
  - docs/development-guide.md
  - docs/deployment-guide.md
  - docs/integration-architecture.md
  - docs/project-scan-report.json
  - _bmad-output/project-context.md
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 13
workflowType: 'prd'
---

# Product Requirements Document - Nowing

**Author:** luisphan
**Date:** 2026-04-13

## Executive Summary

Nowing là nền tảng tìm kiếm và trích xuất ngữ cảnh (Context Extraction & Agentic RAG) AI-native, được thiết kế để giải quyết triệt để bài toán độ trễ và phân mảnh thông tin. Hệ thống cho phép người dùng và hạ tầng doanh nghiệp truy vấn dữ liệu theo thời gian thực một cách liền mạch, biến kho dữ liệu phức tạp thành các câu trả lời chính xác, an toàn và có thể hành động ngay lập tức. Thông qua kiến trúc Web App & Backend linh hoạt (Next.js & FastAPI), Nowing đảm bảo trải nghiệm người dùng tối ưu với cơ chế xử lý dữ liệu song song và quy trình lập luận AI chuyên sâu.

### What Makes This Special

Điểm khác biệt cốt lõi của Nowing nằm ở kiến trúc **Local-first** kết hợp cùng mô hình **Multi-agent Graph**. Bằng việc tích hợp công nghệ đồng bộ `@rocicorp/zero` (Zero-cache), nền tảng hỗ trợ đồng bộ dữ liệu tức thì và hoạt động hoàn hảo ngay cả khi offline (mất kết nối internet). Điều này khắc phục được điểm yếu cố hữu của các hệ thống RAG truyền thống: sự phụ thuộc vào kết nối mạng và độ trễ truy vấn cao. Đặc biệt, việc triển khai FastAPI & LangGraph cho phép hệ thống triển khai các luồng tác vụ Agentic linh hoạt đa bước, streaming kết quả về phía người dùng với tốc độ cao đồng thời bảo vệ nghiêm ngặt tính riêng tư của dữ liệu.

## Project Classification

- **Project Type:** Web App & API Backend
- **Domain:** Scientific / General (AI, Thông tin mạng, Retrieval-Augmented Generation)
- **Complexity:** Medium (Tích hợp Local-first Data Sync, Background Workers với Celery, Multi-agent orchestration)
- **Project Context:** Brownfield (Nền tảng kiến trúc đã thiết lập với Postgres/pgvector, Redis, Docker Stack và quy trình CI/CD hoàn thiện)

## Success Criteria

### User Success

Người dùng trải nghiệm được khoảnh khắc "Aha!" khi nhận được luồng phản hồi (streaming response) từ Agentic RAG ngay lập tức (dưới 1 giây kể từ khi submit) và có thể truy vấn ngữ cảnh/kho tài liệu ở dạng offline mượt mà không khác gì khi có mạng nhờ Zero-cache.

### Business Success

Hệ thống đạt tỷ lệ giữ chân (Retention rate) cao với tệp người dùng nghiên cứu chuyên sâu, đồng thời kiến trúc module hóa đủ linh hoạt để mở rộng quy mô (Scalability) và sẵn sàng đóng gói license nhắm tới thị trường B2B. Gift Subscription mở rộng kênh acquisition organically — người dùng hiện tại giới thiệu người mới thông qua việc tặng gói subscription.

### Technical Success

Cơ chế Local-first (Zero-cache) đồng bộ hàng nghìn vector và bản ghi dữ liệu ngầm mà không gây tác động hay đóng băng (freeze) UI client. Ở backend, các Celery workers xử lý pipeline nhúng dữ liệu (background embeddings) hoàn toàn cách ly, duy trì độ ổn định và trơn tru cho API phục vụ.

### Measurable Outcomes

- Độ trễ Time-to-First-Token (TTFT) < 1 giây kể cả với các truy vấn sử dụng đa AI Agent.
- Web Client truy cập bình thường toàn bộ thông tin đã lưu trữ khi offline.
- Tác vụ Embedding không gây nghẽn (bottleneck) hệ thống Chat.

## Product Scope

### MVP - Minimum Viable Product

- Tích hợp framework `@rocicorp/zero` cung cấp Local-first caching và realtime sync.
- Hỗ trợ khai thác truy vấn văn bản, lưu trữ lịch sử offline.
- Triển khai LangGraph Agents cơ bản (tìm, đọc, tổng hợp nội dung).

### Growth Features (Post-MVP)

- Hỗ trợ RAG đa định dạng (đọc file PDF, hình ảnh).
- Tích hợp tài liệu nội bộ, Chatbot riêng cá nhân hóa.
- Filter thông minh và tagging đa dạng để quản lý vector.
- Gift Subscription: Cho phép bất kỳ tài khoản nào mua gói subscription làm quà tặng (chọn plan + thời hạn), nhận gift code duy nhất, và người nhận redeem code để kích hoạt subscription từ ngày sử dụng.
- Deep Research via Chainlens: Tích hợp B2B API từ Chainlens làm engine chính cho tính năng "deep research" — người dùng gõ từ khóa trigger ("deep research", "thorough investigation") để kích hoạt nghiên cứu web chuyên sâu; auto-fallback về `generate_report(report_style="deep_research")` khi Chainlens không khả dụng.
- **Crypto Orchestra (Epic 9 — Advanced Crypto Sub-Agents)**: Mở rộng đội ngũ crypto sub-agents từ 4 (DeFiLlama, Sentiment, News, Smart Contract — Epic 1-2) lên 10 với 6 specialist agents mới chạy song song qua LangGraph SubAgentMiddleware: Tokenomics Analyst (vesting, supply, distribution), Whale Tracker (smart money flows), Token Unlock Scheduler (vesting events, sell pressure), Yield Optimizer (risk-adjusted DeFi yields), Governance Analyst (DAO proposals, voting outcomes), Technical Analyst (chart patterns, MA/RSI/MACD). Triển khai phased: Phase 1 Tokenomics+Yield → Phase 2 Whale+Governance → Phase 3 Unlock+TA. Quality-first (accuracy <3%, parallelism ratio <1.3x, hallucination <1%). Reuse `chainlens_deep_research` cho 5/6 agents — không scrape trực tiếp. **🚨 Prerequisite (audit 2026-04-23)**: Epic 0 (Crypto Foundation) phải implement trước — bao gồm Story 0.1 (4 tool files: defillama, crypto_sentiment, crypto_news, contract_analysis), Story 0.2 (4 base sub-agent specs + SubAgentMiddleware wiring), Story 0.3 (main agent orchestration prompt). Realistic total timeline: Epic 0 (~3-4 weeks incl. testing 0.4-0.6) + Phase 1 (~4 weeks) = **~7-8 weeks**.

### Vision (Future)

- Autonomous Proactive Agents: AI chạy nền thu thập nguồn thông tin hữu ích theo sở thích của người dùng để liên tục cập nhật kho ngữ cảnh cá nhân.

## User Journeys

### 1. Primary User - Success Path
- **Người dùng:** Alex - Chuyên viên Nghiên cứu Dữ liệu.
- **Tình huống:** Có hàng chục tài liệu phân mảnh và cần tổng hợp nhanh.
- **Hành trình:** Cài đặt và mở Nowing Web App -> Nạp hàng loạt tài liệu -> Hệ thống tự động phân tích và nhúng dữ liệu qua Celery workers/LangGraph API đồng bộ bằng Zero-cache trong nền -> Gõ truy vấn -> Nowing streaming câu trả lời tức thì kèm trích dẫn.

### 2. Primary User - Edge Case (Offline Mode)
- **Người dùng:** Alex (Trường hợp mất kết nối mạng).
- **Tình huống:** Cần tra cứu gấp dữ liệu đã nạp mà không có Internet.
- **Hành trình:** Mở Web App offline -> Toàn bộ dữ liệu ngữ cảnh đều khả dụng nhờ Zero-cache -> Truy vấn Local DB -> Giao diện phản hồi mượt mà không độ trễ, không lỗi "No Internet".

### 3. Admin / Operations User
- **Người dùng:** Jamie - Kỹ sư DevOps nội bộ.
- **Tình huống:** Quản lý tài nguyên, theo dõi tính ổn định khi traffic tăng cao.
- **Hành trình:** Giám sát hệ thống qua Docker Logs -> Nhận biết hàng đợi Celery có lượng công việc lớn -> Can thiệp/Scale up node không làm luồng chat của người dùng bị gián đoạn.

### 4. API Consumer / Developer
- **Người dùng:** Sam - Kỹ sư phần mềm.
- **Tình huống:** Xây dựng ứng dụng bên thứ ba tích hợp AI Agent của Nowing.
- **Hành trình:** Tham khảo API -> Gửi cấu trúc truy vấn vào endpoint FastAPI `/api/rag/stream` -> Nhận lại chuỗi sự kiện Server-Sent Events (SSE) theo thời gian thực -> Tích hợp dễ dàng nội dung streaming vào ứng dụng của mình.

### 5. Gift Purchaser
- **Người dùng:** Minh — Người dùng PRO muốn tặng gói subscription cho đồng nghiệp.
- **Tình huống:** Muốn mua gói PRO 3 tháng làm quà tặng sinh nhật.
- **Hành trình:** Truy cập trang Gift Purchase -> Chọn plan (PRO) và thời hạn (1/3/6/12 tháng) -> Thanh toán qua Stripe (one-time payment) -> Nhận gift code dạng `GIFT-XXXX-XXXX-XXXX` -> Chia sẻ code/link cho người nhận qua email hoặc tin nhắn. Khi Stripe không khả dụng, hệ thống tạo yêu cầu chờ admin duyệt (admin-approval fallback).

### 6. Gift Recipient
- **Người dùng:** Lan — Người nhận gift code từ Minh.
- **Tình huống:** Nhận được gift code và muốn kích hoạt gói PRO.
- **Hành trình:** Truy cập trang Redeem Gift (hoặc click link chứa code) -> Đăng nhập/đăng ký tài khoản -> Nhập gift code -> Hệ thống xác thực code (hợp lệ, chưa dùng, chưa hết hạn) -> Subscription được kích hoạt từ thời điểm redeem với thời hạn đầy đủ -> Nếu đang có subscription active, thời hạn được cộng dồn (extension formula: `new_expiry = max(current_period_end, now) + gift_duration`).

### 7. Power User - Deep Research via Chainlens
- **Người dùng:** Duy — Nhà phân tích nghiên cứu cần khảo sát toàn diện nhiều nguồn web.
- **Tình huống:** Cần báo cáo chuyên sâu về một topic mà context đã upload chưa đủ, cần khai thác thêm nguồn từ internet.
- **Hành trình:** Gõ câu hỏi trong chat kèm từ khóa trigger ("deep research về X" hoặc "thorough investigation of Y") -> LangGraph Agent nhận diện intent và gọi tool `chainlens_deep_research` -> Tool gọi Chainlens B2B API (`POST /api/v1/b2b/research`) với Bearer token auth -> Kết quả trả về và được stream dần tới người dùng trong vòng tối đa 120 giây. Nếu Chainlens API không khả dụng (feature flag tắt hoặc API down), hệ thống tự động fallback sang `generate_report(report_style="deep_research")` mà không báo lỗi.

### 8. Crypto Power User - Multi-Agent Crypto Orchestra
- **Người dùng:** Khoa — Crypto investor (long-term holder + active trader) cần phân tích toàn diện token trước khi mở position.
- **Tình huống:** Muốn đánh giá $UNI cho long position 6 tháng — cần biết tokenomics, vesting unlocks sắp tới, hoạt động whale gần đây, governance health, technical entry levels và DeFi yield opportunities — tất cả trong một câu hỏi.
- **Hành trình:** Gõ câu hỏi "Phân tích toàn diện $UNI cho quyết định long position 6 tháng" trong chat -> Main agent (orchestrator) nhận diện intent và spawn song song 6+ specialist sub-agents trong cùng 1 LangGraph ToolNode: `tokenomics_analyst` (vesting/supply), `whale_tracker` (smart money flows), `token_unlock_scheduler` (upcoming unlocks), `governance_analyst` (DAO proposals), `technical_analyst` (chart patterns), `yield_optimizer` (DeFi pools), cộng với các agents Epic 1-2 đã có (`defillama_analyst`, `news_analyst`, `sentiment_analyst`, `smart_contract_analyst`) -> Mỗi sub-agent có scoped tool list riêng và chạy đồng thời (total time ≈ max(individual)) -> Main agent tổng hợp kết quả thành response đa chiều có thể hành động ngay -> Stream về user trong vòng < 90s P95. Khi 1-2 agents fail (rate limit, timeout), main agent vẫn trả response hoàn chỉnh dựa trên data available và mention nguồn nào unavailable (graceful degradation > 98%).

### Journey Requirements Summary

- **Giao diện Client (Journey 1 & 2):** Đòi hỏi kiến trúc Frontend (Next.js) kết hợp chặt chẽ việc quản trị State và Local Offline Syncing `@rocicorp/zero`. Phải cung cấp tín hiệu (Indicator) về tiến trình đồng bộ dữ liệu tới file bộ nhớ cục bộ mà không gây khóa luồng chính (Main Thread).
- **Kiến trúc Server & DevOps (Journey 3 & 4):** Backend APIs cần được REST/SSE tối ưu; chuẩn Open-API contracts; và cách ly nghiêm ngặt giữa luồng Embedding Worker process cùng Data sync để không gây tắc nghẽn khả năng trả lời query.
- **Gift Purchase & Redemption (Journey 5 & 6):** Yêu cầu endpoint thanh toán one-time (Stripe `mode: "payment"` với `price_data` động), hệ thống sinh gift code cryptographically secure (`secrets.choice()`, format `GIFT-XXXX-XXXX-XXXX`), bảng `gift_codes` riêng biệt, trang redeem xác thực và kích hoạt subscription. Hỗ trợ admin-approval fallback khi Stripe env không khả dụng (cùng pattern với token topup và subscription upgrade).
- **Deep Research (Journey 7):** Yêu cầu `ChainlensResearchService` (~100 LOC) với method `is_available()` kiểm tra feature flag `CHAINLENS_RESEARCH_ENABLED` và API health; tool `chainlens_deep_research` đăng ký trong `BUILTIN_TOOLS`; timeout 120 giây; graceful fallback không gây lỗi user-facing.
- **Crypto Orchestra (Journey 8):** Yêu cầu 6 sub-agent spec files mới trong `app/agents/new_chat/subagents/crypto/` (tokenomics, whale, unlock, yield, governance, TA), mỗi spec ~50 LOC chỉ định nghĩa `name` + `system_prompt` (< 500 tokens). Wire qua `SubAgentMiddleware` trong `chat_deepagent.py`. Reuse `chainlens_deep_research` tool đã có cho 5/6 agents (whale, unlock, governance, TA, tokenomics — supplementary). Yield optimizer dùng deterministic tools (DeFiLlama, GoPlus). Parallel execution qua LangGraph ToolNode native batch. Telemetry logging cho 4 quality gates: accuracy < 3%, parallelism ratio < 1.3x, graceful degradation > 98%, hallucination rate < 1%.

## Domain-Specific Requirements

### Compliance & Regulatory
- **Quyền bảo mật dữ liệu:** Bảo vệ quyền riêng tư tuyệt đối cho tài liệu độc quyền của người dùng nhờ tận dụng kiến trúc Local-first (giảm thiểu luồng dữ liệu thô đẩy lên hạ tầng cloud không cần thiết).

### Technical Constraints
- **Kiểm soát tính chính xác (Accuracy):** Hệ thống LLM phải tuân thủ chặt chẽ ngữ cảnh được nạp (Strict Context Grounding), chống lại hiện tượng ảo giác (Hallucinations).
- **Phân bổ tài nguyên (Computational Resources):** Duy trì sự cô lập hoàn toàn giữa Celery workers (dành cho embed) và FastAPI server (dành cho API endpoints) để loại bỏ rủi ro nghẽn cổ chai.

### Integration Requirements
- Kiến trúc mở cho phép người dùng tự do lựa chọn các mô hình ngôn ngữ (OpenAI, Anthropic) do Nowing quản lý. Chi phí sử dụng Token sẽ được tự động trừ vào gói cước Subscription của người dùng (Tuyệt đối không hỗ trợ chức năng User tự nhập LLM API Key riêng nhằm kiểm soát chất lượng và doanh thu).
- **Chainlens B2B API:** Tích hợp external deep research API qua `POST /api/v1/b2b/research` (Bearer token auth). Health check tại `GET /api/v1/b2b/health` (public, cache 30 giây). Được bật/tắt qua feature flag `CHAINLENS_RESEARCH_ENABLED`. Các env vars liên quan: `CHAINLENS_RESEARCH_API_URL`, `CHAINLENS_RESEARCH_API_KEY`, `CHAINLENS_RESEARCH_ENABLED`, `CHAINLENS_HEALTH_CACHE_TTL`.

### Risk Mitigations
- **Phòng ngừa lỗi đọc file:** Cơ chế fallback thông minh phát hiện, báo lỗi cụ thể và tiếp tục với các file không trích xuất được text.
- **Giám sát dung lượng phía biên (Client):** Kiểm soát kích cỡ của IndexedDB hay Local DB để phòng ngừa Zero-cache làm ngốn bộ nhớ thiết bị của Client.

## Innovation & Novel Patterns

### Detected Innovation Areas
**Local-First Agentic RAG:** Sự kết hợp mới mẻ giữa RAG nhiều tác tử điều phối (Multi-Agent) cùng kiến trúc Local-first (thông qua `@rocicorp/zero`). Các hệ thống RAG truyền thống dựa hoàn toàn vào Cloud Database nên thường gặp độ trễ lớn và giới hạn về bộ nhớ cục bộ. Nowing đảo ngược mô hình này, đồng bộ ngữ cảnh (Context) trực tiếp về IndexedDB/SQLite ở biên (Client). Điều này mang lại cảm giác phản hồi tức thì (Instant) mà vẫn sở hữu khả năng suy luận đa tầng ở phía Backend (thông qua LangGraph).

### Market Context & Competitive Landscape
Đa số các công cụ RAG SaaS hiện tại phụ thuộc hoàn toàn vào Cloud (gây lo ngại về bảo mật tài liệu và phụ thuộc internet). Ngược lại, các công cụ Local (chạy LLM trên máy cá nhân) lại thiếu tính liên thông giữa nhiều thiết bị và giới hạn bởi phần cứng nội bộ. Nowing đánh vào khoảng trống ở giữa (Sweet Spot): Nắm giữ độ bảo mật và tốc độ của "Local", đồng thời khai thác sức mạnh khổng lồ của "Cloud LLM/Agents".

### Validation Approach
- **Đo lường TTFT:** Đo đạc "Time-to-First-Token", đặt mục tiêu luôn phản hồi dưới 1 giây nhờ việc bớt đi một bước gọi Database trung gian.
- **Kiểm thử Offline-to-Online:** Đánh giá khả năng hoạt động (đọc Context/State) bất chấp việc mất mạng và tự động phục hồi sự kiện khi có wifi trở lại.

### Risk Mitigation
- **Vấn đề đồng bộ dung lượng lớn:** Cấu trúc Local-first mang tới rủi ro là nếu kho dữ liệu người dùng lên tới hàng Gigabytes, việc tải Zero-cache ban đầu sẽ quá chậm.
- **Fallback (Giải pháp dự phòng):** Sử dụng cơ chế Partial Sync (Đồng bộ một phần) theo Filter/Tag, hoặc phân trang để tối ưu băng thông.

## Web App & API Backend Specific Requirements

### Project-Type Overview
Nowing kết hợp giữa kiến trúc Single Page Application (SPA) cực kỳ mượt mà trên Next.js và một Backend API vững chắc chuyên trị các tác vụ AI (FastAPI). Hai lớp này giao tiếp qua chuẩn REST/SSE và đặc biệt là hệ thống đồng bộ Local-first từ `@rocicorp/zero`.

### Technical Architecture Considerations
- **Kiến trúc SPA & Real-time:** Next.js sẽ đóng vai trò SPA cung cấp trải nghiệm liền mạch. Trạng thái ứng dụng được đồng bộ real-time mà không cần tải lại trang.
- **Browser Matrix (Hỗ trợ trình duyệt):** Yêu cầu bắt buộc trên trình duyệt hiện đại (Chrome 90+, Safari 15+, Edge 90+) vì dữ liệu Zero-cache nội bộ phụ thuộc vào WebAssembly và IndexedDB.
- **Performance Targets:** Giới hạn Time-to-First-Token (TTFT) ở mức dưới 1 giây. Tốc độ đồng bộ Local-DB dưới 2 giây cho một chunk dữ liệu mới.

### Endpoint Specifications
Cấu trúc API (FastAPI) bao gồm:
- `/api/v1/documents` (REST): Upload files, trích xuất text, đưa vào Celery tasks queuing.
- `/api/v1/chat` (SSE): Trả về luồng streaming answers từ các mô hình học máy theo thời gian thực.
- `/api/zero/sync` (WebSocket/Sync): Endpoint kết nối Rocicorp Zero Client để chia sẻ state.

### Authentication & Rate Limits
- **Auth Model:** Định danh qua token (JWt/Supabase Auth) để phân lập không gian làm việc (Workspace) của mỗi User.
- **Rate Limits:** Giới hạn số Token tải lên và Token trả lời để tránh nguy cơ phá vỡ hệ thống bằng cách lạm dụng Celery Worker.

### Data Schemas & Local Sync
- Cấu trúc Local Schema (phía Client) mô phỏng lại một tập con tối giản (Sub-set) của Remote Schema nhằm phục vụ riêng cho các thao tác Offline (Xem danh sách tài liệu, đọc và truy vấn lịch sử chat).

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**MVP Approach:** Problem-solving MVP (Tập trung giải quyết cốt lõi vấn đề: RAG cực nhanh nhờ sự hỗ trợ của Rocicorp Zero). Chứng minh được dữ liệu trích xuất thành công và LLM có thể trả lời tức thì (Streaming).
**Resource Requirements:** Nhóm nhỏ (1-2 kỹ sư Full-stack am hiểu kiến trúc Agent và Web Real-time).

### MVP Feature Set (Phase 1)
**Core User Journeys Supported:**
- User Tải File & Chờ trích xuất nền (Background extraction).
- User Hỏi đáp (Chat) dựa trên nội dung file đó với độ trễ (TTFT) < 1 giây.
- Tính năng xem lại lịch sử Chat ngay khi Offline (Zero-cache).
- Đăng ký và thanh toán gói cước Subscription thông qua Stripe để nâng cấp/quản lý hạn mức sử dụng.

**Must-Have Capabilities:**
- Giao diện thao tác Upload File (PDF/TXT cơ bản).
- Pipeline xử lý nền (Celery queue cho Embedding).
- Chức năng Chatbot gọi Stream API từ Agent.
- Local Database (Zero-cache) lưu được `Documents` và `Messages` cơ bản.
- Hỗ trợ duy nhất 1 LLM Provider mạnh mẽ ở giai đoạn đầu (Ví dụ: OpenAI / gpt-4o) để đảm bảo không bị phân tán.
- Tích hợp cổng thanh toán Stripe xử lý Subscriptions và giao diện Pricing/Usage Tracking.

### Post-MVP Features

**Phase 2 (Growth):**
- Đăng nhập nhiều Workspaces (Làm việc nhóm).
- Phân luồng quyền File (RBAC).
- Cho phép người dùng chuyển đổi linh hoạt giữa các mô hình LLM (như Claude 3.5 Sonnet, GPT-4) được cung cấp sẵn, tích hợp thẳng với hệ thống tính phí quota.

**Phase 3 (Expansion):**
- Tích hợp thêm Data Sources (Google Drive, Notion, Slack).
- Mở rộng Agent System: Agent tự biên tập bài viết dài, Agent tổng hợp nghiên cứu (Research Agent).
- API Keys cho bên thứ ba tích hợp (Consumer API access).

### Risk Mitigation Strategy
- **Technical Risks:** Ở MVP, chỉ chạy 1 Worker tập trung với logic Queue đơn giản nhất để giảm rủi ro về Scale.
- **Market Risks:** Đặt một bộ định tuyến trạng thái UI rõ ràng hiển thị "Offline", "Syncing", "Online" để giải tỏa sự khó hiểu của User về Local-first.
- **Resource Risks:** Tận dụng tối đa bộ Docker-compose dựng sẵn và component UI mở. Hạn chế thiết kế lại từ đầu.

## Functional Requirements

### Document Management
- **FR1:** Người dùng có thể tải lên các tệp tài liệu (PDF, TXT) vào không gian làm việc của họ.
- **FR2:** Người dùng có thể xem lại danh sách các tài liệu đã tải lên trước đó.
- **FR3:** Người dùng có thể xem được trạng thái tiến trình trích xuất (Đang đợi, Đang xử lý, Hoàn thành, Lỗi) của một tài liệu.
- **FR4:** Người dùng có thể xóa một tài liệu khỏi không gian làm việc của họ.

### Chat & AI Interaction
- **FR5:** Người dùng có thể tạo một phiên hỏi đáp (Chat Session) mới.
- **FR6:** Người dùng có thể gửi câu hỏi dạng văn bản vào một phiên chat.
- **FR7:** Người dùng có thể nhận được các luồng phản hồi trực tiếp (Streaming responses) từ AI bot theo thời gian thực.
- **FR8:** Người dùng có thể xem lại danh sách các phiên trò chuyện trong quá khứ.
- **FR9:** Người dùng có thể đọc lại toàn bộ nội dung tin nhắn của một phiên trò chuyện cụ thể.

### Offline & Synchronization Capabilities
- **FR10:** Người dùng có thể đọc danh sách tài liệu và nội dung các khung chat cũ ngay cả khi ngắt kết nối hoàn toàn với internet.
- **FR11:** Người dùng có thể nhận biết được trạng thái đồng bộ dữ liệu hiện tại của hệ thống (Ví dụ: Offline, Đang đồng bộ, Đã cập nhật xong).

### Background Processing & System Limits
- **FR12:** Hệ thống có khả năng tự động bóc tách văn bản và tạo Vector Embeddings một cách bất đồng bộ ngầm khi tài liệu mới được tải lên.
- **FR13:** Hệ thống có khả năng chặn yêu cầu (Rate Limit) nếu người dùng sử dụng vượt mức Token cho phép hoặc tải file quá quy định.
- **FR14:** Người dùng có thể xác thực (Authentication) để đăng nhập và bảo vệ dữ liệu thuộc private workspace của họ.

### Pricing & Subscription
- **FR15:** Hệ thống hiển thị bảng giá (Pricing) cho các gói cước với những đặc quyền về giới hạn tải file/nhắn tin khác nhau.
- **FR16:** Người dùng có thể đăng ký gói cước và thanh toán an toàn thông qua cổng Stripe.com.
- **FR17:** Hệ thống tự động theo dõi lượng sử dụng (Usage Tracking) và cập nhật trạng thái gói cước (Active/Canceled) qua Stripe Webhook.

### Gift Subscription
- **FR18:** Người dùng (bất kỳ tài khoản nào, kể cả FREE) có thể mua gift subscription bằng cách chọn plan (PRO) và thời hạn (1, 3, 6, hoặc 12 tháng), thanh toán one-time qua Stripe.
- **FR19:** Hệ thống tạo gift code duy nhất (format `GIFT-XXXX-XXXX-XXXX`, 36^12 tổ hợp, cryptographically secure) sau khi thanh toán thành công hoặc admin duyệt.
- **FR20:** Người mua có thể xem gift code và link redeem để chia sẻ cho người nhận. Gift code có thời hạn sử dụng 90 ngày kể từ ngày tạo.
- **FR21:** Người nhận có thể redeem gift code trên trang Redeem Gift (hoặc qua link chứa code). Hệ thống xác thực code hợp lệ, chưa sử dụng, và chưa hết hạn trước khi kích hoạt.
- **FR22:** Khi redeem thành công, subscription được kích hoạt từ thời điểm redeem với thời hạn đầy đủ. Nếu người nhận đã có subscription active, thời hạn được cộng dồn (`new_expiry = max(current_period_end, now) + gift_duration`).
- **FR23:** Khi Stripe env không khả dụng, hệ thống cho phép submit gift request để admin duyệt thủ công (admin-approval fallback, cùng pattern với token topup và subscription upgrade).

### Chainlens Deep Research
- **FR24:** Người dùng có thể kích hoạt tính năng deep research từ chat bằng cách sử dụng các từ khóa trigger ("deep research", "thorough investigation", v.v.). LangGraph Agent tự động nhận diện intent và gọi tool `chainlens_deep_research`.
- **FR25:** Hệ thống sử dụng Chainlens B2B API (`POST /api/v1/b2b/research`) làm primary engine cho deep research. Khi Chainlens không khả dụng (feature flag tắt, API down, hoặc health check thất bại), hệ thống tự động fallback sang `generate_report(report_style="deep_research")` mà không hiển thị lỗi cho người dùng.
- **FR26:** Admin/DevOps có thể bật hoặc tắt tích hợp Chainlens bằng cách set/unset biến môi trường `CHAINLENS_RESEARCH_ENABLED` mà không cần deploy lại code.

### Crypto Orchestra — Advanced Crypto Sub-Agents (Epic 9)
- **FR27 (Tokenomics Analyst):** Hệ thống cung cấp sub-agent `tokenomics_analyst` chuyên phân tích token economics: circulating vs total vs max supply, vesting schedule, distribution (team/investors/community/treasury), inflation/deflation mechanics, demand drivers. Tools scoped: `get_coingecko_token_info`, `chainlens_deep_research` (Messari, CryptoRank, official docs). System prompt < 500 tokens.
- **FR28 (Whale Tracker):** Hệ thống cung cấp sub-agent `whale_tracker` theo dõi large wallet movements và smart money flows: known whale wallets (exchanges, funds, insiders), inflow/outflow patterns, accumulation vs distribution phases. Tools scoped: `chainlens_deep_research` (Arkham, Nansen, Etherscan token holders).
- **FR29 (Token Unlock Scheduler):** Hệ thống cung cấp sub-agent `token_unlock_scheduler` track upcoming vesting events: unlock dates, % supply unlocked, historical price action sau unlock events, sell pressure assessment cho short-term holds. Tools scoped: `chainlens_deep_research` (TokenUnlocks.app, Vesting.is, CryptoRank).
- **FR30 (Yield Optimizer):** Hệ thống cung cấp sub-agent `yield_optimizer` đề xuất DeFi yields theo risk preference (conservative/moderate/aggressive): filter theo risk level, tính impermanent loss cho LP positions, so sánh protocol security score. Tools scoped: `get_defillama_yields`, `get_defillama_protocol`, `check_token_security`.
- **FR31 (Governance Analyst):** Hệ thống cung cấp sub-agent `governance_analyst` theo dõi DAO governance: active proposals, voting outcomes, governance participation rate, treasury size/management, flag controversial decisions. Tools scoped: `chainlens_deep_research` (Snapshot.org, Tally, Commonwealth, protocol forums).
- **FR32 (Technical Analyst):** Hệ thống cung cấp sub-agent `technical_analyst` phân tích chart patterns và technical indicators: support/resistance levels, 50MA/200MA cross, RSI overbought/oversold, MACD signals, chart patterns (head & shoulders, cup & handle, double bottom/top). Tools scoped: `get_live_token_data` (DexScreener), `chainlens_deep_research` (TradingView, CoinGecko charts).
- **FR33 (Parallel Orchestration):** Main agent có khả năng spawn multiple crypto sub-agents song song qua `task()` tool trong cùng 1 LangGraph ToolNode khi user yêu cầu phân tích toàn diện ("phân tích toàn diện $X", "comprehensive analysis"). Total execution time ≈ max(individual times), không phải sum.
- **FR34 (Smart Agent Selection):** Main agent system prompt có instruction để chọn subset agents phù hợp với câu hỏi cụ thể (không spawn cả 10 agents khi user chỉ hỏi về 1 khía cạnh). Lookup table: agent name → chuyên môn → trigger keywords.
- **FR35 (Graceful Degradation):** Khi 1 hoặc nhiều sub-agents fail (rate limit 429, timeout, API unavailable), main agent vẫn tổng hợp response từ các agents thành công và mention rõ nguồn nào unavailable trong response — không crash toàn bộ analysis.

## Non-Functional Requirements

### Performance
- **NFR-P1 (Time to First Token - TTFT):** Hệ thống bắt buộc phải phản hồi ký tự đầu tiên từ AI Agent thông qua SSE dưới 1.5 giây kể từ khi user nhấn Submit.
- **NFR-P2 (Sync Latency):** Thời gian bộ nhớ đệm Zero-cache đồng bộ thay đổi trạng thái (ví dụ một message mới) từ Remote DB về Local IndexedDB không được vượt quá 3 giây.
- **NFR-P3 (Background Processing):** Tác vụ bóc tách văn bản và tạo Vector Embeddings cho một file chuẩn (dưới 5MB) phải được giải quyết xong trên Celery Queue trong vòng dưới 30 giây.
- **NFR-P4 (Deep Research Timeout):** Phản hồi tính năng deep research (qua Chainlens hoặc fallback) phải được deliver hoàn toàn trong vòng tối đa 120 giây. Nếu vượt timeout, hệ thống trả về thông báo lỗi thân thiện và gợi ý thử lại.

### Security
- **NFR-S1 (Data Segregation):** Row-level Security (RLS) bắt buộc được áp dụng trên cấu trúc Database. Một User ID tuyệt đối không có quyền truy vấn chéo Document List hay Messages của tài khoản khác.
- **NFR-S2 (Local Storage Security):** Toàn bộ dữ liệu Zero-cache lưu ở IndexedDB phía Client sẽ bị xóa hoàn toàn (purged) ngay khi người dùng nhấn "Log Out".

### Scalability
- **NFR-SC1 (Worker Scalability):** Kiến trúc Celery Worker phải được giữ ở trạng thái "Stateless". Hệ thống phải đảm bảo việc thêm n-Workers vào hạ tầng Docker khi hàng đợi đang quá tải sẽ chạy lập tức mà không phải cấu hình lại mã nguồn.

### Reliability
- **NFR-R1 (Offline Tolerance - Chống chịu rớt mạng):** Website phải chịu đựng được việc mất mạng vô thời hạn. Giao diện không được "Trắng màn hình" (White Screen of Death), mà phải cho phép User đọc dữ liệu đã cache mượt mà như đang online.

### Crypto Orchestra (Epic 9)
- **NFR-CS1 (Sub-agent Token Budget):** System prompts cho mỗi crypto sub-agent phải < 500 tokens để tiết kiệm cost khi spawn nhiều agents song song. Áp dụng cho cả 6 agents Epic 9 (Tokenomics, Whale, Unlock, Yield, Governance, TA) và đảm bảo tổng token overhead khi spawn full suite < 5000 tokens.
- **NFR-CS2 (Parallel Execution):** LangGraph ToolNode bắt buộc thực thi tất cả `task()` calls đồng thời trong 1 graph step — không tuần tự. Đo bằng tỷ số `total_time / max(individual_time)` phải < 1.3x (near-perfect parallelism).
- **NFR-CS3 (API Rate Awareness):** Crypto tools phải handle rate limits gracefully — CoinGecko 30 req/min (hoặc Pro tier nếu upgrade), GoPlus 2000 req/day, CryptoPanic public tier, DeFiLlama unlimited. Khi rate limit hit, agent fallback sang `chainlens_deep_research` hoặc trả error message để main agent xử lý (NFR-Q3 graceful degradation).
- **NFR-CS4 (Stateless Tools):** Tất cả crypto tools đăng ký với `requires=[]` trong tool registry — không phụ thuộc DB, không cần session state, không cần workspace context. Đảm bảo các agents có thể scale horizontal mà không cần shared state.

### Quality Gates (Epic 9 — North Star Metrics)
- **NFR-Q1 (Accuracy):** Factual error rate cho crypto research responses (sample QA vs raw API ground truth) phải < 3%. Đo bằng manual QA + automated cross-check trên random sample 100 full-analysis queries mỗi 2 tuần production.
- **NFR-Q2 (Hallucination Rate):** % responses chứa số liệu không xuất phát từ tool output (fabricated numbers) phải < 1%. Đo bằng pattern check + sample QA.
- **NFR-Q3 (Graceful Degradation):** % requests có ≥ 1 sub-agent error nhưng main agent vẫn trả response đúng cấu trúc và mention nguồn unavailable phải > 98%.
- **NFR-Q4 (Speed):** P95 response time cho full-suite analysis (6+ agents spawned) phải < 90s — relaxed so với NFR-P1 vì cho phép Chainlens 125s timeout, tận dụng parallelism.
- **NFR-Q5 (Smart Selection Accuracy):** ≥ 90% queries route đúng Rule A/B/C/D (FR34 main-agent decision tree). Đo bằng manual classification 20 sample queries (Story 0.3 AC) + production sampling 100 queries/day. Khác NFR-Q1 (Q1 = factual accuracy của response, Q5 = routing accuracy của orchestrator).

