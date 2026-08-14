# Story 15.1: CafeF Financial Data Integration

**Status:** pending-human-review
**Epic:** Epic 15 — Financial Data (Vietnam)
**Priority:** P0

## Story

As an investment researcher,
I want stock prices, financial statements, and market news from CafeF,
So that I can analyze company fundamentals without leaving Nowing.

### Scope Notes

- This story covers the **CafeF capability** (API Playground + `cafef.scrape` endpoint): quote, financial statements, news, and rate-limiting.
- **Chat subagent integration** for CafeF has been split to a follow-up story because it is outside the explicit scope of Story 15.1.

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

### Review Findings

- [x] [Review][Decision] Chat subagent integration is outside the explicit scope of Story 15.1 — split into follow-up story `15-1b-cafef-chat-subagent-integration.md`.
- [x] [Review][Patch] `tests/unit/agents/multi_agent_chat/test_subagent_composition.py:28` `_EXPECTED_SUBAGENTS` missing `"cafef"` — fixed. (source: Blind Hunter + Acceptance Auditor)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/main_agent/middleware/mode_budget.py:63` `_WEB_RESEARCH_SUBAGENTS` missing `"cafef"` — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/subagents/builtins/cafef/system_prompt.md:18` missing `<include snippet="run_reader"/>` — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/kb_first.md:4` missing `task(cafef, ...)` routing example — fixed. (source: Blind Hunter)
- [x] [Review][Patch] `app/agents/chat/multi_agent_chat/subagents/builtins/cafef/tools/index.py:27` missing Story 3.13 attribution comment for `user_id` — fixed. (source: Acceptance Auditor)
