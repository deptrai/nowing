# BMAD Code Review Report — Story 10.1: Batdongsan.com.vn Scraper

**Review date:** 2026-08-03  
**Story file:** `_bmad-output/implementation-artifacts/10-1-batdongsan-scraper.md`  
**ATDD checklist:** `_bmad-output/test-artifacts/atdd-checklist-10-1-batdongsan-scraper.md`  
**Epic section:** `_bmad-output/planning-artifacts/epics.md` §Story 10.1  
**Baseline commit:** `0eba86e9ed66527e2f0bfe661a19c7fc1c4e4ed2` (develop)  
**Review mode:** full  
**Diff artifact:** `_bmad-output/implementation-artifacts/bmad-cr-10-1-diff.md`

---

## 1. Executive Summary

| Item | Value |
|---|---|
| Files changed (tracked diff) | 32 files |
| Insertions / deletions | +4,104 / −4 |
| Untracked in diff | `nowing_backend/scripts/capture_batdongsan_session.py` (+245 lines) |
| `ruff check` | ✅ All checks passed |
| `pytest tests/unit/platforms/batdongsan -q` | ✅ 42 passed |
| `pytest tests/unit/capabilities/batdongsan -q` | ✅ 37 passed |
| **Verdict** | **CHANGES REQUESTED** |

Tổng quan: Code đáp ứng phần lớn AC-1 → AC-7 (decode pipeline, parser, pagination, billing unit, MCP/REST exposure, tests). Tuy nhiên có 4 lỗi/thiếu sót cần patch (trong đó 1 high là thiếu pre-warm session theo AC-9), 2 khoản cần quyết định PO (schema boundary và concurrency phone fetch), 1 khoản defer cross-platform billing, và 1 khoản dismiss do mâu thuẫn giữa ATDD và implementation artifact.

---

## 2. AC / ATDD Coverage Summary

| AC | Status | Notes |
|---|---|---|
| AC-1 Mobile API + typed listing | ✅ Pass | `fetch.py` gọi `p_sync`, parser trả `BatdongsanListing` đúng fields. |
| AC-2 Decode pipeline | ✅ Pass | `gzip → base64 → nibble-swap → Latin-1 → json` đúng thứ tự, có test fixture. |
| AC-3 Pagination & limits | ⚠️ Partial | `max_items`/`max_pages` dùng `ge=1`; ATDD mong đợi `0`. Cần quyết định. |
| AC-4 Billing | ✅ Pass | `BATDONGSAN_ITEM` + `billable_units` + `charge_capability` hoạt động; test billing pass. |
| AC-5 Degraded mode | ✅ Pass | `degraded` + `degradation_reason` typed, không hard-fail, retry 403/429. |
| AC-6 MCP/REST/Agent exposure | ✅ Pass | Capability, MCP tool, route, marketing page wired. |
| AC-7 Test coverage | ✅ Pass | 79 tests unit + integration recorded pass. |
| AC-8 Phone unmask | ⚠️ Partial | `resolve_phones` không expose; response `DecryptPhone` chưa parse JSON; chưa log `USER_NO_PERMISSION_TO_VIEW_PHONE`. |
| AC-9 Cookie capture & pre-warm | ❌ Fail | Admin UI + capture script OK, nhưng **thiếu hoàn toàn pre-warm session** khi `con.ses.id` sắp hết hạn. |

---

## 3. Findings (triage)

### 3.1 `decision_needed`

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| D-1 | Acceptance Auditor + Edge Case Hunter | medium | decision_needed | `nowing_backend/app/proprietary/platforms/batdongsan/schemas.py:19-20`<br>`nowing_backend/app/capabilities/batdongsan/scrape/schemas.py:18-19` | Schema boundary & city allow-list | ATDD AC-1/AC-3 mong đợi `max_items=0`/`max_pages=0` trả empty list / no charge, và `city` không hợp lệ trả 422. Schema hiện tại dùng `ge=1` và không validate `city`. Cần PO quyết định: (a) có hỗ trợ zero-cap không, (b) allow-list city dựa trên `CITY_SLUGS` hay mobile-only codes? Cập nhật schema + tests sau quyết định. |
| D-2 | Edge Case Hunter | medium | decision_needed | `nowing_backend/app/proprietary/platforms/batdongsan/scraper.py:219-235` | Serial, unbounded phone detail fetches | Khi `resolve_phones=True`, scraper mở trang chi tiết tuần tự cho từng listing tới `max_items` (100). Không có semaphore, không có timeout/cap riêng, rủi ro chạy rất lâu hoặc toàn run timeout. Cần quyết định giới hạn concurrency/số lượng (vd max 5-10 song song, hoặc cap phone resolve tùy theo giá trị nghiệp vụ). |

### 3.2 `patch`

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| P-1 | Acceptance Auditor | high | patch | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:172-201`<br>`nowing_backend/app/proprietary/platforms/batdongsan/scraper.py:219-237` | Missing session pre-warm (AC-9) | AC-9 yêu cầu scraper tự động ghé `/dang-nhap` khi `con.ses.id` hoặc `accessToken` sắp hết hạn để duy trì phone unmask trong suốt lifetime. Hiện tại `_open_stealth_session` chỉ load cookies, không kiểm tra expiry hay pre-warm. Cần thêm `_should_prewarm(cookies)` dựa trên `expires` của `con.ses.id`/`accessToken` và navigate tới `LOGIN_URL` khi < 5 phút. |
| P-2 | Acceptance Auditor | medium | patch | `nowing_backend/app/capabilities/batdongsan/scrape/schemas.py:10-24`<br>`nowing_backend/app/capabilities/batdongsan/scrape/executor.py:67-70` | `resolve_phones` not exposed in input schema | AC-8 đề cập `resolve_phones=True`, nhưng `ScrapeInput`/`BatdongsanScrapeInput` không có field này; executor luôn truyền `resolve_phones=True`. Buộc mọi run đều mở browser cho phone. Cần thêm `resolve_phones: bool = True` vào cả 2 schema, truyền `payload.resolve_phones` xuống `scrape_batdongsan`, và cập nhật MCP tool. |
| P-3 | Acceptance Auditor + Blind Hunter + Edge Case Hunter | medium | patch | `nowing_backend/app/proprietary/platforms/batdongsan/fetch.py:344-350` | `DecryptPhone` response not parsed as JSON; `USER_NO_PERMISSION_TO_VIEW_PHONE` not logged | Endpoint trả về JSON (ví dụ `{"phone":"0906..."}` hoặc `{"message":"USER_NO_PERMISSION_TO_VIEW_PHONE"}`). Code hiện xử lý `phone_text` như text thuần, chỉ lọc digit và check `*`. Có thể trả cả JSON string làm `phone_display`. Cần `json.loads(phone_text)`, extract `phone` / `message`, log warning khi gặp `USER_NO_PERMISSION_TO_VIEW_PHONE`, và không coi message đó là số hợp lệ. |
| P-4 | Blind Hunter | low | patch | `nowing_backend/app/services/scraper_platform_account_service.py:48-84` | `cookie_string_to_playwright` ignores `domain` for legacy strings | `_parse_cookie_input` hardcode `domain=".batdongsan.com.vn"` cho mọi chuỗi `name=value; ...`. Tham số `domain` của `cookie_string_to_playwright` chỉ dùng trong fallback cho chuỗi rỗng (practically unreachable). Nên chuyển việc gán `domain` sang `cookie_string_to_playwright` để helper này đúng nghĩa dùng cho nhiều platform. |

### 3.3 `defer`

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| F-1 | Blind Hunter + Acceptance Auditor | low | defer | `nowing_backend/app/capabilities/batdongsan/scrape/executor.py:104-108`<br>`nowing_backend/app/capabilities/core/billing.py:398-426` | `ScrapeOutput.cost_micros` is 0 for degraded runs but wallet may still be charged | Executor đặt `cost_micros=0` khi `degraded=True`, nhưng `charge_capability` qua `_charge_platform_meter` vẫn debit theo `output.billable_units` nếu > 0. Đây là pattern chung với `muaban_bds`/`chotot` executors. Sửa trong story này sẽ tạo divergence; nên xử lý cross-platform ở `billing.py` khi audit toàn bộ platform scrapers. Đã ghi vào `deferred-work.md`. |

### 3.4 Dismissed

| ID | Source | Severity | Route | Location | Title | Detail |
|---|---|---|---|---|---|---|
| R-1 | Acceptance Auditor | low | dismiss | `nowing_backend/app/proprietary/platforms/batdongsan/scraper.py:193-196` | ATDD vs implementation artifact conflict on empty first page | ATDD AC-1 Pattern 2 mong `degraded=false` khi API trả empty / `district_id` invalid; implementation artifact AC-5 lại yêu cầu `degraded=true` với `degradation_reason="empty"`. Code tuân theo AC-5. Đây là mâu thuẫn tài liệu, không phải lỗi code. Recommend cập nhật ATDD cho khớp. |

---

## 4. Layer Review Notes

### 4.1 Blind Hunter
- Nhấn mạnh helper `cookie_string_to_playwright` bỏ qua `domain` (P-4) và mâu thuẫn billing `cost_micros` vs `charge_capability` (F-1).
- Không phát hiện backdoor/security nghiêm trọng; `subprocess.Popen` trong admin route chỉ chạy script đã tồn tại trong `scripts/`, không dùng shell, gọi bởi superuser.
- Admin UI có nút "Auto-filter for Batdongsan" nhưng fallback keep-all cho cookies không rõ ràng; không đủ nghiêm trọng để triage.

### 4.2 Edge Case Hunter
- `decode_response` có size cap (`_MAX_DECODED_BYTES`) và xử lý gzip-bomb; nibble-swap self-inverse test đầy đủ.
- Pagination dừng đúng khi `m=None`, `max_items`, `max_pages`, dedupe theo `listing_id` hoạt động.
- `resolve_phones` luôn bật → rủi ro performance (D-2).
- Phone XHR polling 30 lần × 500ms = 15s; không click nút `Hiện số` trước khi lấy `raw`; có thể cần bổ sung click event nếu `raw` không xuất hiện sẵn (không đủ bằng chứng để triage, ghi nhận trong P-3).

### 4.3 Acceptance Auditor
- AC-1: parser trả đủ fields, mapping `listing_type` → `ptype`, `city` → API code. `detail_url` tồn tại trên model; live mobile API có thể không trả `url` và sẽ phụ thuộc `resolve_phones`/`resolve_detail_urls`.
- AC-2: decode pipeline chính xác, có unit test nibble-swap, fixture roundtrip.
- AC-3: pagination/cap logic đúng, nhưng schema từ chối zero-boundary (D-1).
- AC-4: `BATDONGSAN_ITEM` billing unit, rate 3500 micros, `billable_units` trên cả hai output model.
- AC-5: degradation reasons typed, retry 403/429, không hard-fail.
- AC-6: capability, MCP, REST wired.
- AC-7: tests đầy đủ, tất cả pass.
- AC-8: `resolve_phones` không expose (P-2); XHR response chưa parse JSON/log permission (P-3).
- AC-9: capture script + admin UI OK; **pre-warm hoàn toàn thiếu** (P-1).

---

## 5. Verification Results

### 5.1 Ruff

```bash
cd nowing_backend
ruff check app/proprietary/platforms/batdongsan app/services/scraper_platform_account_service.py app/routes/admin_scraper_platform_accounts_routes.py app/capabilities/batdongsan/scrape/executor.py
```

**Result:** `All checks passed!`

### 5.2 Pytest — unit platforms

```bash
cd nowing_backend
pytest tests/unit/platforms/batdongsan -q
```

**Result:**
```
collected 42 items
...
======================== 42 passed, 7 warnings in 0.30s ========================
```

### 5.3 Pytest — unit capabilities

```bash
cd nowing_backend
pytest tests/unit/capabilities/batdongsan -q
```

**Result:**
```
collected 37 items
...
======================== 37 passed, 7 warnings in 2.69s ========================
```

---

## 6. Action Items & Story Status

- Đã cập nhật `10-1-batdongsan-scraper.md` frontmatter `status: in-progress`.
- Đã thêm `### Review Findings` vào story file với 2 `decision-needed`, 4 `patch`, 1 `defer`.
- Đã cập nhật `sprint-status.yaml` chuyển `10-1` từ `review` sang `in-progress`.
- Đã append `F-1` vào `deferred-work.md`.
- **Cần xử lý trước khi done:**
  1. Quyết định PO cho D-1 (zero-cap & city allow-list) và D-2 (phone concurrency cap).
  2. Patch P-1 (pre-warm), P-2 (`resolve_phones`), P-3 (phone JSON/log), P-4 (cookie domain).
- Sau khi patch xong: chạy lại `ruff check`, `pytest tests/unit/platforms/batdongsan -q`, và `pytest tests/unit/capabilities/batdongsan -q`.

---

## 7. Verdict

**CHANGES REQUESTED**

Có 1 finding high (thiếu pre-warm AC-9) và 2 finding medium cần quyết định PO. Các phần core (decode, parser, billing, capability exposure, tests) đã vững, nhưng story chưa thể merge/done cho đến khi P-1 → P-4 được xử lý và D-1/D-2 được giải quyết.

---

## 8. Post-Review Patch Update

**Updated:** 2026-08-03  
**Verification:** `ruff check` ✅ / `pytest tests/unit/platforms/batdongsan tests/unit/capabilities/batdongsan -q` ✅ 79 passed

| ID | Status | Notes |
|---|---|---|
| P-1 | ✅ Fixed | Pre-warm session đã được triển khai: `_should_prewarm`, `_prewarm_batdongsan_session`, `_make_page_setup` trong `fetch.py`; `fetch_detail_phone` dùng `_make_page_setup(credentials)`. Kiểm thử thực tế với `con.ses.id` sắp hết hạn vẫn trả về số điện thoại đầy đủ. |
| P-2 | ✅ Fixed | `resolve_phones: bool = True` đã thêm vào `BatdongsanScrapeInput` và `ScrapeInput`; executor truyền `payload.resolve_phones` xuống `scrape_batdongsan`. |
| P-3 | ✅ Fixed | `_extract_phone_from_xhr` parse JSON/text, log `USER_NO_PERMISSION...`, không coi đó là số hợp lệ. |
| P-4 | ✅ Fixed | `_parse_cookie_input` nhận `domain` từ `cookie_string_to_playwright`, gán đúng domain cho legacy cookie string. |
| D-1 | ⏳ Open | Vẫn cần PO quyết định về `max_items=0`/`max_pages=0` và allow-list `city`. |
| D-2 | ⏳ Open | Vẫn cần PO quyết định về concurrency cap / timeout cho phone detail fetch. |
| F-1 | ⏸️ Defer | Giữ nguyên, ghi trong `deferred-work.md` (cross-platform billing). |

**Verdict sau patch:** Còn 2 `decision-needed` (D-1, D-2) chưa giải quyết; 4 `patch` đã xử lý.

---

## Next steps in Nowing quality pipeline

**Vừa xong:** `bmad-code-review` (Story 10.1) — CHANGES REQUESTED với 4 patch, 2 decision-needed, 1 defer.

**Bước tiếp theo (BẮT BUỘC):**
- [4.7] `bmad-dev-story` — sửa 4 patch + giải quyết 2 decision-needed, sau đó re-run `bmad-code-review` (tối đa 2 vòng).

**Bước tiếp theo (recommended, áp dụng khi story done):**
- [4.9] `bmad-testarch-test-review` — Recommended cho mọi story.
- [4.10] `bmad-nowing-mutation-gate` — **P0-gated** vì story chạm `app/capabilities/core/billing.py` / `app/capabilities/core/types.py` (billing/credit area).
- [4.11] `bmad-testarch-trace` — Recommended khi epic sắp xong.
- [4.12] `bmad-testarch-nfr` — Recommended (nếu story liên quan NFR latency/retention).
- [4.13] `bmad-nowing-human-review-gate` — **P0-gated** vì billing/credit code paths bị tác động.
- [4.14] `bmad-nowing-web-e2e-gate` — Recommended vì `nowing_web/app/admin/scraper-accounts/page.tsx` thay đổi.

**Còn lại trong pipeline:** Sau khi epic 10 xong → [4.17] `bmad-retrospective`.
