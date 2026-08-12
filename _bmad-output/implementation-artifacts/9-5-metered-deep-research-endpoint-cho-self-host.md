

## File List

- `nowing_backend/app/routes/self_host_research.py` — new route `POST /v1/self-host/research`, auth, rate limit, cost/billing, degradation.
- `nowing_backend/app/routes/personal_access_tokens_routes.py` — allow `token_kind='self_host'` PAT creation.
- `nowing_backend/app/app.py` — mount `self_host_research_router` at `/v1`.
- `nowing_backend/app/config/__init__.py` — add `SELF_HOST_RESEARCH_COST_MULTIPLIER` env config.
- `nowing_backend/tests/unit/routes/test_self_host_research.py` — 10 unit tests.
- `nowing_backend/.env.example` — document self-host research env vars.
- `README.md` — self-host deep research guide and comparison table update.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status `9-5: in-progress` → `9-5: review`.

## Dev Agent Record

### Implementation Plan

- Chose to reuse `personal_access_tokens` with `token_kind='self_host'` instead of a new table; the existing `token_kind` column (Epic 18) already supports scoped PATs and avoids a migration.
- Built a dedicated `self_host_research.py` router to keep the auth/billing/quota logic isolated from the workspace-scrapers door pattern, while reusing `build_research_executor`, `wallet_credit`, `record_token_usage`, and `ChainLensServiceAuth`.
- Rate limit is per API key (hashed) using Redis + in-process fallback, mirroring `enforce_capability_rate_limit` but keyed by self-host token instead of workspace.
- Pre-flight balance check uses `fallback_micros * multiplier` so the engine is not wasted when the wallet is empty; post-call billing uses the actual engine `cost_micros` (or fallback) with 1.5× margin.
- Degradation preserves FR-38: missing/invalid key → 401; ChainLens unconfigured → `engine_unavailable`; upstream 429/5xx/timeout → `engine_unavailable` with appropriate reason.

### Completion Notes

- All 10 unit tests pass.
- `ruff check` clean on changed files.
- Relevant regression suites (chainlens research unit, access/rest, agent tools) pass: 293 passed, 1 skipped.
- Docs updated in `README.md` and `.env.example`.

### Debug Log

- Initial route draft added a `correlation_id` field to a `ResearchInput` subclass, but `ResearchInput` does not accept `correlation_id` and it was unnecessary; removed and used `uuid4()` for `run_id`.
- Unit tests initially returned `SimpleNamespace` from the fake executor; FastAPI/Pydantic serialization required real `ResearchOutput`/`Source` models.
- Mock `ChainLensServiceAuth` needed an `__init__` accepting `*args, **kwargs` because the route instantiates it with `config_obj=config`.

## Change Log

- 2026-08-12: Implement `POST /v1/self-host/research` route with PAT auth, rate limit, cost multiplier, wallet debit, and TokenUsage recording.
- 2026-08-12: Add `SELF_HOST_RESEARCH_COST_MULTIPLIER` config and support `token_kind='self_host'` PAT creation.
- 2026-08-12: Update `README.md` self-host comparison table and add "Use deep research on self-host" section; update `.env.example`.
- 2026-08-12: Add 10 unit tests in `tests/unit/routes/test_self_host_research.py`.
- 2026-08-12: Mark story 9-5 as `review` in sprint-status and story file.

## Status

`review` — implementation complete, unit tests pass, lint clean, ready for code review.
