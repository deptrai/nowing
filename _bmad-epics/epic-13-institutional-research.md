# Epic 13: Institutional Research & Risk Management Terminal

**Trạng thái:** 📝 ĐANG LÊN KẾ HOẠCH (PLANNING)
**Giai đoạn:** Phase 5 (Extension/Web Hybrid)
**Mức độ ưu tiên:** P2 (Chiến lược dài hạn - Mở rộng tệp khách hàng Institutional/B2B)

## Tổng quan Epic

Nâng cấp Nowing từ một công cụ hỗ trợ giao dịch cá nhân (Retail Crypto Co-pilot) thành một Terminal Nghiên cứu và Quản trị Rủi ro chuyên sâu phục vụ cho các Crypto Researchers, Institutional Investors, VC Funds và HNWI. Epic này tập trung vào phân tích on-chain sâu, mô hình hóa tài chính giao thức, và quản trị rủi ro ở quy mô danh mục.

**Giá trị kinh doanh (Business Value):**
- **Thu hút dòng vốn lớn:** Mở khóa tệp khách hàng có khả năng chi trả cao (B2B/Premium Subscription liên kết trực tiếp với Epic 5 Billing).
- **Lợi thế cạnh tranh độc quyền:** Chuyển đổi dữ liệu on-chain thô thành actionable insights cấp quỹ mà các tool retail thông thường không có.
- **Giữ chân người dùng:** Biến Nowing thành công cụ không thể thiếu hàng ngày của các chuyên gia nghiên cứu.

---

## User Stories

### Story 13.1: Phân Tích Thực Thể & Dòng Tiền Thông Minh (Entity Resolution & Smart Money Flow)
**Là một** Crypto Researcher,
**Tôi muốn** hệ thống tự động gom nhóm các địa chỉ ví và phân tích luồng tiền giữa chúng,
**Để** tôi có thể theo dõi hành vi của các quỹ đầu tư lớn, Market Makers và phát hiện các ví nội bộ (insider wallets) gom hàng.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Tính năng Entity Clustering: Gom nhóm ví dựa trên mô hình giao dịch và tương tác.
- [ ] Gắn nhãn tự động (Auto-labeling) cho các ví nghi ngờ là Dev/Insider.
- [ ] Biểu đồ Sankey trực quan hóa dòng tiền (inflow/outflow) giữa các nhóm thực thể.
- [ ] Cảnh báo realtime khi có dòng vốn bất thường từ Smart Money vào một token vốn hóa nhỏ.

### Story 13.2: Phân Tích Tokenomics & Lợi Suất Thực (Advanced Protocol Revenue & Tokenomics)
**Là một** Institutional Investor,
**Tôi muốn** xem các chỉ số tài chính truyền thống (như P/E, P/S) và dự phóng lạm phát của token,
**Để** đánh giá tính bền vững dài hạn của giao thức trước khi rót vốn.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Tích hợp API (như Token Terminal/DefiLlama) để hiển thị Real Yield, Protocol Revenue.
- [ ] AI tự động phân tích smart contract và lịch vesting để vẽ biểu đồ áp lực bán (Sell Pressure Chart) dự kiến trong 12 tháng.
- [ ] Tokenomics Sandbox: Cho phép thay đổi các biến số (burn rate, emission) để AI mô phỏng giá trị mạng lưới trong tương lai.

### Story 13.3: Đón Đầu Xu Hướng Bằng Heatmap & Phân Tích Vĩ Mô (Narrative Heatmap & Macro Correlation)
**Là một** VC Fund Analyst,
**Tôi muốn** theo dõi sự dịch chuyển của các "narrative" và mối tương quan vĩ mô của tài sản,
**Để** tôi có thể phân bổ vốn sớm trước khi xu hướng phản ánh vào giá.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Quét và phân tích NLP trên Github, Governance Forums, và Twitter để đánh giá mức độ quan tâm (Heatmap).
- [ ] Ma trận tương quan (Correlation Matrix) giữa token và các chỉ số như DXY, NASDAQ.
- [ ] Chức năng "Tạo Báo Cáo Nghiên Cứu": 1-click tổng hợp dữ liệu on-chain và sentiment thành báo cáo dạng PDF/Notion.

### Story 13.4: Quản Trị Rủi Ro Cấp Độ Quỹ (Enterprise Risk Management)
**Là một** Portfolio Manager,
**Tôi muốn** stress-test danh mục của mình và quét rủi ro pháp lý/bảo mật,
**Để** đảm bảo an toàn vốn tối đa trước các sự kiện thiên nga đen.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] AI Smart Contract Scanner: Tóm tắt rủi ro bảo mật từ mã nguồn hoặc báo cáo audit bên thứ 3.
- [ ] Portfolio Stress Testing: Cho phép giả lập kịch bản (ví dụ: BTC giảm 20%) để tính toán Max Drawdown của danh mục hiện tại.
- [ ] Tự động cắm cờ (flag) các tài sản có rủi ro pháp lý cao (ví dụ: thuộc diện bị SEC kiện).

### Story 13.5: Công Cụ Khai Thác Thanh Khoản & Arbitrage (Liquidity Routing Insights)
**Là một** Institutional Trader,
**Tôi muốn** xem độ sâu sổ lệnh và các cơ hội Arbitrage/Yield đa chuỗi,
**Để** thực hiện các lệnh lớn mà không bị trượt giá và tối ưu hóa dòng tiền nhàn rỗi.

**Tiêu chí chấp nhận (Acceptance Criteria):**
- [ ] Liquidity Depth Profiler: Phân tích và trực quan hóa độ sâu thanh khoản trên cả CEX và DEX.
- [ ] Gợi ý chiến lược xả/gom hàng dựa trên dữ liệu thanh khoản realtime.
- [ ] Scanner tìm kiếm Yield an toàn (risk-adjusted) tốt nhất cho Stablecoin trên đa chuỗi.

---

## Các Phụ Thuộc Kỹ Thuật (Technical Dependencies)
- **Data Providers:** Nansen API, Arkham Intelligence, Token Terminal, DefiLlama.
- **AI & RAG:** Mở rộng RAG để index các báo cáo audit, tài liệu pháp lý và thảo luận Governance.
- **Backend:** Cần hạ tầng xử lý stream dữ liệu on-chain cường độ cao (Apache Kafka/Kafka streams hoặc tương đương) để phân tích Entity.
- **Frontend:** Cần các thư viện biểu đồ nâng cao (ví dụ: D3.js hoặc Recharts cho biểu đồ Sankey và Heatmaps).
