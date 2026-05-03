# Story 10.5: Công Cụ Khai Thác Thanh Khoản & Arbitrage (Liquidity Routing Insights)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**Là một** Institutional Trader / Giám đốc Thanh khoản,
**Tôi muốn** xem độ sâu sổ lệnh và các cơ hội Arbitrage/Yield đa chuỗi,
**Để** thực hiện các lệnh giao dịch quy mô lớn (block trades) mà không bị trượt giá (slippage) nặng và tối ưu hóa dòng tiền nhàn rỗi.

## Acceptance Criteria

1. **Liquidity Depth Profiler (Hồ sơ Độ sâu Thanh khoản):**
   - **Given** một token cụ thể (VD: $LINK) và API của Aggregator (VD: 1inch API, 0x API).
   - **When** người dùng nhập số lượng muốn giao dịch (VD: Bán 1 triệu USD) trên giao diện Widget.
   - **Then** hệ thống tổng hợp độ sâu sổ lệnh (Orderbook depth) từ các pool DEX.
   - **And** UI hiển thị biểu đồ "Trượt giá dự kiến" (Estimated Slippage Curve) cho từng mức khối lượng (tính toán Client-side).

2. **Block Trade Execution Routing (Gợi ý định tuyến lệnh):**
   - **Given** kết quả từ Liquidity Profiler.
   - **When** người dùng yêu cầu gợi ý thực thi.
   - **Then** Sub-Agent cung cấp chiến lược phân bổ lệnh (ví dụ: "Bán 40% trên Binance, 30% qua Uniswap v3 qua các giao dịch nhỏ giọt (TWAP) trong 2 giờ tới").
   - **And** Agent chỉ ra rõ rủi ro Price Impact nếu thực hiện Market Order một lần.

3. **Cross-Chain Safe Yield Scanner (Trình quét Yield an toàn):**
   - **Given** danh mục vốn nhàn rỗi (Stablecoins) và dữ liệu từ DefiLlama Yields.
   - **When** người dùng tìm kiếm lợi suất (Yield).
   - **Then** hệ thống quét các chain để tìm các pool lợi suất.
   - **And** hệ thống lọc các pool này bằng cách sử dụng chung logic đánh giá rủi ro bảo mật (GoPlus) từ Sub-Agent của Story 10.4 để loại bỏ các pool rủi ro cao, chỉ hiển thị "Risk-adjusted Yield".

## Tasks / Subtasks

- [ ] Task 1: Thiết lập LangGraph Sub-Agent (`liquidity_routing_expert`) (AC: 2, 3)
  - [ ] Tạo `liquidity_routing_expert_spec.py` đăng ký vào `SubAgentMiddleware`.
  - [ ] Thiết lập Tools: `get_aggregated_liquidity_depth` (qua 1inch/0x API), `simulate_trade_slippage`, `scan_cross_chain_safe_yields`.
  - [ ] Đảm bảo Sub-Agent có thể truy cập kết quả quét bảo mật từ các tool của GoPlus.
- [ ] Task 2: Phát triển Liquidity Widget (AC: 1)
  - [ ] Xây dựng `LiquidityProfilerWidget` trong Context Pane.
  - [ ] Sử dụng thư viện Recharts để vẽ biểu đồ Slippage Curve mô phỏng theo số lượng nhập vào.
  - [ ] Cung cấp nút `Table View Toggle` cho Accessibility (A11y).
- [ ] Task 3: Xử lý Kiến trúc & Caching (AC: 1, 3)
  - [ ] Áp dụng `CryptoDataCacheMiddleware` cho các lệnh gọi 1inch/0x API để tránh rate limit.
  - [ ] Render Skeleton Loading State cho biểu đồ trong khi API tính toán slippage.

## Dev Notes

- **Kiến trúc (Architecture Requirements):** Tránh việc duy trì Websocket trực tiếp tới Orderbook của các sàn CEX (như bản draft cũ) vì quá tốn tài nguyên và không phù hợp với kiến trúc Stateless Backend hiện tại. Thay vào đó, sử dụng các API Aggregator (1inch, 0x) để lấy Snapshot độ sâu thanh khoản tại thời điểm Request, đi qua `CryptoDataCacheMiddleware` (ADR-001) với TTL rất ngắn (ví dụ 30-60 giây).
- **Mô phỏng Client-side:** Biểu đồ trượt giá nên được nội suy và vẽ lại trên Client (React) khi người dùng kéo thanh trượt khối lượng, dựa trên snapshot dữ liệu thanh khoản đã lấy được, đảm bảo độ mượt UI <150ms.
- **Graceful Degradation:** Nếu API 1inch bị rate-limit, trả về Error JSON để LLM xuất câu trả lời text thân thiện "Dữ liệu độ sâu thanh khoản hiện không khả dụng" và vô hiệu hóa Widget biểu đồ.

### Project Structure Notes

- Backend Agent: `nowing_backend/app/agents/new_chat/subagents/crypto/liquidity_routing_spec.py`
- Frontend Components: `app/components/chat/context-pane/sandbox/LiquidityProfilerWidget.tsx`
- Đảm bảo tuân thủ Naming Convention (Python snake_case, TS camelCase).

### References

- [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Split-Pane & Interactive Widget Patterns`]
- [Source: `_bmad-output/planning-artifacts/epics.md#Epic 10: Institutional Research & Risk Management Terminal`]
- [Source: ADR-001-crypto-data-layer.md]

## Dev Agent Record

### Agent Model Used



### Debug Log References

### Completion Notes List

### File List
