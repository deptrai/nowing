---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 2-6-indeed-jobs-scraper
status: ready-for-dev
---

# Story 2.6: Indeed Jobs Scraper

**Status:** ready-for-dev
**Epic:** 2 — Connectors
**Priority:** HIGH
**Requirements:** FR-6
**Architecture:** AD-19 (anti-bot taxonomy)
**Dependencies:** Existing scraper framework (warm browser, block detection, billing units). Story 2.9 (Scraper API Input Validation) is a downstream consumer that inherits the same `HttpUrlStr` contract for URL fields.

## Story

As a recruiter or market researcher,
I want to scrape job listings and job details from Indeed,
So that I can track hiring trends, competitor headcount, and job market signals in my workspace.

## Context

### Upstream reference

SurfSense PR #1605 (`MODSetter/SurfSense#1605`, merged 2026-07-19) already implemented the Indeed scraper we need to port. It adds a single `indeed.scrape` verb that is self-contained and touches the same layers as the existing Reddit/Amazon scrapers in Nowing.

Key files and patterns from the upstream PR:

- **Platform scraper package** (`surfsense_backend/app/proprietary/platforms/indeed_jobs/`)
  - `url_resolver.py`: classifies a start URL into `search` (`/jobs?q=...`, `https://www.indeed.com/jobs` with query params) or `job` (`/viewjob?jk={id}`, `/rc/clk?...&jk={id}`) page kinds; returns `ResolvedUrl(kind, url, job_key, domain)`.
  - `parsers.py`: parses jobs from **embedded JSON** on the search results page and the `/viewjob` detail page. Job card extraction yields `title`, `company`, `salary`, `location`, `remote` (hybrid/remote/on-site), `posting_date`, and `apply_url`. Detail extraction additionally yields the full job description, requirements, benefits, and apply link.
  - `schemas.py`: `IndeedScrapeInput` (query string or start URLs, `scrape_job_details` flag), `JobItem`, `ErrorItem`. Outputs use `extra="allow"` and `to_output()` to keep the contract open.
  - `fetch.py`: warmed camoufox session (Cloudflare solve + homepage warm) with residential proxy rotation, `is_blocked()` on challenge markers, `_MAX_IP_ATTEMPTS` rotation, rate-limit/backoff.
  - `scraper.py`: async streaming core. `iter_jobs()` pages search results (with a `max_items`/`max_pages` cap), optionally enriches each card into a full `/viewjob` detail page when `scrape_job_details=True`, and dedupes by `job_key`. Emits in-stream error items, not exceptions.

- **Capability registration** (`surfsense_backend/app/capabilities/indeed/`)
  - `scrape/definition.py`: `Capability(name="indeed.scrape", billing_unit=BillingUnit.INDEED_JOB, docs_url="/docs/connectors/native/indeed")`.
  - `scrape/executor.py`: maps agent-facing `ScrapeInput` (`query`, `location`, `radius`, `sort`, `urls`, `scrape_job_details`, `max_items`) to `IndeedScrapeInput` and calls the platform scraper.
  - `scrape/schemas.py`: agent REST/MCP surface with caps on query length and `max_items` (1–100), `estimated_units`, and `billable_units` (count non-error items).

- **Billing and config**
  - `app/capabilities/core/types.py`: added `INDEED_JOB` to `BillingUnit`.
  - `app/capabilities/core/billing.py`: mapped `INDEED_JOB` → `INDEED_SCRAPE_MICROS_PER_ITEM` (noun `job`).
  - `app/config/__init__.py`: added `INDEED_SCRAPE_MICROS_PER_ITEM` rate default.

- **Agent subagent** (`surfsense_backend/app/agents/chat/multi_agent_chat/subagents/builtins/indeed/`)
  - `agent.py`, `description.md`, `system_prompt.md`, `tools/index.py` with `NAME = "indeed"` and `_CI_VERBS = [INDEED_SCRAPE]`.
  - Registry and constants updated: `SUBAGENT_BUILDERS_BY_NAME["indeed"]`, `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP["indeed"] = frozenset()`, and main-agent prompts (`identity/private.md`, `identity/team.md`, `kb_first.md`, `routing.md`) mention `indeed` alongside the other market specialists.

- **MCP tool** (`surfsense_mcp/mcp_server/features/scrapers/platforms/indeed.py`)
  - `surfsense_indeed_scrape` (Nowing equivalent: `nowing_indeed_scrape`).

- **Frontend/marketing** (SurfSense)
  - `surfsense_web/lib/playground/catalog.ts` and `platform-icons.tsx`.
  - `surfsense_web/lib/connectors-marketing/indeed.tsx`.
  - `surfsense_web/content/docs/connectors/native/indeed.mdx` and `meta.json`.
  - `surfsense_web/public/connectors/indeed.svg`.

### Nowing current state

- The Nowing backend already has the same capability framework as SurfSense. Existing native scrapers live in `nowing_backend/app/proprietary/platforms/` (`amazon/`, `reddit/`, `youtube/`, `tiktok/`, `instagram/`, `google_maps/`, `batdongsan/`). The `batdongsan/` package (Story 10.1, merged as `7a38d5310`) is the most recent port and shows the exact Nowing conventions: `url_resolver.py`, `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, plus `nowing_backend/app/capabilities/<platform>/scrape/`. There is **no** `indeed_jobs/` or `indeed/` directory yet.
- `nowing_backend/app/capabilities/core/types.py` currently defines `BillingUnit` with no `INDEED_JOB` entry.
- `nowing_backend/app/capabilities/core/billing.py` maps platform meters to `config` rate keys and display nouns (`_PLATFORM_RATE_KEYS`, `_UNIT_NOUNS`); it has no Indeed mapping.
- `nowing_backend/app/config/__init__.py` (platform scrape billing block, ~line 864) has `PLATFORM_SCRAPE_BILLING_ENABLED` and all platform micro-rates; no `INDEED_*` keys.
- `nowing_backend/app/routes/__init__.py` imports `app.capabilities.<platform>` for side-effect registration (line 4-13: amazon, batdongsan, chainlens, google_maps, google_search, instagram, reddit, tiktok, web, youtube); `app.capabilities.indeed` does not exist.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/registry.py` and `constants.py` have no `indeed` route; `subagents/builtins/` has no `indeed/`.
- `nowing_mcp/mcp_server/features/scrapers/__init__.py` (`_REGISTRARS` tuple) and `platforms/` have no `indeed.py`.
- `nowing_mcp/mcp_server/selfcheck.py` `EXPECTED_TOOLS` and `nowing_backend/app/mcp_tools.py` `MCP_TOOL_CATALOG` do not list `nowing_indeed_scrape`.
- `nowing_web/lib/playground/catalog.ts` and `platform-icons.tsx` do not list Indeed.
- `nowing_web/lib/connectors-marketing/index.ts` does not export an Indeed page.
- `nowing_web/content/docs/connectors/native/meta.json` and `index.mdx` do not list Indeed; `nowing_web/public/connectors/indeed.svg` does not exist.
- Story 2.9 is ready-for-dev and will introduce a shared `HttpUrlStr` validator. The Indeed capability can ship with `list[str]` URL fields to match the current Amazon pattern, then adopt `HttpUrlStr` when 2.9 lands, or use it directly if 2.9 merges first. The two stories must not fight over the same schema files.

### Gaps to close for this story

1. The entire platform package, capability, billing unit, subagent, MCP tool, and frontend surface must be created — this is a new-capability port, not an extension.
2. Indeed's anti-bot posture (Cloudflare) is the heaviest of any platform in the current set. The port must keep the **warmed session pattern** (Cloudflare solve + homepage warm) rather than dropping to a cold-browser fetch like some lighter platforms. Nowing already has this exact seam: `reddit/fetch.py` is a "browser-warm, HTTP-fetch" port of `youtube/innertube.py` (warm camoufox/patchright session on a sticky proxy IP, then HTTP-fetch). Reuse that pattern for Indeed.
3. `sort` values in the upstream differ per market (Indeed US: `date`/`relevance`/`salary`/`rating`; non-US markets vary). Decide whether the capability exposes a literal enum or a free string with a documented default — match the upstream surface to avoid porting drift.
4. Salary parsing: Indeed renders salary as human text (e.g. "$70,000 - $90,000 a year"). Upstream keeps it as text; do not invent a structured salary parser in this story unless the epics require it (it does not).
5. `scrape_job_details=True` multiplies request volume (one detail page per card). Cap concurrent detail enrichment (`gather_bounded`) and honor `max_items` as a hard ceiling on billed items so a single call cannot explode the wallet.
6. Indeed is geo-localized: results vary by `country`/market domain (`indeed.com` vs `indeed.co.uk`, etc.). The upstream pins US for the MVP. Keep `country`/domain out of the MVP surface or expose a documented `domain` default of `www.indeed.com`, mirroring Amazon's `domain` field.

## Acceptance Criteria

1. **Search scraping**
   - **Given** a search query with optional title, location, radius, and sort, **When** I call `indeed.scrape`, **Then** it returns paginated job cards with `title`, `company`, `location`, `salary`, `summary`, `posting_date`, and `apply_url`.

2. **Job detail scraping**
   - **Given** a job detail URL (`/viewjob`), **When** I call `indeed.scrape` with `scrape_job_details=true`, **Then** it returns full job description, requirements, benefits, and apply link.

3. **Anti-bot & pagination**
   - **Given** a page is blocked or gated, **When** scraping, **Then** the scraper returns a typed `block_type` matching the existing `BlockType` taxonomy (`ok`, `rate_limited`, `cloudflare`, `empty`, `unknown`) and stops pagination without hard-failing; the run continues and emits an in-stream error item for the affected page.

4. **Billing & integration**
   - **Given** a successful scrape, **When** the run completes, **Then** billing is metered per job card returned (`INDEED_JOB` unit, config-driven `INDEED_SCRAPE_MICROS_PER_ITEM` rate), error items are never billed, and the capability is exposed via REST (`POST /workspaces/{id}/scrapers/indeed/scrape`), agent chat (`task(indeed, ...)`), and MCP (`nowing_indeed_scrape`).

5. **Deduplication**
   - **Given** a paginated search run, **When** the same job appears on multiple pages, **Then** the output contains each `job_key` at most once.

## Tasks / Subtasks

### Backend — platform scraper

- [ ] Create `nowing_backend/app/proprietary/platforms/indeed_jobs/`
  - [ ] `__init__.py` — export `IndeedScrapeInput`, `JobItem`, `ErrorItem`, `scrape_indeed`, `iter_jobs`, `resolve_url`.
  - [ ] `url_resolver.py` — `ResolvedUrl`, `resolve_url()`; classify `search` vs `job` kinds; extract `jk` job key from `/viewjob` and `/rc/clk` URLs; `indeed.` hostname guard.
  - [ ] `parsers.py` — `parse_search_page()` (embedded-JSON job cards), `parse_job_detail()` (description/requirements/benefits/apply link), salary/remote/posting-date normalization; `None`/`[]` for missing sections.
  - [ ] `schemas.py` — `IndeedScrapeInput`, `JobItem`, `ErrorItem`; `extra="allow"`; `to_output()`; error codes `invalid_url`, `job_not_found`, `no_results_found`, `blocked`.
  - [ ] `fetch.py` — warmed camoufox session (Cloudflare solve + homepage warm) with residential proxy rotation; `is_blocked()` on challenge markers and `412`/`429`/`503`; `_MAX_IP_ATTEMPTS` rotation; rate-limit/backoff; no proxy URL logging.
  - [ ] `scraper.py` — `iter_jobs()`, `scrape_indeed()`; search pagination, optional detail enrichment (`scrape_job_details=True`), dedupe by `job_key`, in-stream error items, `max_items` ceiling, progress emissions.
  - [ ] `README.md` — architecture, anti-bot notes, verification commands.

### Backend — capabilities and billing

- [ ] Create `nowing_backend/app/capabilities/indeed/`
  - [ ] `__init__.py` — import `scrape.definition` for side-effect registration.
  - [ ] `scrape/definition.py` — `INDEED_SCRAPE` `Capability` with `BillingUnit.INDEED_JOB`, `docs_url="/docs/connectors/native/indeed"`.
  - [ ] `scrape/executor.py` — `build_scrape_executor()` mapping `ScrapeInput` → `IndeedScrapeInput`, calling the platform scraper with `limit`.
  - [ ] `scrape/schemas.py` — `ScrapeInput` (`query`, `location`, `radius`, `sort`, `urls`, `scrape_job_details`, `max_items`), `ScrapeOutput` with `billable_units`.
- [ ] Update `nowing_backend/app/capabilities/core/types.py` — add `INDEED_JOB = "indeed_job"` to `BillingUnit`.
- [ ] Update `nowing_backend/app/capabilities/core/billing.py` — add `BillingUnit.INDEED_JOB` → `INDEED_SCRAPE_MICROS_PER_ITEM` in `_PLATFORM_RATE_KEYS` and noun `job` in `_UNIT_NOUNS`.
- [ ] Update `nowing_backend/app/config/__init__.py` — add `INDEED_SCRAPE_MICROS_PER_ITEM` (default ~3500, matching Reddit/Instagram items) in the platform scrape billing block.
- [ ] Update `nowing_backend/app/routes/__init__.py` — add `import app.capabilities.indeed` alongside other capability imports.

### Backend — agent subagent

- [ ] Create `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/indeed/`
  - [ ] `__init__.py`, `agent.py`, `description.md`, `system_prompt.md`, `tools/__init__.py`, `tools/index.py` loading `INDEED_SCRAPE` via `build_capability_tools()`.
- [ ] Update `nowing_backend/app/agents/chat/multi_agent_chat/subagents/registry.py` — import `build_indeed_subagent` and add `"indeed"` to `SUBAGENT_BUILDERS_BY_NAME`.
- [ ] Update `nowing_backend/app/agents/chat/multi_agent_chat/constants.py` — add `"indeed": frozenset()` to `SUBAGENT_TO_REQUIRED_CONNECTOR_MAP`.
- [ ] Update main agent prompts (`identity/private.md`, `identity/team.md`, `kb_first.md`, `routing.md`) — add Indeed to the live web data / market specialist lists.

### MCP server

- [ ] Create `nowing_mcp/mcp_server/features/scrapers/platforms/indeed.py` — register `nowing_indeed_scrape` with the same parameter surface as the REST schema.
- [ ] Update `nowing_mcp/mcp_server/features/scrapers/__init__.py` — import `indeed` and add it to `_REGISTRARS`.
- [ ] Update `nowing_mcp/mcp_server/selfcheck.py` — add `"nowing_indeed_scrape"` to `EXPECTED_TOOLS`.
- [ ] Update `nowing_backend/app/mcp_tools.py` — add `{"name": "nowing_indeed_scrape", "group": McpToolGroup.SCRAPER}` to `MCP_TOOL_CATALOG` (alphabetized).

### Frontend

- [ ] Add `nowing_web/public/connectors/indeed.svg`.
- [ ] Update `nowing_web/lib/playground/platform-icons.tsx` — export `IndeedIcon = brandIcon("/connectors/indeed.svg", "Indeed")`.
- [ ] Update `nowing_web/lib/playground/catalog.ts` — add `indeed` platform with the `indeed.scrape` verb.
- [ ] Create `nowing_web/lib/connectors-marketing/indeed.tsx` — marketing page content (slug `indeed`, icon, meta, schema, FAQ, related connectors).
- [ ] Update `nowing_web/lib/connectors-marketing/index.ts` — import and register the Indeed connector page.
- [ ] Create `nowing_web/content/docs/connectors/native/indeed.mdx`.
- [ ] Update `nowing_web/content/docs/connectors/native/meta.json` — add `indeed` to `pages`.
- [ ] Update `nowing_web/content/docs/connectors/native/index.mdx` — add an Indeed card.

### Tests

- [ ] `nowing_backend/tests/unit/platforms/indeed_jobs/`
  - [ ] `__init__.py`, `fixtures/search.html`, `fixtures/job_detail.html`, `fixtures/blocked.html`.
  - [ ] `test_parsers.py` — search card extraction, detail extraction, salary/remote/date normalization, block detection, url resolver.
  - [ ] `test_flows.py` — search pagination, detail enrichment, dedupe by `job_key`, `max_items` cap, invalid URL error item.
- [ ] `nowing_backend/tests/unit/capabilities/indeed/`
  - [ ] `__init__.py`, `test_registry.py`.
  - [ ] `scrape/test_schemas.py`, `scrape/test_executor.py`.
- [ ] `nowing_backend/scripts/e2e_indeed_scraper.py` (optional, manual live check) — exercise live search + detail with proxy.

## Dev Notes

- **Port, do not blindly copy.** The SurfSense stack is the same (FastAPI + Pydantic v2, Next.js + TypeScript, `scrapling` fetcher), but Nowing paths and naming differ. Use `nowing_backend/app/proprietary/platforms/` (not `app/services/scrapers/`), the `app.utils.proxy.ProxyProvider` seams (not SurfSense's client), and `nowing_*` MCP tool names.
- **Reuse the warm-session fetch pattern, not the cold one.** Nowing already has the exact warm-session seam the upstream Indeed flow needs: `nowing_backend/app/proprietary/platforms/reddit/fetch.py` is a "browser-warm, HTTP-fetch" port of `youtube/innertube.py` — warm a camoufox/patchright browser session on a sticky proxy IP (`get_sticky_proxy_url`), load a public page so the JS challenge runs, then HTTP-fetch through the warmed IP; rotate on 403, back off on 429. Indeed's Cloudflare-heavy posture requires this same warm-first approach; do not degrade to a cold-browser fetch like `amazon/fetch.py`'s plain `AsyncFetcher.get` flow.
- **Jobs come from embedded JSON, not the DOM.** Parse the search page's embedded JSON (the same `window._initialData`-style approach the existing parsers use); never build selectors on DOM structure that A/B tests reorder.
- **In-stream error items, not exceptions.** Follow the Amazon/batdongsan pattern: every failure for a single page/input is emitted as a dict with an `error` key (`invalid_url`, `job_not_found`, `no_results_found`, `blocked`) so the rest of the run continues. `block_type` values must match the existing `BlockType` taxonomy (`ok`, `rate_limited`, `cloudflare`, `empty`, `unknown`).
- **Billing per job card.** `indeed.scrape` is one billable unit per returned job (deduped). Error items are never billed. The `billable_units` property on `ScrapeOutput` drives `charge_capability()`. Keep `max_items` as the hard ceiling so detail enrichment cannot overspend the gate.
- **Salary stays as text.** Indeed renders salary as human text; upstream keeps it as text. Do not build a structured salary parser in this story — epics do not require it.
- **US-only for the MVP.** Upstream pins US Indeed. Keep `domain`/`country` out of the MVP or expose a documented default of `www.indeed.com` (mirror Amazon's `domain` field); do not attempt multi-market locale handling in this story.
- **Do not log proxy URLs or credentials.** The fetch layer logs status, attempt count, and timing only.
- **URL validation.** Keep URL fields as `list[str]` to match the current Amazon pattern. If Story 2.9 (`HttpUrlStr`) lands first, use `list[HttpUrlStr]` and its shared validator; if 2.6 lands first, leave a clear TODO for 2.9 to migrate the Indeed schemas.

## Verification

- [ ] Backend unit tests pass:
  ```bash
  cd nowing_backend
  pytest tests/unit/platforms/indeed_jobs -q
  pytest tests/unit/capabilities/indeed -q
  ```
- [ ] Backend lint/format:
  ```bash
  cd nowing_backend
  ruff check app/proprietary/platforms/indeed_jobs app/capabilities/indeed app/capabilities/core app/agents/chat/multi_agent_chat/subagents/builtins/indeed app/config/__init__.py app/routes/__init__.py
  ruff format app/proprietary/platforms/indeed_jobs app/capabilities/indeed app/agents/chat/multi_agent_chat/subagents/builtins/indeed
  ```
- [ ] MCP selfcheck passes (tool registered):
  ```bash
  cd nowing_mcp
  python -m mcp_server.selfcheck
  ```
- [ ] Web typecheck and lint on changed files:
  ```bash
  cd nowing_web
  pnpm tsc --noEmit
  pnpm exec biome check --max-diagnostics=500 \
    lib/playground/catalog.ts \
    lib/playground/platform-icons.tsx \
    lib/connectors-marketing/indeed.tsx \
    lib/connectors-marketing/index.ts \
    content/docs/connectors/native/indeed.mdx \
    content/docs/connectors/native/index.mdx
  ```
- [ ] Runtime smoke (requires proxy env + `SCRAPE_LIVE=1`-style flag):
  ```bash
  cd nowing_backend
  python scripts/e2e_indeed_scraper.py --query "software engineer" --location "remote"
  ```
- [ ] Playground and MCP list `indeed.scrape` after registration.

## References

- Upstream PR: `MODSetter/SurfSense#1605`
- Model story: `_bmad-output/implementation-artifacts/2-7-walmart-product-reviews-scraper.md` (same new-capability port shape)
- `nowing_backend/app/proprietary/platforms/batdongsan/` — most recent Nowing port (10.1)
  - `__init__.py`, `url_resolver.py` (n/a), `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`
- `nowing_backend/app/capabilities/batdongsan/scrape/` — `definition.py`, `executor.py`, `schemas.py`
- `nowing_backend/app/capabilities/core/` — `types.py`, `billing.py`, `store.py`, `access/rest.py`
- `nowing_backend/app/config/__init__.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/`
  - `subagents/registry.py`, `subagents/constants.py`
  - `subagents/builtins/amazon/` or `subagents/builtins/reddit/` — template for a specialist subagent
  - `main_agent/system_prompt/prompts/identity/private.md`, `identity/team.md`, `kb_first.md`, `routing.md`
- `nowing_mcp/mcp_server/features/scrapers/` — `__init__.py`, `platforms/amazon.py`, `capability.py`
- `nowing_mcp/mcp_server/selfcheck.py` (`EXPECTED_TOOLS`)
- `nowing_backend/app/mcp_tools.py` (`MCP_TOOL_CATALOG`)
- `nowing_web/lib/playground/catalog.ts`, `platform-icons.tsx`
- `nowing_web/lib/connectors-marketing/index.ts`, `amazon.tsx`
- `nowing_web/content/docs/connectors/native/` (e.g. `amazon.mdx`, `index.mdx`, `meta.json`)
- `nowing_web/public/connectors/indeed.svg` (to be added)
