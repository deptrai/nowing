# PRD Status Ratification Amendment — 2026-08-25

**PRD:** `prd-Nowing-2026-07-22/prd.md`  
**Amendment date:** 2026-08-25  
**Author:** bmad-prd pass (readiness closeout)  
**Status:** Ratified — supersedes the 2026-08-24 ratification where conflicting.

## 1. Change summary

This is the second `bmad-prd` ratification pass for `prd-Nowing-2026-07-22/prd.md`. It reconciles PRD status tags with the canonical `sprint-status.yaml` and `epics.md` after the 2026-08-24 implementation readiness closeout. The following changes were made:

- **FR-43–47** promoted from `[READY-FOR-DEV]` / `[IN-PROGRESS]` to `[DONE]` because Stories `12.1–12.5` and `12.4a–e` are `done` in `sprint-status.yaml`, code is merged, and `bmad-code-review` patches were applied.
- **FR-93 / FR-94** revised from `[READY-FOR-DEV]` to `[IN-PROGRESS]` to match the Epic 27 table summary in the PRD, `epic-27: in-progress` in `sprint-status.yaml`, and the actual implementation mix: `27.1a` `done`, `27.1` parent/children `backlog`, `27.2a/27.2b` `ready-for-dev`.
- **Epic 27** in `epics.md` updated from `[ready-for-dev]` to `[in-progress]`, and FR-93/94 references updated.
- The 2026-08-24 reconciliation note in `epics.md` was updated to record that the PRD tags were ratified.

No FR numbering, structure, or acceptance criteria were changed; only status tags and short explanatory notes were updated.

## 2. Status ratification log

| FR | Old status | New status | Rationale / source |
|---|---|---|---|
| FR-43 | `[READY-FOR-DEV]` | `[DONE]` | Story `12.1` `done`; ToS/legal review passed; VietnamWorks public-API spike passed; code merged and `bmad-code-review` passed. |
| FR-44 | `[IN-PROGRESS]` | `[DONE]` | Story `12.2` `done`; Cloudflare/anti-bot POC passed 2026-08-12; code merged and `bmad-code-review` passed. |
| FR-45 | `[READY-FOR-DEV]` | `[DONE]` | Story `12.3` `done`; HTML parsing spike passed; rate-limit + user-agent rotation implemented; code merged and `bmad-code-review` passed. |
| FR-46 | `[IN-PROGRESS]` | `[DONE]` | Stories `12.4a–e` `done`; dependencies FR-43–45, FR-62, AD-34, `NowingIngestService`, and FR-47 all satisfied; code merged and `bmad-code-review` passed. |
| FR-47 | `[READY-FOR-DEV]` | `[DONE]` | Story `12.5` `done`; shared PII redaction pipeline for job data implemented; code merged and `bmad-code-review` passed. |
| FR-49 | `[RE-SCOPED]` | `[RE-SCOPED]` | No change. Feed/crawl infrastructure done; local news index delegated to `chainlens-research`. |
| FR-50 | `[RE-SCOPED]` | `[RE-SCOPED]` | No change. Feed/crawl infrastructure done; local financial index delegated to `chainlens-research`. |
| FR-51 | `[RE-SCOPED]` | `[RE-SCOPED]` | No change. Feed/crawl partially done; local company index delegated to `chainlens-research`. |
| FR-52 | `[RE-SCOPED]` | `[RE-SCOPED]` | No change. Feed/crawl partially done; local product index delegated to `chainlens-research`. |
| FR-56 | `[DONE]` | `[DONE]` | No change. Epic 18 / Story `18.1` done; public agent-chat endpoints and PAT auth implemented. |
| FR-57 | `[DONE]` | `[DONE]` | No change. Epic 18 / Story `18.3` done; `agent_configs` registry implemented. |
| FR-63 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.1` done; Epic 21 overall in-progress. |
| FR-64 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.2` done; Epic 21 overall in-progress. |
| FR-65 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.3` done; 3-tier phone waterfall and PII vault in place; Epic 21 overall in-progress. |
| FR-66 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.4` done; outbound sequence engine implemented; Epic 21 overall in-progress. |
| FR-67 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.5` done; CRM write-back implemented; Epic 21 overall in-progress. |
| FR-68 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.6` done; Zalo OA integration implemented; Epic 21 overall in-progress. |
| FR-69 | `[IN-PROGRESS]` | `[IN-PROGRESS]` | No change. Story `21.7` done; outcome-based pricing ledger implemented; Epic 21 overall in-progress. |
| FR-93 | `[READY-FOR-DEV]` | `[IN-PROGRESS]` | Epic 27 / Story `27.1a` `done`; Story `27.1` parent/tracking `backlog` (`27.1b/c/d` `backlog`); `27.2a/27.2b` `ready-for-dev`. Matches `epic-27: in-progress` in `sprint-status.yaml`. |
| FR-94 | `[READY-FOR-DEV]` | `[IN-PROGRESS]` | Epic 27 / Stories `27.2a/27.2b` `ready-for-dev`; Mark Tool `27.1d` and container deploy `27.1c` `backlog`; Story `27.1` parent/tracking `backlog`. Matches `epic-27: in-progress`. |

## 3. Sources

- `prd-Nowing-2026-07-22/prd.md` (FR-43–47, FR-93/94 status lines)
- `epics.md` (Epic 12, Epic 27, FR inventory)
- `sprint-status.yaml` (Stories 12.1–12.5, 12.4a–e, Epic 27 statuses)
- `implementation-readiness-report-2026-08-24.md` (Section 7.1, issue #1)
- `AMENDMENT-PRD-Status-Ratification-2026-08-24.md` (superseded for FR-43–47 / FR-93/94; retained for FR-49–52, 56–62, 63–69 history)

## 4. Decision workspace

The `bmad-prd` working memlog for this pass is kept at:
`_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/.bmad-prd-update-2026-08-24/.memlog.md`.
