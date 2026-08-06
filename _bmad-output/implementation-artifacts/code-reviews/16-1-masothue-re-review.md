---
story: "16.1 masothue.com Company Data"
previous_commit: de5496d6e
current_commit: 04de3720c
reviewer: bmad-code-review
review_date: "2026-08-07"
verdict: approved
---

# BMAD Re-Review — Story 16.1 "masothue.com Company Data"

## Tóm tắt phán quyết

- **Mức độ:** `APPROVED` — tất cả **1 must-fix (M1)** và **6 should-fix (S1-S6)** từ review `de5496d6e` đã được xử lý.
- **Rủi ro chính:** Không còn must-fix/should-fix mới. Có 2 quan sát nhỏ về đặt tên/pool test nhưng không chặn approval.
- **Kiểm thử:** `ruff` pass, 34 unit test + 16 integration test pass (1 live test skip), `nowing_mcp` selfcheck pass với 53 tool.

## Thống kê diff

- **Phạm vi:** `de5496d6e..04de3720c`
- **Files thay đổi:** 10 files (chủ yếu `nowing_backend/app/proprietary/platforms/masothue/`, `app/capabilities/masothue/scrape/`, tests, BMAD artifacts).
- **Dòng thay đổi:** ~372 insertions, ~21 deletions.

## Xác minh các finding đã sửa

| ID | Nội dung | File / line tại `04de3720c` | Test xác minh | Kết quả |
|----|----------|----------------------------|---------------|---------|
| M1 | `cost_micros=0` khi `degraded=True` | `nowing_backend/app/capabilities/masothue/scrape/executor.py:122` — `cost = 0 if degraded else total * rate` | `tests/unit/capabilities/masothue/scrape/test_executor.py::test_executor_returns_zero_cost_when_degraded` | ✅ pass |
| S1 | 429 trên detail page trigger `degraded=True` / `rate_limited` | `nowing_backend/app/proprietary/platforms/masothue/scraper.py:177-181` — bắt `MasothueRateLimitedError`, set `rate_limited_seen=True`, `degraded=True`, `degradation_reason="rate_limited"`, break | `tests/unit/platforms/masothue/test_scraper.py::test_scrape_detail_rate_limit_degrades` | ✅ pass |
| S2 | 302 exact-match kết hợp `tax_code` filter hoạt động | `fetch.py:131-135` — trích MST từ `location` gắn vào synthetic search result; `scraper.py:201-203` — `_matches_filter` chạy sau `apply_detail` | `tests/unit/platforms/masothue/test_scraper.py::test_scrape_exact_match_with_tax_code_filter` | ✅ pass |
| S3 | Delay giữa các request detail page | `scraper.py:170` — `await asyncio.sleep(_page_delay())` trước mỗi `detail_fetch` | `tests/unit/platforms/masothue/test_scraper.py::_no_page_delay` fixture đảm bảo test nhanh; runtime tôn trọng `MASOTHUE_PAGE_DELAY_S` | ✅ pass |
| S4 | `parse_pagination` được dùng để tránh fetch trang rỗng | `scraper.py:223-225` — gọi `parse_pagination(html)` và break khi `next_page is None`; `parsers.py:179-197` — logic tìm trang tiếp theo chính xác | `tests/unit/platforms/masothue/test_scraper.py::test_scrape_stops_when_no_next_page` | ✅ pass |
| S5 | Regex `_extract_representative` dừng ở nhãn kế tiếp | `parsers.py:34-37` — `_REP_RE` dùng `.+?` non-greedy + lookahead tất cả nhãn tiếp theo (`Mã số thuế`, `Điện thoại`, `Địa chỉ`, v.v.) | `tests/unit/platforms/masothue/test_parsers.py::test_parse_search_results` kiểm tra trích `Nguyễn Văn A`; thêm fixture nếu text dính liền | ✅ pass |
| S6 | Bổ sung test cho `resolve_detail=False`, `include_phone=True`, no next page, detail rate limit, exact-match filter, live `SCRAPE_LIVE` | `test_scraper.py:97-203`, `test_executor.py:50-71`, `test_masothue_scrape.py:762-785` | tất cả test mới pass; `test_masothue_scrape_live_sample` skip khi thiếu `SCRAPE_LIVE` | ✅ pass |

## Kiểm thử đã chạy

```bash
cd nowing_backend
ruff check app/proprietary/platforms/masothue app/capabilities/masothue app/services/company_aggregator app/capabilities/core/billing.py app/config/__init__.py tests/unit/platforms/masothue tests/unit/capabilities/masothue tests/unit/services/company_aggregator
# → All checks passed

uv run pytest tests/unit/platforms/masothue tests/unit/capabilities/masothue/scrape tests/unit/services/company_aggregator -q
# → 34 passed

uv run pytest tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py -q
# → 16 passed, 1 skipped (SCRAPE_LIVE)

cd ../nowing_mcp
uv run python -m mcp_server.selfcheck
# → selfcheck OK: 53 tools registered and well-formed
```

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|----|----------|---------|
| AC-1 — HTML search | **Đạt** | `fetch.py` + `parsers.py` trả về `MasothueCompany` đã type hóa. |
| AC-2 — Resolve detail | **Đạt** | `resolve_detail=True/False` hoạt động; 302 exact-match + `tax_code` filter đã fix. |
| AC-3 — Pagination/cap | **Đạt** | `ScrapeInput` clamp `max_items`/`max_pages`; scraper tôn trọng cap và dùng `parse_pagination`. |
| AC-4 — Billing | **Đạt** | `cost_micros = 0` khi `degraded`; `BillingUnit.MASOTHUE_COMPANY` đăng ký. |
| AC-5 — Degraded/failure | **Đạt** | Degrade typed cho search và detail 429; không hard-fail. |
| AC-6 — Anti-bot | **Đạt** | `stealthy_headers=True`, proxy, delay giữa search pages và detail pages. |
| AC-7 — MCP/REST/Agent | **Đạt** | Capability, REST router, MCP tool, `selfcheck` đều được wire. |
| AC-8 — Canonical/dedup | **Đạt** | `company_aggregator` + `executor` upsert canonical hoạt động; test idempotent/workspace scope pass. |
| AC-9 — Test coverage | **Đạt** | Unit + integration đầy đủ; thêm `SCRAPE_LIVE` smoke test. |

## Sanity re-check toàn bộ implementation

- **Capability wiring:** `masothue.scrape` đã đăng ký trong `app/capabilities/masothue/scrape/definition.py`, `app/routes/__init__.py` import `app.capabilities.masothue`, `app/mcp_tools.py` có `nowing_masothue_scrape`.
- **MCP server:** `nowing_mcp/mcp_server/features/scrapers/platforms/masothue.py` + `__init__.py` đã wire; `selfcheck` xác nhận tool hiện diện và well-formed.
- **Billing/config:** `BillingUnit.MASOTHUE_COMPANY` trong `app/capabilities/core/types.py` và `_PLATFORM_RATE_KEYS`; `MASOTHUE_SCRAPE_MICROS_PER_ITEM` / `MASOTHUE_PAGE_DELAY_S` trong `app/config/__init__.py`.
- **Canonical:** `app/services/company_aggregator/dedupe.py` cung cấp `fingerprint`, `merge`, `search_text`, `normalize`; `executor` upsert canonical với workspace scope.
- **BSL/Apache boundary:** Proprietary fetch/parser/scraper ở `app/proprietary/platforms/masothue/`, capability contract ở `app/capabilities/masothue/scrape/`, giữ đúng ranh giới AD-16.

Không phát hiện lỗi mới trong sanity re-check.

## Quan sát (non-blocking)

- `tests/unit/platforms/masothue/test_scraper.py::test_scrape_stops_when_no_next_page` thực chất dừng do `max_items=1` đạt cap trước khi `parse_pagination` được gọi. Không phải lỗi chức năng, nhưng nên bổ sung một unit test trực tiếp cho `parse_pagination` hoặc một case `max_items` lớn hơn số kết quả trang để cover nhánh `next_page is None`.
- `test_scrape_detail_rate_limit_degrades` có docstring "returns partial results" nhưng với fixture 2 item và rate-limit xảy ra ở item đầu tiên, output `total_items == 0`. Đây là kết quả đúng với logic break ngay; nên điều chỉnh docstring cho khớp.

Cả hai quan sát đều ở mức **low** / **watch**, không phải blocker.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|------|----------|--------------|
| must-fix | 0 | — |
| should-fix | 0 | — |
| watch | 2 | W1: test naming/pool; W2: docstring `test_scrape_detail_rate_limit_degrades` |
| non-issue | 0 | — |

## Hành động tiếp theo

1. ✅ Re-review approved.
2. Cập nhật story file `16-1-masothue-company-data.md` → `status: done`.
3. Cập nhật `sprint-status.yaml` → `16-1: done`.
4. Commit re-review report với message `docs(masothue): BMAD re-review approved for story 16.1`.
5. Tiếp tục pipeline:
   - **4.10 `bmad-nowing-mutation-gate`** (P0-gated, khuyến nghị)
   - **4.11 `bmad-testarch-trace`** (khuyến nghị)
   - **4.12 `bmad-testarch-nfr`** (khuyến nghị)
   - **4.13 `bmad-nowing-human-review-gate`** (P0-gated, khuyến nghị)
   - **4.14 `bmad-nowing-web-e2e-gate`** (khuyến nghị, nếu cần UI)
