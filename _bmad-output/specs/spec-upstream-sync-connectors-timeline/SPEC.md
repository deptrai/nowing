---
id: SPEC-upstream-sync-connectors-timeline
companions:
  - architecture-changes.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Upstream Feature Sync: Connectors & Timeline UI

## Why

Upstream repository (`SurfSense`) has introduced major resilience and feature improvements in live data scraping (Walmart product & review parsers, Indeed anti-bot mitigation, Reddit community streaming) and modernized the agent execution visual feedback (canonical progress titles, activity indicator replacing pixel grid loader, auto-scrolling reasoning episodes). Nowing needs to integrate these battle-tested upgrades to enhance research agent reliability and user experience while preserving Nowing-specific architecture and Vietnamese connectors.

## Capabilities

- **CAP-1**
  - **intent:** Users and AI agents can scrape Walmart product information and customer reviews via REST API, chat subagent, and MCP tools with structured output.
  - **success:** Executing Walmart scrape and review requests returns parsed product specs, prices, and reviews without errors when encountering captcha/blocked pages or deeply nested breadcrumb structures.

- **CAP-2**
  - **intent:** AI agents can retrieve job postings from Indeed with robust pagination handling and anti-bot mitigation.
  - **success:** Indeed job queries return structured listings and gracefully preserve collected results on pagination challenge without timing out the orchestrator.

- **CAP-3**
  - **intent:** Users and AI agents can scrape recent and top posts directly from any Reddit subreddit without specifying a search keyword.
  - **success:** Calling Reddit scraper endpoint with `community` provided and empty `search_queries` returns the latest subreddit feed.

- **CAP-4**
  - **intent:** Backend platform scrapers manage headless browser instances via a unified lifecycle pool to prevent orphaned processes.
  - **success:** Running concurrent multi-platform scraping jobs recycles and terminates browser instances deterministically with zero zombie browser processes.

- **CAP-5**
  - **intent:** Chat interface renders an animated, pulse-based Activity Indicator displaying canonical progress titles during agent execution.
  - **success:** In `nowing_web`, real-time streaming displays `TimelineActivityIndicator` with animated step status and clear activity labels, fully replacing the legacy pixel-grid loader.

- **CAP-6**
  - **intent:** Chat interface automatically scrolls streaming reasoning/thinking blocks and displays scroll indicators for collapsed episodes.
  - **success:** Extended reasoning traces auto-scroll to the current line during streaming without disrupting the overall chat viewport.

## Constraints

- All ported code must reside strictly within `nowing_*` packages (`nowing_backend`, `nowing_web`, `nowing_mcp`) and eliminate any `surfsense_*` references.
- All existing custom Vietnamese connectors (`batdongsan`, `topcv`, `itviec`, `cafef`, `vietstock`, `chotot`, `masothue`) must remain untouched and pass their unit tests.
- Existing Nowing database schema and authentication/credit-metering models must not be altered or regressed.
- UI strings must support Vietnamese localization while maintaining technical identifiers in English.

## Non-goals

- Porting the OpenTelemetry / Grafana LGTM Docker container stack from upstream (Nowing continues using its current Dokploy deployment).
- Upstream signup credit claims migration and credit accounting changes.
- Direct git merge of `upstream/main` to avoid namespace collisions.
- Daytona code interpreter sandbox deployment (scheduled for Phase 2).

## Success signal

- Automated test suites for scrapers (`pytest nowing_backend/tests`) pass with new Walmart, Indeed, and Reddit test cases.
- Next.js web application (`pnpm build` in `nowing_web`) builds cleanly and displays the new `TimelineActivityIndicator` in interactive chat sessions.

## Assumptions

- Headless browser drivers (Playwright / Chromium) available in the backend environment support the updated scraper loops.
- Existing frontend Tailwind / CSS configurations accommodate the new keyframes defined in `timeline-activity-indicator`.
