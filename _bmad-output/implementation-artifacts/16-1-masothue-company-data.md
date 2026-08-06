---
baseline_commit: 69967a9edd034f98d6df2b5d0e23c3ca159f27b9
baseline_branch: develop
story_key: 16-1-masothue-company-data
status: done
---

# Story 16.1: masothue.com Company Data

**Story ID:** 16.1  
**Epic:** 16 — Company Directory (Vietnam)  
**Title:** masothue.com Company Data  
**Status:** ready-for-dev  
**Priority:** P0  
**Requirements:** FR-51 (company data integration)  
**Architecture:** AD-3 (capability tự đăng ký route), AD-16 (ranh giới license Apache/BSL), AD-19 (anti-bot thuộc Nowing, degrade thay vì hard-fail), AD-27 (canonical entity convention), AD-25 (PII redaction), AD-26 (ToS/legal gate)  
**Dependencies:** Capability framework (`batdongsan.scrape`, `vietnamworks.scrape`, `cafef.scrape`); shared canonical storage (`app/canonical/`); `scrapling` anti-bot fetcher.

---

## 1. Goal

Thêm `masothue.scrape` thành built-in scraper capability mới. Story này lấy thông tin doanh nghiệp từ `masothue.com` (tên, mã số thuế, địa chỉ, người đại diện, tình trạng, loại hình, ngành nghề chính) qua HTML search + detail page, trả về danh sách company đã được type-hóa, đồng thời upsert vào canonical entity `company` để tránh duplicate khi re-fetch. Expose qua REST, agent chat và MCP tool `nowing_masothue_scrape` theo pattern `batdongsan.scrape`.

**Non-goal:**
- Không fetch chi tiết cá nhân (mã số thuế cá nhân/CMND) — chỉ tập trung doanh nghiệp.
- Không lưu số điện thoại vào canonical entity hoặc source snapshot (PII).
- Không build aggregator đa nguồn đầy đủ ở V1 (Story 16.2 mới thêm `business.gov.vn`); V1 giữ AD-27 convention trong `app/services/company_aggregator/` tối thiểu.
- Không crawl toàn bộ 2M+ companies; story chỉ hỗ trợ tìm kiếm theo query.

---

## 2. User Story

> As a business researcher,  
> I want to query Vietnamese company profiles from masothue.com,  
> So that I can verify business partners and research market players.

---

## 3. Acceptance Criteria

### AC-1 — Tìm kiếm doanh nghiệp qua HTML
**Given** một truy vấn `query` (tên công ty, MST, tên người đại diện) và `search_type` (`auto`, `enterpriseTax`, `enterpriseName`, `legalName`, `personalTax`, `identity`), tùy chọn `max_pages` và `max_items`,  
**When** tôi gọi `masothue.scrape`,  
**Then** nó trả về danh sách `MasothueCompany` đã typed, mỗi phần tử gồm `tax_code`, `name`, `address`, `tax_address`, `legal_representative`, `status`, `company_type`, `main_industry`, `active_date`, `managed_by`, `international_name`, `short_name`, `detail_url`.

### AC-2 — Resolve detail page
**Given** search trả về result list,  
**When** `resolve_detail=True` (mặc định),  
**Then** scraper mở từng `detail_path`, parse `table.table-taxinfo`, trả về đầy đủ các trường ở AC-1; nếu `resolve_detail=False`, trả về summary (name, tax_code, representative, address, detail_url) từ result list.

### AC-3 — Phân trang và giới hạn
**Given** `max_pages` (0–20) và `max_items` (0–100),  
**When** scraper chạy,  
**Then** nó dừng khi đạt `max_items`, hết trang, hoặc `max_pages`; over-cap bị clamp như pattern `batdongsan`.

### AC-4 — Billing & metering
**Given** một lần scrape thành công,  
**When** run hoàn tất,  
**Then** nó tính phí theo số company trả về bằng `MASOTHUE_COMPANY` billing unit, ghi `total_items`, `cost_micros`, `degraded` vào `Run`.

### AC-5 — Xử lý lỗi & degraded mode
**Given** masothue trả non-HTML, 403/429/timeout, Cloudflare challenge, hoặc cấu trúc không mong muốn,  
**When** scrape,  
**Then** run trả về `degraded=true` với `degradation_reason` typed (`api_error`, `rate_limited`, `access_blocked`, `decode_error`, `empty`, `ambiguous_query`, `unknown`), không charge cho trang lỗi, và không hard-fail.

### AC-6 — Anti-bot & Cloudflare
**Given** masothue.com sử dụng Cloudflare,  
**When** fetch,  
**Then** dùng `scrapling.fetchers.AsyncFetcher` với `stealthy_headers=True`, duy trì session/cookies giữa `POST /Ajax/Token` và `POST /Ajax/Search`, áp `MASOTHUE_PAGE_DELAY_S` giữa các request; nếu vẫn bị block thì degrade chứ không đẩy user vào CAPTCHA.

### AC-7 — MCP / REST / Agent exposure
**Given** capability đã build,  
**When** dùng REST, agent chat hoặc MCP,  
**Then** `nowing_masothue_scrape` / `masothue.scrape` khả dụng với contract tương tự `nowing_batdongsan_scrape`.

### AC-8 — Canonical entity & dedup
**Given** company data được fetch,  
**When** lưu vào workspace,  
**Then** nó tạo/cập nhật `canonical_entities` với `entity_type="company"`, fingerprint từ `tax_code` (normalize) hoặc fallback `name + address`, `search_text` cho vector/FTS, và `canonical_entity_sources` với `source_name="masothue"`; re-fetch cùng company sẽ update, không duplicate.

### AC-9 — Test coverage
**Given** code scraper,  
**Then** có unit tests cho parser với fixture HTML từ trang thật (detail + result list), integration test gọi thật hoặc recorded fixture, test billing/metering, và test canonical fingerprint/merge/search_text.

---

## 4. Tasks / Subtasks

- [x] ToS/legal review (AC ngoài code)
  - [x] Xác nhận scrape dữ liệu công khai từ masothue.com được phép; ghi vào `_bmad-output/planning-artifacts/legal/` hoặc đánh dấu approved.
- [x] Billing & config (AC #4)
  - [x] Thêm `BillingUnit.MASOTHUE_COMPANY` và rate config.
  - [x] Đăng ký micros/item trong `app/capabilities/core/billing.py`, `app/config/__init__.py`, `.env.example`.
- [x] Pydantic schemas (AC #1)
  - [x] `MasothueScrapeInput` (`query`, `search_type`, `tax_code` filter, `max_items`, `max_pages`, `resolve_detail`, `include_phone`).
  - [x] `MasothueCompany` và `MasothueScrapeOutput`.
- [x] Company canonical domain (AC #8, AD-27)
  - [x] Tạo `app/services/company_aggregator/__init__.py` với `fingerprint()`, `merge()`, `search_text()`, `normalize()`.
  - [x] `CompanyCanonical` / `MergeResult` schemas nếu cần (hoặc dùng `TypedDict`).
- [x] Proprietary fetcher (BSL) (AC #1, #5, #6)
  - [x] `nowing_backend/app/proprietary/platforms/masothue/__init__.py`.
  - [x] `nowing_backend/app/proprietary/platforms/masothue/schemas.py`.
  - [x] `nowing_backend/app/proprietary/platforms/masothue/fetch.py` — `fetch_search_page`, `fetch_detail_page`, `fetch_ajax_token`, `fetch_ajax_search`.
  - [x] `nowing_backend/app/proprietary/platforms/masothue/parsers.py` — parse result list, pagination, `table.table-taxinfo`.
  - [x] `nowing_backend/app/proprietary/platforms/masothue/scraper.py` — orchestrator, pagination, degrade, rate-limit.
- [x] Đăng ký capability `app/capabilities/masothue/scrape/` theo pattern `batdongsan.scrape` (AC #1, #6, #7)
  - [x] `app/capabilities/masothue/__init__.py`.
  - [x] `app/capabilities/masothue/scrape/schemas.py`.
  - [x] `app/capabilities/masothue/scrape/executor.py` — gọi scraper, upsert canonical, tính cost.
  - [x] `app/capabilities/masothue/scrape/definition.py` — `Capability(..., context_aware=True, billing_unit=BillingUnit.MASOTHUE_COMPANY)`.
- [x] Wire registry (AC #6, #7)
  - [x] `app/routes/__init__.py` import `app.capabilities.masothue`.
  - [x] `app/mcp_tools.py` thêm `{"name": "nowing_masothue_scrape", "group": McpToolGroup.SCRAPER}`.
  - [x] `nowing_mcp/mcp_server/features/scrapers/platforms/masothue.py` tool.
  - [x] `nowing_mcp/mcp_server/features/scrapers/__init__.py` thêm `masothue`.
  - [x] `nowing_mcp/mcp_server/selfcheck.py` thêm `nowing_masothue_scrape` vào `EXPECTED_TOOLS`.
  - [~] `nowing_web/app/(home)/mcp-server/page.tsx` thêm tool vào `TOOL_GROUPS` nếu marketing page cần cập nhật.
- [x] Viết tests (AC #9)
  - [x] Tạo ATDD checklist test-first (`bmad-nowing-test-first-atdd`) → `_bmad-output/test-artifacts/atdd-checklist-16-1-masothue-company-data.md`
  - [x] Unit parser tests với fixture detail + search list.
  - [x] Unit capability schema/executor/billing tests.
  - [x] Integration test với `@pytest.mark.integration` và flag `SCRAPE_LIVE`.
  - [x] Canonical convention tests `test_company_fingerprint.py`, `test_company_dedup.py`.

---

## 5. Dev Notes

### Architecture & License
- **AD-3:** `app/capabilities/masothue/scrape/` export `build_capabilities_router()`; mỗi lần gọi tạo một `Run` row.
- **AD-16:** logic fetch/anti-bot/parsing thuộc `app/proprietary/platforms/masothue/` (BSL 1.1); contract capability (`definition.py`, `schemas.py`, `executor.py`) ở `app/capabilities/masothue/scrape/` (Apache-2.0). Không đảo ngược ranh giới.
- **AD-19:** masothue.com dùng Cloudflare. Dùng `scrapling.fetchers.AsyncFetcher` với `stealthy_headers=True`; nếu vẫn bị challenge thì degrade (`degraded=true`) thay vì hard-fail hoặc giải CAPTCHA trên critical path. Có thể dùng `AsyncStealthySession` (patchright) làm fallback nếu cần, nhưng đo lường cost trên `WEB_CRAWL` meter.
- **AD-27:** `app/services/company_aggregator/` phải expose `fingerprint(raw_data)`, `merge(canonical, new_raw)`, `search_text(canonical)`. Vì V1 chỉ có `masothue`, `merge()` có thể pass-through và trả `MergeResult` với `resolution="most_recent"`.
- **AD-25 / PII:** Không lưu số điện thoại/rep phone vào `canonical_data` hay `source_snapshot`. `app/canonical/services/canonical_pii.py` đã redact mọi key chứa `phone`/`email` từ mọi entity type; nếu `include_phone=True` thì chỉ hiển thị trong `Run.output_text` (không lưu canonical).
- **AD-26:** Ghi ToS/legal review trước khi bật trên production. Nếu bị chặn, đánh `degraded=true` và loại bỏ capability khỏi default tools.

### Technical Details

#### Search & Detail Endpoints
- Search form: `GET https://masothue.com/Search/?q=<query>&type=<search_type>[&page=<n>]`.
- `search_type` values từ form option: `auto`, `enterpriseTax`, `personalTax`, `identity`, `enterpriseName`, `legalName`.
- Kết quả exact-match có thể trả về 302 redirect đến detail page (ví dụ `/0314539064-cong-ty-tnhh-vinamilk-tan-son`); khi đó parse detail page luôn.
- Kết quả multi-match trả về 200 với danh sách `h3 > a[href]`; pagination là `.page-numbers`.
- AJAX search token: `POST /Ajax/Token` với `r=<random>` trả `{"success":1,"token":"..."}`.
- AJAX search: `POST /Ajax/Search` với `q`, `type`, `token`, `force-search=1` trả `{"success":1,"url":"..."}` hoặc `mutilResult`. Trong quá trình research, endpoint này thường trả `url":"\/"` cho query MST khi token chưa được trình duyệt thật xác thực; V1 nên **dùng GET search HTML làm primary** và chỉ dùng AJAX như fallback.
- Detail page: `https://masothue.com<detail_path>` hoặc `https://masothue.com/<tax_code>-<slug>`. Parse `table.table-taxinfo`; mỗi `tr` có `th` (nhãn) và `td` (giá trị). Các nhãn quan trọng:
  - `Mã số thuế` → `tax_code`
  - `Địa chỉ Thuế` → `tax_address`
  - `Địa chỉ` → `address`
  - `Tình trạng` → `status`
  - `Tên quốc tế` → `international_name`
  - `Tên viết tắt` → `short_name`
  - `Người đại diện` → `legal_representative`
  - `Điện thoại` → `phone` (chỉ trả về output nếu `include_phone=True`)
  - `Ngày hoạt động` → `active_date`
  - `Quản lý bởi` → `managed_by`
  - `Loại hình DN` → `company_type`
  - `Ngành nghề chính` → `main_industry`

#### Parsing Strategy
- Dùng `BeautifulSoup` với `lxml` (đã có dependency).
- Search result card: `h3 > a[href]`; text của `a` là `name`. Tax code và người đại diện nằm trong text kế tiếp, có thể parse qua regex `Mã số thuế:\s*([\d\-]{10,})` và `Người đại diện:\s*([^\n]+)`.
- Detail table: lặp `table.table-taxinfo tr`, lấy `th.get_text(strip=True)` làm key, `td.get_text(" ", strip=True)` làm value. Bỏ qua hàng quảng cáo (`Cập nhật mã số thuế...`, `Nếu bạn có đề xuất...`).

#### Fingerprint & Canonical
- `fingerprint(raw_data)`:
  - Nếu có `tax_code` (sau khi `normalize` loại bỏ khoảng trắng, giữ nguyên số 0 đầu): dùng `sha256(normalized_tax_code.encode("utf-8")).hexdigest()[:16]`.
  - Fallback: `sha256((normalize(name) + "|" + normalize(address)).encode("utf-8")).hexdigest()[:16]`.
- `search_text(canonical)` join: `name`, `tax_code`, `address`, `legal_representative`, `status`, `company_type`, `main_industry`, `managed_by`.
- `merge(canonical, new_raw)`: V1 pass-through vì chỉ một nguồn. Trả `MergeResult(entity=new_data, conflict=False, conflict_fields=[], resolution="most_recent")`.
- `normalize(text)`: lowercase, NFKC, collapse whitespace, strip punctuation. Có thể dùng `unicodedata.normalize("NFKC", text)` + regex.

#### Capability I/O
- `ScrapeInput`:
  - `query: str`
  - `search_type: Literal["auto","enterpriseTax","enterpriseName","legalName","personalTax","identity"] = "auto"`
  - `tax_code: str | None = None` (filter kết quả sau khi tìm)
  - `max_pages: int = 5` (`ge=0`, `le=20`)
  - `max_items: int = 10` (`ge=0`, `le=100`)
  - `resolve_detail: bool = True`
  - `include_phone: bool = False`
- `ScrapeOutput`:
  - `items: list[MasothueCompany]`
  - `cost_micros: int = 0`
  - `degraded: bool = False`
  - `degradation_reason: str | None = None`
  - `total_items: int` (computed từ `len(items)`)
  - `billable_units: int` = `len(items)`
- `estimated_units` trong `ScrapeInput` = `max_items` (pre-flight gate worst-case).

#### Billing
- `BillingUnit.MASOTHUE_COMPANY = "masothue_company"`
- `MASOTHUE_SCRAPE_MICROS_PER_ITEM` default `3000` micros (0.3 cent / company).
- `MASOTHUE_PAGE_DELAY_S` default `1.0` (lịch sự với Cloudflare).
- `MASOTHUE_TIMEOUT_S` default `30.0`.
- `MASOTHUE_MAX_PAGES` default `5`.
- `MASOTHUE_MAX_ITEMS` default `50` (cap trong clamp validator, tương tự `VIETNAMWORKS_MAX_ITEMS`).

#### Error Handling
- `degradation_reason` typed: `api_error`, `rate_limited`, `access_blocked`, `decode_error`, `empty`, `ambiguous_query`, `unknown`.
- Khi detail page trả 404 hoặc không có `table.table-taxinfo`, bỏ qua item đó (không tính phí) nhưng vẫn trả các item khác.
- Khi query MST bị redirect về unrelated page hoặc homepage, trả `degraded=true` với `ambiguous_query`.
- Không log API key, proxy URL, PII.

#### Testing
- Fixtures: `tests/unit/platforms/masothue/fixtures/detail_page.html` (trimmed từ trang thật) và `search_page.html`.
- `test_parsers.py`: verify parse detail table, parse result list, pagination, tax code filter.
- `test_fetch.py`: mock `AsyncFetcher`/`httpx`, test token flow, 302 redirect, 403 degrade.
- `test_scraper.py`: mock fetcher, test pagination cap, `resolve_detail=False`, degraded mode.
- `test_executor.py`: test cost micros, canonical upsert mock, `context_aware`.
- `test_schemas.py`: test clamp `max_items`/`max_pages`, `estimated_units`.
- `test_billing.py`: verify `BillingUnit.MASOTHUE_COMPANY` tính đúng micros.
- Integration: `tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py`, chạy thật nếu `SCRAPE_LIVE=1`, ngược lại dùng fixture.

### Challenge Log (grill-me)

#### Q1 — Already implemented?
- **Partial pattern duplicate**: Proposed `company_aggregator` module duplicates the structure of existing `bds_aggregator` and `jobs_aggregator`. **Action**: Model `app/services/company_aggregator/dedupe.py` EXACTLY after `bds_aggregator/dedupe.py` (fingerprint, merge, search_text, deduplicate functions). New module is correct (different domain), but reuse the established pattern.

#### Q2 — Simpler alternative?
- No simpler alternative found. Masothue requires custom HTML parsing, Cloudflare anti-bot handling, AJAX token flow, and exact-match redirect handling. Vietnamworks (JSON API), cafef (simple HTML), and batdongsan (mobile API) cannot be reused.

#### Q3 — Edge cases spec misses (Pattern 3)
- **Boundary**:
  - [ ] `max_pages=0` or `max_items=0` → return empty list without degrading
  - [ ] Clarify if `max_pages=20` is hard limit or can be increased
  - [ ] Clarify if `max_items=100` is hard limit or can be increased
- **Null/empty**:
  - [ ] `query=""` or `query=None` → specify behavior (empty results vs degraded)
  - [ ] Invalid `search_type` value → specify error handling
  - [ ] Detail page missing `table.table-taxinfo` → clarify if this degrades whole run or just skips item
  - [ ] Tax code missing AND name+address missing → specify fingerprint behavior
- **Concurrent**:
  - [ ] Concurrent upsert of same company → executor should catch `ConcurrentUpdateError` and retry
  - [ ] Re-fetch same company → document merge behavior for conflicting fields
- **Data quality**:
  - [ ] Unicode normalization for non-Vietnamese characters
  - [ ] Tax code normalization rules (dashes vs no dashes)

#### Q4 — Failure modes unspecified (Pattern 2, 4)
- **Service down**:
  - [ ] `scrapling.AsyncFetcher` unavailable → specify fallback or hard degrade
  - [ ] Postgres down during canonical upsert → executor should catch and not charge
  - [ ] Embedding service down → clarify if this affects scrape response (backfill is async)
- **Timeout**:
  - [ ] Clarify if `MASOTHUE_TIMEOUT_S` is per-request or total
  - [ ] AJAX token request timeout → specify fallback to GET search HTML
- **Money/cost (Pattern 4)**:
  - [ ] Degraded run with partial items → clarify if successful page items are charged
  - [ ] Cost calculation timing → specify if charge happens before or after canonical upsert
- **Cloudflare/anti-bot**:
  - [ ] Cloudflare JS challenge detection logic
  - [ ] IP ban cooldown and user notification
- **Canonical dedup**:
  - [ ] Document V1 limitation: pass-through merge (no conflict resolution)
  - [ ] Fingerprint collision handling (extremely rare but possible)
- **Workspace isolation**:
  - [ ] Executor should verify workspace isolation before canonical upsert
- **Rate limiting**:
  - [ ] Consider adaptive backoff if masothue rate limit detected
  - [ ] V1 doesn't need platform account rotation (unlike batdongsan), document this

**Triage:** CLEAN — PROCEED with test additions for edge cases and failure modes. No critical blockers found.

---

## 6. File List

### New (proprietary — BSL 1.1)
- `nowing_backend/app/proprietary/platforms/masothue/__init__.py`
- `nowing_backend/app/proprietary/platforms/masothue/schemas.py`
- `nowing_backend/app/proprietary/platforms/masothue/fetch.py`
- `nowing_backend/app/proprietary/platforms/masothue/parsers.py`
- `nowing_backend/app/proprietary/platforms/masothue/scraper.py`

### New (capability — Apache-2.0)
- `nowing_backend/app/capabilities/masothue/__init__.py`
- `nowing_backend/app/capabilities/masothue/scrape/__init__.py`
- `nowing_backend/app/capabilities/masothue/scrape/schemas.py`
- `nowing_backend/app/capabilities/masothue/scrape/executor.py`
- `nowing_backend/app/capabilities/masothue/scrape/definition.py`

### New (company domain — Apache-2.0)
- `nowing_backend/app/services/company_aggregator/__init__.py`
- `nowing_backend/app/services/company_aggregator/schemas.py` (optional)

### Modified (billing/config)
- `nowing_backend/app/capabilities/core/types.py`
- `nowing_backend/app/capabilities/core/billing.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/.env.example`

### Modified (routing/MCP)
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/mcp_tools.py`
- `nowing_mcp/mcp_server/features/scrapers/__init__.py`
- `nowing_mcp/mcp_server/features/scrapers/platforms/masothue.py`
- `nowing_mcp/mcp_server/selfcheck.py`
- `nowing_web/app/(home)/mcp-server/page.tsx` (nếu marketing page cần liệt kê tool)

### Tests / fixtures
- `nowing_backend/tests/unit/platforms/masothue/test_parsers.py`
- `nowing_backend/tests/unit/platforms/masothue/test_fetch.py`
- `nowing_backend/tests/unit/platforms/masothue/test_scraper.py`
- `nowing_backend/tests/unit/platforms/masothue/fixtures/detail_page.html`
- `nowing_backend/tests/unit/platforms/masothue/fixtures/search_page.html`
- `nowing_backend/tests/unit/capabilities/masothue/scrape/test_schemas.py`
- `nowing_backend/tests/unit/capabilities/masothue/scrape/test_executor.py`
- `nowing_backend/tests/unit/capabilities/masothue/scrape/test_billing.py`
- `nowing_backend/tests/integration/capabilities/masothue/scrape/test_masothue_scrape.py`
- `nowing_backend/tests/unit/services/company_aggregator/test_fingerprint.py`
- `nowing_backend/tests/unit/services/company_aggregator/test_dedup.py`

---

## 7. Traceability

| AC | Code location | Test |
|---|---|---|
| AC-1 HTML search | `proprietary/platforms/masothue/fetch.py:fetch_search_page` | `test_fetch.py`, `test_masothue_scrape.py` |
| AC-2 detail parse | `proprietary/platforms/masothue/parsers.py:parse_detail` | `test_parsers.py` |
| AC-3 pagination/cap | `proprietary/platforms/masothue/scraper.py:scrape_masothue` | `test_scraper.py` |
| AC-4 billing | `app/capabilities/masothue/scrape/executor.py`, `app/capabilities/core/billing.py` | `test_billing.py` |
| AC-5 degrade | `proprietary/platforms/masothue/scraper.py`, `executor.py` | `test_scraper.py`, `test_executor.py` |
| AC-6 anti-bot | `proprietary/platforms/masothue/fetch.py` (AsyncFetcher + stealthy_headers) | `test_masothue_scrape.py` (live flag) |
| AC-7 MCP/REST | `app/capabilities/masothue/scrape/definition.py`, `nowing_mcp/.../masothue.py`, `app/mcp_tools.py` | `test_registry.py`, `mcp_server/selfcheck.py` |
| AC-8 canonical | `services/company_aggregator/`, `app/capabilities/masothue/scrape/executor.py` | `test_fingerprint.py`, `test_dedup.py` |
| AC-9 tests | (all test files ở File List) | — |

---

## 8. References

- Epic 16: `_bmad-output/planning-artifacts/epics.md` §"Epic 16: Company Directory (Vietnam)"
- Manual story pointer: `_bmad-output/implementation-artifacts/stories/16-1-masothue-company-data.md`
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3, AD-16, AD-19, AD-27, AD-25, AD-26
- Pattern scraper: `nowing_backend/app/capabilities/batdongsan/scrape/` and `nowing_backend/app/proprietary/platforms/batdongsan/`
- Pattern simple API scraper: `nowing_backend/app/capabilities/vietnamworks/scrape/` and `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py`
- Pattern capability with context + indexing: `nowing_backend/app/capabilities/cafef/scrape/executor.py`
- Pattern canonical persist: `nowing_backend/app/canonical/services/canonical_persist_service.py`
- Pattern domain AD-27: `nowing_backend/app/services/bds_aggregator/` and `nowing_backend/app/services/jobs_aggregator/`
- Pattern PII redaction: `nowing_backend/app/canonical/services/canonical_pii.py`
- Pattern MCP tool: `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py`
- Billing / types: `nowing_backend/app/capabilities/core/billing.py`, `nowing_backend/app/capabilities/core/types.py`
- Config pattern: `nowing_backend/app/config/__init__.py` (các dòng `BATDONGSAN_*`, `VIETNAMWORKS_*`, `CAFEF_*`)
- masothue.com search form and detail page HTML đã được fetch trực tiếp trong research session.

---

## 9. Change Log

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-08-07 | 1.0 | Initial story file ready-for-dev | bmad-create-story |

---

## 10. Dev Agent Record

### Agent Model Used

N/A — story file; implementation chưa thực hiện.

### Debug Log References

- Research trực tiếp trên `masothue.com` 2026-08-07:
  - `GET /Search/?q=vinamilk&type=auto` trả về danh sách kết quả với pagination `.page-numbers`.
  - `GET /Search/?q=vinamilk&type=auto&page=2` trả về trang tiếp theo.
  - `GET /0314539064-cong-ty-tnhh-vinamilk-tan-son` trả về `table.table-taxinfo` với các trường mục tiêu.
  - `POST /Ajax/Token` trả `{"success":1,"token":"..."}`.
  - `POST /Ajax/Search` với token thường trả `{"success":1,"url":"\/"}` cho query MST, cho thấy V1 nên dùng GET search HTML làm primary.

### Completion Notes List

- Story được tạo dựa trên template `bmad-create-story`, epic 16, architecture spine, và pattern từ 10.1 batdongsan + 15.1 cafef.
- Cần update `stories/16-1-masothue-company-data.md` để trỏ về file canonical này.
- Cần update `sprint-status.yaml` chuyển `16-1` thành `ready-for-dev`.

### Review Findings

Từ `bmad-code-review` trên commit `de5496d6e` (2026-08-07). Xem đầy đủ tại `_bmad-output/implementation-artifacts/code-reviews/16-1-masothue-code-review.md`.

- [x] [Review][must-fix] `cost_micros` không zero khi run bị degraded — `nowing_backend/app/capabilities/masothue/scrape/executor.py:120-121`
- [x] [Review][should-fix] Detail page 429 không trigger degraded/rate_limited — `nowing_backend/app/proprietary/platforms/masothue/scraper.py:178-195`
- [x] [Review][should-fix] 302 exact-match redirect + `tax_code` filter trả về empty sai — `nowing_backend/app/proprietary/platforms/masothue/fetch.py:131-133`, `scraper.py:166-167,198-199`
- [x] [Review][should-fix] Thiếu delay giữa các request detail page — `nowing_backend/app/proprietary/platforms/masothue/scraper.py:170-184`
- [x] [Review][should-fix] `parse_pagination` không được dùng, scraper fetch thêm trang rỗng — `parsers.py:176-198`
- [x] [Review][should-fix] Regex trích `legal_representative` có thể lấn sang trường kế tiếp — `parsers.py:109-115`
- [x] [Review][should-fix] Thiếu unit/integration test cho `resolve_detail=False`, `include_phone=True`, live `SCRAPE_LIVE` — `tests/unit/platforms/masothue/`, `tests/integration/capabilities/masothue/scrape/`
- [x] [Review][watch] `fetch_ajax_token`/`fetch_ajax_search`/`fetch_all_pages` chưa được dùng (dead code/fallback chưa wire) — `fetch.py:182-290`
- [x] [Review][watch] Canonical upsert lỗi per-item vẫn tính phí và trả về item — `executor.py:124-147`
- [x] [Review][watch] Regex `_extract_tax_code` không xử lý khoảng trắng trong MST ở search result — `parsers.py:99-107`
- [x] [Review][non-issue] `mcp_tools.py` insertion không theo alphabet, `nowing_web` marketing page chưa liệt kê, typo trong label map, local `import json` — không ảnh hưởng runtime
