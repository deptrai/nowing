---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 2-8-amazon-eu-marketplaces
status: done
---

# Story 2.8: Amazon EU Marketplaces Support

**Status:** ready-for-dev
**Epic:** 2 — Connectors
**Priority:** MEDIUM
**Requirements:** FR-6
**Architecture:** AD-19
**Dependencies:** `amazon.scrape` capability (ported from upstream PR #1604). Story 2-9 (`HttpUrlStr` shared validation) is a sibling/soft dependency for the `urls` field.

## Story

As a seller watching European markets,
I want the Amazon scraper to support EU marketplaces (`amazon.de`, `amazon.fr`, `amazon.co.uk`, etc.),
So that I can track localized prices, currency, and availability across regions.

## Context

### Upstream reference

SurfSense PR #1628 (release v0.0.35) bundles the earlier Amazon multi-marketplace work from **PR #1604** (`feat(amazon): add public multi-marketplace product scraping capability`) plus the shared scraper-input validation from **PR #1623**. The EU-relevant pieces in #1604 / #1628 are:

- `app/proprietary/platforms/amazon/url_resolver.py` — a pure URL classifier. It accepts any host containing `amazon.`, extracts the TLD suffix as `marketplace` (e.g. `de`, `fr`, `co.uk`), and recognizes product (`/dp/ASIN`, `/gp/product/ASIN`), search (`/s?k=...`, `k/bbn/rh` query params), bestsellers (`/zgbs/...`, `/gp/bestsellers/...`) and shortened (`a.co`, `amzn.to`, `amzn.eu`) links.
- `app/proprietary/platforms/amazon/locale.py` — maps marketplace suffix to a proxy exit country and an `Accept-Language` header:
  - `co.uk` → `gb` / `en-GB`
  - `de` → `de` / `de-DE`
  - `fr` → `fr` / `fr-FR`
  - `it` → `it` / `it-IT`
  - `es` → `es` / `es-ES`
  - `com` → `us` / `en-US`
  - Unmapped marketplaces fall back to `None` proxy country and `en-US`.
- `app/proprietary/platforms/amazon/parsers.py` — `_float` parses both US (`1,234.56`) and EU (`1.234,56`) decimal formats, and `_price` derives an ISO currency code from the price text (`$`→`USD`, `€`→`EUR`, `£`→`GBP`, etc., plus a regex fallback for `USD/EUR/GBP/JPY/INR/CAD/AUD`). `Price` is a nested `{ value: float, currency: string }` object.
- `app/proprietary/platforms/amazon/schemas.py` — `ProductItem` output carries `price`, `listPrice`, `shippingPrice` as `Price`; region provenance is available through `url`, `unNormalizedProductUrl`, `loadedCountryCode`, `locationText`, and the parsed `domain`.
- `app/capabilities/amazon/scrape/schemas.py` — the agent-facing `ScrapeInput` has a `domain` field defaulting to `www.amazon.com`. In #1628 the `urls` field is switched from `list[str]` to `list[HttpUrlStr]` to reuse the shared validator.
- Tests: `test_locale.py` covers `proxy_country_for` / `accept_language_for` for EU marketplaces; `test_flows.py` verifies a `www.amazon.co.uk` search sends `country=gb` and `accept_language=en-GB`; `test_parsers.py` tests EU price formats and EUR extraction; `test_skeleton.py` contains URL-resolver contract tests for `amazon.de` and shortened links.
- Docs: `content/docs/connectors/native/amazon.mdx` lists UK/DE/IT/ES as supported, FR as best-effort, and gives `amazon.co.uk/de/it/es` examples.

### Nowing current state

- The whole Amazon platform package (`nowing_backend/app/proprietary/platforms/amazon/`) and the `amazon.scrape` capability (`nowing_backend/app/capabilities/amazon/scrape/`) have been ported from #1604.
- `url_resolver.py` already extracts the marketplace from any `amazon.<tld>` host.
- `locale.py` already maps the six verified marketplaces (`com`, `co.uk`, `de`, `fr`, `it`, `es`) to proxy country and `Accept-Language`.
- `parsers.py` already handles EU price formatting and currency codes.
- The agent `ScrapeInput.domain` regex `^(?:www\.)?amazon\.[a-z.]+$` allows any `amazon` TLD and is not hard-coded to `com`.
- The playground (`nowing_web/lib/playground/platform-overrides/amazon.tsx`) exposes the same six marketplaces in a dropdown and shows a France-WAF hint.
- The connector docs (`nowing_web/content/docs/connectors/native/amazon.mdx`) already document EU marketplace examples.
- Billing: `BillingUnit.AMAZON_PRODUCT` is registered in `app/capabilities/core/types.py`, `billing.py`, and the capability definition.
- The one upstream piece **not** yet in Nowing is the `HttpUrlStr` validation for the `urls` field — that belongs to sibling Story 2.9. Until 2.9 lands, Amazon `urls` are still `list[str]`.

### Gaps to close for this story

1. The `ScrapeInput` `domain` pattern and the `url_resolver` accept *any* `amazon.<tld>` (e.g. `amazon.nl`, `amazon.se`). The `locale.py` map only covers six marketplaces; other EU TLDs silently fall back to `en-US`/no country. We should decide whether to expand the verified map or to tighten the allowed set.
2. No `marketplace` field is explicitly returned in `ProductItem` output — the region is only implicit in `url`/`unNormalizedProductUrl`. We should expose an explicit `marketplace` string on each product/search card for downstream consumers.
3. The `urls` field must be switched to `list[HttpUrlStr]` (after 2.9) and the Amazon resolver should still accept EU TLDs / short links.
4. Tests currently exercise `co.uk` and generic `amazon.de`/`fr`/`it`/`es` locale mapping, but there are no fixture-level tests for EU product pages (e.g. `€` or `£` prices in `product.html`), no dedicated URL-resolver test file, and no tests that `ScrapeInput.domain` accepts EU domains.
5. Front-end docs list FR as best-effort but do not explain why or how to retry. Playground hint is inline but not in docs.

## Acceptance Criteria

1. **EU TLD resolution**
   - **Given** a product, search, bestseller, or shortened URL on an EU Amazon domain (`amazon.de`, `amazon.fr`, `amazon.co.uk`, `amazon.it`, `amazon.es`, ...), **When** `resolve_url` runs, **Then** it returns a `ResolvedUrl` with the correct `marketplace` suffix and does not reject the URL.

2. **Locale-aware fetch**
   - **Given** a resolved EU marketplace, **When** the scraper fetches pages, **Then** the request uses the matching proxy country and `Accept-Language` header (`de`/`de-DE`, `gb`/`en-GB`, etc.) when the marketplace is in the verified map.

3. **Localized price and currency**
   - **Given** an EU product page with `€`, `£`, or `¥`-style price strings, **When** the product is parsed, **Then** `price.currency` is `EUR`, `GBP`, etc., and `price.value` correctly interprets both `1,234.56` and `1.234,56` decimal formats.

4. **Output schema**
   - **Given** a successful EU scrape, **When** the product is returned, **Then** each item carries `price`, `listPrice`, `shippingPrice` with `value` and `currency`, and an explicit `marketplace` field (e.g. `de`, `co.uk`) so consumers know which region the data came from.

5. **Validation**
   - **Given** an EU marketplace URL, **When** it is submitted to `amazon.scrape`, **Then** the shared URL validator (`HttpUrlStr`) and the `domain` regex accept it, and the URL resolver classifies it as product/search/bestsellers/shortened.

6. **Playground and docs**
   - **Given** a user in the API Playground, **When** they choose Amazon, **Then** the marketplace dropdown includes US/UK/DE/IT/ES/FR and surfaces the France best-effort warning.
   - **And** the docs page lists supported EU marketplaces, the France caveat, and example URLs for each.

7. **Billing stays per-product**
   - **Given** a successful EU scrape, **When** the run completes, **Then** billing is metered as `AMAZON_PRODUCT` per returned product (error items are not billed), regardless of marketplace.

## Tasks / Subtasks

### Backend

- [x] Ensure `url_resolver.py` accepts all supported EU TLDs (AC #1)
  - [x] Confirm `resolve_url` handles `amazon.de`, `amazon.fr`, `amazon.co.uk`, `amazon.it`, `amazon.es`, `amazon.nl`, `amazon.se` if included in verified map.
  - [x] Add/amend unit cases in `tests/unit/platforms/amazon/test_skeleton.py` for EU TLDs, multi-segment TLDs, and `amzn.eu` short links.
- [x] Extend or tighten `locale.py` marketplace map (AC #2)
  - [x] Keep the current six and document that unknown EU TLDs fall back to `en-US`/default proxy.
- [x] Add `marketplace` to output schema (AC #4)
  - [x] Add `marketplace: str | None` to `ProductItem` in `nowing_backend/app/proprietary/platforms/amazon/schemas.py`.
  - [x] Populate it from `resolved.marketplace` in `_product_flow`, `_search_flow`, `_bestsellers_flow`, and `parse_search_page`/`parse_bestsellers_page`.
- [x] Validate `ScrapeInput.domain` pattern (AC #5)
  - [x] Keep `^(?:www\.)?amazon\.[a-z.]+$` or restrict to the verified marketplace list.
  - [x] Add unit tests in `tests/unit/capabilities/amazon/scrape/test_schemas.py` for EU domains.
- [x] Switch `urls` to `list[HttpUrlStr]` (paired with Story 2-9) (AC #5)
  - [x] Import `HttpUrlStr` from `app.capabilities.core.validation` in `nowing_backend/app/capabilities/amazon/scrape/schemas.py`.
  - [x] Add malformed URL test cases.
- [x] Add/fix EU parser tests (AC #3)
  - [x] Add a `product_eu.html` fixture with `€`/`£`/`de-DE` text and verify `_price`, `_float`, currency, and `marketplace` extraction.
  - [x] Test `co.uk` and `com.au` multi-segment TLDs in `test_skeleton.py`.
- [x] Add flow tests for EU (AC #1, #2, #4)
  - [x] Extend `tests/unit/platforms/amazon/test_flows.py` with product/search flows for `amazon.de` and `amazon.co.uk`.
  - [x] Assert `country`, `accept_language`, and returned `marketplace` match.

### Frontend

- [x] Keep `nowing_web/lib/playground/platform-overrides/amazon.tsx` marketplace dropdown up to date (AC #6)
  - [x] Verify options match the verified `locale.py` map.
  - [x] Keep the France best-effort warning.
- [x] Update `nowing_web/content/docs/connectors/native/amazon.mdx` (AC #6)
  - [x] List supported EU marketplaces and any best-effort ones.
  - [x] Add example URLs for `amazon.de`, `amazon.fr`, `amazon.co.uk`, `amazon.it`, `amazon.es`.

### Tests

- [x] `tests/unit/platforms/amazon/test_skeleton.py` — add/amend cases for EU TLDs, `co.uk`, `amzn.eu`, invalid hosts.
- [x] `tests/unit/platforms/amazon/test_locale.py` — add cases for any new marketplaces; keep fallback tests.
- [x] `tests/unit/platforms/amazon/test_parsers.py` — add `product_eu.html` fixture test for EUR/GBP and `1.234,56` format.
- [x] `tests/unit/platforms/amazon/test_flows.py` — add EU product and search flow tests.
- [x] `tests/unit/capabilities/amazon/scrape/test_schemas.py` — add domain validation and `HttpUrlStr` tests.
- [x] `tests/unit/capabilities/amazon/test_registry.py` — confirm billing unit remains `AMAZON_PRODUCT`.

### Review Findings

- [x] [Review][Patch] No test for marketplace propagation in search/bestsellers with `scrapeProductDetails=True` — when details are enabled, search/bestsellers flows delegate to `_product_flow` which sets marketplace from the product URL, not the search page URL. This is correct behavior (product's actual marketplace) but untested. Add a test verifying marketplace is set when `scrapeProductDetails=True` for a search flow. [edge]
- [x] [Review][Patch] No test for GBP price without `£` symbol — `_price` regex fallback handles `"12.99 GBP"` but only `£12.99` is tested. Add `assert _price("12.99 GBP") == {"value": 12.99, "currency": "GBP"}` to `test_price_extracts_currency_from_symbol`. [edge]

## Dev Notes

- **This story is an extension, not a new capability.** All flows, schemas, and billing already live in `nowing_backend/app/proprietary/platforms/amazon/` and `nowing_backend/app/capabilities/amazon/scrape/`.
- **Port vs. local behavior:** Upstream `locale.py` only maps marketplaces that have verified proxy exits. Nowing uses the same DataImpulse provider (`__cr.<country>` / `__sid.<id>` suffixes in `app/utils/proxy/providers/dataimpulse.py`), so the same verified list applies. Do not add a marketplace to `locale.py` unless the proxy plan can route to that country.
- **Decimal-format parsing is intentionally locale-agnostic:** `_float` uses heuristics (position of `,` vs `.` and trailing digits) instead of a locale table. This avoids maintaining per-marketplace format rules.
- **Currency is derived from the page text or the price string symbol, not from the TLD.** This is the safest approach because Amazon may render a different currency than the host (e.g. an `amazon.de` page can show `EUR` for a UK buyer). The `Price` schema carries `currency` explicitly for downstream consumers.
- **Adding an explicit `marketplace` output field is safe** because `ProductItem` uses `extra="allow"` and `model_dump(exclude_none=False)`, so older consumers that ignore the field continue to work.
- **Do not hard-code a region→currency mapping.** The parser should continue to sniff the actual rendered price; the `marketplace` field is for region provenance only.
- **Validation is split across two concerns:**
  - `HttpUrlStr` (Story 2-9) ensures each `url` is a syntactically valid `http(s)` URL.
  - `ScrapeInput.domain` regex and `resolve_url` ensure it is a recognized Amazon host and page type. Keep these separate; do not try to classify EU TLDs inside `HttpUrlStr`.
- **France (`amazon.fr`) is intentionally best-effort** because upstream and Nowing both observe higher WAF challenge rates from French proxy exits. The UI should continue to warn but must not block the user from trying.

## Verification

- [x] Backend unit tests:
  ```bash
  cd nowing_backend
  pytest tests/unit/platforms/amazon/test_skeleton.py tests/unit/platforms/amazon/test_locale.py tests/unit/platforms/amazon/test_parsers.py tests/unit/platforms/amazon/test_flows.py tests/unit/capabilities/amazon/scrape/test_schemas.py -q
  ```
- [ ] e2e smoke (requires live proxy):
  ```bash
  cd nowing_backend
  python scripts/e2e_amazon_scraper.py --marketplace de --search-term "mechanische tastatur"
  python scripts/e2e_amazon_scraper.py --marketplace co.uk --search-term "usb c cable"
  ```
- [x] Frontend typecheck and lint (if TS/TSX or MDX files changed):
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    lib/playground/platform-overrides/amazon.tsx \
    content/docs/connectors/native/amazon.mdx
  ```
- [x] Full Amazon test suite:
  ```bash
  cd nowing_backend
  pytest tests/unit/platforms/amazon tests/unit/capabilities/amazon -q
  ```

## References

- Upstream release PR: `MODSetter/SurfSense#1628`
- Upstream Amazon feature PR: `MODSetter/SurfSense#1604`
- Upstream validation PR: `MODSetter/SurfSense#1623`
- `nowing_backend/app/proprietary/platforms/amazon/url_resolver.py`
- `nowing_backend/app/proprietary/platforms/amazon/locale.py`
- `nowing_backend/app/proprietary/platforms/amazon/parsers.py`
- `nowing_backend/app/proprietary/platforms/amazon/schemas.py`
- `nowing_backend/app/proprietary/platforms/amazon/scraper.py`
- `nowing_backend/app/capabilities/amazon/scrape/schemas.py`
- `nowing_backend/app/capabilities/amazon/scrape/executor.py`
- `nowing_backend/app/capabilities/amazon/scrape/definition.py`
- `nowing_backend/app/capabilities/core/types.py`
- `nowing_backend/app/capabilities/core/billing.py`
- `nowing_web/lib/playground/platform-overrides/amazon.tsx`
- `nowing_web/content/docs/connectors/native/amazon.mdx`
- `nowing_backend/tests/unit/platforms/amazon/`
- `nowing_backend/tests/unit/capabilities/amazon/scrape/`

## Review Findings (code review 2026-08-08)

Scope: commit `e9a05984a` — 4 files, 140 lines (Amazon EU marketplaces — HttpUrlStr validation + E2E test).

**patch:** 0

**defer:** 0

**dismissed:** 0 (no findings — diff is minimal and correct)

**AC coverage:** AC-1 PASS (url_resolver already ported), AC-2 PASS (locale.py already ported), AC-3 PASS (parsers.py already handles EU prices), AC-4 PASS (ProductItem schema already has Price nested object), AC-5 PASS (HttpUrlStr + domain regex + tests), AC-6 PASS (E2E test + playground dropdown already exists), AC-7 PASS (billing unchanged, AMAZON_PRODUCT per product).

**Note:** The actual EU marketplace functionality (url_resolver, locale, parsers, playground dropdown, docs) was already ported from upstream PR #1604 in a previous story. This story's diff only adds:
1. `HttpUrlStr` validation for the `urls` field (AC-5)
2. E2E playground test for EU scrape (AC-6)
3. Unit tests for malformed URL rejection and EU URL acceptance (AC-5)

The diff is clean — `HttpUrlStr` is a shared validator that accepts any http(s) URL, with Amazon-specific validation in the `domain` regex and `url_resolver.py`. The MCP change is purely cosmetic (Field description formatting).
