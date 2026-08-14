---
baseline_commit: null
---

# Story 10.7: Chợ Tốt Multi-Category Capability and Billing

Status: ready-for-dev

## Story

As a workspace owner,
I want a single `chotot.scrape` capability that accepts any supported category and bills per returned listing on the correct meter,
So that users can research Chợ Tốt vehicles, jobs, electronics, and goods without separate capabilities or mis-billed BĐS rates.

## Acceptance Criteria

1. **Given** the existing `chotot_bds.scrape` capability is registered with `BillingUnit.CHOTOT_BDS_ITEM`,
   **When** Story 10.7 is complete,
   **Then** a single generic `chotot.scrape` capability is registered with `category` as a required input, and `chotot_bds.scrape` is kept as a deprecated alias that calls `chotot.scrape(category="bds")` for backward compatibility.

2. **Given** `chotot.scrape` runs with `category=cars` and returns 12 listings,
   **When** billing is recorded,
   **Then** `TokenUsage.usage_type="chotot_item"`, `cost_micros = 12 × CHOTOT_SCRAPE_MICROS_PER_ITEM`, and `call_details` includes `category="cars"` so cost analytics can break down by vertical.

3. **Given** `chotot.scrape` runs with `category=electronics` and returns 0 listings due to a block,
   **When** the output is `degraded=true`,
   **Then** `cost_micros=0` and `degradation_reason` is preserved from the scraper.

4. **Given** `chotot.scrape` returns a listing with `category="unknown"` because the gateway returned an unmapped `cg`,
   **When** billing is computed,
   **Then** that listing is not counted in `cost_micros` and `degradation_reason="unknown_category"` is returned.

5. **Given** the pre-flight wallet gate in `gate_capability`,
   **When** `chotot.scrape` is called with `max_items=20` and `category=jobs`,
   **Then** the gate reserves `20 × CHOTOT_SCRAPE_MICROS_PER_ITEM` micros.

6. **Given** the existing `chotot_bds.scrape` API consumers (REST, agent, MCP),
   **When** the new capability is live,
   **Then** `chotot_bds.scrape` keeps working for at least one release, either as an alias to `chotot.scrape(category="bds")` or as a deprecated duplicate, and there is a migration/deprecation note in the docs.

7. **Given** the `ScrapeInput` / `ScrapeOutput` contract in `app/capabilities/chotot/scrape/schemas.py`,
   **When** the capability is registered,
   **Then** the input schema includes `category: str` with a supported-slug validator, optional `subcategory`, and the output schema includes typed `items` and `cost_micros` computed with the `chotot_item` rate.

## Tasks / Subtasks

- [x] Confirm capability & billing shape (AC #1, #2)
  - [x] Billing unit `BillingUnit.CHOTOT_ITEM` already exists.
  - [x] `CHOTOT_SCRAPE_MICROS_PER_ITEM` config and `_PLATFORM_RATE_KEYS` / `_UNIT_NOUNS` mapping already wired.

- [x] Implement or update capability definition (AC #1, #6, #7)
  - [x] `app/capabilities/chotot/scrape/definition.py` registers `chotot.scrape` and `chotot_bds.scrape` (deprecated alias).
  - [x] `app/capabilities/chotot/scrape/executor.py` accepts `category`, computes `cost_micros`, skips degraded/unknown, and calls `_maybe_escalate`.

- [ ] Update capability schemas (AC #7)
  - [ ] `ScrapeInput` in `app/capabilities/chotot/scrape/schemas.py` must make `category` required and validate against `app.proprietary.platforms.chotot.fetch._SUPPORTED_CATEGORY_SLUGS` (or raw numeric `cg`). Optional `subcategory` can be deferred.
  - [x] `ScrapeOutput` already has `cost_micros`, `degraded`, `degradation_reason`, `next_action`.
  - [x] `estimated_units` is `max_items`.

- [ ] Tests
  - [ ] Unit tests in `tests/unit/capabilities/chotot/scrape/test_executor.py` (note: path is `scrape/test_executor.py`, not `chotot/test_scrape_executor.py`):
    - `chotot.scrape` is registered with `BillingUnit.CHOTOT_ITEM`.
    - `ScrapeInput` rejects unsupported `category`.
    - `gate_capability` reserves `max_items × CHOTOT_SCRAPE_MICROS_PER_ITEM`.
    - `category="unknown"` listings are not billed.
    - `chotot_bds.scrape` still works as alias and bills at `CHOTOT_ITEM` rate (or `CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM` if kept).
  - [ ] Integration test `POST /api/v1/workspaces/{workspace_id}/scrapers/chotot/scrape` (correct REST path) with `category=cars`.

- [ ] Docs and registration
  - [x] `nowing_chotot_scrape` already in `app/mcp_tools.py` catalog.
  - [ ] Create `docs/connectors/native/chotot.md` with supported categories and billing rate.
  - [ ] Add `CHOTOT_SCRAPE_MICROS_PER_ITEM=3500` to `nowing_backend/.env.example`.
  - [ ] Add deprecation note for `chotot_bds.scrape` in docs and code.

## Validation Notes (2026-08-14)

- Most billing/capability wiring is already in place (likely shipped as part of Story 10.6 or earlier backend work). The remaining delta is:
  1. `ScrapeInput.category` must be **required** and validated against supported slugs.
  2. Add missing `.env.example` line and docs file.
  3. Complete unit/REST tests and deprecate `chotot_bds.scrape` in user-facing docs.
- Correct unit test path: `tests/unit/capabilities/chotot/scrape/test_executor.py`.
- Correct REST endpoint path: `POST /api/v1/workspaces/{workspace_id}/scrapers/chotot/scrape`.
- Supported slugs for validation: import `_SUPPORTED_CATEGORY_SLUGS` from `app.proprietary.platforms.chotot.fetch` (or inline the set: `bds`, `cars`, `motorbikes`, `electronics`, `jobs`, `pets`, `fashion`, `home_goods`, `home_appliances`, `kitchen`, `services`, `home_services`). Raw numeric `cg` strings are also valid.

## Dev Notes

- Relevant architecture patterns and constraints
  - `AD-3` — scraper capabilities self-register; add `register_capability` calls in `definition.py`.
  - `AD-16` — billing and capability code is Apache-2.0; keep `app/capabilities/chotot/scrape/` open. BSL 1.1 stays in `app/proprietary/platforms/chotot/`.
  - `AD-19` — anti-bot escalation already wired; executor should call `_maybe_escalate` on bot/rate-limit blocks.
  - `AD-34` / `AD-35` — scraper output is a listing, not a searchable corpus; ingestion into `chainlens-research` uses `NowingIngestService` (Epic 20) if desired.
  - Billing pre-flight (`gate_capability`) must use the `CHOTOT_ITEM` rate; do not hardcode BĐS rate.

- Source tree components to touch
  - `nowing_backend/app/capabilities/core/types.py` — `BillingUnit` addition
  - `nowing_backend/app/capabilities/core/billing.py` — `_PLATFORM_RATE_KEYS`, `_UNIT_NOUNS`
  - `nowing_backend/app/config/__init__.py` — rate config default
  - `nowing_backend/app/capabilities/chotot/scrape/definition.py`
  - `nowing_backend/app/capabilities/chotot/scrape/executor.py`
  - `nowing_backend/app/capabilities/chotot/scrape/schemas.py`
  - `nowing_backend/.env.example`
  - `docs/connectors/native/chotot.md` (create if missing)

- Testing standards summary
  - `tests/unit/capabilities/chotot/scrape/test_executor.py`
  - `tests/unit/capabilities/test_billing.py` for `BillingUnit` resolution
  - `tests/integration/capabilities/chotot/scrape/test_chotot_scrape.py` (live call optional)

### References

- [Source: `nowing_backend/app/capabilities/chotot/scrape/definition.py`]
- [Source: `nowing_backend/app/capabilities/chotot/scrape/executor.py`]
- [Source: `nowing_backend/app/capabilities/chotot/scrape/schemas.py`]
- [Source: `nowing_backend/app/capabilities/core/billing.py`]
