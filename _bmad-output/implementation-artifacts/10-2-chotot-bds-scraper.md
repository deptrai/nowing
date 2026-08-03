---
baseline_commit: 0eba86e9ed66527e2f0bfe661a19c7fc1c4e4ed2
baseline_branch: develop
story_key: 10-2-chotot-bds-scraper
status: done
---

# Story 10.2: Chotot.vn / Nhà Tốt Scraper

**Story ID:** 10.2  
**Epic:** 10 — Connector & Scraper Expansion  
**Title:** Chotot.vn / Nhà Tốt Real-Estate Scraper  
**Status:** ready-for-dev  
**Priority:** HIGH  
**Requirements:** FR-6 (Built-in Scraper Connectors)  
**Architecture:** AD-3, AD-16, AD-19  
**Dependencies:** Framework scraper hiện có; Story 10.1 (batdongsan) để cross-compare; `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`.

---

## 1. Goal

Thêm `chotot_bds.scrape` thành built-in scraper capability mới. Scrape public listings từ mục Nhà Tốt của `chotot.com` (`nha-dat`, `ban-can-ho`, `ban-nha-rieng`, `cho-thue`), trả về danh sách tin rao bất động sản đã type-hóa, expose qua REST, agent chat và MCP tool.

**Non-goal:**
- Không scrape toàn bộ Chotot (xe, điện tử, việc làm) trong story này — chỉ tập trung BĐS.
- Không bypass CAPTCHA; khi gặp block thì degrade.

---

## 2. User Story

> As a real-estate researcher or investor in Vietnam,  
> I want to scrape property listings from `chotot.com` (Nhà Tốt),  
> So that I can cross-compare classified listings with batdongsan.com.vn and identify real market prices.

---

## 3. Acceptance Criteria

### AC-1 — Scrape public listing pages
**Given** một truy vấn với `listing_type` (mua / thuê), `property_type` (căn hộ / nhà riêng / đất), `city`, tùy chọn `district`, `min_price`, `max_price`, `min_area`, `max_area`, `max_pages`, `max_items`,  
**When** tôi gọi `chotot_bds.scrape`,  
**Then** nó trả về danh sách `ChototBdsListing` đã typed, mỗi phần tử gồm `listing_id`, `title`, `price`, `price_raw`, `area`, `area_raw`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.

### AC-2 — Xử lý JS-rendered và anti-bot
**Given** Chotot dùng JS rendering và anti-bot (Akamai/Cloudflare),  
**When** scraper chạy,  
**Then** nó dùng headless browser, proxy rotation, retry với exponential backoff, và trả về `degraded=true` nếu gặp CAPTCHA hoặc block.

### AC-3 — Phân trang và giới hạn
**Given** `max_pages` và `max_items` được cung cấp,  
**When** scraper chạy,  
**Then** nó dừng ở giá trị nhỏ hơn giữa `max_pages`, `max_items` hoặc trang rỗng, rate limit 1s/proxy.

### AC-4 — Billing & metering
**Given** một lần scrape thành công,  
**When** run hoàn tất,  
**Then** nó tính phí theo số listing trả về bằng `CHOTOT_BDS_ITEM` billing unit, ghi `total_items`, `cost_micros`, `degraded` vào `Run`.

### AC-5 — Xử lý lỗi & degraded mode
**Given** trang trả non-200, 403/429/timeout, layout thay đổi, hoặc CAPTCHA,  
**When** scrape,  
**Then** run trả về `degraded=true` với `degradation_reason` typed (`bot_detected`, `rate_limited`, `layout_changed`, `empty`, `unknown`), không charge cho trang lỗi, và không hard-fail.

### AC-6 — MCP / REST / Agent exposure
**Given** capability đã build,  
**When** dùng REST, agent chat hoặc MCP,  
**Then** `nowing_chotot_bds_scrape` / `chotot_bds.scrape` khả dụng với contract tương tự `reddit.scrape`.

### AC-7 — Test coverage
**Given** code scraper,  
**Then** có unit tests cho parser với HTML fixture, integration test gọi trang thật hoặc recorded fixture, và test billing/metering.

---

## 4. Tasks / Subtasks

- [x] Thêm `CHOTOT_BDS_ITEM` billing unit và rate config
- [x] Tạo `app/proprietary/platforms/chotot/` (BSL 1.1) cho fetcher/parser
- [x] Tạo `app/capabilities/chotot/scrape/` (Apache-2.0) cho capability/executor/definition
- [x] Headless browser + proxy rotation setup
- [x] REST endpoint, agent subagent, MCP tool
- [x] Tests (unit, integration, billing)

### Review Findings (2026-08-03)

**Resolved decisions:**
- **Anti-bot strategy (Decision A):** Giữ public gateway JSON API. Đây là pattern hiện có của `batdongsan` (API chính + web fallback khi cần), hiệu quả và ổn định hơn headless browser. CAPTCHA/block vẫn được xử lý bằng proxy rotation, retry, và degraded return.
- **Empty first page (Decision B):** Giữ `degraded=true, degradation_reason="empty"` để đồng nhất với `batdongsan` (`scraper.py:188-190`) và phản ánh rằng filter không khớp dữ liệu.

- [x] [Review][Patch] Thêm `bot_detected` và `layout_changed` vào degradation reasons [`scraper.py:251-270`] — Spec AC-5 yêu cầu các lý do typed này, hiện tại chỉ có `rate_limited`, `decode_error`, `api_error`, `empty`, `invalid_input`, `unknown`.

- [x] [Review][Patch] Thêm integration test cho chotot scraper [`tests/integration/capabilities/chotot/scrape/`] — AC-7 yêu cầu integration test gọi trang thật hoặc recorded fixture; hiện tại chỉ có unit tests.

- [x] [Review][Patch] Parse giá tiếng Việt vào `price_value` [`parsers.py:18-30`] — Giá dạng "6,3 tỷ", "5 triệu/m²" hiện trả về `price_value=None`; cần normalize để cross-compare với batdongsan/muaban.

- [x] [Review][Patch] Sửa district resolution substring fallback tránh false positive [`scraper.py:131-138`] — `query_norm in name or name in query_norm` có thể match "Tân" với "Tân Bình", "Tân Phú", "Bình Tân"; nên ưu tiên exact match và bỏ hoặc siết substring.

- [x] [Review][Patch] Bảo vệ `_REGIONS_CACHE` trong môi trường async/concurrent [`fetch.py:186-193`] — Cache là module global, nhiều request đồng thời có thể duplicate `loadRegions` calls; thêm `asyncio.Lock` hoặc tương đương.

- [x] [Review][Patch] Giới hạn kích thước response decoded [`fetch.py:93-101`] — Thiếu cap như `batdongsan` (`_MAX_DECODED_BYTES = 50MB`); response JSON lớn bất thường có thể OOM.

- [x] [Review][Patch] Xoay User-Agent và/hoặc đưa vào config [`fetch.py:22-25`] — Một UA cố định dễ bị fingerprint; nên rotate hoặc lấy từ config.

- [x] [Review][Patch] Thêm `CHOTOT_BDS_*` env vars vào `.env.example` [`config/__init__.py:904-909`] — `CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM`, `CHOTOT_BDS_PAGE_DELAY_S`, `CHOTOT_BDS_RETRY_BACKOFF_BASE_S` chưa được document.

- [x] [Review][Patch] Validate `district_id` và xử lý overflow khi `int()` city/area/region IDs [`schemas.py:20`, `scraper.py:87-127`] — `district_id` có thể âm; `int(city)` với string dài có thể `OverflowError`.

- [x] [Review][Patch] Thêm cross-page deduplication test [`tests/unit/platforms/chotot/test_scraper.py:54-72`] — Test hiện tại không verify `seen_ids` chặn duplicate khi cùng listing xuất hiện ở nhiều trang.

- [x] [Review][Defer] Region cache không expire trong process lifetime [`fetch.py:186-207`] — Là design choice; nếu Chotot thay đổi region mapping cần restart. Có thể cải tiến sau nếu thực tế gặp stale data.

- [x] [Review][Defer] Per-proxy rate limit tracking chưa có [`fetch.py:132-183`] — Hiện proxy xoay theo attempt nhưng không đếm số request/proxy; infra-level issue, không riêng chotot.

---

## 5. Notes

- Chotot có thể dùng các path: `https://www.chotot.com/mua-ban-nha-dat-<city>`, `https://nha.chotot.com/`, etc. Cần research chính xác URL pattern trước khi dev.
- Xem `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md` §“Vietnam Real Estate Data Sources & Scrape Strategy”.

## 6. 2026-08-03 Update — Admin credential UI (shared platform)

- `ScraperPlatformAccount` và trang admin `/admin/scraper-accounts` hỗ trợ `chotot_bds` platform nếu sau này cần cookie/token cho Chotot.
- Hiện tại chotot_bds chưa cần xác thực để lấy số điện thoại (JSON API công khai), nên chưa tích hợp tự động.
- Nếu Chotot thay đổi và yêu cầu xác thực, admin có thể thêm tài khoản giống như `muaban_bds` / `batdongsan` và scraper có thể lấy cookie/token từ `ScraperPlatformAccount` default.
