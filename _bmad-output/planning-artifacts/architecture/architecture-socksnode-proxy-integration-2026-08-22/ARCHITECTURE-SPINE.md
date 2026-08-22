# Architecture Spine — SocksNode Proxy Platform Integration

**Ngày lập:** 2026-08-22  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-SN-1 đến AD-SN-6  
**Epic liên kết:** Epic 21 (Social Automation & XActions Integration), Epic 10 (Real Estate Scraping), Epic 2 (Cross-Platform Crawlers)  
**Tác giả:** Winston (BMAD System Architect)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Tích hợp nền tảng **SocksNode Residential & Mobile Proxy Network** vào toàn bộ hệ sinh thái thu thập dữ liệu và tự động hóa:
* Cung cấp cơ chế Ingress Gateway đa giao thức (HTTP, HTTPS, SOCKS5) tốc độ cao thông qua cụm Gateway Singapore (`sg.premium.socksnode.com:9000`).
* Đảm bảo khả năng vượt qua 100% các hệ thống phòng thủ bot (Cloudflare, Akamai, Facebook Checkpoint, TikTok WAF, Google SERP /sorry).
* Chuẩn hóa mô hình Provider Adapter (`SocksNodeProvider`) tương thích liền mạch với các microservices trong `nowing_backend` và `XActions` (Node.js).
* Tối ưu hóa chi phí vận hành thông qua kỹ thuật lọc tài nguyên nặng (Media/Font Blocking) và tái sử dụng session IP cho việc giải Captcha.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

### AD-SN-1 [ADOPTED]: Unified Multi-Protocol Port 9000 Ingress Gateway
* **Binds**: Cấu hình endpoint proxy toàn hệ thống.
* **Prevents**: Phân mảnh port và việc mở các port tĩnh thủ công trên dashboard.
* **Rule**: Toàn bộ kết nối hướng tới SocksNode phải đi qua cổng `9000` của Gateway khu vực (mặc định: `sg.premium.socksnode.com:9000` cho APAC/Việt Nam). Hỗ trợ chuẩn:
  - `http://` cho Fast Fetchers, Scrapling, Undici.
  - `https://` cho Playwright / Puppeteer Connect Tunneling.
  - `socks5h://` cho Telethon Telegram Userbot (bắt buộc remote DNS resolution).

### AD-SN-2 [ADOPTED]: Dynamic Headerless Username Parameterization
* **Binds**: Cơ chế cấu hình và định tuyến tham số Geo/Session.
* **Prevents**: Sự phụ thuộc vào custom HTTP headers (vốn không được hỗ trợ bởi các native browser drivers như Chromium).
* **Rule**: Toàn bộ thông số định tuyến bắt buộc phải được mã hóa vào chuỗi Username theo chuẩn RFC:
  ```text
  username = <base_token>[-country-<iso2>][-city-<name>][-session-<sid>][-lifetime-<sec>]
  ```
  - `country`: Mã 2 ký tự ISO 3166-1 alpha-2 (ví dụ: `vn`, `us`, `de`, `jp`).
  - `session`: Chuỗi alphanumeric duy nhất (tối đa 32 ký tự) để cố định IP exit.
  - `lifetime`: Thời gian duy trì sticky IP (mặc định: `3600`, tối đa `86400` giây).

### AD-SN-3 [ADOPTED]: Multi-Account 1-to-1 Sticky Session Binding (AD-SOC-3)
* **Binds**: Quản lý phiên tài khoản bot mạng xã hội (Facebook, X/Twitter, TikTok).
* **Prevents**: Khóa/Checkpoint tài khoản do IP bị nhảy chéo bất thường giữa các request trong cùng một ngày.
* **Rule**: Mỗi `account_id` khi thực thi tác vụ automation bắt buộc được cấp một `session_id = fb_<account_id>` (hoặc `x_<account_id>`) cố định với `lifetime = 86400`. Cấu hình này được lưu bền vững trong Redis Hash `xactions:proxy_bindings`. Mọi worker đều phải tái sử dụng proxy binding này.

### AD-SN-4 [ADOPTED]: Circuit Breaker & Rotate-on-Block Failure Policy
* **Binds**: Xử lý lỗi kết nối và phản hồi chặn từ target site (HTTP 403, 429, WAF Challenge).
* **Prevents**: Hiện tượng "Retry Amplification" (bão request thử lại trên cùng một IP exit đã bị đưa vào blacklist).
* **Rule**: Khi phát hiện target site chặn IP:
  1. Hủy ngay lập tức session proxy hiện tại.
  2. Đưa `session_id` cũ vào trạng thái cách ly (`QuarantineState`) trong 5 phút.
  3. Cấp phát `session_id` mới ngẫu nhiên và retry tối đa 2 lần trước khi báo lỗi.

### AD-SN-5 [ADOPTED]: Request Routing Interception for Bandwidth Conservation
* **Binds**: Tầng Headless Browser Automation (Playwright & Puppeteer).
* **Prevents**: Lãng phí 70–89% dung lượng data vào việc tải hình ảnh, font chữ, video/media không phục vụ trích xuất text/DOM.
* **Rule**: Tất cả các phiên trình duyệt thu thập dữ liệu bắt buộc phải bật Request Interception để chặn nạp các resource types: `image`, `font`, `media` (trừ khi luồng nghiệp vụ yêu cầu chụp screenshot trang web).

### AD-SN-6 [ADOPTED]: Fingerprint & Anti-Leak Coherence Standard
* **Binds**: Browser launch arguments và JS runtime environment.
* **Prevents**: Rò rỉ IP thực của máy chủ qua WebRTC STUN và lệch dấu vân tay (Tell-tale Bot Signature).
* **Rule**: Khởi chạy Chromium với cờ `--disable-webrtc`, ghi đè `window.RTCPeerConnection = undefined`. Khi proxy được cấu hình `-country-vn`, tự động thiết lập Timezone `Asia/Ho_Chi_Minh`, Locale `vi-VN`, và Geolocation TP.HCM (`10.8231, 106.6297`) hoặc Hà Nội (`21.0285, 105.8542`).

---

## 3. Kiến Trúc Luồng Dữ Liệu (Data & Control Flow)

```mermaid
sequenceDiagram
    autonumber
    actor Worker as Celery / Node Worker
    participant Provider as SocksNodeProvider
    participant Redis as Redis (xactions:proxy_bindings)
    participant Gateway as SocksNode Gateway (sg.premium...:9000)
    participant Target as Target (FB / Google / BĐS)

    Worker->>Provider: Request Proxy (account_id="acc_01", country="vn")
    Provider->>Redis: Check existing binding for "acc_01"
    alt Binding exists & active
        Redis-->>Provider: Return cached session URL
    else No binding or expired
        Provider->>Provider: Build URL with session-fb_acc_01-lifetime-86400
        Provider->>Redis: HSET xactions:proxy_bindings acc_01 <proxy_url>
    end
    Provider-->>Worker: Return formatted Proxy URL

    Worker->>Gateway: Connect via HTTP/HTTPS/SOCKS5
    Gateway->>Target: Egress from Clean VNPT/Viettel IP
    alt Target returns 200 OK
        Target-->>Worker: Data payload
    else Target blocks (403/429/Captcha)
        Worker->>Provider: Signal block (Circuit Breaker)
        Provider->>Redis: Invalidate session for "acc_01"
        Provider->>Provider: Rotate to new session ID
        Worker->>Gateway: Retry request with fresh exit IP
    end
```

---

## 4. Đặc Tả Mã Nguồn & Cấu Hình Triển Khai

### 4.1. File Cấu Hình Môi Trường Tập Trung ([`.env`](file:///Users/luisphan/Documents/GitHub/XActions/.env))

```dotenv
# Proxy Provider Selection
PROXY_PROVIDER=socksnode

# Gateway URL định tuyến chính (Singapore Gateway cho độ trễ < 50ms)
PROXY_URL=http://snkidcjf24qjp5-country-vn:24c7170b-095d-47f4-a7c9-3e936af7af45@sg.premium.socksnode.com:9000
PROXY_URLS=http://snkidcjf24qjp5-country-vn:24c7170b-095d-47f4-a7c9-3e936af7af45@sg.premium.socksnode.com:9000

# Facebook Scrapers & Multi-Account Automation
FACEBOOK_PROXY=http://sg.premium.socksnode.com:9000
FACEBOOK_PROXY_AUTH_USERNAME=snkidcjf24qjp5-country-vn
FACEBOOK_PROXY_AUTH_PASSWORD=24c7170b-095d-47f4-a7c9-3e936af7af45
FACEBOOK_PROXY_TIMEZONE=Asia/Ho_Chi_Minh
FACEBOOK_PROXY_LATITUDE=10.8231
FACEBOOK_PROXY_LONGITUDE=106.6297
FACEBOOK_PROXY_ACCURACY=100
```

### 4.2. Cấu Trúc File & Module trong Codebase

```text
nowing_backend/
├── app/
│   └── utils/
│       └── proxy/
│           ├── base.py                   # ProxyProvider Abstract Base Class
│           ├── registry.py               # Thêm 'socksnode': SocksNodeProvider
│           └── providers/
│               └── socksnode.py          # [NEW] SocksNodeProvider implementation
src/
├── proxy/
│   ├── index.js                          # Re-exports & pool helpers
│   ├── providers.js                      # parseProxyUrl & Playwright proxy builder
│   └── proxy-pool.js                     # Quarantine & Session Round-Robin
```

---

## 5. Tiêu Chuẩn Đảm Bảo Chất Lượng & KPI

| Tiêu chí | Ngưỡng KPI Bắt buộc | Phương pháp Kiểm chứng |
| :--- | :--- | :--- |
| **Độ trễ HTTP Fast Fetch** | $\le 1.500\text{ ms}$ | `tests/unit/utils/proxy/test_socksnode_provider.py` |
| **Độ trễ Full Browser Render** | $\le 3.500\text{ ms}$ | `tests/scrapers/facebook-live.test.js` |
| **Tỷ lệ sống của Sticky Session** | $\ge 99\%$ trong 1 giờ | Benchmark đo đạc phiên liên tục |
| **Mức tiết kiệm Băng thông** | $\ge 80\%$ so với nạp full DOM | Đo byte transferred qua Route Interception |
| **Chống rò rỉ WebRTC / DNS** | $0\%$ rò rỉ IP thật | Kiểm tra tự động qua `browserleaks.com` test suite |

---
