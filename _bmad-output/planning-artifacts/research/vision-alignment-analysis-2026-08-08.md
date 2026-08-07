# Nowing — Vision Alignment Analysis

**Analyst:** Mary (Business Analyst) + Winston correct-course
**Date:** 2026-08-07
**Scope:** Active FRs + epic priority after Epic 18 split

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Core vision (Data→Entity→Knowledge→Memory) | Strong — canonical path is the right completion move |
| Epic 13 (canonical) | Necessary; **implementation not closed** (P0 reviews open) |
| Epic 18 (vertical client platform) | Valid product expansion; **architecture incomplete until AD-29/30/31 accepted** |
| Epics 14–17 | Phase 2 unless already shipping |
| Epic 12 | Blocked on ToS/legal (12.0) |

**Verdict:** Vision direction is sound. Prior "100% aligned / ready to implement everything" packaging was overstated. Alignment ≠ implementation readiness.

---

## Fixes Applied (2026-08-07 correct-course)

| # | Issue | Action | Status |
|---|-------|--------|--------|
| 1 | Public chat hijacked Epic 13 | Split to **Epic 18** | ✅ |
| 2 | AD-27/28 mis-bound | AD-29/30/31 + AD-13 amend | ✅ |
| 3 | 13.1–13.3 marked done with P0 open | sprint-status → `review` | ✅ |
| 4 | Readiness 18/18 | Retracted; dual scores | ✅ |
| 5 | FR-53/55 duplicates | Remain covered-by-existing | ✅ |
| 6 | FR-54 | Remain deferred (ChainLens) | ✅ |
| 7 | E12 ToS | Blocker note retained | ✅ |

---

## Priority

| Priority | Epic | Rationale |
|----------|------|-----------|
| **P0** | Epic 13 close-out (fix P0 reviews) | Canonical platform substrate |
| **P0 design** | AD-29/30/31 acceptance | Unlock Epic 18 safely |
| **P1** | Epic 18 implementation | First vertical client revenue path |
| **P1 gated** | Epic 12 | After ToS clearance |
| **P2** | Epics 14–17 | After platform hardening |
| **Defer** | FR-54 | ChainLens covers web search intent |

---

## Risks

1. **Scope bloat** if E14–17 and E18 run while E13 P0 remains open
2. **Tenant model mistakes** if `client_id` ships without AD-31
3. **False "done"** signals from docs-only readiness scores

---

## Three Transformations

| Transformation | Status |
|---------------|--------|
| Data → Entity | Strong (scrapers + canonical work in flight) |
| Entity → Knowledge | Depends on finishing E13 search/persistence P0s |
| Knowledge → Memory | Core differentiator built; E18 must not puncture isolation |

---

**Vision alignment:** Directionally strong.
**Implementation readiness:** Not 100%. Track E13 P0 and E18 entry criteria separately.
