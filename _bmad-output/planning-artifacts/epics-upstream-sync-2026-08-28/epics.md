---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/specs/spec-upstream-sync-connectors-timeline/SPEC.md
  - _bmad-output/planning-artifacts/architecture/architecture-upstream-sync-2026-08-28/ARCHITECTURE-SPINE.md
---

# Nowing - Upstream Sync Connectors & Timeline - Epic Breakdown

## Overview

This document decomposes the upstream SurfSense sync work for Walmart, Indeed, Reddit scrapers and the Timeline/Thinking Steps UI into implementable epics and user stories.

## Requirements Inventory

### Functional Requirements

FR1: Users and AI agents can scrape Walmart product information and customer reviews via REST API.
FR2: Users and AI agents can scrape Walmart product information and customer reviews via chat subagent.
FR3: Users and AI agents can scrape Walmart product information and customer reviews via MCP tools.
FR4: Walmart scrape returns parsed product specs, prices, and reviews without errors on captcha/blocked pages.
FR5: Walmart scrape handles deeply nested breadcrumb structures correctly.
FR6: AI agents can retrieve Indeed job postings with robust pagination handling.
FR7: AI agents can retrieve Indeed job postings with anti-bot mitigation.
FR8: Indeed job queries preserve collected results on pagination challenge without timing out the orchestrator.
FR9: Users and AI agents can scrape recent and top posts from any Reddit subreddit without a search keyword.
FR10: Reddit scraper endpoint accepts `community` with empty `search_queries` and returns the latest subreddit feed.
FR11: Backend platform scrapers manage headless browser instances via a unified lifecycle pool.
FR12: Concurrent multi-platform scraping jobs recycle and terminate browser instances deterministically.
FR13: Chat interface renders an animated, pulse-based Activity Indicator during agent execution.
FR14: Chat interface displays canonical progress titles during agent execution.
FR15: Activity Indicator fully replaces the legacy pixel-grid loader in `nowing_web`.
FR16: Chat interface automatically scrolls streaming reasoning/thinking blocks.
FR17: Chat interface displays scroll indicators for collapsed reasoning episodes.

### Non-Functional Requirements

NFR1: All ported code must reside strictly within `nowing_*` packages and contain no `surfsense_*` references.
NFR2: All existing Vietnamese connectors (`batdongsan`, `topcv`, `itviec`, `cafef`, `vietstock`, `chotot`, `masothue`) must remain untouched and pass their unit tests.
NFR3: Existing Nowing database schema and authentication/credit-metering models must not be altered or regressed.
NFR4: UI strings must support Vietnamese localization while maintaining technical identifiers in English.
NFR5: Running concurrent multi-platform scraping jobs must produce zero zombie browser processes.
NFR6: Extended reasoning traces must auto-scroll to the current line during streaming without disrupting the overall chat viewport.
NFR7: New scraper test cases for Walmart, Indeed, and Reddit must pass in `pytest nowing_backend/tests`.
NFR8: `pnpm build` in `nowing_web` must build cleanly after the new `TimelineActivityIndicator` is integrated.

### Additional Requirements

- Port file-by-file from upstream PRs #1614 (Walmart), #1605 (Indeed), #1692 (Timeline), and #1686 (Thinking Steps). Do not merge `upstream/main`.
- Do not port OpenTelemetry / Grafana LGTM Docker container stack.
- Do not port upstream signup credit claims migration or credit accounting changes.
- Do not deploy Daytona code interpreter sandbox in this phase.
- Apply namespace transform `surfsense_*` → `nowing_*` for package paths, class names, loggers, environment variables, and URL prefixes.
- Browser lifecycle manager in `nowing_backend/app/proprietary/platforms/crawler/` is the single owner of Playwright browser instances.
- Capability executors are thin adapters that validate request, map schema, call the platform, map response, and record credit.
- MCP tool input/output Pydantic schemas must mirror the corresponding backend capability schemas.
- Platform packages must expose `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, and `url_resolver.py` where applicable.

### UX Design Requirements

UX-DR1: Define canonical progress titles for agent execution steps.
UX-DR2: Implement pulse-based animated `TimelineActivityIndicator` component.
UX-DR3: Remove or replace legacy pixel-grid loader across chat sessions.
UX-DR4: Implement auto-scroll behavior for streaming reasoning/thinking blocks.
UX-DR5: Add scroll indicators for collapsed reasoning episodes.

### FR Coverage Map

FR1: Epic 1 — Walmart Scraper & Reviews (REST)
FR2: Epic 1 — Walmart Scraper & Reviews (chat subagent)
FR3: Epic 1 — Walmart Scraper & Reviews (MCP)
FR4: Epic 1 — Walmart Scraper & Reviews (resilience)
FR5: Epic 1 — Walmart Scraper & Reviews (breadcrumb)
FR6: Epic 2 — Indeed Jobs (pagination)
FR7: Epic 2 — Indeed Jobs (anti-bot)
FR8: Epic 2 — Indeed Jobs (graceful degradation)
FR9: Epic 3 — Reddit Community Scrape
FR10: Epic 3 — Reddit Community Scrape (empty search_queries)
FR11: Epic 4 — Browser Lifecycle Pool
FR12: Epic 4 — Browser Lifecycle Pool (zero zombies)
FR13: Epic 5 — Timeline Activity Indicator UI
FR14: Epic 5 — Timeline Activity Indicator (progress titles)
FR15: Epic 5 — Timeline Activity Indicator (replace loader)
FR16: Epic 6 — Reasoning Auto-scroll
FR17: Epic 6 — Reasoning Auto-scroll (indicators)

## Epic List

### Epic 1: Walmart Scraper & Reviews
Users and AI agents can scrape Walmart product information and customer reviews via REST, chat, and MCP with structured output.
**FRs covered:** FR1, FR2, FR3, FR4, FR5

### Epic 2: Indeed Jobs Scraper Resilience
AI agents can retrieve Indeed job postings with robust pagination, anti-bot mitigation, and graceful degradation on challenge pages.
**FRs covered:** FR6, FR7, FR8

### Epic 3: Reddit Community-Only Scrape
Users and AI agents can scrape recent and top posts from any Reddit subreddit without providing a search keyword.
**FRs covered:** FR9, FR10

### Epic 4: Unified Browser Lifecycle Pool
Backend platform scrapers manage headless browser instances through a shared lifecycle pool to prevent orphaned processes.
**FRs covered:** FR11, FR12

### Epic 5: Timeline Activity Indicator UI
Chat interface renders an animated, pulse-based Activity Indicator with canonical progress titles, fully replacing the legacy pixel-grid loader.
**FRs covered:** FR13, FR14, FR15

### Epic 6: Reasoning Episode Auto-scroll
Chat interface automatically scrolls streaming reasoning/thinking blocks and displays scroll indicators for collapsed episodes.
**FRs covered:** FR16, FR17

## Epic 1: Walmart Scraper & Reviews

Users and AI agents can scrape Walmart product information and customer reviews via REST, chat, and MCP with structured output.

### Story 1.1: Port Walmart platform scraper files

As a backend engineer,
I want to port the upstream Walmart proprietary platform files into `nowing_backend/app/proprietary/platforms/walmart/`,
So that Walmart scraping logic is available under the Nowing namespace.

**Acceptance Criteria:**

**Given** the upstream delta from PR #1614,
**When** the files are copied to `nowing_backend/app/proprietary/platforms/walmart/`,
**Then** the package contains `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, `url_resolver.py`, and `next_data.py` aligned with upstream.
**And** no `surfsense_*` strings remain in any ported file.
**And** `pytest nowing_backend/tests` for Walmart passes.

### Story 1.2: Create Walmart scrape capability

As a backend engineer,
I want a thin `scrape` capability adapter for Walmart under `nowing_backend/app/capabilities/walmart/scrape/`,
So that REST and chat subagents can call the Walmart platform uniformly.

**Acceptance Criteria:**

**Given** a valid Walmart product URL or search request,
**When** the capability executor receives the request,
**Then** it validates the schema, calls the platform scraper, maps the response, and records credit.
**And** the response envelope matches Nowing's standard `{items, total, has_more}` format.

### Story 1.3: Create Walmart reviews capability

As a backend engineer,
I want a new `reviews` capability under `nowing_backend/app/capabilities/walmart/reviews/`,
So that AI agents can fetch customer reviews for a Walmart product.

**Acceptance Criteria:**

**Given** a valid Walmart product identifier or URL,
**When** the reviews capability is invoked,
**Then** it returns structured review data (rating, text, author, date) without duplicating scraping logic.
**And** the capability uses the same platform scraper as the scrape capability.

### Story 1.4: Update Walmart MCP tool definition

As an MCP server maintainer,
I want `nowing_mcp/mcp_server/features/scrapers/platforms/walmart.py` to expose scrape and reviews tools,
So that external agents can invoke Walmart actions over MCP.

**Acceptance Criteria:**

**Given** the MCP tool is registered,
**When** an agent calls `nowing_walmart_scrape` or `nowing_walmart_reviews`,
**Then** the tool uses the same Pydantic request/response models as the backend capabilities.
**And** tool descriptions and parameter names are in English with clear Vietnamese labels where user-facing.

## Epic 2: Indeed Jobs Scraper Resilience

AI agents can retrieve Indeed job postings with robust pagination, anti-bot mitigation, and graceful degradation on challenge pages.

### Story 2.1: Port Indeed platform scraper files

As a backend engineer,
I want to port the upstream `indeed_jobs` platform into `nowing_backend/app/proprietary/platforms/indeed/`,
So that the scraper can resolve URLs, fetch pages, parse listings, and handle pagination.

**Acceptance Criteria:**

**Given** the upstream delta from PR #1605,
**When** the files are placed under `nowing_backend/app/proprietary/platforms/indeed/`,
**Then** the package contains `fetch.py`, `parsers.py`, `schemas.py`, `scraper.py`, and `url_resolver.py`.
**And** the existing `scraper.py` in `nowing_backend/app/proprietary/platforms/indeed/` is either replaced or refactored to use the new modular files.
**And** no `surfsense_*` references remain.

### Story 2.2: Update Indeed scrape capability

As a backend engineer,
I want to update the existing `indeed/scrape` capability to use the new platform modules,
So that REST and chat calls get consistent, structured job listings.

**Acceptance Criteria:**

**Given** a job query with keywords, location, and pagination,
**When** the capability is invoked,
**Then** it delegates to the platform scraper and returns a paged list of job postings.
**And** the executor remains a thin adapter without scraping logic.

### Story 2.3: Implement anti-bot mitigation and graceful degradation

As a backend engineer,
I want the Indeed scraper to detect pagination challenges and preserve already-collected results,
So that the orchestrator does not time out and partial data is not lost.

**Acceptance Criteria:**

**Given** a multi-page Indeed query that hits a challenge or block page,
**When** the scraper encounters the challenge,
**Then** it records the collected pages as a partial result and returns them with a `has_more=false` or `interrupted` flag.
**And** the orchestrator receives the partial result without raising a timeout.

### Story 2.4: Update Indeed MCP tool

As an MCP server maintainer,
I want `nowing_mcp/mcp_server/features/scrapers/platforms/indeed.py` to reflect the new request/response schema,
So that MCP clients query Indeed jobs correctly.

**Acceptance Criteria:**

**Given** the MCP tool definition,
**When** it is registered and invoked,
**Then** request parameters match `nowing_backend/app/capabilities/indeed/scrape/schemas.py` exactly.
**And** no `surfsense_*` strings remain in the tool file.

## Epic 3: Reddit Community-Only Scrape

Users and AI agents can scrape recent and top posts from any Reddit subreddit without providing a search keyword.

### Story 3.1: Port Reddit platform community-only support

As a backend engineer,
I want to port the upstream Reddit delta so the platform supports `community` with empty `search_queries`,
So that subreddit feeds can be fetched without a keyword.

**Acceptance Criteria:**

**Given** the upstream delta from PR #1605/related Reddit commits,
**When** the `reddit` platform files are updated in `nowing_backend/app/proprietary/platforms/reddit/`,
**Then** `url_resolver.py` and `scraper.py` accept `community` and optional `search_queries`.
**And** `parsers.py` returns the latest subreddit feed when `search_queries` is empty.
**And** no `surfsense_*` references remain.

### Story 3.2: Update Reddit scrape capability

As a backend engineer,
I want to update `nowing_backend/app/capabilities/reddit/scrape/` to accept community-only requests,
So that the REST endpoint and chat subagent can call the new flow.

**Acceptance Criteria:**

**Given** a request with `community="SaaS"` and `search_queries=[]`,
**When** the capability is invoked,
**Then** it delegates to the platform scraper and returns recent/top posts for that subreddit.
**And** the schema still accepts requests with non-empty `search_queries` for backward compatibility.

### Story 3.3: Update Reddit MCP tool

As an MCP server maintainer,
I want `nowing_mcp/mcp_server/features/scrapers/platforms/reddit.py` to allow optional `search_queries` when `community` is provided,
So that agents can stream subreddit feeds without inventing a keyword.

**Acceptance Criteria:**

**Given** the MCP tool definition,
**When** an agent calls `nowing_reddit_scrape` with `community` and no `search_queries`,
**Then** the call is accepted and delegated to the backend capability.
**And** the tool input schema mirrors the updated backend capability schema.

## Epic 4: Unified Browser Lifecycle Pool

Backend platform scrapers manage headless browser instances through a shared lifecycle pool to prevent orphaned processes.

### Story 4.1: Port or align crawler lifecycle manager

As a backend engineer,
I want the shared browser lifecycle manager in `nowing_backend/app/proprietary/platforms/crawler/` to support the new Walmart/Indeed/Reddit loops,
So that all scrapers acquire and release browsers through one pool.

**Acceptance Criteria:**

**Given** the upstream refactor consolidating browser loop management,
**When** the crawler module is aligned with Nowing,
**Then** Walmart, Indeed, and Reddit scrapers call the lifecycle manager to get/return browser contexts.
**And** existing Vietnamese scrapers continue to work without modification.

### Story 4.2: Verify zero zombie browser processes

As a backend engineer,
I want concurrent multi-platform scraping to terminate all browser instances deterministically,
So that no orphaned chromium processes remain after jobs complete or fail.

**Acceptance Criteria:**

**Given** a test running Walmart, Indeed, and Reddit scrapers concurrently,
**When** all jobs finish or time out,
**Then** no residual `chrome` or `chromium` processes from the test remain.
**And** the test is added to `nowing_backend/tests` and passes.

## Epic 5: Timeline Activity Indicator UI

Chat interface renders an animated, pulse-based Activity Indicator with canonical progress titles, fully replacing the legacy pixel-grid loader.

### Story 5.1: Create `TimelineActivityIndicator` component

As a frontend engineer,
I want a new `nowing_web/components/ui/timeline-activity-indicator.tsx` component,
So that chat sessions can display an animated pulse-based activity indicator.

**Acceptance Criteria:**

**Given** the upstream `timeline-activity-indicator.tsx` as reference,
**When** the component is created in Nowing,
**Then** it renders animated step status, canonical progress titles, and a pulse indicator.
**And** it uses Tailwind classes and keyframes from `nowing_web/app/globals.css`.
**And** technical identifiers remain in English while user-facing labels are Vietnamese-ready.

### Story 5.2: Update chat streaming to use activity journal

As a frontend engineer,
I want `nowing_web/lib/chat/activity-journal.ts` to manage client-side activity state smoothly,
So that the Timeline component renders from streaming journal entries.

**Acceptance Criteria:**

**Given** a chat stream producing activity journal events,
**When** the journal is consumed,
**Then** `activity-journal.ts` normalizes entries, tracks step status, and exposes a stable state for the UI.
**And** the legacy pixel-grid loader is no longer used for activity indication.

### Story 5.3: Replace pixel-grid loader in chat

As a frontend engineer,
I want to remove or replace the legacy pixel-grid loader across the chat UI,
So that the new Timeline Activity Indicator is the single loading/activity visual.

**Acceptance Criteria:**

**Given** all references to the pixel-grid loader,
**When** they are replaced or removed,
**Then** the chat renders `TimelineActivityIndicator` during agent execution.
**And** `pnpm build` in `nowing_web` completes without errors.

## Epic 6: Reasoning Episode Auto-scroll

Chat interface automatically scrolls streaming reasoning/thinking blocks and displays scroll indicators for collapsed episodes.

### Story 6.1: Implement reasoning item auto-scroll

As a frontend engineer,
I want `nowing_web/features/chat-messages/timeline/items/reasoning-item.tsx` to auto-scroll to the current reasoning line during streaming,
So that users can follow long thinking traces without losing the overall chat context.

**Acceptance Criteria:**

**Given** a reasoning block that streams many lines,
**When** a new line is appended,
**Then** the reasoning container scrolls to the current line using `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` or `IntersectionObserver`.
**And** the overall chat viewport does not scroll unexpectedly.

### Story 6.2: Add scroll indicator for collapsed reasoning episodes

As a frontend engineer,
I want collapsed reasoning episodes to show a scroll indicator,
So that users know more content is available and can expand to view it.

**Acceptance Criteria:**

**Given** a reasoning episode longer than the collapsed height,
**When** it is in the collapsed state,
**Then** a visual scroll/fade indicator appears at the bottom of the episode.
**And** clicking the indicator or the episode expands it to full height.
