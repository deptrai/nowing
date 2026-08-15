# Story 17.2: Shopee Vietnam In-House Scraper & Price Normalization

Status: done

<!-- Governed by architecture-shopee-ecommerce-2026-08-15 (AD-EC-1 to AD-EC-8) and UX Widget U1 -->

## Story

As an e-commerce intelligence user or retail seller,
I want an in-house fast Shopee Vietnam scraper with exact price normalization and historical price tracking,
So that I can monitor product prices, capture price drops, and analyze merchant sales volume without relying on third-party APIs.

## Acceptance Criteria

1. **Given** a product search query or URL, **When** `ShopeeScraper` is invoked, **Then** it queries the Shopee Fast JSON API (`/api/v4/search/search_items` and `/api/v4/item/get`) with latency $\le 200$ms using stealth browser headers and rotating residential proxies.
2. **Given** raw Shopee pricing data (scaled by $100,000$), **When** `ShopeePriceNormalizer` executes, **Then** it applies `Decimal(raw_price) / Decimal("100000")` with `ROUND_HALF_UP` and stores the normalized value in `NUMERIC(18, 2)` (preventing floating point imprecision).
3. **Given** product records, **When** persisted to PostgreSQL, **Then** records are saved into `ecommerce_products` with unique constraint `(platform, external_product_id)` and status (`in_stock`, `out_of_stock`, `unlisted`).
4. **Given** price observations over time, **When** price changes occur, **Then** historical snapshots are saved into `ecommerce_price_history` with timestamps for generating 90-day sparkline charts (Widget U1).
5. **Given** an AI Agent session, **When** calling `ecommerce_search_products(keyword, min_price, max_price)` or `ecommerce_track_price_history(product_id)`, **Then** normalized pricing, ratings, sales volume, and historical trends are returned.

## Architectural Invariants Mapping

- **AD-EC-1**: Direct Internal Endpoint Ingress (`/api/v4/search/search_items` & `/api/v4/item/get`)
- **AD-EC-2**: Decimal Price Normalization (`Decimal / 100000`, `NUMERIC(18, 2)`)
- **AD-EC-3**: Historical Price Time-Series Storage with Deduplication
- **AD-EC-4**: Stealth Session Headers & Rotating Vietnamese Residential Proxies
- **AD-EC-5**: AI Agent Capability Tools (`ecommerce_search_products`, `ecommerce_track_price_history`)
- **AD-EC-6**: Idempotent Product Ingestion with Unique `(platform, external_product_id)`
- **AD-EC-7**: 90-day Sparkline Price Visualization & 1-Click Price Drop Alert (Widget U1)

## Review Findings & Fixes Applied (2026-08-15)

- [x] RF-1: URL-encode Vietnamese keywords in Referer header using `quote_plus` to prevent `UnicodeEncodeError`.
- [x] RF-2: Atomic PostgreSQL upsert handling in `record_or_get_price_history` using nested transaction savepoints.
- [x] RF-3: Unified `external_product_id` format to `f"{shop_id}_{item_id}"` and supported single/composite ID resolutions.
- [x] RF-4: Added `not val.is_finite()` guard against `NaN` and `Infinity` in `normalize_price` and `normalize_rating`.
- [x] RF-5: Cleaned percentage formatting in `normalize_discount` (`"25%"`, `"-18%"`).
- [x] RF-6: Safe string/null rating count summation in `scraper.py`.
- [x] RF-7: Anti-bot HTML challenge retry backoff and mapped HTTP 404 to `ShopeeNotFoundError`.
- [x] RF-8: Added baseline fallback price query before 90 days when recent history is stable/empty.
- [x] RF-9: Removed redundant duplicate composite index in `EcommercePriceHistory`.
- [x] RF-10: Added `min_price <= max_price` and non-empty keyword validators in `EcommerceSearchInput`.

## Tasks / Subtasks

- [x] Task 1: Database Models & Migrations (AC: 2, 3, 4)
  - [x] 1.1 Tạo model `EcommerceProduct` trong `nowing_backend/app/proprietary/platforms/shopee/models.py` (`id`, `platform`, `external_product_id`, `shop_id`, `name`, `current_price NUMERIC(18, 2)`, `original_price NUMERIC(18, 2)`, `rating_star FLOAT`, `historical_sold INT`, `stock INT`, `status`, `product_url`, `created_at`, `updated_at`, `CONSTRAINT uq_ecommerce_product UNIQUE (platform, external_product_id)`).
  - [x] 1.2 Tạo model `EcommercePriceHistory` (`id`, `product_id`, `price NUMERIC(18, 2)`, `recorded_at`).
  - [x] 1.3 Tạo chỉ mục `idx_shopee_product_ext_id` và `idx_shopee_price_history_product_time`.
- [x] Task 2: Shopee Fast JSON Scraper & Stealth Client (AC: 1, 4)
  - [x] 2.1 Xây dựng `ShopeeScraper` tại `nowing_backend/app/proprietary/platforms/shopee/scraper.py`.
  - [x] 2.2 Tích hợp stealth client headers (`User-Agent`, `af-ac-enc-dat`, `X-Shopee-Language: vi`).
  - [x] 2.3 Xử lý exponential backoff retry khi gặp HTTP 429 / 403.
- [x] Task 3: Decimal Price Normalization Pipeline (AC: 2)
  - [x] 3.1 Xây dựng `ShopeePriceNormalizer` tại `nowing_backend/app/proprietary/platforms/shopee/normalizer.py`.
  - [x] 3.2 Viết logic chia `100,000` chính xác tuyệt đối với kiểu dữ liệu `Decimal`.
- [x] Task 4: AI Agent Capability & Tools (AC: 5)
  - [x] 4.1 Đăng ký Capability `ecommerce.products` trong `nowing_backend/app/capabilities/ecommerce/`.
  - [x] 4.2 Định nghĩa Agent Tool `nowing_ecommerce_search_products` và `nowing_ecommerce_track_price_history`.
- [x] Task 5: Unit & Quality Tests (AC: 1-5)
  - [x] 5.1 `tests/unit/proprietary/platforms/shopee/test_shopee_normalizer.py` (Assert Decimal / 100k and diacritics).
  - [x] 5.2 `tests/unit/proprietary/platforms/shopee/test_shopee_scraper.py` (Mock /api/v4 JSON responses).
  - [x] 5.3 `tests/unit/capabilities/test_ecommerce_capabilities.py`.

## Dev Notes

- **Shopee Scale Invariant:** Shopee API trả về giá tiền nhân với 100,000 (Ví dụ: `15000000000` đại diện cho `150,000` VNĐ). Tuyệt đối không dùng `float` để chia; BẮT BUỘC dùng `Decimal(str(raw_price)) / Decimal("100000")`.
- **Dependencies:** `httpx>=0.27.0`, `sqlalchemy>=2.0.0`.

### References
- [Architecture Spine: architecture-shopee-ecommerce-2026-08-15/ARCHITECTURE-SPINE.md]
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U1]

