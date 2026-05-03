---
stepsCompleted:
  - step-01-document-discovery.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-04
**Project:** Nowing

## Document Inventory

**PRD Documents:**
- `prd.md`

**Architecture Documents:**
- `architecture.md`
- `epic-11-architecture-assessment.md`

**Epics & Stories Documents:**
- `epics.md`
- `crypto-subagents-epics.md`
- `epic5-billing-user-flow.md`
- `epic-11-architecture-assessment.md`

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
FR11: Người dùng có thể nhận biết được trạng thái đồng bộ dữ liệu hiện tại của hệ thống.
FR12: Hệ thống có khả năng tự động bóc tách văn bản và tạo Vector Embeddings một cách bất đồng bộ ngầm khi tài liệu mới được tải lên.
FR13: Hệ thống có khả năng chặn yêu cầu (Rate Limit) nếu người dùng sử dụng vượt mức Token cho phép hoặc tải file quá quy định.
FR14: Người dùng có thể xác thực (Authentication) để đăng nhập và bảo vệ dữ liệu thuộc private workspace của họ.
FR15: Hệ thống hiển thị bảng giá (Pricing) cho các gói cước.
FR16: Người dùng có thể đăng ký gói cước và thanh toán an toàn thông qua cổng Stripe.com.
FR17: Hệ thống tự động theo dõi lượng sử dụng (Usage Tracking) và cập nhật trạng thái gói cước (Active/Canceled) qua Stripe Webhook.
FR18: Người dùng có thể mua gift subscription thanh toán one-time qua Stripe.
FR19: Hệ thống tạo gift code duy nhất sau khi thanh toán thành công hoặc admin duyệt.
FR20: Người mua có thể xem gift code và link redeem để chia sẻ cho người nhận.
FR21: Người nhận có thể redeem gift code trên trang Redeem Gift.
FR22: Khi redeem thành công, subscription được kích hoạt hoặc cộng dồn thời gian.
FR23: Khi Stripe env không khả dụng, hệ thống cho phép submit gift request để admin duyệt thủ công.
FR24: Người dùng có thể kích hoạt tính năng deep research từ chat bằng từ khóa trigger.
FR25: Hệ thống sử dụng Chainlens B2B API làm primary engine cho deep research, fallback sang local report khi fail.
FR26: Admin/DevOps có thể bật hoặc tắt tích hợp Chainlens qua biến môi trường.
FR27: Sub-agent Tokenomics Analyst phân tích supply, vesting, inflation.
FR28: Sub-agent Whale Tracker theo dõi ví cá mập và dòng tiền smart money.
FR29: Sub-agent Token Unlock Scheduler theo dõi lịch trả token và áp lực bán.
FR30: Sub-agent Yield Optimizer đề xuất DeFi yields theo risk preference.
FR31: Sub-agent Governance Analyst theo dõi DAO governance, proposals, voting.
FR32: Sub-agent Technical Analyst phân tích chart patterns và technical indicators.
FR33: Main agent có khả năng spawn multiple crypto sub-agents song song.
FR34: Smart Agent Selection sử dụng system prompt để chọn subset agents phù hợp.
FR35: Graceful Degradation đảm bảo main agent vẫn tổng hợp được khi 1 vài sub-agent fail.
FR36: Crypto Data Schema định nghĩa 3 bảng Postgres cho caching crypto data.
FR37: CryptoDataCacheMiddleware chặn gọi API nếu đã có cache hợp lệ (Hit/Miss).
FR38: Thundering Herd Protection qua Redis distributed lock để bảo vệ API khỏi bão request.
FR39: Background Data Refresh (Celery) cập nhật trước dữ liệu token nóng và dọn dẹp cache rác.
FR40: Workspace Watchlist API truy xuất danh sách token đang theo dõi của Workspace.
FR41: SSE Heartbeat & Auto-Reconnect giữ kết nối ổn định và tự động nối lại.
FR42: Circuit Breaker Hardening bổ sung HALF_OPEN state và Redis-backed logic.
FR43: Orphaned Cache Purge tự dọn dẹp dữ liệu của Workspace đã xóa.
FR44: Per-API Token Bucket Rate Limiters phòng chống việc bị rate-limit bởi Third-Party.
FR45: Client-Side Quota Enforcement chặn yêu cầu trực tiếp từ UI khi hết hạn gói cước.
FR49: Entity Resolution gom nhóm ví, phân tích dòng tiền và dán nhãn Insider/Dev.
FR50: Protocol Revenue Modeling mô phỏng P/E, P/S và biểu đồ áp lực bán.
FR51: Narrative & Macro Correlation quét NLP sentiment và tương quan tài sản vĩ mô (Heatmap).
FR52: Enterprise Risk Management (Portfolio stress testing, VaR) và quét rủi ro hợp đồng/pháp lý.
FR53: Liquidity Routing phân tích sổ lệnh CEX/DEX gợi ý xả hàng tối ưu trượt giá.

Total FRs: 53

### Non-Functional Requirements

NFR-P1: Time to First Token (TTFT) < 1.5 giây thông qua SSE.
NFR-P2: Sync Latency Zero-cache < 3 giây.
NFR-P3: Background Processing file <5MB hoàn thành trên Celery < 30 giây.
NFR-P4: Deep Research Timeout hoàn trả hoàn toàn < 120 giây.
NFR-P5: Rate Limit Prevention giảm > 95% số lỗi 429 từ External Providers.
NFR-S1: Data Segregation (RLS) bắt buộc áp dụng, ngăn chặn chéo user.
NFR-S2: Local Storage Security (IndexedDB purged khi Log Out).
NFR-SC1: Worker Scalability (Celery worker phi trạng thái).
NFR-R1: Offline Tolerance (UI không trắng xoá khi ngắt mạng, đọc cache mượt).
NFR-R2: SSE Connection Reliability (Chịu được proxy timeout, auto-recover < 5s).
NFR-R3: Circuit Breaker Consistency (<1s propagation delay qua Redis).
NFR-CS1: Sub-agent Token Budget (System prompt < 500 tokens).
NFR-CS2: Parallel Execution (total_time / max_individual < 1.3x).
NFR-CS3: API Rate Awareness (handle rate limit gracefully, fallbacks).
NFR-CS4: Stateless Tools (Requires=[]).
NFR-CS5: Cache Hit Rate ≥ 70% sau warmup period.
NFR-CS6: Cache Failure Isolation (Bypass to direct API if Cache/Redis is down).
NFR-Q1: Accuracy (Factual error rate < 3%).
NFR-Q2: Hallucination Rate (< 1%).
NFR-Q3: Graceful Degradation (> 98% pass khi sub-agent fail).
NFR-Q4: Speed (P95 < 90s cho 6+ agents spawned).
NFR-Q5: Smart Selection Accuracy (≥ 90% routing chuẩn).

Total NFRs: 22

### Additional Requirements

- Tận dụng Starter Template đã chọn: Official Next.js CLI & Custom Fast-Modern Async API.
- Database Postgres sử dụng extension pgvector 0.8.2. Backend Python dùng SQLModel.
- Đồng bộ Realtime Local-first với rocicorp/zero 1.1.1.
- State Management: Zustand cho Global UI state, form xử lý với react-hook-form.
- Electron 41+ cho ứng dụng Desktop nội bộ.
- Core UX-DR1 đến UX-DR9: Shadcn/UI, độ trễ animation <150ms, kiến trúc Split-pane, micro-sync indicators.

### PRD Completeness Assessment

## Epic Quality Review

### 🔴 Critical Violations

**1. Sự Tồn Tại Của "Technical Epics" (Epic Thuần Kỹ Thuật):**
Theo chuẩn mực BMad (Best Practices), mọi Epic đều phải mang lại User Value trực tiếp (Góc nhìn người dùng). Việc gom nhóm các công việc kỹ thuật thành một Epic riêng biệt là vi phạm quy tắc cơ bản.
- **Epic 11 (Architecture Resilience & Stability):** Đây là một Epic thuần túy kỹ thuật giải quyết NFRs (Rate Limit, SSE Heartbeat, Circuit Breaker). Mặc dù rất quan trọng cho hệ thống, nhưng về mặt cấu trúc Agile, nó nên được chuyển thành các NFRs gắn vào các User Stories của Epic 9 và Epic 10 thay vì đứng độc lập như một Epic.
- **Epic 9-DF (Data Foundation):** Tương tự, việc xây dựng Postgres schema và Caching Middleware là các bước chuẩn bị kỹ thuật. Story `9-DF-1` ("As a backend developer...") vi phạm nguyên tắc "User-centric". 

### 🟠 Major Issues

**1. Database Creation Timing (Thời điểm khởi tạo Database):**
- Trong Epic 1 (Story 1.1), hệ thống yêu cầu "Khởi tạo Hạ tầng Dự án & Cơ sở Dữ liệu". Mặc dù điều này hợp lý với tư cách là Greenfield/Brownfield setup, nhưng nó chứa nguy cơ tạo trước (upfront) toàn bộ các bảng thay vì tuân thủ "Mỗi story chỉ tạo bảng mà nó cần". Đội ngũ Dev cần chú ý chỉ chạy migration cho `users` ở Story 1.1, và để phần migration bảng `crypto_projects` cho Story `9-DF-1`.

### 🟡 Minor Concerns

**1. Story Sizing & Trọng lượng:**
- Một số Story trong Epic 10 (ví dụ: `10-2 Protocol Revenue` và `10-4 Enterprise Risk Management`) yêu cầu tính toán logic rất phức tạp ở Client-side (Zustand, Sandbox Simulation). Mặc dù ACs được viết rất tốt theo chuẩn GIVEN/WHEN/THEN, khối lượng công việc của những story này có thể vượt quá một story tiêu chuẩn (cần 3-5 ngày). Developer Agent có thể sẽ cần chia nhỏ (Sub-tasks) kĩ càng khi implement.

### Best Practices Compliance Checklist

- [ ] Epic delivers user value *(Fail: Epic 11 and Epic 9-DF are purely technical)*
- [x] Epic can function independently
- [x] Stories appropriately sized *(Mostly Pass, some heavy UI logic)*
- [x] No forward dependencies *(Pass: Dependencies are strictly linear or backward-looking)*
- [ ] Database tables created when needed *(Warning: Upfront DB init in Story 1.1 needs careful scoping)*
- [x] Clear acceptance criteria *(Pass: Excellent GIVEN/WHEN/THEN adoption)*
- [x] Traceability to FRs maintained *(Pass: 100% Coverage)*

### Remediation Guidance (Hướng dẫn khắc phục)
Mặc dù có các vi phạm về "Technical Epics", nhưng xét trên thực tế bối cảnh (Brownfield Context) và tính chất phức tạp của hệ thống Multi-Agent, việc duy trì Epic 9-DF và Epic 11 mang lại sự rõ ràng trong quản trị rủi ro kiến trúc. 
## Summary and Recommendations

### Overall Readiness Status

**READY** (Với Technical Debt đã biết)

### Critical Issues Requiring Immediate Action

Không có blocker kỹ thuật hoặc rủi ro mất dấu (missing requirement) nào ngăn cản việc lập trình. Tất cả 53 FRs đã được map 100%. Tuy nhiên, cần chú ý:
1. **Quản trị Timing Migration Database:** Đội Dev phải kiểm soát chặt chẽ việc tạo bảng (Epic 1 vs Epic 9-DF) để tránh tạo dư thừa bảng không cần thiết từ sớm.
2. **Khối lượng Story:** Cần cảnh giác với độ phức tạp của các Story trong Epic 10 (vd: 10-2, 10-4).

### Recommended Next Steps

1. Tiến hành Handoff dự án sang cho Developer Agent (`bmad-agent-dev`) để bắt đầu code trực tiếp dựa trên Epic list.
2. Dev Agent khi triển khai Story 1.1 cần ghi chú không chạy toàn bộ database migration mà chỉ chạy migration giới hạn cho User Schema.
3. Khi implement Epic 10, Dev Agent cần chủ động đề xuất cắt nhỏ (sub-task) nếu các logic tính toán Client-side trở nên quá lớn.

### Final Note

This assessment identified 2 structural issues (Technical Epics, DB Timing) across 4 categories (PRD, UX, Epic Coverage, Epic Quality). Address the critical issues before proceeding to implementation. These findings can be used to improve the artifacts or you may choose to proceed as-is. Hệ thống được đánh giá là ĐÃ SẴN SÀNG cho quá trình lập trình (Ready for Implementation).## UX Alignment Assessment

### UX Document Status

**Status: Found**
- `ux-design-specification.md` (Tài liệu UX cốt lõi)
- `ux-crypto-orchestra-handoff.md` (Tài liệu Handoff chuyên biệt)

### Alignment Issues

**UX ↔ PRD Alignment:**
- **Aligned:** Tài liệu UX phản ánh chính xác các User Journeys trong PRD, đặc biệt là Journey #8 (Crypto Power User) cho Epic 10. Các thiết kế như Split-Pane layout và Interactive Widgets trực tiếp hỗ trợ các FR49-FR53 (Phân tích Tokenomics, Risk Management, Liquidity Routing).
- **Aligned:** Các UX-DR (Design Requirements) như Micro-Sync Indicators và Offline Graceful Degradation được đặc tả chi tiết bằng UI Patterns, khớp hoàn toàn với FR10, FR11.

**UX ↔ Architecture Alignment:**
- **Aligned:** UX yêu cầu độ trễ tương tác <150ms và Auto-save Forms. Kiến trúc đáp ứng hoàn hảo thông qua Client-side computation (Zustand state management) và Zero-cache syncing (được chỉ định rõ trong ADR-001 và các dev notes của Epic 10).
- **Aligned:** Các yêu cầu cập nhật Realtime Streaming của UX được kiến trúc server FastAPI hỗ trợ qua Server-Sent Events (SSE).
- **Aligned:** Skeleton Loading pattern trong UX thay thế vòng xoay Spinner truyền thống, tương thích hoàn toàn với kiến trúc Streaming LLM và cơ chế gọi API song song của LangGraph.

### Warnings

Không có cảnh báo nghiêm trọng. Tuy nhiên, đội ngũ Frontend cần lưu ý kỹ thuật khi triển khai Bottom Sheet trên Mobile (thiết kế Degradation của Epic 10) để tránh xung đột thao tác cuộn trên trình duyệt iOS Safari. Kiến trúc tổng thể và tài liệu hoàn toàn sẵn sàng cho quá trình implement. ## Epic Coverage Validation

### Coverage Matrix

| FR Number | PRD Requirement | Epic Coverage | Status |
| --------- | --------------- | ------------- | ------ |
| FR1 | Người dùng có thể tải lên các tệp tài liệu (PDF, TXT) | Epic 2 | ✓ Covered |
| FR2 | Người dùng có thể xem lại danh sách các tài liệu đã tải lên | Epic 2 | ✓ Covered |
| FR3 | Người dùng có thể xem được trạng thái tiến trình trích xuất | Epic 2 | ✓ Covered |
| FR4 | Người dùng có thể xóa một tài liệu khỏi workspace | Epic 2 | ✓ Covered |
| FR5 | Người dùng có thể tạo một phiên hỏi đáp mới | Epic 3 | ✓ Covered |
| FR6 | Người dùng có thể gửi câu hỏi dạng văn bản | Epic 3 | ✓ Covered |
| FR7 | Người dùng nhận luồng phản hồi trực tiếp (Streaming) | Epic 3 | ✓ Covered |
| FR8 | Người dùng có thể xem lại danh sách các phiên trò chuyện cũ | Epic 4 | ✓ Covered |
| FR9 | Người dùng có thể đọc lại toàn bộ nội dung tin nhắn cũ | Epic 4 | ✓ Covered |
| FR10 | Đọc danh sách tài liệu và nội dung chat khi ngắt kết nối (Offline) | Epic 4 | ✓ Covered |
| FR11 | Nhận biết được trạng thái đồng bộ dữ liệu (Online/Offline/Syncing) | Epic 4 | ✓ Covered |
| FR12 | Hệ thống tự động bóc tách văn bản và tạo Vector Embeddings | Epic 2 | ✓ Covered |
| FR13 | Hệ thống có khả năng chặn yêu cầu (Rate Limit) | Epic 2 | ✓ Covered |
| FR14 | Người dùng có thể xác thực (Authentication) để đăng nhập | Epic 1 | ✓ Covered |
| FR15 | Xem bảng giá (Pricing) cho các gói cước | Epic 5 | ✓ Covered |
| FR16 | Đăng ký gói cước và thanh toán an toàn qua Stripe | Epic 5 | ✓ Covered |
| FR17 | Tự động theo dõi lượng sử dụng và cập nhật trạng thái gói cước | Epic 5 | ✓ Covered |
| FR18 | Mua gift subscription thanh toán one-time qua Stripe | Epic 6 | ✓ Covered |
| FR19 | Tạo gift code duy nhất sau khi thanh toán hoặc admin duyệt | Epic 6 | ✓ Covered |
| FR20 | Xem gift code và link redeem để chia sẻ cho người nhận | Epic 6 | ✓ Covered |
| FR21 | Người nhận có thể redeem gift code | Epic 6 | ✓ Covered |
| FR22 | Kích hoạt hoặc cộng dồn thời gian subscription | Epic 6 | ✓ Covered |
| FR23 | Submit gift request để admin duyệt thủ công | Epic 6 | ✓ Covered |
| FR24 | Kích hoạt tính năng deep research từ chat | Epic 7 | ✓ Covered |
| FR25 | Sử dụng Chainlens B2B API làm primary engine cho deep research | Epic 7 | ✓ Covered |
| FR26 | Admin/DevOps bật/tắt tích hợp Chainlens qua biến môi trường | Epic 7 | ✓ Covered |
| FR27 | Sub-agent Tokenomics Analyst | Epic 9 | ✓ Covered |
| FR28 | Sub-agent Whale Tracker | Epic 9 | ✓ Covered |
| FR29 | Sub-agent Token Unlock Scheduler | Epic 9 | ✓ Covered |
| FR30 | Sub-agent Yield Optimizer | Epic 9 | ✓ Covered |
| FR31 | Sub-agent Governance Analyst | Epic 9 | ✓ Covered |
| FR32 | Sub-agent Technical Analyst | Epic 9 | ✓ Covered |
| FR33 | Spawn multiple crypto sub-agents song song | Epic 9 | ✓ Covered |
| FR34 | Smart Agent Selection | Epic 9 | ✓ Covered |
| FR35 | Graceful Degradation | Epic 9 | ✓ Covered |
| FR36 | Crypto Data Schema | Phase 3 Data Foundation (Epic 9-DF) | ✓ Covered |
| FR37 | CryptoDataCacheMiddleware | Phase 3 Data Foundation (Epic 9-DF) | ✓ Covered |
| FR38 | Thundering Herd Protection | Phase 3 Data Foundation (Epic 9-DF) | ✓ Covered |
| FR39 | Background Data Refresh | Phase 3 Data Foundation (Epic 9-DF) | ✓ Covered |
| FR40 | Workspace Watchlist API | Phase 3 Data Foundation (Epic 9-DF) | ✓ Covered |
| FR41 | SSE Heartbeat & Auto-Reconnect | Epic 11 | ✓ Covered |
| FR42 | Circuit Breaker Hardening | Epic 11 | ✓ Covered |
| FR43 | Orphaned Cache Purge | Epic 11 | ✓ Covered |
| FR44 | Per-API Token Bucket Rate Limiters | Epic 11 | ✓ Covered |
| FR45 | Client-Side Quota Enforcement | Epic 11 | ✓ Covered |
| FR46 | Quản lý vòng đời FastAPI Backend binary trong Electron | Epic 8 | ✓ Covered |
| FR47 | Đồng bộ Metadata file cục bộ tự động qua Zero-sync | Epic 8 | ✓ Covered |
| FR48 | Dynamic Hybrid LLM Routing | Epic 8 | ✓ Covered |
| FR49 | Entity Resolution (Gom nhóm ví, phân tích dòng tiền) | Epic 10 | ✓ Covered |
| FR50 | Protocol Revenue Modeling (P/E, P/S, biểu đồ áp lực bán) | Epic 10 | ✓ Covered |
| FR51 | Narrative & Macro Correlation (Heatmap, NLP sentiment) | Epic 10 | ✓ Covered |
| FR52 | Enterprise Risk Management (Portfolio stress testing, VaR) | Epic 10 | ✓ Covered |
| FR53 | Liquidity Routing (Phân tích sổ lệnh CEX/DEX) | Epic 10 | ✓ Covered |

### Missing Requirements

Tất cả các tính năng chức năng (Functional Requirements - FRs) từ PRD đều đã được ánh xạ (mapped) thành công vào các Epic và Story. KHÔNG PHÁT HIỆN YÊU CẦU NÀO BỊ THIẾU SÓT (No missing FRs detected). Các Epics đã phủ toàn bộ 53 FRs. Đáng chú ý, các FR49-FR53 (Institutional Terminal) đã được đối chiếu khớp với các Stories từ 10-1 đến 10-5 mà chúng ta vừa rà soát và sinh ra ở phiên làm việc này.

### Coverage Statistics

- Total PRD FRs: 53
- FRs covered in epics: 53
- Coverage percentage: 100%
