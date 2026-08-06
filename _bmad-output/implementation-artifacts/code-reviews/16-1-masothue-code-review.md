---
story: "16.1 masothue.com Company Data"
reviewed_commit: de5496d6e
parent_commit: 2d3eac9e8
reviewer: bmad-code-review
review_date: "2026-08-07"
verdict: changes_requested
---

# BMAD Code Review — Story 16.1 "masothue.com Company Data"

## Tóm tắt phán quyết

- **Mức độ:** `CHANGES_REQUESTED` — còn **1 must-fix**, **6 should-fix**, **3 watch**, **4 non-issue**.
- **Rủi ro chính:** `cost_micros` trong response không nhất quán khi run bị `degraded`; anti-bot chưa áp `MASOTHUE_PAGE_DELAY_S` giữa các request detail page; một số edge-case (302 exact-match kết hợp `tax_code` filter, 429 trên detail page) chưa xử lý đúng.
- **Kiểm thử:** 28 unit test + 15 integration test liên quan đều pass; `ruff` pass trên các file thay đổi; `nowing_mcp` selfcheck pass với 53 tool.

## Thống kê diff

- 33 files thay đổi, ~1796 dòng insert, ~37 dòng xóa.
- Phạm vi: `nowing_backend/app/proprietary/platforms/masothue/`, `app/capabilities/masothue/`, `app/services/company_aggregator/`, billing/config, MCP server, tests, và BMAD artifacts.

## Kiểm thử đã chạy

```bash
cd nowing_backend
ruff check app/proprietary/platforms/masothue app/capabilities/masothue app/services/company_aggregator app/capabilities/core/billing.py app/config/__init__.py tests/unit/platforms/masothue tests/unit/capabilities/masothue tests/unit/services/company_aggregator
# → All checks passed

python -m pytest tests/unit/platforms/masothue tests/unit/capabilities/masothue/scrape tests/unit/services/company_aggregator -q
# → 28 passed

python -m pytest tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py -q
# → 15 passed

cd ../nowing_mcp
python -m mcp_server.selfcheck
# → selfcheck OK: 53 tools registered and well-formed
```

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|----|----------|---------|
| AC-1 — HTML search | **Đạt** | `fetch.py` + `parsers.py` + `scraper.py` trả về `MasothueCompany` đã type hóa. |
| AC-2 — Resolve detail | **Hầu hết** | `resolve_detail=True` hoạt động; chưa có unit test `resolve_detail=False`; edge 302 exact-match + `tax_code` filter có lỗi. |
| AC-3 — Pagination/cap | **Đạt** | `ScrapeInput` clamp `max_items`/`max_pages`; scraper tôn trọng cap. |
| AC-4 — Billing | **Cần sửa** | `BillingUnit.MASOTHUE_COMPANY` đã đăng ký; executor tính `cost_micros` không về 0 khi `degraded`, gây mâu thuẫn với `charge_capability`/`Run.cost_micros`. |
| AC-5 — Degraded/failure | **Cần sửa** | Degrade typed/retry cho search page đúng; 429 trên detail page bị xử lý như lỗi item thay vì `degraded`. |
| AC-6 — Anti-bot | **Cần cải thiện** | `stealthy_headers=True`, proxy, delay giữa các search page đúng; thiếu delay giữa các request detail page. |
| AC-7 — MCP/REST/Agent | **Đạt** | Capability, REST router, MCP tool, `mcp_tools.py`, `selfcheck` đều được wire. |
| AC-8 — Canonical/dedup | **Đạt** | `company_aggregator` + `executor` upsert canonical hoạt động; test idempotent/workspace scope pass. |
| AC-9 — Test coverage | **Hầu hết** | Unit + Pattern-6 SQL integration đầy đủ; thiếu test `resolve_detail=False`, `include_phone=True`, và integration live `SCRAPE_LIVE`. |

## Findings (theo lớp review)

### [must-fix]

#### M1. `cost_micros` không zero khi run bị degraded
- **File/lines:** `nowing_backend/app/capabilities/masothue/scrape/executor.py:120-121` và `156-161`
- **Mô tả:** Executor tính `cost = total * rate` sau khi `degraded=True`, rồi trả về `ScrapeOutput(cost_micros=cost, degraded=True)`. Trong khi đó `rest.py` gọi `charge_capability(output, ...)` — `_charge_platform_meter` thấy `degraded=True` nên charge **0** và ghi `Run.cost_micros=0`. Người dùng nhận response có `cost_micros > 0` trong khi ví không bị trừ và Run ghi 0, gây mâu thuẫn billing/UX.
- **Bằng chứng:** `batdongsan.scrape` executor đã xử lý `cost = 0 if degraded else total * rate` (so sánh pattern tại `app/capabilities/batdongsan/scrape/executor.py:105-108`).
- **Đề xuất sửa:**
  ```python
  rate = getattr(config, "MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000)
  cost = 0 if degraded else total * rate
  ```

### [should-fix]

#### S1. Detail page bị 429 không trigger degraded/rate_limited
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/scraper.py:178-195`
- **Mô tả:** `fetch_detail_page` raise `MasothueRateLimitedError` khi gặp 429. Scraper bắt `(MasothueAccessBlockedError, MasothueTimeoutError)` và `MasothueDecodeError`, nhưng `MasothueRateLimitedError` rơi xuống `except Exception` và `continue`, bỏ qua item. 429 là tín hiệu rate-limit toàn cục, nên nên đặt `degraded=True`, `degradation_reason="rate_limited"` và dừng hoặc retry giống search page.
- **Đề xuất sửa:** Thêm `except MasothueRateLimitedError` trong khối detail, set `rate_limited_seen=True` hoặc `degraded=True` và break.

#### S2. 302 exact-match redirect kết hợp `tax_code` filter trả về empty sai
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/fetch.py:131-133` + `scraper.py:166-167,198-199`
- **Mô tả:** Khi server trả 302 redirect đến detail page, `fetch_search_page` tạo HTML tổng hợp với `<p>Mã số thuế: </p>` (không có mã). Parser tạo company có `tax_code=None`. Nếu `input.tax_code` được set, `_matches_filter` **trước** `apply_detail` sẽ `continue`, bỏ qua kết quả duy nhất. Run kết thúc với `degraded=True`, `degradation_reason="empty"` sai.
- **Đề xuất sửa:** Di chuyển `_matches_filter` xuống **sau** `apply_detail`, hoặc parse MST từ `location` path `<mst>-<slug>` trong synthetic result.

#### S3. Không có delay giữa các request detail page
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/scraper.py:170-184`
- **Mô tả:** `MASOTHUE_PAGE_DELAY_S` chỉ được `await asyncio.sleep` giữa các search page (`scraper.py:213-214`). Khi `resolve_detail=True`, vòng lặp detail có thể gọi liên tiếp nhiều request mà không có pacing, vi phạm AC-6 chống rate-limit/Cloudflare.
- **Đề xuất sửa:** Thêm `await asyncio.sleep(_page_delay())` trong vòng lặp resolve detail (ví dụ sau mỗi `detail_fetch`).

#### S4. `parse_pagination` không được dùng, scraper vẫn fetch trang rỗng
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/parsers.py:176-198` + `scraper.py`
- **Mô tả:** `parse_pagination` được implement/test nhưng `scraper.py` không gọi; nó chỉ break khi `page_items` rỗng. Với `max_pages` lớn hơn số trang thực, scraper fetch thêm một trang trống rồi mới break, tốn request và tăng rủi ro bị chặn.
- **Đề xuất sửa:** Gọi `parse_pagination(html)` để lấy `next_page` và break khi `next_page is None`.

#### S5. Regex trích `legal_representative` có thể lấn sang trường kế tiếp
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/parsers.py:109-115`
- **Mô tả:** `_REP_RE = re.compile(r"Người\s+đại\s+diện[:\s]*([^\n]+)", re.IGNORECASE)`. Nếu text kết quả tìm kiếm có các trường nằm trên cùng một dòng (ví dụ `Người đại diện: A Điện thoại: 028...`), regex lấy cả phần `Điện thoại...`.
- **Đề xuất sửa:** Giới hạn match đến trước từ khóa nhãn tiếp theo (`Mã số thuế`, `Điện thoại`, v.v.) hoặc tách theo `<br/>`.

#### S6. Thiếu unit/integration test cho một số nhánh
- **File/lines:** `tests/unit/platforms/masothue/test_scraper.py`, `tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py`
- **Mô tả:** Không có test cho `resolve_detail=False`, `include_phone=True` end-to-end, pagination cap khi `max_pages` lớn hơn thực tế, và integration test live với `SCRAPE_LIVE`/`pytest.mark.live` theo AC-9.
- **Đề xuất sửa:** Bổ sung test cases.

### [watch]

#### W1. `fetch_ajax_token`/`fetch_ajax_search` và `fetch_all_pages` chưa được dùng
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/fetch.py:182-290`
- **Mô tả:** Các hàm AJAX token/search và `fetch_all_pages` được implement nhưng `scraper.py` không gọi. Story ghi V1 dùng GET HTML primary, AJAX là fallback, nhưng fallback chưa được wire. Có thể là dead code hoặc dự trữ V2.

#### W2. Canonical upsert lỗi per-item vẫn tính phí và trả về item
- **File/lines:** `nowing_backend/app/capabilities/masothue/scrape/executor.py:124-147`
- **Mô tả:** Nếu `upsert_canonical_entity` raise (DB/network) cho một item, exception bị bắt, log, tiếp tục. Item vẫn nằm trong output và billing tính phí, mặc dù dữ liệu không được lưu canonical. Đây là trade-off fail-open; cân nhắc degrade hoặc loại item khỏi output nếu upsert thất bại.

#### W3. `_extract_tax_code` regex không xử lý khoảng trắng trong MST ở search result
- **File/lines:** `nowing_backend/app/proprietary/platforms/masothue/parsers.py:99-107`
- **Mô tả:** Regex `[\d\-]{10,}` không match MST có khoảng trắng (ví dụ `031 4539 064`). Khi đó `_matches_filter` trước detail sẽ bỏ qua item nếu `tax_code` filter được set. Detail page thường có MST không khoảng trắng, nên mức độ nghiêm trọng thấp.

### [non-issue]

- **N1.** `nowing_backend/app/mcp_tools.py` insertion của `nowing_masothue_scrape` không theo thứ tự alphabet — file đã không fully sorted; không ảnh hưởng runtime.
- **N2.** `nowing_web/app/(home)/mcp-server/page.tsx` chưa liệt kê `nowing_masothue_scrape` — đây là marketing page optional, nhiều scraper khác cũng không có mặt.
- **N3.** `parsers.py` có key `"loại hình doanh nghiệm"` (typo) nhưng bản đúng `"loại hình doanh nghiệp"` cũng có trong `_DETAIL_LABEL_MAP`, không ảnh hưởng parse.
- **N4.** `import json` local trong `fetch.py` — phong cách, không lỗi.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|------|----------|--------------|
| must-fix | 1 | M1 |
| should-fix | 6 | S1-S6 |
| watch | 3 | W1-W3 |
| non-issue | 4 | N1-N4 |

## Hành động tiếp theo

1. Dev agent thực hiện **M1** (1 dòng) và các **S1-S3** (quan trọng cho AC-5/AC-6/anti-bot) trước.
2. Re-run **4.8 `bmad-code-review`** sau khi sửa.
3. Sau khi review approved, tiếp tục pipeline:
   - **4.10 `bmad-nowing-mutation-gate`** (P0-gated, khuyến nghị)
   - **4.13 `bmad-nowing-human-review-gate`** (P0-gated, khuyến nghị)
   - **4.17 `bmad-retrospective`** (optional, khi epic kết thúc)
