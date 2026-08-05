---
date: 2026-08-05 (final v3)
project: Nowing
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05 (final v3)  
**Project:** Nowing  
**Assessor:** `bmad-check-implementation-readiness` workflow  
**Workflow customization:** `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-check-implementation-readiness --key workflow`

---

## 1. Document Discovery

### PRD Documents

**Selected PRD (sharded folder):**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (108,388 bytes, modified 2026-08-05 17:13)

**Other PRD-related files in the same folder:**
- `prds/prd-Nowing-2026-07-22/.memlog.md`
- `prds/prd-Nowing-2026-07-22/review-prfaq-gap.md`
- `prds/prd-Nowing-2026-07-22/review-rubric.md`
- `prds/prd-Nowing-2026-07-22/validation-report.md`
- `prds/prd-Nowing-2026-07-22/validation-report.html`

No whole PRD `.md` file exists at the top level; the folder version is the authoritative PRD.

### Architecture Documents

**Selected Architecture:**
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (78,269 bytes, modified 2026-08-05 10:24)

### Epics & Stories Documents

**Selected Epics document:**
- `epics.md` (110,631 bytes, modified 2026-08-05 17:22)

**Selected status source of truth:**
- `implementation-artifacts/sprint-status.yaml` (5,838 bytes, modified 2026-08-05 17:13)

### UX Design Documents

**Selected UX contracts (sharded folder `ux-designs/ux-Nowing-2026-07-22/`):**
- `ux-contract-admin-global-model-config.md` (2,470 bytes, 2026-08-05 15:38)
- `ux-contract-async-deep-research.md` (7,417 bytes, 2026-08-04 20:16)
- `ux-contract-chat-benchmark.md` (2,203 bytes, 2026-08-05 15:39)
- `ux-contract-first-run-onboarding.md` (2,160 bytes, 2026-08-05 15:39)
- `ux-contract-sync-offline-indicator.md` (2,149 bytes, 2026-08-05 15:39)
- `ux-contract-usage-dashboard.md` (1,962 bytes, 2026-08-05 15:39)

### Issues Found

- No duplicate whole/sharded versions were found for PRD, architecture, epics, or UX.
- `epics.md` and `prd.md` are newer than the architecture and reflect the 2026-08-05 fixes (commit `9f6a4c594` — *docs(nowing): adopt OQ-7 (5 questions) and update coverage map*).
- `sprint-status.yaml:117` still carries an outdated comment (`# 9-6 partial ...`) even though `9-6: done` is recorded on line 124. The comment should be refreshed in the next docs pass.
- The top-level `## Requirements Inventory` in `epics.md` (`epics.md:35-47`) still carries stale `[GAP]` / `[PARTIAL]` labels that conflict with the updated `### FR Coverage Map` and the reconciled PRD tags. This is documented as a non-blocking hygiene issue in the Final Assessment.
- Earlier assessment reports (`implementation-readiness-report-2026-08-05.md`, `implementation-readiness-report-2026-08-05-final.md`, `implementation-readiness-report-2026-08-05-final-v2.md`) are not used as sources.

---

## 2. PRD Analysis

### Status Tag Reconciliation (Verified Fixes)

| Requirement | PRD Location | Status Tag | Assessment |
| --- | --- | --- | --- |
| FR-31 Credit Wallet & Purchases | `prd.md:548-556` | `[DONE]` | Done |
| NFR-7 Usage & Credit Dashboard | `prd.md:804-808` | `[DONE]` | Done |
| FR-40 First-Run Value — Research Runs Produce Memory | `prd.md:335-369` | `[DONE — story 3-13]` | Done |
| NFR-1b Memory injection (blocks every chat turn) | `prd.md:742-774` | `[DONE — story 3-14]` | Done |
| NFR-1c Recall tool (`nowing_recall`, `/memories/search`) | `prd.md:749-774` | `[DONE — story 3-14]` | Done |
| NFR-1d Auto-extract (Celery, off critical path) | `prd.md:766-774` | `[DONE — story 3-14]` | Done |
| FR-41 Admin UI for Global LLM Model Configuration | `prd.md:558-582` | `[DONE — story 8-11]` | Done |
| FR-39 Memory → Scraper-Run Provenance & Source Re-Validation | `prd.md:691-722` | `[DONE — story 9-6]` | Done |
| NFR-8 Recall Quality (eval-gated) | `prd.md:810-817` | `[DONE — story 3-9]` | Done; `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` records `baseline_ratified: true` |
| FR-37 Deep-Research Cost Metering | `prd.md:623-651` | `[DONE — parser + fallback updated]` | Done |
| FR-38 Research Degradation & Self-Host Independence | `prd.md:653-687` | `[DONE — P0]` | Done |
| FR-24 Deep Open-Web Research via ChainLens | `prd.md:594-621` | `[DONE — contract + regression guard in place]` | Done |
| OQ-7 (5 questions from ChainLens `42-3`) | `epics.md:80` / `prd.md:908` references | `ADOPTED 2026-08-05` | Done; mapped to E9.1b/E9.2/E9.3 |

All targeted PRD status tags now read `DONE` / `RESOLVED` / `ADOPTED`.

### PRD Completeness Assessment

The PRD is complete for the current MVP scope. The targeted items are reconciled with `sprint-status.yaml` and the codebase. The remaining PRD tags are deliberate:

- **NFR-9** (`prd.md:819-889`) remains `[PARTIAL]` — State A (async deliverable) is done; State B (sync chat-mode) is a launch gate that requires a measured Nowing e2e benchmark and ratification.
- **NFR-10** (`prd.md:891-899`) is described as a deploy gate; `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` still has `baseline_ratified: false`, so the gate is not yet ratified.
- **FR-32** (`prd.md:264-285`) still carries `[BUILT — schema/endpoints/tools; PARTIAL — dedupe/quality]` in the PRD header and `[PARTIAL]` dedupe/quality notes. The relevant stories (`3.9` recall eval-gate and `3.11` dedupe) are `done` in `sprint-status.yaml` and the `epics.md` `### FR Coverage Map` maps them to `FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11)`. This is a documentation/labeling nuance rather than a missing MVP capability.
- Post-MVP GAPs (advanced memory lifecycle, UI memory browser, document retention enforcement, rich relation graph traversal) remain correctly labeled as non-MVP.

No new unimplemented capabilities were found in the PRD.

---

## 3. Epic Coverage Validation

### Targeted Story Status Tags (Verified Fixes)

| Story | Epic Location | Status Tag | Assessment |
| --- | --- | --- | --- |
| 8.11 Admin UI for Global LLM Model Configuration | `epics.md:520` | `[DONE per sprint-status: 8-11]` | Done |
| 8.12 Workspace Limits | `epics.md:565` | `[DONE per sprint-status: 8-12]` | Done |
| 8.13 PostHog Product Analytics | `epics.md:578` | `[DONE per sprint-status: 8-13]` | Done |
| 9.3 Latency Budget & State A→B Gate | `epics.md:722` | `[DONE per sprint-status: 9-3]` | Done |
| 9.6 Memory Provenance & Re-Validation | `epics.md:839` | `[DONE per sprint-status: 9-6]` | Done |
| 10.1 Batdongsan.com.vn Scraper | `epics.md:1010` | `[DONE per sprint-status: 10-1]` | Done |
| 10.4 Vietnam BĐS Listing Aggregator & Cross-Source Trust Score | `epics.md:1073` | `[DONE per sprint-status: 10-4]` | Done |
| 4.8h Mode-Aware Chat Policy for Latency/Cost | `epics.md:951-962` | Clean G/W/T; done | Done |

All requested epic story status tags are now `DONE`.

### FR/NFR Coverage Map Verification

The stale coverage map issue called out in the previous report (`epics.md:76-77`, `epics.md:80`) has been fixed. The current `### FR Coverage Map` (`epics.md:75-86`) now reads:

```
- FR-1/2/3/4/10 → E1 [DONE] · FR-6/7/8 → E2 [DONE] · FR-6 mở rộng → E10.1 [DONE]
  (batdongsan scraper) · FR-9/11/12/13 → E3 [DONE] · FR-14/15/16/17/42 → E4 [DONE]
  (4.8a–4.8g chat benchmark & regression gate) · FR-21/22/23 → E5 [DONE]
  · FR-19/20 → E6 [DONE] · FR-25/26/27/28/29 → E7 [DONE] · FR-30 → E8 [DONE]
  · FR-41 → E8.11 [DONE]
- FR-24/37/38/39 + NFR-9 → E9 (...): FR-38 → E9.1a [DONE, P0]
  · FR-24 → E9.1b [DONE, P0] · FR-37 → E9.2 [DONE, P0, ...]
  · NFR-9 → E9.3 [DONE] · OQ-6/AR-10 → E9.4 [DONE, P1]
  · D5-Phase2 → E9.5 [deferred] · FR-39 → E9.6 [DONE]
- FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11) · FR-33 → E4 (4.6 done)
  · FR-34 → E3/E4 (done)
- FR-36 → E3.10 [RESOLVED 2026-07-25] · FR-18 → E6.4 [DONE]
  · FR-31/NFR-7 → E8.3 [DONE] · FR-35 → E6.5 [DONE]
- NFR-8 → E3.9 [DONE — baseline ratified 2026-08-04] · NFR-6 → E3.6 [DONE]
  · NFR-10 → E4 [DONE — 4.8b/4.8e/4.8f/4.8g] · OQ-3/AR-4 → E3.7 [PARTIAL]
  · OQ-4 → E2.5 [DONE] · OQ-5 → E6.4 [DONE] · OQ-6/AR-10 → E8.10 + E9.4 [DONE]
  · OQ-7 (5 câu hỏi từ ChainLens `42-3`, ADOPTED 2026-08-05) → E9.1b/E9.2/E9.3 [DONE]
  · FR-5 → [REMOVED]
```

A targeted verification script confirmed that the previously stale entries (`FR-6 mở rộng → E10.1`, `FR-41 → E8.11`, `FR-39 → E9.6`, `NFR-8 → E3.9`, `NFR-10 → E4`, `OQ-6/AR-10 → E8.10 + E9.4`, `OQ-7 → E9.1b/E9.2/E9.3`) are now marked `DONE`.

### FR/NFR Coverage Matrix

The overall coverage picture is now aligned between the PRD, the `epics.md` `### FR Coverage Map`, and `sprint-status.yaml`.

| FR | PRD Requirement | Epic Coverage | Status |
| --- | --- | --- | --- |
| FR-1 | User Authentication | E1 | DONE |
| FR-2 | API Access for External Clients (PAT/API key) | E1 | DONE |
| FR-3 | Workspace Lifecycle | E1 | DONE |
| FR-4 | Workspace Invites & Memberships | E1 | DONE |
| FR-10 | RBAC with three system roles | E1 | DONE |
| FR-6 | Built-in Scraper Connectors | E2 / E10.1 | DONE |
| FR-7 | External OAuth Connectors | E2 | DONE |
| FR-8 | External MCP Connectors | E2 | DONE |
| FR-9 | Document Upload, Parse & Index | E3 | DONE |
| FR-11 | Folders & Document Management | E3 | DONE |
| FR-12 | Hybrid Search over Knowledge Base | E3 | DONE |
| FR-13 | Citation Panel for Knowledge-base Chunks | E3 | DONE |
| FR-32 | Long-Term Research Memory | E3 (3.8/3.9/3.11/3.14) | DONE; recall baseline ratified; dedupe wired |
| FR-33 | Research Continuity | E4 (4.6) | DONE |
| FR-34 | Memory Correction | E3/E4 | DONE |
| FR-36 | Legacy Memory Data-Loss | E3.10 | RESOLVED |
| FR-5 | AI File Sorting | — | REMOVED |
| FR-14 | Chat Threads & Messages | E4 | DONE |
| FR-15 | Multi-agent Runtime with Tools | E4 | DONE |
| FR-16 | Real-time Collaborative Chat | E4 | DONE |
| FR-17 | Anonymous Chat with Quota | E4 | DONE |
| FR-42 | Chat Response Benchmark | E4 (4.8a-g) | DONE |
| FR-21 | Report Generation & Export | E5 | DONE |
| FR-22 | Podcast & Video Presentation | E5 | DONE |
| FR-23 | Image Generation | E5 | DONE |
| FR-18 | Automation Action Types | E6.4 | DONE |
| FR-19 | Automation Triggers | E6 | DONE |
| FR-20 | Automation Runs & Retries | E6 | DONE |
| FR-35 | Memory-Driven Automations | E6.5 | DONE |
| FR-25 | Web Client (Next.js) | E7 | DONE |
| FR-26 | Desktop Client (Electron) | E7 | DONE |
| FR-27 | Browser Extension (Plasmo) | E7 | DONE |
| FR-28 | Obsidian Plugin | E7 | DONE |
| FR-29 | MCP Server | E7 / E7.7 | DONE; expansion in 7.7 ready-for-dev |
| FR-30 | Token Usage Tracking | E8 | DONE |
| FR-31 | Credit Wallet & Purchases | E8.3 | DONE |
| FR-41 | Admin UI for Global LLM Model Configuration | E8.11 | DONE |
| FR-24 | Deep Open-Web Research via ChainLens | E9.1b | DONE |
| FR-37 | Deep-Research Cost Metering | E9.2 | DONE |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a | DONE |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | E9.6 | DONE |
| FR-40 | First-Run Value — Research Runs Produce Memory | E3.13 | DONE |

| NFR | PRD Requirement | Epic Coverage | Status |
| --- | --- | --- | --- |
| NFR-1a | CRUD & scraper performance | E1/E2 | Covered |
| NFR-1b | Memory injection (blocks every chat turn) | E3.14 | DONE |
| NFR-1c | Recall tool latency/score | E3.14 | DONE |
| NFR-1d | Auto-extract off critical path | E3.14 | DONE |
| NFR-2 | Security & Auth | E1/E3 | DONE |
| NFR-3 | Observability | E8.9 / platform | DONE |
| NFR-4 | Reliability | E1/E6/E8 | DONE |
| NFR-5 | Multi-tenancy Isolation | E1/E3 | DONE |
| NFR-6 | Citation Full-Editor Highlight | E3.6 | DONE |
| NFR-7 | Usage & Credit Dashboard | E8.3 | DONE |
| NFR-8 | Recall Quality (eval-gated) | E3.9 | DONE — baseline ratified 2026-08-04 |
| NFR-9 | Deep-Research Latency & Availability (State A/B) | E9.3 | PARTIAL — State A done; State B launch gate open |
| NFR-10 | Chat Response Regression Gate | E4 (4.8b/e/f/g) | Covered; `chat/regression/gate.yaml` `baseline_ratified: false` so gate not yet ratified |

### Coverage Statistics

- **Total PRD FRs (excluding removed/resolved):** 38
- **Covered/Done in epics:** 38
- **Gaps:** no unimplemented capabilities
- **Coverage percentage:** 100% of FRs are covered; the only open items are NFR-9 State B and NFR-10 baseline ratification, which are launch gates, not missing capability.

### New Epics Not Traceable to Original PRD

- **Epic 10: Connector & Scraper Expansion** (BDS scrapers) — extends FR-6; implementation done for 10.1-10.4.
- **Epic 11: Telegram Automation & Bot** — introduces `FR-TELE-*` requirements; implementation done for 11.1-11.3.

These epics are valid for current work and are tracked in `sprint-status.yaml` as done.

---

## 4. UX Alignment Assessment

### UX Document Status

UX contracts are behavior contracts (not visual designs) in `ux-designs/ux-Nowing-2026-07-22/`:

- `ux-contract-async-deep-research.md` — blocks Story 9.3 (NFR-9 State A)
- `ux-contract-admin-global-model-config.md` — blocks Story 8.11 (FR-41)
- `ux-contract-chat-benchmark.md` — blocks Stories 4.8a-g (FR-42, NFR-10)
- `ux-contract-first-run-onboarding.md` — blocks Story 3.13 (FR-40)
- `ux-contract-sync-offline-indicator.md` — blocks Stories 9.1a (FR-38) and 9.3 (NFR-9)
- `ux-contract-usage-dashboard.md` — blocks Story 8.3 (FR-31/NFR-7) and 8.12 (workspace limits)

### UX <-> PRD Alignment

| UX Contract | PRD Requirement(s) | Alignment |
| --- | --- | --- |
| Async Deep Research | NFR-9 State A, FR-38, FR-24 | Aligned. Defines S1-S10 UI states for progress-first async deep research, including `partial`, `insufficientEvidence`, `engine_unavailable`, and `degraded`. |
| Admin Global Model Config | FR-41 | Aligned. Contract A1-A7 matches FR-41 AC: superuser-only, merged file/DB-backed list, hidden API key, test connection, hot-reload. |
| Chat Benchmark | FR-42, NFR-10 | Aligned. B1-B7 mirror NFR-10 metrics and FR-42 telemetry (p95 latency, TTFB, error rate, finish rate, citation count, cost/turn, per-mode matrix). |
| First-Run Onboarding | FR-40 | Aligned. Contract focuses on research-run seeding rather than fake data, matching PRD decision. |
| Sync & Offline Indicator | FR-38, NFR-9 | Aligned. Defines states for Zero sync, auth cookie cross-subdomain failure, and deep-research degradation. |
| Usage & Credit Dashboard | FR-31, NFR-7, Story 8.12 | Aligned. U1-U7 match FR-31/NFR-7 dashboard requirements and workspace limits. |

### UX <-> Architecture Alignment

All UX contracts are supported by architecture:

- Async Deep Research: `AD-17` (async door), `AD-5` (Zero scope), `AD-18` (memory bounds)
- Admin Global Model Config: `AD-8` (cost registration), `AD-9` (RBAC 3 roles unchanged)
- Chat Benchmark: `AD-4` (multi-agent runtime), `AD-8` (cost tracking)
- First-Run Onboarding: `AD-18` (memory bounds), `FR-38` (degradation)
- Sync & Offline Indicator: `AD-5` (Zero sync), `AD-4` (Redis/Celery), `FR-38`
- Usage & Credit Dashboard: `AD-8` (unified wallet), `AD-10` (token usage)

### Alignment Issues

No critical UX/PRD/Architecture misalignment was found.

The targeted planning-truth gaps (`8.11`, `8.12`, `8.13`, `9.3`, `9.6`, `10.1`, `10.4`, `FR-31`, `NFR-7`, `FR-40`, `NFR-1b/1c/1d`, `FR-41`, `FR-39`, `NFR-8`, `OQ-7`) are now resolved in the PRD story status tags and the UX contracts are unblocked.

A residual planning-truth drift remains in the `epics.md` top-level `## Requirements Inventory` (see Epic Quality Review / Final Assessment). The UX contracts themselves are not misaligned.

---

## 5. Epic Quality Review

### Epic-by-Epic Quality Summary

| Epic | User Value | Independence | Story Sizing | AC Format (G/W/T) | No Forward Deps | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| E1 Identity, Auth & Workspace RBAC | PASS | PASS | PASS | PASS | PASS | Brownfield; done. |
| E2 Connectors | PASS | PASS | PASS | PASS | PASS | 2.6-2.9 are `ready-for-dev` expansion; no forward dependencies. |
| E3 Knowledge Base + Long-Term Memory | PASS | PASS | PASS | PASS | PASS | 3.13/3.14 done; 3.15/3.16 `ready-for-dev`. |
| E4 Chat & Agents | PASS | PASS | PASS | PASS | PASS | 4.8a-g done; 4.7/4.8d `ready-for-dev`. |
| E5 Deliverables | PASS | PASS | PASS | PASS | PASS | Done. |
| E6 Automations | PASS | PASS | PASS | PASS | PASS | 6.6/6.7/6.9 gated after BDS pilot; no forward technical dependencies. |
| E7 Multi-surface Clients | PASS | PASS | PASS | PASS | PASS | 7.4/7.7 `ready-for-dev`. |
| E8 Billing / Usage | PASS | PASS | PASS | PASS | PASS | 8.10 done; 8.11/8.12/8.13 done per sprint-status. |
| E9 Deep Research | PASS | WARN | PASS | PASS | PASS | 9.1a -> 9.1b/9.2/9.3 -> 9.4 is architecture sequence, not business forward dep. |
| E10 Connector & Scraper Expansion | PASS | PASS | PASS | PASS | PASS | 10.1-10.4 done per sprint-status. |
| E11 Telegram Automation & Bot | PASS | PASS | PASS | PASS | PASS | 11.1-11.3 done. |

### Best Practices Compliance Checklist

- [x] Epics deliver user value (no technical milestone epics).
- [x] Epics can function independently.
- [x] Stories are appropriately sized.
- [x] No forward dependencies on future epics.
- [x] Database tables are created when needed (brownfield; tables exist).
- [x] Acceptance criteria use Given/When/Then.
- [x] Traceability to FRs is maintained.

### Single-Story Verification

- **3.10:** Merged from `3-10a` and `3-10b` into one story. `epics.md:242-255` and `sprint-status.yaml:72` both confirm a single story.
- **6.9:** `epics.md:432-453` is a single `### Story 6.9` section with no sub-story split.
- **9.6:** `epics.md:839` explicitly merged `9.6a` and `9.6b` into one story; both provenance and re-validation ACs live under `### Story 9.6` (`epics.md:853-894`). `sprint-status.yaml:124` records `9-6: done`.

### Acceptance Criteria Cleanliness Check

| Story | Location | Assessment |
| --- | --- | --- |
| 4.8h Mode-Aware Chat Policy for Latency/Cost | `epics.md:951-962` | Clean G/W/T; tool-call budget and `top_k`/`max_passages` details moved to the `_Implementation hints (not AC)_` paragraph (`epics.md:963`). |
| 8.10 Docs / README / Vision Sync | `epics.md:507-513` | Clean G/W/T; verified by `check-docs-drift.py` pass. |
| 8.11 Admin UI for Global LLM Model Configuration | `epics.md:528-553` | Clean G/W/T; implementation hints explicitly separated. |
| 9.1a Research Degradation & Self-Host Independence | `epics.md:611-638` | Clean G/W/T; covers timeout, unconfigured, heartbeat, and public-repo gate. |
| 9.1b Research Contract Regression Guard | `epics.md:653-676` | Clean G/W/T; contract, clamp, source order, fixture reuse covered. |
| 9.2 Deep-Research Cost Metering | `epics.md:695-713` | Clean G/W/T; real cost, fallback, aggregate, pricing gate covered. |
| 10.1 Batdongsan Scraper | `epics.md:1016-1027` | AC no longer prescribes the `gzip -> base64 -> nibble-swap -> Latin-1 JSON` decode pipeline; the pipeline is now only in the `_Implementation hints (not AC)_` paragraph (`epics.md:1029`). |
| 10.2 Chotot.vn / Nha Tot Scraper | `epics.md:1039-1046` | Clean G/W/T. |
| 10.3 Muaban.net BDS Scraper | `epics.md:1058-1067` | Clean G/W/T. |
| 10.4 Vietnam BĐS Listing Aggregator | `epics.md:1079-1088` | Clean G/W/T. |
| 11.1 Telegram Notification Foundation | `epics.md:1110-1121` | Clean G/W/T. |
| 11.2 Telegram Write-Back, Builder UI & Chat Resolution | `epics.md:1131-1142` | Clean G/W/T. |
| 11.3 Telegram Interactive Bot & Commands | `epics.md:1152-1169` | Clean G/W/T. |

### Critical / Major / Minor Issues

#### Critical Violations

*None.* All epics are user-value focused, and no story is blocked by a future epic. Epic 9's architecture sequence is explicitly documented and justified.

#### Major Issues

*None.* The previously documented planning-truth drift in the `epics.md` `### FR Coverage Map` is now resolved. No capability is unimplemented or blocked.

#### Minor Concerns

1. **Stale top-level `## Requirements Inventory` in `epics.md`** (`epics.md:35-47`)
   - Line 36 still labels `FR-32` as `[PARTIAL]` and `FR-24` as `[PARTIAL]` even though the coverage map, PRD, and `sprint-status.yaml` mark them `DONE`.
   - Line 39 still labels `FR-38`, `FR-39`, `FR-40`, and `FR-41` as `[GAP]` even though their stories and the PRD are `DONE`.
   - Line 40 still labels `NFR-1b/1c/1d` as `[GAP — NFR]` even though `E3.14` is `DONE`.
   - Line 47 still describes `NFR-8` as `baseline ratification pending` even though `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` records `baseline_ratified: true`.
   - **Impact:** The top-level inventory no longer matches the reconciled `### FR Coverage Map` (`epics.md:75-86`) or the PRD. It is a documentation hygiene issue, not a missing capability.
   - **Action:** Refresh the top-level `## Requirements Inventory` to match the reconciled coverage map in the next docs pass.

2. **FR-32 PRD status still reads `[BUILT — PARTIAL — dedupe/quality]`** (`prd.md:264-285`)
   - The PRD header/Status still flags dedupe and recall-quality as partial, while `sprint-status.yaml` has `3-9: done` (baseline ratified) and `3-11: done` (dedupe wired), and `epics.md` maps `FR-32 → E3 (3.8 done; quality→3.9, dedupe→3.11)`.
   - **Impact:** This is a documentation/labeling nuance. The capability is implemented and the eval gate is ratified.
   - **Action:** Reconcile the FR-32 PRD tag with the coverage map and `sprint-status.yaml` in the next docs pass.

3. **Stale `sprint-status.yaml` comment on `epic-9`**
   - Line 117 still reads `# 9-6 partial (provenance done, re-validation API gap); rest done`, but line 124 records `9-6: done` (merged 9.6a and 9.6b, both done). The comment should be updated to reflect the actual state.

4. **Launch-gate ratification still open for NFR-9 and NFR-10**
   - NFR-9 State B requires a clean Nowing e2e benchmark and ratification before `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` can be enabled.
   - NFR-10 `chat/regression` gate has thresholds in `gate.yaml` but `baseline_ratified: false`; the gate cannot block/fail deploys until the baseline is ratified.

### Dependency Analysis

- Within-epic dependencies are natural (e.g., `3.13` -> `3.14`, `9.1a` -> `9.1b`/`9.2`/`9.3`).
- Cross-epic dependencies are minimal and well documented:
  - `3.13` has a soft dependency on `9.6` for full provenance but ships a minimal version first.
  - `4.8h` depends on FR-42/NFR-10 benchmark harness (done).
  - `8.3` usage dashboard depends on FR-37 `costDollars` (done).
  - `10.4` aggregator depends on `10.1/10.2/10.3` and FR-39.
- No circular or forward dependencies were found.

---

## 6. Final Assessment

### Workflow Customization

`python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-check-implementation-readiness --key workflow` resolved to:

```json
{
  "workflow": {
    "activation_steps_prepend": [],
    "activation_steps_append": [],
    "persistent_facts": [
      "file:{project-root}/**/project-context.md"
    ],
    "on_complete": ""
  }
}
```

### Docs-Drift Check Result

`python3 /Users/luisphan/Documents/GitHub/nowing/scripts/check-docs-drift.py` was run during the assessment.

- **Result:** `Docs-drift check PASSED.`

This verifies that public-facing docs (README, landing, install scripts) do not contain forbidden pre-pivot phrases and include the required product promise.

### Targeted Consistency Check

A targeted verification was run against the PRD, `epics.md` `### FR Coverage Map`, `sprint-status.yaml`, and the eval `gate.yaml` files. It confirmed:

- `FR-6 mở rộng → E10.1` is `[DONE]` in the coverage map.
- `FR-41 → E8.11` is `[DONE]` in the coverage map.
- `FR-39 → E9.6` is `[DONE]` in the coverage map.
- `NFR-8 → E3.9` is `[DONE — baseline ratified 2026-08-04]` in the coverage map, and `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` has `baseline_ratified: true`.
- `NFR-10 → E4` is `[DONE]` in the coverage map; `chat/regression/gate.yaml:1` has `baseline_ratified: false` (launch gate).
- `OQ-6/AR-10 → E8.10 + E9.4` is `[DONE]` in the coverage map.
- `OQ-7 → E9.1b/E9.2/E9.3` is `[DONE]` in the coverage map.
- PRD sections for `FR-31`, `FR-41`, `FR-39`, `FR-40`, `NFR-7`, `NFR-8`, `FR-37`, `FR-38`, and `FR-24` all contain `DONE`/`RESOLVED` markers.
- `sprint-status.yaml` records `8-11: done`, `9-6: done`, `10-1: done`, and `3-9: done`.

The same check flagged the stale top-level `## Requirements Inventory` in `epics.md` (see Minor Concerns above) and the two open launch gates (`NFR-9 State B`, `NFR-10` baseline).

### Overall Readiness Status

**READY**

The Nowing implementation is ready to proceed. The specific items targeted in this final v3 run are now correctly reflected:

- The stale `epics.md` `### FR Coverage Map` (`epics.md:76-77`, `epics.md:80`) is fixed.
- PRD tags for `FR-31`, `NFR-7`, `FR-40`, `NFR-1b/1c/1d`, `FR-41`, `FR-39`, `NFR-8`, `FR-37`, `FR-38`, and `FR-24` all read `DONE`.
- Epic story tags for `8.11`, `8.12`, `8.13`, `9.3`, `9.6`, `10.1`, `10.4`, and `4.8h` all read `DONE`.
- `sprint-status.yaml:124` records `9-6: done` (merged 9.6a and 9.6b); `sprint-status.yaml:71` records `3-9: done` (baseline ratified); `sprint-status.yaml:112` records `8-11: done`; `sprint-status.yaml:128` records `10-1: done`; `sprint-status.yaml:90` records `4-8h: done`.
- Story `4.8h` AC is clean; tool-call budgets and `top_k`/`max_passages` are in implementation hints, not AC.
- Story `10.1` AC is clean; the decode pipeline is in implementation hints, not AC.
- `check-docs-drift.py` passes.
- `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` confirms the NFR-8 baseline is ratified (`baseline_ratified: true`).

No critical or major issues remain. The remaining items are documentation hygiene and launch-gate ratification, not unimplemented capability.

### Critical Issues Requiring Immediate Action

*None.* No issue identified in this assessment blocks implementation or launch.

### Major Issues Requiring Attention

*None.* No major blockers remain.

### Remaining Non-Blocking Issues

1. **Stale `epics.md` top-level `## Requirements Inventory`**
   - `epics.md:35-47` still shows `[GAP]`/`[PARTIAL]` for `FR-38`, `FR-39`, `FR-40`, `FR-41`, `FR-24`, `FR-32`, `NFR-1b/1c/1d`, and `NFR-8` (`baseline ratification pending`), while the `### FR Coverage Map`, PRD, and `sprint-status.yaml` are reconciled.
   - These entries should be refreshed to match the story status tags and the ratified recall baseline.

2. **FR-32 PRD still carries `[BUILT — PARTIAL — dedupe/quality]`**
   - `prd.md:264-285` still marks dedupe/quality as partial, while the coverage map and `sprint-status.yaml` treat the relevant stories as `done`.
   - This is a documentation/labeling nuance, not a missing capability.

3. **Stale `sprint-status.yaml` comment**
   - `sprint-status.yaml:117` still references `9-6 partial`, which is now outdated.

4. **NFR-9 State B and NFR-10 baseline ratification remain open**
   - `NFR-9` State B (sync chat-mode) is gated on a clean Nowing e2e benchmark and `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` remains off.
   - `NFR-10` chat regression gate is covered but `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` has `baseline_ratified: false`.
   - These are launch gates, not implementation blockers, but they must be closed before broad production traffic.

### Recommended Next Steps

1. Refresh the `epics.md` top-level `## Requirements Inventory` (`epics.md:35-47`) and the `FR-32` PRD tag (`prd.md:264-285`) to match the reconciled coverage map and `sprint-status.yaml`.
2. Clean up the stale comment on `sprint-status.yaml:117` to reflect `9-6: done`.
3. Continue `nowing_evals` runs to ratify `NFR-10` (chat regression) and `NFR-9` State B thresholds.
4. Run `check-docs-drift.py` after any docs/README update to keep public docs aligned with code.

### Final Note

This final v3 assessment identified **no critical issues**, **no major blockers**, and **four minor non-blocking clusters** (stale `epics.md` top-level inventory, FR-32 PRD labeling nuance, stale `sprint-status.yaml` comment, and launch-gate ratification for NFR-9/NFR-10) across the six workflow categories. With the targeted `epics.md` coverage map now reconciled, the docs-drift check passing, and the launch gates tracked through `nowing_evals`, the project can proceed to implementation and public-repo readiness.
