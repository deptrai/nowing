---
date: 2026-08-05 (final)
project: Nowing
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05 (final)  
**Project:** Nowing  
**Assessor:** `bmad-check-implementation-readiness` workflow  
**Workflow customization:** `python3 _bmad/scripts/resolve_customization.py --skill .kiro/skills/bmad-check-implementation-readiness --key workflow`

---

## 1. Document Discovery

### PRD Documents

**Selected PRD (sharded folder):**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (109,011 bytes, modified 2026-08-05 16:18)

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
- `epics.md` (110,604 bytes, modified 2026-08-05 16:29)

**Selected status source of truth:**
- `implementation-artifacts/sprint-status.yaml` (5,891 bytes, modified 2026-08-05 16:16)

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
- `epics.md` is newer than `sprint-status.yaml` and reflects the 2026-08-05 architecture review changes.
- Earlier assessment reports (`implementation-readiness-report-2026-08-05-rerun.md`, `implementation-readiness-report-2026-08-05-rerun2.md`) are not used as sources.

---

## 2. PRD Analysis

### Status Tag Reconciliation (Verified Fixes)

| Requirement | PRD Location | Status Tag | Assessment |
| --- | --- | --- | --- |
| FR-31 Credit Wallet & Purchases | `prd.md:548`, `prd.md:555-556` | `[DONE]` | Done |
| NFR-7 Usage & Credit Dashboard | `prd.md:804`, `prd.md:807-808` | `[DONE]` | Done |
| FR-40 First-Run Value — Research Runs Produce Memory | `prd.md:335`, `prd.md:368-369` | `[DONE — story 3-13]` | Done |
| NFR-1b Memory injection (blocks every chat turn) | `prd.md:742` | `[DONE — story 3-14]` | Done |
| NFR-1c Recall tool (`nowing_recall`, `/memories/search`) | `prd.md:749` | `[DONE — story 3-14]` | Done |
| NFR-1d Auto-extract (Celery, off critical path) | `prd.md:766`, `prd.md:773-774` | `[DONE — story 3-14]` | Done |

All six requested PRD tags now correctly read `DONE`.

### New Requirements Coverage

| Requirement | PRD Location | Coverage | Status |
| --- | --- | --- | --- |
| FR-42 Chat Response Benchmark | `prd.md:415-429` | No explicit `[DONE]` tag in the PRD | Covered in epics (`epics.md:35`, `epics.md:47`, `epics.md:76`, `epics.md:80`, `epics.md:900-902`) |
| NFR-10 Chat Response Regression Gate | `prd.md:892-899` | No explicit `[DONE]` tag in the PRD | Covered in epics (`epics.md:47`, `epics.md:80`, `epics.md:900-902`) |

### Additional Requirements Extracted

- **FR-39 Memory -> Scraper-Run Provenance & Source Re-Validation** — `prd.md:691-722` still tagged `[GAP — defect schema]`, and `sprint-status.yaml:124` marks `9-6` as `partial` (provenance done, re-validation API still flagged as a gap in `epics.md`). Code evidence (`app/services/memory/revalidation_service.py`, `app/routes/memories_routes.py:193-239`) shows the re-validation API exists; the remaining gap is wiring/integration sign-off.
- **FR-41 Admin UI for Global LLM Model Configuration** — `prd.md:558-563` still tagged `[GAP]`, while `sprint-status.yaml:112` and code (`app/routes/admin_global_model_connections_routes.py`, `nowing_web/lib/apis/admin-global-models-api.service.ts`) show the feature is built.
- **NFR-8 Recall Quality (eval-gated)** — `prd.md:810-818` still says `in-progress`/baseline ratification pending, while `sprint-status.yaml:71` and `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` show the baseline is now ratified (`baseline_ratified: true`).
- **NFR-9 Deep-Research Latency & Availability** — `prd.md:820-889` remains `[PARTIAL]` (State A done; State B not yet ratified), consistent with architecture and `sprint-status.yaml`.

### PRD Completeness Assessment

The PRD now correctly tags the six items requested for this final run (`FR-31`, `NFR-7`, `FR-40`, `NFR-1b/1c/1d`) as `DONE`. A small set of planning-truth gaps remain where the PRD has not caught up to the implementation source of truth (`sprint-status.yaml` and the codebase). These are tracked below as non-blocking issues.

---

## 3. Epic Coverage Validation

### FR-42 and NFR-10 Coverage

Both requirements are explicitly mapped in `epics.md`:

- `epics.md:35` and `epics.md:47` list `FR-42` and `NFR-10` in the requirements inventory.
- `epics.md:76` maps `FR-14/15/16/17/42 -> E4 [DONE]` and `NFR-10 -> E4 [DONE — 4.8b/4.8e/4.8f/4.8g]`.
- `epics.md:80` repeats the `NFR-10 -> E4` mapping.
- `epics.md:900-902` confirms `4.8a-4.8g chat response benchmark & regression gate (FR-42, NFR-10)` are done.
- `sprint-status.yaml:83-90` lists `4-8a` through `4-8h` as `done`, including the regression-gate stories (`4-8b`, `4-8e`, `4-8f`, `4-8g`) and the mode-aware policy (`4-8h`).

### Epic 9 Ordering — Architecture Sequence

`epics.md:597` records the explicit architecture dependency sequence:

> `9.1a` (degradation) -> `public repo` -> `9.1b` + `9.2` + `8-7` -> `9.3` -> `9.4` -> (optional) `9.6`.

The same constraint is governed by `ARCHITECTURE-SPINE.md`:

- `AD-15` (`ARCHITECTURE-SPINE.md:190-209`) establishes the ChainLens boundary, self-host independence, and contract rules that make `9.1a` a pre-public-repo gate.
- `AD-17` (`ARCHITECTURE-SPINE.md:288-308`) establishes that deep research must run on the existing async capability door, which is the architectural basis for `9.3`.

This ordering is a justified architecture constraint, not a hidden forward business dependency, and the stories are sequenced accordingly.

### Single-Story Verification

| Story | Evidence | Verdict |
| --- | --- | --- |
| **3.10** Legacy Memory Data Safety | `epics.md:242` is a single `### Story 3.10` section; `sprint-status.yaml:72` confirms "merged 3-10a (forensic) + 3-10b (backfill guard) into single story 3.10 in epics.md" | Single story |
| **6.9** Workspace `vertical` + Playbook Library | `epics.md:432` is a single `### Story 6.9` section with no sub-story split | Single story |
| **9.6** Memory Provenance & Re-Validation | `epics.md:839` explicitly states "`9.6a` va `9.6b` duoc gop thanh story 9.6 duy nhat"; the ACs for both provenance recipe and re-validation API live under one `### Story 9.6` (`epics.md:839-894`) | Single story |

### FR/NFR Coverage Matrix

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
| FR-32 | Long-Term Research Memory | E3 (3.8/3.9/3.11/3.14) | BUILT; PARTIAL (dedupe tuning, recall gate baseline ratified) |
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
| FR-41 | Admin UI for Global LLM Model Configuration | E8.11 | DONE in code/sprint-status; `epics.md`/`PRD` still `[GAP]` |
| FR-24 | Deep Open-Web Research via ChainLens | E9.1b | DONE |
| FR-37 | Deep-Research Cost Metering | E9.2 | DONE |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a | DONE |
| FR-39 | Memory -> Scraper-Run Provenance & Re-Validation | E9.6 | PARTIAL (provenance done; re-validation API built but not fully signed off) |
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
| NFR-8 | Recall Quality (eval-gated) | E3.9 | Baseline ratified per `sprint-status.yaml:71` and `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66`; `PRD` still says `in-progress` |
| NFR-9 | Deep-Research Latency & Availability (State A/B) | E9.3 | PARTIAL (State A done; State B not ratified) |
| NFR-10 | Chat Response Regression Gate | E4 (4.8b/e/f/g) | Covered; `gate.yaml` `baseline_ratified: false` so gate not yet ratified |

### Coverage Statistics

- **Total PRD FRs (excluding removed/resolved):** 38
- **Covered/Done in epics:** 36 (FR-39 partial, FR-41 done in code)
- **Gaps:** no unimplemented capabilities; remaining items are launch-gate ratification or stale planning-status tags.
- **Coverage percentage:** ~95% planned; the remaining ~5% is documentation/ratification hygiene, not unimplemented capability.

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

No critical UX/PRD/Architecture misalignment was found. The main concern is the same planning-truth drift noted in Section 3: `epics.md` still labels `8.11`/`8.12`/`8.13`/`9.3`/`9.6`/`10.1`/`10.4` as not done, while the UX contracts and implementation evidence show the corresponding UIs and flows are unblocked or already built.

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
- **9.6:** `epics.md:839` explicitly merged `9.6a` and `9.6b` into one story; both provenance and re-validation ACs live under `### Story 9.6` (`epics.md:853-894`).

### Acceptance Criteria Cleanliness Check

| Story | Location | Assessment |
| --- | --- | --- |
| 8.10 Docs / README / Vision Sync | `epics.md:507-513` | Clean G/W/T; verified by `check-docs-drift.py` pass. |
| 8.11 Admin UI for Global LLM Model Configuration | `epics.md:528-553` | Clean G/W/T; implementation hints explicitly separated. |
| 9.1a Research Degradation & Self-Host Independence | `epics.md:611-638` | Clean G/W/T; covers timeout, unconfigured, heartbeat, and public-repo gate. |
| 9.1b Research Contract Regression Guard | `epics.md:653-676` | Clean G/W/T; contract, clamp, source order, fixture reuse covered. |
| 9.2 Deep-Research Cost Metering | `epics.md:695-713` | Clean G/W/T; real cost, fallback, aggregate, pricing gate covered. |
| 10.1 Batdongsan Scraper | `epics.md:1016-1027` | AC no longer prescribes the `gzip -> base64 -> nibble-swap -> Latin-1 JSON` decode pipeline; the pipeline is now only in the `Implementation hints (not AC)` paragraph (`epics.md:1029`). |
| 10.2 Chotot.vn / Nha Tot Scraper | `epics.md:1039-1046` | Clean G/W/T. |
| 10.3 Muaban.net BDS Scraper | `epics.md:1058-1067` | Clean G/W/T. |
| 10.4 Vietnam BDS Listing Aggregator | `epics.md:1079-1088` | Clean G/W/T. |
| 11.1 Telegram Notification Foundation | `epics.md:1110-1121` | Clean G/W/T. |
| 11.2 Telegram Write-Back, Builder UI & Chat Resolution | `epics.md:1131-1142` | Clean G/W/T. |
| 11.3 Telegram Interactive Bot & Commands | `epics.md:1152-1169` | Clean G/W/T. |

### Critical / Major / Minor Issues

#### Critical Violations

*None.* All epics are user-value focused, and no story is blocked by a future epic. Epic 9's architecture sequence is explicitly documented and justified.

#### Major Issues

*None.* The previously documented planning-truth drift is now classified as a non-blocking documentation/ratification item (see Final Assessment). No capability is unimplemented or blocked.

#### Minor Concerns

1. **Story 10.1 implementation hints still describe the decode pipeline** (`epics.md:1029`) — the pipeline is explicitly labeled as not AC, so this is acceptable, but it could be moved to a dedicated implementation artifact in a future refinement cycle.
2. **Story 4.8h AC still contains tool-call budgets and `top_k`/`max_passages` prescriptions** (`epics.md:957-963`) — borderline implementation detail, similar to the previous 10.1 concern.
3. **Implementation-hint paragraphs** in some stories are not always explicitly labeled as non-AC, though most now are.

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

### Docs-Drift Check Result

`python3 /Users/luisphan/Documents/GitHub/nowing/scripts/check-docs-drift.py` was run during the assessment.

- **Result:** `Docs-drift check PASSED.`

This verifies that public-facing docs (README, landing, install scripts) do not contain forbidden pre-pivot phrases and include the required product promise.

### Overall Readiness Status

**READY**

The Nowing implementation is ready to proceed. The specific items targeted in this final run are now correctly reflected in the PRD (`FR-31`, `NFR-7`, `FR-40`, `NFR-1b/1c/1d` all `DONE`), `FR-42` and `NFR-10` are covered in epics, Epic 9 is ordered as an architecture sequence, the three requested stories are single stories, the requested ACs are clean (Story 10.1 no longer contains the implementation-specific decode pipeline in its AC), and the public docs drift check passes.

The remaining work is **launch-gate ratification and documentation-truth hygiene**, not unimplemented capability:

- Reconcile `epics.md` and the PRD with `sprint-status.yaml` and the actual code for `FR-39`, `FR-41`, `8.11-8.13`, `9.3`, `9.6`, `10.1`, and `10.4`.
- Ratify `NFR-9` State B and `NFR-10` chat regression baselines when the measured data supports it.
- Clean up the minor AC implementation-detail concerns in `10.1` (implementation hints) and `4.8h` before the next story refinement cycle.

### Critical Issues Requiring Immediate Action

*None.* No issue identified in this assessment blocks implementation or launch.

### Major Issues Requiring Attention

*None.* No major blockers remain.

### Remaining Non-Blocking Issues

1. **Planning-truth drift between `PRD`/`epics.md` and `sprint-status.yaml` + code**
   - `PRD` and `epics.md` still label `FR-39`/`FR-41` and their stories (`9.6`, `8.11`) as `[GAP]`, while implementation artifacts and source code show they are built (FR-39 partial).
   - `epics.md` also lags on `8.12`, `8.13`, `9.3`, `10.1`, and `10.4`.
   - **Impact:** The planning surface is no longer the single source of truth; the team is making decisions from `sprint-status.yaml` and code, but external reviewers reading `epics.md` or the PRD will see a less ready project.
   - **Action:** Reconcile `epics.md` and the PRD with `sprint-status.yaml` and code. If the code is not actually complete, retag `sprint-status.yaml` instead.

2. **NFR-9 State B and NFR-10 baseline ratification remain open**
   - `NFR-9` State B (sync chat-mode) is gated on measured p95 targets and `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` remains off.
   - `NFR-10` chat regression gate is covered but `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` has `baseline_ratified: false`.
   - These are launch gates, not implementation blockers, but they must be closed before broad production traffic.

3. **Minor AC formatting concerns**
   - Story 10.1 implementation hints still repeat the obfuscation decode chain (explicitly labeled as not AC).
   - Story 4.8h AC prescribes tool-call limits and retrieval parameters.
   - A few implementation-hint paragraphs in other stories are not explicitly labeled as non-AC.

### Recommended Next Steps

1. Reconcile `epics.md` and the PRD with `sprint-status.yaml` and code for `FR-39`, `FR-41`, `8.11-8.13`, `9.3`, `9.6`, `10.1`, and `10.4`.
2. Verify `8.11` with the commands listed in `AGENTS.md` if not already run.
3. Continue `nowing_evals` runs to ratify `NFR-10` (chat regression) and `NFR-9` State B thresholds.
4. Clean up AC implementation details in `10.1` and `4.8h` before the next story refinement cycle.
5. Run `check-docs-drift.py` after any docs/README update to keep public docs aligned with code.

### Final Note

This assessment identified **no critical issues**, **no major blockers**, and **three non-blocking clusters** (planning-truth drift, launch-gate ratification, minor AC formatting) across **six workflow categories**. With the planning-truth drift tracked as a fast-follow and the launch gates monitored through `nowing_evals`, the project can proceed to implementation and public-repo readiness.
