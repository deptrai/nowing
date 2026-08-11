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

- [ ] Confirm capability & billing shape (AC #1, #2)
  - [ ] Architecture decision: single `chotot.scrape` (Option A); record in architecture spine or a short AD note.
  - [ ] Billing: single `BillingUnit.CHOTOT_ITEM` plus `call_details["category"]`. Avoid per-category `BillingUnit` explosion.

- [ ] Add billing unit and config (AC #2, #5)
  - [ ] Add `BillingUnit.CHOTOT_ITEM = "chotot_item"` to `app/capabilities/core/types.py`.
  - [ ] Add `CHOTOT_SCRAPE_MICROS_PER_ITEM` to `app/config/__init__.py`.
  - [ ] Update `app/capabilities/core/billing.py` `_PLATFORM_RATE_KEYS` and `_UNIT_NOUNS` for `CHOTOT_ITEM`.
  - [ ] If existing `CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM` is kept, map it to the same rate or add a warning/deprecation note.

- [ ] Implement or update capability definition (AC #1, #6, #7)
  - [ ] Update `app/capabilities/chotot/scrape/definition.py`:
    - Register `chotot.scrape` with `BillingUnit.CHOTOT_ITEM`.
    - Keep `chotot_bds.scrape` as a deprecated alias calling `chotot.scrape` with `category="bds"`.
  - [ ] Update `app/capabilities/chotot/scrape/executor.py`:
    - Accept `category` and route to `scrape_chotot`.
    - Compute `cost_micros = total_returned × CHOTOT_SCRAPE_MICROS_PER_ITEM`.
    - Skip billing for listings with `category="unknown"` / degraded runs.
    - Reuse `_maybe_escalate` on bot/rate-limit blocks (`AD-19`).

- [ ] Update capability schemas (AC #7)
  - [ ] `ScrapeInput` in `app/capabilities/chotot/scrape/schemas.py` adds `category: str` (validated against supported slugs), optional `subcategory`.
  - [ ] `ScrapeOutput` keeps `cost_micros`, `degraded`, `degradation_reason`, `next_action`.
  - [ ] `estimated_units` remains `max_items`.

- [ ] Tests
  - [ ] Unit test `build_scrape_executor` uses `BillingUnit.CHOTOT_ITEM` and includes `category` in `call_details`.
  - [ ] Unit test `ScrapeInput` rejects unsupported `category`.
  - [ ] Unit test pre-flight `gate_capability` reserves `max_items × CHOTOT_SCRAPE_MICROS_PER_ITEM`.
  - [ ] Unit test `category="unknown"` listings are not billed.
  - [ ] Integration test `POST /api/v1/capabilities/chotot.scrape` with `category=cars` returns typed listings and correct `cost_micros`.
  - [ ] Regression test `chotot_bds.scrape` still returns BĐS listings and bills at `CHOTOT_ITEM` rate.

- [ ] Docs and registration
  - [ ] Add `chotot.scrape` to MCP capability selfcheck list if applicable.
  - [ ] Update `docs/connectors/native/chotot.md` (or create) with supported categories and billing rate.
  - [ ] Update `.env.example` with `CHOTOT_SCRAPE_MICROS_PER_ITEM` default.
  - [ ] Add deprecation note for `chotot_bds.scrape` in docs and code.

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
  - `tests/unit/capabilities/chotot/test_scrape_executor.py`
  - `tests/unit/capabilities/test_billing.py` for `BillingUnit` resolution
  - `tests/integration/capabilities/chotot/test_chotot_scrape.py` (live call optional)

### References

- [Source: `nowing_backend/app/capabilities/chotot/scrape/definition.py`]
- [Source: `nowing_backend/app/capabilities/chotot/scrape/executor.py`]
- [Source: `nowing_backend/app/capabilities/chotot/scrape/schemas.py`]
- [Source: `nowing_backend/app/capabilities/core/billing.py`]
