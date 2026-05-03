---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Tính năng nâng cao cho Crypto Researchers & Institutional Investors'
session_goals: 'Phát triển Nowing từ Retail Co-pilot thành Institutional Data Terminal'
selected_approach: 'Phân tích tài liệu hiện tại và đề xuất tính năng chiến lược'
techniques_used: ['Tư duy hệ thống (Systems Thinking)', 'Phân tích khoảng trống (Gap Analysis)']
ideas_generated: ['Epic 13: Institutional Research Terminal', 'Smart Money Sankey Diagram', 'Macro Correlation Heatmap', 'Tokenomics Sandbox']
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Luisphan
**Date:** 2026-05-03

## Session Overview

**Topic:** Tính năng nâng cao cho Crypto Researchers & Institutional Investors
**Goals:** Phát triển Nowing từ Retail Co-pilot thành Institutional Data Terminal

### Context Guidance

Dự án Nowing 2.0 hiện tại (Epics 1-4, 9-12) đã có nền tảng cực tốt cho Retail Users (One-click analysis, cơ bản tracking whale, chat assistant). Mục tiêu của phiên làm việc là mở rộng tập khách hàng sang nhóm tổ chức (B2B, Quỹ đầu tư, HNWI).

### Session Execution & Outcomes

Phiên làm việc đã đi từ việc rà soát kiến trúc hiện tại đến việc thiết kế một Epic hoàn toàn mới, làm thay đổi định hướng hiển thị và xử lý dữ liệu của Nowing.

#### 1. Quyết định Chiến lược (Strategic Shift)
Thay vì chỉ thêm công cụ (tools) cho các AI Chatbots hiện tại, chúng ta quyết định nâng cấp Nowing thành một **Data Terminal** (Giao diện dạng Grid với các Widgets phức tạp, AI đóng vai trò Copilot bên cạnh). Quyết định này tạo ra một rào cản cạnh tranh lớn.

#### 2. Các Artifacts đã được tạo ra
- **Tích hợp PRD & Epics:** Tạo và thêm thành công **Epic 13: Institutional Research & Risk Management Terminal** vào hệ thống tài liệu cốt lõi (`prd.md` và `epics.md`), liên kết trực tiếp với Epic 5 (Billing).
- **Kiến trúc Mở rộng (Architecture Extension):** Tạo file `adrs/architecture-extension-epic13.md` định nghĩa hạ tầng dữ liệu lớn: Kafka/Spark cho Real-time Stream, Neo4j Graph DB cho Entity Clustering, và Elasticsearch cho NLP Heatmap.
- **Đặc tả Kỹ thuật Chuyên sâu (Deep Dives):**
  - **Story 13.1 (Smart Money Flow):** File `stories/13-1-smart-money-flow.md` và `research/smart_money_analyst_spec.md`. Xác định cách dùng Graph DB để tìm kiếm các ví ẩn danh và hiển thị qua biểu đồ Sankey.
  - **Story 13.2 (Protocol Revenue & Tokenomics):** File `stories/13-2-protocol-revenue-tokenomics.md`. Xây dựng Tokenomics Sandbox và agent định giá cơ bản (`fundamental_analyst`).
  - **Story 13.3 (Narrative Heatmap):** File `stories/13-3-narrative-heatmap.md`. Xác định cách dùng Elasticsearch và FinBERT để quét Github/Forums/Twitter tạo Treemap Heatmap và Ma trận tương quan Vĩ mô.
  - **Story 13.4 (Enterprise Risk Management):** File `stories/13-4-enterprise-risk-management.md`. Thiết kế agent `risk_management_officer` và mô phỏng Stress Test cho danh mục.
  - **Story 13.5 (Liquidity Routing Insights):** File `stories/13-5-liquidity-routing-insights.md`. Thiết kế agent `liquidity_routing_expert`, tổng hợp Orderbook CEX/DEX và tư vấn xả/gom hàng tối ưu trượt giá.
- **Thiết kế Trải nghiệm Người dùng (UX/UI):** Cập nhật `ux-design-specification.md` (Phụ lục B), chuyển đổi từ giao diện Split-pane (MVP) sang Dynamic Grid Workspace với các chỉ báo Graceful Degradation cho Data Streaming.

#### 3. Kết luận
Nowing đã sẵn sàng cho giai đoạn phát triển nhắm tới khách hàng doanh nghiệp. Epic 13 cung cấp một tầm nhìn rõ ràng về dữ liệu, kiến trúc và giao diện để biến ứng dụng thành một cỗ máy nghiên cứu tiền điện tử chuyên nghiệp.
