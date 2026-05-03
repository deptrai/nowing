# Implementation Readiness Assessment Report

**Date:** 2026-05-03
**Project:** Nowing

## Document Inventory

- _bmad-output/planning-artifacts/prd.md
- _bmad-output/planning-artifacts/architecture.md
- _bmad-output/planning-artifacts/epic-11-architecture-assessment.md
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/planning-artifacts/crypto-subagents-epics.md
- _bmad-output/planning-artifacts/epic5-billing-user-flow.md
- _bmad-output/planning-artifacts/ux-design-specification.md
- _bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md

## PRD Analysis

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
FR15: Hệ thống hiển thị bảng giá (Pricing) cho các gói cước với những đặc quyền về giới hạn tải file/nhắn tin khác nhau.
FR16: Người dùng có thể đăng ký gói cước và thanh toán an toàn thông qua cổng Stripe.com.
FR17: Hệ thống tự động theo dõi lượng sử dụng (Usage Tracking) và cập nhật trạng thái gói cước (Active/Canceled) qua Stripe Webhook.
FR18: Người dùng (bất kỳ tài khoản nào, kể cả FREE) có thể mua gift subscription bằng cách chọn plan (PRO) và thời hạn (1, 3, 6, hoặc 12 tháng), thanh toán one-time qua Stripe.
FR19: Hệ thống tạo gift code duy nhất (format GIFT-XXXX-XXXX-XXXX, 36^12 tổ hợp, cryptographically secure) sau khi thanh toán thành công hoặc admin duyệt.
FR20: Người mua có thể xem gift code và link redeem để chia sẻ cho người nhận. Gift code có thời hạn sử dụng 90 ngày kể từ ngày tạo.
FR21: Người nhận có thể redeem gift code trên trang Redeem Gift (hoặc qua link chứa code). Hệ thống xác thực code hợp lệ, chưa sử dụng, và chưa hết hạn trước khi kích hoạt.
FR22: Khi redeem thành công, subscription được kích hoạt từ thời điểm redeem với thời hạn đầy đủ. Nếu người nhận đã có subscription active, thời hạn được cộng dồn (new_expiry = max(current_period_end, now) + gift_duration).
FR23: Khi Stripe env không khả dụng, hệ thống cho phép submit gift request để admin duyệt thủ công (admin-approval fallback, cùng pattern với token topup và subscription upgrade).
FR24: Người dùng có thể kích hoạt tính năng deep research từ chat bằng cách sử dụng các từ khóa trigger ("deep research", "thorough investigation", v.v.). LangGraph Agent tự động nhận diện intent và gọi tool chainlens_deep_research.
FR25: Hệ thống sử dụng Chainlens B2B API (POST /api/v1/b2b/research) làm primary engine cho deep research. Khi Chainlens không khả dụng (feature flag tắt, API down, hoặc health check thất bại), hệ thống tự động fallback sang generate_report(report_style="deep_research") mà không hiển thị lỗi cho người dùng.
FR26: Admin/DevOps có thể bật hoặc tắt tích hợp Chainlens bằng cách set/unset biến môi trường CHAINLENS_RESEARCH_ENABLED mà không cần deploy lại code.
FR27 (Tokenomics Analyst): Hệ thống cung cấp sub-agent tokenomics_analyst chuyên phân tích token economics: circulating vs total vs max supply, vesting schedule, distribution (team/investors/community/treasury), inflation/deflation mechanics, demand drivers. Tools scoped: get_coingecko_token_info, chainlens_deep_research (Messari, CryptoRank, official docs). System prompt < 500 tokens.
FR28 (Whale Tracker): Hệ thống cung cấp sub-agent whale_tracker theo dõi large wallet movements và smart money flows: known whale wallets (exchanges, funds, insiders), inflow/outflow patterns, accumulation vs distribution phases. Tools scoped: chainlens_deep_research (Arkham, Nansen, Etherscan token holders).
FR29 (Token Unlock Scheduler): Hệ thống cung cấp sub-agent token_unlock_scheduler track upcoming vesting events: unlock dates, % supply unlocked, historical price action sau unlock events, sell pressure assessment cho short-term holds. Tools scoped: chainlens_deep_research (TokenUnlocks.app, Vesting.is, CryptoRank).
FR30 (Yield Optimizer): Hệ thống cung cấp sub-agent yield_optimizer đề xuất DeFi yields theo risk preference (conservative/moderate/aggressive): filter theo risk level, tính impermanent loss cho LP positions, so sánh protocol security score. Tools scoped: get_defillama_yields, get_defillama_protocol, check_token_security.
FR31 (Governance Analyst): Hệ thống cung cấp sub-agent governance_analyst theo dõi DAO governance: active proposals, voting outcomes, governance participation rate, treasury size/management, flag controversial decisions. Tools scoped: chainlens_deep_research (Snapshot.org, Tally, Commonwealth, protocol forums).
FR32 (Technical Analyst): Hệ thống cung cấp sub-agent technical_analyst phân tích chart patterns và technical indicators: support/resistance levels, 50MA/200MA cross, RSI overbought/oversold, MACD signals, chart patterns (head & shoulders, cup & handle, double bottom/top). Tools scoped: get_live_token_data (DexScreener), chainlens_deep_research (TradingView, CoinGecko charts).
FR33 (Parallel Orchestration): Main agent có khả năng spawn multiple crypto sub-agents song song qua task() tool trong cùng 1 LangGraph ToolNode khi user yêu cầu phân tích toàn diện ("phân tích toàn diện $X", "comprehensive analysis"). Total execution time ≈ max(individual times), không phải sum.
FR34 (Smart Agent Selection): Main agent system prompt có instruction để chọn subset agents phù hợp với câu hỏi cụ thể (không spawn cả 10 agents khi user chỉ hỏi về 1 khía cạnh). Lookup table: agent name → chuyên môn → trigger keywords.
FR35 (Graceful Degradation): Khi 1 hoặc nhiều sub-agents fail (rate limit 429, timeout, API unavailable), main agent vẫn tổng hợp response từ các agents thành công và mention rõ nguồn nào unavailable trong response — không crash toàn bộ analysis.
FR36 (Crypto Data Schema): Hệ thống tạo 3 bảng PostgreSQL mới: crypto_projects (entity registry với project_id, symbol, coingecko_id, defillama_slug), crypto_data_snapshots (append-only timeline với data_category, tool_name, tool_args JSONB, data JSONB, ttl_seconds, expires_at, is_error), và search_space_crypto_watchlist (workspace → project link với pin_order). Tất cả crypto tool results được persist với full metadata.
FR37 (Cache Middleware Interception): CryptoDataCacheMiddleware intercept awrap_tool_call trước khi gọi external API — check DB cho fresh snapshot (expires_at > NOW()), return cached data nếu có. Nếu miss → gọi API → write snapshot. Middleware đặt sau SourceAttributionMiddleware trong stack. Feature flag CRYPTO_DATA_CACHE_ENABLED cho phép bật/tắt không cần redeploy. Graceful degradation: nếu DB/Redis fail → pass-through to direct API call, không throw exception.
FR38 (Thundering Herd Protection): Khi nhiều concurrent requests cùng query token X và cache miss, hệ thống dùng Redis distributed lock (SET NX EX 60s) để đảm bảo chỉ 1 request gọi external API, các requests còn lại double-check DB sau khi acquire lock. Fallback sang asyncio.Lock per-process nếu Redis unavailable.
FR39 (Background Data Refresh): Celery beat task refresh_popular_crypto_data chạy mỗi 30 phút: tìm tokens được query trong 24h qua, pre-fetch categories sắp expire (trong vòng 5 phút), write vào DB. Task cleanup_expired_crypto_snapshots chạy daily 3 AM: xóa snapshots > 30 ngày, error snapshots > 24h, giữ max 1000 snapshots per project per category.
FR40 (Workspace Watchlist API): REST API endpoint GET /api/crypto/projects/{project_id}/timeline trả về lịch sử snapshots theo data_category + time range. GET /api/crypto/workspaces/{search_space_id}/watchlist trả về danh sách crypto projects được pin bởi workspace. Data exposed là historical snapshots (không phải real-time) — không cần auth scope phức tạp, chỉ cần search_space ownership check.
FR41 (SSE Heartbeat & Auto-Reconnect): Backend SSE stream inject : heartbeat comment mỗi 15s khi không có data event — giữ connection alive qua proxy/gateway. Frontend tự reconnect với exponential backoff (1s→2s→4s→max 30s) khi stream đứt, resume từ after_seq parameter để không mất event. Sau 5 lần retry fail, UI hiển thị banner "Connection lost — click to retry". HTTP/2 multiplexing enforced ở reverse proxy để bypass browser 6-connection limit.
FR41.1 (Production CDN compatibility — Story 11.6): SSE traffic verified compatible với Cloudflare CDN — không bị recompression hay buffering. Required Cloudflare config (page rule hoặc worker bypass) documented in docs/deployment/sse-cdn.md.
FR41.2 (HTTP/2 multiplexing verification — Story 11.6): Reverse proxy (Traefik) HTTP/2 config verified in staging với 3+ concurrent SSE tabs maintaining connections. Required Traefik flags documented in docs/deployment/http2.md.
FR41.3 (Heartbeat cancel safety — Story 11.7): SSE consumer disconnect mid-stream không corrupt LangGraph state hoặc leak DB sessions. Structured concurrency / sentinel pattern thay vì raw task.cancel().
FR42 (Circuit Breaker Hardening): Circuit breaker (đã Redis-backed) bổ sung explicit HALF_OPEN state cho probe logic — chỉ cho 1 request thử khi cooldown hết, các request khác fail-fast. In-memory cache retain last-known state khi Redis unavailable (thay vì default closed). Structured logging cho mọi state transition (closed→open, open→half_open, half_open→closed/open).
FR43 (Orphaned Cache Purge): Celery weekly task (Sunday 4 AM UTC) tự động xóa crypto_data_snapshots có search_space_id trỏ tới workspace đã bị xóa (orphaned records). Batch delete 1000 rows/lần tránh long transaction lock. Independent of CRYPTO_DATA_CACHE_ENABLED flag.
FR44 (Per-API Token Bucket Rate Limiters): Per-provider Redis-backed token bucket rate limiter thay vì rely chỉ vào circuit breaker sau 429. Mỗi provider có capacity/refill_rate riêng (CoinGecko 30/min, GoPlus ~33/30min, Etherscan 5/sec, DeFiLlama generous 120/min). Tool chờ tối đa 5s cho bucket refill trước khi return error. In-memory fallback khi Redis unavailable.
FR45 (Client-Side Quota Enforcement): useSubscriptionGate() hook đọc subscription_current_period_end từ Zero local cache — redact deep research content (blur + upgrade CTA) khi subscription expired. Hoạt động offline (pure client-side timestamp check). Auto-unlock khi Zero-sync push renewal. Bổ sung cho server-side enforcement — không thay thế.
FR49 (Entity Resolution): Gom nhóm tự động các ví (wallets) và phân tích dòng tiền (Smart Money Flow) thông qua biểu đồ Sankey. Tự động phát hiện ví Insider/Dev.
FR50 (Protocol Revenue Modeling): Phân tích P/E, P/S ratio dựa trên dữ liệu DefiLlama/Token Terminal. AI đọc lịch vesting từ contract để dựng biểu đồ áp lực bán trong 12 tháng.
FR51 (Narrative & Macro Correlation): NLP Heatmap quét Governance Forums, Github, Twitter để dự báo trend. Ma trận tương quan với các chỉ số vĩ mô (DXY, NASDAQ).
FR52 (Enterprise Risk Management): Portfolio stress testing dưới kịch bản sụp đổ, AI scan lỗi smart contract và rủi ro pháp lý (ví dụ: bị SEC phân loại là chứng khoán).
FR53 (Liquidity Routing): Profiler phân tích độ sâu sổ lệnh trên CEX/DEX để gợi ý chiến lược xả hàng/gom hàng lớn tối ưu slippage, cùng scanner tìm yield an toàn trên đa chuỗi.

Total FRs: 52

### Non-Functional Requirements

NFR-P1 (Time to First Token - TTFT): Hệ thống bắt buộc phải phản hồi ký tự đầu tiên từ AI Agent thông qua SSE dưới 1.5 giây kể từ khi user nhấn Submit.
NFR-P2 (Sync Latency): Thời gian bộ nhớ đệm Zero-cache đồng bộ thay đổi trạng thái (ví dụ một message mới) từ Remote DB về Local IndexedDB không được vượt quá 3 giây.
NFR-P3 (Background Processing): Tác vụ bóc tách văn bản và tạo Vector Embeddings cho một file chuẩn (dưới 5MB) phải được giải quyết xong trên Celery Queue trong vòng dưới 30 giây.
NFR-P4 (Deep Research Timeout): Phản hồi tính năng deep research (qua Chainlens hoặc fallback) phải được deliver hoàn toàn trong vòng tối đa 120 giây. Nếu vượt timeout, hệ thống trả về thông báo lỗi thân thiện và gợi ý thử lại.
NFR-P5 (Rate Limit Prevention): Per-API token bucket phải prevent > 95% of 429 responses từ external providers (so với baseline không có rate limiter). Đo bằng http_429_total counter before/after deployment.
NFR-S1 (Data Segregation): Row-level Security (RLS) bắt buộc được áp dụng trên cấu trúc Database. Một User ID tuyệt đối không có quyền truy vấn chéo Document List hay Messages của tài khoản khác.
NFR-S2 (Local Storage Security): Toàn bộ dữ liệu Zero-cache lưu ở IndexedDB phía Client sẽ bị xóa hoàn toàn (purged) ngay khi người dùng nhấn "Log Out".
NFR-SC1 (Worker Scalability): Kiến trúc Celery Worker phải được giữ ở trạng thái "Stateless". Hệ thống phải đảm bảo việc thêm n-Workers vào hạ tầng Docker khi hàng đợi đang quá tải sẽ chạy lập tức mà không phải cấu hình lại mã nguồn.
NFR-R1 (Offline Tolerance - Chống chịu rớt mạng): Website phải chịu đựng được việc mất mạng vô thời hạn. Giao diện không được "Trắng màn hình" (White Screen of Death), mà phải cho phép User đọc dữ liệu đã cache mượt mà như đang online.
NFR-R2 (SSE Connection Reliability): SSE stream phải survive proxy timeout (Nginx default 60s, Cloudflare 100s) qua heartbeat mechanism. Auto-reconnect phải recover trong < 5s (P95) sau network interruption. Multi-tab scenario (3+ tabs) phải hoạt động nhờ HTTP/2 multiplexing.
NFR-R3 (Circuit Breaker Consistency): Circuit breaker state phải consistent across tất cả Uvicorn workers (< 1s propagation delay qua Redis). Khi Redis unavailable, last-known state phải retained (không default closed/open).
NFR-CS1 (Sub-agent Token Budget): System prompts cho mỗi crypto sub-agent phải < 500 tokens để tiết kiệm cost khi spawn nhiều agents song song. Áp dụng cho cả 6 agents Epic 9 (Tokenomics, Whale, Unlock, Yield, Governance, TA) và đảm bảo tổng token overhead khi spawn full suite < 5000 tokens.
NFR-CS2 (Parallel Execution): LangGraph ToolNode bắt buộc thực thi tất cả task() calls đồng thời trong 1 graph step — không tuần tự. Đo bằng tỷ số total_time / max(individual_time) phải < 1.3x (near-perfect parallelism).
NFR-CS3 (API Rate Awareness): Crypto tools phải handle rate limits gracefully — CoinGecko 30 req/min (hoặc Pro tier nếu upgrade), GoPlus 2000 req/day, CryptoPanic public tier, DeFiLlama unlimited. Khi rate limit hit, agent fallback sang chainlens_deep_research hoặc trả error message để main agent xử lý (NFR-Q3 graceful degradation).
NFR-CS4 (Stateless Tools): Tất cả crypto tools đăng ký với requires=[] trong tool registry — không phụ thuộc DB, không cần session state, không cần workspace context. Đảm bảo các agents có thể scale horizontal mà không cần shared state.
NFR-CS5 (Cache Hit Rate): Sau warmup period (24h từ khi enable CRYPTO_DATA_CACHE_ENABLED), cache hit rate cho top-10 tokens (ETH, BTC, SOL, BNB, etc.) phải ≥ 70% khi có ≥ 10 requests/hour. Đo bằng Prometheus counter crypto_cache_hits_total / (crypto_cache_hits_total + crypto_cache_misses_total).
NFR-CS6 (Cache Failure Isolation): Khi DB hoặc Redis không khả dụng, CryptoDataCacheMiddleware phải tự động bypass và gọi trực tiếp external API — không raise exception, không thay đổi response format, không ảnh hưởng agent execution. P99 overhead của cache layer (khi cache miss) phải < 5ms.
NFR-Q1 (Accuracy): Factual error rate cho crypto research responses (sample QA vs raw API ground truth) phải < 3%. Đo bằng manual QA + automated cross-check trên random sample 100 full-analysis queries mỗi 2 tuần production.
NFR-Q2 (Hallucination Rate): % responses chứa số liệu không xuất phát từ tool output (fabricated numbers) phải < 1%. Đo bằng pattern check + sample QA.
NFR-Q3 (Graceful Degradation): % requests có ≥ 1 sub-agent error nhưng main agent vẫn trả response đúng cấu trúc và mention nguồn unavailable phải > 98%.
NFR-Q4 (Speed): P95 response time cho full-suite analysis (6+ agents spawned) phải < 90s — relaxed so với NFR-P1 vì cho phép Chainlens 125s timeout, tận dụng parallelism.
NFR-Q5 (Smart Selection Accuracy): ≥ 90% queries route đúng Rule A/B/C/D (FR34 main-agent decision tree). Đo bằng manual classification 20 sample queries (Story 0.3 AC) + production sampling 100 queries/day. Khác NFR-Q1 (Q1 = factual accuracy của response, Q5 = routing accuracy của orchestrator).

Total NFRs: 23

### Additional Requirements

- Cấu trúc API (FastAPI) bao gồm: /api/v1/documents, /api/v1/chat, /api/zero/sync
- Kiến trúc mở cho phép người dùng tự do lựa chọn các mô hình ngôn ngữ
- Bảo vệ quyền riêng tư tuyệt đối cho tài liệu độc quyền của người dùng

### PRD Completeness Assessment

PRD rất chi tiết, bao quát đầy đủ tính năng, hiệu suất, và đánh giá rủi ro cho toàn dự án, với sự phân tách rõ ràng giữa chức năng (FR) và phi chức năng (NFR).

## Epic Coverage Validation

### Coverage Matrix

| FR Number | PRD Requirement | Epic Coverage | Status |
| --------- | --------------- | ------------- | ------ |
| FR1 | Người dùng có thể tải lên các tệp tài liệu... | Epic 2 | ✓ Covered |
| FR2 | Người dùng có thể xem lại danh sách... | Epic 2 | ✓ Covered |
| FR3 | Người dùng có thể xem được trạng thái... | Epic 2 | ✓ Covered |
| FR4 | Người dùng có thể xóa một tài liệu... | Epic 2 | ✓ Covered |
| FR5 | Người dùng có thể tạo một phiên hỏi đáp... | Epic 3 | ✓ Covered |
| FR6 | Người dùng có thể gửi câu hỏi dạng văn bản... | Epic 3 | ✓ Covered |
| FR7 | Người dùng có thể nhận được các luồng... | Epic 3 | ✓ Covered |
| FR8 | Người dùng có thể xem lại danh sách... | Epic 4 | ✓ Covered |
| FR9 | Người dùng có thể đọc lại toàn bộ nội dung... | Epic 4 | ✓ Covered |
| FR10 | Người dùng có thể đọc danh sách tài liệu... | Epic 4 | ✓ Covered |
| FR11 | Người dùng có thể nhận biết được trạng thái... | Epic 4 | ✓ Covered |
| FR12 | Hệ thống có khả năng tự động bóc tách... | Epic 2 | ✓ Covered |
| FR13 | Hệ thống có khả năng chặn yêu cầu (Rate Limit)... | Epic 2 | ✓ Covered |
| FR14 | Người dùng có thể xác thực (Authentication)... | Epic 1 | ✓ Covered |
| FR15 | Hệ thống hiển thị bảng giá (Pricing)... | Epic 5 | ✓ Covered |
| FR16 | Người dùng có thể đăng ký gói cước... | Epic 5 | ✓ Covered |
| FR17 | Hệ thống tự động theo dõi lượng sử dụng... | Epic 5 | ✓ Covered |
| FR18 | Người dùng có thể mua gift subscription... | Epic 6 | ✓ Covered |
| FR19 | Hệ thống tạo gift code duy nhất... | Epic 6 | ✓ Covered |
| FR20 | Người mua có thể xem gift code và link... | Epic 6 | ✓ Covered |
| FR21 | Người nhận có thể redeem gift code... | Epic 6 | ✓ Covered |
| FR22 | Khi redeem thành công, subscription được kích hoạt... | Epic 6 | ✓ Covered |
| FR23 | Khi Stripe env không khả dụng, hệ thống cho phép... | Epic 6 | ✓ Covered |
| FR24 | Người dùng có thể kích hoạt deep research... | Epic 7 | ✓ Covered |
| FR25 | Hệ thống sử dụng Chainlens B2B API... | Epic 7 | ✓ Covered |
| FR26 | Admin/DevOps có thể bật hoặc tắt tích hợp... | Epic 7 | ✓ Covered |
| FR27 | Hệ thống cung cấp sub-agent tokenomics_analyst... | Epic 9 | ✓ Covered |
| FR28 | Hệ thống cung cấp sub-agent whale_tracker... | Epic 9 | ✓ Covered |
| FR29 | Hệ thống cung cấp sub-agent token_unlock_scheduler... | Epic 9 | ✓ Covered |
| FR30 | Hệ thống cung cấp sub-agent yield_optimizer... | Epic 9 | ✓ Covered |
| FR31 | Hệ thống cung cấp sub-agent governance_analyst... | Epic 9 | ✓ Covered |
| FR32 | Hệ thống cung cấp sub-agent technical_analyst... | Epic 9 | ✓ Covered |
| FR33 | Main agent có khả năng spawn multiple crypto... | Epic 9 | ✓ Covered |
| FR34 | Main agent system prompt có instruction... | Epic 9 | ✓ Covered |
| FR35 | Khi 1 hoặc nhiều sub-agents fail... | Epic 9 | ✓ Covered |
| FR36 | Hệ thống tạo 3 bảng PostgreSQL mới... | **NOT FOUND** | ❌ MISSING |
| FR37 | CryptoDataCacheMiddleware intercept awrap_tool_call... | **NOT FOUND** | ❌ MISSING |
| FR38 | Khi nhiều concurrent requests cùng query... | **NOT FOUND** | ❌ MISSING |
| FR39 | Celery beat task refresh_popular_crypto_data... | **NOT FOUND** | ❌ MISSING |
| FR40 | REST API endpoint GET /api/crypto/projects/... | **NOT FOUND** | ❌ MISSING |
| FR41 | Backend SSE stream inject : heartbeat... | Epic 11 | ✓ Covered |
| FR42 | Circuit breaker bổ sung explicit HALF_OPEN state... | Epic 11 | ✓ Covered |
| FR43 | Celery weekly task tự động xóa crypto_data_snapshots... | Epic 11 | ✓ Covered |
| FR44 | Per-API Token Bucket Rate Limiters... | Epic 11 | ✓ Covered |
| FR45 | useSubscriptionGate() hook đọc subscription_current_period_end... | Epic 11 | ✓ Covered |
| FR49 | Gom nhóm tự động các ví (wallets)... | **NOT FOUND** | ❌ MISSING |
| FR50 | Phân tích P/E, P/S ratio dựa trên dữ liệu... | **NOT FOUND** | ❌ MISSING |
| FR51 | NLP Heatmap quét Governance Forums... | **NOT FOUND** | ❌ MISSING |
| FR52 | Portfolio stress testing dưới kịch bản sụp đổ... | **NOT FOUND** | ❌ MISSING |
| FR53 | Profiler phân tích độ sâu sổ lệnh... | **NOT FOUND** | ❌ MISSING |

*(Lưu ý: FR46-FR48 có trong FR Coverage Map của Epic 12 nhưng không được liệt kê trong PRD)*

### Missing Requirements

### Critical Missing FRs

FR36-FR40: [Các tính năng Persistent Shared Crypto Data Layer]
- Impact: Dữ liệu cho Epic 10 bị thiếu trong `FR Coverage Map` của `epics.md`, dẫn đến khoảng trống (gap) trong quản lý requirements.
- Recommendation: Thêm Epic 10 vào phần FR Coverage Map trong `epics.md`.

FR49-FR53: [Các tính năng Institutional Research Terminal]
- Impact: Các tính năng Epic 13 (vừa được brainstorm) chưa được ánh xạ trong `FR Coverage Map` của `epics.md`.
- Recommendation: Thêm Epic 13 vào phần FR Coverage Map trong `epics.md`.

### Coverage Statistics

- Total PRD FRs: 50
- FRs covered in epics: 40
- Coverage percentage: 80%

## UX Alignment Assessment

### UX Document Status

**Found:**
- `ux-design-specification.md`
- `ux-crypto-orchestra-handoff.md`

### Alignment Issues

UX Documentation hiện tại khá đồng bộ với PRD và Architecture, cụ thể:
- **UX ↔ PRD Alignment:** Các tính năng cốt lõi như Zero-cache offline mode, SSE Streaming, Deep Research, và Crypto Orchestra đều được cover chi tiết về mặt UI/UX. Gần đây nhất, phần mở rộng UX cho Epic 13 (Institutional Data Terminal) đã được bổ sung để map trực tiếp với FR49-FR53 trong PRD (Sankey Diagram, Tokenomics Sandbox, Narrative Heatmap).
- **UX ↔ Architecture Alignment:** Kiến trúc Frontend (Next.js, Rocicorp Zero) và Backend (FastAPI, SSE, Kafka, Neo4j, Elasticsearch) hoàn toàn hỗ trợ các tương tác phức tạp được thiết kế trong UX document (ví dụ: Dynamic Grid Workspace, real-time widgets, indicators cho graceful degradation).

### Warnings

- Cần cập nhật bổ sung các thông tin của Epic 10 (FR36-FR40) và Epic 13 (FR49-FR53) vào `FR Coverage Map` trong tài liệu `epics.md` để đảm bảo tính nhất quán (Traceability) xuyên suốt dự án.
- Chưa thấy rõ các thiết kế UX/UI cụ thể cho màn hình cấu hình Kafka Streams hoặc cài đặt rủi ro vĩ mô của Epic 13 (có thể nằm trong giai đoạn thiết kế chi tiết hơn).

## Epic Quality Review

### 🔴 Critical Violations
- **Technical Epics (Thiếu User Value):** 
  - **Epic 8 (Integration Testing):** Kiểm thử (Testing) phải là một phần của Acceptance Criteria (AC) trong từng Story, không nên tách thành một Epic riêng biệt.
  - **Epic 10 (Persistent Shared Crypto Data Layer):** Tập trung hoàn toàn vào Schema Database, Middleware, Redis Locks. Đây là các task hạ tầng kỹ thuật (Technical Milestones), không mang lại giá trị trực tiếp cho End-User theo chuẩn định nghĩa Epic.
  - **Epic 11 (Architecture Resilience & Stability):** Tập trung vào SSE Heartbeat, Circuit Breaker, Rate Limiters. Tương tự Epic 10, đây là Technical Epic.

### 🟠 Major Issues
- **Vấn đề Tạo Database (Database Creation Timing):**
  - **Epic 10, FR36:** Đề xuất tạo cùng lúc 3 bảng PostgreSQL (`crypto_projects`, `crypto_data_snapshots`, `search_space_crypto_watchlist`). Điều này vi phạm nguyên tắc "Mỗi Story tự tạo Table khi cần thiết" (Chống lại Big Design Up Front về Data).
- **Vấn đề Phụ thuộc (Dependencies):**
  - **Epic 9 (Crypto Orchestra):** Yêu cầu (Prerequisite) toàn bộ Epic 0 (Crypto Foundation) phải hoàn thành trước. Việc một Epic có quá nhiều phụ thuộc lớn làm giảm tính độc lập (Epic Independence).

### 🟡 Minor Concerns
- **Định dạng Acceptance Criteria (AC):**
  - Một số tính năng trong Epic 13 (như Story 13.5) có định dạng AC dạng Gherkin (Given/When/Then) nhưng phần Then/And đôi khi còn hơi tổng quát (vague), ví dụ "AI cung cấp chiến lược phân bổ lệnh" cần cụ thể hơn về định dạng đầu ra.
- **Thiết lập Project Setup (Greenfield/Brownfield):**
  - Dự án được đánh dấu là Brownfield (đã có Docker, CI/CD, Postgres, Redis), nhưng thiếu các Story hướng dẫn việc Tích hợp/Migration rõ ràng ở giai đoạn đầu cho các developer mới.

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK**

### Critical Issues Requiring Immediate Action

1. **Mất đồng bộ Traceability:** FR Coverage Map trong `epics.md` chưa cập nhật FR36-FR40 (Epic 10) và FR49-FR53 (Epic 13).
2. **Sai lệch cấu trúc Epic:** Các Epic 8, Epic 10, Epic 11 đang được thiết kế dưới dạng các "Technical Milestones" thay vì mang lại User Value. (Cần phân bổ các task kỹ thuật này thành các Stories hỗ trợ cho các Epic cốt lõi tương ứng).
3. **Big Design Up Front (Data):** Epic 10 (FR36) tạo cùng lúc 3 bảng DB trước khi cần thiết, vi phạm nguyên tắc cấp phát tài nguyên theo Story.

### Recommended Next Steps

1. Cập nhật file `epics.md` để đưa đầy đủ FR36-FR40 và FR49-FR53 vào bảng `FR Coverage Map`.
2. Refactor (cấu trúc lại) Epic 8, 10, 11 thành các cụm Stories và đính kèm vào các Epic sản phẩm (VD: Epic 10 Data Layer nên là prerequisite stories của Epic 9 và Epic 13).
3. Tinh chỉnh lại các Acceptance Criteria của Epic 13 (đặc biệt Story 13.5) để đảm bảo định dạng BDD (Given/When/Then) rõ ràng và có đầu ra test được (testable output).

### Final Note

This assessment identified 8 issues across 3 categories (Coverage, UX Alignment, Epic Quality). Address the critical issues before proceeding to implementation. These findings can be used to improve the artifacts or you may choose to proceed as-is.