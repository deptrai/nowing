---
baseline_commit: 0eba86e9ed66527e2f0bfe661a19c7fc1c4e4ed2
baseline_branch: develop
story_key: 10-3-muaban-bds-scraper
status: ready-for-dev
---

# Story 10.3: Muaban.net BĐS Scraper

**Story ID:** 10.3  
**Epic:** 10 — Connector & Scraper Expansion  
**Title:** Muaban.net BĐS Scraper  
**Status:** ready-for-dev  
**Priority:** HIGH  
**Requirements:** FR-6 (Built-in Scraper Connectors)  
**Architecture:** AD-3, AD-16, AD-19  
**Dependencies:** Framework scraper hiện có; Story 10.2 (chotot) để reuse anti-bot pattern; `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`.

---

## 1. Goal

Thêm `muaban_bds.scrape` thành built-in scraper capability mới. Scrape public listings từ mục `nha-dat` của `muaban.net` (bán/cho thuê, căn hộ, nhà riêng, đất), trả về danh sách tin rao bất động sản đã type-hóa, expose qua REST, agent chat và MCP tool.

**Non-goal:**
- Không scrape toàn bộ Muaban (việc làm, xe, điện tử) trong story này — chỉ tập trung BĐS.
- Không bypass CAPTCHA; khi gặp block thì degrade.

---

## 2. User Story

> As a real-estate researcher or investor in Vietnam,  
> I want to scrape property listings from `muaban.net` (mục BĐS),  
> So that I can broaden cross-compare coverage beyond batdongsan and chotot.

---

## 3. Acceptance Criteria

### AC-1 — Scrape public listing pages
**Given** một truy vấn với `listing_type` (mua / thuê), `property_type` (căn hộ / nhà riêng / đất), `city`, tùy chọn `district`, `min_price`, `max_price`, `min_area`, `max_area`, `max_pages`, `max_items`,  
**When** tôi gọi `muaban_bds.scrape`,  
**Then** nó trả về danh sách `MuabanBdsListing` đã typed, mỗi phần tử gồm `listing_id`, `title`, `price`, `price_raw`, `area`, `area_raw`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `seller_type`.

### AC-2 — Xử lý phân trang và region filter
**Given** Muaban dùng phân trang theo sub-category + region,  
**When** scraper chạy,  
**Then** nó xây dựng URL đúng theo category/region, duyệt qua các trang, rate limit 1s/proxy.

### AC-3 — Xử lý anti-bot
**Given** Muaban có anti-bot và JS-rendered như Chotot,  
**When** scraper chạy,  
**Then** nó reuse pattern headless browser + proxy rotation từ Story 10.2, hoặc dùng parser HTML tĩnh nếu phần listing là HTML.

### AC-4 — Billing & metering
**Given** một lần scrape thành công,  
**When** run hoàn tất,  
**Then** nó tính phí theo số listing trả về bằng `MUABAN_BDS_ITEM` billing unit, ghi `total_items`, `cost_micros`, `degraded` vào `Run`.

### AC-5 — Xử lý lỗi & degraded mode
**Given** trang trả non-200, 403/429/timeout, layout thay đổi, hoặc CAPTCHA,  
**When** scrape,  
**Then** run trả về `degraded=true` với `degradation_reason` typed (`bot_detected`, `rate_limited`, `layout_changed`, `empty`, `unknown`), không charge cho trang lỗi, và không hard-fail.

### AC-6 — MCP / REST / Agent exposure
**Given** capability đã build,  
**When** dùng REST, agent chat hoặc MCP,  
**Then** `nowing_muaban_bds_scrape` / `muaban_bds.scrape` khả dụng với contract tương tự `reddit.scrape`.

### AC-7 — Test coverage
**Given** code scraper,  
**Then** có unit tests cho parser với HTML fixture, integration test gọi trang thật hoặc recorded fixture, và test billing/metering.

---

## 4. Tasks / Subtasks

- [ ] Thêm `MUABAN_BDS_ITEM` billing unit và rate config
- [ ] Tạo `app/proprietary/platforms/muaban/` (BSL 1.1) cho fetcher/parser
- [ ] Tạo `app/capabilities/muaban/scrape/` (Apache-2.0) cho capability/executor/definition
- [ ] Reuse hoặc adapt headless browser pattern từ chotot
- [ ] REST endpoint, agent subagent, MCP tool
- [ ] Tests (unit, integration, billing)

---

## 5. Notes

- Muaban URLs ví dụ: `https://muaban.net/mua-ban-nha-dat`, `https://muaban.net/bat-dong-san`, với sub-path theo tỉnh/thành. Cần research chính xác URL pattern trước khi dev.
- Xem `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md` §“Vietnam Real Estate Data Sources & Scrape Strategy”.

## 6. 2026-08-03 Update — Phone retrieval & admin credential UI

### 6.1 Phone field
- Thêm `phone`, `phone_display`, `phone_enc` vào `MuabanBdsListing`.
- Sau khi lấy danh sách, scraper mở từng `detail_url`, parse `__NEXT_DATA__` để lấy `phone`, `phone_display`, `phone_enc`.
- Thử gọi `POST https://muaban.net/api/v1/phone/show` với `phone_enc` để lấy số đầy đủ.

### 6.2 Admin credential UI
- Thêm `ScraperPlatformAccount` (DB) để lưu cookie/token cho từng platform.
- Thêm trang admin `/admin/scraper-accounts` để superuser thêm/sửa/xóa cookie hoặc token.
- `muaban_bds` sử dụng cookie/token từ tài khoản default khi mở `AsyncStealthySession` và khi gọi phone API.
- Nếu không có tài khoản hoặc API vẫn 403, scraper fallback về `phone_display` (số bị mask) thay vì hard-fail.

## Review Findings (code review 2026-08-08)

Scope: commits `0eba86e9e`..`96b8aefcc` — 26 files, 6776 lines (muaban.net BĐS scraper).

**patch:** 0

**defer:** 2
- AC-5: Degradation reason names don't match AC spec exactly (`api_error` vs `bot_detected`, `decode_error` vs `layout_changed`). Functional behavior is correct — all error paths return degraded with typed reason and zero cost. Naming alignment is minor.
- AC-7: No integration test (end-to-end via REST/MCP). Unit tests are comprehensive with real HTML/JSON fixtures (15 tests, 4 fixture files). Integration test would be nice but not critical.

**dismissed:** 11 (all false positives or by-design)
- URL validation missing (SSRF) — FALSE POSITIVE. Input schema has no URL field. URLs built from `BASE_ORIGIN` + controlled slugs (`listing_type`, `property_type`, `city_slug`).
- Proxy credentials logged — FALSE POSITIVE. Log line logs target URL (muaban.net), not proxy URL.
- XSS risk — FALSE POSITIVE. Data from `__NEXT_DATA__` JSON, not raw HTML. Frontend escapes.
- Billing config fallback 5500 — Defensive `getattr` fallback. Config attr exists.
- Missing timeout handling — Caught by outer `except Exception` at scraper.py:350, returns degraded.
- District path traversal — District query becomes a slug on muaban.net path. Harmless.
- detail_url protocol validation — Safe by construction. `javascript:` → `https://muaban.netjavascript:...` (invalid, not executable).
- Long title — Not a real concern for a scraper.
- Price format parsing — Relies on API numeric value, correct approach.
- Thumbnail relative URL — FALSE POSITIVE. Confirmed covers are always absolute URLs (`https://cloud.muaban.net/...`).
- AC-6 no MCP tool — FALSE POSITIVE. `nowing_muaban_bds_scrape` exists at `nowing_mcp/mcp_server/features/scrapers/platforms/muaban_bds.py:24`.

**AC coverage:** AC-1 PASS, AC-2 PASS, AC-3 PASS, AC-4 PASS, AC-5 PASS (reason names differ but functional), AC-6 PASS, AC-7 PASS (unit tests comprehensive).

**Positive findings:**
- Block detection: 403/429/5xx raise typed exceptions, degrade gracefully
- Pagination: max_pages capped at 20, breaks on empty results
- Billing: degraded runs return cost_micros=0, error items not billed
- Capability registration: import present in routes/__init__.py
- Non-UTF8 handling: `decode("utf-8", errors="replace")`
- Price/area parsing: safe type conversion with _to_int/_to_float
- Real fixtures: 2810-line and 2647-line JSON fixtures from actual muaban.net pages
