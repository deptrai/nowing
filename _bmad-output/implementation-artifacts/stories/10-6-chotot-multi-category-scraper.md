---
baseline_commit: null
---

# Story 10.6: Chợ Tốt Multi-Category Scraper

Status: ready-for-dev

## Story

As a researcher using the Chợ Tốt scraper,
I want to scrape listings from any major vertical (`xe cộ`, `điện tử`, `việc làm`, `đồ gia dụng`, `vật nuôi`, `dịch vụ`, `thời trang`, v.v.) in addition to real estate,
So that one scraper foundation returns typed, useful data for each category instead of a BĐS-shaped record full of nulls.

## Acceptance Criteria

1. **Given** the existing Chợ Tốt BĐS scraper uses the public gateway `gateway.chotot.com/v1/public/ad-listing` with `cg` (category group) and `st` (listing type/sort) parameters,
   **When** Story 10.6 is complete,
   **Then** the fetcher supports a `category` input that maps to the correct `cg`, `st`, and detail URL origin for each supported vertical, and the BĐS `property_type` mapping keeps working without changes.

2. **Given** the category codes discovered from public Chợ Tốt gateway usage (e.g., `2010` = bất động sản bán, `2020` = bất động sản cho thuê, `4010` = xe máy, `4020` = ô tô, `5000` = điện tử, `7000` = đồ gia dụng/nội thất, `9000` = thời trang),
   **When** the mapping module is loaded,
   **Then** it exposes a deterministic lookup from stable slugs (`cars`, `motorbikes`, `electronics`, `jobs`, `home_goods`, `pets`, `fashion`, `services`) to the correct `cg` and a per-vertical `listing_type` default (`sell` / `rent` / `want_to_buy` / N/A).

3. **Given** a category slug that is not yet mapped,
   **When** the scraper runs,
   **Then** it fails fast with a clear validation error (`category_not_supported`) and does not silently fall back to BĐS.

4. **Given** each Chợ Tốt vertical uses a different public detail URL origin (`nhatot.com`, `xe.chotot.com`, `vieclamtot.com`, `www.chotot.com`, v.v.),
   **When** a listing is parsed,
   **Then** `detail_url` is built from the vertical's canonical origin and the `list_id` as `https://{origin}/{list_id}.htm` (best-effort; redirect if platform uses slug is acceptable), and is not hardcoded to `nhatot.com`.

5. **Given** the public `loadRegions` endpoint returns the shared region/area tree used by the gateway,
   **When** the scraper resolves `city`/`district` for any supported category,
   **Then** it reuses the existing `_resolve_region_v2` / `_resolve_area_v2` logic. A per-vertical region loader is added only if a real category proves the tree differs.

6. **Given** the current `ChototBdsListing` schema with BĐS-only fields (`area`, `rooms`, `floors`, `toilets`, `property_type`),
   **When** Story 10.6 is complete,
   **Then** there is a generic `ChototListing` schema with common fields (`listing_id`, `ad_id`, `title`, `price`, `price_raw`, `price_value`, `location`, `district`, `city`, `ward`, `post_date`, `thumbnail_url`, `detail_url`, `latitude`, `longitude`, `seller_type`, `phone`, `scrapedAt`) plus a per-category `attributes: dict[str, Any]` bag for vertical-specific fields.

7. **Given** raw ad JSON from the gateway contains a `category` / `category_name` field,
   **When** `parse_listing` runs,
   **Then** it routes to the correct category parser (or `parse_generic`) based on `category`/`cg` code, and returns a `ChototListing` with `category` set to a stable slug.

8. **Given** a vehicle ad from `xe.chotot.com`,
   **When** it is parsed,
   **Then** `attributes` includes `make`, `model`, `year`, `mileage`, `fuel_type`, `transmission`, `condition`, `vehicle_type` where present, and `price`/`location` come from common fields.

9. **Given** a job ad from `vieclamtot.com`,
   **When** it is parsed,
   **Then** `attributes` includes `salary_min`, `salary_max`, `salary_string`, `job_type`, `company_name`, `experience`, `education`, `benefits` where present.

10. **Given** an electronics / home goods / fashion ad,
    **When** it is parsed,
    **Then** `attributes` includes `brand`, `condition`, `warranty`, `accessories` where present; no BĐS-only fields are emitted as null.

11. **Given** the gateway returns a `cg` code that is not in the mapping table,
    **When** `parse_listing` runs,
    **Then** `parse_generic` captures the top-level scalar fields into `attributes`, sets `category="unknown"`, and the executor must mark the run `degraded=true` with `degradation_reason="unknown_category"` and **not bill** the listing (both `ChototScrapeOutput.billable_units` and `ScrapeOutput.billable_units` exclude `category="unknown"`).

12. **Given** the `phone` fetch endpoint uses the same RSA encryption for all `list_id`s,
    **When** `fetch_phone` is called for a non-BĐS listing,
    **Then** it reuses the existing encryption and returns the public phone number, or `None` if the vertical does not expose phone on the gateway.

13. **Given** a new vertical is discovered during the spike,
    **When** the vertical is added to `_CATEGORY_CONFIG`,
    **Then** ToS review for that vertical must pass before it is enabled in production.

## Tasks / Subtasks

- [ ] Spike: inspect live gateway behavior (AC #1, #2, #4, #5, #12)
  - [ ] Capture `cg` codes for P0 verticals: `cars`, `motorbikes`, `electronics`, `jobs`, `home_goods`, `pets`, `fashion`, `services`.
  - [ ] Document `st` behavior per vertical (default `st=s`; only BĐS supports `st=u` for rent; unsupported values fall back to `s` with warning) and confirm `w=1` is universal.
  - [ ] Verify `loadRegions` returns the same tree for each `cg`; if different, record which category needs a different region endpoint.
  - [ ] Verify detail URL pattern (`/{id}.htm` vs `/{slug}-{id}.htm`) for each vertical and whether bare `/{id}.htm` redirects or 404s.
  - [ ] Test `fetch_phone` with one non-BĐS `list_id` and document if RSA key/endpoint is universal.
  - [ ] If verticals split into sub-categories, record sub-`cg` and decide P0/P1.

- [ ] Refactor `app/proprietary/platforms/chotot/fetch.py` (AC #1, #2)
  - [ ] Replace hardcoded `_PROPERTY_TYPE_TO_CG` with a lightweight `_CATEGORY_CONFIG: dict[str, CategoryConfig]` keyed by stable slug.
  - [ ] Each config entry holds: `cg`, `default_listing_type`, `supported_listing_types`, `detail_origin`.
  - [ ] `_build_listing_params` accepts `category` and resolves `cg` + `st` from config, keeping `w=1` and pagination params.

- [ ] Refactor `app/proprietary/platforms/chotot/scraper.py` (AC #1, #5)
  - [ ] `scrape_chotot_bds` becomes `scrape_chotot` and accepts a `category` parameter.
  - [ ] Input schema adds `category` (required) and keeps `property_type` as optional BĐS-only sub-filter.
  - [ ] Region/area resolution reuses existing helpers; no per-vertical branch unless spike proves it.

- [ ] Add detail URL builder (AC #4)
  - [ ] Move `_build_detail_url` from `parsers.py` into a shared helper that uses `category_config.detail_origin`.
  - [ ] Validate `list_id` before building URL; return `None` for invalid IDs.

- [ ] Design generic `ChototListing` schema (AC #6)
  - [ ] Update `app/proprietary/platforms/chotot/schemas.py`:
    - `ChototListing` with `dataType: Literal["chotot_listing"]`, common fields, `category: str`, `attributes: dict[str, Any]`.
    - `ChototScrapeInput` accepts `category: str` (required) and `subcategory: str | None`.
    - `ChototScrapeOutput` returns `items: list[ChototListing]`.
  - [ ] Mark `ChototBdsListing` as **deprecated**; either make it a thin subclass/alias of `ChototListing` with `category="bds"` or remove it and fix internal consumers in this story.

- [ ] Implement category parser dispatch (AC #7)
  - [ ] Add a lightweight dispatch dict `CATEGORY_PARSERS: dict[int, Callable[[dict], ChototListing]]` in `parsers.py`.
  - [ ] `parse_listing(raw)` looks up `raw["category"]` / `cg` and dispatches; default to `parse_generic`.

- [ ] Implement per-category parsers (AC #8, #9, #10, #11)
  - [ ] `parse_vehicle` — `make`, `model`, `year`, `mileage`, `fuel_type`, `transmission`, `condition`, `vehicle_type`.
  - [ ] `parse_job` — `salary_min`, `salary_max`, `salary_string`, `job_type`, `company_name`, `experience`, `education`, `benefits`.
  - [ ] `parse_general_goods` — `brand`, `condition`, `warranty`, `accessories`.
  - [ ] `parse_generic` — copy all scalar top-level fields into `attributes`; keep `category="unknown"`.

- [ ] Price/location normalization + phone reuse (AC #6, #8, #9, #10, #12)
  - [ ] Keep `_parse_price_string`, `_format_price`, `_build_address`, `_first_image`, `_seller_type` as shared helpers.
  - [ ] Verify `fetch_phone` does not assume BĐS; document any vertical where phone is unavailable.

- [ ] Capability / MCP surface (boundary with Story 10.7)
  - [ ] `app/capabilities/chotot/scrape/definition.py` registers `chotot.scrape` with `BillingUnit.CHOTOT_ITEM`.
  - [ ] `chotot_bds.scrape` is kept as deprecated alias calling `chotot.scrape(category="bds")`.
  - [ ] `ScrapeOutput.billable_units` excludes `category="unknown"` listings.
  - [ ] Update MCP tool `nowing_mcp/mcp_server/features/scrapers/platforms/chotot.py` (or rename from `chotot_bds.py`) with the new `category` parameter and pass `mcp_server/selfcheck.py`.

- [ ] Tests
  - [ ] Unit test `category → cg` lookup, `_build_listing_params` `st`, `_build_detail_url` per origin, unsupported category validation.
  - [ ] Unit test each parser against sample raw JSON for vehicle, job, electronics.
  - [ ] Unit test generic parser for unknown `cg` returns `category="unknown"` and is not billed.
  - [ ] Unit test capability executor: `billable_units` excludes unknown-category listings.
  - [ ] Integration test real `ad-listing` call for one non-BĐS vertical and `parse_listings`.

## Previous Story Learnings

- **Story 10.1 (batdongsan):** License boundary is BSL 1.1 in `app/proprietary/platforms/` and Apache-2.0 in `app/capabilities/`; every platform needs MCP tool registration, `mcp_server/selfcheck.py` update, and a `billable_units` property on the capability output.
- **Story 10.2 (chotot BĐS):** Region cache (`_REGIONS_CACHE`) must be guarded by `asyncio.Lock`; response size caps and UA rotation prevent anti-bot blocks.
- **Story 10.5 (anti-bot escalation):** Bot/rate-limit blocks trigger `capture_platform_anti_bot_screenshot_task.delay(...)` with `run_id`, `workspace_id`, `capability`, `domain`, `block_type`.
- **Epic 10 retrospective:** Keep unit tests hermetic (fixtures, no live network); add parser-regression fixtures for each supported vertical to guard API contract drift.

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-3` — scraper capabilities self-register; capability/billing work is Story 10.7.
  - `AD-16` — `app/proprietary/platforms/chotot/` (BSL 1.1) holds mapping + parser; Apache-2.0 wrapper in `app/capabilities/chotot/scrape/` (Story 10.7).
  - `AD-19` — anti-bot escalation already wired; re-use existing `ChototBdsAccessBlockedError`, `ChototBdsRateLimitedError`, `ChototBdsBotDetectedError`. Wire `_maybe_escalate` via `capture_platform_anti_bot_screenshot_task` following the pattern from Story 10.5.
  - `AD-25` — phone numbers are PII; `fetch_phone` returns raw data, downstream `Memory`/ingestion must run `redact_pii` before storage.
  - `AD-26` — ToS review is a **hard gate** before any new vertical is enabled in production; record per-vertical ToS approval in the story.
  - `AD-34` — scraper output must be compatible with `to_chunks()` / `NowingIngestService` (`source: 'nowing_scraper'`, `metadata.domain`); this story does not implement ingestion itself.
  - `AD-35` — Nowing does not build a public/vertical search corpus; scraper output feeds `chainlens-research` if ingestion is wired later.
  - `AD-50` — Chợ Tốt Multi-Category Scraper & Capability (authoritative): single generic `scrape_chotot` actor; single `chotot.scrape` capability with `category` required; `BillingUnit.CHOTOT_ITEM` per returned listing; `ChototListing` with `attributes` bag; detail URL origins per vertical; parser dispatch with `parse_generic` fallback; unknown-category fallback listings are **not billed**.

- Source tree components to touch
  - `nowing_backend/app/proprietary/platforms/chotot/fetch.py`
  - `nowing_backend/app/proprietary/platforms/chotot/scraper.py`
  - `nowing_backend/app/proprietary/platforms/chotot/parsers.py`
  - `nowing_backend/app/proprietary/platforms/chotot/schemas.py`

- Testing standards summary
  - `tests/unit/proprietary/platforms/chotot/`
  - Sample fixtures in `tests/unit/platforms/chotot/fixtures/sample_ad_listing.json` (BĐS) plus new `vehicles.json`, `jobs.json`, `electronics.json` for non-BĐS parser tests.
  - Integration tests gated behind `SCRAPE_LIVE=1` or equivalent.

### References

- [Source: `nowing_backend/app/proprietary/platforms/chotot/fetch.py`]
- [Source: `nowing_backend/app/proprietary/platforms/chotot/scraper.py`]
- [Source: `nowing_backend/app/proprietary/platforms/chotot/parsers.py`]
- [Source: `nowing_backend/app/proprietary/platforms/chotot/schemas.py`]
- [Source: Apify Chotot Scraper docs — category codes `2010`, `2020`, `4010`, `4020`, `5000`, `7000`, `9000`]
