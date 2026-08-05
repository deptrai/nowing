---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/epics.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/research/market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md"
workflowType: 'research'
lastStep: 6
research_type: 'market'
research_topic: 'Vietnamese recruitment/HR market: candidate sourcing, employer hiring demand, job board data, and integration opportunities for Nowing'
research_goals: 'Identify customer segments, pain points, data sources, competitive landscape, and strategic integration options for Nowing to expand into Vietnamese HR/recruitment research'
user_name: 'Luisphan'
date: '2026-08-05'
web_research_enabled: true
source_verification: true
---

# Research Report: market

**Date:** 2026-08-05
**Author:** Mary (Business Analyst) for Luisphan
**Research Type:** market

---

## Table of Contents

- [Research Overview](#research-overview)
- [Research Initialization](#research-initialization)
- [Customer Behavior and Segments](#customer-behavior-and-segments)
- [Customer Pain Points and Needs](#customer-pain-points-and-needs)
- [Customer Decision Processes and Journey](#customer-decision-processes-and-journey)
- [Competitive Landscape](#competitive-landscape)
- [Vietnam Job Data Sources & Scrape Strategy](#vietnam-job-data-sources--scrape-strategy)
- [Strategic Synthesis and Recommendations](#strategic-synthesis-and-recommendations)
- [Integration Options for Nowing](#integration-options-for-nowing)

---

## Research Overview

This market research analyzes the Vietnamese recruitment and HR market with a focus on **candidate sourcing, employer hiring demand, and job-board data intelligence**. The goal is to identify how Nowing can extend its open-source long-term research memory into the HR vertical, starting with Vietnam.

**Key findings:**

1. Vietnam's recruitment market is resilient and growing, driven by FDI, manufacturing expansion, and digital transformation. Hiring demand in Q2 2026 rose 32% quarter-over-quarter (Adecco), with a Net Employment Outlook of +28% in Q3 2026 (ManpowerGroup).
2. The defining tension is **hiring ambition vs. execution**: 69% of employers plan to increase hiring (Reeracoen), but 80% report difficulty finding suitable candidates (Vietnam Briefing). Talent shortages are acute in AI, data, cloud, cybersecurity, semiconductor, manufacturing engineering, sales, and mid-level management.
3. Job seekers and employers operate across fragmented platforms: VietnamWorks, TopCV, ITviec, LinkedIn, CareerBuilder, CareerLink, JobHopin, and Facebook/Zalo groups. No single platform provides cross-platform market intelligence, salary benchmarking, or skill-demand analytics.
4. New HR-tech entrants (HireX, UpNow, LinkTalent, Talenten, Talehu) are AI-native but small, proprietary, and focused on matching/ATS rather than open research memory.
5. Nowing can differentiate by applying its proven **multi-source aggregation + citations + provenance + self-host** model to the recruitment vertical — essentially a "research layer for hiring" rather than an ATS.

**Methodology:** Web search across industry reports, job-platform data, recruiter insights, and open-source scraper repositories; cross-verified with multiple independent sources where possible.

---

## Research Initialization

### Research Understanding Confirmed

- **Topic:** Vietnamese recruitment/HR market: candidate sourcing, employer hiring demand, job-board data, and integration opportunities for Nowing.
- **Goals:** Identify customer segments, pain points, data sources, competitive landscape, and strategic integration options for Nowing to expand into Vietnamese HR/recruitment research.
- **Research Type:** Market Research
- **Date:** 2026-08-05

### Research Scope

**Market Analysis Focus Areas:**

- Market size, growth dynamics, and hiring demand in Vietnam
- Customer segments and behavior patterns (employers, recruiters, headhunters, job seekers, analysts)
- Competitive landscape: job boards, recruitment agencies, HR-tech platforms, data providers
- Data sources, scraping patterns, and legal/cultural constraints
- Strategic integration options and implementation guidance for Nowing

**Research Methodology:**

- Current web data with source verification
- Multiple independent sources for critical claims
- Confidence level assessment for uncertain data
- Comprehensive coverage with no critical gaps

### Scope Clarification

Clarified with Luisphan on 2026-08-05:

1. **Scope breadth:** Vietnam-first; focus on **candidate sourcing and employer/recruiter demand** ("mua-bán lead" framing) rather than full HRIS/ATS.
2. **Research goals:** (a) identify which job data sources to integrate, (b) define a lightweight vertical playbook for hiring intelligence, and (c) recommend how Nowing should position against job boards and headhunters.
3. **Competitor focus:** Local Vietnamese job platforms (VietnamWorks, TopCV, ITviec, CareerLink, JobHopin), LinkedIn, recruitment agencies (Adecco, Manpower, Navigos, Reeracoen, Talentnet, HR2B), and AI HR-tech startups.

---

## Customer Behavior and Segments

### Customer Behavior Patterns

_Behavior Drivers:_
- Vietnamese employers are **hiring more selectively**: the market is shifting from CV-volume hiring to **intelligence-led recruitment** (Reeracoen).
- **Speed is a competitive advantage**: in-demand professionals receive multiple offers within days; time-to-hire is a strategic priority (Michael Page).
- **AI and digital literacy are becoming hiring filters**: 70–75% of employers identify AI adoption and upskilling as key productivity drivers; employers are willing to pay a premium for AI/digital literacy (ManpowerGroup).
- **Retention is part of hiring decisions**: employers now weigh long-term commitment (71%), cultural fit (49%), and salary alignment (61%) alongside hands-on experience (82%) (Human Resources Online).
- **Mobile-first job search**: job seekers browse and apply via smartphone; platforms optimize for speed, notifications, and one-tap apply.

_Interaction Preferences:_
- Employers and recruiters prefer platforms with **real-time data**, salary benchmarks, candidate pipeline visibility, and integration with Zalo/Email/SMS.
- Job seekers use multiple job boards simultaneously and rely on recommendations, social proof, and direct recruiter contact.
- Analysts and HR leaders want **market intelligence**: skill-demand trends, salary pressure by function/region, competitor hiring velocity, and talent-availability signals.

_Decision Habits:_
- Employers: define JD → post to multiple boards → screen manually or via AI → interview → negotiate offer. Bottlenecks are sourcing quality candidates, salary alignment, and slow internal approvals.
- Recruiters/headhunters: maintain talent pools, search across platforms and LinkedIn, use personal networks, and match candidates to JDs for a fee.
- Job seekers: search by skill/location/salary, upload CV, apply to multiple openings, and compare offers.

_Source:_
- https://www.reeracoen.com.vn/en/articles/vietnam-employers-are-hiring-more-in-2026---but-struggling-to-compete-for-the-talent-they-need
- https://www.manpower.com.vn/en/insights/blogs/2026/06/manpowergroup-employment-outlook-survey-q3-2026-vietnam-findings
- https://www.michaelpage.com.vn/recruitment-expertise/employer-insights/cut-hiring-time-secure-top-talent
- https://production.humanresourcesonline.net/employers-in-vietnam-are-not-just-hiring-for-skills-they-are-hiring-against-attrition-new-research-shows

### Demographic Segmentation

_Age Demographics:_
- Workforce is young: a large share of job seekers are Gen Z and Millennials (18–44).
- Mid-level professionals (3–8 years experience) face the tightest supply relative to demand.

_Geographic Distribution:_
- **Hanoi** surpassed Ho Chi Minh City in Q2 2026 for both hiring scale and growth (VietnamWorks Q2/2026 report).
- Strong regional demand in Bac Ninh, Binh Duong, Hai Phong, and Da Nang due to manufacturing and FDI.
- Southern region still leads Net Employment Outlook at +33% (ManpowerGroup Q3 2026).

_Sector Concentration:_
- Highest hiring demand: **Sales, Accounting/Auditing, Architecture/Construction, Human Resources, Banking/Financial Services, Legal, IT/AI, Manufacturing, Supply Chain**.
- Hardest-to-fill roles: manufacturing engineers, sales professionals, factory supervisors, IT/AI specialists, mid-level managers (Reeracoen).

_Income Levels:_
- Average monthly income reached VND 8.4 million (~USD 336) in Q3 2025 (Vietnam Briefing).
- Bilingual premiums (Japanese, Chinese) remain at 10–20% above non-bilingual roles (Reeracoen).
- Salary pressure highest at 3–8 years experience band.

_Source:_
- https://www.navigosgroup.com/news/vietnamworks-releases-the-q2-2026-hiring-market-report/
- https://www.vietnam-briefing.com/news/vietnam-labor-market-in-2026-hiring-hotspots-and-talent-shifts.html
- https://www.reeracoen.com.vn/en/articles/salary-expectations-in-vietnam-q2-2026-what-employers-must-budget-to-hireand-retain-top-talent

### Firmographic Segmentation

**Employers by size:**
- **Mid-sized (50–249 employees):** strongest hiring demand (+39% NEO, ManpowerGroup). They have lean HR teams and need cost-effective sourcing tools.
- **Large (250–999 employees):** expansion-driven hiring, more structured procurement, willing to pay for market intelligence and RPO.
- **MNCs/FDI companies:** demand bilingual talent, compliance support, and salary benchmarking; often use recruitment agencies.

**Recruitment Agencies/Headhunters:**
- Local: Navigos Search, Talentnet, HR2B, HR Vietnam, NIC Global, First Alliances, JobHopin.
- International: Adecco, ManpowerGroup, Michael Page, Robert Walters, Reeracoen.
- They compete on speed, candidate network, and industry specialization.

**HR-tech / Data buyers:**
- AI matching platforms: HireX, UpNow, LinkTalent, Talenten, Talehu.
- Market-intelligence consumers: compensation consultants, workforce planners, investors tracking sector hiring.

---

## Customer Pain Points and Needs

### Employer Pain Points

1. **Talent shortage and rising salary expectations**
   - 80% of employers struggle to find suitable candidates; 86% cite rising salary expectations as the top hiring challenge (Reeracoen).
   - 42% of candidates are actively seeking new jobs, and 28.6% would consider switching — meaning >70% of the workforce is open to moving (Vietnam Briefing).

2. **Sourcing speed and quality**
   - Internal HR teams are overburdened; 80% of employers want faster shortlisting from recruitment partners (Reeracoen).
   - 37% of employers say hiring has become harder over the past 12 months (Michael Page).

3. **Fragmented data across job boards**
   - Employers and recruiters post to multiple platforms (VietnamWorks, TopCV, ITviec, LinkedIn, CareerLink, Facebook groups) but lack a unified view of candidate availability, salary trends, or competitor hiring.

4. **Salary benchmark accuracy**
   - Companies using 2–3 year-old compensation bands lose candidates at the offer stage. Candidates now evaluate total compensation (base, bonus, benefits, allowances) (Reeracoen).

5. **Retention risk after hire**
   - Employers hire against attrition. Top retention risks: salary competition (33%), young workforce job-hopping (24%), career progression expectations (20%) (Human Resources Online).

### Recruiter / Headhunter Pain Points

1. **Candidate pool visibility**
   - Recruiters maintain proprietary databases but lack real-time cross-platform market data.

2. **Speed to match**
   - Time-to-hire is critical; clients expect shortlists within days.

3. **Market intelligence for client counsel**
   - Clients increasingly ask for salary benchmarks, skill-demand trends, and competitor hiring data.

### Job Seeker Pain Points

1. **Information overload**
   - Hundreds of listings across platforms; difficulty identifying the right fit.

2. **Lack of salary transparency**
   - Many postings hide salary; candidates waste time on mismatched roles.

3. **Slow or no feedback**
   - Application black hole; lack of status updates.

### HR / Workforce Analyst Pain Points

1. **No real-time labor-market analytics**
   - Existing reports (VietnamWorks Q2, Reeracoen, ManpowerGroup) are periodic and high-level.
   - No platform offers live skill-demand tracking, competitor hiring velocity, or regional salary pressure by role.

---

## Customer Decision Processes and Journey

### Employer Hiring Journey

1. **Demand planning** — define headcount, budget, role requirements.
2. **Sourcing** — post JD to multiple job boards, engage headhunters, search internal database/LinkedIn.
3. **Screening** — AI or manual CV screening, phone screens.
4. **Interview & assessment** — technical, cultural, language tests.
5. **Offer & negotiation** — salary, total compensation, start date.
6. **Onboarding & retention** — onboarding, training, career path.

Nowing's earliest value is in **step 2 (sourcing intelligence)** and **pre-step 1 (market intelligence)**.

### Recruiter Journey

1. Receive client brief (role, budget, timeline).
2. Search candidate pool across platforms and networks.
3. Shortlist, pre-screen, present to client.
4. Coordinate interviews and offer.
5. Maintain candidate relationships for future roles.

Nowing can accelerate **step 2** by aggregating live job/candidate signals and providing market context.

### Job Seeker Journey

1. Update CV/profile.
2. Search and apply to multiple job boards.
3. Engage with recruiters.
4. Interview and compare offers.

Nowing is less likely to compete directly for job seekers at launch; value is primarily B2B (employers, recruiters, analysts).

---

## Competitive Landscape

### Job Boards & Platforms

| Player | Strengths | Weaknesses |
|---|---|---|
| **VietnamWorks** | Largest English-friendly direct-posting platform; 19,000+ employers, 689,000+ job seekers; public search API (no auth) | Fragmented by itself; no cross-platform aggregation |
| **TopCV** | Strong local employer base; AI screening; annual market reports | Proprietary; no open API; data siloed |
| **ITviec** | Dominant IT/tech niche; high-quality tech talent pool | Limited to tech; no cross-vertical analytics |
| **CareerBuilder/CareerLink/Glints/JobHopin** | Niche reach, sector focus | Smaller scale; proprietary data |
| **LinkedIn** | Global professional network; passive candidate sourcing | Limited Vietnamese penetration outside white-collar; expensive Recruiter seats |
| **Facebook/Zalo groups** | Informal, high-volume, local | Unstructured, noisy, no verification |

### Recruitment Agencies

| Player | Strengths | Weaknesses |
|---|---|---|
| **Adecco Vietnam** | End-to-end HR services, RPO, payroll, compliance, mass recruitment | Premium pricing; data not accessible externally |
| **ManpowerGroup Vietnam** | Global brand, staffing, outsourcing | High cost; less agile for SMB |
| **Navigos Search / Talentnet** | Strong local networks, executive search, employer branding | Fee-based; no self-service data product |
| **Reeracoen** | Data-driven hiring studies, salary benchmarks | Studies are gated/survey-based |
| **HR2B, NIC Global, First Alliances** | Local specialization, mid-market focus | Limited technology/data products |

### HR-tech Startups

| Player | Strengths | Weaknesses |
|---|---|---|
| **HireX** | AI matching, outbound hiring, talent rediscovery, Vietnam real-estate sales hiring focus | Proprietary, early stage, narrow vertical |
| **UpNow** | AI job matching, Kanban pipeline, two-way reviews | Proprietary, small traffic |
| **LinkTalent** | NLP CV reading, matching score, Zalo/Email/SMS outreach | Proprietary, enterprise sales model |
| **Talenten** | AI-powered talent matching | Tiny team and traffic |
| **Talehu** | One-stop recruiting, crowdsourcing, staffing | Basic web presence, unclear scale |

### Competitive Summary

| Segment | Players | Weakness Nowing can exploit |
|---|---|---|
| Job boards | VietnamWorks, TopCV, ITviec, CareerLink | No cross-platform market intelligence; salary data fragmented |
| Recruitment agencies | Adecco, Manpower, Navigos, Reeracoen | Data and insights locked behind services; no self-serve research layer |
| HR-tech AI matching | HireX, UpNow, LinkTalent, Talenten | Proprietary, siloed, no long-term memory or citations |
| Open-source job crawlers | epsi10nvn/vn-job-data-crawler, goodjobs, vn-jobs-data-pipeline | Need technical skill, maintenance, anti-bot, no UI/memory |

**Nowing's unique value proposition for HR:** open-source long-term research memory + citations + multi-source aggregation + self-host — applied to live job market data. This combination does not exist in Vietnam today.

---

## Vietnam Job Data Sources & Scrape Strategy

### Public Data Sources

| Source | Data available | Access pattern | Notes |
|---|---|---|---|
| **VietnamWorks** | Job title, company, location, salary range (when visible), JD, requirements, experience, function, post date | Public no-auth POST API: `POST https://ms.vietnamworks.com/job-search/v1.0/search` | ~13.7k active postings (May 2026); stable API; easiest P0 source |
| **TopCV** | Jobs, company, salary, location, tags | Public website; some API endpoints; anti-bot | Large local traffic; needs scraper |
| **ITviec** | Tech jobs, company, salary, tags, levels, skills | Public website; requires scraping | Strong tech niche |
| **CareerBuilder / CareerLink / Glints / JobHopin** | Job listings by sector | Public website; anti-bot varies | Lower priority |
| **LinkedIn** | Jobs, company, location, applicant count | Requires authenticated session or third-party scraping service | Higher friction; use ScrapingDog or similar if needed |
| **Facebook/Zalo groups** | Informal job posts, recruiter leads | Unstructured, noisy, hard to scale | Defer |

### Open-source Evidence

- `kalil0321/ats-scrapers` already implements a `VietnamWorksScraper` using the public API.
- `epsi10nvn/vn-job-data-crawler` scrapes VietnamWorks, TopCV, LinkedIn with Scrapy/Selenium.
- `vnk8071/goodjobs` aggregates LinkedIn, ITviec, TopCV, VietnamWorks, CareerViet, TopDev, JobsGo, CareerLink, Glints, ViecOi into `goodjobs.io.vn`.
- `TrNguyenMQuan/vn-jobs-data-pipeline` builds a full Medallion pipeline on VietnamWorks public API with dbt + Metabase + pgvector.

This confirms the data sources are **technically accessible** and the community has validated the scraping patterns.

### Legal and Compliance Notes

- Vietnam **Employment Law 2013** and **Decree No. 23/2021/ND-CP** regulate employment service providers (VND 300 million deposit, licensing, 5-year validity). This applies to **employment service businesses**, not necessarily to research/data aggregation for business intelligence.
- ToS of individual job boards must be respected. Public no-auth APIs (VietnamWorks search) are lower risk than authenticated scraping.
- PII: candidate CVs and contact details are high-risk. Public **job postings** (title, company, salary, JD) are lower-risk and the natural starting point.
- License alignment: Nowing's `app/proprietary/` BSL 1.1 crawler engine already handles platform-specific fetchers; the aggregator and capability contract live in Apache-2.0 core.

---

## Strategic Synthesis and Recommendations

### 1. The opportunity is "market intelligence for hiring," not an ATS

The Vietnamese recruitment market has plenty of job boards and ATS/matching tools. The gap is **cross-platform research memory**:
- Real-time skill-demand trends across VietnamWorks, TopCV, ITviec.
- Salary benchmark by role, level, location, sector — with citations.
- Competitor hiring velocity and job-posting patterns.
- Long-term tracking of how demand for a skill (e.g., "AI engineer in Hanoi") evolves.

This matches Nowing's existing strength: **live data connectors + memory + citations + deliverables**.

### 2. Beachhead customer = SMB/mid-market employers and local recruiters

- **Mid-market employers (50–249 employees)** have the strongest hiring demand and the leanest HR teams. They need fast, affordable sourcing intelligence.
- **Local recruiters/headhunters** need market intelligence to advise clients and speed up matching.
- **HR/workforce analysts** in consulting, PE, and corporates need regional talent market data.

### 3. Start with VietnamWorks public API, then expand

VietnamWorks offers a stable, no-auth public API with rich fields (title, company, location, salary, JD, requirements, function, experience). This is the lowest-friction P0 source.

P0 sources:
- VietnamWorks (public API)

P1 sources:
- TopCV (scraper)
- ITviec (scraper)

P2 sources:
- CareerLink, Glints, JobHopin, LinkedIn

### 4. Product shape: "Job Market Research" playbook, not a job board

Nowing should package HR as a **vertical research playbook** within its existing workspace:
- User asks: "Xu hướng tuyển dụng AI ở Hà Nội Q2 2026?"
- Agent calls `vn_jobs.aggregate` across VietnamWorks (+TopCV/ITviec), stores results as memories, generates a deliverable with charts and citations.
- User can save searches, schedule automations ("báo cáo hàng tuần về việc làm Data Engineer tại TP.HCM"), and track over time.

This avoids building ATS features (apply, interview scheduling, payroll) and leverages Nowing's existing primitives.

### 5. Differentiation vs. existing players

| Capability | VietnamWorks/TopCV | HireX/UpNow/LinkTalent | Nowing |
|---|---|---|---|
| Cross-platform aggregation | No | No (single platform or proprietary) | **Yes** |
| Long-term research memory | No | No | **Yes** |
| Citations / provenance | Limited | No | **Yes** |
| Self-host / open-source | No | No | **Yes** |
| Salary trend analytics | Periodic reports | Limited | **Yes, live** |
| MCP / agent integration | No | No | **Yes** |

### 6. Business model alignment

- **Self-host:** free, Apache-2.0 core + BSL crawler. Community builds connectors.
- **Cloud:** pay-as-you-go per connector call, aggregate query, and deliverable. Job-market research becomes a natural cloud-conversion driver (data is live, cloud is easiest).
- **Enterprise:** custom connectors, SLA, private deployment for recruiters who want proprietary talent-pool analytics.

This is consistent with Nowing's existing OSS/PLG-led model and avoids the Exa-like "sell raw data" trap defined in NG-1.

### 7. Non-Goals for HR vertical (proposed)

- Do **not** become an ATS (applicant tracking, interviews, offer management) in MVP.
- Do **not** scrape or store candidate CVs/contact without explicit consent and legal review.
- Do **not** sell raw job-posting databases as a data product (violates NG-1).
- Do **not** compete directly with LinkedIn Recruiter on passive candidate sourcing in Phase 1.

---

## Integration Options for Nowing

### Option A: Add native job scrapers + a Vietnam Job Aggregator (recommended)

**Description:** Build `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` as BSL fetchers, then a `vn_jobs.aggregate` capability in Apache-2.0 core that normalizes, dedupes, scores confidence, and exposes REST/MCP.

**Pros:**
- Reuses exact pattern from Epic 10 BĐS aggregator.
- VietnamWorks public API = fast P0 win.
- Fits Nowing's "connectors + memory + deliverables" architecture.
- Can be built by the same team that shipped `vn_bds.aggregate`.

**Cons:**
- Requires new proprietary fetchers for TopCV/ITviec (anti-bot, HTML parsing).
- Legal/compliance review needed for each platform.

**MVP scope:**
- `vietnamworks.scrape` (P0)
- `vn_jobs.aggregate` with VietnamWorks only (P0)
- `topcv.scrape` + `itviec.scrape` (P1)
- Job market research playbook/automation template (P1)

### Option B: Integrate with existing open-source job aggregators via MCP

**Description:** Use open-source projects like `goodjobs` or `vn-jobs-data-pipeline` as external data sources, exposed to Nowing via MCP or REST.

**Pros:**
- Less proprietary code.
- Leverages community maintenance.

**Cons:**
- Dependency on external projects with unknown reliability/scale.
- Harder to control citations, provenance, and billing.
- No guarantee of data freshness.

**Verdict:** Less aligned with Nowing's goal of owning the connector layer and citations.

### Option C: Partner with a job board (VietnamWorks/TopCV) for API access

**Description:** Negotiate official API/data partnership for structured job feeds.

**Pros:**
- Legal certainty; higher rate limits; richer data.

**Cons:**
- Long sales cycle; possible fees; platform dependency.
- Not feasible for fast MVP.

**Verdict:** Defer to Phase 2 after proving demand.

### Option D: Build an AI recruiting assistant on top of existing data (HireX-style)

**Description:** Focus on matching/job-description generation/outreach automation.

**Pros:**
- High perceived value for recruiters.

**Cons:**
- Requires ATS/candidate management features Nowing does not have.
- Competes directly with well-funded local HR-tech startups.
- Diverges from Nowing's research-memory positioning.

**Verdict:** Not recommended for MVP.

### Recommended Path: Option A

Nowing should **extend its connector catalog and aggregator pattern into the HR vertical**, starting with `vietnamworks.scrape` and `vn_jobs.aggregate`. This is the lowest-risk, highest-fit path:
- It reuses proven architecture (Epic 10 BĐS).
- It targets a clear pain point (cross-platform job market intelligence).
- It does not require building ATS features.
- It aligns with Nowing's OSS/PLG-led model and licensing boundary.

---

## Source Index

- Adecco Vietnam, "Vietnam's recruitment market shows resilience in H1," August 2026: https://vir.com.vn/vietnams-recruitment-market-shows-resilience-in-h1-158112.html
- ManpowerGroup Vietnam, "MEOS Q3 2026 Vietnam findings," June 2026: https://www.manpower.com.vn/en/insights/blogs/2026/06/manpowergroup-employment-outlook-survey-q3-2026-vietnam-findings
- Reeracoen Vietnam, "Employer Hiring Study 2026": https://www.reeracoen.com.vn/en/events/reeracoen-vietnam-employer-hiring-study-2026
- Reeracoen, "Salary Expectations in Vietnam Q2 2026": https://www.reeracoen.com.vn/en/articles/salary-expectations-in-vietnam-q2-2026-what-employers-must-budget-to-hireand-retain-top-talent
- Reeracoen, "Vietnam Employers Are Hiring More in 2026": https://www.reeracoen.com.vn/en/articles/vietnam-employers-are-hiring-more-in-2026---but-struggling-to-compete-for-the-talent-they-need
- Human Resources Online, "Employers in Vietnam are not just hiring for skills..." 2026: https://production.humanresourcesonline.net/employers-in-vietnam-are-not-just-hiring-for-skills-they-are-hiring-against-attrition-new-research-shows
- Michael Page Vietnam, "Need talent fast? Hire smarter in Vietnam": https://www.michaelpage.com.vn/recruitment-expertise/employer-insights/cut-hiring-time-secure-top-talent
- Michael Page Vietnam, "Guide to working with a recruitment agency": https://www.michaelpage.com.vn/recruitment-expertise/employer-insights/recruitment-agency-employers-guide
- VietnamWorks Q2/2026 Hiring Market Report (Navigos Group), July 2026: https://www.navigosgroup.com/news/vietnamworks-releases-the-q2-2026-hiring-market-report/
- Vietnam Briefing, "Vietnam's Labor Market in 2026": https://www.vietnam-briefing.com/news/vietnam-labor-market-in-2026-hiring-hotspots-and-talent-shifts.html/
- Invest Vietnam, "The Recruitment and Staffing Industry in Vietnam 2025": https://blog.investvietnam.co/the-recruitment-and-staffing-industry-in-vietnam-an-in-depth-analysis-for-2025/
- TopCV Insights, "Recruitment Report 2025-2026": https://insights.topcv.vn/recruitment-report-2025-2026-eng
- Kenresearch, "Vietnam Human Resource Professional Services Market 2025-2031": https://www.kenresearch.com/vietnam-human-resource-hr-professional-services-market
- Kenresearch, "Vietnam Recruitment Process Outsourcing Market 2025-2031": https://www.kenresearch.com/vietnam-recruitment-process-outsourcing-rpo-market
- SurfSense PR #1605 / `kalil0321/ats-scrapers` VietnamWorks scraper: https://github.com/kalil0321/ats-scrapers/pull/82
- `epsi10nvn/vn-job-data-crawler` (VietnamWorks/TopCV/LinkedIn): https://github.com/epsi10nvn/vn-job-data-crawler
- `vnk8071/goodjobs` (multi-source job aggregator): https://github.com/vnk8071/goodjobs
- `TrNguyenMQuan/vn-jobs-data-pipeline` (VietnamWorks Medallion pipeline): https://github.com/TrNguyenMQuan/vn-jobs-data-pipeline
- HireX: https://hirex.vn/
- UpNow: https://upnow.vn/
- LinkTalent: https://linktalent.vn/
- Talenten: https://talenten.vn/
- Talehu: https://talehu.vn/
