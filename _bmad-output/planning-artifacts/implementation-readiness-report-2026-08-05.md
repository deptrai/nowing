---
title: Implementation Readiness Assessment Report
project: Nowing
scope: Epic 12 — HR/Recruitment Vertical (Vietnam)
date: 2026-08-05
assessor: Mary (Business Analyst)
status: conditional-pass
effort_estimate: 18–24 dev-days
stepsCompleted:
  - document-discovery
  - prd-analysis
  - architecture-analysis
  - epics-stories-analysis
  - traceability-check
  - gap-identification
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05  
**Project:** Nowing  
**Scope:** Epic 12 — HR/Recruitment Vertical (Vietnam) — VietnamWorks + TopCV + ITviec pilot  
**Assessor:** Mary  
**Status:** **CONDITIONAL PASS**  
**Effort Estimate:** 18–24 dev-days

---

## 1. Document Inventory

| Document | Path | Status |
|---|---|---|
| PRD | `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` | ✅ Updated 2026-08-05 |
| Architecture Spine | `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | ✅ Updated 2026-08-05 |
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | ✅ Updated 2026-08-05 |
| PRFAQ | `_bmad-output/planning-artifacts/prfaq-hr-vertical-vietnam-2026-08-05.md` | ✅ Final |
| Feature Brief | `_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md` | ✅ Final |
| Pilot Plan C | `_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md` | ✅ Final |
| VietnamWorks API Spike | `_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md` | ✅ Done |
| TopCV/ITviec Spike | `_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md` | ✅ Done |
| Market Validation Plan | `_bmad-output/planning-artifacts/research/market-validation-hr-vertical-2026-08-05.md` | ✅ Final |

No duplicate documents found. No UX design required (reuse Nowing chat/agent/capability surfaces).

---

## 2. PRD Coverage

### FR Coverage

| FR | Title | PRD § | Epic | Story | Architecture |
|---|---|---|---|---|---|
| FR-43 | VietnamWorks scraper | §4.2 | E12 | 12.1 | AD-22 |
| FR-44 | TopCV scraper | §4.2 | E12 | 12.2 | AD-23 |
| FR-45 | ITviec scraper | §4.2 | E12 | 12.3 | AD-23 |
| FR-46 | `vn_jobs.aggregate` | §4.2 | E12 | 12.4 | AD-24 |
| FR-47 | PII redaction for job data | §4.2 | E12 | 12.5 | AD-25 |

### NFR / OQ / SM Coverage

| ID | Title | PRD § | Epic | Architecture |
|---|---|---|---|---|
| NFR-11 | Scraping compliance & anti-bot resilience | §5 | E12 | AD-26 |
| OQ-8 | HR/Recruitment Vertical in Vietnam | §8 | E12 | AD-26 |
| SM-12 | HR pilot metrics | §7 | E12 | — |

### Open Questions (OQ-8) Status

1. **ToS VietnamWorks/TopCV/ITviec** — ❌ Open, hard gate.
2. **Employment service provider classification** — ❌ Open, hard gate.
3. **TopCV anti-bot POC** — ❌ Open, hard gate.
4. **ITviec salary hidden** — ⚠️ Known risk, parse from title / low-confidence.
5. **Willingness-to-pay** — ⚠️ Validate during 8-week pilot.
6. **PII pipeline strength** — ⚠️ Validate with 10–20 samples per source.

---

## 3. Epic/Story Quality

### Epic 12 Breakdown

| Story | Title | AC Count | Risks | Status |
|---|---|---|---|---|
| 12.0 | ToS & Legal Review | 4 | Legal/ToS gates | ready-for-dev (hard gate) |
| 12.1 | VietnamWorks Scraper | 5 | ToS, rate-limit in prod | ready-for-dev after 12.0 |
| 12.2 | TopCV Scraper | 4 | Anti-bot Cloudflare challenge | blocked until POC |
| 12.3 | ITviec Scraper | 5 | Salary hidden, HTML drift | ready-for-dev after 12.0 |
| 12.4 | Vietnam Job Aggregator | 7 | Cross-source dedupe, scoring | ready-for-dev |
| 12.5 | PII Redaction | 4 | Coverage ≥95% needs samples | ready-for-dev |

### Story Quality Checks

- ✅ Each story has clear actor + want + so-that.
- ✅ Each story has acceptance criteria with Given/When/Then.
- ✅ Stories are independent enough for parallel work (12.1/12.3/12.5 can start before 12.2).
- ✅ No forward dependencies within Epic 12 that prevent sprint planning.
- ✅ All stories map to at least one FR and one AD.

### Issue: 12.2 TopCV Anti-Bot

- **Severity:** BLOCKER for P0 if POC fails.
- **Mitigation:** If POC fails, disable TopCV gracefully and run pilot with 2 sources (VietnamWorks + ITviec). This is acceptable per go/no-go criteria.

---

## 4. Architecture Alignment

### AD Coverage

| AD | Binds | Prevents | Status |
|---|---|---|---|
| AD-22 | VietnamWorks scraper | PII leak, HTML-first design | ✅ Clear |
| AD-23 | TopCV/ITviec scrapers | Anti-bot divergence, CAPTCHA token storage | ✅ Clear |
| AD-24 | `vn_jobs.aggregate` | Duplicating BĐS logic, source leakage | ✅ Clear |
| AD-25 | PII redaction | PII in Memory, PII in logs | ✅ Clear |
| AD-26 | ToS/legal gates | ToS violation, employment-service classification | ✅ Clear |

### Existing ADs Reused

| AD | Reused For |
|---|---|
| AD-3 | Capability self-registration for 3 scrapers + aggregator |
| AD-16 | BSL 1.1 boundary for `app/proprietary/` fetchers |
| AD-19 | Anti-bot stack for TopCV |
| AD-8 | Billing units `VIETNAMWORKS_JOB`, `TOPCV_JOB`, `ITVIEC_JOB`, `VN_JOBS_AGGREGATE_QUERY` — added to `BillingUnit` and billing maps |
| AD-8.1 | Config constants for VietnamWorks/TopCV/ITviec per-item rates and `VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY` — added to `app/config/__init__.py` |
| AD-11.1 | Memory provenance for aggregated job listings |

### No Architecture Conflicts

- No contradiction with parent ADs.
- No new license boundary introduced (still BSL 1.1 fetcher + Apache-2.0 capability).
- No new persistence layer required (reuse `Memory` + `TokenUsage`).

---

## 5. Traceability

### Bidirectional Trace

- PRD FR-43 ↔ Epic 12.1 Story 12.1 ↔ AD-22
- PRD FR-44 ↔ Epic 12.1 Story 12.2 ↔ AD-23
- PRD FR-45 ↔ Epic 12.1 Story 12.3 ↔ AD-23
- PRD FR-46 ↔ Epic 12.1 Story 12.4 ↔ AD-24
- PRD FR-47 ↔ Epic 12.1 Story 12.5 ↔ AD-25
- PRD NFR-11 ↔ Epic 12 P0 ↔ AD-26
- PRD OQ-8 ↔ Epic 12 P0 ↔ AD-26
- PRD SM-12 ↔ Epic 12 P0

### No Orphan Requirements

- All 5 new FRs have stories.
- All 5 new FRs have architecture decisions.
- NFR-11 and OQ-8 are addressed by AD-26.

---

## 6. Gaps & Risks

### Critical (Must Resolve Before Build)

| # | Gap | Owner | Resolution |
|---|---|---|---|
| 1 | **ToS review for VietnamWorks, TopCV, ITviec** | Legal/PO | Complete review and document in `_bmad-output/planning-artifacts/legal/` |
| 2 | **Legal counsel opinion on employment service provider** | Legal | Confirm pilot does not require môi giới việc làm license |
| 3 | **TopCV anti-bot POC** | Dev + Ops | Pass headless/residential proxy/bypass service POC |

### Major (Resolve During Pilot)

| # | Gap | Owner | Resolution |
|---|---|---|---|
| 4 | ITviec salary hidden | Dev | Parse from title or mark low-confidence; evaluate login flow |
| 5 | PII detection coverage ≥95% | Dev | Test 10–20 samples per source |
| 6 | Willingness-to-pay validation | PM | 10 customer interviews during pilot |
| 7 | Rate-limit re-test from production network | Dev | Run production-network stress test for VietnamWorks |

### Minor

| # | Gap | Resolution |
|---|---|---|
| 8 | Billing unit pricing not finalized | Baseline during pilot, decide at go/no-go |
| 9 | `vn_jobs.aggregate` config constants (query micros) | Add to `app/config/__init__.py` when implementing |

---

## 7. Recommendation

**CONDITIONAL PASS — Ready to proceed to Sprint Planning if the 3 critical gates are resolved:**

1. ToS review complete for all 3 sources.
2. Legal counsel opinion confirms no employment service provider license required.
3. TopCV anti-bot POC passes or is explicitly disabled with graceful degradation.

**If critical gates are not resolved:**
- Do **not** merge TopCV code.
- VietnamWorks and ITviec can still be built and piloted as 2-source `vn_jobs.aggregate`.

**Next step:** `bmad-sprint-planning` (after critical gates) or `bmad-dev-story` for 12.1/12.3/12.5 while gates are in progress.

---

## 8. Implementation Skeleton (2026-08-05)

An implementation skeleton has been created to make the gaps concrete and allow incremental dev once hard gates clear:

- `app/capabilities/{vietnamworks,topcv,itviec}/scrape/` — capability packages with `BillingUnit` registration.
- `app/capabilities/vn_jobs/aggregate/` — aggregator capability wired to `BillingUnit.VN_JOBS_AGGREGATE_QUERY`.
- `app/services/jobs_aggregator/` — copy-modify skeleton (`schemas.py`, `orchestrator.py`, `normalize.py`, `dedupe.py`).
- `app/services/pii/redact.py` — Vietnamese phone/email/name redaction with unit tests.
- `app/proprietary/platforms/{vietnamworks,topcv,itviec}/` — BSL 1.1 fetcher stubs that degrade until gates clear.
- `app/agents/chat/multi_agent_chat/subagents/builtins/vn_jobs/` — subagent package exposing per-source and aggregate verbs.
- `nowing_mcp/mcp_server/features/scrapers/platforms/{vietnamworks,topcv,itviec,vn_jobs}.py` — MCP tools and selfcheck updated.
- `app/capabilities/core/types.py`, `app/capabilities/core/billing.py`, `app/config/__init__.py` — billing units, rates, gates, and config constants.
- `app/routes/__init__.py`, `app/mcp_tools.py` — registration and catalog wiring.
- `app/observability/metrics.py` — new counters for `vn_jobs` source blocks, PII detection, and aggregate degradation.
- Unit tests: 21 tests pass for registry, billing, normalize, dedupe, and PII.
- MCP selfcheck: 48 tools registered and well-formed.

The skeleton returns `degraded=true` with `degradation_reason` for every source until ToS/legal/anti-bot gates are resolved, so it is safe to keep in source control.

---

## 9. References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
