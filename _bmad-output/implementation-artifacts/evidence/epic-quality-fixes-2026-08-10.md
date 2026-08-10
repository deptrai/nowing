# Epic Quality Defect Fixes — Evidence

**Date:** 2026-08-10  
**Target file:** `_bmad-output/planning-artifacts/epics.md`  

## Fixed critical violations

| # | Story | Problem | Fix applied |
|---|---|---|---|
| 1 | `12.6` / `12.9` | `12.6` (Job Market Alerts) depended on later `12.9` (Saved Searches). | Swapped numbering: `12.6` = Saved Searches (P0, must ship first), `12.9` = Job Market Alerts (P1, depends on `12.6`). Updated dependency ordering note and AD-33 note. |
| 2 | `20.1` / `20.4` | `20.1` (Nowing Scraper / `NowingIngestService`) depended on later `20.4` (`ChainLensServiceAuth`). | Reordered Epic 20: `20.1` = Service-to-Service Auth + Cost Ledger Sync, `20.2` = Nowing Scraper + `NowingIngestService`, `20.3` = Gap-Fill Caller, `20.4` = `NowingPrivateProvider`. Updated internal references (`Story 20.4` → `20.1`, `Story 20.1` → `20.2`). |
| 3 | `4.8d` | No formal acceptance criteria. | Replaced the one-line `_AC:` with full G/W/T acceptance criteria plus error-path cases (judge unavailable, malformed JSON, empty/missing dataset) and validation tests. |

## Fixed major issues

| # | Story / area | Problem | Fix applied |
|---|---|---|---|
| 1 | `8.7` | Still referenced renumbered `8.4a` (now `8.8`). | Changed `Dep: 8.4a` → `Dep: 8.8` in `Story 8.7`. |
| 2 | Cross-cutting dependencies | `NowingIngestService`, `ChainLensServiceAuth`, and AD-33 Generic Alert Engine were referenced but not surfaced as hard prerequisites. | Added a `Cross-cutting prerequisite note` in Epic 20 intro and a full `Cross-Cutting Dependency Mapping` table at the end of `epics.md` linking every dependent story to `Story 20.1`, `Story 20.2`, and/or AD-33. |
| 3 | Epic 21 | `PROPOSED` but had detailed stories missing metrics, error paths, and PII/consent gating. | Added a governance-gates callout at the Epic 21 intro listing legal/ToS, vendor contracts, Zalo OA, PII pipeline, and CRM sync as blockers before any Epic 21 story can move to `ready-for-dev`. |

## Re-check results

Scripted checks run on `epics.md`:

- `REPLACEMENT_PLACEHOLDER`: not present.
- Forward `depends on` / `Dep:` references: none point to a later-numbered story.
- `Story 4.8d`: contains a formal `**Acceptance Criteria:**` block.
- `Story 8.7`: no longer references `8.4a`.
- `## Cross-Cutting Dependency Mapping`: present.
- **Remaining gap:** 45 active stories still lack an explicit error-path acceptance-criteria line. These need a domain-specific manual pass rather than boilerplate insertion.

## Remaining work to reach READY

1. Add explicit error-path G/W/T ACs to the 45 active stories identified by the re-check.
2. Close Epic 21 governance gates (legal/ToS, vendor POC, Zalo OA, PII pipeline, CRM sync scope).
3. Re-run the full implementation-readiness workflow and update the readiness report.
