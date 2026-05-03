# Story 10.2: Phân Tích Tokenomics & Lợi Suất Thực (Advanced Protocol Revenue & Tokenomics)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**Là một** Institutional Investor / Quản lý Danh mục,
**Tôi muốn** xem các chỉ số tài chính truyền thống (như P/E, P/S) và dự phóng áp lực bán từ lịch vesting (Tokenomics),
**Để** đánh giá tính bền vững dài hạn của giao thức và lên kế hoạch quản trị rủi ro giá (Price Risk) trước khi rót vốn lớn.

## Acceptance Criteria

1. **Fundamental Valuation Metrics (Các chỉ số định giá cơ bản):**
   - **Given** dữ liệu từ DefiLlama hoặc các API Tokenomics.
   - **When** người dùng yêu cầu phân tích Fundamentals của một token (VD: $UNI, $AAVE).
   - **Then** hệ thống (thông qua LLM) hiển thị bảng tóm tắt trong Context Pane: Protocol Revenue (30D, 1Y), Token Incentives (Lạm phát), Real Yield, P/E Ratio (Price-to-Earnings), và P/S Ratio (Price-to-Sales).
   - **And** LLM đưa ra so sánh tự động (VD: "P/E của UNI đang rẻ hơn 30% so với trung bình mảng DEX").

2. **Vesting & Sell Pressure Predictor (Dự phóng Áp lực bán):**
   - **Given** dữ liệu lịch trả token (Vesting Schedule) đã được lấy qua API (VD: TokenUnlocks hoặc public endpoints).
   - **When** người dùng mở "Vesting Chart" (hoặc AI tạo ra widget này ở Pane phải).
   - **Then** hiển thị biểu đồ kết hợp: Đường cung lưu hành dự kiến (Projected Circulating Supply) trong 12-36 tháng tới, và các cột đánh dấu các đợt Unlock lớn.
   - **And** LLM tự động tính toán "Estimated Sell Pressure" (Áp lực bán ước tính) bằng cách đối chiếu số lượng unlock với thanh khoản (Liquidity Depth) hiện tại.

3. **Tokenomics Scenario Sandbox (Mô phỏng Tokenomics):**
   - **Given** các biến số cơ bản của token (Burn rate, Emission rate, Staking ratio) được load vào Interactive Widget.
   - **When** người dùng kéo thanh trượt (Slider) để thay đổi giả định (VD: Tăng phí giao dịch lên 2%, giảm emission đi 50%).
   - **Then** hệ thống (tính toán hoàn toàn Client-side trên Frontend) vẽ lại biểu đồ dự phóng Market Cap & Token Price tương ứng với kịch bản đó trong 1-5 năm tới.
   - **And** thao tác kéo trượt phản hồi tức thì (Zero Friction, Auto-save state).

## Tasks / Subtasks

- [ ] Task 1: Mở rộng LangGraph Sub-Agent (`tokenomics_analyst`) (AC: 1, 2)
  - [ ] Nâng cấp prompt của `tokenomics_analyst_spec.py` để phân tích sâu Real Yield và P/E.
  - [ ] Cập nhật/Thêm tool lấy dữ liệu Revenue và Vesting Schedule (có bọc qua `CircuitBreakerMiddleware`).
- [ ] Task 2: Phát triển Component Sandbox & Biểu đồ (AC: 2, 3)
  - [ ] Tạo `TokenomicsSandbox` widget trong `app/components/chat/context-pane/`.
  - [ ] Phát triển engine tính toán Client-side (Zustand state + React Hooks) xử lý thay đổi thanh trượt mượt mà.
  - [ ] Tích hợp thư viện biểu đồ (Recharts) để render Vesting Chart và Simulated Price Chart.
- [ ] Task 3: Xử lý Caching & Kiến trúc Data (AC: 1)
  - [ ] Đảm bảo các lệnh gọi API lấy số liệu Tokenomics/Revenue được đi qua `CryptoDataCacheMiddleware` (ADR-001) để tận dụng Postgres caching.
  - [ ] Đảm bảo biểu đồ có "Table View Toggle" (A11y yêu cầu).

## Dev Notes

- **Kiến trúc (Architecture Requirements):** Mọi công thức giả lập (Sandbox) phải được thực thi ở Client-side (Next.js / React) để đảm bảo độ trễ < 150ms khi kéo Slider. Không gọi API về FastAPI khi người dùng chỉ đang thay đổi biến số.
- **Graceful Degradation:** Nếu API Tokenomics sập, Agent phải xuất ra được câu trả lời dạng Text Fallback ("Dữ liệu Vesting hiện không khả dụng...") và Widget bị disable nhẹ.
- **UX/UI:** Áp dụng Skeleton Loading cho các widget biểu đồ (không dùng Spinner).

### Project Structure Notes

- Backend Agent: Sửa đổi `nowing_backend/app/agents/new_chat/subagents/crypto/tokenomics_spec.py`
- Frontend Components: Tạo thư mục con cho `TokenomicsSandbox` tại `app/components/chat/context-pane/sandbox/`.
- Cấu trúc State: Mở rộng store để giữ trạng thái các Slider cho Sandbox (nhằm cho phép user chuyển tab đi chỗ khác và quay lại không mất state).

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Data Entry & Form Patterns`]
- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Split-Pane & Interactive Widget Patterns`]
- [Source: `_bmad-output/planning-artifacts/epics.md#Story 10.2`]

## Dev Agent Record

### Agent Model Used



### Debug Log References

### Completion Notes List

### File List
