---
title: "Sprint Change Proposal — Epic 18: Vertical Client Platform (correct-course)"
project: Nowing
date: 2026-08-07
status: approved-correct-course
author: Winston (Architect)
supersedes: sprint-change-proposal-2026-08-08.md (Epic 13 expansion draft)
scope: Split public agent-chat out of Epic 13 into Epic 18; add AD-29/30/31
---

# Sprint Change Proposal — Correct-Course

## Why

The 2026-08-08 draft expanded Epic 13 with public agent-chat stories and claimed implementation readiness. Architecture review found:

1. Epic identity collision (canonical storage vs public multi-tenant API)
2. Incorrect AD-27/AD-28 bindings
3. Missing vertical `client_id` tenancy design
4. `done` status conflicting with P0 code reviews on 13.1–13.3
5. Unrealistic ~4.5 day effort and 18/18 readiness score

## Decision

| Before | After |
|--------|-------|
| Stories 13.4–13.11 inside Epic 13 | **Epic 18** stories 18.1–18.8 |
| Bound to AD-27/AD-28 | **AD-29, AD-30, AD-31** (+ AD-13 linkage only) |
| FR-48 + FR-56/57 mixed | FR-48 = E13; FR-56/57/NFR-MULTI-1 = E18 |
| 13.1–13.3 `done` | **`review`** until P0 closed |
| Architecture silent | Spine amended |

## Artifact updates (this correct-course)

- `epics.md` — Epic 18 section; E13 FR list cleaned
- `ARCHITECTURE-SPINE.md` — AD-13 amend; AD-29/30/31
- `prd.md` — FR-56/57 point at Epic 18; NFR-MULTI-1 notes AD-31
- `sprint-status.yaml` — E13 review; E18 backlog; indent fixed
- `ux-contract-agent-registry.md` — 18.x + AD-30 refs
- readiness + vision reports — overclaims retracted
- this SCP — supersedes prior expansion packaging

## Entry criteria before Epic 18 code

1. Close or waive E13 P0 code-review findings
2. Human accept AD-29/30/31
3. PAT scope + composite RLS test plan
4. Short threat model (prompt injection, tool exfil, metadata abuse)

## Effort

Multi-week platform work. Prior 4.5-day estimate is **rejected**.

## Proposal Status

**Approved correct-course** — docs landed; implementation of Epic 18 still gated.
