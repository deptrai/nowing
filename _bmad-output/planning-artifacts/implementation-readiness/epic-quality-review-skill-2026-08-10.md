# Epic / Story Quality Review — `epics.md`

**Review date:** 2026-08-10  
**Source:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md`  
**Reviewer:** lazy-senior-dev quality pass

---

## Executive Summary

| Metric | Value |
| --- | --- |
| Distinct epics reviewed | 20 (Epics 1–18, 20, 21; Epic 19 omitted, Epic 13 archived) |
| Epic heading sections | 32 (overview + detailed + extended sections) |
| Story-level sections reviewed | 108 (102 main stories + 6 follow-up/tech-debt items) |
| Active `ready-for-dev` / P0 / P1 / P2 stories | 50 |
| Active stories missing explicit error-path ACs | 27 |
| **Critical violations** | **3** |
| **Major issues** | **7** |
| **Minor concerns** | **6** |

**Bottom line:** The backlog is generally well-structured and user-value oriented, but it contains **two active forward dependencies that make stories unimplementable as numbered** and **one active story with no testable acceptance criteria**. A large number of active P0/P1/P2 stories lack explicit error-path ACs, and several cross-cutting capabilities (`NowingIngestService`, `ChainLensServiceAuth`, AD-33 Generic Alert Engine) are assumed by earlier-numbered epics without a clear implementation story. The database/entity discipline is healthy — the only upfront-table candidate (Epic 13) has been correctly archived.

---

## Critical Violations

> Issues that block implementation or acceptance if not resolved.

### C1 — Story 12.6 depends on later Story 12.9 within the same epic
- **Location:** Epic 12, `Story 12.6: Job Market Alerts` (line 1980); explicit dependency note at line 1986.
- **Issue:** Story 12.6 is labeled `[P1 — depends on 12.9]` and the body states *“Story 12.9 (Saved Searches) must ship first — alerts use saved search infrastructure.”* Story 12.9 is a later-numbered, P0, `ready-for-dev` story. This violates epic/story independence and makes 12.6 impossible to complete before 12.9.
- **Remediation:** Renumber/reorder so that Saved Searches (`12.9`) precedes Job Market Alerts, or merge the two into a single “Saved Searches + Job Alerts” story with internal scaffolding.

### C2 — Story 20.1 depends on later Story 20.4 in Epic 20
- **Location:** Epic 20, `Story 20.1: Nowing Scraper to_chunks() + NowingIngestService` (line 2211); implementation note at line 2251 references *“Auth qua `ChainLensServiceAuth` (`Story 20.4`)”*.
- **Issue:** Story 20.1 is a foundational feeder story but assumes the service-to-service auth and cost ledger story (20.4, later in the same epic) is already done. Stories 20.2 and 20.3 likewise require `ChainLensServiceAuth`/token handling. This inverts the dependency chain.
- **Remediation:** Reorder Epic 20 so `20.4 Service-to-Service Auth + Cost Ledger Sync` is the first story; make 20.1/20.2/20.3 depend on it with forward numbering.

### C3 — Story 4.8d has no formal acceptance criteria
- **Location:** Epic 4, `Story 4.8d: Chat quality benchmark with LLM-as-judge` (line 1118).
- **Issue:** The story has only a one-line `_AC:` note: *"`nowing_evals run chat quality` judges each turn; reports aggregate score + per-tag breakdown; uses judge model separate from the tested model."* There is no `**Acceptance Criteria:**` section, no `Given/When/Then`, no measurable thresholds, and no error/edge paths. It is not independently testable.
- **Remediation:** Add a full `**Acceptance Criteria:**` block with G/W/T cases covering happy path, judge model failure/unavailability, missing baseline, invalid dataset, and per-tag breakdown requirements.

---

## Major Issues

> Issues that weaken independence, testability, or clarity and should be fixed before the next planning lock.

### M1 — Story 3.9 (DONE) has forward/cross-epic dependencies
- **Location:** `Story 3.9: Memory Recall Eval-Gate` (line 282); ordering notes at lines 293 and 403–404.
- **Issue:** The final baseline for 3.9 must be measured *after* `3.10` (legacy data safety), `3.14` (memory injection bound), and `8.4a` (auto-extract kill-switch, renumbered to `8.8`). This means an earlier-numbered story depends on later-numbered stories and on a later epic. The file itself acknowledges the issue with *“baseline đo trên lượng inject phụ thuộc N thì không tái lập được.”*
- **Remediation:** Move the “finalize baseline / ratify SM-10” acceptance criteria into a separate follow-up story (e.g., `3.18`) that follows 3.10, 3.14, and 8.8; update all references from `8.4a` to `8.8`.

### M2 — Story 8.7 (DONE) references a renumbered/forward dependency
- **Location:** `Story 8.7: Auto-Extract Spend/Budget Cap` (line 587); dependency note at line 595.
- **Issue:** The body lists `Dep: 8.4a` even though the renumbering note at line 153 states `8.4a → 8.8`. This creates an inconsistent forward dependency (8.7 depending on 8.8) and stale numbering in the dependency map.
- **Remediation:** Update the dependency to `8.8` and, because the kill-switch logically must precede the spend cap, consider renumbering 8.7/8.8 so the sequence matches the dependency.

### M3 — Story 9.5 has placeholder acceptance criteria
- **Location:** `Story 9.5: Metered Deep-Research Endpoint cho Self-Host` (line 962).
- **Issue:** The story is `[POST-MVP]` and its AC block is explicitly labeled *“Acceptance Criteria (nháp — cần SCP phê duyệt trước khi dev)”*. The criteria are high-level Phase-2 statements without concrete thresholds, error paths, or testable gates.
- **Remediation:** Keep 9.5 in backlog until a new SCP is approved; then replace the draft ACs with full G/W/T acceptance criteria and a `blocked-until` dependency on the approved SCP.

### M4 — Epic 13 is a pure technical/infrastructure epic
- **Location:** `## Epic 13: Canonical Entity Storage & Multi-Domain Indexing` (line 1545).
- **Issue:** The title and goal are purely technical (“Canonical Entity Storage & Multi-Domain Indexing”), with no user-facing value statement. It also represents the exact kind of “build all tables upfront” architecture the project later rejected.
- **Remediation:** The epic is already marked `[DROPPED 2026-08-08 — ARCHIVED]`; leave it archived and guard against resurrecting it or any similar technical-only epic without a user-value reframe.

### M5 — Widespread missing error-path acceptance criteria in active stories
- **Location:** 27 active `ready-for-dev` / P0 / P1 / P2 stories (see list below).
- **Issue:** A large number of active stories describe only happy-path behavior. They do not include explicit `Given/When/Then` branches for failure, invalid input, downstream unavailability, rate limits, auth errors, or degradation. Examples include:
  - `2.8 Amazon EU Marketplaces` (line 204)
  - `3.15 Run Citations as Verifiable Sources` (line 411)
  - `4.7 Pointer-Based Tabs with Live Title Resolution` (line 1090)
  - `6.6/6.7/6.9 Playbook/Schema/Vertical` (lines 502, 520, 537)
  - `7.4 Dedicated Connectors Layout` (line 1194)
  - `7.7 MCP Server Tool Expansion` (line 1207)
  - `12.5 PII Redaction for Job Data` (line 1525)
  - `14.2 News Entity Enrichment` (line 1751)
  - `16.1/16.2 masothue.com / Official Business Registry` (lines 1842, 1863)
  - `17.2 Shopee Product Data` (line 1918)
  - `18.2/18.4/18.5/18.6/18.7 Public Agent-Chat extension stories` (lines 1594, 1626, 1641, 1656, 1671)
  - `20.2 Gap-Fill Caller + Cost Allocation` (line 2255)
  - plus `12.6`, `14.3`, `15.3`, `15.4`, `16.3`, `17.3`, `17.4` (alert/intelligence stories)
- **Remediation:** For each active story, add at least one G/W/T case covering an error or edge path (e.g., invalid URL, auth failure, rate-limit, missing data, model unavailability, downstream 5xx, PII edge cases, anti-bot block).

### M6 — Cross-cutting dependencies on later/generic infrastructure are not surfaced
- **Location:** Multiple P0/P1/P2 stories across Epics 12, 14–17, and 20.
- **Issue:** Many vertical/alert stories assume `NowingIngestService`, `ChainLensServiceAuth`/`TokenUsage` cost ledger, and the AD-33 Generic Alert Engine already exist. The canonical definitions for these capabilities live in Epic 20 (`20.1`, `20.4`) and in AD-33, which are later or not represented by a concrete story. This creates hidden forward dependencies that could block parallel implementation.
- **Remediation:** 
  - Make `20.4 Service-to-Service Auth + Cost Ledger Sync` and `20.1 NowingIngestService` explicit prerequisites for any story that calls them.
  - Add a concrete implementation story for AD-33 (Generic Alert Engine) and link it from `12.9`, `12.6`, `14.3`, `15.3`, `15.4`, `16.3`, `17.3`, `17.4`.

### M7 — Epic 21 is PROPOSED but already has 7 high-level stories
- **Location:** `## Epic 21: Lead Gen Intelligence` (line 2344) and stories 21.1–21.7 (lines 2357–2433).
- **Issue:** The epic is `[PROPOSED]`, yet stories 21.1–21.7 are written as backlog items with concrete ACs that lack measurable thresholds, cost/latency/error-path detail, and PII/consent handling. This is premature for a proposal and risks leaking a half-baked vertical into active planning.
- **Remediation:** Keep Epic 21 in a separate proposal doc until product discovery is complete; rewrite each story with a user role, concrete success metrics, explicit error paths, and a PII/consent gate before merging into `epics.md` as active work.

---

## Minor Concerns

> Issues that are acceptable for now but create documentation debt or review friction.

### m1 — Done benchmark stories use one-line `_AC:` notes
- **Location:** `4.8a`, `4.8b`, `4.8c`, `4.8e`, `4.8f`, `4.8g` (lines 1103–1137).
- **Issue:** These stories are marked `[done]` but their acceptance criteria are one-line `_AC:` notes rather than formal `Given/When/Then` blocks. No remediation is required for completed work, but the file should not be used as a template for new stories.
- **Remediation:** When these stories are touched again, expand the `_AC:` lines into proper G/W/T ACs for auditability.

### m2 — Dropped stories 12.7 and 12.8 have no acceptance criteria
- **Location:** `12.7 Property Price Alerts` (line 1999) and `12.8 Cross-Source Entity Timeline` (line 2005).
- **Issue:** Both are `[DROPPED]` and contain only a drop rationale, which is fine. Keeping them in the file is useful for traceability, but they should not be mistaken for planned work.
- **Remediation:** No action; optionally move them to an `ARCHIVED.md` file to reduce noise.

### m3 — Follow-up/tech-debt stories are framed for platform engineers, not end users
- **Location:** `3.7-followup` (line 331), `8.11-followup` (line 695), `4.8c-followup` (line 1153), `4.8d-followup` (line 1165), `4.8h-followup` (line 1175), `9.6-followup` (line 1044).
- **Issue:** These items are titled “followup / tech debt” and use platform-engineer roles. They are `[backlog]` items, so this is acceptable, but if they are scheduled, they should be rewritten with end-user value or explicitly labeled as engineering-only debt with no acceptance criteria changes.
- **Remediation:** Refactor each follow-up into either a user-value story or a clear engineering task with a `tech-debt` label.

### m4 — Inconsistent status tags and formatting
- **Location:** Across all story headings.
- **Issue:** Status tags mix conventions: `` `[DONE]` ``, `` `[done]` ``, `` `[ready-for-dev]` ``, `` `[P0]` ``, `` `[GAP]` ``, `` `[backlog]` ``, `` `[PROPOSED]` ``, `` `[DROPPED]` ``. Some include P-levels inside the same bracket, others do not. This makes automated parsing fragile.
- **Remediation:** Adopt a single tag schema, e.g., `` `[STATUS|Pn]` `` or separate fields for status and priority.

### m5 — Mixed Vietnamese/English in epic descriptions and context notes
- **Location:** Epic descriptions and implementation notes (e.g., Epic 8, Epic 9, Epic 12).
- **Issue:** The file convention (line 111) requires ACs to be in English with G/W/T. Epic descriptions and notes are allowed in Vietnamese, but the mix increases friction for non-Vietnamese reviewers and for automated AC extraction.
- **Remediation:** Keep the convention; optionally add English summaries for epic context notes that affect cross-team review.

### m6 — Story 9.4 and other “Docs” stories lack error paths
- **Location:** `9.4 Docs — Quan hệ Nowing ↔ ChainLens` (line 930), `8.10 Docs / README / Vision Sync` (line 607).
- **Issue:** Documentation/sync stories are marked `[DONE]` and have reasonable G/W/T but no explicit error/edge branches (e.g., what happens if docs drift is detected). For docs stories this is minor.
- **Remediation:** Add a single “Given docs drift is detected…” AC when these stories are next revised.

---

## Recommendations

1. **Fix forward dependencies first.** Renumber/reorder `12.6 ↔ 12.9` in Epic 12 and `20.1–20.4` in Epic 20 so dependencies only flow from lower to higher story numbers. Update all stale references (`8.4a` → `8.8`).
2. **Add error-path ACs to all active stories.** Run a one-pass review of the 27 active stories flagged in M5 and add at least one explicit failure/degradation/edge `Given/When/Then` per story.
3. **Make critical infrastructure explicit.** Split `20.4 Service-to-Service Auth + Cost Ledger Sync` and the AD-33 Generic Alert Engine into concrete, blockable stories and link them from every dependent vertical/alert story.
4. **Keep proposed work out of the active backlog.** Move Epic 21 to a separate proposal document until it has user roles, concrete metrics, error paths, and PII/consent gates.
5. **Normalize status tags.** Adopt a single, machine-readable status format (e.g., `` `[ready-for-dev|P0]` `` or separate status and priority fields).
6. **Maintain the database discipline.** No active upfront-table violations were found; continue creating tables/migrations only in the story that first needs them. Keep Epic 13 archived and do not resurrect it without a user-value reframe.
7. **Add a lightweight AC lint.** Consider a CI check or pre-merge checklist that rejects new stories missing `**Given**` / `**When**` / `**Then**` or any error-path clause.

---

*End of review.*
