---
title: Plan C — HR Vertical Pilot with 3 Sources (VietnamWorks + TopCV + ITviec)
project: Nowing
date: 2026-08-05
author: Mary (Business Analyst) for Luisphan
status: proposal
---

# Plan C: HR Vertical Pilot — 3 Sources in P0

## Decision

Chạy pilot 8 tuần với **cả 3 nguồn trong P0**: VietnamWorks, TopCV, ITviec. Multi-source là cốt lõi của value proposition (cross-platform research, citations, salary conflict detection).

## Why 3 Sources in P0

- **Giá trị cốt lõi nằm ở cross-platform aggregation**: so sánh lương, phát hiện trùng lặp, tính confidence score.
- **VietnamWorks public API đã ổn định**: 200 OK, no auth, `hitsPerPage` max 100, no CAPTCHA, rate limit OK in short test.
- **ITviec HTML dễ parse**: server-rendered, selectors rõ ràng, no Cloudflare challenge.
- **TopCV cần anti-bot POC**: đã gặp Cloudflare "Just a moment..." challenge. Cần headless browser/residential proxy/bypass service POC trước build.

## Hard Gates Before Build

1. **ToS review** cho VietnamWorks, TopCV, ITviec.
2. **Anti-bot POC** cho TopCV (và fallback ITviec nếu bị bật Cloudflare).
3. **Legal counsel opinion** về employment service provider classification.
4. **SCP** về NG-1 ambiguity.

## P0 Scope (Plan C)

| Story | Description | Effort (days) |
|---|---|---|
| 11.1 | VietnamWorks scraper (public API) | 3–4 |
| 11.2 | TopCV scraper (HTML + anti-bot) | 5–7 |
| 11.3 | ITviec scraper (HTML) | 3–4 |
| 11.4 | PII detection & redaction | 2–3 |
| 11.5 | `vn_jobs.aggregate` (3 sources) | 4–5 |
| 11.6 | MCP, billing, capability wiring | 1–2 |
| | **Total P0 estimate** | **18–24 dev-days** |

## Timeline

| Week | Activity |
|---|---|
| W1 | ToS review; anti-bot POC TopCV; customer discovery interviews start |
| W2 | Anti-bot POC result; legal counsel; SCP NG-1; VietnamWorks scraper build |
| W3 | TopCV/ITviec scraper build; PII redaction; aggregator build |
| W4 | Integration tests; MCP/billing; beta setup |
| W5–W8 | Pilot beta (20–50 workspaces); usage tracking; feedback |
| W9 | Go/No-Go review |

## Key Risks

1. **TopCV anti-bot POC fails** → TopCV bị disable gracefully, pilot chạy 2 nguồn.
2. **ITviec salary hidden** → mark salary low-confidence, parse from title khi có thể.
3. **ToS cấm scraping** → no-go cho nguồn đó.
4. **Employment service provider classification** → no-go toàn bộ pilot.
5. **Effort 24 dev-days** vượt quá 3 tuần → cần parallel work hoặc cắt scope.

## Go/No-Go Criteria

**Go:**
- ≥10 workspaces active ≥3 days/week.
- ≥100 aggregate queries trong 8 tuần.
- ToS cả 3 nguồn cho phép (hoặc source bị disable gracefully).
- Anti-bot POC pass cho TopCV hoặc TopCV bị disable.
- Cost/query ≤$0.10.
- ≥3/10 interviewees willing to pay ≥$0.05/query.

**No-go:**
- <5 workspaces active.
- ToS/legal blocker.
- TopCV anti-bot không pass và không thể disable.
- Cost/query >$0.15 hoặc no willingness-to-pay.

## Files

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> — PRD with FR-43..47, NFR-11, OQ-8, SM-12.
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> — Epic 12 breakdown.
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prfaq-hr-vertical-vietnam-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-vietnamworks-api-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-spike-topcv-itviec-2026-08-05.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/market-validation-hr-vertical-2026-08-05.md" />
