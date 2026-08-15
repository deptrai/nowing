---
baseline_commit: 457993915f0ac27026e16643a1fe4e2c1b3bc38b
---

# Story 10.7: Chợ Tốt Multi-Category Capability and Billing

Status: review

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

- [x] Update capability schemas (AC #7)
  - [x] `ScrapeInput.category` is now required and validates against supported slugs or raw numeric `cg` codes via `get_category_config`.
  - [x] `ScrapeOutput` already has `cost_micros`, `degraded`, `degradation_reason`, `next_action`.
  - [x] `estimated_units` is `max_items`.

- [x] Tests
  - [x] Unit tests in `tests/unit/capabilities/chotot/scrape/test_executor.py`:
    - `chotot.scrape` is registered with `BillingUnit.CHOTOT_ITEM`.
    - `ScrapeInput` rejects unsupported `category`.
    - `gate_capability` reserves `max_items × CHOTOT_SCRAPE_MICROS_PER_ITEM`.
    - `category="unknown"` listings are not billed.
    - `chotot_bds.scrape` still works as alias.
  - [x] Integration test `test_chotot_multi_category_scrape.py` already covers `cars`, `jobs`, `electronics` round-trips and billing.

- [x] Docs and registration
  - [x] `nowing_chotot_scrape` already in `app/mcp_tools.py` catalog.
  - [x] Created `nowing_web/content/docs/connectors/native/chotot.mdx` with categories, billing, endpoint, and deprecation note.
  - [x] Added `CHOTOT_SCRAPE_MICROS_PER_ITEM=3500` to `nowing_backend/.env.example`.
  - [x] Added deprecation note for `chotot_bds.scrape` in docs.

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

## File List

- `nowing_backend/app/capabilities/chotot/scrape/schemas.py`
- `nowing_backend/tests/unit/capabilities/chotot/scrape/test_executor.py`
- `nowing_backend/tests/unit/capabilities/chotot/test_registry.py`
- `nowing_backend/.env.example`
- `nowing_web/content/docs/connectors/native/chotot.mdx`
- `_bmad-output/implementation-artifacts/stories/10-7-chotot-multi-category-capability.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-08-14: Dev Story 10.7 — made `ScrapeInput.category` required with supported-slug validator, added `CHOTOT_SCRAPE_MICROS_PER_ITEM` to `.env.example`, created Chợ Tốt connector docs, expanded unit tests, validated integration tests.

## Dev Agent Record

### Implementation Plan

- Reused existing `get_category_config` from `app.proprietary.platforms.chotot.fetch` to validate `ScrapeInput.category` and keep slug support in sync with the gateway.
- Added `field_validator` to `ScrapeInput` making `category` required; raw numeric `cg` codes remain valid.
- Backfilled unit tests for required category, unsupported category, raw `cg`, `estimated_units`, and pre-flight gate reserve.
- Updated `tests/unit/capabilities/chotot/test_registry.py` to assert both `chotot.scrape` and `chotot_bds.scrape` registration.
- Added connector docs under `nowing_web/content/docs/connectors/native/chotot.mdx` and `.env.example` default.

### Completion Notes

- `ScrapeInput` no longer defaults `category` to `bds`; `chotot_bds.scrape` remains a deprecated alias via `locked_category="bds"`.
- Unit tests: 23/23 pass in `tests/unit/capabilities/chotot/scrape/test_executor.py`, 2/2 pass in `tests/unit/capabilities/chotot/test_registry.py`.
- Integration tests: 7 passed, 2 skipped in `tests/integration/capabilities/chotot/`.
- Ruff clean for modified `app/capabilities/chotot/scrape` and `tests/unit/capabilities/chotot` paths.
- Full repo `ruff check .` still reports pre-existing violations outside this story's scope.

### Review Findings

Code review of the `chotot` multi-category subagent wiring (2026-08-15).

- [x] [Review][Patch] Missing `chotot` in `test_subagent_composition.py` expected sets — `tests/unit/agents/multi_agent_chat/test_subagent_composition.py:28-54`.
- [x] [Review][Patch] New subagent `system_prompt.md` advertises `district_id` but the scraper rejects all valid non-negative values — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/system_prompt.md:17`.
- [x] [Review][Patch] `evidence.sources` hard-codes `chotot.com` for all categories, but the parser builds category-specific origins — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/system_prompt.md:66`.
- [x] [Review][Patch] `listing_type` playbook over-promises `rent` and `want_to_buy` for non-BĐS categories — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/system_prompt.md:15`.
- [x] [Review][Patch] `description.md` lists wrong BĐS domain `nha.chotot.com` instead of `nhatot.com` — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/description.md:1`.
- [x] [Review][Patch] New subagent uses `tools/__init__.py` instead of the established `tools/index.py` convention — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/agent.py:17-18`.
- [x] [Review][Patch] `evidence.findings` template includes `area` for all categories, but `area` is BĐS-specific — `app/agents/chat/multi_agent_chat/subagents/builtins/chotot/system_prompt.md:65`.
- [x] [Review][Patch] No dedicated tests added for the new `chotot` subagent builder and tool loading.
- [x] [Review][Patch] Billing `call_details` does not include `category`, violating AC 2 — `app/capabilities/core/billing.py:715`.
- [x] [Review][Patch] Unknown-category listings do not set `degradation_reason="unknown_category"`, violating AC 4 — `app/capabilities/chotot/scrape/executor.py:194-202`.
- [x] [Review][Patch] Missing optional `subcategory` field in `ScrapeInput`, violating AC 7 — `app/capabilities/chotot/scrape/schemas.py:22-38`.
- [x] [Review][Patch] `ScrapeInput` silently drops extra fields (e.g. `subcategory`, `sort`) instead of rejecting or honoring them — `app/capabilities/chotot/scrape/schemas.py:25`.
- [x] [Review][Patch] Whitespace-padded or formatted raw `cg` codes fail validation — `app/proprietary/platforms/chotot/fetch.py:181-197`.
- [x] [Review][Patch] Raw numeric `cg` requests keep the requested code as item `category`, so unmapped gateway `cg` listings may still be billed — `app/proprietary/platforms/chotot/parsers.py:471-476`.
- [x] [Review][Patch] Listings with missing `listing_id` bypass `seen_ids` deduplication — `app/proprietary/platforms/chotot/scraper.py:310-314`.
- [x] [Review][Patch] `ScrapeOutput.total_items` is `len(items)`, not the gateway total, so the subagent cannot distinguish "no results" from "cap reached" — `app/capabilities/chotot/scrape/schemas.py:90-93`.
- [x] [Review][Patch] Empty first page is marked `degraded=True` with reason "empty", conflicting with the subagent playbook that instructs broadening and `status=partial` — `app/proprietary/platforms/chotot/scraper.py:301-304`.
- [x] [Review][Patch] `ChototBdsAccessBlockedError` (5xx / access failure) is reported as `degradation_reason="bot_detected"` — `app/capabilities/chotot/scrape/executor.py:141-151`.
- [x] [Review][Patch] Any `degraded=True` result triggers the anti-bot screenshot task, not only bot/rate-limit blocks — `app/capabilities/chotot/scrape/executor.py:180-183`.
- [x] [Review][Patch] `chotot` and `chotot_bds` subagents can both handle BĐS queries with different billing meters; main agent has no guidance on which to pick — `app/agents/chat/multi_agent_chat/subagents/registry.py:116-117`.
- [x] [Review][Defer] Inverted `district_id` guard in `app/proprietary/platforms/chotot/scraper.py:116-119` — pre-existing; remove from prompt now, fix guard separately.
