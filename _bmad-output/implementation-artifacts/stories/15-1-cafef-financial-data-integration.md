# Story 15.1: CafeF Financial Data Integration

**Status:** in-progress
**Epic:** Epic 15 — Financial Data (Vietnam)
**Priority:** P0

## Story

As an investment researcher,
I want stock prices, financial statements, and market news from CafeF,
So that I can analyze company fundamentals without leaving Nowing.

## Acceptance Criteria

- **Given** CafeF unofficial API is connected, **When** a user queries a stock symbol, **Then** current price, OHLCV, and key ratios are returned.
- **Given** financial statements are fetched, **When** stored, **Then** balance sheet, income statement, and cash flow are available per company.
- **Given** market news is fetched, **When** new articles are published, **Then** they appear in workspace search.
- **Given** data is fetched, **When** rate limit approached (20 req/min), **Then** requests are throttled gracefully.

## Validation

- Integration test: `test_cafef_api_connection.py` — API responds correctly.
- Unit test: `test_cafef_financial_parsing.py` — financial statements parsed accurately.
- Rate limit test: `test_cafef_throttling.py` — graceful throttling.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, CafeF, financial data, stock price, Vietnam, rate limit
