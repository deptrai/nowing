---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Giải pháp kỹ thuật lấy số điện thoại từ batdongsan.com.vn trong scraper Python khi API bị bảo vệ bởi Cloudflare/session/bot detection'
research_goals: 'Tìm cách khắc phục lỗi 401 khi gọi DecryptPhone, có thể là in-browser login, full cookie capture, residential proxy, anti-detect browser, hoặc kỹ thuật khác; đề xuất hướng triển khai phù hợp với Nowing.'
user_name: 'Luisphan'
date: '2026-08-03'
web_research_enabled: true
source_verification: true
---

# Research Report: Giải pháp kỹ thuật lấy số điện thoại từ batdongsan.com.vn

**Date:** 2026-08-03
**Author:** Luisphan
**Research Type:** technical

---

## 1. Technical Research Scope Confirmation

**Research Topic:** Giải pháp kỹ thuật để gọi thành công API `DecryptPhone` của `batdongsan.com.vn` trong scraper Python, khi gặp lỗi 401 do Cloudflare/session/bot detection.

**Research Goals:**
- Tìm hiểu tại sao XHR trả 401 trong scrapling dù Playwright MCP thành công.
- Đánh giá các hướng: in-browser login, full cookie capture (HttpOnly), residential proxy, anti-detect browser (patchright/Camoufox/DrissionPage), CDP với Chrome profile, hoặc giải pháp thay thế.
- Đề xuất hướng triển khai phù hợp với Nowing.

**Scope Confirmed:** 2026-08-03

---

## 2. Technology Stack Analysis

### Công nghệ hiện tại trong Nowing

- **Scraper browser:** `scrapling` (`AsyncStealthySession`) — wrapper trên Playwright patchright, có `solve_cloudflare=True`, `real_chrome=True`.
- **HTTP client:** `AsyncFetcher` (scrapling) cho mobile `p_sync` API.
- **Cookie store:** `ScraperPlatformAccount` lưu `cookies` (string từ `document.cookie`) + `token`.
- **Browser MCP test:** Playwright MCP (Chrome thật của user) — XHR thành công.

### Công nghệ/công cụ nghiên cứu liên quan

- **Camoufox:** Firefox fork anti-detect, spoof fingerprint ở C++ level, hỗ trợ Playwright API.
- **patchright / scrapling:** Playwright fork với stealth patches.
- **curl_cffi / tls-client:** TLS/HTTP2 fingerprint impersonation.
- **Residential proxies:** IPRoyal, Bright Data, Microlink, v.v.
- **Playwright `storage_state`:** lưu toàn bộ cookie (kể cả HttpOnly) + `localStorage`.
- **Chrome CDP / user_data_dir:** kết nối hoặc dùng profile Chrome của user.

### Nguồn

- Playwright authentication with `storage_state`: https://playwright.dev/docs/next/auth
- Camoufox anti-detect browser: https://camoufox.com/
- Anti-detect browser benchmark: https://github.com/ianlpaterson/anti-detect-browser-bench
- Cloudflare scraping methods: https://use-apify.com/blog/how-to-bypass-cloudflare-web-scraping

---

## 3. Integration Patterns

### Pattern A: In-Browser Login
Scraper tự đăng nhập bằng `username`/`password` trong cùng browser context (`scrapling`/`Playwright`). Sau login, context có đầy đủ cookie (HttpOnly, `con.ses.id`, `AWSALB`, `cf_clearance`) sinh ra cùng lúc nên XHR thành công.

### Pattern B: Full `storage_state` Capture
Dùng Playwright đăng nhập/khởi tạo session trên máy user, lưu `context.storage_state()` ra JSON, import toàn bộ cookie vào `scrapling`. Khác với `document.cookie`, `storage_state` capture được HttpOnly.

### Pattern C: Anti-Detect Browser
Thay `scrapling` bằng **Camoufox** hoặc **CloakBrowser**. Camoufox spoof TLS/HTTP2/JA3 và fingerprint ở C++ level, được benchmark vượt qua Cloudflare Turnstile và nhiều real-world targets.

### Pattern D: Residential Proxy
Thay IP datacenter (hiện tại `PROXY_URL` chưa set) bằng residential proxy. Cloudflare đánh giá IP reputation; residential IP giảm tần suất challenge/blocked.

### Pattern E: Hybrid (Login → `storage_state` → headless)
Tách làm 2 bước: (1) một playwright job login/lấy `storage_state`, (2) scraper headless dùng state đó. State ngắn hạn, cần refresh định kỳ.

---

## 4. Architectural Patterns

### Lớp bảo vệ của Cloudflare/Batdongsan

| Lớp | Cách hoạt động | Cách vượt |
|---|---|---|
| IP reputation | Datacenter IP bị điểm thấp | Residential proxy |
| TLS/HTTP2 fingerprint (JA3/JA4) | `requests`/`httpx` có signature riêng | curl_cffi / Camoufox |
| JS challenge / Managed Challenge | Đòi hỏi browser thật giải challenge | Stealth Playwright / Camoufox |
| Behavioral analysis | Mouse, scroll, timing | Human-like interaction |
| Session binding | `con.ses.id` bind với `AWSALB`/`cf_clearance`/fingerprint | In-browser login hoặc same state |

### Mô hình khuyến nghị cho Nowing

```
[ScraperPlatformAccount]
   ├─ username/password (mới)
   ├─ storage_state JSON (mới)
   └─ token/cookies (giữ lại fallback)

[Phone Fetch Job]
   ├─ Mở anti-detect browser context (Camoufox/patchright)
   ├─ Login (nếu chưa có storage_state)
   ├─ Lưu storage_state
   ├─ Navigate detail page
   └─ XHR DecryptPhone → lấy số
```

---

## 5. Implementation Research

### 5.1. Tại sao XHR 401?

Phân tích thực tế:
- Playwright MCP (browser thật của user): XHR `POST /microservice-architecture-router/Product/ProductDetail/DecryptPhone` trả 200 + số đầy đủ.
- `scrapling` với cookie copy từ Playwright: XHR trả **401** với header `WWW-Authenticate: Bearer` và `cf-ray`.
- `page.request.post` trong `scrapling`: trả **403** (Cloudflare challenge).

Nhận định:
- `document.cookie` không chứa cookie **HttpOnly** (nếu có). Cookie import bị thiếu.
- `con.ses.id` từ browser khác bị bind với fingerprint/IP/`AWSALB`/`cf_clearance` của browser gốc → server từ chối khi dùng trong scrapling.
- Cloudflare Bot Management kết hợp nhiều tín hiệu; copy mỗi visible cookie không đủ.

### 5.2. Đánh giá giải pháp

| Giải pháp | Độ tin cậy | Chi phí | Độ phức tạp | Ghi chú |
|---|---|---|---|---|
| In-browser login | **Cao nhất** | Thấp | Trung bình | Cần username/password; session hợp lệ trong chính browser đó |
| Full `storage_state` capture | Cao | Thấp | Trung bình | Cần tool/script lấy toàn bộ cookie; state hết hạn nhanh |
| Camoufox | Cao | Thấp (OSS, ~200MB) | Trung bình | Thay `scrapling`; cần test với Batdongsan |
| Residential proxy | Trung bình | Cao ($5-8/GB) | Thấp | Giảm challenge, không giải quyết session binding |
| curl_cffi | Thấp | Thấp | Thấp | Không qua được JS challenge 403 |
| CDP + Chrome profile | Cao | Thấp | Cao | Cần user để Chrome mở với remote debugging |

### 5.3. Khuyến nghị

**Hướng ưu tiên: Pattern A (In-Browser Login) kết hợp Camoufox hoặc patchright.**

Lý do:
- Session được tạo trong cùng browser context với XHR → tránh session binding.
- Không cần export/import cookie thủ công.
- Có thể tích hợp vào `ScraperPlatformAccount` credentials (`username`/`password`).
- Nếu login bị challenge, Camoufox có khả năng vượt cao hơn `scrapling`.

**Hướng dự phòng:**
- Nếu user không muốn lưu mật khẩu: dùng `storage_state` JSON được tạo từ Playwright MCP/script của user và upload vào admin UI.
- Nếu vẫn bị block: thêm residential proxy + Camoufox.

---

## 6. Research Synthesis

### Kết luận

Lỗi 401 không phải do sai URL/payload; `DecryptPhone` API hoạt động đúng trong browser thật. Nguyên nhân là **session/cookie không tương thích giữa Playwright MCP và `scrapling`**, kết hợp với Cloudflare bot/session detection.

### Giải pháp nhanh nhất để triển khai

1. **Mở rộng `ScraperPlatformAccount` credentials** thêm `username` và `password`.
2. **Thêm `login_batdongsan`** trước khi gọi `fetch_detail_phone`:
   - Navigate `https://batdongsan.com.vn/dang-nhap`.
   - Fill user/pass, submit.
   - Wait cho `con.ses.id`/`c_u_id` xuất hiện.
3. **Tái sử dụng browser context** để navigate detail và gọi XHR.
4. **Lưu `storage_state`** để lần sau không cần login lại (trong giới hạn TTL của session).
5. **Nếu vẫn fail**, migrate sang **Camoufox** hoặc thêm residential proxy.

### Rủi ro

- Form login có thể thay đổi; cần robust selectors.
- Cloudflare có thể challenge trang login; Camoufox giải quyết tốt hơn `scrapling`.
- Lưu password trong DB (dù encrypted) là rủi ro bảo mật → cân nhắc dùng `storage_state` thay thế.

### Hành động tiếp theo

- Nếu muốn anh triển khai: cung cấp `username`/`password` Batdongsan (hoặc anh thêm trường và em tự nhập qua admin UI).
- Nếu không muốn lưu password: anh implement `storage_state` upload/download, user tự capture từ Playwright MCP.

---
