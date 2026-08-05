---
title: ToS & Legal Review Log — Epic 12 HR Vertical
project: Nowing
date: 2026-08-05
status: open
sources:
  - VietnamWorks
  - TopCV
  - ITviec
---

# ToS & Legal Review Log — Epic 12 HR Vertical

**Status:** OPEN  
**Scope:** VietnamWorks, TopCV, ITviec  
**Owner:** Founder + Legal  
**Due:** Before any Epic 12 scraper code is merged.

---

## 1. ToS Review

| Source | URL | Allows automated access? | Allows commercial use? | Notes |
|---|---|---|---|---|
| VietnamWorks | https://www.vietnamworks.com | ⬜ | ⬜ | Public API `ms.vietnamworks.com` observed; ToS pending. |
| TopCV | https://www.topcv.vn | ⬜ | ⬜ | Cloudflare challenge observed; ToS pending. |
| ITviec | https://itviec.com | ⬜ | ⬜ | Server-rendered HTML; ToS pending. |

## 2. Legal Counsel Opinion

| Question | Status | Answer |
|---|---|---|
| Does Nowing qualify as an "employment service provider" / "môi giới việc làm" under Vietnamese law? | ⬜ | _Pending_ |
| Does the pilot require a labor brokerage license? | ⬜ | _Pending_ |
| Is the research/memory-layer positioning sufficient to avoid intermediary classification? | ⬜ | _Pending_ |

## 3. Messaging Guidelines

- Nowing is a **research/memory layer**.
- Nowing is **not** a job board, ATS, or employment intermediary.
- No apply/shortlist/candidate-matching features.

## 4. Decisions

- If a source is blocked: disable gracefully (`degraded=true`), remove from default `sources`, do not bypass.

## 5. Next Steps

1. Review each site's ToS.
2. Obtain written legal counsel opinion.
3. Update this log with decisions.
4. Update `epics.md`, `sprint-status.yaml`, and `ARCHITECTURE-SPINE.md` if any source is blocked.
