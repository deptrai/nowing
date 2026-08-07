# Implementation Readiness Assessment Report

**Date:** 2026-08-07 (correct-course supersedes 2026-08-08 18/18 claim)
**Project:** Nowing
**Assessor:** Winston (Architect) correct-course after review of commit `24ea83b`

---

## Scope Split (mandatory)

| Epic | Scope | Status |
|------|-------|--------|
| **Epic 13** | FR-48 canonical entity persistence, lineage, unified search (13.1–13.3 / 13.2a–e) | **In progress / review** — P0 code-review findings still open |
| **Epic 18** | FR-56/FR-57 public agent-chat, Agent Registry, vertical `client_id` tenancy, cost attribution, rate limits (18.1–18.8) | **Backlog** — blocked on AD-29/30/31 + E13 P0 closure |

Do **not** treat public chat as part of Epic 13 readiness.

---

## Document Discovery

| Doc | Status |
|-----|--------|
| PRD | Present — FR-56/57/NFR-MULTI-1 retargeted to Epic 18 |
| Architecture Spine | AD-13 amended; **AD-29/30/31 added** (2026-08-07) |
| Epics | Epic 13 FR-48-only; Epic 18 holds former 13.4–13.11 |
| UX agent registry | Present; story refs → 18.3/18.4 |
| Sprint status | E13 stories in `review`; E18 backlog |

---

## Epic 13 Readiness (canonical only)

### Open blockers (from validation_reports)

| Story | Verdict | P0 themes |
|-------|---------|-----------|
| 13.1 | CHANGES_REQUESTED | Celery RLS context, version CAS, outbox/workspace contract |
| 13.2 | CHANGES_REQUESTED | outbox worker missing, CAS WHERE bug, source_record_id collision, phone_key hashing |
| 13.3 | CHANGES_REQUESTED | dead `view_sources` href, FTS config mismatch |

### Score (Epic 13 only)

| Dimension | Score | Max | Notes |
|-----------|-------|-----|-------|
| Document discovery | 4 | 4 | OK |
| FR-48 coverage | 5 | 5 | 13.1–13.3 cover FR-48 |
| UX canonical | 4 | 4 | contract exists |
| Implementation quality gate | **1** | 5 | P0 reviews open |
| **Total** | **14** | **18** | **NOT READY to call done** |

**Overall Epic 13:** ⚠️ **CONTINUE IMPLEMENTATION / FIX P0** — not "READY to close".

---

## Epic 18 Readiness (vertical client platform)

### Entry criteria (all required)

1. [ ] Epic 13 P0 code-review items closed or explicitly waived by owner
2. [ ] AD-29, AD-30, AD-31 accepted (now drafted on Spine — need human confirm)
3. [ ] PAT scope model written (workspace / client / agent)
4. [ ] Composite RLS test plan (workspace + client, pool reuse, fail closed)
5. [ ] Threat model: prompt injection, tool exfiltration, metadata abuse

### Score (Epic 18)

| Dimension | Score | Max | Notes |
|-----------|-------|-----|-------|
| Product need | 4 | 4 | BDS vertical client is real |
| Architecture decisions | 3 | 5 | ADs drafted; tenancy details still open questions |
| Story quality | 3 | 5 | ACs exist; security ACs still thin |
| Effort honesty | 2 | 5 | Prior 4.5-day estimate rejected |
| **Total** | **12** | **19** | **NOT READY to start coding** |

**Overall Epic 18:** 🛑 **NOT READY** until entry criteria pass.

---

## Prior Overclaim (retracted)

The 2026-08-08 report claimed **18/18 READY** and **Blockers: None** while:

- binding public chat to AD-27/AD-28 (incorrect)
- marking 13.1–13.3 done despite CHANGES_REQUESTED
- omitting Spine amendments
- estimating ~4.5 days for a multi-tenant public API

Those claims are **retracted** by this correct-course.

---

## Recommended Next Steps

1. **Close Epic 13 P0 reviews** (13.1 → 13.2 → 13.3) before any Epic 18 code.
2. **Human-accept AD-29/30/31** (or amend further).
3. Only then create story files for 18.1–18.8 and implement in order:
   `18.3 → 18.2 → 18.4 → 18.1 → 18.5 → 18.6 → 18.7 → 18.8`
4. Keep Epics 14–17 Phase 2 unless already in flight; do not let them silently outrank E13 P0 fixes.

---

**Report status:** Correct-course assessment — replaces readiness claims in commit `24ea83b`.
