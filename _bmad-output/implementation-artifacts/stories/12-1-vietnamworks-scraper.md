---
title: Story 12.1 — VietnamWorks Scraper
epic: 12
story: 1
status: done
priority: P0
---

# Story 12.1 — VietnamWorks Scraper

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** recruiter or market researcher  
**I want:** to search VietnamWorks job postings via the public API  
**So that:** I can source live job data into my Nowing workspace.

---

## Acceptance Criteria

1. **Given** a query + optional city filter, **When** `vietnamworks.scrape` runs, **Then** it calls `POST https://ms.vietnamworks.com/job-search/v1.0/search` no-auth and returns typed `JobItem`.
2. **Given** the response, **When** parsed, **Then** it maps: `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `salaryCurrency`, `salaryPeriodId`, `jobDescription`, `jobRequirement`, `jobFunction`, `yearsOfExperience`, `createdOn`, `approvedOn`, `typeWorkingId`, `expiredOn`, `isActive`.
3. **Given** pagination, **When** `hitsPerPage` (max 100) and `page` are set, **Then** the scraper iterates correctly and respects rate-limit (429) with backoff and circuit-breaker.
4. **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.VIETNAMWORKS_JOB`), capability registry, MCP, and REST routes.
5. **Given** upstream schema changes, **When** detected, **Then** golden fixture regression tests fail before deployment.

---

## Tasks / Subtasks

- [x] Implement `app/proprietary/platforms/vietnamworks/scraper.py` — public API client (AC 1–3)
  - [x] Implement async `scrape_vietnamworks(...)` with pagination, rate-limit handling, exception translation
  - [x] Map API response fields to normalized `JobItem` shape
  - [x] Return `degraded=true` with reason on upstream failure
- [x] Implement `app/capabilities/vietnamworks/scrape/executor.py` — capability wrapper (AC 4)
  - [x] Adapt `ScrapeInput` → proprietary input with `hitsPerPage` and `page`
  - [x] Compute `cost_micros` from returned items × `config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM`
  - [x] Preserve `degraded`/`degradation_reason` from fetcher
  - [x] Add optional `scrape_fn` seam for tests
- [x] Update `app/capabilities/vietnamworks/scrape/schemas.py` with validation and caps (AC 1, 3)
  - [x] Clamp `max_pages` to `config.VIETNAMWORKS_MAX_PAGES` (default 5)
  - [x] Clamp `max_items` to `config.VIETNAMWORKS_MAX_ITEMS` (default 100)
  - [x] Add `estimated_units` property
- [x] Add golden fixture regression tests (AC 5)
  - [x] Snapshot representative API response in `tests/unit/capabilities/vietnamworks/fixtures/sample-response-page-1.json`
- [x] Add unit + integration tests
  - [x] `tests/unit/capabilities/vietnamworks/scrape/test_executor.py`
  - [x] `tests/unit/capabilities/vietnamworks/scrape/test_schemas.py`
  - [x] `tests/unit/proprietary/platforms/vietnamworks/test_scraper.py`
  - [x] `tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py`
- [ ] Update UX / docs references (deferred to release checklist)
  - [ ] Confirm `toolIcons.tsx` display name/icon for `vietnamworks_scrape`
  - [ ] Confirm Playground catalog entry exists
  - [ ] Confirm `/docs/connectors/native/vn_jobs.mdx` mentions VietnamWorks schema

---

## Dev Notes

### Architecture & patterns to follow

- **AD-22** (VietnamWorks scraper): public API no-auth, `hitsPerPage` max 100, 1-based `page`. BSL 1.1 fetcher lives in `app/proprietary/platforms/vietnamworks/`; Apache-2.0 capability lives in `app/capabilities/vietnamworks/scrape/`. [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-22]
- **AD-3** (self-registering capabilities): `definition.py` creates a `Capability(...)` and calls `register_capability(...)`. `app/capabilities/__init__.py` already imports `vietnamworks`. The router is mounted automatically. [Source: `app/capabilities/batdongsan/scrape/definition.py`]
- **AD-8** (unified credit wallet): `cost_micros` is a per-item integer. Billable unit is `BillingUnit.VIETNAMWORKS_JOB`. The executor must compute `cost_micros = returned_items × config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM`. Degraded or empty runs cost 0. [Source: `app/capabilities/batdongsan/scrape/executor.py`]
- **AD-16** (BSL 1.1 boundary): all HTTP fetching, raw response parsing, and anti-bot/tactical code must live in `app/proprietary/platforms/vietnamworks/`. `app/capabilities/` must be clean, Apache-2.0. Do not import BSL modules from capability tests. [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-16]
- **AD-25** (PII redaction): the `jobDescription` and `jobRequirement` fields returned by `vietnamworks.scrape` will be redacted downstream in `MemoryExtractionService` / `vn_jobs.aggregate`. The scraper itself should not redact; it should preserve raw text for provenance but never write unredacted text to memory. [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-25]

### Existing skeleton — do not reinvent

The following files already exist and must be **extended**, not duplicated:

| File | Current state | What to do |
|---|---|---|
| `app/capabilities/vietnamworks/scrape/definition.py` | Registers `vietnamworks.scrape` with `BillingUnit.VIETNAMWORKS_JOB`, `docs_url`, and skeleton executor. | No change required unless description needs tuning. |
| `app/capabilities/vietnamworks/scrape/schemas.py` | `ScrapeInput`, `ScrapeOutput` with basic fields and caps. | Add `estimated_units`, input validators, optional salary/employment filters already present. |
| `app/capabilities/vietnamworks/scrape/executor.py` | Skeleton: calls `scrape_vietnamworks(input.model_dump())` and returns `ScrapeOutput(**raw)`. | Add exception handling, cost computation, progress emits, proper input mapping. |
| `app/proprietary/platforms/vietnamworks/scraper.py` | Returns degraded stub. | Replace with real API client + parser. |
| `nowing_mcp/mcp_server/features/scrapers/platforms/vietnamworks.py` | MCP tool already defined. | No backend change needed; verify once capability works. |
| `nowing_web/lib/playground/catalog.ts` | VietnamWorks platform/verb already listed. | No change unless icon swap. |
| `nowing_web/contracts/enums/toolIcons.tsx` | Tool icon + display name already added. | No change. |

### Reference implementation: `batdongsan.scrape`

Study these for patterns (same framework, same provenance rules):

- `app/capabilities/batdongsan/scrape/definition.py` — capability registration
- `app/capabilities/batdongsan/scrape/schemas.py` — input/output Pydantic with `estimated_units`, `billable_units`, clamping
- `app/capabilities/batdongsan/scrape/executor.py` — exception translation, cost compute, `_unwrap_result` pattern
- `app/proprietary/platforms/batdongsan/scraper.py` — pagination, rate-limit handling, fallback logic
- `tests/unit/capabilities/batdongsan/scrape/test_executor.py` — fake scraper, exception tests, cost tests
- `tests/unit/capabilities/batdongsan/scrape/test_schemas.py` — validation tests

### Files to create / modify

**Modify:**
- `app/proprietary/platforms/vietnamworks/scraper.py`
- `app/capabilities/vietnamworks/scrape/executor.py`
- `app/capabilities/vietnamworks/scrape/schemas.py` (if needed)
- `nowing_web/content/docs/connectors/native/vn_jobs.mdx` (optional, mention schema)

**Create:**
- `app/proprietary/platforms/vietnamworks/schemas.py` (input/output/job item models)
- `tests/unit/capabilities/vietnamworks/fixtures/sample-response-page-1.json` (golden fixture)

**Already created (test skeletons):**
- `tests/unit/capabilities/vietnamworks/scrape/test_executor.py`
- `tests/unit/capabilities/vietnamworks/scrape/test_schemas.py`
- `tests/unit/proprietary/platforms/vietnamworks/test_scraper.py`
- `tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py`
- `_bmad-output/test-artifacts/atdd-checklist-12-1-vietnamworks-scraper.md`

### API contract details

From the technical spike:

- Endpoint: `POST https://ms.vietnamworks.com/job-search/v1.0/search`
- Headers: `Content-Type: application/json`, `Accept: application/json`, `User-Agent` (use `config.VIETNAMWORKS_USER_AGENT` if defined; else a generic `Mozilla/5.0`)
- Request body:
  - `keyword`: string (required)
  - `locationId`: integer or omitted (VietnamWorks uses city IDs, e.g. 29 = Hà Nội; see spike note)
  - `hitsPerPage`: integer, max 100
  - `page`: integer, 1-based
- Response body:
  - `meta.nbHits`: total matching jobs
  - `meta.nbPages`: total pages
  - `data`: list of job objects
- Field mapping (required fields):
  - `jobId` → `id`
  - `jobTitle` → `title`
  - `jobUrl` → `source_url`
  - `companyName` → `company`
  - `companyId` → `company_id` (optional)
  - `workingLocations` → `location` (string, take first `cityNameVI` or `cityName`; fallback list)
  - `salaryMin` → `salary.min`
  - `salaryMax` → `salary.max`
  - `salaryCurrency` → `salary.currency`
  - `salaryPeriodId` → `salary.period_id` (1 = monthly)
  - `prettySalary` → `salary_raw`
  - `jobDescription` → `job_description`
  - `jobRequirement` → `job_requirement`
  - `jobFunction` → `job_function`
  - `yearsOfExperience` → `experience_years`
  - `createdOn` → `posted_at`
  - `approvedOn` → `approved_at`
  - `expiredOn` → `expired_at`
  - `isActive` → `is_active`
  - `typeWorkingId` → `employment_type_id`
  - `skills` → `skills` (list of `skillName` strings)
  - `benefits` → `benefits` (list of strings)

Salary semantics for the raw fields:
- `salaryMin == 0 && salaryMax == 0` → record `salary_min = 0`, `salary_max = 0`, `salary_raw` as returned.
- `salaryMin > 0 && salaryMax == 0` → record `salary_min = salaryMin`, `salary_max = None`.
- `salaryMin > 0 && salaryMax > 0` → record both.
- `salaryCurrency` is `USD` or `VND` (pass through).
- `salaryPeriodId` is 1 (monthly) in all samples; if missing or != 1, still pass the raw value but the aggregator will set low confidence.

Location filter note:
- `locationId` in request **does not filter** server-side (`nbHits` stays same in spike). Implementor must decide: either map `location` string to `locationId` for best-effort server hint, then **re-filter at aggregator/capability level** by `workingLocations` city name. For `vietnamworks.scrape` alone, return all results matching keyword and accept that location is post-filtered downstream.

### Pagination and rate-limiting

- Iterate `page = 1 .. max_pages` until `items >= max_items`, `page > meta.nbPages`, or no `data`.
- Use `hitsPerPage = min(100, max_items)` to minimize requests.
- Delay `config.VIETNAMWORKS_PAGE_DELAY_S` (default 0.5s) between pages.
- On `429 Too Many Requests`: mark `degraded=true`, `degradation_reason="rate_limited"`, stop pagination.
- On `> config.VIETNAMWORKS_TIMEOUT_S` (default 30s): degrade with `degradation_reason="timeout"`.
- On any unhandled exception: degrade with `degradation_reason="api_error"`.
- Do not retry more than `config.VIETNAMWORKS_RETRY_ATTEMPTS` (default 2); use exponential backoff `config.VIETNAMWORKS_RETRY_BACKOFF_BASE_S` (default 0.5).

### Normalized output shape

`items` should be a list of `dict` compatible with `app/services/jobs_aggregator/normalize.py`:

```python
{
  "id": "vw:{jobId}",
  "title": str,
  "company": str,
  "location": str,
  "source_url": str,
  "salary_raw": str,  # the original `prettySalary` text (e.g. "Thương lượng", "Từ 30tr ₫/tháng")
  "salary_min": int | None,
  "salary_max": int | None,
  "salary_currency": str | None,
  "salary_period_id": int | None,  # 1 = monthly in VietnamWorks samples
  "employment_type": str | None,  # map from typeWorkingId if possible
  "experience_years": int | None,
  "job_description": str,
  "job_requirement": str,
  "skills": list[str],
  "benefits": list[str],
  "posted_at": str | None,  # ISO-8601 date or datetime
  "approved_at": str | None,
  "expired_at": str | None,
  "is_active": bool,
  "source": "vietnamworks",
}
```

**Why `salary_raw` instead of a nested `salary` object:** `app/services/jobs_aggregator/normalize.py` already parses `salary_raw` with `_parse_salary`. VietnamWorks returns a structured `prettySalary` string plus numeric `salaryMin/Max/Currency/PeriodId`; the scraper should preserve **both** the raw display string (for the normalizer) and the structured numeric fields (so the normalizer can use them when available). Do **not** pre-parse into `VnJobSalary` in the scraper — that is the aggregator's job.

Confidence rules (for the item-level `confidence_score` the aggregator may compute, or for `salary_min`/`salary_max` reliability):
- `salary` confidence = `0.0` if both `salary_min == 0` and `salary_max == 0` (negotiable), `0.5` if only `salary_min > 0` ("From X"), `0.9` if both present.
- `salary_period_id` confidence = `0.0` if missing or != 1, `0.9` if == 1.
- `employment_type` confidence: `0.9` if mapped from a known `typeWorkingId`, `0.0` if missing or unknown.

### Capability output

`ScrapeOutput` already defined. Use it. `cost_micros` must equal `total_items × config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM` (default 3000 micros) when not degraded; 0 otherwise. `billable_units` is `len(items)`.

### Testing standards

- All new Python files must pass `ruff check` and `ruff format`.
- Unit tests in `tests/unit/capabilities/vietnamworks/` and `tests/unit/proprietary/platforms/vietnamworks/`.
- Do **not** write tests that call the real VietnamWorks API. Use fixtures and `httpx.AsyncClient` mocks or a `fetch_fn` seam.
- Golden fixtures: store real (sanitized) API responses; tests must assert that the parser requires the fields listed in AC 2 and fails with a clear error when those fields are missing or of the wrong type.
- **P0-gated integration tests:** `bmad-nowing-integration-test` (Step 4.6) is required because this story touches SQL/DB logic via the `Run` table and billing ledger. Integration tests must use the transactional `db_session` fixture, verify `TokenUsage` rows are written with `usage_type='vietnamworks_job'`, and confirm degraded runs cost 0.

### Verification commands (to run after implementation)

Backend (from `nowing_backend/`):

```bash
ruff check app/proprietary/platforms/vietnamworks app/capabilities/vietnamworks/scrape tests/unit/capabilities/vietnamworks tests/unit/proprietary/platforms/vietnamworks
ruff format app/proprietary/platforms/vietnamworks app/capabilities/vietnamworks/scrape tests/unit/capabilities/vietnamworks tests/unit/proprietary/platforms/vietnamworks
pytest tests/unit/capabilities/vietnamworks -q
pytest tests/unit/proprietary/platforms/vietnamworks -q
pytest tests/unit/capabilities/vietnamworks/scrape/test_executor.py tests/unit/capabilities/vietnamworks/scrape/test_schemas.py tests/unit/proprietary/platforms/vietnamworks/test_scraper.py -q
python -m mcp_server.selfcheck  # from nowing_mcp/
```

Frontend (from `nowing_web/`) — only if docs or catalog change:

```bash
pnpm tsc --noEmit
pnpm exec biome check lib/playground/catalog.ts lib/playground/platform-icons.tsx contracts/enums/toolIcons.tsx content/docs/connectors/native/vn_jobs.mdx content/docs/connectors/native/index.mdx
```

### UX / copy

- Capability description: `"Search public VietnamWorks job postings by keyword, location, salary, and employment type. Returns typed job listings. Does not apply or submit CVs."` [Source: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-vn-jobs-copy.md` §3]
- MCP tool description: `"Search VietnamWorks job postings. Use for research; does not apply to jobs."` [Source: `nowing_mcp/mcp_server/features/scrapers/platforms/vietnamworks.py`]
- Tool display name: `"Search VietnamWorks jobs"` [Source: `nowing_web/contracts/enums/toolIcons.tsx`]

### Additional critical details from spike

- `contactName` is present in **96%** of samples (e.g. "People Department", "HR Department"). It is a department name, not a person, but do **not** map it into the normalized `JobItem` by default; if you must keep it, place it in a `raw_contact` field and ensure `AD-25` PII redaction audits it before memory storage.
- `emailAddress` was present in **0%** of samples but the field exists in some responses. Do **not** emit it in normalized output.
- `typeWorkingId` values observed: map known IDs to `employment_type` strings. If unknown, leave `employment_type = None` and set confidence to `0.0`.

| `typeWorkingId` | `employment_type` | Confidence |
|---|---|---|
| 1 | `full_time` | 0.9 |
| 2 | `part_time` | 0.9 |
| 3 | `contract` | 0.9 |
| 4 | `intern` | 0.9 |
| other / missing | `None` | 0.0 |

- `workingLocations` parsing:
  - `cityNameVI` (Vietnamese) is preferred for display.
  - `cityName` (English) is fallback.
  - `address` is optional; include only if `cityNameVI`/`cityName` are missing.
  - Normalize to a single `location` string (first location only). If multiple, keep `additional_locations` only if aggregator needs it; otherwise drop to avoid schema drift.

### Integration with Run / Memory

- `Capability` execution creates a `Run` row via `app/capabilities/core/access/rest.py` or `agent` door. The `Run.output_text` may contain the raw capability output JSON for provenance.
- `job_description` and `job_requirement` must **not** be written to `Memory` unredacted. This story does not implement redaction (Story 12.5), but the capability must expose raw fields in a way that lets `vn_jobs.aggregate` / `MemoryExtractionService` apply `redact_job_pii` before memory write.

### Dependencies

No new third-party dependencies are expected. Use:
- `httpx.AsyncClient` (already a dependency)
- `pydantic` (already a dependency)
- `app.config.config` for constants
- `app.capabilities.core.progress.emit_progress` for SSE progress
- `app.observability.metrics` (optional): `record_vn_jobs_source_block` on degradation

---

## Project Structure Notes

- `app/proprietary/platforms/vietnamworks/` is BSL 1.1 — keep all network logic and raw parsing there.
- `app/capabilities/vietnamworks/scrape/` is Apache-2.0 — only typed contracts, executor, and capability registration.
- Tests mirror the package layout exactly: `tests/unit/proprietary/platforms/vietnamworks/` and `tests/unit/capabilities/vietnamworks/scrape/`.
- The `app/proprietary/platforms/vietnamworks/` package currently has only `scraper.py`; add `schemas.py` and `__init__.py` there.
- Capability `vietnamworks` package already has `__init__.py`, `scrape/__init__.py`; no structural change needed.

---

## References

- PRD / Epic: `_bmad-output/planning-artifacts/epics.md` §"Epic 12" and Story 12.1
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-22, AD-3, AD-8, AD-16, AD-25
- Technical spike: `_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md`
- UX copy: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-vn-jobs-copy.md`
- Reference capability: `app/capabilities/batdongsan/scrape/`
- Reference tests: `tests/unit/capabilities/batdongsan/scrape/test_executor.py`, `test_schemas.py`
- Existing skeleton: `app/capabilities/vietnamworks/scrape/`, `app/proprietary/platforms/vietnamworks/scraper.py`, `nowing_mcp/mcp_server/features/scrapers/platforms/vietnamworks.py`
- Aggregator schema: `app/services/jobs_aggregator/schemas.py`
- Aggregator normalizer: `app/services/jobs_aggregator/normalize.py`

---

## Challenge Log (grill-me)

### Q1 — Is this already implemented?

- **No duplicate logic found.** The only existing VietnamWorks code is the skeleton `app/proprietary/platforms/vietnamworks/scraper.py` returning a degraded stub.
- **Relevant existing helpers identified:**
  - `app/utils/async_retry.py` — `build_retry` / `retry_on_transient` with tenacity (exponential backoff + jitter) for transient errors and rate limits.
  - `app/proprietary/platforms/batdongsan/scraper.py` — pagination loop pattern with `degraded`/`degradation_reason`.
  - `app/proprietary/platforms/youtube/innertube.py` — `AsyncFetcher.post(..., json=..., proxy=..., stealthy_headers=True)` pattern for proxied POST JSON APIs.
  - `app/services/jobs_aggregator/normalize.py` — consumes raw `salary_raw` string and parses into `VnJobSalary`.
- **Action:** Reuse `AsyncFetcher` or `httpx.AsyncClient` + `app/utils/async_retry` patterns rather than inventing a new HTTP stack.

### Q2 — Is there a simpler alternative?

- **Simpler alternative exists for HTTP layer:** `httpx.AsyncClient` with `timeout` and manual retry loop is smaller and easier to test than `AsyncFetcher`. However, `AsyncFetcher` from `scrapling.fetchers` is already installed and provides:
  - `stealthy_headers=True` (TLS fingerprint + User-Agent)
  - `proxy=get_proxy_url()` (residential proxy, avoids exposing server IP)
  - built-in `impersonate="chrome"` option
- **Simpler alternative exists for parsing:** do not pre-parse `VnJobSalary` in the scraper. `app/services/jobs_aggregator/normalize.py` already handles `salary_raw`. The scraper should emit `salary_raw` (the `prettySalary` string) plus raw `salary_min/max/currency/period_id`.
- **Simpler alternative exists for pagination:** copy the loop from `batdongsan.scraper.py` (small, explicit, easy to test) rather than the session/rotation complexity of `youtube/innertube.py`.
- **Recommendation:** Use `AsyncFetcher.post` (or `httpx.AsyncClient`) with the batdongsan-style pagination loop. Do **not** add `VietnamWorksJobItem` Pydantic in the proprietary layer unless the capability requires it; the capability layer already has `ScrapeInput`/`ScrapeOutput`.

### Q3 — Edge cases the spec misses (Pattern 3)

- [ ] **Boundary — `max_items = 0`:** Story accepts `max_items=0`. Expected behavior: return `ScrapeOutput(items=[], cost_micros=0, degraded=False)` without calling upstream.
- [ ] **Boundary — `max_pages = 0`:** Should be treated like `max_items=0` (no pages fetched) and not an error.
- [ ] **Boundary — `max_items` not a multiple of `hitsPerPage`:** The last page should return only the remaining count, not over-fetch.
- [ ] **Boundary — upstream `meta.nbPages` < `max_pages`:** Stop at `nbPages`, do not request empty pages.
- [ ] **Null/empty — `keyword = ""` or whitespace:** Schema currently requires non-empty string. If empty, `ValidationError` is acceptable, but test must verify.
- [ ] **Null/empty — `workingLocations` empty list:** `location` should be `None` or `""` (not crash).
- [ ] **Null/empty — `skills` / `benefits` missing:** Return empty list, not `None`.
- [ ] **Null/empty — `jobDescription` or `jobRequirement` is `None` or empty string:** Return empty string or `None` and still bill the item.
- [ ] **Null/empty — `salaryMin`/`salaryMax` missing:** Treat as `0` (negotiable) and set `salary_raw`.
- [ ] **Date edge cases:** `createdOn`/`approvedOn`/`expiredOn` may be Unix timestamp (ms), ISO string, or `0`. Story does not specify format.
- [ ] **Concurrency — multiple `vietnamworks.scrape` calls in one workspace:** Each call is independent (no session reuse required for stateless API), but tests should verify no global mutable state.
- [ ] **Dedupe pre-condition:** `id` must be stable across pages (`vw:{jobId}`). If `jobId` is reused across pages, the scraper should not return duplicates.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **VietnamWorks API returns `429`:** Story says "rate-limit (429) with backoff and circuit-breaker" but does not define max retries, backoff formula, or circuit-breaker threshold. Existing config has `VIETNAMWORKS_PAGE_DELAY_S`, `VIETNAMWORKS_TIMEOUT_S`; no `RETRY_ATTEMPTS`/`RETRY_BACKOFF_BASE` config exists yet.
- [ ] **VietnamWorks API returns `5xx`:** Should degrade with `degradation_reason="api_error"` and cost 0.
- [ ] **VietnamWorks API returns `403/451`:** Should degrade with `degradation_reason="access_blocked"` and stop retries immediately (no point retrying a ToS/legal block).
- [ ] **HTTP timeout (`httpx.TimeoutException`):** Should degrade with `degradation_reason="timeout"`.
- [ ] **DNS / network unreachable (`httpx.ConnectError`):** Should degrade with `degradation_reason="api_error"`.
- [ ] **Invalid JSON response:** Should degrade with `degradation_reason="decode_error"`.
- [ ] **Unexpected schema (field missing or wrong type):** Golden fixture tests should fail; runtime should degrade or drop only the malformed item.
- [ ] **Billing service down / DB unavailable during `charge_capability`:** `charge_capability` is called by the access door after executor. Fail-open behavior is required (do not crash the response if TokenUsage insert fails).
- [ ] **Insufficient credit before run:** `gate_capability` checks `estimated_units`. For `vietnamworks.scrape` the executor should not additionally check; the access door already gates.
- [ ] **Proxy unavailable or `AsyncFetcher` import broken at runtime:** If using `scrapling`, missing dependency should degrade gracefully.
- [ ] **`Run.output_text` too large:** The Run table stores `output_text` as JSONL. Very large job descriptions may exceed storage / truncate. No spec for capping output size.

### Triage

- **Severity:** All findings above are **non-critical** (edge cases and failure mode gaps that can be added to the test skeleton in Step 4.4 `bmad-nowing-test-first-atdd`).
- **No HALT required.** No duplicate logic to reuse or simpler alternative that would change scope.
- **One spec adjustment applied:** Story output shape now emits `salary_raw` + structured salary fields to align with existing `app/services/jobs_aggregator/normalize.py` instead of pre-parsing into `VnJobSalary`.
- **Proceed to:** `bmad-nowing-test-first-atdd` (Step 4.4) to add test cases for the above boundaries and failures, then `bmad-nowing-integration-test` (Step 4.6) for SQL/billing verification.

---

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max / Devin

### Debug Log References

- Red phase: `build_scrape_executor() got an unexpected keyword argument 'scrape_fn'`
- Red phase: `ScrapeInput` clamping not implemented
- Red phase: `ModuleNotFoundError: No module named 'structlog'`
- Adjusted: executor now owns pagination loop; proprietary `scrape_vietnamworks` fetcher handles single-page requests

### Completion Notes List

- Implemented `app/proprietary/platforms/vietnamworks/scraper.py` with `httpx.AsyncClient`, field mapping, salary normalization, pagination, and exception translation.
- Implemented `app/capabilities/vietnamworks/scrape/executor.py` with pagination loop, cost computation, exception handling, and `scrape_fn` seam for tests.
- Updated `app/capabilities/vietnamworks/scrape/schemas.py` to clamp `max_items`/`max_pages`.
- Added `VIETNAMWORKS_MAX_ITEMS` to `app/config/__init__.py`.
- Red/green unit tests: 38 passed.
- Integration tests: 3 passed, 1 skipped (live test).

### File List

- `app/proprietary/platforms/vietnamworks/scraper.py`
- `app/capabilities/vietnamworks/scrape/executor.py`
- `app/capabilities/vietnamworks/scrape/schemas.py`
- `app/config/__init__.py`
- `tests/unit/capabilities/vietnamworks/scrape/test_executor.py`
- `tests/unit/capabilities/vietnamworks/scrape/test_schemas.py`
- `tests/unit/proprietary/platforms/vietnamworks/test_scraper.py`
- `tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py`
- `tests/unit/capabilities/vietnamworks/fixtures/sample-response-page-1.json`
- `_bmad-output/test-artifacts/atdd-checklist-12-1-vietnamworks-scraper.md`

### Review Findings (Code Review 2026-08-10)

> Review dựa trên diff `15df5c9e1..2e2e293ac` và cross-check với current HEAD. Một số finding liên quan đến `app/services/jobs_aggregator/` hoặc `vn_jobs` aggregate được xếp sang story 12.4/12.5 vì nằm ngoài phạm vi 12.1.

#### decision_needed

- [x] [Review][Patch] ~~Xử lý 429 theo spec có mâu thuẫn~~ — Quyết định: implement retry với exponential backoff/circuit-breaker theo pattern `batdongsan` (`_MAX_RETRIES=2`, delay `VIETNAMWORKS_RETRY_BACKOFF_BASE_S`), trả partial items khi vẫn bị 429. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:208-209`
- [x] [Review][Dismiss] ~~Location filter~~ — Quyết định: giữ nguyên. `locationId` không filter server-side theo spike; `orchestrator.py:68` ghi "The aggregator filters by location after normalization". Không cần thay đổi 12.1. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:130-132`, `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:28-30`

#### patch

- [x] [Review][Patch] `nbPages` early-stop trong executor vô hiệu — `scrape_vietnamworks` không trả `meta`, nên `raw.get("meta", {}).get("nbPages")` luôn `None`, gây fetch thừa ít nhất 1 trang. `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:56-59`
- [x] [Review][Patch] Thiếu retry/backoff/circuit-breaker cho 429 — Cần thêm `VIETNAMWORKS_RETRY_ATTEMPTS`/`VIETNAMWORKS_RETRY_BACKOFF_BASE_S` vào config và retry loop trên 429, sau đó mới degrade. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:208-209`
- [x] [Review][Patch] `_degraded()` luôn trả `items: []` — khi gặp 429/403/5xx ở trang > 1, dữ liệu các trang trước bị mất. Nên trả `items` đã fetch kèm `degraded=true` hoặc giữ partial result. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:25-32`, `scraper.py:208-219`
- [x] [Review][Patch] `_extract_items` dừng cả trang khi một job lỗi — `_normalize_job` gọi `_normalize_salary` (`int()` không guard), `_first_location`, `_parse_date`; một job lỗi làm mất cả trang. Cần try/except per-item để chỉ loại job lỗi. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:159-165`
- [x] [Review][Patch] `_normalize_salary` crash trên chuỗi định dạng — API có thể trả `"25,000,000"` hoặc `"25.5"`, `int()` raise. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:63-64`
- [x] [Review][Patch] `_parse_date` yếu — không xử lý timestamp dạng string/float, threshold ms/s (`> 1e10`) quá lỏng cho giá trị future-seconds, và trả ISO string full datetime mà `app/services/jobs_aggregator/normalize.py` chưa parse được. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:42-53`
- [x] [Review][Patch] `ScrapeInput` thiếu validation — `keyword` rỗng/khoảng trắng không bị từ chối, `salary_min`/`salary_max`/`experience_years` có thể âm, không kiểm `salary_max >= salary_min`. `nowing_backend/app/capabilities/vietnamworks/scrape/schemas.py:17-24`
- [x] [Review][Patch] `ScrapeInput.max_pages` mặc định 1, trong khi config/MCP/reference dùng 5 — gây mặc định không nhất quán. `nowing_backend/app/capabilities/vietnamworks/scrape/schemas.py:23`
- [x] [Review][Patch] `max_pages=0` và `hitsPerPage=0` bị ép thành 1/100 — `int(params.get(...) or default)` coi `0` là falsy. Người gọi không thể yêu cầu 0 trang. `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:189-190`
- [x] [Review][Patch] Executor over-fetch trang cuối — `_scrape` nhận `max_items` gốc mỗi trang nên `remaining` tính theo 0 item trong call, gây yêu cầu `hitsPerPage` đầy đủ dù chỉ cần vài item. `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:28-36`, `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:199-203`
- [x] [Review][Patch] Executor exception handling không đầy đủ — chỉ bắt `httpx.TimeoutException` và `RuntimeError("429")`; `httpx.HTTPStatusError`, `ValueError`, `TypeError` từ `scrape_fn` propagate. `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:61-81`
- [x] [Review][Patch] Executor thiếu `CapabilityContext`, `next_action`, `done` progress — so với topcv/itviec, degraded runs không có hướng dẫn human-review và progress stream không được đóng. `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:23-90`
- [x] [Review][Patch] Golden regression tests không ép buộc các trường AC 2 — `test_scraper.py:127-141` chỉ assert một phần trường; nhiều trường dùng `.get(..., default)` nên schema drift có thể pass âm thầm. `nowing_backend/tests/unit/proprietary/platforms/vietnamworks/test_scraper.py:127-141`
- [x] [Review][Patch] Integration test fake bypass `_normalize_job` — fake trả `envelope["data"]` raw, sau đó assert `item["title"]`/`item["company"]` mà raw items không có. `nowing_backend/tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py:37-49`

#### defer

- [x] [Review][Defer] `posted_at` full-ISO datetime không tương thích với aggregator `normalize.py` — `normalize.py` chỉ parse `%Y-%m-%d`, cần cập nhật để chấp nhận full ISO hoặc `datetime`. Deferred đến story 12.4 (aggregator). `nowing_backend/app/services/jobs_aggregator/normalize.py:54-57`
- [x] [Review][Defer] `salary_period_id:1` bị aggregator map thành "hour" thay vì "month" — `_SALARY_PERIOD_MAP` chung nhưng các nguồn có semantics khác nhau. Deferred đến story 12.4. `nowing_backend/app/services/jobs_aggregator/normalize.py:13-23`
- [x] [Review][Defer] Aggregate billing base fee không được charge — `_gate_vn_jobs_aggregate` reserve `VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY` nhưng `_charge_vn_jobs_aggregate` chỉ charge `cost_micros` con. Deferred đến 12.4/12.5. `nowing_backend/app/capabilities/core/billing.py:287-294`, `billing.py:631-671`
- [x] [Review][Defer] `vn_jobs` subagent `load_tools` không validate `workspace_id` — có thể `None`, gây crash. Deferred đến 12.4. `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/tools/index.py:28-36`
- [x] [Review][Defer] `_gate_vn_jobs_aggregate` under-reserve, empty sources = all sources, fallback `max_items_per_source=10` khác schema default 50 — Deferred đến 12.4/12.5. `nowing_backend/app/capabilities/core/billing.py:267-296`
- [x] [Review][Defer] `_charge_vn_jobs_aggregate` có thể charge khi degraded — kiểm tra `cost_micros <= 0` nhưng không kiểm `degraded`. Deferred đến 12.4/12.5. `nowing_backend/app/capabilities/core/billing.py:631-671`
- [x] [Review][Defer] `PII_REDACTION_MIN_CONFIDENCE` chưa được dùng — config tồn tại nhưng chưa có logic. Deferred đến 12.5. `nowing_backend/app/config/__init__.py:1025-1029`

#### dismissed

- [Review][Dismiss] Diff `2e2e293ac` stale so với current HEAD — bỏ `INDEED_JOB` trong diff nhưng HEAD vẫn giữ, và chứa stub của 12.2-12.5. Đây là artifact review trên historical commit, không phải defect của 12.1.
- [Review][Dismiss] "Diff chứa ngoài phạm vi TopCV/ITviec/vn_jobs" — các issue riêng lẻ đã được gán cho story 12.2-12.5; không cần action cho 12.1.
