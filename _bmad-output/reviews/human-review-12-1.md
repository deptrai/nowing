# Human Review Gate — Story 12.1

## Reviewer
- **Reviewer:** Step 4.13 Quality Gate (AI-assisted human review)
- **Date:** 2026-08-09
- **Pipeline:** Nowing quality pipeline, Story 12.1 — VietnamWorks Scraper

## Scope
Implementation, contracts, and test coverage reviewed for the `vietnamworks.scrape` capability:

- `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py`
- `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py`
- `nowing_backend/app/capabilities/vietnamworks/scrape/schemas.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/capabilities/vietnamworks/scrape/definition.py`
- `nowing_backend/app/capabilities/core/billing.py`
- `nowing_backend/app/services/jobs_aggregator/normalize.py`
- `nowing_mcp/mcp_server/features/scrapers/platforms/vietnamworks.py`
- `nowing_backend/tests/unit/capabilities/vietnamworks/scrape/test_executor.py`
- `nowing_backend/tests/unit/capabilities/vietnamworks/scrape/test_schemas.py`
- `nowing_backend/tests/unit/capabilities/vietnamworks/scrape/test_billing.py`
- `nowing_backend/tests/unit/capabilities/vietnamworks/scrape/test_registry.py`
- `nowing_backend/tests/unit/proprietary/platforms/vietnamworks/test_scraper.py`
- `nowing_backend/tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py`
- `_bmad-output/implementation-artifacts/stories/12-1-vietnamworks-scraper.md`
- `_bmad-output/reviews/12-1-review-diff.patch`

## P0 Risk Checklist

| # | Concern | Status | Notes |
|---|---------|--------|-------|
| 1 | **Billing: `cost_micros` per returned item** | ✅ PASS | `executor.py:106` computes `len(items) * config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM`; `billing.py:535-537` charges via `billable_units` (= `len(items)`, `schemas.py:92-94`); integration test confirms correct debit. |
| 2 | **Billing: degraded/empty runs cost 0** | ✅ PASS | `scraper.py:26-35` returns `cost_micros: 0` and partial items; `executor.py:65-72, 88-103` propagates degraded with `cost_micros: 0`; `billing.py:554-574` records a 0-cost audit row on degraded output. |
| 3 | **Billing: unit wired and pre-flight gate** | ✅ PASS | `BillingUnit.VIETNAMWORKS_JOB` is present (`core/types.py:39`), mapped to `VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM` (`billing.py:53,89`); `ScrapeInput.estimated_units` equals `max_items` (`schemas.py:71-73`). |
| 4 | **Data quality: required field mapping** | ✅ PASS | Maps `jobId`, `jobTitle`, `companyName`, `workingLocations`, salary fields, dates, `typeWorkingId`, `skills`, `benefits`, `isActive` to the normalized JobItem shape (`scraper.py:153-210`). |
| 5 | **Data quality: salary parsing** | ⚠️ CONDITIONAL | Integer / formatted-thousands inputs parse correctly, but decimal strings are corrupted (see Finding F1). |
| 6 | **Data quality: date parsing** | ✅ PASS | Handles ISO-8601 (with/without time and offset) and Unix timestamps in seconds or milliseconds (`scraper.py:45-93`). |
| 7 | **Data quality: location mapping** | ✅ PASS | First location prefers `cityNameVI`, falls back to `cityName` then `address` (`scraper.py:38-42`). |
| 8 | **Data quality: schema drift handling** | ✅ PASS | Envelope-level drift degrades with `schema_drift` (`scraper.py:366-399`); malformed individual jobs are skipped without killing the page (`scraper.py:257-262`). |
| 9 | **Rate limiting: 429 retry / partial results** | ✅ PASS | Exponential backoff on 429, partial results preserved, exhausted retries degrade as `rate_limited` (`scraper.py:337-345`). |
| 10 | **Rate limiting: page pacing / other failures** | ✅ PASS | `VIETNAMWORKS_PAGE_DELAY_S` between pages, `403/451` → `access_blocked`, `5xx`/network → `api_error`, timeout → `timeout` (`scraper.py:350-402`). |
| 11 | **No hardcoded secrets** | ✅ PASS | Public endpoint and generic `User-Agent` only; no API keys, tokens, or credentials in source. |
| 12 | **No PII leakage** | ✅ PASS | `contactName`/`emailAddress` are not emitted. Raw `job_description` and `job_requirement` are passed through for provenance; downstream PII redaction is the responsibility of Story 12.5 (`jobs_aggregator`/`MemoryExtractionService`). |

## Findings

All originally identified findings have been remediated. Residual notes are captured below for transparency.

### F1 — `_to_int` decimal parsing ✅ RESOLVED
- **File:** `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py`
- **Lines:** 96–123
- **Resolution:** `_to_int` now tries `float(text.replace(",", ""))` first for single-dot decimal strings (e.g. `"25.5"` → `25`), and only removes dots when the float parse fails (e.g. `"25.000.000"` → `25000000`).

### F2 — Failing unit test `test_degrades_on_non_dict_json_response` ✅ RESOLVED
- **File:** `nowing_backend/tests/unit/proprietary/platforms/vietnamworks/test_scraper.py`
- **Line:** 742
- **Resolution:** Test now uses the literal endpoint URL; the implementation correctly returns `degradation_reason="decode_error"` for a non-dict JSON response.

### F3 — `ruff check` import-order failure in test file ✅ RESOLVED
- **File:** `nowing_backend/tests/unit/capabilities/vietnamworks/scrape/test_billing.py`
- **Resolution:** Import order fixed with `ruff check --fix`.

### F4 — `location` input is not passed to the upstream request or post-filtered ✅ BY DESIGN
- **Files:** `nowing_backend/app/capabilities/vietnamworks/scrape/executor.py:46`, `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:213-246`
- **Detail:** `ScrapeInput.location` and the MCP `location` parameter are accepted but never mapped to `locationId` or filtered by `workingLocations`. Direct callers of `vietnamworks.scrape` will receive unfiltered keyword results.
- **Impact:** Expected by design for 12.1 (deferred to `vn_jobs.aggregate` per `12-1-vietnamworks-scraper.md:157-158` and review-diff `decision_needed`); not a blocker.

### F5 — `_normalize_salary` accepts unused `raw` parameter ✅ RESOLVED
- **File:** `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py`
- **Resolution:** Removed the unused `raw` parameter from `_normalize_salary` and its call site in `_normalize_job`.

### F6 — Broad `except Exception` masks programming errors ⚠️ RESIDUAL
- **Files:** `nowing_backend/app/proprietary/platforms/vietnamworks/scraper.py:396-398, 420-422`
- **Detail:** The outer catch is `Exception` to avoid crashing the capability on unexpected errors; full tracebacks are logged. This is acceptable for a P0 public-API scraper but could be narrowed in a future hardening pass.

## Verification Run

```bash
cd nowing_backend
uv run ruff check app/proprietary/platforms/vietnamworks app/capabilities/vietnamworks/scrape tests/unit/capabilities/vietnamworks tests/unit/proprietary/platforms/vietnamworks  # ✅ passed
uv run pytest tests/unit/capabilities/vietnamworks tests/unit/proprietary/platforms/vietnamworks -q  # ✅ 73 passed
uv run pytest tests/integration/capabilities/vietnamworks/scrape/test_vietnamworks_scrape.py -q -m integration  # ✅ 3 passed, 1 skipped (SCRAPE_LIVE)
```

## Verdict

**APPROVED**

The two blocking findings (F1, F2) and the lint finding (F3) have been fixed. F4 is by design (deferred to aggregator). F5 is resolved. F6 is a residual observability note, not a P0 blocker. The capability is ready to proceed to the next quality gate.
