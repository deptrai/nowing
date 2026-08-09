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

1. **Given** a query and optional city filter (`location`) plus pagination params (`page`, `max_pages`, `max_items`), **When** `topcv.scrape` runs, **Then** it fetches the TopCV search results page and follows detail-page links for each job card.

2. **Given** a Cloudflare/anti-bot challenge (`HTTP 403` or page title contains `Just a moment...`), **When** encountered, **Then** the scraper attempts a warmed headless browser/proxy rotation (Playwright/Puppeteer with stealth or a residential proxy), returns `degraded=true` with `degradation_reason: ANTI_BOT` if bypass fails, and does not crash.

3. **Given** a successful fetch of a detail page, **When** parsed, **Then** it returns a typed `JobItem` with: `title`, `company`, `location`, `salary` (empty/null if hidden), `job_description`, `job_requirement`, `skills` (list), `employment_type`, `experience_years`, `post_date`, and `source_url`.

4. **Given** salary is not visible or is marked `Thương lượng`, **When** parsed, **Then** `salary` is `null`, `salary_hidden=true`, and `salary_confidence` is `low`; if a numeric range can be inferred from the title, it is placed in `salary` with `salary_confidence: medium`.

5. **Given** the search results page has pagination, **When** `page` and `max_pages` are provided, **Then** the scraper iterates until `max_pages` is reached, no more results are found, or `max_items` total listings are collected.

6. **Given** TopCV returns `HTTP 429`, **When** rate-limited, **Then** the scraper backs off exponentially (starting at 2s, max 30s), rotates `User-Agent`, and uses a circuit-breaker that trips after 3 consecutive failures and returns `degraded=true` with `degradation_reason: RATE_LIMIT`.

7. **Given** PII such as Vietnamese phone numbers, email addresses, or person names appears in `job_description` or `job_requirement`, **When** the `JobItem` is produced, **Then** the PII pipeline masks or drops those fields, logs only counts (no values), and the raw unredacted JD is not stored in `Memory` or returned in the payload.

8. **Given** a list of valid `JobItem[]` objects, **When** `to_chunks()` is called, **Then** each `JobItem` becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, a stable `sourceId` (e.g. `sha256(title|company|location|post_date)`), `domain: 'topcv.vn'`, `fetchedAt`, `contentType: 'job'`, and the redacted `content`; the chunk conforms to AD-34 and is ready for `NowingIngestService`.

9. **Given** the capability is built, **When** registered, **Then** it appears in `BillingUnit.TOPCV_JOB`, the capability registry, MCP (`nowing_topcv_scrape`), and REST routes with typed request/response schemas.

10. **Given** the upstream site changes its HTML structure, **When** the selectors fail to match the golden fixtures, **Then** the regression test `test_topcv_golden_fixtures.py` fails before deployment.

11. **Given** Story 12.0 (ToS/Legal Review) returns a `disabled` or `blocked` decision for TopCV, **When** the capability is loaded, **Then** TopCV is excluded from the default source list and any call returns `degraded=true` with `degradation_reason: LEGAL_BLOCKED`.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/capabilities/topcv/scrape/` and `app/proprietary/platforms/topcv/`.
- Cost model: use `WEB_CRAWL` + `captcha` billing per AD-23; anti-bot POC is the hard gate.
- Do not merge before TopCV anti-bot POC passes or the source is explicitly disabled in config.
- Reuse the `to_chunks()` helper from `app/services/scraper_chunks/` per Epic 20.1 / AD-34.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
