---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 2-7-walmart-product-reviews-scraper
status: ready-for-dev
---

# Story 2.7: Walmart Product + Reviews Scraper

**Status:** ready-for-dev
**Epic:** 2 — Connectors
**Priority:** HIGH
**Requirements:** FR-6
**Architecture:** AD-19
**Dependencies:** Existing scraper framework (`amazon.scrape` pattern); Story 2.9 (Scraper API Input Validation) is a downstream consumer that will inherit the same `HttpUrlStr` contract.

## Story

As an e-commerce analyst,
I want to scrape Walmart product listings and reviews,
So that I can monitor competitor pricing, ratings, and customer feedback.

## Context

### Upstream reference

SurfSense PR #1614 (`MODSetter/SurfSense#1614`) already implemented the Walmart scraper pattern we need to port. It is a self-contained addition of two verbs — `walmart.scrape` and `walmart.reviews` — and touches the same layers as the existing Amazon scraper.

Key files and patterns from the upstream PR:

- **Platform scraper package** (`surfsense_backend/app/proprietary/platforms/walmart/`)
  - `url_resolver.py`: classifies a start URL into `product` (`/ip/{slug}/{id}` or bare numeric `usItemId`) or `listing` (`/search`, `/cp/{slug}/{id}`, `/browse/...`, or query keys `q`/`cat_id`/`browse`); returns `ResolvedUrl(kind, url, item_id, domain)`.
  - `next_data.py`: extracts the hidden Next.js state from `<script id="__NEXT_DATA__">` with an `__APP_DATA__` fallback; provides `dig(obj, *keys)` for defensive nested JSON walks and `initial_data()` to reach `props.pageProps.initialData`.
  - `parsers.py`: pure, I/O-free JSON navigators for product detail, search/category cards, and review pages. Returns `None`/`[]` for missing sections. Normalizes `Price`, `Seller` (WALMART vs MARKETPLACE), breadcrumbs, review sample, and deep reviews.
  - `schemas.py`: `WalmartScrapeInput`, `WalmartReviewsInput`, `ProductItem`, `ReviewItem`, `ErrorItem`, `Price`, `Seller`. Outputs use `extra="allow"` and `to_output()` to keep the contract open.
  - `fetch.py`: proxy-aware `AsyncFetcher.get` with US-geo residential proxies, `is_blocked()` that scans body markers (`"robot or human"`, `px-captcha`, `/blocked`, etc.) and treats `412`/`429`/`503` as blocked, plus `_MAX_IP_ATTEMPTS = 6` rotation. Returns `FetchResult(status, html, url, cookies, headers)`.
  - `scraper.py`: two async streaming cores. `iter_products()` dispatches product/listing flows, enriches listing cards into full product pages when `includeDetails=True`, pages search results up to 25 pages, and uses `gather_bounded` with `_DETAIL_CONCURRENCY = 6`. `iter_reviews()` pages the public `/reviews/product/{usItemId}` URL with `sort` mapping (`most-recent` → `submission-desc`, etc.) until empty or `maxReviews` (default 200, cap 5000). Emits in-stream error items, not exceptions.

- **Capability registration** (`surfsense_backend/app/capabilities/walmart/`)
  - `scrape/definition.py`: `Capability(name="walmart.scrape", billing_unit=BillingUnit.WALMART_PRODUCT, docs_url="/docs/connectors/native/walmart")`.
  - `scrape/executor.py`: maps agent-facing `ScrapeInput` (`urls`, `search_terms`, `max_items`, `include_details`, `include_reviews_sample`) to `WalmartScrapeInput`, calls `scrape_products(..., limit=MAX_WALMART_RESULTS)`.
  - `scrape/schemas.py`: agent REST/MCP surface with `max_length=20` source caps, `max_items` 1–100, `estimated_units`, and `billable_units` (count non-error items).
  - `reviews/definition.py`: `Capability(name="walmart.reviews", billing_unit=BillingUnit.WALMART_REVIEW)`.
  - `reviews/executor.py`: maps `urls`/`item_ids` to `WalmartReviewsInput` and calls `scrape_reviews(..., limit=payload.estimated_units)`.
  - `reviews/schemas.py`: accepts product URLs or `item_ids`, `max_reviews` 1–5000, `sort_by` literal, and `estimated_units`/`billable_units`.

- **Billing and config**
  - `app/capabilities/core/types.py`: added `WALMART_PRODUCT` and `WALMART_REVIEW` to `BillingUnit`.
  - `app/capabilities/core/billing.py`: mapped `WALMART_PRODUCT` → `WALMART_MICROS_PER_PRODUCT` (noun `product`) and `WALMART_REVIEW` → `WALMART_MICROS_PER_REVIEW` (noun `review`).
  - `app/config/__init__.py`: added `WALMART_MICROS_PER_PRODUCT=3500` and `WALMART_MICROS_PER_REVIEW=1500`.

- **Agent subagent** (`surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins/walmart/`)
  - `agent.py`, `description.md`, `system_prompt.md`, `tools/index.py` with `NAME = "walmart"` and `_CI_VERBS = [WALMART_SCRAPE, WALMART_REVIEWS]`.
  - Registry and constants updated: `SUBAGENT_BUILDERS_BY_NAME["walmart"]`, `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP["walmart"] = frozenset()`, and main-agent prompts (`identity/private.md`, `identity/team.md`, `kb_first.md`, `routing.md`) mention `walmart` alongside `amazon`.

- **MCP tools** (`surfsense_mcp/mcp_server/features/scrapers/platforms/walmart.py`)
  - `surfsense_walmart_scrape` and `surfsense_walmart_reviews` (Nowing equivalent: `nowing_walmart_scrape` / `nowing_walmart_reviews`).

- **Frontend/marketing** (SurfSense)
  - `surfsense_web/lib/playground/catalog.ts` and `platform-icons.tsx`.
  - `surfsense_web/lib/connectors-marketing/walmart.tsx`.
  - `surfsense_web/content/docs/connectors/native/walmart.mdx` and `meta.json`.
  - `surfsense_web/public/connectors/walmart.svg`.

### Nowing current state

- The Nowing backend already has the same capability framework as SurfSense. Existing native scrapers live in `nowing_backend/app/proprietary/platforms/` (e.g. `amazon/`, `google_maps/`, `reddit/`, `youtube/`). The Amazon package is the closest analog: `url_resolver.py`, `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, plus `nowing_backend/app/capabilities/amazon/scrape/`. There is no `walmart/` directory yet.
- `nowing_backend/app/capabilities/core/types.py` currently defines `BillingUnit` with no Walmart entries (no `walmart_product`, no `walmart_review`).
- `nowing_backend/app/capabilities/core/billing.py` maps platform meters to `config` rate keys and display nouns; it has no Walmart mapping.
- `nowing_backend/app/config/__init__.py` (around line 864) has the `PLATFORM_SCRAPE_BILLING_ENABLED` block and all platform micro-rates; no `WALMART_*` keys.
- `nowing_backend/app/routes/__init__.py` imports `app.capabilities.<platform>` for side-effect registration; `app.capabilities.walmart` does not exist.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/registry.py` and `constants.py` have no `walmart` route.
- `nowing_mcp/mcp_server/features/scrapers/__init__.py` and `platforms/` have no `walmart.py`.
- `nowing_web/lib/playground/catalog.ts` and `platform-icons.tsx` do not list Walmart.
- `nowing_web/lib/connectors-marketing/index.ts` does not export a Walmart page.
- `nowing_web/content/docs/connectors/native/meta.json` and `index.mdx` do not list Walmart.
- `nowing_web/public/connectors/walmart.svg` does not exist.
- Story 2.9 is ready-for-dev and will introduce a shared `HttpUrlStr` validator. The Walmart capability can ship with `list[str]` URL fields to match the current Amazon pattern, then adopt `HttpUrlStr` when 2.9 lands, or use it directly if 2.9 merges first. The two stories must not fight over the same schema files.

## Acceptance Criteria

1. **Product scraping**
   - **Given** a Walmart product search URL (`/search?q=...`), a product page URL (`/ip/{slug}/{id}` or `/ip/{id}`), a category URL (`/cp/...`), a browse URL (`/browse/...`), or a bare numeric `usItemId`, **When** I call `walmart.scrape`, **Then** it returns product `name`, `usItemId`, `brand`, `price`, `listPrice`, `currency`, `availabilityStatus`, `inStock`, `stars`, `reviewsCount`, `seller` (Walmart 1P vs marketplace), `images`, `category`, `breadCrumbs`, `variants`, and a free `reviewsSample` (when `include_reviews_sample=True`).

2. **Reviews scraping**
   - **Given** a product with reviews, **When** I request `walmart.reviews` with a product URL or `item_id`, **Then** it returns paginated review `reviewId`, `rating`, `title`, `text`, `submissionTime`, `author`, `verifiedPurchase`, `positiveFeedback`, `negativeFeedback`, `images`, `syndicated`, and `sellerResponse`.

3. **Multi-channel exposure**
   - **Given** the capability is built, **When** I use REST (`POST /workspaces/{id}/scrapers/walmart/scrape` and `/.../walmart/reviews`), the playground, agent chat (`task(walmart, ...)`), or MCP (`nowing_walmart_scrape` / `nowing_walmart_reviews`), **Then** both verbs are available and return the same typed output.

4. **Block handling**
   - **Given** Walmart blocks or returns a bot challenge, **When** scraping, **Then** the scraper rotates proxies, detects the block by HTTP status (`412`/`429`/`503`) or body markers (`robot or human`, `px-captcha`, etc.), and fails gracefully with an in-stream error item (e.g. `product_not_found`, `reviews_not_found`) after exhausting retries.

5. **Billing and metering**
   - **Given** a successful run, **When** billing is enabled (`PLATFORM_SCRAPE_BILLING_ENABLED=true`), **Then** `walmart.scrape` charges per returned product and `walmart.reviews` charges per returned review; error items are never billed and the per-item rate is config-driven (`WALMART_MICROS_PER_PRODUCT` / `WALMART_MICROS_PER_REVIEW`).

6. **Agent integration**
   - **Given** the `walmart` subagent is registered, **When** a user asks for Walmart product data or reviews, **Then** the main agent routes to the `walmart` specialist, which uses `walmart_scrape` / `walmart_reviews` and returns the standard JSON output contract.

7. **Frontend surface**
   - **Given** the Walmart scraper is live, **When** a user opens the API Playground, the connectors marketing pages, or the docs, **Then** Walmart appears with an icon, two verbs (`scrape` and `reviews`), and a dedicated `/walmart` marketing page and docs page.

## Tasks / Subtasks

### Backend — platform scraper

- [ ] Create `nowing_backend/app/proprietary/platforms/walmart/`
  - [ ] `__init__.py` — export `WalmartScrapeInput`, `WalmartReviewsInput`, `ProductItem`, `ReviewItem`, `ErrorItem`, `scrape_products`, `scrape_reviews`, `iter_products`, `iter_reviews`.
  - [ ] `url_resolver.py` — `ResolvedUrl`, `resolve_url()`, `extract_item_id()`; product vs listing classification; bare numeric id support; `walmart.` hostname guard.
  - [ ] `next_data.py` — `extract_next_data()` with `__NEXT_DATA__` + `__APP_DATA__` fallback, `dig()`, `initial_data()`.
  - [ ] `parsers.py` — `parse_product()`, `parse_listing_page()`, `parse_reviews_page()`, `normalize_review()`, `_price()`, `_seller()`, `_breadcrumbs()`, `_images()`.
  - [ ] `schemas.py` — `WalmartScrapeInput`, `WalmartReviewsInput`, `ProductItem`, `ReviewItem`, `Price`, `Seller`, `ErrorItem`; `extra="allow"`; `to_output()`; error codes `invalid_url`, `product_not_found`, `no_results_found`, `reviews_not_found`.
  - [ ] `fetch.py` — `FetchResult` dataclass, `fetch_page()`, `is_blocked()`, `_selected_proxy()`, `gather_bounded()`; US-geo residential proxies; block markers; 6-attempt rotation; no proxy URL logging.
  - [ ] `scraper.py` — `iter_products()`, `scrape_products()`, `iter_reviews()`, `scrape_reviews()`; product flow, listing flow with optional detail enrichment, reviews pagination, in-stream error items, progress emissions.
  - [ ] `README.md` — architecture, anti-bot notes, verification commands.

### Backend — capabilities and billing

- [ ] Create `nowing_backend/app/capabilities/walmart/`
  - [ ] `__init__.py` — import `scrape.definition` and `reviews.definition` for side-effect registration.
  - [ ] `scrape/definition.py` — `WALMART_SCRAPE` `Capability` with `BillingUnit.WALMART_PRODUCT`, `docs_url="/docs/connectors/native/walmart"`.
  - [ ] `scrape/executor.py` — `build_scrape_executor()` mapping `ScrapeInput` → `WalmartScrapeInput`, calling `scrape_products(..., limit=MAX_WALMART_RESULTS)`.
  - [ ] `scrape/schemas.py` — `ScrapeInput` (`urls`, `search_terms`, `max_items`, `include_details`, `include_reviews_sample`), `ScrapeOutput` with `billable_units`.
  - [ ] `reviews/definition.py` — `WALMART_REVIEWS` `Capability` with `BillingUnit.WALMART_REVIEW`.
  - [ ] `reviews/executor.py` — `build_reviews_executor()` mapping `ReviewsInput` → `WalmartReviewsInput`.
  - [ ] `reviews/schemas.py` — `ReviewsInput` (`urls`, `item_ids`, `max_reviews`, `sort_by`), `ReviewsOutput` with `billable_units`.
- [ ] Update `nowing_backend/app/capabilities/core/types.py` — add `WALMART_PRODUCT = "walmart_product"` and `WALMART_REVIEW = "walmart_review"` to `BillingUnit`.
- [ ] Update `nowing_backend/app/capabilities/core/billing.py` — add `BillingUnit.WALMART_PRODUCT` → `WALMART_MICROS_PER_PRODUCT` and `BillingUnit.WALMART_REVIEW` → `WALMART_MICROS_PER_REVIEW` in `_PLATFORM_RATE_KEYS` and `_UNIT_NOUNS`.
- [ ] Update `nowing_backend/app/config/__init__.py` — add `WALMART_MICROS_PER_PRODUCT=3500` and `WALMART_MICROS_PER_REVIEW=1500` in the platform scrape billing block (after `AMAZON_MICROS_PER_PRODUCT`).
- [ ] Update `nowing_backend/app/routes/__init__.py` — add `import app.capabilities.walmart` alongside other capability imports.

### Backend — agent subagent

- [ ] Create `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/walmart/`
  - [ ] `__init__.py`, `agent.py`, `description.md`, `system_prompt.md`, `tools/__init__.py`, `tools/index.py`.
  - [ ] `tools/index.py` loads `WALMART_SCRAPE` and `WALMART_REVIEWS` via `build_capability_tools()`.
- [ ] Update `nowing_backend/app/agents/chat/multi_agent_chat/subagents/registry.py` — import `build_walmart_subagent` and add `"walmart"` to `SUBAGENT_BUILDERS_BY_NAME`.
- [ ] Update `nowing_backend/app/agents/chat/multi_agent_chat/constants.py` — add `"walmart": frozenset()` to `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`.
- [ ] Update main agent prompts:
  - [ ] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/identity/private.md` — add `Walmart` to the live web data list.
  - [ ] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/identity/team.md` — same.
  - [ ] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/kb_first.md` — add `task(walmart, ...)` in the market specialists list.
  - [ ] `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md` — mention `task(amazon, ...)` / `task(walmart, ...)` for product ratings and customer reviews.

### MCP server

- [ ] Create `nowing_mcp/mcp_server/features/scrapers/platforms/walmart.py` — register `nowing_walmart_scrape` and `nowing_walmart_reviews` with the same parameter surface as the REST schemas.
- [ ] Update `nowing_mcp/mcp_server/features/scrapers/__init__.py` — import `walmart` and add it to `_REGISTRARS`.

### Frontend

- [ ] Add `nowing_web/public/connectors/walmart.svg`.
- [ ] Update `nowing_web/lib/playground/platform-icons.tsx` — export `WalmartIcon = brandIcon("/connectors/walmart.svg", "Walmart")`.
- [ ] Update `nowing_web/lib/playground/catalog.ts` — add `walmart` platform with `walmart.scrape` and `walmart.reviews` verbs.
- [ ] Create `nowing_web/lib/connectors-marketing/walmart.tsx` — marketing page content (slug `walmart`, icon, meta, schema, FAQ, related connectors).
- [ ] Update `nowing_web/lib/connectors-marketing/index.ts` — import and register the Walmart connector page.
- [ ] Create `nowing_web/content/docs/connectors/native/walmart.mdx`.
- [ ] Update `nowing_web/content/docs/connectors/native/meta.json` — add `walmart` to `pages`.
- [ ] Update `nowing_web/content/docs/connectors/native/index.mdx` — add a Walmart card.

### Tests

- [ ] `nowing_backend/tests/unit/platforms/walmart/`
  - [ ] `__init__.py`, `fixtures/product.html`, `fixtures/listing.html`, `fixtures/reviews.html`, `fixtures/blocked.html`.
  - [ ] `test_parsers.py` — product/listing/reviews extraction, block detection, url resolver.
  - [ ] `test_flows.py` — product flow, listing flow (card-only and enriched), reviews pagination, invalid URL error item, `max_reviews` cap.
- [ ] `nowing_backend/tests/unit/capabilities/walmart/`
  - [ ] `__init__.py`, `test_registry.py`.
  - [ ] `scrape/test_schemas.py`, `scrape/test_executor.py`.
  - [ ] `reviews/test_schemas.py`, `reviews/test_executor.py`.
- [ ] `nowing_backend/scripts/e2e_walmart_scraper.py` (optional, manual live check) — exercise live product/listing/reviews with proxy.

## Dev Notes

- **Port, do not blindly copy.** The SurfSense stack is the same (FastAPI + Pydantic v2, Next.js + TypeScript, `scrapling` fetcher), but Nowing paths and naming differ. Use `nowing_backend/app/proprietary/platforms/` (not `app/services/scrapers/`), the `app.utils.proxy.ProxyProvider` seams (not SurfSense's client), and `nowing_*` MCP tool names.
- **Reuse the Amazon fetch pattern.** `nowing_backend/app/proprietary/platforms/amazon/fetch.py` already uses `AsyncFetcher.get`, `get_geo_proxy_url`/`get_sticky_proxy_url`, `is_blocked()`, and `gather_bounded()`. The Walmart fetch layer can mirror it, with Walmart-specific block markers and the `412` PerimeterX status.
- **Data is in `__NEXT_DATA__`, not the DOM.** Walmart obfuscates CSS classes and A/B-tests layout; the hidden Next.js JSON is the stable source. Always extract `__NEXT_DATA__` first, `__APP_DATA__` second. Use the `dig()` helper to tolerate layout drift.
- **In-stream error items, not exceptions.** Follow the Amazon pattern: every failure for a single input is emitted as a dict with an `error` key (`invalid_url`, `product_not_found`, `no_results_found`, `reviews_not_found`) so the rest of the run continues. This is the same failure model as `amazon.scrape`.
- **US-only for the MVP.** The upstream implementation pins `country="us"` because Walmart geo-locks inventory. The capability surface can keep `country: str = "us"` for future expansion, but the fetch layer should default to US proxy/headers.
- **Reviews are public and pagination-limited.** Walmart serves roughly 10 reviews per `/reviews/product/{usItemId}` page; robots.txt permits the reviews path. Stop on the first empty page. Cap at 5000 reviews (500 pages) as a safety ceiling.
- **Search/category/browse listings share one parser.** All three URL shapes feed into the same `listing` flow and `parse_listing_page()`; when `includeDetails=True`, each card is resolved to a product and enriched in parallel.
- **Billing per item.** `walmart.scrape` is one billable unit per returned product; `walmart.reviews` is one billable unit per returned review. Error items are never billed. The `billable_units` property on `ScrapeOutput`/`ReviewsOutput` drives `charge_capability()`.
- **Do not log proxy URLs or credentials.** The fetch layer logs status, attempt count, and timing only.
- **Avoid the `/orchestra/*` GraphQL API.** Upstream deliberately skipped it because persisted-query hashes rotate and make the integration brittle. Stay on the server-rendered `__NEXT_DATA__` pages.
- **Ponytail ceiling:** MVP uses server-rendered JSON + residential proxies. If block rates climb, the upgrade path is a warmed sticky session (seed `_px3`/`_pxhd` on a sticky exit), the same shape as Amazon's `get_location_session`.
- **URL validation.** Keep URL fields as `list[str]` to match the current Amazon pattern. If Story 2.9 (`HttpUrlStr`) lands first, use `list[HttpUrlStr]` and its shared validator; if 2.7 lands first, leave a clear TODO or follow-up for 2.9 to migrate the Walmart schemas.

## Verification

- [ ] Backend unit tests pass:
  ```bash
  cd nowing_backend
  pytest tests/unit/platforms/walmart -q
  pytest tests/unit/capabilities/walmart -q
  ```
- [ ] Backend lint/format:
  ```bash
  cd nowing_backend
  ruff check app/proprietary/platforms/walmart app/capabilities/walmart app/capabilities/core app/agents/chat/multi_agent_chat/subagents/builtins/walmart app/config/__init__.py app/routes/__init__.py
  ruff format app/proprietary/platforms/walmart app/capabilities/walmart app/agents/chat/multi_agent_chat/subagents/builtins/walmart
  ```
- [ ] Web typecheck and lint on changed files:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    lib/playground/catalog.ts \
    lib/playground/platform-icons.tsx \
    lib/connectors-marketing/walmart.tsx \
    lib/connectors-marketing/index.ts \
    content/docs/connectors/native/walmart.mdx \
    content/docs/connectors/native/index.mdx
  ```
- [ ] Runtime smoke (requires `PLATFORM_SCRAPE_BILLING_ENABLED` and proxy env):
  ```bash
  cd nowing_backend
  python - <<'PY'
  import asyncio
  from app.proprietary.platforms.walmart import WalmartScrapeInput, scrape_products
  out = asyncio.run(scrape_products(WalmartScrapeInput(startUrls=["https://www.walmart.com/ip/212092810"])))
  print(out[0]["usItemId"], out[0].get("name"))
  PY
  ```
  Or use the e2e script:
  ```bash
  cd nowing_backend
  python scripts/e2e_walmart_scraper.py
  ```
- [ ] Playground and MCP list both `walmart.scrape` and `walmart.reviews` after registration.

## References

- Upstream PR: `MODSetter/SurfSense#1614`
- Model story: `_bmad-output/implementation-artifacts/2-9-scraper-input-validation.md`
- `nowing_backend/app/proprietary/platforms/amazon/` — closest existing implementation
  - `__init__.py`, `url_resolver.py`, `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`
- `nowing_backend/app/capabilities/amazon/scrape/`
  - `definition.py`, `executor.py`, `schemas.py`
- `nowing_backend/app/capabilities/google_maps/reviews/` — pattern for a separate reviews verb
  - `definition.py`, `executor.py`, `schemas.py`
- `nowing_backend/app/capabilities/core/`
  - `types.py`, `billing.py`, `store.py`, `access/rest.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/`
  - `subagents/registry.py`, `subagents/constants.py`
  - `subagents/builtins/amazon/` — template for a market specialist subagent
  - `main_agent/system_prompt/prompts/identity/private.md`, `identity/team.md`, `kb_first.md`, `routing.md`
- `nowing_mcp/mcp_server/features/scrapers/`
  - `__init__.py`, `platforms/amazon.py`, `platforms/google_maps.py`, `capability.py`
- `nowing_web/lib/playground/catalog.ts`, `platform-icons.tsx`
- `nowing_web/lib/connectors-marketing/index.ts`, `amazon.tsx`
- `nowing_web/content/docs/connectors/native/` (e.g. `amazon.mdx`, `index.mdx`, `meta.json`)
- `nowing_web/public/connectors/walmart.svg` (to be added)
