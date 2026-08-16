# Story 24.2: Waterfall Phone & B2B Tax Code (MST) Corporate Verification Engine

Status: `ready-for-dev`
Epic: `epic-24`

## Story Overview

As a B2B sales development representative or data sourcer,
I want scraped entity leads to be automatically enriched with verified corporate tax IDs (Mã Số Thuế - MST), legal representatives, charter capital, and phone number validation,
So that outreach teams target legitimate companies with high purchasing power and reach actual decision-makers.

---

## Architectural Invariants
- **INV-24.3 (Waterfall Phone & Tax Code Isolation):** Caching kết quả tra cứu MST và Zalo UID trên Redis (TTL 24h) với Circuit Breaker.
- **INV-21.3 (Privacy & PII Vault):** Mã hóa SĐT bằng HMAC và mã hóa đối xứng khi lưu trữ, phân quyền hiển thị theo Role.

---

## Acceptance Criteria

1. **B2B Corporate Tax Registry Integration:**
   - Kết nối API tra cứu thông tin doanh nghiệp (masothue, thongtindoanhnghiep, dangkykinhdoanh).
   - Tự động trích xuất: Mã Số Thuế (MST), Tên pháp nhân, Người đại diện pháp luật, Vốn điều lệ, Ngày cấp phép, Địa chỉ trụ sở, Trạng thái (Đang hoạt động / Tạm ngừng).
2. **3-Tier Waterfall Phone Validation:**
   - *Tier 1:* Số điện thoại từ tin đăng / danh thiếp công khai.
   - *Tier 2:* Kiểm tra số có đăng ký Zalo / WhatsApp hay không qua Zalo UID lookup.
   - *Tier 3:* Đối chiếu số điện thoại người đại diện pháp luật từ cổng thông tin đăng ký doanh nghiệp.
3. **National DNC & Carrier Formatting:**
   - Chuẩn hóa định dạng chuẩn E.164 (`+84...`).
   - Loại trừ tự động các số nằm trong danh sách không nhận cuộc gọi rác (DNC Quốc gia).
4. **Verified Badges in Split-View Table Matrix:**
   - Hiển thị huy hiệu `MST Verified` (màu xanh lá) và `Zalo Active` trên bảng dữ liệu.

---

## Technical Tasks
- [ ] Backend: Xây dựng `CorporateVerificationService` kết nối API tra cứu MST.
- [ ] Backend: Nâng cấp `PhoneWaterfallService` hỗ trợ Tier 3 tra cứu MST Representative.
- [ ] Backend: Bổ sung các trường `tax_id`, `legal_representative`, `charter_capital`, `company_status` vào schema `leads`.
- [ ] Frontend: Hiển thị tooltip chi tiết pháp lý công ty khi click vào MST trong Table Matrix.
- [ ] Unit & Integration Tests: Test trích xuất MST, test cache hit/miss trên Redis, test chuẩn hóa E.164.
