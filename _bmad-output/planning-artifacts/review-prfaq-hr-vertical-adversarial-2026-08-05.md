---
title: Adversarial Review — PRFAQ HR Vertical for Vietnam
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
status: BLOCKER ISSUES IDENTIFIED
---

# Adversarial Review Report: HR Vertical for Vietnam

**Date:** 2026-08-05  
**Reviewed:**
- `_bmad-output/planning-artifacts/prfaq-hr-vertical-vietnam-2026-08-05.md`
- `_bmad-output/planning-artifacts/research/market-vietnam-hr-recruitment-research-2026-08-05.md`
- `_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md`

**Status:** BLOCKER ISSUES IDENTIFIED

---

## Executive Summary

The HR vertical proposal has **significant unhandled weaknesses** across all five personas. While the technical pattern reuse from BĐS aggregator is sound, the proposal suffers from:

1. **Unvalidated market assumptions** (TAM/SAM/SOM are speculative)
2. **Legal/compliance gaps** (ToS review incomplete, PII risks underestimated)
3. **Defensibility concerns** (easily replicated by incumbents)
4. **Technical effort underestimation** (anti-bot complexity dismissed)
5. **Strategic ambiguity** (vertical expansion vs. product dilution)

**Recommendation:** DO NOT APPROVE Epic 11 in current form. Require evidence-based market validation, legal review completion, and strategic clarity before proceeding.

---

## Persona 1: Skeptical Investor

### Weakness 1: TAM/SAM/SOM are speculative, not evidence-based
**Severity:** BLOCKER  
**Evidence:**
- PRFAQ §Q7 claims TAM $50-100M, SAM $5-15M, SOM $1-2K MRR Year 1 with **no methodology**.
- No customer interviews, pre-sales, or demand validation cited.
- Market research cites industry reports (Reeracoen, ManpowerGroup) but these describe **hiring demand**, not **willingness to pay for cross-platform aggregation**.
- SOM of $1-2K MRR (100-300 workspaces × $10-20/month) is trivial vs. claimed $5-15M SAM.

**Why this matters:** Without validated demand, this is a solution looking for a problem. The revenue assumptions are disconnected from actual buyer behavior.

**Recommended Fix:**
- Conduct 10-15 customer discovery interviews with target segment (mid-market HR managers, recruiters).
- Test pricing willingness via landing page or pre-sale.
- Re-calculate TAM/SAM/SOM with bottom-up methodology (price × qualified leads × conversion).
- Gate Epic 11 on evidence of 5+ pre-committed workspaces.

---

### Weakness 2: Defensibility is weak — this is easily a feature of bigger platforms
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q1 claims differentiation as "research intelligence layer" vs. job boards.
- **VietnamWorks, TopCV, ITviec could launch cross-platform aggregation in 3-6 months** by either (a) scraping competitors or (b) partnering.
- LinkedIn Recruiter already has cross-platform data and passive candidate sourcing.
- Feature brief §5 acknowledges "No cross-platform market intelligence" as a weakness — but this is a **feature gap, not a moat**.

**Why this matters:** If incumbents close this gap, Nowing loses its wedge. The "research layer" positioning is not a durable competitive advantage.

**Recommended Fix:**
- Articulate the **time-to-market advantage** (how long would it take VietnamWorks to build this?).
- Identify **network effects** or **data moats** that accumulate over time (e.g., historical salary trends, skill-demand velocity).
- Consider partnership model with one job board to create exclusivity.
- If defensibility cannot be established, frame this as a **short-term wedge** (not a long-term vertical).

---

### Weakness 3: Margin assumptions are optimistic
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q6 claims cost 1,000-2,000 micros/item, aggregate query 5,000 micros, selling at 1.5-2.5× margin.
- **No breakdown of fixed costs** (dev, maintenance, anti-bot infrastructure, legal review).
- **No account for API rate limits** — VietnamWorks may throttle or require paid access at scale.
- Feature brief §9 claims aggregate query cost ≤$0.01, but PRFAQ §Q6 estimates $0.08-0.20 — **10× discrepancy**.

**Why this matters:** If margins are squeezed by rate limits, anti-bot costs, or legal compliance, the unit economics may not work.

**Recommended Fix:**
- Build a **unit economics model** with fixed + variable costs.
- Test VietnamWorks API rate limits at projected scale.
- Include contingency for anti-bot infrastructure (proxies, CAPTCHA solving).
- Re-validate pricing assumptions with actual cost data from P0 implementation.

---

## Persona 2: Technical Realist

### Weakness 1: VietnamWorks API stability is unproven
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q8 claims VietnamWorks has "public API no-auth" with "stable fields".
- Market research §5 cites `kalil0321/ats-scrapers` and `TrNguyenMQuan/vn-jobs-data-pipeline` as evidence — but these are **community projects, not official documentation**.
- **No evidence of VietnamWorks API terms, rate limits, or change notification policy**.
- Feature brief §6.4 mitigation is "monitor API; implement fallback HTML scraping" — but HTML scraping may violate ToS (see Compliance section).

**Why this matters:** If VietnamWorks changes or blocks the API, P0 becomes a blocker. Relying on undocumented public APIs is high-risk.

**Recommended Fix:**
- Contact VietnamWorks for official API documentation or partnership.
- Implement **API contract regression tests** (similar to FR-24/ChainLens).
- Build **HTML fallback only after legal review** of ToS.
- Add **circuit breaker** to fail fast if API returns unexpected responses.

---

### Weakness 2: TopCV/ITviec anti-bot complexity is underestimated
**Severity:** MAJOR  
**Evidence:**
- Feature brief §6.4 dismisses anti-bot as "use warmed browser, residential proxy rotation, rate-limit".
- Market research §5 notes TopCV has "anti-bot" but provides **no technical detail**.
- **No mention of Cloudflare, CAPTCHA, or fingerprinting** — common in Vietnamese job boards.
- AD-19 (Architecture Spine) establishes that anti-bot/CAPTCHA solving is Nowing's responsibility, but **no evidence of existing TopCV/ITviec anti-bot patterns**.

**Why this matters:** Anti-bot is not a "toggle" — it requires ongoing maintenance. If TopCV/ITviec escalate (e.g., Cloudflare Turnstile), the P1 sources may become infeasible.

**Recommended Fix:**
- Conduct **technical reconnaissance** on TopCV/ITviec anti-bot measures before committing to P1.
- Reuse existing anti-bot infrastructure from BĐS scrapers (if applicable).
- Gate P1 on **successful POC** of anti-bot bypass.
- Budget for ongoing anti-bot maintenance (not one-time effort).

---

### Weakness 3: Dev effort is underestimated — copy-modify is not 5-8 days
**Severity:** MINOR  
**Evidence:**
- PRFAQ §Q4 claims copy-modify effort is "5-8 dev-days".
- Feature brief §6.1 claims reuse of BĐS aggregator pattern.
- **But domain differences are significant:**
  - Salary normalization (triệu/tỷ/USD/thỏa thuận) vs. price (billion/m²).
  - Skills/experience fields vs. area/bed/bath.
  - Dedupe key (company+title+location+posted_at) vs. (project+address+price).
- **No account for testing, edge cases, or data quality validation**.

**Why this matters:** If effort is 2-3× higher, opportunity cost increases. The "ponytail" rule (copy-modify before abstract) is sound, but the estimate is optimistic.

**Recommended Fix:**
- Build a **spike/PoC** to validate effort estimate.
- Include testing, edge case handling, and data quality validation in estimate.
- If effort exceeds 10-12 days, reconsider abstraction approach.
- Update PRFAQ with realistic estimate based on spike results.

---

## Persona 3: Compliance/Legal Reviewer

### Weakness 1: ToS review is incomplete — assumes "public API = safe"
**Severity:** BLOCKER  
**Evidence:**
- PRFAQ §Q8 claims "VietnamWorks has public API no-auth — rủi ro thấp".
- Market research §5 states "ToS of individual job boards must be respected" but **provides no actual ToS analysis**.
- **No evidence of VietnamWorks, TopCV, or ITviec ToS being reviewed**.
- Feature brief §8 lists "ToS / legal issues" as a risk with mitigation "review ToS before scaling" — but this is **post-facto, not pre-approval**.

**Why this matters:** Scraping without ToS review exposes Nowing to legal risk. If VietnamWorks/TopCV/ITviec prohibit scraping in ToS, the entire vertical is non-compliant.

**Recommended Fix:**
- **BLOCK Epic 11 until ToS review is complete** for VietnamWorks, TopCV, and ITviec.
- Document ToS clauses related to: (a) automated access, (b) data reuse, (c) commercial redistribution.
- If ToS prohibits scraping, pivot to (a) official API partnership or (b) abandon the vertical.
- Legal review should be **pre-condition**, not mitigation.

---

### Weakness 2: PII risks are underestimated
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q6 claims "Nowing chỉ thu thập tin tuyển dụng công khai (title, công ty, địa điểm, lương, mô tả công việc, yêu cầu, ngày đăng). Chúng tôi không scrape CV, số điện thoại, email, hoặc thông tin cá nhân của ứng viên."
- **But job descriptions often contain:** candidate names, phone numbers, email addresses, or links to social profiles.
- Market research §5 notes "PII: candidate CVs and contact details are high-risk. Public job postings (title, company, salary, JD) are lower-risk" — but this is a **false dichotomy**; JDs can contain PII.
- **No PII detection/redaction pipeline** described in feature brief.

**Why this matters:** Even if intent is to avoid PII, accidental collection is possible. Vietnamese data protection laws (Decree 13/2023/ND-CP) require consent for PII processing.

**Recommended Fix:**
- Add **PII detection/redaction** to the aggregation pipeline (e.g., regex for phone/email, named entity recognition for names).
- Define **data retention policy** for scraped job data (AR-4 from epics).
- Conduct **PII risk assessment** before P0 deployment.
- Update PRFAQ to acknowledge PII risk and mitigation.

---

### Weakness 3: Vietnamese labor law compliance is unclear
**Severity:** MAJOR  
**Evidence:**
- Market research §5 cites "Employment Law 2013 and Decree No. 23/2021/ND-CP regulate employment service providers (VND 300 million deposit, licensing, 5-year validity). This applies to employment service businesses, not necessarily to research/data aggregation for business intelligence."
- **This is a legal conclusion without legal counsel review**.
- Feature brief §8 lists "ToS / legal issues" as a risk but does **not** address employment service provider classification.
- **No analysis of whether Nowing could be classified as an "employment service provider"** under Vietnamese law.

**Why this matters:** If Nowing is classified as an employment service provider, it would require licensing, deposit, and compliance — making the vertical infeasible.

**Recommended Fix:**
- **Obtain legal counsel opinion** on whether Nowing's job market research constitutes an "employment service" under Vietnamese law.
- If classification is ambiguous, add **contractual disclaimers** (e.g., "Nowing is not an employment service provider").
- If classification is clear as employment service, **abandon the vertical** or obtain licensing.
- Gate Epic 11 on legal counsel sign-off.

---

### Weakness 4: BSL 1.1 crawler constraints may conflict with business model
**Severity:** MINOR  
**Evidence:**
- PRFAQ §Q4 states "Fetchers job board nằm trong `app/proprietary/platforms/` theo BSL 1.1 — được dùng production nhưng không được bán lại dưới dạng hosted service."
- Feature brief §6.2 confirms "Fetchers live in `app/proprietary/platforms/` (BSL 1.1)."
- **But cloud business model is "pay-as-you-go per connector call"** — this is effectively selling access to BSL-licensed fetchers as a hosted service.
- PRD §1.1 (license boundary) states BSL fetchers "không được đem chính nó (hoặc sản phẩm/dịch vụ mà giá trị chủ yếu bắt nguồn từ nó) bán cho bên thứ ba như commercial product hoặc hosted/managed service."

**Why this matters:** If the HR vertical's value is primarily the fetchers (not the aggregation/memory layer), this may violate BSL 1.1 terms.

**Recommended Fix:**
- Clarify whether **aggregator + memory + citations** (Apache-2.0 core) provides sufficient value without BSL fetchers.
- If yes, ensure BSL fetchers are **optional** (self-hosters can bring their own).
- If no, reconsider license strategy or vertical value proposition.
- Document license boundary analysis in feature brief.

---

## Persona 4: Competitive Analyst

### Weakness 1: Why use Nowing vs. VietnamWorks paid reports?
**Severity:** MAJOR  
**Evidence:**
- Market research §5 cites "VietnamWorks Q2/2026 Hiring Market Report" as a source.
- VietnamWorks already publishes **periodic market reports** with salary trends, hiring demand, and skill analysis.
- PRFAQ §Q1 claims Nowing differentiates via "real-time data" and "cross-platform aggregation" — but **VietnamWorks could add real-time dashboards**.
- **No evidence that customers find VietnamWorks reports insufficient**.

**Why this matters:** If VietnamWorks reports already satisfy the "market intelligence" need, Nowing's wedge is weak.

**Recommended Fix:**
- Interview customers who use VietnamWorks reports to identify **gaps** (e.g., real-time, cross-platform, historical trends).
- If gaps are small, reconsider the vertical.
- If gaps are real, emphasize them in PRFAQ (currently absent).

---

### Weakness 2: Why use Nowing vs. HireX/UpNow/LinkTalent?
**Severity:** MAJOR  
**Evidence:**
- Market research §5 lists HireX, UpNow, LinkTalent as "AI-native HR-tech startups" with strengths in "AI matching, outbound hiring, talent rediscovery".
- Feature brief §5 claims differentiation via "cross-platform + citations + self-host" — but **HireX/UpNow/LinkTalent could add citations**.
- **No evidence that customers want "research memory" vs. "AI matching"**.
- Feature brief §2 claims "pain point: fragmented data across job boards" — but HireX/UpNow/LinkTalent solve this via **matching, not research**.

**Why this matters:** If customers want matching/outreach (not research), Nowing is solving the wrong problem.

**Recommended Fix:**
- Clarify the **job-to-be-done**: is it "research market" or "find candidates"?
- If it's "find candidates," Nowing is not competitive vs. HireX/UpNow/LinkTalent.
- If it's "research market," validate that customers actually pay for this (vs. using free reports).
- Update PRFAQ to explicitly address why customers would choose Nowing over AI matching platforms.

---

### Weakness 3: Why use Nowing vs. LinkedIn Recruiter?
**Severity:** MINOR  
**Evidence:**
- Market research §5 notes LinkedIn has "Global professional network; passive candidate sourcing" but "Limited Vietnamese penetration outside white-collar; expensive Recruiter seats".
- Feature brief §7 non-goals states "No passive candidate sourcing: do not compete with LinkedIn Recruiter in Phase 1".
- **But if the value is "market intelligence," LinkedIn Recruiter already has this** (hiring insights, skill demand, salary benchmarks).
- **No evidence that LinkedIn Recruiter's insights are insufficient for Vietnamese market**.

**Why this matters:** For white-collar roles, LinkedIn Recruiter may already satisfy the need. Nowing's wedge is unclear.

**Recommended Fix:**
- Validate that LinkedIn Recruiter's insights are **insufficient** for Vietnamese market.
- If sufficient, focus on **non-white-collar segments** (manufacturing, construction, local SMEs).
- Update PRFAQ to explicitly position vs. LinkedIn Recruiter.

---

## Persona 5: Nowing Purist

### Weakness 1: Does this violate NG-1 (selling research data)?
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q3 claims "NG-1 (không bán research data kiểu Exa): Chúng ta không bán raw job-posting database; chúng ta cung cấp research tool."
- **But the business model is "pay-as-you-go per query"** — this is effectively selling access to aggregated job data.
- PRD §2.4 NG-1 states "Nowing không bán raw web index hay research corpus như một sản phẩm dữ liệu" and cites "Biến thể duy nhất còn mở (chưa phê duyệt): bán research output/deliverable đã cấu trúc cho một vertical cụ thể — không phải raw index."
- **The HR vertical is exactly this "biến thể"** — but it has not been approved via SCP.

**Why this matters:** NG-1 is a **frozen non-goal** (§2.4: "đóng vĩnh viễn — 🔒 frozen tới 2026-08-24"). Violating it requires SCP.

**Recommended Fix:**
- **Raise SCP to clarify whether selling job market research queries violates NG-1**.
- If approved, document the exception in PRD §2.4.
- If not approved, restructure the business model (e.g., sell the tool, not the data).
- Do not proceed with Epic 11 until NG-1 ambiguity is resolved.

---

### Weakness 2: Does this violate NG-2 (consumer parity)?
**Severity:** MINOR  
**Evidence:**
- PRFAQ §Q3 claims "NG-2 (không đua Perplexity parity): Đây là vertical research, không phải consumer search."
- **But the press release frames it as "nhà tuyển dụng, headhunter và nhà phân tích nhân sự"** — this is B2B, not consumer.
- Feature brief §2 targets "SMB/mid-market employers and local recruiters" — also B2B.
- **No evidence of consumer-facing features**.

**Why this matters:** This appears to comply with NG-2, but the framing is ambiguous. If the product evolves to serve job seekers (consumer), it would violate NG-2.

**Recommended Fix:**
- Add explicit non-goal: "No job seeker-facing features in MVP" (already in feature brief §7, but not in PRFAQ).
- Document the B2B-only positioning in PRD.
- If job seeker features are considered later, raise SCP to revisit NG-2.

---

### Weakness 3: Is this a strategic pivot or a vertical?
**Severity:** MAJOR  
**Evidence:**
- PRFAQ §Q2 claims "This is vertical expansion of product surface, not a new product line."
- **But the HR vertical requires:** new domain knowledge (recruitment), new data sources (job boards), new normalization rules (salary, skills), new playbooks (job market research).
- PRD §1.1 states "Nowing là bộ nhớ nghiên cứu lâu dài" — HR vertical is consistent, but **the beachhead is "AI agent builder" (§2.1)**, not HR.
- **No evidence that HR aligns with the "agent builder → team" rollout sequence**.

**Why this matters:** If this is a pivot away from the agent-builder beachhead, it dilutes focus. If it's a vertical, it needs to be sequenced after the beachhead is validated.

**Recommended Fix:**
- Clarify the **strategic rationale**: is HR a (a) vertical to monetize agent builders, (b) new beachhead, or (c) pivot?
- If (a), document how HR features will be used by agent builders (e.g., "agent builders can build HR research agents").
- If (b), raise SCP to change beachhead from "agent builder" to "HR".
- If (c), raise SCP to approve pivot.
- Update PRFAQ to explicitly state strategic rationale.

---

### Weakness 4: Does this violate the "ponytail" rule (abstraction before validation)?
**Severity:** MINOR  
**Evidence:**
- PRFAQ §Q4 cites "ponytail rule: copy-modify trước, abstract sau khi có 2–3 vertical stable."
- Feature brief §6.1 states "reuse `app/services/bds_aggregator/` as `app/services/jobs_aggregator/`, or generalize `bds_aggregator` into a shared `vertical_aggregator` service."
- **The proposal correctly chooses copy-modify**, but **BĐS aggregator just shipped (Epic 10, done 2026-08-03)** — it has not been validated in production.
- **No evidence that BĐS aggregator pattern is stable** before copying to HR.

**Why this matters:** Copy-modifying an unvalidated pattern propagates technical debt. If BĐS aggregator has issues, HR will inherit them.

**Recommended Fix:**
- Validate BĐS aggregator in production for 2-4 weeks before copying to HR.
- If issues are found, fix them in BĐS first (don't copy bugs).
- Document BĐS aggregator validation results in feature brief.
- Sequence Epic 11 after BĐS validation is complete.

---

## Triage Table

| Issue | Severity | Evidence | Recommended Fix |
|---|---|---|---|
| TAM/SAM/SOM are speculative | BLOCKER | PRFAQ §Q7 has no methodology; no customer validation | Conduct 10-15 customer interviews; test pricing via landing page; re-calculate with bottom-up methodology |
| ToS review incomplete | BLOCKER | PRFAQ §Q8 assumes "public API = safe"; no actual ToS analysis | BLOCK Epic 11 until ToS review complete for VietnamWorks, TopCV, ITviec |
| NG-1 violation ambiguity | MAJOR | Business model sells access to job data; NG-1 frozen; requires SCP | Raise SCP to clarify if job market research violates NG-1 |
| Defensibility weak | MAJOR | Incumbents could close gap in 3-6 months; no moat articulated | Articulate time-to-market advantage; identify data/network effects; consider partnership |
| VietnamWorks API stability unproven | MAJOR | No official documentation; relies on community projects | Contact VietnamWorks for official docs; implement contract regression tests; add circuit breaker |
| PII risks underestimated | MAJOR | JDs can contain PII; no detection/redaction pipeline | Add PII detection/redaction; define retention policy; conduct risk assessment |
| Vietnamese labor law unclear | MAJOR | No legal counsel review of employment service classification | Obtain legal opinion; add disclaimers if ambiguous; abandon if classified as employment service |
| Why use Nowing vs. VietnamWorks reports? | MAJOR | VietnamWorks already publishes market reports; no gap validation | Interview customers to identify gaps; if small, reconsider vertical |
| Why use Nowing vs. HireX/UpNow/LinkTalent? | MAJOR | They solve matching; Nowing solves research; unclear which customers want | Clarify job-to-be-done; validate willingness to pay for research vs. matching |
| Margin assumptions optimistic | MAJOR | No fixed cost breakdown; 10× discrepancy in cost estimates | Build unit economics model; test rate limits; include anti-bot costs |
| TopCV/ITviec anti-bot underestimated | MAJOR | Dismissed as "warmed browser"; no technical reconnaissance | Conduct reconnaissance; gate P1 on POC; budget for maintenance |
| Strategic ambiguity (pivot vs. vertical) | MAJOR | Beachhead is agent-builder; HR not sequenced; rationale unclear | Clarify strategic rationale; if pivot, raise SCP; if vertical, align with agent-builder rollout |
| BSL 1.1 constraints conflict | MINOR | Selling access to BSL fetchers may violate license | Clarify if Apache-2.0 core provides sufficient value; document license analysis |
| Dev effort underestimated | MINOR | 5-8 days for copy-modify; domain differences significant | Build spike/PoC; include testing/edge cases; update estimate |
| NG-2 ambiguity | MINOR | B2B framing but unclear if consumer features later | Add explicit non-goal for job seekers; document B2B-only positioning |
| Ponytail rule violation risk | MINOR | Copy-modifying unvalidated BĐS pattern | Validate BĐS in production 2-4 weeks; fix issues before copying |

---

## Summary

**Blockers (2):**
1. TAM/SAM/SOM are speculative — no customer validation.
2. ToS review incomplete — assumes "public API = safe".

**Major Issues (10):**
1. NG-1 violation ambiguity (selling research data).
2. Defensibility weak (incumbents can close gap).
3. VietnamWorks API stability unproven.
4. PII risks underestimated.
5. Vietnamese labor law unclear.
6. Why use Nowing vs. VietnamWorks reports?
7. Why use Nowing vs. HireX/UpNow/LinkTalent?
8. Margin assumptions optimistic.
9. TopCV/ITviec anti-bot underestimated.
10. Strategic ambiguity (pivot vs. vertical).

**Minor Issues (4):**
1. BSL 1.1 constraints conflict.
2. Dev effort underestimated.
3. NG-2 ambiguity.
4. Ponytail rule violation risk.

**Recommendation:** Do not approve Epic 11 until blockers are resolved and major issues are addressed. The proposal requires evidence-based market validation, legal review completion, and strategic clarity before proceeding.
