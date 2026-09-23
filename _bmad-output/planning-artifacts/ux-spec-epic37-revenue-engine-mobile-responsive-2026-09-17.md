# UX Spec — Epic 37: Nowing Revenue Engine & Mobile-First Outbound Experience

**Project:** Nowing  
**Date:** 2026-09-17  
**Scope:** Giao diện Zalo Co-pilot Extension, Trang tương tác Mini-Pitch Portal (`pitch.nowing.ai`), Thông báo Telegram Bot, Giao diện Bảng giá Hybrid & Thanh toán VietQR thích ứng Mobile, và Tích hợp Split Canvas  
**Owner:** Sally — UX Designer (BMad)  
**Mục tiêu:** Thiết kế trải nghiệm bán hàng B2B tự hành, mượt mà trên Mobile, công thái học chạm chuẩn xác, minh bạch chi phí và tạo dựng niềm tin tuyệt đối cho cả Sales Rep lẫn Khách hàng tiềm năng (Prospect).

---

## 1. Tổng quan & Bối cảnh

Epic 37 cung cấp 7 mắt xích hoàn thiện nền tảng tăng trưởng doanh thu (Autonomous Revenue Engine) cho Nowing tại thị trường Việt Nam & Đông Nam Á. 

Khảo sát hành vi người dùng B2B tại Việt Nam chỉ ra 2 sự thật quan trọng:
1. **Hơn 75% khách hàng B2B (CEO, Founder, Quản lý mua hàng) mở đọc link chào hàng và tin nhắn lần đầu tiên trên điện thoại di động (qua Zalo hoặc Email).**
2. **Sales Rep thường xuyên di chuyển ngoài đường**, tương tác với khách hàng qua ứng dụng Zalo trên smartphone và cần nhận thông báo hành động ngay lập tức (Instant Actionable Alert).

Tài liệu này đặc tả chi tiết visual, micro-interactions, layout responsive và checklist công thái học để đảm bảo tỷ lệ chuyển đổi (Conversion Rate) cao nhất.

---

## 2. Design Principles

| # | Nguyên tắc | Ý nghĩa trong Epic 37 |
|---|---|---|
| **P1** | **Mobile-First Touch Ergonomics** | Mọi thành phần tương tác (nút bấm, slider, link) trên mobile phải có kích thước vùng chạm tối thiểu $44 \times 44$px (chuẩn Apple HIG), không có hiện tượng giật layout (CLS < 0.05). |
| **P2** | **First 3-Second Trust Hook** | Khi prospect mở trang Mini-Pitch, 3 giây đầu tiên phải thấy ngay logo và tên công ty của chính họ, cùng tóm tắt 30 giây rõ ràng, xóa bỏ cảm giác "link spam/lừa đảo". |
| **P3** | **Zero-Occlusion & Human-in-the-Loop** | Extension Zalo Co-pilot không chiếm dụng diện tích chat của Zalo; tự động thu nhỏ sau khi chèn text; trao quyền quyết định bấm gửi cuối cùng cho con người (Zero Ban Penalty). |
| **P4** | **Frictionless Mobile Payment** | Khắc phục triệt để "nghịch lý không thể quét mã QR trên màn hình điện thoại đang cầm": Cung cấp 1-Click Copy số tài khoản/số tiền/cú pháp và nút mở thẳng App Ngân Hàng. |
| **P5** | **Transparent Value & Zero-Risk Seal** | Bảng giá trực quan bằng bộ quy đổi số lượng số điện thoại thực tế; cam kết hoàn 100% credit nổi bật ngay cạnh nút thanh toán. |

---

## 3. Personas & Scenarios

### 3.1. Personas
* **Anh Nam (Prospect — CEO Công ty Logistics):** Bận rộn, nhận được link Mini-Pitch qua Zalo khi đang ngồi taxi. Anh mở link trên iPhone 15, lướt nhanh 30 giây xem biểu đồ chi phí và muốn đặt lịch trao đổi nhanh mà không phải gõ phím nhiều.
* **Bạn Tuấn (Sales Rep — SDR B2B):** Làm việc cả trên laptop (Zalo Web) và điện thoại. Khi Tuấn đang đi gặp khách ngoài đường, Tuấn nhận được ping Telegram báo "Anh Nam đang đọc báo giá"; Tuấn bấm 1 nút là app Zalo trên điện thoại tự mở ra khung chat với anh Nam.
* **Chị Hương (Business Owner — Người mua gói cước):** Duyệt bảng giá trên điện thoại trong giờ nghỉ trưa. Chị cần thấy rõ 2.490.000đ sẽ mua được bao nhiêu số điện thoại đã xác minh và thanh toán nhanh qua app Vietcombank trong 30 giây.

---

## 4. Chi tiết Thiết kế Từng Bề mặt (Component Specs)

### 4.1. Zalo Desktop/Web Co-pilot Overlay (`nowing_browser_extension`)

*Vị trí:* Inject trực tiếp vào `chat.zalo.me` thông qua Plasmo CSUI.

```
+-------------------------------------------------------------+
| chat.zalo.me                                                |
|                                         +------------------+|
| [Tin nhắn gần nhất...]                  | NOWING CO-PILOT  ||
|                                         | Nguyễn Văn Nam   ||
|                                         | CEO @ LogiTech   ||
|                                         | 🔥 Signal: Hiring ||
|                                         |------------------||
|                                         | Kịch bản đề xuất ||
|                                         | "Chào anh Nam..."||
|                                         |                  ||
|                                         | [Chèn vào chat]  ||
| [Nhập tin nhắn...]            [✨ Pill] | [📋 Copy Text]   ||
+-----------------------------------------+------------------++
```

#### 4.1.1. Trạng thái nghỉ (Resting State — Floating Pill)
* **Kích thước:** Viên thuốc tròn $36 \times 36$px, bo góc `rounded-full`.
* **Vị trí:** Cố định ở góc trên bên phải khung nhập liệu của Zalo (`bottom: 80px, right: 24px`), màu xanh bạc hà Nowing (`bg-emerald-500`), icon tia sét hoặc ngôi sao `✨`.
* **Badge thông minh:** Hiển thị chấm nhỏ nếu lead này có Buying Signal mới trong 24h.

#### 4.1.2. Bảng ngữ cảnh mở rộng (Flyout Drawer)
* **Kích thước:** Chiều rộng cố định 320px, chiều cao co giãn theo nội dung (tối đa 480px), đổ bóng `shadow-2xl`, bo góc `rounded-xl`, viền `border border-border/60`.
* **Nội dung:**
  1. *Lead Context Header:* Tên khách hàng, Chức vụ, Tên công ty, Tag tín hiệu (`🔥 Đang tuyển 5 vị trí kinh doanh`).
  2. *Script Variant Tabs:* 2 tab chuyển đổi: `[Ngắn gọn]` / `[Kèm link Mini-Pitch]`.
  3. *Action Row:*
     - Nút chính: `[Chèn vào chat]` (Màu xanh Emerald, cao 40px, font Medium).
     - Nút phụ: `[Copy]` và icon link mở thẻ Lead trên Nowing CRM.
* **Quy tắc công thái học:**
  - Bấm `[Chèn vào chat]` ➔ Text được điền vào ô chat của Zalo ➔ **Drawer tự động thu gọn về Pill sau 150ms** để giải phóng tầm nhìn cho Sales Rep xem lại nội dung trước khi tự tay bấm gửi.
  - **DNC Warning:** Nếu số điện thoại thuộc danh sách DNC, drawer hiển thị viền đỏ cảnh báo `⚠️ Thuộc danh sách DNC (NĐ 91/2020)` và nút chèn bị vô hiệu hóa (`disabled`).

---

### 4.2. 1-Click Interactive Mini-Pitch Portal (`pitch.nowing.ai/[workspace]/[lead]`)

*Trải nghiệm của Prospect khi mở link trên trình duyệt di động (Mobile Safari / Chrome).*

#### 4.2.1. Hero Header & Dual-Branding (3 giây đầu)
* **Mobile Viewport (< 640px):**
  * Logo khách hàng (chiều cao 40px) đặt cạnh Logo công ty người gửi (chiều cao 32px), nối bằng dấu $\times$ mờ.
  * Tag bảo mật: `🔒 Báo cáo nội bộ dành riêng cho [Tên Công Ty]`.
  * Tiêu đề lớn (22px, Bold): *"3 Đòn bẩy Tối ưu Tỷ lệ Chốt Hợp đồng B2B năm 2026"*.

#### 4.2.2. The 30-Second Executive Card Stack
* 3 Card xếp dọc gọn gàng, nền `bg-card/50` với viền màu tương ứng:
  1. 🔴 *Thực trạng:* Tỷ lệ phản hồi email lạnh ngành Logistics đang rơi xuống dưới 4%.
  2. 🟡 *Khoảng trống:* Đối thủ cùng ngành đang tiếp cận khách hàng trực tiếp qua Zalo.
  3. 🟢 *Giải pháp Nowing:* Kịch bản tiếp cận theo tín hiệu mở rộng doanh nghiệp.

#### 4.2.3. Máy tính ROI Trực quan (Interactive Calculator)
* Thanh trượt (Slider) dự toán:
  * Cho phép khách hàng vuốt ngón tay chọn quy mô Sales Rep: `[3 sales] ➔ [10 sales]`.
  * Kết quả nhảy số theo thời gian thực (Counter animation): Dự kiến mang lại `+15 cuộc hẹn bán hàng/tháng` và tiết kiệm `~25.000.000 đ` chi phí data.
  * **Công thái học chạm:** Vùng bắt chạm cảm ứng (Hit area) của núm trượt $\ge 48 \times 48$px, có feedback rung haptic nhẹ trên thiết bị hỗ trợ.

#### 4.2.4. Inline Meeting Booking Accordion (Không dùng Popup Modal)
* Khi bấm nút CTA chính `[Đặt lịch trao đổi 15 phút với chuyên viên]`:
  * Mở rộng khối Accordion ngay bên dưới (không mở modal popover làm che mất màn hình điện thoại).
  * Hiển thị 3 khung giờ trống (lấy từ Google/Lark Calendar của AE):
    * `[14:00 - Thứ Ba, 22/09]`
    * `[10:00 - Thứ Năm, 24/09]`
    * `[15:30 - Thứ Sáu, 25/09]`
  * Chạm 1 lần để chọn ➔ Nút chuyển sang trạng thái `[Xác nhận]` ➔ Sau khi xác nhận, tự động hiển thị link Google Meet và nút `[Thêm vào lịch trên máy]`.
* **Footer Tuân thủ Nghị định 13/2023/NĐ-CP:** Dòng chữ nhỏ tinh tế ở đáy trang:  
  *"Bạn nhận được báo cáo này vì doanh nghiệp của bạn đang hoạt động công khai trong ngành. [Yêu cầu xóa thông tin của tôi]"*.

---

### 4.3. Realtime Telegram Push Notification cho Sales Rep trên Điện thoại

Nội dung tin nhắn gửi vào Telegram Bot của Sales Rep phải tối ưu để **đọc trong 3 giây và hành động trong 1 chạm**:

```text
🔥 HOT LEAD ĐANG XEM MINI-PITCH!
━━━━━━━━━━━━━━━━━━━━
🏢 Doanh nghiệp: Công ty Cổ phần LogiTech
👤 Người xem: Anh Nguyễn Văn Nam (CEO)
⏱️ Thời gian đọc: 2 phút 15 giây
📍 Đang dừng tại: Bảng giá & Dự toán ROI

💡 Đề xuất: Khách đang quan tâm đến bài toán chi phí.
━━━━━━━━━━━━━━━━━━━━
[💬 Mở Chat Zalo Với Anh Nam]  ➔ URL: zalo.me/0908123456
[📊 Mở Thẻ Lead Trên CRM]
```

* **Công thái học Mobile:** Khi Sales Rep đang cầm smartphone và bấm nút `[💬 Mở Chat Zalo Với Anh Nam]`, deep-link `zalo.me/{phone}` kích hoạt OS mở ngay ứng dụng Zalo trên điện thoại, nhảy thẳng vào khung chat với khách mà không qua bất kỳ trang trung gian nào.

---

### 4.4. Giao diện Bảng giá Hybrid & Thanh toán VietQR trên Dashboard (`/buy-tokens`)

#### 4.4.1. Responsive Pricing Grid
* **Desktop ($\ge 1024$px):** 3 cột ngang: Starter (990k) | **Professional (2.490k - Highlight)** | Business (5.990k).
* **Mobile (< 768px):** Xếp chồng 1 cột. **Thẻ Professional được ưu tiên đảo lên vị trí đầu tiên (Order-1)**, kèm badge nổi bật `ĐƯỢC CHỌN NHIỀU NHẤT`.
* **Thanh trượt Giá trị Thực tế (Interactive Credit Calculator):**
  * Slider chọn số lượng lead cần xử lý mỗi tháng:  
    *Hiển thị trực quan: "3.500 credits = Mở khóa 350 số điện thoại đã xác minh Zalo + 1.750 lượt quét radar tín hiệu"*.

#### 4.4.2. Khắc phục Bẫy QR trên Mobile (The Mobile VietQR Adaptor)
Trong Modal thanh toán (`VietQRCheckoutModal`):
* **Nếu phát hiện thiết bị Desktop:** Hiển thị mã QR to rõ (240px) ở trung tâm để quét bằng điện thoại.
* **Nếu phát hiện thiết bị Mobile (`useIsMobile() === true`):**
  * Thu nhỏ mã QR xuống góc phụ hoặc ẩn mặc định trong nút `[Xem mã QR để quét trên máy khác]`.
  * Hiển thị bảng **3 Nút Sao Chép 1-Chạm (One-Tap Copy Block)**:
    1. Số tài khoản: `0123456789 (Vietcombank)` ➔ `[📋 Sao chép]`
    2. Số tiền: `2.490.000 đ` ➔ `[📋 Sao chép]`
    3. Nội dung chuyển khoản: `NOWING 98765` ➔ `[📋 Sao chép]`
  * **Nút CTA Chính:** `[📲 Mở Ứng Dụng Ngân Hàng Trên Máy]` (Sử dụng universal scheme hỗ trợ mở App Vietcombank, Techcombank, MB, Momo).
  * Thông báo trạng thái: Vòng tròn xoay `Đang chờ ngân hàng xác nhận...` tự động đổi sang icon tích xanh `🎉 Thanh toán thành công! Gói cước đã kích hoạt` ngay sau 3–5 giây.
* **The Trust Seal (Khiên Bảo vệ Không Rủi ro):**
  * Banner xanh ngọc trang trọng đặt dưới nút chọn gói:  
    `"🛡️ Bảo đảm hoàn 100% credit: Tự động hoàn trả ngay lập tức nếu số điện thoại sau khi mở khóa không tồn tại trên Zalo hoặc không liên lạc được."`

---

### 4.5. Tích hợp Nowing Split Canvas trên Màn hình Nhỏ (< 768px)

Trong file `NowingSplitCanvas.tsx`:
* Màn hình điện thoại không cho phép hiển thị song song cột chat 340px và bảng Lead Matrix.
* **Giải pháp Thanh Điều Hướng Đáy (Mobile Bottom Tab Bar):**
  * Cung cấp 2 tab cố định ở chân màn hình:
    * `[💬 Trợ Lý Chat]`
    * `[📋 Bảng Lead & Radar]` (Hiển thị badge chấm đỏ `🔴` khi có lead mới từ Radar 37.1).
  * Vuốt ngang (Swipe gesture) mượt mà để chuyển đổi qua lại giữa hội thoại AI và danh sách lead.

---

## 5. Accessibility, Performance & Touch Targets

* **Touch Targets:** Tất cả các thành phần có thể bấm được trên mobile đều có `min-height: 44px` và `min-width: 44px`. Khoảng cách giữa các nút bấm liền kề tối thiểu 8px để tránh bấm nhầm (Fat-finger prevention).
* **Contrast Ratio:** Văn bản chính đạt tỷ lệ tương phản tối thiểu $4.5:1$ (chuẩn WCAG AA). Chữ phụ (metadata, timestamps) tối thiểu $3:1$.
* **Safe-Area Padding:** Trang web mini và dashboard luôn tính toán `env(safe-area-inset-bottom)` để thanh CTA không bị che bởi thanh điều hướng cử chỉ (Home bar) trên iPhone/Android.
* **Loading Skeletons:** Khi dữ liệu đang tải, hiển thị Skeleton đúng kích thước của các Card để loại bỏ hoàn toàn hiện tượng giật cục khung hình (CLS = 0).

---

## 6. Danh mục Yêu cầu Thiết kế Trải nghiệm (UX Acceptance Criteria)

- **UX-DR-E37-1 (Mobile VietQR Adaptation):** Modal thanh toán trên mobile phải có 3 nút sao chép độc lập cho STK, Số tiền, Nội dung và nút mở app ngân hàng, không bắt buộc người dùng mobile phải quét ảnh QR.
- **UX-DR-E37-2 (Zalo Co-pilot Floating Pill):** Extension Zalo hiển thị dạng Pill 36px gọn gàng, bung drawer 320px khi cần và tự động thu nhỏ sau khi chèn text, không che khuất ô nhập liệu.
- **UX-DR-E37-3 (Mobile-First Mini-Pitch Portal):** Trang `pitch.nowing.ai` tải dưới 100ms trên 4G, hiển thị dual-branding trong 3 giây đầu, không dùng popup modal cho lịch hẹn mà dùng inline accordion.
- **UX-DR-E37-4 (1-Tap Native Zalo Deep-link):** Alert Telegram chứa nút bấm gọi link `zalo.me/{phone}` mở thẳng ứng dụng Zalo trên điện thoại của Sales Rep.
- **UX-DR-E37-5 (DNC & Opt-Out Visibility):** Hiển thị cảnh báo đỏ khi lead thuộc DNC trên Zalo extension; Mini-Pitch portal có link Opt-out xóa dữ liệu tuân thủ Nghị định 13.
- **UX-DR-E37-6 (Trust Seal & Credit Calculator):** Trang mua gói cước có thanh trượt tính toán giá trị thực tế của credit và banner cam kết hoàn 100% credit cho số điện thoại lỗi.
- **UX-DR-E37-7 (Split Canvas Mobile Tab Bar):** Giao diện Nowing Split Canvas trên mobile chuyển sang 2 tab đáy mượt mà, có chỉ báo trực quan khi có lead mới từ Radar.
