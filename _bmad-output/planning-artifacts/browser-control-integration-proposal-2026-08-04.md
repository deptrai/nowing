---
title: "Đề xuất tích hợp Browser-Control cho bdsai (extension trong browser của user)"
status: "draft kỹ thuật — cần luật sư duyệt ToS/Web Store trước khi phát hành"
created: "2026-08-04"
research_sources:
  - "Manus docs — Cloud Browser vs My Browser (Browser Operator extension)"
  - "browser-use docs — connect existing Chrome via CDP / user profile"
  - "playwright.dev — Playwright MCP (accessibility-tree automation)"
  - "Chrome MV3 docs — service worker / content script / host_permissions"
  - "OSS refs: crab-ts (Crab-Agent), hasaansworld/chrome-agent (MV3 side-panel agents)"
legal_throughline: "Chạy trong browser + session của chính user = dạng mạnh nhất của 'user tự làm'. NHƯNG: không auto-phá cổng hiện-số, không kho tập trung, và ToS/Web Store vẫn cần luật sư."
---

# Browser-Control cho bdsai — đề xuất tích hợp

## 0. Phát hiện then chốt từ research
**Chính Manus cũng làm y hệt vấn đề của bạn — và câu trả lời của họ là EXTENSION.** Manus có 2 chế độ (theo docs của họ):

| Chế độ Manus | Bản chất | Manus khuyến nghị khi |
|---|---|---|
| **Cloud Browser** | Browser headless trong **cloud của Manus**, IP data-center | Web công khai, scrape quy mô lớn |
| **My Browser (Browser Operator)** | **Extension** điều khiển **browser LOCAL của user**, IP dân cư, **session đăng nhập sẵn của user** | *"Đăng nhập tài khoản nhạy cảm; tránh CAPTCHA; site chặn IP data-center"* |

→ Đây chính là điều bạn cần: **Cloud Browser = đúng pattern server-side đang gây rủi ro cho bạn; My Browser (extension) = pattern hợp pháp hơn.** Bạn nên copy mô hình "Browser Operator extension".

## 1. Ba pattern & lựa chọn

| Pattern | Chạy ở đâu | Ai là "actor" | Ma sát cài | Phù hợp môi giới? |
|---|---|---|---|---|
| Cloud browser server-side (Manus Cloud, hiện trạng scraper của bạn) | Server bạn | **Bạn** ❌ | 0 | (rủi ro pháp lý cao) |
| CDP-attach Chrome local (`browser-use --cdp-url`, Playwright) | Máy user | **User** ✅ | Cao (cần chạy Chrome debug-port) | Chỉ power user/dev |
| **Extension MV3 (side panel + content script)** | Trình duyệt user | **User** ✅ | **Thấp** (cài từ store) | ✅ **Chọn cái này** |

**Kết luận:** làm **bdsai Browser Assistant** dạng **Chrome Extension MV3** (giống Manus "My Browser", và giống các OSS `crab-ts`/`chrome-agent`). Nó chạy trong session batdongsan mà môi giới **đã đăng nhập** — không server-side scrape, không proxy farm, không IP data-center.

## 2. Kiến trúc tích hợp

```
┌─ Trình duyệt của môi giới ───────────────────────────┐
│  Tab batdongsan/chotot/muaban (user ĐÃ đăng nhập)     │
│     ▲ đọc DOM (isolated world)                        │
│  [Content script] ──postMessage──► [Service worker]   │
│     │ inject UI nhỏ                      │            │
│  [Side panel React] ◄────────────────────┘            │
│        │ (chat, filter, kết quả)                      │
└────────┼──────────────────────────────────────────────┘
         │ HTTPS (token bdsai của user)
         ▼
┌─ bdsai backend (sản phẩm hiện có) ───────────────────┐
│  AI agent (engine Nowing) · workspace/memory per-user │
│  dedup · matching · alert · KHÔNG kho PII tập trung   │
└───────────────────────────────────────────────────────┘
```

**Thành phần extension (MV3):**
- **Side panel (React)** — chat + mô tả filter bằng lời + hiển thị kết quả/alert. (SSE stream từ bdsai backend.)
- **Content script** — chạy trong *isolated world*, đọc DOM listing user đang xem, trích dữ liệu có cấu trúc, chèn nút nhỏ ("Lưu vào bdsai"). Giao tiếp với service worker qua message passing.
- **Service worker** — điều phối, giữ token bdsai, `chrome.storage` cho state, `chrome.alarms` cho lịch "Deal-Radar". (Lưu ý MV3: worker bị kill khi idle — state phải ở `chrome.storage`, không giữ biến module.)
- **(Tùy chọn) `chrome.debugger`/CDP** cho input phức tạp — **né dùng** nếu chỉ đọc, vì nó hiện banner "controlled by automated software" và tăng rủi ro.

## 3. Auth (điểm pháp lý mấu chốt)
- **Extension xác thực với bdsai backend bằng tài khoản bdsai của user** (OAuth/token, lưu `chrome.storage.session`).
- **Extension KHÔNG bao giờ chạm credentials của portal.** Nó thao tác trong **tab mà user đã tự đăng nhập** batdongsan. → login là của user, IP là của user, session là của user. Đây là thứ biến "chỉ là công cụ" thành **sự thật**.
- Khi agent (engine Nowing ở backend) cần dữ liệu, nó nhận **dữ liệu đã trích từ session của user** do extension gửi lên — không tự đi crawl từ server.

## 4. Luồng "Deal-Radar" (automation) phiên bản hợp pháp
1. User mô tả filter bằng lời trong side panel → bdsai backend dựng truy vấn.
2. `chrome.alarms` đánh thức service worker theo khung giờ user đặt.
3. Service worker mở/refresh trang tìm kiếm portal **trong session của user** → content script trích **tin mới khớp** (thứ user vốn xem được).
4. Backend dedup/verify/matching **trong workspace của user** → gửi **alert + LINK VỀ NGUỒN** (extension notification / Telegram / inbox bdsai).
5. **KHÔNG auto bấm "hiện số".** Nếu user muốn số, họ tự bấm reveal theo luồng của chính portal. Extension không gọi `DecryptPhone`.

## 5. Giới hạn MV3 phải thiết kế quanh (từ Chrome docs)
- **Service worker ephemeral:** không giữ state trong biến; dùng `chrome.storage` + `chrome.alarms` (không `setInterval`).
- **Content script isolated world:** chia sẻ DOM, không chia sẻ JS scope của trang → message passing / `postMessage`.
- **Throttling tab nền:** Chrome bóp timer ở tab nền → lịch chạy nền có thể bị trễ; cân nhắc cần tab active hoặc dùng offscreen document. (Ràng buộc thực tế cho Deal-Radar.)
- **host_permissions hẹp:** chỉ khai 3 domain portal (đừng `<all_urls>`) để giảm cảnh báo quyền + ma sát review.
- **CSP không remote code:** bundle hết; mọi LLM call đi qua bdsai backend (khai host_permission tới API của bạn).
- **Chính sách Chrome Web Store:** extension tự động trích dữ liệu + quyền rộng bị soi kỹ ("single purpose", phải disclose). Extension chuyên "hút dữ liệu site cụ thể" có thể bị review từ chối hoặc portal khiếu nại → **rủi ro phát hành, cần tính trước.**

## 6. Bảo mật (theo pattern crab-ts/chrome-agent + GPTBots)
- Token bdsai ở `chrome.storage.session` (xóa khi đóng browser) hoặc mã hoá; **không lưu credentials portal**.
- `host_permissions` tối thiểu; content script isolated; TLS; validate mọi message từ content script (coi như untrusted).
- **Permission mode kiểu `ask`** (như crab-ts): domain nhạy cảm/đăng nhập cần user duyệt, không auto.
- Dữ liệu **chỉ ở workspace user**, retention tối thiểu, nút xoá. (Nhất quán thiết kế pháp lý đã chốt.)

## 7. Ranh giới pháp lý (KHÔNG đổi so với các phiên trước)
Extension đưa bạn tới **dạng mạnh nhất** của "user tự làm" — đúng như Manus "My Browser". Nhưng:
- ✅ Được: chạy trong session user, đọc thứ user được xem, alert + link, per-user, không kho tập trung.
- ⚠️ Vẫn nóng: **auto-phá cổng hiện-số** (đừng làm — để user tự bấm); **truy cập tự động vẫn có thể vi phạm ToS portal** (giờ là hành vi của user; extension là trợ lý chung, không phải máy hút số → inducement thấp hơn, nhưng **vẫn là câu hỏi luật sư**); **Chrome Web Store** có thể từ chối.
- ⚠️ Nếu dữ liệu trích (kể cả PII) gửi về workspace trên server bạn → bạn vẫn là **processor** → giữ tối thiểu + delete.

## 8. Lộ trình triển khai (pilot-friendly)
1. **MVP extension đọc-thôi:** side panel + content script trích listing user đang xem → "Lưu vào bdsai workspace". Không alarm, không phone. (Đủ cho pilot Deal-Radar thủ công.)
2. **Thêm Deal-Radar:** `chrome.alarms` + refresh search trong session user + alert-có-link.
3. **Song song:** luật sư duyệt (a) ToS 3 portal khi truy cập tự động qua session user, (b) chính sách Chrome Web Store, (c) PDPD xử lý dữ liệu trích trong workspace.
4. Gỡ hẳn code server-side scrape + `DecryptPhone` cũ (kill-list ở phiên trước) để code khớp mô hình mới.

## 9. Tham chiếu mã nguồn mở để học nhanh
- **crab-ts (Crab-Agent)** & **hasaansworld/chrome-agent**: extension MV3 side-panel, tool-use loop, `chrome.debugger`/CDP input, permission modes `ask/auto/strict`, sensitive-domain approval — gần đúng cái bạn cần.
- **browser-use**: nếu sau này làm bản desktop/power-user → `--cdp-url`/`user_data_dir` nối Chrome thật của user.
- **Playwright MCP**: mô hình điều khiển qua **accessibility tree** (200-400 token/snapshot) — tham khảo để agent đọc trang rẻ/ổn định.

## Tóm tắt một dòng
**Copy mô hình "My Browser / Browser Operator" của Manus: làm một Chrome MV3 extension chạy trong session đăng nhập của chính môi giới (side panel + content script + service worker + chrome.alarms), đẩy dữ liệu về workspace bdsai của họ — KHÔNG server-side scrape, KHÔNG auto hiện-số, KHÔNG kho tập trung. Đây là dạng mạnh nhất của "user tự làm", nhưng ToS portal + Chrome Web Store + PDPD vẫn phải qua luật sư trước khi phát hành.**
