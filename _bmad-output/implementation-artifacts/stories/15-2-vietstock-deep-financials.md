# Story 15.2: Vietstock Deep Financials

**Status:** ready-for-dev
**Epic:** Epic 15 — Financial Data (Vietnam)
**Priority:** P1

## Story

As a deep researcher,
I want comprehensive financial data from Vietstock (3000+ companies, 130K+ statements),
So that I can perform historical analysis and cross-company comparison.

## Scope Notes

- This story builds the **Vietstock capability** (`vietstock.scrape`): cookie-authenticated deep financials, 20+ years historical data, and cross-source canonical `sourceId` with CafeF.
- It reuses the file structure, billing, and chainlens-ingest pattern from **Story 15.1 (CafeF)**.
- News is out of scope unless it falls out naturally from the scraper; focus on financial statements and ratios.
- Chat subagent / subagent integration is out of scope; covered by follow-up stories if needed.

## Dependencies

- **Story 15.1 — CafeF Financial Data Integration** (`done`): provides the financial scraper pattern, `to_chunks`, `NowingIngestService`, and shared ratio normalization helpers.
- **Story 20.1 — Nowing Scraper `to_chunks()` + `NowingIngestService`** (`done`): required for `POST /v1/ingest/scraper` contract.
- **Story 20.4 — Service-to-Service Auth + Cost Ledger Sync** (`done`): required for chainlens-research auth and cost accounting.
- **Story 3.13 / 3.14** are NOT hard dependencies; memory provenance and bounded injection are cross-cutting but do not block the scraper capability.

## Architecture Context

### License Boundary (AD-16)

- `app/proprietary/platforms/vietstock/` — **BSL 1.1** (fetcher, cookie/session handling, anti-bot, parser).
- `app/capabilities/vietstock/` — **Apache-2.0** (capability registration, executor, schemas, REST/MCP contracts).

### File Structure

```text
nowing_backend/app/
├── proprietary/platforms/vietstock/        # BSL 1.1
│   ├── __init__.py
│   ├── fetch.py                             # HTTP client, cookie auth/refresh, rate limiting
│   ├── parsers.py                           # Parse statements, normalize ratios
│   ├── schemas.py                           # VietstockScrapeInput/Output, Quote, Financials
│   └── scraper.py                           # Orchestrator with test seams
└── capabilities/vietstock/scrape/           # Apache-2.0
    ├── __init__.py
    ├── definition.py                        # Capability registration
    ├── executor.py                          # Bind scraper, calculate cost, ingest chunks
    └── schemas.py                           # Capability I/O contracts
```

### Authentication

- Vietstock requires a **cookie-based session** (unlike CafeF, which is public API).
- Use `ScraperPlatformAccountService` / `ScraperPlatformAccountRotator` if credentials are managed; otherwise use env/session cookie with refresh logic.
- On `401/403`, attempt **one** cookie refresh and retry. If refresh fails, mark `degraded=true` with `degradation_reason: AUTH_REFRESH_FAILED`.
- Do NOT log raw session cookies or tokens.

### Billing

- Add `BillingUnit.VIETSTOCK_DATA` in `app/capabilities/core/types.py`.
- Add `VIETSTOCK_DATA_MICROS_PER_ITEM` (default e.g. 5000 micro-USD) in `app/config/__init__.py`.
- Add mapping in `app/capabilities/core/billing.py` (`_PLATFORM_RATE_KEYS`, `_UNIT_NOUNS`).
- `cost_micros = billable_units * VIETSTOCK_DATA_MICROS_PER_ITEM` when not degraded.
- `billable_units = 0 if degraded or quote is None else 1` (same as CafeF).
- Degraded runs are **free**.

### Rate Limiting

- `VIETSTOCK_RATE_LIMIT_RPS` (default ~10 req/min or lower; Vietstock is stricter than CafeF).
- Process-local `asyncio.Lock` throttle in `fetch.py`.
- Exponential backoff on 429.
- Add per-call timeout for historical-data fetches to avoid blocking the whole scrape.

### Data Model

- `VietstockQuote`: current price, OHLCV, change, key ratios (P/E, P/B, ROE, ROA).
- `VietstockFinancials`: balance sheet, income statement, cash flow with 20+ years historical periods.
- `VietstockScrapeInput`: `symbol`, `include_financials`, `include_news` (optional), `max_news`.
- `VietstockScrapeOutput`: quote/financials/news, `degraded`, `degradation_reason`, `billable_units`.

### Ratios Normalization

- Store P/E, P/B, ROE, ROA as comparable numeric values.
- Normalize string formats: `"12.5"`, `"12,5"`, `"12.5x"`, `"18.5%"` → `12.5`, `12.5`, `12.5`, `18.5`.
- Put numeric ratios in `metadata.ratios` and also in `content` for human-readable chunk text.

### Cross-Source sourceId (AD-24)

- Use canonical identity: `symbol + statement_type + period`.
- Hash the sorted canonical fields to produce a stable `sourceId`.
- Prefix with domain: `vietstock:sha256:<digest>`.
- CafeF and Vietstock chunks for the same `(symbol, statement_type, period)` should share the same canonical hash so `chainlens-research` can merge.
- Set `metadata.conflict_flags` and `metadata.source_count` to let the canonical index handle cross-source merge; **Nowing does NOT merge locally**.

### Ingestion

- Convert financial records to `Chunk[]` via `to_chunks()` in `app/services/scraper_chunks/serializer.py`.
- Call `NowingIngestService.ingest(scraper_id="vietstock.scrape", chunks=chunks, workspace_id=...)`
- Metadata: `source: 'nowing_scraper'`, stable `sourceId`, `domain: 'vietstock.com'` or `vietstock.vn`, `fetchedAt`, `contentType: 'financial_statement'`, `metadata.ratios`, `metadata.conflict_flags`, `metadata.source_count`.
- Handle 409 duplicate → noop; 5xx/timeout → retry (max 3) + dead-letter queue.

## Architecture Decisions

- **AD-16:** Three-tier license boundary — proprietary BSL 1.1, capability Apache-2.0.
- **AD-24:** Cross-source `sourceId` convention — canonical identity + `conflict_flags` + `source_count`.
- **AD-34:** Scraper output feeds `chainlens-research` via `POST /v1/ingest/scraper`.
- **AD-35:** Nowing does not build a public/vertical financial corpus; unified search belongs in `chainlens-research`.
- **AD-8:** Unified credit wallet — `TokenUsage` and `BillingEvent` debit the same `User.credit_micros_balance`.
- **AD-25:** PII redaction pipeline applies to chunk content before indexing/ingest (minimal for public company data, but must pass through pipeline).

## Acceptance Criteria

- **Given** the Vietstock scraper is authenticated, **When** a company is queried, **Then** 20+ years of historical financial statements are fetched.
- **Given** financial ratios are extracted, **When** normalized to `Chunk[]`, **Then** P/E, P/B, ROE, ROA are stored as comparable numeric values in `content` and `metadata.ratios`.
- **Given** Vietstock data conflicts with CafeF for the same symbol and period, **When** both source `Chunk[]` are produced, **Then** each chunk is sent with the same canonical `sourceId` (normalized `symbol + statement + period`) and `metadata.conflict_flags` and `metadata.source_count` so `chainlens-research` canonical index handles cross-source merge; Nowing does not merge them locally.
- **Given** a batch of Vietstock `Chunk[]`, **When** `NowingIngestService.ingest()` is called, **Then** it calls `POST /v1/ingest/scraper` and returns `ingestJobId`.
- **Given** the cookie-based session expires, **When** the scraper detects `401/403`, **Then** it refreshes the cookie and retries once; if refresh fails, it marks `degraded=true` with `degradation_reason: AUTH_REFRESH_FAILED`.

## Validation

- Unit test: `test_vietstock_auth.py` — cookie refresh works, 401/403 degrades with `AUTH_REFRESH_FAILED`.
- Unit test: `test_vietstock_ratio_normalization.py` — P/E, P/B, ROE, ROA normalized to comparable floats across formats.
- Unit test: `test_vietstock_parsers.py` — financial statements parsed accurately for historical/grouped/flat structures.
- Unit test: `test_vietstock_to_chunks.py` — chunk metadata includes canonical `sourceId`, `conflict_flags`, `source_count`, and `metadata.ratios`.
- Integration test: `test_vietstock_chainlens_feed.py` — `POST /v1/ingest/scraper` called with correct auth and batch.
- Integration test (optional/live): `test_vietstock_api_connection.py` — live API responds correctly when credentials configured.
- Ruff pass on `app/proprietary/platforms/vietstock`, `app/capabilities/vietstock`, and related tests.

## Implementation Notes

1. **Clone CafeF pattern** for `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, `definition.py`, `executor.py`, and capability `schemas.py`.
2. **Add billing plumbing** before writing the executor: `BillingUnit.VIETSTOCK_DATA`, config variables, and billing mapping.
3. **Implement demo mode** (`VIETSTOCK_DEMO_MODE`) with deterministic synthetic data so unit/integration tests can run without live credentials.
4. **Use test seams** (`*_fn` parameters) in `scrape_vietstock()` for unit tests, matching CafeF.
5. **Reuse `_as_float` / `_parse_change_string` helpers** from CafeF where possible; do not duplicate if they are shared utilities.
6. **Do not implement news indexing** unless it is trivial; if included, it must be optional and not fail the whole scrape.
7. **Cross-source sourceId**: coordinate with Story 15.1 to ensure both CafeF and Vietstock use the same canonical hash input for `(symbol, statement_type, period)`.
8. **P0 credit surface touched**: this story touches billing (`BillingUnit`, `cost_micros`). It must pass `bmad-nowing-mutation-gate` and `bmad-nowing-human-review-gate` before `done`.

## Open Questions

- What is the exact Vietstock login/session endpoint and cookie refresh mechanism? (Spike before implementation if unknown.)
- What is the correct default `VIETSTOCK_RATE_LIMIT_RPS` and `VIETSTOCK_DATA_MICROS_PER_ITEM`? (Align with product/commercial after a live probe.)
- Should Vietstock financial records be split by period into multiple chunks or one large chunk? (Default: one chunk per `(symbol, statement_type, period)` to match canonical `sourceId`.)

## Tags

AD-16, AD-24, AD-34, AD-35, AD-8, AD-25, Vietstock, financial data, stock price, Vietnam, cookie auth, rate limit, billing, chainlens-ingest, cross-source
