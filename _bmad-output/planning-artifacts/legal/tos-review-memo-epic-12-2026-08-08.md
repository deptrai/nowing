---
title: ToS Review Memo — Epic 12 HR Vertical (VietnamWorks, TopCV, ITviec)
project: Nowing
date: 2026-08-08
author: Devin (bmad-check-implementation-readiness workflow) for Luisphan
status: draft — pending legal counsel review
sources:
  - VietnamWorks (https://www.vietnamworks.com/terms-of-use)
  - TopCV (https://topcv.com/terms)
  - ITviec (https://itviec.com/blog/terms-and-conditions/)
---

# ToS Review Memo — Epic 12 HR Vertical

**Purpose:** Input memo for legal counsel. This document summarizes the public Terms of Service of VietnamWorks, TopCV, and ITviec, identifies clauses relevant to Nowing's planned `vn_jobs.aggregate` pilot, and recommends questions for legal opinion. **This memo is not a substitute for legal counsel opinion.**

**Hard gate:** Per Story 12.0 ACs and `feature-brief-hr-vertical-vietnam-2026-08-05.md` §6.6, no Epic 12 scraper code may be merged until (a) ToS review passes for all 3 sources, (b) legal counsel confirms no employment-service-provider classification.

---

## 1. Executive Summary

| Source | ToS URL | Automated Access | Commercial Use | Verdict |
|--------|---------|------------------|----------------|---------|
| VietnamWorks | https://www.vietnamworks.com/terms-of-use | ⚠️ Restricted ("Mass registration and automation" prohibited) | ⚠️ Restricted ("Improper purposes" — non-recruitment use prohibited) | 🔴 Likely BLOCKER |
| TopCV | https://topcv.com/terms | 🔴 Explicitly prohibited (3 separate clauses) | 🔴 Prohibited | 🔴 BLOCKER |
| ITviec | https://itviec.com/blog/terms-and-conditions/ | 🟡 Restrictive IP clause (no explicit scraping ban) | 🟡 "Reasonable personal use" only without written consent | 🟡 Needs legal opinion |

**Preliminary recommendation:** TopCV is a clear BLOCKER — ToS explicitly prohibits scraping. VietnamWorks is a likely BLOCKER — ToS prohibits non-recruitment use and automation. ITviec is ambiguous — needs legal counsel opinion on whether research aggregation qualifies as "reasonable personal use" or requires written consent.

**If TopCV and VietnamWorks are blocked:** Epic 12 P0 scope reduces from 3 sources to 1 (ITviec only), which may not justify the pilot. Consider (a) seeking API partnerships, (b) pivoting to sources with permissive ToS, or (c) abandoning Epic 12.

---

## 2. VietnamWorks — Detailed ToS Analysis

**Source:** https://www.vietnamworks.com/terms-of-use (fetched 2026-08-08)
**Operator:** Navigos Group Vietnam Joint Stock Company (en-Japan subsidiary)
**Public API:** `POST https://ms.vietnamworks.com/job-search/v1.0/search` (no-auth, observed in technical spike 2026-08-05)

### 2.1 Relevant Clauses

#### Clause A — "Mass registration and automation" (User Conduct section)

> **Mass registration and automation.** Accounts that are registered automatically and/or systematically in mass, at the Company's sole discretion, will be considered as breach will be dealed with as regulated in this Terms of Use.

**Analysis:** This clause prohibits automated mass account registration. Nowing's `vietnamworks.scrape` does not register accounts — it uses the no-auth public API. **However**, the clause's broader phrasing ("automation") could be interpreted to cover any automated access, including API calls. The public API is not gated by authentication, which suggests the operator intends it for public use, but the ToS does not explicitly exempt API access from the "automation" prohibition.

**Risk level:** Medium — depends on interpretation of "automation" (account registration vs. any automated access).

#### Clause B — "Improper purposes" (User Conduct section)

> **Improper purposes.** Any act of abusing and/or using VietnamWorks Website that deviates from the purpose of recruitment or employment opportunity seeking, at the Company's sole discretion, will be considered as breach will be dealed with as regulated in this Terms of Use.

**Analysis:** This is the most concerning clause. Nowing is a **research/memory layer**, not a recruitment tool. The `vn_jobs.aggregate` capability is designed for market research (salary trends, hiring demand, skill analysis), not for recruitment or job seeking. Under a strict reading, using VietnamWorks data for market research "deviates from the purpose of recruitment or employment opportunity seeking" and would be considered a breach.

**Risk level:** High — Nowing's use case (research aggregation) is explicitly outside the stated purpose (recruitment/job seeking).

#### Clause C — Eligible user restrictions (VietnamWorks Services section)

> The Company shall reserve the right to make changes to its services... to individuals, companies and organizations which...:
> 3. To exploit, to use any information provided by the Company's services not for his/her/their own recruitment purpose; and/or
> 4. Provide the services which are directly or indirectly competitive with existing services of the Company

**Analysis:** Clause C.3 prohibits using VietnamWorks information for non-recruitment purposes. Nowing's `vn_jobs.aggregate` uses job postings for market research, not recruitment. Clause C.4 prohibits services competitive with VietnamWorks — Nowing is not a job board, but an aggregator could be seen as competitive if it reduces demand for direct VietnamWorks usage.

**Risk level:** High — Nowing's research use case is explicitly outside the permitted "own recruitment purpose".

#### Clause D — robots.txt

**Source:** https://www.vietnamworks.com/robots.txt (fetched 2026-08-08)

VietnamWorks robots.txt disallows profile/career-center/apply/login areas but does **not** disallow job search or job detail pages. The public API at `ms.vietnamworks.com` is on a different subdomain and not covered by the main site robots.txt.

**Analysis:** robots.txt is permissive for job listings, but robots.txt does not override ToS. The ToS "Improper purposes" clause still applies regardless of robots.txt.

### 2.2 VietnamWorks Verdict

**🔴 Likely BLOCKER.** The ToS "Improper purposes" clause (Clause B) and eligible-user restriction (Clause C.3) explicitly limit use to recruitment/job-seeking. Nowing's research aggregation use case falls outside this scope. The public API being no-auth suggests the operator permits technical access, but the ToS does not permit the use case.

**Questions for legal counsel:**
1. Does the "Improper purposes" clause apply to automated API access, or only to website account usage?
2. Is market research using publicly visible job postings "recruitment purpose" under Vietnamese law?
3. Does the no-auth public API constitute implied consent to automated access, overriding the "automation" clause?
4. Can Nowing obtain a commercial API license or partnership to override ToS restrictions?

---

## 3. TopCV — Detailed ToS Analysis

**Source:** https://topcv.com/terms (fetched 2026-08-08)
**Operator:** TopCV (Toàn Cầu Viec — based on registration)
**Access:** Website only, protected by Cloudflare "Just a moment..." challenge (confirmed in technical spike 2026-08-05)

### 3.1 Relevant Clauses

#### Clause A — No automated access (User representations)

> By using the Platform, you represent and warrant that:... (6) you will not access the Platform through automated or non-human means, whether through a bot, script or otherwise

**Analysis:** This is an explicit, unambiguous prohibition on automated access. Nowing's `topcv.scrape` is automated access by definition. **No interpretation needed — this is a direct prohibition.**

#### Clause B — No data mining/scraper (Prohibited activities)

> 14. Engage in any automated use of the system, such as using scripts to send comments or messages, or using any data mining, robots, or similar data gathering and extraction tools.

**Analysis:** Explicit prohibition on data mining, robots, and data gathering tools. Nowing's scraper is a data gathering tool. **Direct violation.**

#### Clause C — No spider/robot/scraper (Prohibited activities)

> 20. Except as may be the result of standard search engine or Internet browser usage, use, launch, develop, or distribute any automated system, including without limitation, any spider, robot, cheat utility, scraper, or offline reader that accesses the Platform, or using or launching any unauthorized script or other software.

**Analysis:** Explicit prohibition on scrapers. The "standard search engine" exception does not apply to Nowing (Nowing is not a search engine indexing for search results; it aggregates for research memory). **Direct violation.**

### 3.2 TopCV Verdict

**🔴 BLOCKER.** TopCV ToS contains three separate, explicit, unambiguous prohibitions on scraping and automated access. There is no interpretation under which Nowing's `topcv.scrape` would be compliant. The Cloudflare anti-bot challenge (confirmed in technical spike) is a technical enforcement of these ToS provisions.

**Recommendation:** **Remove TopCV from Epic 12 P0 scope.** Do not build `topcv.scrape`. If TopCV data is critical, the only compliant path is a commercial API partnership with TopCV.

**Questions for legal counsel:**
1. Confirm that the three clauses above constitute an absolute prohibition on scraping.
2. Is there any exception for research/non-commercial use? (ToS does not appear to provide one.)
3. Would a Cloudflare bypass service (e.g., scrapingbee, zenrows) constitute "circumvention" under Vietnamese law?

---

## 4. ITviec — Detailed ToS Analysis

**Source:** https://itviec.com/blog/terms-and-conditions/ (fetched 2026-08-08; main site `itviec.com/terms` returns 404)
**Operator:** IT Viec Joint Stock Company (Mynavi Corporation subsidiary)
**Employment Service Certificate:** #19710/2023/39/SLĐTBXH-VLATLĐ (licensed employment service provider)
**Access:** Website, server-rendered HTML, no anti-bot challenge observed in technical spike

### 4.1 Relevant Clauses

#### Clause A — Intellectual Property Rights (Section 2.2)

> Other than insofar as necessary for reasonable personal use of the website, its content may not be retrieved, displayed, modified, copied, printed, sold, downloaded, sold, hired, reverse engineered or transmitted in any way without our prior written consent.

**Analysis:** This clause restricts retrieval of content to "reasonable personal use" without written consent. Nowing's `itviec.scrape` retrieves job postings for aggregation into research memory — this is not "personal use" (it's a commercial service). Under a strict reading, Nowing would need ITviec's **prior written consent** to scrape.

**However:**
- ITviec robots.txt explicitly allows crawling: `User-Agent: * / Allow: /` (only `/subscriptions/new` disallowed).
- ITviec serves server-rendered HTML with no anti-bot challenge, suggesting technical permissiveness.
- Multiple public scrapers exist (haucongle/itviec-scraper, kieuvantuyen01/itviec-scraper) — though existence of scrapers does not imply ToS compliance.

**Risk level:** Medium — the IP clause is restrictive but robots.txt is permissive. Needs legal opinion on whether robots.txt allowance + no anti-bot constitutes implied consent, or whether explicit written consent is still required.

#### Clause B — Governing law (Section 6.2)

> The Terms shall be governed, construed, and shall take effect in accordance with the Laws of Vietnam; and shall be subject to the exclusive jurisdiction of Vietnamese courts.

**Analysis:** Vietnamese law applies. This is relevant for the employment-service-provider classification question (Section 5 below).

### 4.2 ITviec Verdict

**🟡 Needs legal counsel opinion.** ITviec ToS does not explicitly prohibit scraping (unlike TopCV), but the IP clause restricts content retrieval to "reasonable personal use" without written consent. The permissive robots.txt and lack of anti-bot suggest technical tolerance, but ToS compliance is a legal question, not a technical one.

**Questions for legal counsel:**
1. Does ITviec's permissive robots.txt (`Allow: /`) constitute implied consent to automated retrieval, overriding the "prior written consent" requirement in Section 2.2?
2. Does "reasonable personal use" extend to research aggregation for a commercial product?
3. Should Nowing request written consent from ITviec before launching `itviec.scrape`?
4. Is ITviec's Employment Service Certificate (#19710/2023/39/SLĐTBXH-VLATLĐ) relevant to whether Nowing needs a similar license to aggregate job data?

---

## 5. Employment Service Provider Classification — Legal Question

**Context:** All three sources (VietnamWorks, TopCV, ITviec) are licensed employment service providers in Vietnam. ITviec explicitly displays its certificate number (#19710/2023/39/SLĐTBXH-VLATLĐ). The question is whether Nowing's `vn_jobs.aggregate` — which aggregates job postings for market research — would be classified as an "employment service provider" / "môi giới việc làm" under Vietnamese law, requiring a license.

### 5.1 Nowing's Position

Nowing is a **research/memory layer**, not an employment service:
- **No** job posting (Nowing does not post jobs on behalf of employers)
- **No** candidate application processing (Nowing does not accept or forward CVs)
- **No** candidate-employer matching (Nowing aggregates data, does not match)
- **No** recruitment intermediary services (Nowing does not broker between parties)
- **Yes** data aggregation for research (salary trends, hiring demand, skill analysis)
- **Yes** citations and provenance (every data point links back to source)

### 5.2 Questions for Legal Counsel

1. Under Vietnamese labor law (Decree 23/2021/ND-CP on employment services), does aggregating publicly visible job postings for market research constitute "employment service" / "môi giới việc làm"?
2. If Nowing does not post jobs, process applications, or match candidates, is it exempt from employment service licensing?
3. Does the "research/memory layer" positioning provide sufficient legal distance from intermediary classification?
4. What disclaimers or feature restrictions should Nowing implement to avoid classification as an employment service provider?
5. Does PII redaction (Story 12.5) affect the classification — i.e., does NOT storing candidate contact info help avoid intermediary status?

---

## 6. Recommendations

### 6.1 Immediate Actions (before any Epic 12 code)

1. **Send this memo to legal counsel** for written opinion on:
   - TopCV: Confirm scraping prohibition (likely quick answer — ToS is explicit)
   - VietnamWorks: Whether research aggregation violates "Improper purposes" clause
   - ITviec: Whether robots.txt allowance constitutes implied consent
   - Employment service provider classification for Nowing

2. **Do not build `topcv.scrape`** — ToS explicitly prohibits scraping. Remove TopCV from Epic 12 P0 scope pending legal opinion. Update `epics.md` Story 12.2 status and `sprint-status.yaml` accordingly.

3. **Do not build `vietnamworks.scrape`** until legal counsel opines on "Improper purposes" clause. The no-auth API is technically accessible, but ToS may prohibit the use case.

4. **Consider API partnership outreach** to VietnamWorks and TopCV — a commercial API agreement would override ToS restrictions. ITviec may also require written consent (Section 2.2).

### 6.2 If TopCV and VietnamWorks Are Blocked

Epic 12 P0 scope reduces from 3 sources to 1 (ITviec only). Options:

| Option | Description | Trade-off |
|--------|-------------|-----------|
| A. ITviec-only pilot | Build `itviec.scrape` + `vn_jobs.aggregate` with single source | Low value — cross-source comparison is the core value prop; single-source pilot may not validate |
| B. API partnerships | Negotiate commercial API access with VietnamWorks/TopCV | Slow (weeks-months), may require revenue share, but compliant |
| C. Pivot to permissive sources | Find job boards with ToS-permissive scraping (e.g., open data, RSS feeds) | Unknown which Vietnamese job boards have permissive ToS; may not have IT/tech focus |
| D. Abandon Epic 12 | Drop HR vertical pilot entirely | Frees resources for Epics 13-18; loses HR market opportunity |
| E. Public data only | Use only government/public-sector job postings (no ToS restrictions) | Limited data coverage; may not match market demand |

### 6.3 Compliance Safeguards (regardless of source)

If any source is approved (by ToS permission or API partnership), implement these safeguards:

1. **PII redaction** (Story 12.5) — mandatory before any data enters memory
2. **Rate limiting** — respect source infrastructure; do not degrade service
3. **Citations and provenance** — every data point links back to source URL + timestamp
4. **No candidate contact** — Nowing must not store or expose candidate phone/email/name
5. **No application processing** — Nowing must not facilitate job applications
6. **Research-only messaging** — public docs clearly state Nowing is research, not ATS/job board
7. **Degradation on block** — if source blocks (403/CAPTCHA), return `degraded=true` and do not bypass

---

## 7. Decision Log

| Date | Decision | Status |
|------|----------|--------|
| 2026-08-05 | Story 12.0 created as hard gate before Epic 12 scraper code | ✅ Documented |
| 2026-08-08 | ToS review memo drafted (this document) | 🟡 Pending legal counsel |
| 2026-08-08 | TopCV identified as BLOCKER (ToS explicitly prohibits scraping) | 🟡 Pending legal confirmation |
| 2026-08-08 | VietnamWorks identified as likely BLOCKER ("Improper purposes" clause) | 🟡 Pending legal opinion |
| 2026-08-08 | ITviec identified as ambiguous (IP clause vs permissive robots.txt) | 🟡 Pending legal opinion |
| TBD | Legal counsel opinion on employment service provider classification | ⬜ Pending |
| TBD | Final go/no-go decision per source | ⬜ Pending |

---

## 8. References

- VietnamWorks ToS: https://www.vietnamworks.com/terms-of-use
- VietnamWorks robots.txt: https://www.vietnamworks.com/robots.txt
- TopCV ToS: https://topcv.com/terms
- TopCV robots.txt: https://www.topcv.vn/robots.txt
- ITviec ToS (blog): https://itviec.com/blog/terms-and-conditions/
- ITviec robots.txt: https://itviec.com/robots.txt
- ITviec About Us (certificate): https://itviec.com/about-us
- Technical spike VietnamWorks: `_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md`
- Technical spike TopCV/ITviec: `_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md`
- Feature brief HR vertical: `_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md`
- Story 12.0 ACs: `_bmad-output/planning-artifacts/epics.md` (line 1267)
- ToS decision log (scaffold): `_bmad-output/planning-artifacts/legal/tos-legal-epic-12-hr-vertical-2026-08-05.md`
- Decree 23/2021/ND-CP (employment services): https://thuvienphapluat.vn/van-ban/Lao-dong/Nghi-dinh-23-2021-ND-CP-dich-vu-viec-lam-486111.aspx
