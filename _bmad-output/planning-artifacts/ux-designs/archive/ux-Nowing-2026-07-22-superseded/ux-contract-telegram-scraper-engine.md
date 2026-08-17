# UX Contract — Telegram Scraper & Channel Ingestion Engine

**Ngày:** 2026-08-15  
**Tác giả:** Sally (UX Designer & UI Specialist)  
**Phạm vi:** UX Design Spec cho Epic 22 (Stories 22.1, 22.2, 22.3) — Quản lý Scraper Accounts Telegram, Theo dõi Kênh (Channel Monitoring), và Hiển thị Trích xuất Dữ liệu Telegram trong AI Chat.  
**Bám vào:** FR-70 đến FR-79 · AD-1 đến AD-8 · UX-DR1, UX-DR2, UX-DR3 · Stories 22.1, 22.2, 22.3.  
**Loại tài liệu:** *UX Contract* — định nghĩa tương tác, trạng thái giao diện, luồng xử lý lỗi và trải nghiệm người dùng bắt buộc.

---

## 1. Bài toán UX & Persona Mục tiêu

### Đối tượng Người dùng:
1. **Platform Administrator:** Cần thêm tài khoản Telegram (Userbot) an toàn qua OTP/2FA, giám sát tình trạng Rate-limit/Cooldown theo thời gian thực và quản lý danh sách kênh cần cào.
2. **End User / Market Intelligence Analyst:** Tìm kiếm thông tin nhà đất, việc làm, tin tức qua chat AI; cần thấy bài viết gốc Telegram kèm các thực thể quan trọng (SĐT liên hệ, khoảng giá, địa điểm) được bóc tách trực quan và media đính kèm rõ ràng.

### Thách thức Trải nghiệm (UX Challenges):
* **Xác thực 2 bước bất đồng bộ:** Telegram yêu cầu gửi mã OTP (qua SMS hoặc App Telegram), sau đó mới gửi mã và có thể yêu cầu thêm mật khẩu Cloud Password (2FA). Form UI phải xử lý State Machine mượt mà, có bộ đếm ngược OTP timeout, không làm treo ứng dụng.
* **Minh bạch trạng thái Cooldown:** Khi tài khoản bị Telegram giới hạn (`FloodWaitError`), UI phải hiển thị rõ lý do và thời gian chờ còn lại (countdown timer) thay vì báo lỗi mơ hồ.
* **Hiển thị thông tin cô đọng trong Chat:** Bài viết Telegram thường dài và lộn xộn; UI Widget trong khung chat cần làm nổi bật thông tin liên hệ và metadata thay vì hiển thị raw text.

---

## 2. Đặc tả Giao diện & Luồng Tương tác (UX Specification)

### 🎨 Surface 1: Quản trị Tài khoản Scraper (`/admin/scraper-accounts`)

Vị trí: Tab **"Telegram"** trong trang quản lý tài khoản scraper nền tảng.

#### A. Modal Thêm Tài khoản Telegram (Multi-step Auth Modal)

```
+-------------------------------------------------------------+
|  Connect Telegram MTProto Account                    [ X ]  |
+-------------------------------------------------------------+
|  Step 1: Account Credentials                                |
|                                                             |
|  Phone Number:      [ +84 912 345 678                     ] |
|  Telegram API ID:   [ 20401234                            ] |
|  API Hash:          [ 9ab8c7d6e5f4a3b2c1d0e9f8a7b6c5d4    ] |
|  Proxy (Optional):  [ socks5h://user:pass@proxy.net:1080  ] |
|                                                             |
|  [ Cancel ]                                [ Send Auth Code ]|
+-------------------------------------------------------------+
```

```
+-------------------------------------------------------------+
|  Connect Telegram MTProto Account                    [ X ]  |
+-------------------------------------------------------------+
|  Step 2: Enter Verification Code                            |
|                                                             |
|  We sent a login code to your Telegram App / SMS.           |
|  Code expires in: 01:54                                     |
|                                                             |
|  Verification Code: [ 5 8 9 2 1 ]                           |
|                                                             |
|  [✓] Two-Step Verification (2FA Cloud Password enabled)     |
|  Cloud Password:    [ **********                          ] |
|                                                             |
|  [ Back ]         [ Resend Code (30s) ]      [ Verify & Save ]|
+-------------------------------------------------------------+
```

* **Trạng thái Step 1 (Input Credentials):**
  * Validation: Số điện thoại phải đúng định dạng E.164 (`+` và mã quốc gia); `api_id` là số nguyên; `api_hash` là hex 32 ký tự.
  * Khi bấm "Send Auth Code": Button chuyển sang loading spinner, gọi API backend gửi mã xác thực.
* **Trạng thái Step 2 (Verify Code & 2FA):**
  * Input Code dạng 5–6 ô số tự động focus kế tiếp.
  * Checkbox 2FA mở rộng thêm trường mật khẩu nếu tài khoản bật bảo mật 2 lớp.
  * Bộ đếm thời gian hiệu lực mã OTP (countdown timer).
  * Xử lý lỗi: Nếu sai mã hoặc sai mật khẩu 2FA, hiển thị inline alert màu đỏ (VD: *"Invalid code. 2 attempts remaining"*), không reset toàn bộ form.

#### B. Bảng Giám sát Tài khoản Telegram (Account Health Table)

| Phone Number | Platform | Status | Token Quota | Proxy | Last Used | Actions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `+84912***678` | MTProto Userbot | 🟢 **Active** | 28 / 30 rpm | `socks5h://...` | 2m ago | `[Test]` `[Delete]` |
| `+84988***999` | MTProto Userbot | 🟡 **Rate-Limited** | 0 / 30 rpm | `socks5h://...` | 10s ago | `[Details]` |
| `+84903***111` | MTProto Userbot | 🔴 **Cooldown (42s)** | 0 / 30 rpm | `Direct` | 15s ago | `[Force Reset]` |

* **Badge Status trực quan:**
  * 🟢 **Active:** Sẵn sàng nhận task cào, hiển thị hạn mức token bucket còn lại.
  * 🟡 **Rate-Limited:** Đang chạm trần tốc độ tạm thời, tự hồi phục sau vài giây.
  * 🔴 **Cooldown (Timer):** Đang bị Telegram `FloodWaitError`, hiển thị countdown giây/phút tự động giảm dần theo thời gian thực (Zero Cache sync).

---

### 📡 Surface 2: Quản lý Kênh Giám sát (`/admin/telegram-channels`)

```
+----------------------------------------------------------------------------------------------------+
|  + Monitor New Channel                                                                             |
|  [ https://t.me/batdongsan_vietnam_vip                     ] [ Mode: Web Preview ▼ ] [ Add Channel ]|
+----------------------------------------------------------------------------------------------------+
|  Monitored Channels (12)                                                                           |
|                                                                                                    |
|  Channel Name          Type          Mode          Messages    Realtime Stream    Status   Actions |
|  ------------------------------------------------------------------------------------------------- |
|  @bds_hanoi_chinhchu   Public        Web Preview   1,420       [ Toggle: OFF ]    🟢 Idle  [Scrape]|
|  @nhadat_saigon_vip    Private/Group MTProto Deep  8,950       [ Toggle: ON  ]    ⚡ Live   [Scrape]|
|  @tinnhanh_bds247      Public        Web Preview   350         [ Toggle: OFF ]    🔴 Error [Logs]  |
+----------------------------------------------------------------------------------------------------+
```

* **Chế độ Ingestion linh hoạt:**
  * `Web Preview (Zero-risk)`: Khuyên dùng cho mọi kênh công khai (không tốn slot account).
  * `MTProto Deep`: Dùng cho kênh riêng tư, nhóm chat thảo luận bình luận (comment replies).
* **Toggle Realtime Stream:** Khi bật ON, kích hoạt listener `events.NewMessage` đưa sự kiện vào luồng thông báo Saved Search tức thì.

---

### 💬 Surface 3: Trực quan hóa Bài viết Telegram trong AI Chat (Chat Message Widget)

Khi người dùng hỏi Nowing Agent (VD: *"Tìm các tin bán nhà quận Cầu Giấy trên kênh Telegram vừa cào"*), Agent trả về Widget Card được format chuẩn mực:

```
+-----------------------------------------------------------------------+
| ✈️ Telegram Post • @bds_hanoi_chinhchu                 15/08/2026 14:30 |
+-----------------------------------------------------------------------+
| Bán gấp nhà phố Trung Kính, Cầu Giấy 55m2 x 5 tầng, ô tô đỗ cửa.      |
| Nhà mới đẹp, nội thất gỗ lim cao cấp, sổ đỏ chính chủ sẵn sàng giao...|
|                                                                       |
| 🏷️ Entities Extracted:                                                |
| [ 📞 0912.345.678 (Copy) ]  [ 💰 12.5 Tỷ ]  [ 📍 Cầu Giấy, Hà Nội ]    |
|                                                                       |
| 📷 3 Media Attachments: [ Thumbs: 🖼️ 🖼️ 🖼️ ]                           |
| 👁️ 1,240 views • 🔄 14 forwards                       [ Open in Telegram ↗ ] |
+-----------------------------------------------------------------------+
```

* **Actionable Badges:**
  * 📞 **Phone Number Pill:** Bấm vào tự động copy số điện thoại vào clipboard kèm toast thông báo `"Copied phone number!"` (hoặc mở ứng dụng gọi điện trên di động).
  * 💰 **Price Pill:** Highlight màu nổi bật (Xanh lá/Amber) giúp người dùng lướt nhanh giá trị giao dịch.
  * 📷 **Media Gallery:** Click vào thumbnail mở Lightbox xem ảnh/video HD được stream từ S3 CDN.
  * ↗️ **Deep Link:** Bấm nút mở trực tiếp tin nhắn trên ứng dụng Telegram (`tg://resolve?domain=...&post=...` hoặc `https://t.me/...`).

---

## 3. Bảng Ma trận Trạng thái UX (UI State Contract)

| # | Thành phần | Trạng thái UI | Hành vi & Trải nghiệm |
| :--- | :--- | :--- | :--- |
| **U1** | **OTP Modal** | `Requesting Code` | Disable input, hiển thị spinner *"Connecting to Telegram DC..."*. |
| **U2** | **OTP Modal** | `Invalid Code` | Lắc nhẹ ô input (shake animation), viền đỏ, giữ nguyên số điện thoại. |
| **U3** | **OTP Modal** | `2FA Required` | Tự động mở rộng trường nhập Cloud Password khi nhận phản hồi `SESSION_PASSWORD_NEEDED`. |
| **U4** | **Account List**| `FloodWait Active` | Countdown timer đếm ngược trực tiếp trên UI; tooltip giải thích *"Telegram rate limit cooling down"*. |
| **U5** | **Channel List**| `Adding Channel` | Kiểm tra định dạng username/link Telegram trước khi submit; hiển thị avatar và title kênh khi lookup thành công. |
| **U6** | **Chat Widget** | `Media Loading` | Skeleton shimmer placeholder trong khi ảnh thumbnail đang tải từ S3. |
| **U7** | **Chat Widget** | `Empty Entities`| Ẩn vùng Badges nếu tin nhắn không chứa số điện thoại hoặc giá tiền. |

---

## 4. Truy vết Yêu cầu & Tính tương thích Kỹ thuật

* **Bao phủ:**
  * **Story 22.1:** Channel Monitor Table, Web Preview status badge, sync Zero Cache.
  * **Story 22.2:** Multi-step OTP/2FA Account Modal, Countdown FloodWait Timer, Proxy config input.
  * **Story 22.3:** Entity Extraction Pills (Phone/Price), S3 Lightbox Media, Realtime Stream indicator, AI Chat Message Widget.
* **Design System:** Tương thích $100\%$ với Tailwind/Vanilla CSS tokens của Nowing (`zinc` dark/light palette, Radix UI dialogs, Lucide-react icons).

---

Sally đã hoàn thành UX Contract chi tiết cho cả 3 Stories của Epic 22! 🎨✨
