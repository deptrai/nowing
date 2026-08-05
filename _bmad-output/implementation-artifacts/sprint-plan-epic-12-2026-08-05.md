---
title: Sprint Plan — Epic 12 (HR/Recruitment Vertical)
date: 2026-08-05
status: draft
---

# Sprint Plan — Epic 12: HR/Recruitment Vertical (Vietnam)

**Sprint goal:** Hoàn thành implementation skeleton, giải quyết 3 hard gates, và bắt đầu dev các story không bị block.

---

## Current Status (from sprint-status.yaml)

| Story | Title | Status | Blocker | Dev-days |
|---|---|---|---|---|
| 12.0 | ToS & Legal Review | `in-progress` | Hard gate | 2–3 |
| 12.1 | VietnamWorks Scraper | `ready-for-dev` | 12.0 ToS | 3–4 |
| 12.2 | TopCV Scraper | `blocked` | Anti-bot POC | 5–7 |
| 12.3 | ITviec Scraper | `ready-for-dev` | 12.0 ToS | 3–4 |
| 12.4 | Vietnam Job Aggregator | `ready-for-dev` | None (skeleton ready) | 4–5 |
| 12.5 | PII Redaction for Job Data | `ready-for-dev` | None (skeleton ready) | 2–3 |

**Epic 12 status:** `in-progress`

---

## Sprint Goals

1. **Close hard gates:**
   - 12.0 ToS & legal review (Founder + Legal)
   - TopCV anti-bot POC (Dev + Ops) — go/no-go for 12.2

2. **Deliver dev-ready stories:**
   - 12.4 Vietnam Job Aggregator (not blocked by ToS)
   - 12.5 PII Redaction for Job Data (not blocked by ToS)

3. **Prepare gated stories:**
   - 12.1 VietnamWorks Scraper (dev starts immediately after 12.0)
   - 12.3 ITviec Scraper (dev starts immediately after 12.0)

4. **Defer if blocked:**
   - 12.2 TopCV Scraper remains blocked until anti-bot POC passes.

---

## Proposed Sprint Backlog (3-week sprint)

### Week 1: Gates + Foundation

| Day | Story | Task |
|---|---|---|
| 1–2 | 12.0 | ToS review for VietnamWorks, TopCV, ITviec; draft decision log |
| 3 | 12.0 | Legal counsel opinion on "employment service provider" classification |
| 4 | 12.5 | Wire `redact_job_pii` into `MemoryExtractionService`; unit tests |
| 5 | 12.4 | Complete `jobs_aggregator` schema + orchestrator fan-out |

### Week 2: Aggregator + Unblocked Scrapers

| Day | Story | Task |
|---|---|---|
| 6–7 | 12.4 | Implement normalize, dedupe, salary conflict scoring |
| 8 | 12.4 | Location post-filter, cost caps, degraded handling |
| 9 | 12.4 | REST/MCP/agent wiring; integration tests |
| 10 | 12.1 | Implement VietnamWorks API fetch + parser (if 12.0 done) |
| 11 | 12.3 | Implement ITviec HTML parser (if 12.0 done) |

### Week 3: Anti-bot POC + Polish

| Day | Story | Task |
|---|---|---|
| 12 | 12.2 | TopCV anti-bot POC with `WEB_CRAWL` + captcha billing |
| 13 | 12.2 | Document cost-per-page; go/no-go decision |
| 14 | 12.1 / 12.3 | VietnamWorks/ITviec golden fixtures + regression tests |
| 15 | 12.4 / 12.5 | End-to-end aggregate + PII pipeline test |

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| ToS blocks a source | High | Disable source, fallback to 2-source aggregate, update `sources` default |
| Legal says Nowing = employment intermediary | Critical | Pivot messaging, remove apply/contact features, re-scope pilot |
| TopCV anti-bot cost > $0.05/page | High | Disable TopCV, pilot with VietnamWorks + ITviec only |
| VietnamWorks rate-limit in prod | Medium | Add backoff, circuit-breaker, production stress test |
| PII redaction misses edge cases | Medium | Manual QA on 20 samples per source before memory extraction |

---

## Definition of Done for This Sprint

- [ ] 12.0 ToS & legal memo merged to `_bmad-output/planning-artifacts/legal/`.
- [ ] 12.4 `vn_jobs.aggregate` returns normalized, deduplicated, degraded-aware results.
- [ ] 12.5 PII redaction runs before LLM prompt; unit tests pass for all 3 sources.
- [ ] 12.1 VietnamWorks scraper implemented and regression-tested (if 12.0 clears).
- [ ] 12.3 ITviec scraper implemented and regression-tested (if 12.0 clears).
- [ ] 12.2 TopCV anti-bot POC report merged with go/no-go decision.
- [ ] `sprint-status.yaml` updated with actual story statuses.

---

## Next Sprint Trigger

Sprint kế tiếp bắt đầu khi:
- 12.0 + 12.2 gates rõ ràng, **và**
- 12.4 + 12.5 hoàn thành, **và**
- 12.1/12.3 đang `in-progress` hoặc `done`.

---

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-05.md" />
