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

1. **Given** a query and optional filters (`location`, `page`, `max_pages`, `max_items`), **When** `itviec.scrape` runs, **Then** it fetches `https://itviec.com/it-jobs/{query}` (server-rendered HTML, no CAPTCHA) and follows detail-page links from each job card.

2. **Given** the list page, **When** parsed, **Then** it extracts up to 20 job cards per page via selectors for `job-card ipt-2`, `h3/a`, and `employer-name`, and stops when fewer than 20 cards are returned or `max_pages`/`max_items` is reached.

3. **Given** a detail page, **When** parsed, **Then** it extracts `title`, `company`, `location`, `work_mode` (e.g. `At office`, `Remote`, `Hybrid`), `posted_time` (as ISO-8601 or relative text), `skills` (list), `job_domain`, and `job_description` from `//div[contains(@class,"jd-main")]`.

4. **Given** salary is hidden and displayed as `Sign in to view salary`, **When** the detail page is parsed, **Then** the scraper first attempts to parse a numeric salary range from the job title; if none is found, `salary` is `null`, `salary_hidden=true`, and `salary_confidence` is `low`.

5. **Given** the search query returns multiple pages, **When** `page` and `max_pages` are provided, **Then** the scraper iterates sequentially, respects a minimum 1s delay between pages, and stops at `max_pages`, `max_items`, or the last page.

6. **Given** ITviec returns `HTTP 429` or `HTTP 403`, **When** rate-limited or blocked, **Then** the scraper backs off exponentially (starting at 1s, max 20s), rotates `User-Agent`, and uses a circuit-breaker that trips after 3 consecutive failures and returns `degraded=true` with `degradation_reason` in `{RATE_LIMIT, ANTI_BOT}`.

7. **Given** PII such as Vietnamese phone numbers, email addresses, or person names appears in `job_description`, **When** the `JobItem` is produced, **Then** the shared PII pipeline (FR-47) masks or drops those fields, logs only counts, and the raw unredacted JD is not stored in `Memory` or returned in the payload.

8. **Given** the upstream site changes its HTML structure, **When** the selectors fail to match the golden fixtures, **Then** the regression test `test_itviec_golden_fixtures.py` fails before deployment.

9. **Given** a list of valid `JobItem[]` objects, **When** `to_chunks()` is called, **Then** each `JobItem` becomes a `Chunk` with `metadata.source: 'nowing_scraper'`, a stable `sourceId` (e.g. `sha256(title|company|location|post_date)`), `domain: 'itviec.com'`, `fetchedAt`, `contentType: 'job'`, and the redacted `content`; the chunk conforms to AD-34 and is ready for `NowingIngestService`.

10. **Given** the capability is built, **When** registered, **Then** it appears in `BillingUnit.ITVIEC_JOB`, the capability registry, MCP (`nowing_itviec_scrape`), and REST routes with typed request/response schemas.

11. **Given** Story 12.0 (ToS/Legal Review) returns a `disabled` or `blocked` decision for ITviec, **When** the capability is loaded, **Then** ITviec is excluded from the default source list and any call returns `degraded=true` with `degradation_reason: LEGAL_BLOCKED`.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/capabilities/itviec/scrape/` and `app/proprietary/platforms/itviec/`.
- Replace stub with static HTML parser; use `lxml` or `BeautifulSoup` with the selectors from the technical spike.
- Reuse rate-limit, user-agent rotation, circuit-breaker, and PII redaction helpers from `app/proprietary/platforms/`.
- ToS review (Story 12.0) is the hard gate.
- Reuse the `to_chunks()` helper from `app/services/scraper_chunks/` per Epic 20.1 / AD-34.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
