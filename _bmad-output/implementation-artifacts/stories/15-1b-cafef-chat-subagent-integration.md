# Story 15.1b: CafeF Chat Subagent Integration

**Status:** done
**Epic:** Epic 15 — Financial Data (Vietnam)
**Priority:** P1
**Split from:** Story 15.1 — CafeF Financial Data Integration

## Story

As a chat user,
I want the Nowing chat agent to delegate Vietnamese stock questions to a CafeF specialist,
So that I can get live stock quotes, financial statements, and market news without leaving chat.

## Acceptance Criteria

- **Given** the CafeF capability exists, **When** a user asks about a Vietnamese stock symbol in chat, **Then** the main agent dispatches `task(cafef, ...)` and the CafeF subagent returns live data.
- **Given** the subagent is registered, **When** the registry is validated, **Then** the composition guardrail test includes `"cafef"`.
- **Given** the chat runs in `speed`/`balanced`/`quality` mode, **When** the subagent is invoked, **Then** it is subject to the same web-research mode gating as other market-data subagents.
- **Given** a CafeF scrape result is large, **When** the subagent needs more data, **Then** it pages stored runs via `read_run`/`search_run` instead of re-scraping.

## Validation

- Unit test: `test_subagent_composition.py` passes with `"cafef"` in `_EXPECTED_SUBAGENTS`.
- Unit test: `test_mode_budget.py` (or equivalent) includes `"cafef"` in web-research gating.
- Playwright E2E: `tests/chat/cafef-chat.spec.ts` passes — chat stream routes through `task(cafef)` and `cafef_scrape`, UI renders response without crashing, and session expiry redirects to `/login`.
- Ruff pass on all changed files.

## Tasks

- [x] Create `cafef` subagent package (`agent.py`, `tools/index.py`, `description.md`, `system_prompt.md`, `__init__.py`).
- [x] Register `cafef` in `SUBAGENT_BUILDERS_BY_NAME` and `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`.
- [x] Update `tests/unit/agents/multi_agent_chat/test_subagent_composition.py`.
- [x] Add `"cafef"` to `_WEB_RESEARCH_SUBAGENTS` in `mode_budget.py`.
- [x] Add `<include snippet="run_reader"/>` to `cafef/system_prompt.md`.
- [x] Add `task(cafef, ...)` example to `kb_first.md`.
- [x] Add Story 3.13 attribution comment to `cafef/tools/index.py`.

## Tags

AD-27, CafeF, chat subagent, financial data, Vietnam
