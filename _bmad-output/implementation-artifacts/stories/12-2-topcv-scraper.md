---
title: Story 12.2 — TopCV Scraper
epic: 12
story: 2
status: ready-for-dev
priority: P0
---

# Story 12.2 — TopCV Scraper

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** recruiter  
**I want:** to search TopCV job postings  
**So that:** I can access the largest local Vietnamese job board.

---

## Acceptance Criteria

1. **Given** a query + optional city filter, **When** `topcv.scrape` runs, **Then** it fetches TopCV search and detail pages.
2. **Given** a Cloudflare/anti-bot challenge, **When** encountered, **Then** the scraper uses warmed browser/headless/proxy and returns `degraded=true` with reason on block.
3. **Given** a successful fetch, **When** parsed, **Then** it returns typed `JobItem` with title, company, location, salary (if visible), JD, requirements, skills, post date.
4. **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.TOPCV_JOB`), capability registry, MCP, and REST routes.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/capabilities/topcv/scrape/` and `app/proprietary/platforms/topcv/`.
- Cost model: use `WEB_CRAWL` + `captcha` billing per AD-23; anti-bot POC is the hard gate.
- Do not merge before TopCV anti-bot POC passes or is explicitly disabled.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
