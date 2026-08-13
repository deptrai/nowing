---
story: "15.1 CafeF Financial Data Integration"
reviewed_commit: current
parent_commit: 09f8c8c24
reviewer: bmad-code-review
review_date: "2026-08-14"
verdict: approved
---

# BMAD Code Review — Story 15.1 "CafeF Financial Data Integration" (re-review)

## Tóm tắt phán quyết

- **Mức độ:** `APPROVED` — 2 must-fix, 5 should-fix, 3 watch đã được xử lý.
- **Kết quả kiểm thử:** 30 unit + integration test CafeF pass; `ruff` pass trên toàn bộ file thay đổi.

## Kiểm thử đã chạy

```bash
cd nowing_backend
ruff check app/capabilities/cafef app/proprietary/platforms/cafef \
  tests/unit/platforms/cafef tests/integration/cafef tests/unit/capabilities/cafef
# → All checks passed

uv run pytest tests/unit/platforms/cafef tests/unit/capabilities/cafef tests/integration/cafef -q
# → 30 passed
```

## Live probe sau sửa

| Endpoint | HTTP | Ghi chú |
|---|---|---|
| `https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?...` | **200** | Trả OHLCV real-time cho `VCB` |
| `https://cafef.vn/thi-truong-chung-khoan.rss` | **200** | RSS market news; content-type text/html nhưng body là XML hợp lệ |
| `https://apiweb.cafef.vn/api/v2/BCTC/GetReportCDKT?symbol=VCB&...` | **200** | Dữ liệu BCTC đúng cấu trúc `templace`/`data` |
| `https://apiweb.cafef.vn/api/v1/BCTC/GetReportDetail?symbol=VCB&...` | **200** | KQKD dạng flat |
| `https://apiweb.cafef.vn/api/v1/BCTC/GetReportLCTT?symbol=VCB&...` | **200** | LCTT dạng nhóm |

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|---|---|---|
| AC-1 — Quote/OHLCV/ratios | **Đạt** | Quote lấy từ price-history Ajax endpoint, trả OHLCV, volume, change, change_percent. |
| AC-2 — Financial statements | **Đạt** | 3 endpoint BCTC hoạt động, parser xử lý đúng cả dạng flat và nhóm, `key_metrics` được trích. |
| AC-3 — Market news in search | **Đạt** | News lấy từ category RSS `https://cafef.vn/thi-truong-chung-khoan.rss` và filter theo symbol. |
| AC-4 — Rate limit 20 req/min | **Đạt** | Process-local throttle; 429 retry với bounded exponential backoff. |

## Findings đã xử lý

### [must-fix] M1. Endpoint quote và news live trả về 404

- **Trạng thái:** Đã sửa.
- **Giải pháp:**
  - `_QUOTE_URL` chuyển sang `https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx` với range 30 ngày, thử 3 sàn `HOSE`, `HNX`, `UPCOM`.
  - `_NEWS_URL` chuyển sang RSS `https://cafef.vn/thi-truong-chung-khoan.rss` và filter bằng symbol.
- **Files thay đổi:** `app/proprietary/platforms/cafef/fetch.py`.

### [must-fix] M2. Parser không kiểm tra `isSuccess: false`

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `parse_quote` và `parse_financials` đã kiểm tra `isSuccess is False` và raise `CafeFAccessBlockedError` với nội dung lỗi.
- **Files thay đổi:** `app/proprietary/platforms/cafef/parsers.py`.

### [should-fix] S1. `_do_get` thiếu headers, không follow redirects, không phân biệt Cloudflare challenge

- **Trạng thái:** Đã sửa.
- **Giải pháp:** Đã thêm `_CAFEF_HEADERS`, `follow_redirects=True`, kiểm tra `content-type` HTML và raise `CafeFAccessBlockedError`.

### [should-fix] S2. Rate throttling không retry khi gặp 429

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `_do_get` retry tối đa `_MAX_429_RETRIES=2` với exponential backoff `_BACKOFF_BASE_S=1.0`.

### [should-fix] S3. `fetch_news` không tôn trọng `max_news=0` và `parse_news` không truncate

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `CafeFScrapeInput.max_news` thêm `le=50`; `_news_url` cho phép `pageSize=0`; `parse_news` nhận `max_news` và truncate.

### [should-fix] S4. `_build_name_map` bỏ sót code xuất hiện trong `data` nhưng không có trong `templace`

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `_build_name_map` merge codes từ `data` với `name` mặc định là code; `parse_financials` trích `key_metrics` từ các code chuẩn.

### [should-fix] S5. `scraper.py` catch `Exception` rộng, nuốt traceback

- **Trạng thái:** Đã sửa.
- **Giải pháp:** Tách `Exception` ra `logger.exception`, các lỗi cụ thể dùng `exc_info`; news failure không degrade toàn bộ scrape.

### [watch] W1. Demo mode mặc định `CAFEF_DEMO_MODE=true` vẫn có thể bị tính phí

- **Trạng thái:** Không thay đổi trong phạm vi story; ghi nhận là trade-off. `CAFEF_DEMO_MODE=true` vẫn cần được gắn với billing-off trong môi trường dev.

### [watch] W2. `key_metrics` của báo cáo tài chính luôn rỗng

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `parse_financials` tính `key_metrics` từ các code chuẩn (`270`, `300`, `400`, `10`, `20`, `60`, `HDKD_20`, `HDTC_42`).

### [watch] W3. `CafeFQuote` fallback key chọn giá trị `None`

- **Trạng thái:** Đã sửa.
- **Giải pháp:** `_get` trong `parse_quote` bỏ qua các giá trị `None`, chọn key đầu tiên có giá trị hợp lệ.

## P0 / Human Review Notes

This re-review touches the CafeF scraper degradation path (`scraper.py`), which determines `CafeFScrapeOutput.billable_units` and therefore the `cost_micros` charged to the workspace via `app/capabilities/cafef/scrape/executor.py`. Although the `billable_units` property itself is unchanged, the `degraded` flow and `Exception` handling in `scraper.py` directly affect whether a scrape is billed. Per Nowing P0 policy, any change that can influence credit/quota accounting requires human review before the story is marked `done`.

**What to review manually:**
- `app/proprietary/platforms/cafef/scraper.py:49-109` — `degraded` logic for quote/financials/news and `logger.exception` paths.
- `app/proprietary/platforms/cafef/schemas.py:116-119` — `billable_units = 0 if self.degraded or self.quote is None else 1` remains unchanged.
- `app/capabilities/cafef/scrape/executor.py` (not modified, but consumer) — confirm `billable_units` is used to compute `cost_micros`.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|---|---|---|
| must-fix | 0 | - |
| should-fix | 0 | - |
| watch | 1 | W1 (demo billing, ngoài phạm vi) |
| non-issue | 3 | N1-N3 |

## Hành động tiếp theo

1. Chạy `bmad-nowing-human-review-gate` cho P0 change.
2. Chạy `bmad-nowing-mutation-gate` nếu khuyến nghị.
3. Cập nhật story status thành `done` sau khi human review approve.
