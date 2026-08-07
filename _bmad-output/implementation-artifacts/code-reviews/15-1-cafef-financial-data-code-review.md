---
story: "15.1 CafeF Financial Data Integration"
reviewed_commit: 09f8c8c24
parent_commit: 6b716938095a8a8b530f0999f47a0d499ca9c99e
reviewer: bmad-code-review
review_date: "2026-08-07"
verdict: changes_requested
---

# BMAD Code Review — Story 15.1 "CafeF Financial Data Integration"

## Tóm tắt phán quyết

- **Mức độ:** `CHANGES_REQUESTED` — còn **2 must-fix**, **5 should-fix**, **3 watch**, **3 non-issue**.
- **Rủi ro chính:** Các endpoint **quote** và **news** hardcoded trả về `404` khi gọi thật, khiến AC-1 và AC-3 không thỏa mãn ở live mode; parser không kiểm tra `isSuccess: false`, dễ tính phí cho dữ liệu rỗng; thiếu header/redirect/cloudflare defense; rate throttling chỉ ở process-local và không retry 429.
- **Kiểm thử:** 29 unit + integration test CafeF đều pass; `ruff` pass trên toàn bộ file thay đổi; `nowing_mcp` selfcheck pass với 53 tool.

## Thống kê diff

- 34 files thay đổi, ~2174 dòng insert, ~28 dòng xóa.
- Phạm vi: `nowing_backend/app/proprietary/platforms/cafef/`, `app/capabilities/cafef/`, billing/config, MCP server, tests, routes, và BMAD artifacts.

## Kiểm thử đã chạy

```bash
cd nowing_backend
ruff check app/capabilities/cafef app/proprietary/platforms/cafef \
  app/capabilities/core/billing.py app/capabilities/core/types.py \
  app/config/__init__.py app/routes/__init__.py \
  tests/unit/platforms/cafef tests/integration/cafef tests/unit/capabilities/cafef
# → All checks passed

uv run pytest tests/unit/platforms/cafef tests/unit/capabilities/cafef tests/integration/cafef -q
# → 29 passed, 12 warnings in 21.16s

cd ../nowing_mcp
uv run python -m mcp_server.selfcheck
# → selfcheck OK: 53 tools registered and well-formed
```

## Live probe (thủ công, cùng mạng với dev box)

| Endpoint | HTTP | Ghi chú |
|---|---|---|
| `https://apiweb.cafef.vn/api/v1/Stock/Quote?symbol=VCB` | **404** | Hardcoded trong `fetch.py:25` |
| `https://apiweb.cafef.vn/api/v1/News/Search?symbol=VCB&pageSize=5` | **404** | Hardcoded trong `fetch.py:26` |
| `https://apiweb.cafef.vn/api/v2/BCTC/GetReportCDKT?symbol=VCB&...` | **200** | Dữ liệu BCTC đúng cấu trúc `templace`/`data` |
| `https://apiweb.cafef.vn/api/v1/BCTC/GetReportDetail?symbol=VCB&...` | **200** | KQKD dạng flat |
| `https://apiweb.cafef.vn/api/v1/BCTC/GetReportLCTT?symbol=VCB&...` | **200** | LCTT dạng nhóm |

Probe cho thấy: **chỉ có báo cáo tài chính (BCTC) thực sự kết nối được với CafeF live**; quote và news endpoints hiện tại không tồn tại.

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|---|---|---|
| AC-1 — Quote/OHLCV/ratios | **Cần sửa** | Demo trả về dữ liệu tổng hợp; endpoint live hardcoded trả `404`. |
| AC-2 — Financial statements | **Đạt** | 3 endpoint BCTC hoạt động, parser xử lý đúng cả dạng flat và nhóm. |
| AC-3 — Market news in search | **Cần sửa** | Demo trả fake news; endpoint live trả `404`; indexing news hoạt động. |
| AC-4 — Rate limit 20 req/min | **Hầu hết** | Throttle process-local đúng; chưa retry 429, chưa phân tán giữa các worker. |

## Findings (theo lớp review)

### [must-fix]

#### M1. Endpoint quote và news live trả về 404 — không thực sự tích hợp CafeF cho 2/3 nguồn dữ liệu

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/fetch.py:25-26`
- **Mô tả:** `_QUOTE_URL` và `_NEWS_URL` hardcoded hai endpoint không tồn tại (`/api/v1/Stock/Quote` và `/api/v1/News/Search`). Khi `CAFEF_DEMO_MODE=false`, cả hai gọi đều trả `404` và capability bị degrade. Story yêu cầu giá cổ phiếu, OHLCV, key ratios và tin tức thị trường từ CafeF; hiện tại chỉ có BCTC là live.
- **Bằng chứng:** `curl` manual ở bảng trên → 404 cho cả quote và news; `GET .../v2/BCTC/GetReportCDKT` → 200.
- **Đề xuất sửa:**
  1. Tìm đúng endpoint quote/news của CafeF (có thể là HTML scrape từ `https://s.cafef.vn/hose/{symbol}.chn` hoặc `https://cafef.vn/...`), hoặc
  2. Dùng `trafilatura`/`firecrawl` scrape fallback cho quote/news nếu API không ổn định, hoặc
  3. Thừa nhận phạm vi V1 chỉ là BCTC và đổi tên/AC cho rõ ràng.

#### M2. Parser không kiểm tra `isSuccess: false` — có thể tính phí cho dữ liệu rỗng

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/parsers.py:116-166` (`parse_financials`), `parsers.py:169-206` (`parse_quote`)
- **Mô tả:** API CafeF trả về `{"isSuccess": false, "value": ..., "errors": [...]}`. Hiện tại `parse_quote` chỉ unwrap khi `isSuccess` truthy (`raw.get("isSuccess") and "value" in raw`), nhưng nếu `isSuccess: false` thì nó **không raise** mà trả về `CafeFQuote` với tất cả field `None`. `scrape_cafef` kiểm tra `quote is None` (`scraper.py:98-101`), do đó model rỗng vẫn được coi là thành công, `degraded=False`, `billable_units=1`, và người dùng bị tính phí. Tương tự `parse_financials` luôn lấy `value` mà không kiểm tra `isSuccess`.
- **Bằng chứng:** Real probe trả `{"isSuccess":true,"value":{...}}`; nếu ticker không tồn tại API có thể trả `isSuccess:false` hoặc `value` rỗng.
- **Đề xuất sửa:**
  ```python
  if isinstance(raw, dict) and raw.get("isSuccess") is False:
      raise CafeFDecodeError(f"CafeF API error: {raw.get('errors')}")
  ```
  Tương tự cho `parse_financials` với mỗi `balance_sheet/income_statement/cash_flow`.

### [should-fix]

#### S1. `_do_get` thiếu headers, không follow redirects, không phân biệt Cloudflare challenge

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/fetch.py:208-231`
- **Mô tả:** Client `httpx.AsyncClient` mặc định `follow_redirects=False`, không set `User-Agent`, `Accept: application/json`, hay `Referer`. WAF/Cloudflare thường chặn request thiếu header hoặc trả 302/303 redirect đến challenge. Hiện tại 302 sẽ bị coi là `CafeFAccessBlockedError` (vì `status_code != 200`), và HTML challenge 200 sẽ bị `JSONDecodeError` → `decode_error`, không phải `access_blocked`.
- **Đề xuất sửa:**
  ```python
  headers = {
      "User-Agent": "Mozilla/5.0 (compatible; Nowing/1.0)",
      "Accept": "application/json",
      "Referer": "https://cafef.vn/",
  }
  async with httpx.AsyncClient(timeout=_timeout(), headers=headers, follow_redirects=True) as client:
      ...
  ```
  Và kiểm tra `content-type` trước `resp.json()`.

#### S2. Rate throttling không retry khi gặp 429 và chỉ ở process-local

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/fetch.py:55-69` (`_throttle`), `fetch.py:219-222` (`_do_get`)
- **Mô tả:** `_throttle` dùng global lock + `time.perf_counter` để đảm bảo interval giữa các request trong cùng process. Tuy nhiên khi gặp `429`, code raise `CafeFRateLimitedError` ngay lập tức mà không backoff/retry. Với multi-worker (nhiều process uvicorn/celery), mỗi process có `_last_request_at` riêng, tổng rate toàn hệ thống có thể vượt giới hạn. Ngoài ra `fetch_financials` gather 3 request đồng thời, nhưng do lock nên thực chất bị serialize, mất ~6s ở default 20 req/min.
- **Đề xuất sửa:** Thêm `asyncio.sleep(backoff)` và retry 1-2 lần khi 429; cân nhắc thay token bucket hoặc redis-based rate limiter khi chạy multi-worker.

#### S3. `fetch_news` không tôn trọng `max_news=0` và `parse_news` không truncate

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/fetch.py:82-85` (`_news_url`), `fetch.py:276-282` (`fetch_news`), `parsers.py:226-247` (`parse_news`)
- **Mô tả:** `_news_url` dùng `max(max_news, 1)`, nên `max_news=0` vẫn gọi API với `pageSize=1`. `parse_news` cũng không cắt danh sách về `max_news`. Với `ScrapeInput.max_news` có `le=50`, nhưng `CafeFScrapeInput` ở platform không có `le=50` (`schemas.py:97`), nên nếu ai đó gọi `scrape_cafef` trực tiếp có thể yêu cầu số lượng lớn.
- **Đề xuất sửa:**
  - Để `_news_url` cho phép `pageSize=0` hoặc `fetch_news` early return khi `max_news<=0`.
  - Thêm `max_news` validation `le=50` vào `CafeFScrapeInput`.
  - `parse_news` cắt kết quả về `max_news`.

#### S4. `_build_name_map` bỏ sót code xuất hiện trong `data` nhưng không có trong `templace`

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/parsers.py:47-70`, `parsers.py:139-151`
- **Mô tả:** `parse_financials` chỉ lặp `for code in sorted(name_map)`, tức chỉ các code có trong `templace`. Nếu API trả thêm một dòng trong `data` mà `templace` thiếu (ví dụ data mới, lỗi biên tập), dòng đó bị loại. Với real probe, tất cả code đều nằm trong `templace`, nhưng đây là điểm yếu parse.
- **Đề xuất sửa:** Merge `name_map` với các code thực sự xuất hiện trong `by_period`, đặt `name` mặc định là code hoặc chuỗi rỗng.

#### S5. `scraper.py` catch `Exception` rộng, nuốt traceback và lý do gốc

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/scraper.py:59-62`, `75-78`, `93-96`
- **Mô tả:** Các khối `except (CafeFAccessBlockedError, Exception)` log warning nhưng không đính kèm `exc_info`, traceback mất. Điều này khiến debug production khó khăn. Ngoài ra `Exception` quá rộng, có thể nuốt lỗi lập trình.
- **Đề xuất sửa:** Dùng `logger.warning("...", exc_info=exc)` hoặc `logger.exception` cho các lỗi không mong muốn; tách các exception cụ thể hơn.

### [watch]

#### W1. Demo mode mặc định `CAFEF_DEMO_MODE=true` vẫn có thể bị tính phí

- **File/lines:** `nowing_backend/app/config/__init__.py:1007`, `nowing_backend/app/proprietary/platforms/cafef/fetch.py:236-237`
- **Mô tả:** Nếu `CAFEF_DEMO_MODE` không được set (default `true`), capability trả về synthetic data và vẫn báo `billable_units=1` khi `degraded=False`. Nếu `PLATFORM_SCRAPE_BILLING_ENABLED=true`, người dùng bị tính phí cho dữ liệu giả lập. Đây là trade-off "demo ổn định", nhưng nên ghi log rõ hoặc để demo mode tự động `cost_micros=0`.

#### W2. `key_metrics` của báo cáo tài chính luôn rỗng

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/parsers.py:153-156`
- **Mô tả:** `CafeFFinancialReport.key_metrics` luôn được đặt `{}`. Real CafeF response có thể trích các chỉ tiêu quan trọng (tổng tài sản, doanh thu, lợi nhuận sau thuế, lưu chuyển tiền HĐKD) từ `templace`/`data`. Việc để trống làm giảm giá trị cho agent phân tích.
- **Đề xuất sửa:** Tính `key_metrics` từ các code chuẩn (`270`, `10`, `60`, `HDKD_20`, `HDTC_42`, …) như tham chiếu `lmdat/cafef-financial-mcp`.

#### W3. `CafeFQuote` fallback key chọn giá trị `None` thay vì key khác có dữ liệu

- **File/lines:** `nowing_backend/app/proprietary/platforms/cafef/parsers.py:178-206`
- **Mô tả:** Hàm `_get(*keys)` trả về key đầu tiên **tồn tại** trong dict, bất kể giá trị có là `None` hay không. Ví dụ nếu `raw` có `current_price=None` và `price=95.2`, parser trả `current_price=None`. Có thể làm mất dữ liệu hợp lệ.
- **Đề xuất sửa:** Duyệt các key và chọn giá trị đầu tiên **không `None`**.

### [non-issue]

- **N1.** `nowing_mcp/mcp_server/features/scrapers/platforms/cafef.py` import path `....core.client` hơi dài nhưng nhất quán với pattern của các platform khác.
- **N2.** `app/routes/__init__.py` import `app.capabilities.cafef` đúng thứ tự alphabet giữa `batdongsan` và `chainlens`.
- **N3.** `md5` dùng cho `unique_id` fallback là yếu về mặt lý thuyết nhưng đủ duy nhất trong phạm vi `symbol:title`; không cần SHA-256 ở đây.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|---|---|---|
| must-fix | 2 | M1, M2 |
| should-fix | 5 | S1-S5 |
| watch | 3 | W1-W3 |
| non-issue | 3 | N1-N3 |

## Hành động tiếp theo

1. Dev agent xử lý **M1** (tìm endpoint quote/news live hoặc điều chỉnh phạm vi/AC) và **M2** (validate `isSuccess: false`) trước khi merge.
2. Sau đó xử lý **S1** (headers/redirect/cloudflare) và **S2** (retry/backoff 429) để tăng độ ổn định live.
3. Re-run **4.8 `bmad-code-review`** sau khi sửa.
4. Tiếp tục pipeline:
   - **4.10 `bmad-nowing-mutation-gate`** (P0-gated, khuyến nghị)
   - **4.13 `bmad-nowing-human-review-gate`** (P0-gated, khuyến nghị)
   - **4.17 `bmad-retrospective`** (optional, khi epic kết thúc)
