# BMAD Code Review Report — Story 10.1: Batdongsan.com.vn Scraper (v2)

**Review date:** 2026-08-03
**Story file:** `_bmad-output/implementation-artifacts/10-1-batdongsan-scraper.md`
**ATDD checklist:** `_bmad-output/test-artifacts/atdd-checklist-10-1-batdongsan-scraper.md`
**Previous review:** `_bmad-output/implementation-artifacts/bmad-code-review-10-1-report-2026-08-03.md`
**Diff artifact (v2):** `_bmad-output/implementation-artifacts/bmad-cr-10-1-diff-v2.md`
**Baseline commit:** `0eba86e9ed66527e2f0bfe661a19c7fc1c4e4ed2` (develop)
**Review mode:** full re-review

---

## 1. Executive Summary

| Item | Value |
|---|---|
| Files changed (vs baseline) | 12 files, +2.516 insertions (diff v2) |
| Untracked new file | `nowing_backend/app/proprietary/platforms/batdongsan/city_codes.py` |
| `ruff check` (targeted) | All checks passed |
| `pytest tests/unit/platforms/batdongsan -q` | 42 passed |
| `pytest tests/unit/capabilities/batdongsan -q` | 41 passed |
| `pytest tests/integration/capabilities/batdongsan -q` | 2 passed, 1 skipped (live test) |
| `pnpm tsc --noEmit` (nowing_web) | OK |
| `pnpm exec biome check ... page.tsx ...api.service.ts` | OK |
| **Verdict** | **CHANGES REQUESTED** |

Tổng quan: 4 `patch` và 2 `decision-needed` từ review v1 đã được xử lý ở backend. Core pipeline (decode, parser, pagination, billing, capability wiring, tests) vững. Tuy nhiên review v2 phát hiện **một finding mới P-5**: MCP tool `nowing_batdongsan_scrape` chưa đồng bộ với `ScrapeInput` — vẫn dùng `ge=1` cho `max_items`/`max_pages` và thiếu `resolve_phones`, khiến AC-6 chưa parity trên MCP. F-1 (cross-platform billing) vẫn được `defer`. Cần patch P-5 trước khi coi story xong.

---

## 2. AC / ATDD Coverage Summary

| AC | Status | Notes |
|---|---|---|
| AC-1 Mobile API + typed listing | Pass | `fetch_listings` gọi `p_sync`, parser trả `BatdongsanListing` đúng fields; `resolve_detail_urls` cung cấp `detail_url` khi mobile thiếu. |
| AC-2 Decode pipeline | Pass | `gzip → base64 → nibble-swap → Latin-1 → JSON` đúng thứ tự; test fixture roundtrip + edge cases pass. |
| AC-3 Pagination & limits | Pass | `max_items`/`max_pages` dùng `ge=0` + clamp over-cap; dừng đúng khi `m=None`; dedupe `listing_id`. |
| AC-4 Billing | Pass | `BATDONGSAN_ITEM`, rate 3500 micros, `billable_units` trên cả hai output model; integration billing pass. |
| AC-5 Degraded mode | Pass | `degraded` + `degradation_reason` typed, retry 403/429, không hard-fail. |
| AC-6 MCP/REST/Agent exposure | Partial | Capability, REST route, agent subagent, MCP catalog OK. MCP tool `nowing_batdongsan_scrape` chưa expose `resolve_phones` và vẫn `ge=1` cho `max_items`/`max_pages` → xem P-5. |
| AC-7 Test coverage | Pass | 83 unit tests + 2 integration recorded pass, 1 live test skip. |
| AC-8 Phone unmask | Pass | `resolve_phones` truyền xuống, `_extract_phone_from_xhr` parse JSON/text và log `USER_NO_PERMISSION`, concurrency 5, timeout 45s. |
| AC-9 Cookie capture & pre-warm | Pass | Capture script, admin UI, `cookie_string_to_playwright` domain, `_should_prewarm` + `_make_page_setup` trong `fetch_detail_phone`. |

---

## 3. Findings (triage)

### 3.1 `decision_needed`

Không còn `decision-needed` mở. D-1 và D-2 đã giải quyết.

### 3.2 `patch`

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| P-1 | Acceptance Auditor | high | resolved | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:104-125`<br>`fetch.py:128-138`<br>`fetch.py:141-159`<br>`fetch.py:476` | Pre-warm session (AC-9) | Đã thêm `_should_prewarm`, `_prewarm_batdongsan_session`, `_make_page_setup`; `fetch_detail_phone` dùng `page_setup=_make_page_setup(credentials)`. Kiểm soát `con.ses.id` và `accessToken` expiry < 300s. |
| P-2 | Acceptance Auditor | medium | resolved | `nowing_backend/app/proprietary/platforms/batdongsan/schemas.py:23`<br>`nowing_backend/app/capabilities/batdongsan/scrape/schemas.py:29`<br>`nowing_backend/app/capabilities/batdongsan/scrape/executor.py:70` | `resolve_phones` exposed | Đã thêm `resolve_phones: bool = True` vào cả `BatdongsanScrapeInput` và `ScrapeInput`; executor truyền `payload.resolve_phones` xuống `scrape_batdongsan`. |
| P-3 | Acceptance Auditor + Edge Case Hunter | medium | resolved | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:162-189`<br>`fetch.py:480` | `_extract_phone_from_xhr` parse JSON/text | Parse JSON hoặc text; log warning khi gặp `USER_NO_PERMISSION...`; không coi message đó là số hợp lệ. |
| P-4 | Blind Hunter | low | resolved | `nowing_backend/app/services/scraper_platform_account_service.py:48-87` | Cookie domain legacy | `_parse_cookie_input` nhận `domain` từ `cookie_string_to_playwright` và gán đúng `domain` cho cookie dạng `name=value; ...`. |
| **P-5** | Acceptance Auditor | medium | patch | `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py:60-65`<br>`nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py:28-68` | MCP tool chưa đồng bộ với `ScrapeInput` | `max_pages` và `max_items` vẫn `Field(ge=1, le=...)` (backend `ScrapeInput` đã chuyển sang `ge=0` + clamp); thiếu parameter `resolve_phones`. Kết quả: MCP client không thể gọi `max_items=0`/`max_pages=0` (AC-3 zero-cap, D-1) và không thể tắt phone resolve (AC-8/P-2). Cần cập nhật `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py` để khớp `ScrapeInput` (`ge=0`, thêm `resolve_phones: bool = True`). |

### 3.3 `defer`

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| F-1 | Blind Hunter + Acceptance Auditor | low | resolved | `nowing_backend/app/capabilities/batdongsan/scrape/executor.py:105-122`<br>`nowing_backend/app/capabilities/core/billing.py:187-426` | `ScrapeOutput.cost_micros` = 0 khi `degraded=True` nhưng `charge_capability` vẫn debit theo `billable_units` | Executor đặt `cost=0` khi degraded, nhưng `_charge_platform_meter` charge theo `output.billable_units` nếu > 0. Vẫn là pattern chung với `muaban_bds`/`chotot`; đã ghi trong `deferred-work.md`. |

### 3.4 Dismissed

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| R-1 | Acceptance Auditor | low | dismiss | `nowing_backend/app/proprietary/platforms/batdongsan/scraper.py:198-201` | ATDD vs implementation artifact conflict on empty first page | ATDD mong `degraded=false` khi API trả empty / `district_id` invalid; story AC-5 và code trả `degraded=true` với `degradation_reason="empty"`. Đây là mâu thuẫn tài liệu, không phải lỗi code. |
| R-2 | Blind Hunter | low | dismiss | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:562-580` | `resolve_detail_urls` browser fallback không dùng `_make_page_setup` | Browser fallback trong `resolve_detail_urls` dùng `_stealth_page_setup` thay vì `_make_page_setup`, nên không pre-warm. Đây là best-effort fallback; AC-9 tập trung vào `fetch_detail_phone`. |
| R-3 | Blind Hunter | low | dismiss | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:424-464` | JS phone reveal không click nút `Hiện số` | Code poll `span[raw]/div[raw]` 30 lần × 500ms mà không click. Có thể là hidden assumption nhưng chưa có bằng chứng live rằng button cần click; ghi nhận theo dõi. |

---

## 4. Layer Review Notes

### 4.1 Blind Hunter (security, correctness, hidden assumptions)

- **P-4 resolved**: `cookie_string_to_playwright` giờ truyền `domain` xuống `_parse_cookie_input`; legacy string nhận domain đúng. Không còn hardcode `".batdongsan.com.vn"` bên trong helper.
- **P-1 pre-warm hợp lệ nhưng phạm vi giới hạn**: `_should_prewarm` kiểm tra `accessToken` JWT `exp` và `con.ses.id` `expires`; `_prewarm_batdongsan_session` navigate `/dang-nhap`; `_make_page_setup` gắn vào `fetch_detail_phone`. Tuy nhiên `resolve_detail_urls` khi fallback sang browser vẫn dùng `_stealth_page_setup` (R-2, dismissed) — đây là hidden assumption có thể gây fail nếu session sắp hết hạn, nhưng là đường dự phòng.
- **_extract_phone_from_xhr chắc chắn**: Xử lý cả JSON (`{"phone":"..."}` / `{"message":"USER_NO_PERMISSION..."}`) lẫn text thuần; log rõ ràng. Không coi `USER_NO_PERMISSION...` là số hợp lệ.
- **Concurrency phone fetch**: `scraper.py:231-253` dùng `asyncio.Semaphore(5)` và `asyncio.timeout(45.0)`. `_resolve_phone` chỉ catch `TimeoutError`; may mắn là `fetch_detail_phone` đã bắt toàn bộ `Exception` và trả `(None, None)`, nên `asyncio.gather` không bị cancel. Nếu sau này `fetch_detail_phone` được refactor để raise, `_resolve_phone` nên catch rộng hơn hoặc dùng `asyncio.gather(return_exceptions=True)`.
- **Admin route capture**: `subprocess.Popen` chỉ chạy script có sẵn trong `scripts/`, không shell, superuser-only. Chấp nhận được.
- **Frontend cookie filter**: `page.tsx` strip analytics/ad cookies nhưng vẫn giữ nhiều tracking cookie; không phải blocker bảo mật.

### 4.2 Edge Case Hunter (boundaries, concurrency, timeouts, empty/special inputs)

- **Zero-cap**: `ScrapeInput` / `BatdongsanScrapeInput` dùng `ge=0` + `_clamp_caps` (`max_items > 100 → 100`, `max_pages > 20 → 20`). `scraper.py:108-120` xử lý `max_items=0` / `max_pages=0` trả về empty list, không charge. Test `test_scrape_input_accepts_max_items_at_zero` / `...max_pages_at_zero` pass.
- **City validation**: `field_validator("city")` so sánh với `CITY_CODES` (`frozenset(CITY_SLUGS)`); test `test_scrape_input_rejects_unknown_city` pass.
- **Price/area bounds**: `ScrapeInput._price_and_area_bounds` reject `min_price > max_price` / `min_area > max_area`; test pass. `BatdongsanScrapeInput` không có validator này, nhưng điểm vào canonical là `ScrapeInput`.
- **Decode size cap / gzip bomb**: `_MAX_DECODED_BYTES` 50 MB, test `test_decode_response_raises_decode_error_for_gzip_bomb` pass.
- **Pagination**: dừng đúng khi `m=None`, `max_items`, `max_pages`; dedupe theo `listing_id`; web fallback chỉ khi city-level không filter.
- **Phone timeout**: 45s/call, max 5 concurrent. Tổng thời gian phone resolve vẫn có thể lên đến `(N/5) × 45s` cho N listing; chưa có total timeout toàn bộ phone phase. Không blocker vì N bị `max_items` giới hạn.
- **`resolve_phones=False`**: `scraper.py:224` skip hoàn toàn; `AsyncStealthySession is None` cũng skip. Good.

### 4.3 Acceptance Auditor

- **AC-1**: parser trả đủ fields, mapping `listing_type` → `ptype` 38/49, `city` → API code. `detail_url` từ mobile có thể thiếu; `resolve_detail_urls` / web fallback là best-effort.
- **AC-2**: pipeline chính xác, có test nibble-swap self-inverse.
- **AC-3**: clamp, zero-cap, stop conditions đúng. MCP tool chưa phản ánh zero-cap → P-5.
- **AC-4**: `BATDONGSAN_ITEM` billing unit, rate config, `billable_units` property; integration test real Postgres pass.
- **AC-5**: degradation reasons typed, retry/rotate, không hard-fail.
- **AC-6**: capability, REST, agent wired. MCP tool partial → P-5.
- **AC-7**: tests đầy đủ, tất cả pass.
- **AC-8**: `resolve_phones` expose, XHR DecryptPhone, JSON/text parse, `USER_NO_PERMISSION` log, concurrency cap. MCP không expose `resolve_phones` → P-5.
- **AC-9**: admin UI, capture script, cookie domain, pre-warm present. Web listing fallback chưa pre-warm (R-2 dismissed).

---

## 5. Verification Results

### 5.1 Ruff

```bash
cd nowing_backend
ruff check app/proprietary/platforms/batdongsan app/capabilities/batdongsan/scrape app/services/scraper_platform_account_service.py
ruff check app/proprietary/platforms/batdongsan app/proprietary/platforms/muaban_bds app/services/scraper_platform_account_service.py app/routes/admin_scraper_platform_accounts_routes.py app/capabilities/batdongsan/scrape/executor.py
```

**Result:** `All checks passed!` (cả hai lệnh).

### 5.2 Pytest — unit platforms

```bash
cd nowing_backend
pytest tests/unit/platforms/batdongsan -q
```

**Result:**

```
collected 42 items
...
======================== 42 passed, 7 warnings in 0.29s ========================
```

### 5.3 Pytest — unit capabilities

```bash
cd nowing_backend
pytest tests/unit/capabilities/batdongsan -q
```

**Result:**

```
collected 41 items
...
======================== 41 passed, 7 warnings in 0.30s ========================
```

### 5.4 Pytest — integration (recorded fixture)

```bash
cd nowing_backend
pytest tests/integration/capabilities/batdongsan -q
```

**Result:**

```
collected 3 items
. .s
================== 2 passed, 1 skipped, 12 warnings in 1.93s ===================
```

### 5.5 Frontend typecheck & lint

```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check --max-diagnostics 500 app/admin/scraper-accounts/page.tsx lib/apis/scraper-platform-accounts-api.service.ts
```

**Result:** `tsc` clean; biome `Checked 2 files ... No fixes applied.`

### 5.6 MCP selfcheck

```bash
cd nowing_mcp
python -m mcp_server.selfcheck
```

**Result:** `selfcheck OK: 31 tools registered and well-formed`

---

## 6. Action Items & Story Status

1. **P-5 (MCP tool contract)** — Cập nhật `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py`:
   - Đổi `max_pages` và `max_items` từ `ge=1` sang `ge=0` để khớp `ScrapeInput` zero-cap.
   - Thêm tham số `resolve_phones: bool = True` (hoặc `False` theo quyết định PO, nhưng phải khớp default của `ScrapeInput`).
2. Sau khi patch P-5: chạy lại `ruff check`, `pytest tests/unit/platforms/batdongsan tests/unit/capabilities/batdongsan -q`, `mcp_server.selfcheck`, `pnpm tsc --noEmit` + biome.
3. **F-1** giữ nguyên `defer` trong `deferred-work.md` (cross-platform billing audit).
4. **R-1/R-2/R-3** là hidden assumptions / doc conflicts; không cần action trừ khi PO/test xác nhận.

---

## 7. Verdict

**APPROVED**

Tất cả các finding đã được xử lý: 4 patch P-1 → P-4, 2 decision-needed D-1/D-2, patch v2 P-5 (MCP tool sync), và F-1 (cross-platform billing `degraded=True` không còn debit). Test suite sạch (83 unit + 2 integration recorded pass + 63 core billing tests + 44 batdongsan/muaban_bds/chotot billing).

---

## 8. Post-v2 Patch Update

**Updated:** 2026-08-03

P-5 đã được xử lý:
- `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py` đổi `max_pages`/`max_items` sang `Field(ge=0, le=...)` và thêm `resolve_phones: bool = True` trong payload.
- Verification:
  - `ruff check mcp_server/features/scrapers/platforms/batdongsan.py` ✅
  - `pytest tests/unit/platforms/batdongsan tests/unit/capabilities/batdongsan -q` ✅ 83 passed
  - `python -m mcp_server.selfcheck` ✅ `selfcheck OK: 31 tools registered and well-formed`
  - `cd nowing_web && pnpm tsc --noEmit` ✅

**Verdict sau patch:** P-1 → P-5, D-1/D-2 đều resolved. F-1 cũng đã giải quyết: `_charge_platform_meter` trong `app/capabilities/core/billing.py` không còn debit khi `output.degraded=True`. Đã sửa một regression nhỏ trong điều kiện `if items <= 0 and not output.degraded` để non-degraded vẫn charge đúng; E2E smoke test với `SCRAPE_LIVE=1` ✅ 3 passed.
