---
title: Story 12.2 — TopCV Scraper
epic: 12
story: 2
status: done
priority: P0
baseline_commit: 5904d3ec2c1a04d04296f8eba6d29cf83b3f87e5
review_loop_iteration: 0
---

# Story 12.2 — TopCV Scraper

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** recruiter  
**I want:** to search TopCV job postings  
**So that:** I can access the largest local Vietnamese job board.

---

## Acceptance Criteria

1. **Given** a query and optional city filter (`location`) plus pagination params (`page`, `max_pages`, `max_items`), **When** `topcv.scrape` runs, **Then** it fetches the TopCV search results page and follows detail-page links for each job card.

2. **Given** a Cloudflare/anti-bot challenge (`HTTP 403` or page title contains `Just a moment...`), **When** encountered, **Then** the scraper attempts a warmed headless browser/proxy rotation (Playwright/Puppeteer with stealth or a residential proxy), returns `degraded=true` with `degradation_reason: ANTI_BOT` if bypass fails, and does not crash.

3. **Given** a successful fetch of a detail page, **When** parsed, **Then** it returns a typed `JobItem` with: `title`, `company`, `location`, `salary` (empty/null if hidden), `job_description`, `job_requirement`, `skills` (list), `employment_type`, `experience_years`, `post_date`, and `source_url`.

4. **Given** salary is not visible or is marked `Thương lượng`, **When** parsed, **Then** `salary` is `null`, `salary_hidden=true`, and `salary_confidence` is `low`; if a numeric range can be inferred from the title, it is placed in `salary` with `salary_confidence: medium`.

5. **Given** the search results page has pagination, **When** `page` and `max_pages` are provided, **Then** the scraper iterates until `max_pages` is reached, no more results are found, or `max_items` total listings are collected.

6. **Given** TopCV returns `HTTP 429`, **When** rate-limited, **Then** the scraper backs off exponentially (starting at 2s, max 30s), rotates `User-Agent`, and uses a circuit-breaker that trips after 3 consecutive failures and returns `degraded=true` with `degradation_reason: RATE_LIMIT`.

7. **Given** PII such as Vietnamese phone numbers, email addresses, or person names appears in `job_description` or `job_requirement`, **When** the `JobItem` is produced, **Then** the PII pipeline masks or drops those fields, logs only counts (no values), and the raw unredacted JD is not stored in `Memory` or returned in the payload.

8. **Given** a list of valid `JobItem[]` objects, **When** `to_chunks()` is called, **Then** each `JobItem` becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, a stable `sourceId` (e.g. `sha256(title|company|location|post_date)`), `domain: 'topcv.vn'`, `fetchedAt`, `contentType: 'job'`, and the redacted `content`; the chunk conforms to AD-34 and is ready for `NowingIngestService`.

9. **Given** the capability is built, **When** registered, **Then** it appears in `BillingUnit.TOPCV_JOB`, the capability registry, MCP (`nowing_topcv_scrape`), and REST routes with typed request/response schemas.

10. **Given** the upstream site changes its HTML structure, **When** the selectors fail to match the golden fixtures, **Then** the regression test `test_topcv_golden_fixtures.py` fails before deployment.

11. **Given** Story 12.0 (ToS/Legal Review) returns a `disabled` or `blocked` decision for TopCV, **When** the capability is loaded, **Then** TopCV is excluded from the default source list and any call returns `degraded=true` with `degradation_reason: LEGAL_BLOCKED`.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/capabilities/topcv/scrape/` and `app/proprietary/platforms/topcv/`.
- Cost model: use `WEB_CRAWL` + `captcha` billing per AD-23; anti-bot POC is the hard gate.
- Do not merge before TopCV anti-bot POC passes or the source is explicitly disabled in config.
- Reuse the `to_chunks()` helper from `app/services/scraper_chunks/` per Epic 20.1 / AD-34.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />

### Review Findings (code review chunk 1 — 2026-08-10)

#### Decision Needed

_(Đã giải quyết — xem bên dưới)_

#### Patch

- [ ] [Review][Patch] Thêm `salary_hidden` và `salary_confidence` vào JobItem — `_apply_detail` / `_extract_salary_numbers` chỉ set `salary_min/max/currency/period_id`, vi phạm AC-4. `[scraper.py:66-113,386-399]`
- [ ] [Review][Patch] Trả `degraded=True` khi partial failure — `scraper.py:482-496`: nếu exception xảy ra sau khi đã có items, code rơi vào `return` cuối với `degraded=False`. Cần trả về items + `degraded=True`.
- [ ] [Review][Patch] Tính cost sai khi search/detail thất bại — `scraper.py:461,470` cộng cost trước khi biết kết quả. Cần tính cost chỉ khi parse thành công.
- [ ] [Review][Patch] Phát hiện anti-bot sớm hơn — `_fetch_search_page` chỉ kiểm tra empty HTML, không đọc `title` hay `block_type` từ StealthyFetcher/Crawler. Vi phạm AC-2/AC-3. `[scraper.py:402-422]`
- [ ] [Review][Patch] Thêm `TOPCV_TIMEOUT_S` và timeout cho `asyncio.to_thread` / `WebCrawlerConnector` — `scraper.py:418,428` không truyền timeout. `[scraper.py:402-434]`
- [ ] [Review][Patch] Validate đầu vào `max_items`/`max_pages` âm, keyword whitespace — `scraper.py:438-450` gọi `int()` trực tiếp; mặc dù schema có `ge=0`, `scrape_topcv` có thể được gọi từ test khác. `[scraper.py:437-450]`
- [ ] [Review][Patch] Sửa `_clean_url` và `_normalize_keyword` — `_clean_url` tạo URL invalid khi thiếu scheme; `_normalize_keyword` không URL-encode ký tự đặc biệt (`C++` → `c++`). `[scraper.py:44-64]`
- [ ] [Review][Patch] Thêm kiểm tra legal/TOS block (AC-11) — `scraper.py:499-507` không kiểm tra config vô hiệu hóa TopCV. Cần flag `TOPCV_ENABLED` hoặc tương tự.
- [ ] [Review][Patch] Thêm golden fixture regression test (AC-10) — thiếu `test_topcv_golden_fixtures.py` để phát hiện selector thay đổi.
- [ ] [Review][Patch] Thống nhất `degradation_reason` anti-bot thành `bot_detected` — `scraper.py:485,488,507` dùng `anti_bot_block`; executor `topcv/scrape/executor.py:17-22` cần thêm `bot_detected` vào `_BOT_DEGRADATION_REASONS`. Chọn `bot_detected` để nhất quán với `chotot` scraper.
- [ ] [Review][Patch] Implement retry/backoff/circuit-breaker cho rate limit (AC-6) — `scraper.py:402-434` không bắt 429, không backoff, không circuit. Implement trong `scraper.py` với `TOPCV_RETRY_ATTEMPTS`, `TOPCV_RETRY_BACKOFF_BASE_S`, `TOPCV_CIRCUIT_BREAKER_THRESHOLD` config.

#### Defer

- [x] [Review][Defer] PII redaction tại scraper (AC-7) — deferred sang Story 12.5 / Epic 20.1; PII pipeline hiện chưa có trong `app/services/scraper_chunks/` và `app/services/jobs_aggregator/orchestrator.py` chưa hoàn thiện. `[scraper.py:196-267]`
- [x] [Review][Defer] `to_chunks()` helper (AC-8) — deferred sang Epic 20.1 / AD-34; helper chưa tồn tại.
- [x] [Review][Defer] Capability registration MCP/REST/Billing (AC-9) — đã có sẵn trong skeleton (`app/capabilities/topcv/scrape/definition.py`, `BillingUnit.TOPCV_JOB`, `app/capabilities/__init__.py`), không thuộc diff chunk 1.
- [x] [Review][Defer] Location filter `location` (AC-1) — TopCV dùng city IDs (`?locations=l1_l8`) và slug path `tim-viec-lam-<keyword>-tai-<city>-kl<id>`, cần mapping city→ID. Không có trong spike; hoãn đến khi có dữ liệu.

## Suggested Review Order

**Anti-bot resilience and retry**

- Circuit-breaker and failure accounting live at module scope and use monotonic time.
  [`scraper.py:468`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L468)

- Validate search page for empty HTML, 403/429, `Just a moment...`, and `classify_block` results.
  [`scraper.py:493`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L493)

- Retry search fetch with UA rotation, StealthyFetcher timeout, and exponential backoff.
  [`scraper.py:522`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L522)

- Retry detail fetch and translate `WebCrawlerConnector` block types into rate/anti-bot errors.
  [`scraper.py:577`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L577)

- Orchestrate pages, items, partial degradation, and post-parse cost charging.
  [`scraper.py:623`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L623)

- TopCV config knobs for retry, backoff, circuit breaker, and global enablement.
  [`config/__init__.py:980`](../../../nowing_backend/app/config/__init__.py#L980)

**Salary parsing and item enrichment**

- Parse Vietnamese/English salary text with dot thousands, comma decimals, unit suffixes, and range markers.
  [`scraper.py:83`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L83)

- Merge search-card and detail-page data into the final `JobItem` dict.
  [`scraper.py:427`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L427)

- Extract job cards from search HTML and populate initial fields.
  [`scraper.py:330`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L330)

**Input and URL handling**

- Normalize keyword into a TopCV URL slug, preserving `+` and stripping `#`.
  [`scraper.py:53`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L53)

- Build search URL and clean source URLs (default scheme, keep query).
  [`scraper.py:66`](../../../nowing_backend/app/proprietary/platforms/topcv/scraper.py#L66)

- Add `page` start-offset to the capability input schema.
  [`schemas.py:10`](../../../nowing_backend/app/capabilities/topcv/scrape/schemas.py#L10)

**Capability wiring**

- Unify `degradation_reason` whitelist around `bot_detected`/`rate_limited`.
  [`executor.py:17`](../../../nowing_backend/app/capabilities/topcv/scrape/executor.py#L17)

**Regression tests**

- Golden fixtures exercise search parsing and salary extraction.
  [`test_topcv_golden_fixtures.py:51`](../../../nowing_backend/tests/unit/proprietary/platforms/topcv/test_topcv_golden_fixtures.py#L51)

### Review Findings (bmad-code-review — 2026-08-10)

#### Decision Needed

- [x] [Review][Decision] Xử lý detail-page anti-bot khi bị block — `_fetch_detail_page` đang nuốt anti-bot block và trả `{}` để tiếp tục. Cần quyết định: (a) degrade toàn bộ ngay khi 1 detail bị block, (b) có ngưỡng N lần liên tiếp, hay (c) giữ nguyên `swallow` vì lý do resilience. `[scraper.py:577-617]` — giải quyết: dùng ngưỡng 3 detail anti-bot liên tiếp.

#### Patch

- [x] [Review][Patch] Module-level circuit breaker dùng `asyncio.Lock` — `_consecutive_failures`/`_circuit_open_until` bị chia sẻ giữa các coroutine đồng thời, có thể reset/sập circuit sai. `[scraper.py:24-25,468-472,527-528,580-581]`
- [x] [Review][Patch] Dùng config `TOPCV_USER_AGENT` thay vì `VIETNAMWORKS_USER_AGENT` trong `_user_agent_for_attempt`. `[scraper.py:475-479]`
- [x] [Review][Patch] Bỏ qua job card khi thiếu `data-job-id` hoặc `source_url` để tránh `id: "topcv:"` và URL rỗng. `[scraper.py:340,352-354]`
- [x] [Review][Patch] `_clean_url` xử lý đúng URL tương đối / thiếu netloc để không tạo `https:///path`. `[scraper.py:74-80]`
- [x] [Review][Patch] Thêm unit test cho retry, backoff, circuit breaker, và `_validate_search_page`. `[tests/unit/proprietary/platforms/topcv/test_scraper.py]`

#### Defer

- [x] [Review][Defer] Partial degraded billing — `_scrape` trả `degraded=True` kèm `cost_micros`, nhưng billing service có thể không charge. Cần align ở story billing/orchestrator. `[scraper.py:682-696]`
- [x] [Review][Defer] UA rotation trên detail fetch — `WebCrawlerConnector.crawl_url()` không nhận `useragent`. `[scraper.py:588-590]`
- [x] [Review][Defer] Anti-bot screenshot escalation bị gating bởi `ctx.run_id` (None trong sync path). `[executor.py:40-53]`
- [x] [Review][Defer] Legal block là static env flag, chưa hook runtime legal service. `[scraper.py:624-625,706-707]`
