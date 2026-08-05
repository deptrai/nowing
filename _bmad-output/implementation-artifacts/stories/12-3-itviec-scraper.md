---
title: Story 12.3 — ITviec Scraper
epic: 12
story: 3
status: ready-for-dev
priority: P0
---

# Story 12.3 — ITviec Scraper

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** tech recruiter  
**I want:** to search ITviec job postings  
**So that:** I can monitor IT/AI hiring trends.

---

## Acceptance Criteria

1. **Given** a query, **When** `itviec.scrape` runs, **Then** it fetches `https://itviec.com/it-jobs/{query}` (server-rendered HTML, no CAPTCHA in spike).
2. **Given** the list page, **When** parsed, **Then** it extracts 20 job cards per page via selectors `job-card ipt-2`, `h3/a`, `employer-name`.
3. **Given** a detail page, **When** parsed, **Then** it extracts title, company, location, work mode, posted time, skills, job domain, JD.
4. **Given** salary is hidden, **When** displayed as `Sign in to view salary`, **Then** salary is parsed from title when possible or marked low-confidence.
5. **Given** the capability is built, **When** registered, **Then** it appears in billing (`BillingUnit.ITVIEC_JOB`), capability registry, MCP, and REST routes.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/capabilities/itviec/scrape/` and `app/proprietary/platforms/itviec/`.
- Replace stub with static HTML parser + rate-limit + user-agent rotation + circuit-breaker.
- ToS review (Story 12.0) is the hard gate.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
