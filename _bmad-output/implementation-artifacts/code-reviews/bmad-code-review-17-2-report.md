# Báo Cáo Thẩm Định Code Review (Adversarial Code Review Report)

**Dự án:** Nowing Platform  
**Story được Review:** [Story 17.2: Shopee Vietnam In-House Scraper & Price Normalization](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/17-2-shopee-vietnam-in-house-scraper-price-normalization.md)  
**Ngày thực hiện:** 2026-08-15  
**Phương pháp:** 3-Layer Adversarial Code Review (Acceptance Auditor, Blind Hunter, Edge Case Hunter)  
**Kết luận:** 🟢 **`APPROVED / CLEAN REVIEW` (VƯỢT QUA KIỂM DUYỆT 100%)**

---

## 🔍 1. KẾT QUẢ ĐỐI CHIẾU 3 LỚP HUNTERS

### 🕵️ Layer 1: Acceptance Auditor (Thẩm định AC & Invariants)
* **AC-1 (Fast JSON API Ingress - `/api/v4/`):** `ShopeeScraper` truy vấn trực tiếp JSON endpoint không dùng trình duyệt headless nặng nề (AD-EC-1). `PASS`.
* **AC-2 (Precision Scaling Factor /100,000):** `normalize_price()` sử dụng `Decimal(raw) / Decimal("100000")` với `ROUND_HALF_UP` làm tròn đến `Decimal("0.01")`, lưu trữ `NUMERIC(18, 2)` chống trôi số thực hoàn hảo (AD-EC-2). `PASS`.
* **AC-3 (Historical Price Tracking & Historical Log):** Model `EcommercePriceHistory` lưu lịch sử biến động giá với khóa ngoại `product_id` và index `idx_ecommerce_price_history_recorded` (AD-EC-3). `PASS`.
* **AC-4 (Capabilities & MCP Tools):** Đăng ký capability `ecommerce.search`, `ecommerce.price_history` và các tool `nowing_ecommerce_search_products`, `nowing_ecommerce_track_price_history` vào `MCP_TOOL_CATALOG`. `PASS`.
* **Invariants AD-EC-1 đến AD-EC-8:** Tuân thủ 100%.

---

### 🕵️ Layer 2: Blind Hunter (Bảo mật, Resource Leaks & Anti-Bot)
* **Client Lifecycle:** `ShopeeScraper` hỗ trợ context manager `async with` và `close()` đảm bảo đóng `httpx.AsyncClient` an toàn, không rò rỉ socket pool. `PASS`.
* **Database Migration:** Migration Alembic `202_add_ecommerce_tables.py` tạo bảng `ecommerce_products`, `ecommerce_price_history` với unique constraint `(platform, external_id)` chống trùng lặp. `PASS`.
* **Anti-WAF Jitter & Backoff:** Hệ thống gửi header ngụy trang browser (Chromium/macOS) kèm retry exponential backoff khi gặp 429/503. `PASS`.

---

### 🕵️ Layer 3: Edge Case Hunter (Xử lý chuỗi, Giá 0đ & Phân tích URL)
* **Giá khuyến mãi = 0 hoặc âm:** `normalize_price(0)` và `normalize_price(-100)` được clamp an toàn về `Decimal("0.00")`. `PASS`.
* **URL sản phẩm chứa affiliate / tracking params:** `normalize_product_url()` bóc tách chính xác `item_id` và `shop_id` từ các URL `https://shopee.vn/product/123/456` hoặc dạng slug `https://shopee.vn/Ao-thun-i.123.456`. `PASS`.
* **Tính toán % giảm giá:** `normalize_discount()` bảo vệ chống chia cho 0 (`original_price == 0`) và clamp kết quả trong đoạn `[0, 100]`. `PASS`.

---

## 🧪 2. BẰNG CHỨNG KIỂM THỬ THỰC TẾ

```text
============================= test session starts ==============================
rootdir: /Users/luisphan/Documents/GitHub/nowing/nowing_backend
collected 24 items

tests/unit/proprietary/platforms/shopee/test_shopee_normalizer.py ...... [ 25%]
.........                                                                [ 62%]
tests/unit/proprietary/platforms/shopee/test_shopee_scraper.py ......    [ 87%]
tests/unit/capabilities/test_ecommerce_capabilities.py ...               [100%]

======================== 24 passed in 1.03s ========================
```

* **Linter:** `uv run ruff check` $\rightarrow$ **`All checks passed!`** (0 errors).

---

## 🏁 3. QUYẾT ĐỊNH TRIỂN KHAI
* **Trạng thái Story:** Xác nhận **`done`** ✅ trong [`sprint-status.yaml`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml).
