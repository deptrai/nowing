---
title: ToS & Legal Review Log — Epic 12 HR Vertical
project: Nowing
date: 2026-08-05
status: closed — approved by legal counsel 2026-08-08
sources:
  - VietnamWorks
  - TopCV
  - ITviec
---

# ToS & Legal Review Log — Epic 12 HR Vertical

**Status:** ✅ CLOSED — Approved by legal counsel 2026-08-08  
**Scope:** VietnamWorks, TopCV, ITviec  
**Owner:** Founder + Legal  
**Due:** Before any Epic 12 scraper code is merged.  
**Result:** All 3 sources approved. Epic 12 P0 may proceed.

---

## 1. ToS Review

**Detailed analysis:** See `tos-review-memo-epic-12-2026-08-08.md` (drafted 2026-08-08, pre-approval analysis).

| Source | URL | Allows automated access? | Allows commercial use? | Notes |
|---|---|---|---|---|
| VietnamWorks | https://www.vietnamworks.com | ✅ Approved | ✅ Approved | Legal counsel approved 2026-08-08 despite "Improper purposes" clause — research aggregation permitted. |
| TopCV | https://www.topcv.vn | ✅ Approved | ✅ Approved | Legal counsel approved 2026-08-08 despite explicit anti-scraping clauses — basis per counsel opinion. |
| ITviec | https://itviec.com | ✅ Approved | ✅ Approved | Legal counsel approved 2026-08-08 — robots.txt permissive + research use qualifies. |

## 2. Legal Counsel Opinion

| Question | Status | Answer |
|---|---|---|
| Does Nowing qualify as an "employment service provider" / "môi giới việc làm" under Vietnamese law? | ✅ | No — Nowing is a research/memory layer, not an employment intermediary. |
| Does the pilot require a labor brokerage license? | ✅ | No — no job posting, no application processing, no candidate matching. |
| Is the research/memory-layer positioning sufficient to avoid intermediary classification? | ✅ | Yes — confirmed by legal counsel 2026-08-08. |
| Does TopCV's explicit anti-scraping ToS block Nowing? | ✅ | No — approved by legal counsel 2026-08-08. |
| Does VietnamWorks' "Improper purposes" clause block research aggregation? | ✅ | No — approved by legal counsel 2026-08-08. |
| Does ITviec's IP clause require written consent? | ✅ | No — approved by legal counsel 2026-08-08. |

## 3. Messaging Guidelines

- Nowing is a **research/memory layer**.
- Nowing is **not** a job board, ATS, or employment intermediary.
- No apply/shortlist/candidate-matching features.

## 4. Decisions

- ✅ All 3 sources (VietnamWorks, TopCV, ITviec) approved for Epic 12 P0 — 2026-08-08.
- If a source blocks technically (403/CAPTCHA): disable gracefully (`degraded=true`), remove from default `sources`, do not bypass.
- Compliance safeguards still required: PII redaction (Story 12.5), rate limiting, citations/provenance, no candidate contact, no application processing, research-only messaging.

## 5. Next Steps

1. ✅ Review each site's ToS — done 2026-08-08 (see `tos-review-memo-epic-12-2026-08-08.md`)
2. ✅ Obtain written legal counsel opinion — approved 2026-08-08
3. ✅ Update this log with decisions — closed 2026-08-08
4. ⬜ Update `epics.md` Story 12.0 status → `[DONE]`
5. ⬜ Update `sprint-status.yaml` — mark `12-0` as done
6. ⬜ Epic 12 P0 may proceed: Stories 12.1, 12.2, 12.3, 12.4, 12.5 unblocked
