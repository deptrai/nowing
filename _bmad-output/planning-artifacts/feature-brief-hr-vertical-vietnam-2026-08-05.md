---
title: Feature Brief — HR/Recruitment Vertical for Vietnam
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
status: proposal
---

# Feature Brief: HR/Recruitment Vertical (Vietnam)

## 1. Executive Summary

**Proposal:** Run an **8-week pilot** to test whether a **Vietnam Job Market Research** capability fits Nowing. The pilot delivers **three scrapers** (VietnamWorks, TopCV, ITviec) and a `vn_jobs.aggregate` capability that normalizes, dedupes, and scores job postings across all three sources, storing results as research memories with citations. Multi-source coverage is critical to validate cross-platform data quality and the core value proposition (citations, conflict detection, salary consistency).

**Why this is a pilot, not a vertical launch:**
- Market demand for cross-platform job research is **unvalidated**.
- ToS of VietnamWorks, TopCV, and ITviec are **unreviewed**.
- Vietnamese employment law classification is **unconfirmed**.
- Anti-bot capabilities for TopCV/ITviec are **unproven**.
- BĐS aggregator pattern is **unproven in production** for cross-vertical reuse.

**What we will learn in 8 weeks:**
- Do HR managers/recruiters actually use and return to the tool?
- Are they willing to pay $0.03–$0.08/query?
- Do VietnamWorks, TopCV, and ITviec allow stable automated access?
- Does `vn_jobs.aggregate` produce meaningful cross-source salary/location/skill intelligence?
- Does Nowing risk being classified as an employment service provider?

**Strategic non-goal:** This is **not** an ATS. Nowing will not process applications, schedule interviews, or manage candidate pipelines in MVP.

---

## 2. Problem Statement

Vietnamese employers and recruiters face a structural hiring gap:

- **69%** of employers plan to increase hiring in 2026, but **80%** struggle to find suitable candidates.
- **86%** of employers cite rising salary expectations as the #1 hiring challenge.
- Hiring demand is strongest in **Sales, Accounting/Auditing, Architecture/Construction, HR, Banking, Legal, IT/AI, Manufacturing, and Supply Chain**.
- Data is fragmented across **VietnamWorks, TopCV, ITviec, CareerLink, Glints, JobHopin, LinkedIn, and Facebook/Zalo groups**.
- Existing job boards and AI matching tools are **proprietary silos** with no cross-platform market intelligence, no long-term research memory, and no citations.

For Nowing, this is the same pattern already observed in real estate: multiple listing platforms, no aggregation, low trust, and a clear opportunity for an open-source, citation-first research layer.

**However, the problem statement above is based on secondary research, not validated customer interviews.** The pilot must answer: *do HR managers and recruiters actually need cross-platform research, and will they pay for it?*

---

## 3. Strategic Fit with Nowing

| Nowing Strength | How HR Pilot Uses It |
|---|---|
| **Multi-source connectors** | VietnamWorks, TopCV, ITviec scrapers (P0) |
| **Aggregator pattern (`vn_bds.aggregate`)** | `vn_jobs.aggregate` — normalize/dedupe/score job postings from 3 sources |
| **Long-term research memory** | Track hiring trends, salary pressure, skill demand over time (if pilot passes) |
| **Citations / provenance** | Every data point links back to the original job board URL and timestamp |
| **Self-host / open-source** | Recruiters and SMBs can run on their own infra, keeping proprietary searches private |
| **MCP / agent integration** | Agents can ask "có bao nhiêu việc Data Engineer ở Hà Nội lương trên 30 triệu? So sánh VietnamWorks, TopCV, ITviec." and get structured, cited results |
| **Automations / playbooks** | Schedule weekly market briefs on a skill, company, or location (P1) |

This is a **pilot use case for the same product**, not a new product line or pivot. It tests whether the agent-builder / research-team beachhead can expand into HR domain.

> **Boundary (2026-08-10):** HR pilot data is research/job-market data with PII redaction per FR-47/AD-25. It is **not** a source for Epic 21 lead-enrichment contact data. Lead gen uses separate sources and a separate PII/consent policy (SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`).

---

## 4. Proposed Solution

### 4.1 Capabilities to Build

| Capability | Source | P0/P1/P2 | Notes |
|---|---|---|---|
| `vietnamworks.scrape` | VietnamWorks public API | **P0** | No-auth POST API; requires ToS review |
| `topcv.scrape` | TopCV website | **P0** pending anti-bot POC | Anti-bot, HTML/JSON parsing; POC plan and pass/fail criteria in `technical-spike-topcv-itviec-2026-08-05.md` §2.3; if fail, drop from P0 |
| `itviec.scrape` | ITviec website | **P0** | HTML, no challenge observed; salary hidden for non-logged-in users — mark low-confidence and fallback to VietnamWorks/TopCV for salary |
| `vn_jobs.aggregate` | All 3 job scrapers | **P0** | Reuse `vn_bds.aggregate` pattern: normalize, dedupe, confidence, conflict |
| `pii_detection.redact` | Job description text | **P0** | Regex + NER for phone, email, names; drop or mask PII before memory |
| `vn_jobs.market_brief` | Derived from aggregate | **P1** | Research deliverable: skill-demand, salary trend, competitor hiring |

### 4.2 Aggregator Schema (proposed)

**`VnJobAggregateInput`**:
- `query` (str): job title, skill, or keyword
- `location` (str): city or region (Hà Nội, TP.HCM, Đà Nẵng, etc.)
- `sources` (list): `vietnamworks`, `topcv`, `itviec`
- `min_salary`, `max_salary` (optional)
- `employment_type` (optional): full-time, part-time, contract
- `experience_years` (optional)
- `max_items_per_source` (int, default 50)
- `min_confidence` (float, default 0.5)

**`VnJobAggregateOutput`**:
- `items: List[VnJobAggregatedListing]`
- `degraded: bool`
- `degradation_reasons: List[str]`
- `source_breakdown: Dict[str, int]`
- `cost_micros: int`

**`VnJobAggregatedListing`**:
- `title: str`
- `company: str`
- `location: Optional[str]`
- `salary_min: Optional[int]` (VND, normalized)
- `salary_max: Optional[int]` (VND, normalized)
- `salary_period: Optional[str]` (month/year)
- `employment_type: Optional[str]`
- `experience_years: Optional[str]`
- `skills: List[str]`
- `posted_at: Optional[datetime]`
- `job_url: str`
- `source_urls: List[str]`
- `confidence_score: float`
- `provenance: VnJobProvenance`

### 4.3 Confidence Scoring

Reuse the BDS scoring model, adjusted for jobs:

- `source_trust`: static by source (`vietnamworks=0.45`, `topcv=0.35`, `itviec=0.35`)
- `overlap_score`: `source_count / 3`
- `freshness_score`: 1.0 if ≤7 days, 0.0 if ≥90 days
- `salary_consistency_score`: `1 - (std / mean)` across `source_salaries`, clamped
- `confidence_score = 0.25*source_trust + 0.35*overlap + 0.15*freshness + 0.25*salary_consistency`

### 4.4 Normalization Rules

- **Salary normalization**: parse "triệu", "tỷ", "USD", "thỏa thuận"; convert to VND monthly where possible.
- **Location normalization**: alias map `Hà Nội/Hanoi/HN`, `TP.HCM/Hồ Chí Minh/SG/HCM`, `Đà Nẵng/DN`.
- **Employment type**: map ids to `FULL_TIME`, `PART_TIME`, `CONTRACT`, `INTERN`.
- **Experience**: map "0-1 năm", "1-3 năm", etc.
- **Dedupe key**: `company + title + location + posted_at`.
- **PII redaction**: before storing into memory, run regex for Vietnamese phone, email, and NER for person names found in `job_description` / `job_requirement`. If PII is detected, mask or drop the field. **Do not use phone/email as dedupe key** (risk of storing PII).

### 4.5 MCP / Agent Exposure

- `nowing_vietnamworks_scrape` — search VietnamWorks.
- `nowing_vn_jobs_aggregate` — cross-source job search (P0: VietnamWorks + TopCV + ITviec).
- Agent can answer (P0): "Có bao nhiêu việc Data Engineer ở Hà Nội đang tuyển? So sánh lương giữa VietnamWorks, TopCV, ITviec."

---

## 5. Proposed Epic & Stories

### Epic 11: Vietnam Recruitment Research Pilot (NEW)

**Goal:** Run an 8-week pilot with VietnamWorks, TopCV, and ITviec scrapers plus a `vn_jobs.aggregate` capability to validate demand, ToS compliance, cross-source data quality, anti-bot feasibility, cost, and technical fit before committing to a full vertical.

**Pilot requirements:** FR-6 (scrapers), FR-32 (memory), FR-39 (provenance), AD-3 (self-registering capability), AD-11.1 (provenance recipe), AD-16 (license boundary), AD-19 (degrade under pressure), plus new PII-redaction and anti-bot requirements.

**Gating conditions:** Pilot starts only after (a) ToS review passes for VietnamWorks, TopCV, and ITviec, (b) technical spike/anti-bot POC passes for TopCV and ITviec, (c) legal counsel confirms no employment-service-provider classification, (d) SCP resolves NG-1 ambiguity.

### Story 11.1: VietnamWorks Scraper

**As a** recruiter or market researcher,
**I want** to search VietnamWorks job postings via a no-auth public API,
**So that** I can source live job data into my Nowing workspace.

**Acceptance Criteria:**
1. `vietnamworks.scrape` capability exists with `VietnamWorksScrapeInput` (query, location, page, max_items, scrape_details).
2. Calls `POST https://ms.vietnamworks.com/job-search/v1.0/search` and parses response into typed `JobItem`.
3. Maps fields: `jobId`, `jobTitle`, `companyName`, `workingLocations`, `salaryMin/Max`, `salaryCurrency`, `salaryPeriodId`, `jobDescription`, `jobRequirement`, `jobFunction`, `yearsOfExperience`, `createdOn`, `approvedOn`, `typeWorkingId`, `expiredOn`, `isActive`.
4. Handles pagination (`hitsPerPage` max 100) and rate-limit (429) with backoff and circuit-breaker.
5. Registered in billing (`BillingUnit.VIETNAMWORKS_JOB`), capability registry, MCP, and routes.
6. Logs API contract changes via golden fixture regression tests.
7. Unit + integration tests pass; no PII logging.

### Story 11.2: TopCV Scraper

**As a** recruiter,
**I want** to search TopCV job postings,
**So that** I can access the largest local Vietnamese job board.

**Acceptance Criteria:**
1. `topcv.scrape` capability fetches TopCV search results (search page + detail page if needed).
2. Anti-bot POC passes (warmed browser/headless fallback) before this story is merged.
3. Parses job cards and detail pages for title, company, location, salary, JD, requirements, skills, post date.
4. Handles anti-bot, rate-limit, and graceful degradation.
5. Registered in billing (`BillingUnit.TOPCV_JOB`), capability registry, MCP, and routes.
6. Unit + integration tests pass.

### Story 11.3: ITviec Scraper

**As a** tech recruiter,
**I want** to search ITviec job postings,
**So that** I can monitor IT/AI hiring trends.

**Acceptance Criteria:**
1. `itviec.scrape` capability fetches ITviec search results.
2. Anti-bot POC passes before this story is merged.
3. Parses tech-focused fields: level, skills, salary, company, location, tags, post date.
4. Handles anti-bot, rate-limit, and graceful degradation.
5. Registered in billing (`BillingUnit.ITVIEC_JOB`), capability registry, MCP, and routes.
6. Unit + integration tests pass.

### Story 11.4: PII Detection & Redaction for Job Data

**As a** workspace owner,
**I want** job postings to be scanned for personal information before storage,
**So that** Nowing does not accidentally retain candidate PII.

**Acceptance Criteria:**
1. Regex detects Vietnamese phone numbers and email addresses in `job_description` and `job_requirement` from all three sources.
2. NER (or heuristic) flags person names in JD text.
3. Detected PII is masked or the field is dropped; the full raw JD is not stored in memory.
4. PII detection stats are logged (counts only, no values).
5. Unit tests for representative JD samples from VietnamWorks, TopCV, and ITviec.

### Story 11.5: Vietnam Job Aggregator

**As a** research analyst,
**I want** to query multiple Vietnamese job sources in one call,
**So that** I get a normalized, deduped, confidence-scored view of the job market.

**Acceptance Criteria:**
1. `vn_jobs.aggregate` capability accepts `query`, `location`, `sources` (default `['vietnamworks','topcv','itviec']`), salary filters, `max_items_per_source`, `min_confidence`.
2. Fan-out to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape`.
3. Normalizes `JobItem` into `VnJobAggregatedListing` with salary/location/employment-type/experience.
4. Runs PII redaction on `job_description` / `job_requirement` before storing.
5. Deduplicates by company+title+location+posted_at (cross-source).
6. Computes `confidence_score` and `salary_consistency_score`; flags conflicts.
7. Returns `degraded=true` with `degradation_reasons` if a child source fails.
8. Exposed via REST, MCP, and chat agent.
9. Unit + integration tests for normalize, dedupe, scoring, PII redaction, orchestrator.

### Story 11.6: Job Market Research Playbook (P1 — gated)

**As a** workspace user,
**I want** a pre-built automation/playbook for job market research,
**So that** I can schedule weekly briefs on skills, companies, or locations.

**Acceptance Criteria:**
1. Playbook template accepts `query`, `location`, `frequency`, `output_format`.
2. Runs `vn_jobs.aggregate` on schedule.
3. Generates a deliverable (report) with charts/tables and citations.
4. Stores key findings as memories.

---

## 6. Implementation Notes

### 6.1 Reuse from Existing Codebase

- **BSL fetcher pattern**: reuse `app/proprietary/platforms/batdongsan/` structure for `vietnamworks/` (P0). `topcv/` and `itviec/` deferred until pilot go/no-go.
- **Aggregator pattern**: copy-modify `app/services/bds_aggregator/` → `app/services/jobs_aggregator/`. Do not generalize to `vertical_aggregator` until 2–3 verticals are stable.
- **PII redaction**: reuse existing regex/NER utilities if available; otherwise build a small `jobs_pii` module in `app/services/jobs_aggregator/pii.py`.
- **Capability registration**: reuse `app/capabilities/vn_bds/aggregate/` pattern.
- **MCP wiring**: reuse `nowing_mcp/mcp_server/features/scrapers/platforms/vn_bds.py`.
- **Billing**: reuse `BillingUnit` + `app/capabilities/core/billing.py` pattern. Pilot uses free/discounted credits.

### 6.2 Licensing

- Fetchers live in `app/proprietary/platforms/` (BSL 1.1).
- Aggregator service and capability contract live in Apache-2.0 core, consistent with `AD-16`.
- Cloud offering must not sell BSL fetchers as a standalone hosted service; value must come from the aggregator + memory + citations layer. Raise SCP if ambiguous.

### 6.3 Data Freshness & Retention

- Default cache TTL: 1 hour for live search; 7 days for aggregated market-brief data.
- `Memory` retention: align with `AR-4` / `OQ-3` review for scraped job data.
- PII redaction runs before storage.

### 6.4 Anti-bot & Resilience

- VietnamWorks public API risk is **low-to-medium**: spike shows 200 OK, no CAPTCHA, 30 concurrent requests succeed.
- Implement circuit-breaker and golden fixture regression tests for VietnamWorks API contract.
- TopCV/ITviec require warmed browser/headless fallback (reuse AD-19 taxonomy); deferred to P1.
- Degrade gracefully: VietnamWorks failing returns `degraded=true` with reason.

### 6.5 Spike Findings (2026-08-05)

**VietnamWorks:**
- `POST https://ms.vietnamworks.com/job-search/v1.0/search` trả 200 no-auth.
- Pagination: sử dụng `hitsPerPage` (max 100), không phải `pageSize`.
- Response time: ~1.85s/request; 30 concurrent requests hoàn thành trong 3.15s.
- Rate limit: chưa gặp 429 trong short burst/sequential tests; cần re-test từ production network.
- Salary: 69% "Thương lượng", 22% range, 9% "Từ X"; `salaryCurrency` USD 66% / VND 34% (sample "Data Engineer").
- Location filter: `locationId`/`cityId` trong request không filter ở server; filter ở aggregator.
- PII: 0 phone/email trong JD; `emailAddress` field absent; `contactName` present 96% (department names, not personal).

**ITviec:**
- `GET https://itviec.com/it-jobs/{keyword}` trả 200, HTML server-rendered, **không Cloudflare**.
- 20 job cards/search page, selectors rõ ràng (`job-card ipt-2`, `h3/a`, `employer-name`, `jd-main`).
- Salary bị ẩn (`Sign in to view salary`) → data quality risk, cần fallback parse salary từ title hoặc mark low-confidence.
- PII: 0 phone/email trong sample detail page.

**TopCV:**
- `GET https://www.topcv.vn/viec-lam/data-engineer` trả **403 Cloudflare "Just a moment..." challenge**.
- Cần anti-bot POC (headless browser/stealth/residential proxy/bypass service) trước khi build.

### 6.6 Validation & Legal Pre-work

- **ToS review** is a hard gate for P0. Do not build `vietnamworks.scrape` until ToS allows automated access and commercial use.
- **Legal counsel opinion** on employment service provider classification is a hard gate.
- **SCP on NG-1** is a hard gate for cloud pricing.
- **Customer discovery** runs in parallel with technical spike.

---

## 7. Non-Goals (MVP)

- **No ATS features**: application tracking, interview scheduling, offer management, candidate pipeline.
- **No CV/profile scraping**: do not scrape candidate CVs, contact info, or profiles.
- **No outreach automation**: no auto-email/Zalo/SMS to candidates or employers.
- **No passive candidate sourcing**: do not compete with LinkedIn Recruiter in Phase 1.
- **No raw job-posting database sale**: consistent with NG-1.

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| VietnamWorks API changes or blocks | High | Technical spike completed; golden fixture regression tests; circuit-breaker; cache aggressively; HTML fallback only after ToS review |
| VietnamWorks ToS prohibits scraping | **BLOCKER** | Complete ToS review as hard gate; do not start P0 build until allowed; pivot to API partnership if banned |
| TopCV/ITviec ToS prohibits scraping | **BLOCKER** | Complete ToS review for both; do not start P0 build until allowed |
| TopCV/ITviec anti-bot blocks scraping | **BLOCKER** | Anti-bot POC is a hard gate before merging `topcv.scrape` / `itviec.scrape`; budget for residential proxies/CAPTCHA if needed |
| Classified as employment service provider | **BLOCKER** | Obtain legal counsel opinion before pilot; add disclaimer; abandon or license if required |
| PII in job descriptions | High | Implement PII detection/redaction; do not store raw JD; audit detection stats across 3 sources |
| NG-1 / BSL 1.1 conflict | High | Raise SCP; ensure value is in aggregator + memory, not raw data resale |
| Overlaps with existing HR-tech startups / VietnamWorks reports | High | Validate willingness-to-pay via customer interviews; position as research layer, not ATS/matching |
| Scope creep into ATS | Medium | Strict non-goals; gate any ATS feature behind new SCP |
| Unvalidated market demand | High | 8-week pilot with go/no-go; customer discovery in parallel |
| Effort underestimation (3 scrapers + anti-bot) | High | Spike TopCV/ITviec anti-bot before commit; estimate 18–24 dev-days for P0 |

---

## 9. Success Metrics (Pilot)

| Metric | Target (8 weeks) | Why |
|---|---|---|
| All 3 scrapers (`vietnamworks`, `topcv`, `itviec`) and `vn_jobs.aggregate` deployed | Yes | Technical feasibility |
| Job listings indexed/day (across 3 sources) | ≥1,000 | Coverage |
| Cross-source deduped listings/day | ≥600 | Quality coverage |
| Workspaces active ≥3 days/week | ≥10 | Demand validation |
| Aggregate queries | ≥100 | Usage signal |
| Customer discovery interviews | ≥10 | Validate willingness-to-pay |
| Confidence score top 80% | ≥0.6 | Quality |
| Dedupe accuracy | ≥90% | Quality |
| Cost per aggregate query | Baseline only | Determine unit economics |
| PII detection coverage | ≥95% of obvious PII | Compliance |
| ToS/legal review | Complete for all 3 sources | Gate go/no-go |
| Anti-bot POC | Pass for TopCV + ITviec | Gate go/no-go |

---

## 10. Dependencies & Sequencing

1. **Pre-req 0:** Epic 10 BĐS aggregator pattern stabilized in production for at least 2 weeks.
2. **Pre-req 1 (parallel, 1–2 weeks):**
   - ToS review for VietnamWorks, TopCV, ITviec.
   - Legal counsel opinion on employment service provider.
   - SCP on NG-1 ambiguity.
   - Customer discovery interviews.
   - Technical spike VietnamWorks API.
   - Anti-bot POC for TopCV and ITviec.
3. **Pre-req 2 (hard gate):** All pre-req 1 items pass before P0 build starts.
4. **P0 build (~3 weeks, 18–24 dev-days):**
   - Story 11.1 (VietnamWorks scraper)
   - Story 11.2 (TopCV scraper, anti-bot POC)
   - Story 11.3 (ITviec scraper, anti-bot POC)
   - Story 11.4 (PII redaction)
   - Story 11.5 (Job aggregator)
5. **Pilot (8 weeks):** Beta to 20–50 workspaces; collect usage, feedback, cost data.
6. **Go/No-Go:** Review pilot metrics; decide expand/shrink/stop.
7. **P1 (if go):** Story 11.6 (Playbook) and hardening.
8. **Post-MVP (if go):** Partner API integrations, enterprise recruiter features, salary-trend analytics.

---

## 11. Recommendation

**Approve Epic 11 as an 8-week pilot** with all three sources in P0 (VietnamWorks, TopCV, ITviec). This validates the core cross-platform value proposition from day one. Before build starts, complete the hard gates: ToS review for all 3 sources, anti-bot POC for TopCV/ITviec, legal counsel opinion, and SCP on NG-1.

Effort estimate: **18–24 dev-days** cho P0 (3 scrapers + PII redaction + aggregator + tests + anti-bot integration).

This gives Nowing a fast but controlled way to test the Vietnamese HR market while reusing the BĐS aggregator investment, avoiding ATS scope creep, and resolving the compliance and defensibility risks identified in the adversarial review.

**If pilot passes go/no-go:** proceed to P1 (playbook, salary-trend analytics) and consider full verticalization.
**If pilot fails:** stop or pivot, with clear evidence.

---

## 12. References

- Full market research: `_bmad-output/planning-artifacts/research/market-vietnam-hr-recruitment-research-2026-08-05.md`
- BĐS aggregator implementation: `_bmad-output/implementation-artifacts/10-4-vn-bds-aggregator.md`
- VietnamWorks scraper spec reference: `_bmad-output/implementation-artifacts/2-6-indeed-jobs-scraper.md`
- PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- Epics: `_bmad-output/planning-artifacts/epics.md`
