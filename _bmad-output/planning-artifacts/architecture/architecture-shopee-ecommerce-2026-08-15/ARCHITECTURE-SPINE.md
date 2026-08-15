# Architecture Spine — Shopee Vietnam & E-commerce Intelligence Engine

**Ngày lập:** 2026-08-15  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-EC-1 đến AD-EC-6  
**Epic liên kết:** Epic 17 (E-commerce Intelligence & Pricing Engine)  
**Tác giả:** Winston (BMAD System Architect)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Cung cấp công cụ thu thập, giám sát giá và phân tích dữ liệu sản phẩm từ Shopee Vietnam và các sàn TMĐT:
* Tra cứu danh mục, tìm kiếm từ khóa, bóc tách giá hiện tại, giá trước giảm, số lượng đã bán (`historical_sold`), rating và review.
* Lưu trữ chuỗi thời gian biến động giá (`ecommerce_price_history`) để vẽ biểu đồ và kích hoạt cảnh báo giảm giá (**Price Drop Alerts**).
* Bóc tách sentiment và feedback khách hàng phục vụ nghiên cứu sản phẩm đối thủ.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-EC-1 [ADOPTED]: Fast-Path Reverse-Engineered Internal JSON API**
  * Không dùng Headless Browser (Playwright/Selenium) gây tốn CPU/RAM. Cào trực tiếp qua endpoint nội bộ `https://shopee.vn/api/v4/search/search_items` và `https://shopee.vn/api/v4/item/get` với User-Agent di động và header mã hóa chuẩn.
* **AD-EC-2 [ADOPTED]: Currency Scaling Factor Normalization**
  * Shopee lưu giá tiền theo hệ số nhân `100,000` (VD: `259000000` tương đương `2,590,000 VNĐ`). Engine bắt buộc chia `100,000` trước khi lưu vào PostgreSQL `NUMERIC(18, 2)`.
* **AD-EC-3 [ADOPTED]: Idempotent Product Upsert & Time-Series Price Logging**
  * Thông tin sản phẩm cập nhật dạng `ON CONFLICT (platform, item_id, shop_id) DO UPDATE`.
  * Mỗi lần quét giá mới nếu khác giá cũ, ghi 1 bản ghi vào `ecommerce_price_history`.
* **AD-EC-4 [ADOPTED]: Anti-Bot Rotating Datacenter/ISP Proxies**
  * Kết nối qua pool proxy xoay vòng tại Việt Nam; Token-Bucket limit $\le 30$ req/phút/IP.
* **AD-EC-5 [ADOPTED]: Alert Engine Saved Search Trigger**
  * Khi `current_price <= target_price` trong `AlertRule`, phát tín hiệu tức thì sang `app/alerts/engine/notify.py`.
* **AD-EC-6 [ADOPTED]: AI Capability Tool Registration**
  * Đăng ký 2 công cụ `shopee_search_products` và `shopee_track_price_history` cho Nowing Agent.

---

## 3. Mô Hình Cơ Sở Dữ Liệu (PostgreSQL DDL)

```sql
CREATE TABLE IF NOT EXISTS ecommerce_products (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL DEFAULT 'shopee',
    item_id BIGINT NOT NULL,
    shop_id BIGINT NOT NULL,
    shop_name TEXT,
    shop_location VARCHAR(100),
    title TEXT NOT NULL,
    brand VARCHAR(255),
    current_price NUMERIC(18, 2) NOT NULL,
    original_price NUMERIC(18, 2),
    discount_percent INT DEFAULT 0,
    historical_sold INT DEFAULT 0,
    rating_star NUMERIC(3, 2),
    rating_count INT DEFAULT 0,
    image_url TEXT,
    product_url TEXT,
    raw_specs JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ecommerce_product UNIQUE (platform, item_id, shop_id)
);

CREATE TABLE IF NOT EXISTS ecommerce_price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES ecommerce_products(id) ON DELETE CASCADE,
    price NUMERIC(18, 2) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecom_products_item_shop ON ecommerce_products(item_id, shop_id);
CREATE INDEX IF NOT EXISTS idx_ecom_price_history_prod ON ecommerce_price_history(product_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_ecom_products_gin_specs ON ecommerce_products USING gin (raw_specs);
```
