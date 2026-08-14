# Story 15.1: CafeF Financial Data Integration

**Status:** done
**Epic:** Epic 15 — Financial Data (Vietnam)
**Priority:** P0

## Story

As an investment researcher,
I want stock prices, financial statements, and market news from CafeF,
So that I can analyze company fundamentals without leaving Nowing.

### Scope Notes

- This story covers the **CafeF capability** (API Playground + `cafef.scrape` endpoint): quote, financial statements, news, rate-limiting, and billing.
- **Chat subagent integration** for CafeF has been split to a follow-up story because it is outside the explicit scope of Story 15.1. See `15-1b-cafef-chat-subagent-integration.md`.

## Dependencies

- **Epic 20 — Nowing Ecosystem Integration** (stories 20.1, 20.2, 20.4) must be `done`: provides `NowingIngestService`, `POST /v1/ingest/scraper` contract, service-to-service auth, and cost ledger sync.
- **Story 6.8 — Generic Alert Engine** is NOT a hard dependency for 15.1, but is required for 15.3 (Stock Price Alerts) and 15.4 (Financial Trend Detection).

## Architecture Context

### File Structure

```text
nowing_backend/app/
├── proprietary/platforms/cafef/          # BSL 1.1 (fetch, parsers, schemas, scraper)
│   ├── __init__.py
│   ├── fetch.py                           # HTTP client, rate limiting, 429 retry
│   ├── parsers.py                         # Quote / financials / news parsers
│   ├── schemas.py                         # Pydantic: Quote, Financials, News, ScrapeInput/Output
│   └── scraper.py                         # Orchestrator with degradation handling
├── capabilities/cafef/scrape/             # Apache-2.0 (capability surface)
│   ├── __init__.py
│   ├── definition.py                      # Capability registration + BillingUnit.CAFEF_DATA
│   ├── executor.py                        # Cost calc, news indexing, progress emission
│   └── schemas.py                         # Capability I/O contracts
└── agents/chat/multi_agent_chat/subagents/builtins/cafef/  # split to 15-1b
```

### Billing

- `BillingUnit.CAFEF_DATA` in `app/capabilities/core/types.py`.
- `CAFEF_DATA_MICROS_PER_ITEM` (default 5000 micro-USD ≈ $0.005) in `app/config/__init__.py`.
- `cost_micros = billable_units * CAFEF_DATA_MICROS_PER_ITEM` when not degraded.
- `billable_units = 0 if degraded or quote is None else 1`.
- Degraded runs are **free** (`cost_micros = 0`).

### Rate Limiting

- `CAFEF_RATE_LIMIT_RPS = 20/60` (20 requests per minute).
- Process-local `asyncio.Lock` throttle in `fetch.py`.
- Exponential backoff on 429: `_MAX_429_RETRIES = 2`, `_BACKOFF_BASE_S = 1.0`.

### Ingestion

- Financial statement chunks use `NowingIngestService.ingest()` with `scraper_id="cafef"`.
- News articles are indexed locally via `IndexingPipelineService` as `NEWS_CONNECTOR` documents for workspace search.
- Chunk metadata must include `source: 'nowing_scraper'`, stable `sourceId`, `domain: 'cafef.vn'`, `fetchedAt`, and `contentType`.

## Architecture Decisions

- **AD-27 / AD-34:** Scraper output feeds `chainlens-research` via `POST /v1/ingest/scraper`.
- **AD-35:** Nowing does not build a public/vertical financial corpus; unified search belongs in `chainlens-research`.
- **AD-16:** License boundary — `app/proprietary/platforms/cafef/` is BSL 1.1; `app/capabilities/cafef/` is Apache-2.0.
- **AD-25:** PII redaction pipeline applies to chunk content before indexing/ingest.
- **AD-8:** Unified credit wallet — `TokenUsage` and `BillingEvent` debit the same `User.credit_micros_balance`.

## Acceptance Criteria

- **Given** CafeF unofficial API is connected, **When** a user queries a stock symbol, **Then** current price, OHLCV, volume, change, change_percent, and key ratios are returned.
- **Given** financial statements are fetched, **When** normalized to `Chunk[]`, **Then** each chunk has `metadata.source: 'nowing_scraper'`, a stable `sourceId` (symbol + statement type + period), `domain: 'cafef.vn'`, `fetchedAt`, `contentType`, and the statement data (balance sheet, income statement, cash flow).
- **Given** market news is fetched, **When** the batch is ready, **Then** it is indexed into workspace search (news documents) and, where applicable, sent to `chainlens-research` via `NowingIngestService` for unified search.
- **Given** the user queries financial data in chat, **When** the chat agent calls `chainlens-research` `POST /api/v1/search`, **Then** it returns indexed CafeF data with citations.
- **Given** data is fetched, **When** rate limit approached (20 req/min), **Then** requests are throttled gracefully with exponential backoff and a `degraded` flag is set if throttling exceeds a configurable timeout.
- **Given** `chainlens-research` is unavailable, **When** `NowingIngestService.ingest()` is called, **Then** it retries with exponential backoff (max 3 attempts), stores the failed batch in a dead-letter queue after max retries, and returns `ingestJobId: null` with `degraded=true`.

## Validation

- Integration test: `test_cafef_api.py` — executor → database persistence and news indexing.
- Integration test: `test_cafef_throttling.py` — rate limit enforced.
- Unit test: `tests/unit/platforms/cafef/test_parsers.py` — financial statements parsed accurately for demo/live/grouped/flat formats.
- Unit test: `tests/unit/platforms/cafef/test_scraper.py` — degradation handling and billable units logic.
- Unit test: `tests/unit/capabilities/cafef/scrape/test_executor.py` — cost calculation and `cost_micros = 0` when degraded.
- Ruff pass on `app/proprietary/platforms/cafef`, `app/capabilities/cafef`, and related tests.

## Tags

AD-27, AD-34, AD-35, AD-16, AD-25, AD-8, CafeF, financial data, stock price, Vietnam, rate limit, billing, chainlens-ingest

## Review Findings

- [x] [Review][Decision] Chat subagent integration is outside the explicit scope of Story 15.1 — split into follow-up story `15-1b-cafef-chat-subagent-integration.md`.
- [x] [Review][Patch] `tests/unit/agents/multi_agent_chat/test_subagent_composition.py:28` `_EXPECTED_SUBAGENTS` missing `"cafef"` — fixed. (source: Blind Hunter + Acceptance Auditor)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/main_agent/middleware/mode_budget.py:63` `_WEB_RESEARCH_SUBAGENTS` missing `"cafef"` — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/subagents/builtins/cafef/system_prompt.md:18` missing `<include snippet="run_reader"/>` — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/kb_first.md:4` missing `task(cafef, ...)` routing example — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/subagents/builtins/cafef/tools/index.py:27` missing Story 3.13 attribution comment for `user_id` — fixed. (source: Acceptance Auditor)
