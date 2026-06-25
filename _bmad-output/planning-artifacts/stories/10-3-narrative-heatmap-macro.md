# Story 10.3: Đón Đầu Xu Hướng Bằng Heatmap & Phân Tích Vĩ Mô (Narrative Heatmap & Macro Correlation)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**Là một** VC Fund Analyst / Crypto Researcher,
**Tôi muốn** theo dõi sự dịch chuyển của các "narrative" và mối tương quan vĩ mô của tài sản thông qua một Heatmap trực quan,
**Để** tôi có thể phân bổ vốn sớm trước khi xu hướng phản ánh vào giá và quản trị rủi ro vĩ mô.

## Acceptance Criteria

1. **Cross-Platform Narrative Heatmap Visualization:**
   - **Given** dữ liệu văn bản từ API phân tích (ví dụ: CoinGecko Trending, CryptoPanic hoặc dữ liệu từ `chainlens_deep_research`).
   - **When** người dùng mở tính năng "Narrative Heatmap".
   - **Then** UI hiển thị một biểu đồ Treemap (khối vuông) trong Split-Pane.
   - **And** kích thước khối vuông đại diện cho "Khối lượng thảo luận" (Mention Volume) hoặc Market Cap của Narrative đó.
   - **And** màu sắc (Color scale: Đỏ -> Xanh) đại diện cho Sentiment (từ Tiêu cực đến Tích cực).
   - **And** người dùng có thể nhấp (Drill-down) vào một khối (ví dụ "AI") để xem các token cụ thể thuộc narrative đó.

2. **Macro-Crypto Correlation Matrix:**
   - **Given** dữ liệu giá token và dữ liệu vĩ mô cơ bản (DXY, NASDAQ) được fetch qua API (ví dụ: Yahoo Finance hoặc proxy endpoint).
   - **When** người dùng xem chi tiết một token hoặc một narrative.
   - **Then** hệ thống (tính toán ở Backend) hiển thị Ma trận Tương quan (Pearson correlation heatmap) trong khung thời gian 30D/90D.
   - **And** Agent đưa ra nhận định tự động (ví dụ: "Token này có hệ số beta cao với NASDAQ").

3. **One-Click Deep Dive Research Report (Tích hợp RAG):**
   - **Given** một narrative đang nổi bật trên Heatmap.
   - **When** người dùng bấm nút "Generate Deep Dive Report" trên Widget.
   - **Then** Agent tự động kích hoạt luồng `chainlens_deep_research` để thu thập dữ liệu và tổng hợp thành bản báo cáo chuyên sâu.
   - **And** báo cáo hiển thị chuẩn cấu trúc Markdown, hỗ trợ tải xuống (Download) dạng file hoặc lưu lại trong bộ nhớ phiên.

## Tasks / Subtasks

- [ ] Task 1: Thiết lập LangGraph Sub-Agent (`macro_narrative_analyst`) (AC: 2, 3)
  - [ ] Tạo `macro_narrative_analyst_spec.py` đăng ký vào `SubAgentMiddleware`.
  - [ ] Thêm tools lấy dữ liệu vĩ mô (Macro Data) và tính toán ma trận tương quan (Correlation Engine bằng Python/Pandas).
  - [ ] Tích hợp `chainlens_deep_research` vào bộ công cụ của Sub-Agent này.
- [ ] Task 2: Phát triển Component Treemap & Correlation Matrix (AC: 1, 2)
  - [ ] Xây dựng `NarrativeTreemap` component (sử dụng ECharts hoặc Nivo) cho Context Pane.
  - [ ] Xây dựng `CorrelationHeatmap` component.
  - [ ] Đảm bảo cả hai biểu đồ có fallback sang "Table View" để đảm bảo A11y.
- [ ] Task 3: Caching & Architecture Compliance (AC: 1)
  - [ ] Áp dụng `CryptoDataCacheMiddleware` cho các endpoint dữ liệu Vĩ mô & Narrative.
  - [ ] Sử dụng Skeleton Loading cho Treemap trong quá trình chờ SSE response.

## Dev Notes

- **Kiến trúc (Architecture Requirements):** Mặc dù bản gốc mô tả việc dùng Elasticsearch & Kafka, tuy nhiên ở giai đoạn Epic 10 này theo Kiến trúc đã duyệt (ADR-001), hệ thống **SẼ KHÔNG** triển khai Kafka hay Elasticsearch để giảm độ phức tạp. Thay vào đó, ta dựa vào External APIs (CoinGecko Trending, CryptoPanic Sentiment) và công cụ `chainlens_deep_research` của Epic 7 để bù đắp dữ liệu Narrative. Caching thông qua Postgres + Zero-sync.
- **Graceful Degradation:** Nếu dữ liệu Vĩ mô (Yahoo/FRED) không gọi được do rate limit, Tool phải trả về Error JSON chuẩn để Orchestrator thông báo "Dữ liệu vĩ mô hiện không khả dụng" và bỏ qua phần biểu đồ Correlation.
- **Responsive UI:** Trên thiết bị Mobile, Treemap tự động thu nhỏ hoặc chuyển sang danh sách list view thông thường trong Bottom Sheet.

### Project Structure Notes

- Backend Agent: `nowing_backend/app/agents/new_chat/subagents/crypto/macro_narrative_spec.py`
- Backend Tools: Cần thêm `nowing_backend/app/agents/new_chat/tools/macro_data.py` (cho dữ liệu DXY, NASDAQ).
- Frontend Components: `app/components/chat/context-pane/NarrativeTreemap.tsx` và `CorrelationHeatmap.tsx`.

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Split-Pane & Interactive Widget Patterns`]
- [Source: `_bmad-output/planning-artifacts/epics.md#Epic 10: Institutional Research & Risk Management Terminal`]

## Dev Agent Record

### Agent Model Used



### Debug Log References

### Completion Notes List

### File List
