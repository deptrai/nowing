# Story 10.4: Quản Trị Rủi Ro Cấp Độ Quỹ (Enterprise Risk Management)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**Là một** Portfolio Manager / Risk Officer,
**Tôi muốn** stress-test danh mục của mình và quét các rủi ro pháp lý/bảo mật,
**Để** đảm bảo an toàn vốn tối đa trước các sự kiện thiên nga đen (Black Swan) và các thay đổi quy định.

## Acceptance Criteria

1. **AI Smart Contract Vulnerability Scanner:**
   - **Given** địa chỉ của một smart contract hoặc một mã token.
   - **When** người dùng yêu cầu "Security Scan" hoặc hỏi về rủi ro của token đó.
   - **Then** hệ thống (qua Sub-Agent) tổng hợp dữ liệu từ GoPlus Security API (hoặc các nguồn tương đương qua `chainlens_deep_research`).
   - **And** LLM đưa ra tóm tắt rủi ro bảo mật (ví dụ: "Có hàm mint() không giới hạn", "Owner có quyền đóng băng quỹ").

2. **Portfolio Stress Testing (Mô phỏng rủi ro danh mục):**
   - **Given** danh mục đầu tư (Portfolio) hiện tại của người dùng.
   - **When** người dùng thiết lập một kịch bản rủi ro trên Widget (ví dụ: "Thị trường sập 30%", "Stablecoin X de-peg 10%").
   - **Then** hệ thống (tính toán Client-side) tính toán và hiển thị Max Drawdown dự kiến của toàn bộ danh mục trên biểu đồ Value-at-Risk (VaR).
   - **And** chỉ ra những tài sản nào trong danh mục dễ bị tổn thương nhất (Highest Beta to the downside).

3. **Regulatory Impact Analyzer (Cảnh báo Pháp lý):**
   - **Given** danh mục token của người dùng.
   - **When** Sub-Agent quét tin tức pháp lý mới nhất (qua CryptoPanic hoặc `chainlens_deep_research`).
   - **Then** hệ thống tự động cắm cờ (Flag) các token có rủi ro pháp lý cao trên UI.
   - **And** hiển thị giải thích từ AI (ví dụ: "Token này đang bị SEC điều tra trong vụ kiện với sàn Y").

## Tasks / Subtasks

- [ ] Task 1: Thiết lập LangGraph Sub-Agent (`risk_management_officer`) (AC: 1, 3)
  - [ ] Tạo `risk_management_officer_spec.py` đăng ký vào `SubAgentMiddleware`.
  - [ ] Tích hợp GoPlus Security API (đã có từ Epic 0) và thêm các tools kiểm tra rủi ro pháp lý.
  - [ ] Tích hợp luồng `chainlens_deep_research` để tìm kiếm tin tức pháp lý mới nhất.
- [ ] Task 2: Phát triển Interactive Stress Test Widget (AC: 2)
  - [ ] Xây dựng `RiskDashboard` và `StressTestSimulator` components trong Context Pane.
  - [ ] Cài đặt engine mô phỏng Client-side (tương tự như Tokenomics Sandbox của Story 10.2).
  - [ ] Sử dụng Recharts để vẽ biểu đồ Value-at-Risk (VaR) thay đổi realtime khi kéo thanh trượt (Market Shock).
- [ ] Task 3: Xử lý Kiến trúc Dữ liệu & UI Feedback (AC: 1, 3)
  - [ ] Áp dụng `CryptoDataCacheMiddleware` cho các endpoint kiểm tra bảo mật (GoPlus).
  - [ ] Hiển thị Skeleton Loader cho biểu đồ rủi ro trong lúc chờ xử lý.
  - [ ] Đảm bảo các cờ cảnh báo (Flag) hiển thị màu Đỏ/Cam chuẩn xác theo hệ thống Design System Zinc/Slate.

## Dev Notes

- **Kiến trúc (Architecture Requirements):** Mọi tính toán mô phỏng Stress Test phải chạy trên Client-side (React/Zustand) để đảm bảo độ mượt <150ms. Không gửi request tính toán lại về Backend khi người dùng chỉ đang kéo thanh trượt. Giống như các story khác trong Epic 10, **SẼ KHÔNG** dùng Elasticsearch hay Kafka cho Regulatory News; sử dụng các API tin tức hiện có và `chainlens_deep_research` để giảm độ phức tạp hệ thống, cache qua Postgres + Zero.
- **Graceful Degradation:** Nếu API bảo mật (GoPlus) sập, Agent trả về "Dữ liệu bảo mật on-chain hiện không khả dụng" một cách graceful, không làm sập toàn bộ câu trả lời phân tích rủi ro.

### Project Structure Notes

- Backend Agent: `nowing_backend/app/agents/new_chat/subagents/crypto/risk_management_spec.py`
- Frontend Components: `app/components/chat/context-pane/sandbox/StressTestSimulator.tsx` và `RiskDashboard.tsx`.

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Split-Pane & Interactive Widget Patterns`]
- [Source: `_bmad-output/planning-artifacts/epics.md#Epic 10: Institutional Research & Risk Management Terminal`]
- [Source: ADR-001-crypto-data-layer.md]

## Dev Agent Record

### Agent Model Used



### Debug Log References

### Completion Notes List

### File List
