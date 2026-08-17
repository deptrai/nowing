# UX Design Contract — Scraper Expansion & Multi-Domain Intelligence Engine

**Ngày lập:** 2026-08-15  
**Tác giả:** Sally (BMAD UX Designer & UI Specialist)  
**Trạng thái:** `APPROVED / READY FOR IMPLEMENTATION`  
**Các Epic Chi phối:** Epic 10 (Story 10.8), Epic 12 (Story 12.10), Epic 16 (Story 16.2, 16.5), Epic 17 (Story 17.2, 17.5), Epic 21 (Story 21.8, 21.9).

---

## 🎨 1. TỔNG QUAN HỆ THỐNG GIAO DIỆN (UI/UX DESIGN PHILOSOPHY)

Hệ thống giao diện cho các nguồn dữ liệu cào mới tuân thủ triết lý:
1. **Function-Driven & Frictionless:** Đưa các thông tin giá trị nhất (Số điện thoại, Giá tiền, Cảnh báo quy hoạch, Hạn nộp thầu) lên hàng đầu với 1-click action (Copy, Xem bản đồ, Tạo cảnh báo).
2. **Micro-Visual Signals:** Sử dụng các Badge trực quan, phân cực màu sắc rõ ràng (Xanh lá = An toàn/Giá giảm/Đất ở; Đỏ/Cam = Cảnh báo quy hoạch/Hạn thầu sắp hết).
3. **Zero-Flicker Realtime Sync:** Đồng bộ tức thì qua Zero Cache, cập nhật live countdown timer không cần F5 trình duyệt.

---

## 🛍️ 2. GIAO DIỆN THƯƠNG MẠI ĐIỆN TỬ (SHOPEE & TIKTOK SHOP — EPIC 17)

### U1. Widget Thẻ Sản Phẩm & Biểu Đồ Lịch Sử Giá trong Khung Chat (AI Product Card)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🛍️ [Shopee Mall] Chuột Không Dây Logitech MX Master 3S                     │
│ Shop: Logitech Official Store (TP. Hồ Chí Minh) ★ 4.9 (1.2k đánh giá)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Giá hiện tại: 1,890,000 ₫  [-24%]  │  Đã bán: 4,520 cái                    │
│ Giá gốc: 2,490,000 ₫              │  Doanh thu ước tính: 8.5 tỷ ₫          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 📈 Lịch sử biến động giá (90 ngày qua):                                    │
│  2.4M ──┐                                                                   │
│  2.1M   └───┐                                                               │
│  1.8M       └───────────● 1,890,000 ₫ (Đang ở mức thấp nhất lịch sử!)       │
│        15/06     01/07     15/07     01/08     15/08                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ 🔔 Đặt Cảnh Báo Giảm Giá ]   [ 🌐 Mở trên Shopee ]   [ 📋 So Sánh Giá ]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

* **Interaction Design:**
  * Click `[ 🔔 Đặt Cảnh Báo Giảm Giá ]` $\rightarrow$ Mở Popup thiết lập ngưỡng giá (`target_price`). Khi Shopee giảm xuống mức này, Nowing tự động bắn Telegram.
  * Hover vào điểm `●` trên biểu đồ đường $\rightarrow$ Tooltip hiển thị giá và ngày cụ thể.

---

## 🏛️ 3. GIAO DIỆN ĐẤU THẦU QUỐC GIA (MUASAMCONG — EPIC 16.5)

### U2. Thẻ Thông Báo Mời Thầu & Tóm Tắt AI (Tender Intelligence Card)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🏛️ [XÂY LẮP] Gói thầu số 05: Xây dựng trường THCS Cầu Giấy (Giai đoạn 2)     │
│ Số TBMT: IB2400198273  •  Chủ đầu tư: Ban QLDA ĐTXD Quận Cầu Giấy          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 💰 Giá gói thầu: 45,200,000,000 ₫ (45.2 tỷ)                                │
│ ⏳ Hạn đóng thầu: 09:00 - 25/08/2026  [ ⚠️ Còn 9 ngày 16 giờ ]             │
│ 📍 Địa điểm: Phường Dịch Vọng Hậu, Quận Cầu Giấy, Hà Nội                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🤖 Tóm Tắt AI Hồ Sơ Mời Thầu (E-HSMT - 145 trang):                          │
│ • Doanh thu bình quân 3 năm: Tối thiểu 65 tỷ VNĐ.                           │
│ • Hợp đồng tương tự: Đã hoàn thành 02 công trình giáo dục cấp II trở lên.   │
│ • Bảo đảm dự thầu: 680,000,000 ₫ (Bảo lãnh ngân hàng).                     │
│ • Nhân sự chủ chốt: Cần Chỉ huy trưởng có chứng chỉ hành nghề Hạng I.      │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ 📄 Tải Trọn Bộ E-HSMT (ZIP) ]   [ 🔔 Theo Dõi Kết Quả ]   [ 💬 Hỏi AI ]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

* **Visual Polish:** Badge `[ ⚠️ Còn 9 ngày 16 giờ ]` chuyển sang màu đỏ nhấp nháy khi thời gian đóng thầu còn $< 48$ giờ.

---

## 👥 4. GIAO DIỆN SOCIAL LEAD GENERATION (FACEBOOK & TWITTER/X — EPIC 21.8)

### U3. Thẻ Bài Đăng Mạng Xã Hội với Intent Tag & 1-Click Phone Copy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 👥 [Facebook Group] Hội Bất Động Sản Hà Nội (Chính Chủ & Môi Giới)          │
│ Tác giả: Nguyễn Văn An  •  Đăng lúc: 10 phút trước  [ 🏷️ INTENT: BÁN NHÀ ] │
├─────────────────────────────────────────────────────────────────────────────┤
│ "Chính chủ cần bán gấp nhà ngõ 68 Cầu Giấy, DT 45m2 x 5 tầng mới, ô tô đỗ   │
│ cửa, sổ đỏ vuông vắn sẵn sàng giao dịch. Giá 6.8 tỷ có thương lượng..."     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 📞 Liên hệ: [ 0912.345.678 ] (Click to Copy)  │ 📍 Cầu Giấy, Hà Nội         │
│ 💰 Giá bóc tách: 6,800,000,000 ₫             │ 📐 Diện tích: 45 m²         │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ 📋 Lưu Vào CRM Leads ]   [ 🗺️ Kiểm Tra Quy Hoạch ]   [ ↗ Mở Bài Gốc ]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

* **Micro-interactions:**
  * Click vào Pill `[ 0912.345.678 ]` $\rightarrow$ Copy vào Clipboard, hiện Toast *"Đã copy SĐT 0912.345.678!"* trong 1.5s.
  * Click `[ 🗺️ Kiểm Tra Quy Hoạch ]` $\rightarrow$ Tự động chuyển tọa độ địa chỉ sang công cụ GIS kiểm tra quy hoạch thửa đất.

---

## 💼 5. GIAO DIỆN LINKEDIN B2B INTELLIGENCE (EPIC 12.10 & 21.9)

### U4. Thẻ Doanh Nghiệp Mở Rộng & Danh Bạ Lãnh Đạo (B2B Hiring Velocity Card)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 💼 VNG Corporation  •  Công nghệ thông tin & Dịch vụ Phần mềm               │
│ Trụ sở: TP. Hồ Chí Minh  •  Quy mô: 2,000 - 5,000 nhân viên                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 🚀 Tín hiệu Tăng Trưởng (Hiring Velocity):                                  │
│ • Đang đăng tuyển: 48 vị trí mới trên LinkedIn trong 30 ngày qua (Tăng 65%)│
│ • Các phòng ban nóng: AI Research (12), Cloud Infra (8), Product (10)      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 👔 Danh Bạ Người Ra Quyết Định (Decision Makers):                           │
│ ┌─────────────────────────────┬─────────────────────────────┐               │
│ │ Lê Hồng Minh                │ Nguyễn Hoàng Nam            │               │
│ │ Founder & CEO               │ Head of Procurement / IT    │               │
│ │ [ 🔗 LinkedIn Profile ]     │ [ 🔗 LinkedIn Profile ]     │               │
│ └─────────────────────────────┴─────────────────────────────┘               │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ ✉️ Khởi Tạo Email Outreach ]   [ 🔔 Báo Khi Có Tuyển Thêm ]               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ 6. GIAO DIỆN QUY HOẠCH BĐS & PHÁP LÝ DOANH NGHIỆP (EPIC 10.8 & 16.2)

### U5. Popup Thẩm Định Quy Hoạch Đất Đai (Spatial Land Zoning Modal)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🗺️ Kết Quả Tra Cứu Quy Hoạch Đất Đai (Kỳ quy hoạch 2021 - 2030)            │
│ Địa chỉ: Số 45 Nguyễn Khang, Phường Yên Hòa, Quận Cầu Giấy, Hà Nội          │
├─────────────────────────────────────────────────────────────────────────────┤
│ [🟢 85% ĐẤT Ở ĐÔ THỊ (ODT)]    [🔴 15% ĐẤT GIAO THÔNG MỞ ĐƯỜNG (DGT)]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ ⚠️ CẢNH BÁO QUY HOẠCH:                                                      │
│ • Thửa đất nằm trong chỉ giới mở rộng đường Nguyễn Khang (lộ giới 20m).     │
│ • Phần diện tích bị cắt: ~6.5 m² mặt tiền.                                  │
│ • Phần còn lại: 38.5 m² hoàn toàn an toàn, được phép xây dựng tối đa 6 tầng.│
├─────────────────────────────────────────────────────────────────────────────┤
│ 🏛️ Pháp Lý Doanh Nghiệp Chủ Đầu Tư (Tra cứu dangkykinhdoanh.gov.vn):        │
│ • Công ty CP Đầu Tư Xây Dựng Thủ Đô (MST: 0102938475)                       │
│ • Vốn điều lệ thực góp: 50,000,000,000 ₫ (50 tỷ)                            │
│ • Đại diện pháp luật: Trần Văn Hùng (Không có nợ thuế xấu)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ 🗺️ Xem Bản Đồ Vệ Tinh ]   [ 📄 Xuất Báo Cáo Thẩm Định (PDF) ]   [ Đóng ] │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📱 7. RESPONSIVE BREAKPOINTS & ACCESSIBILITY

* **Desktop ($\ge 1280\text{px}$):** Hiển thị 2 cột (Cột Chat Assistant bên trái, Cột Intelligence Panel / Map bên phải).
* **Tablet ($768\text{px} - 1279\text{px}$):** Widget tự động co giãn về 1 cột, biểu đồ chuyển sang dạng compact view.
* **Mobile ($< 768\text{px}$):** Toàn bộ các nút hành động (Copy SĐT, Mở bản đồ) hiển thị dạng Full-Width Bottom Sheet giúp thao tác ngón cái dễ dàng.

---

Bản đặc tả UX này đã được lưu giữ tại:  
📁 [`_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-scrapers-expansion-and-lead-intelligence.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-scrapers-expansion-and-lead-intelligence.md)
