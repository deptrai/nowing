---
date: 2026-08-05 (final v6)
project: Nowing
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-final-assessment"]
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-05 (final v6)  
**Project:** Nowing  
**Assessor:** `bmad-check-implementation-readiness` workflow (final verification + ChainLens 34.1 / async-only / `estimated`+`resolvedMode` parser confirmation)  
**Workflow customization:** `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-check-implementation-readiness --key workflow`

---

## 1. Document Discovery

### PRD Documents

**Selected PRD (sharded folder):**
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (109,692 bytes, modified 2026-08-05 18:02)

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
- `epics.md` (110,951 bytes, modified 2026-08-05 18:05)

**Selected status source of truth:**
- `implementation-artifacts/sprint-status.yaml` (150 lines, modified 2026-08-05)

### UX Design Documents

**Selected UX contracts (sharded folder `ux-designs/ux-Nowing-2026-07-22/`):**
- `ux-contract-async-deep-research.md`
- `ux-contract-admin-global-model-config.md`
- `ux-contract-chat-benchmark.md`
- `ux-contract-first-run-onboarding.md`
- `ux-contract-sync-offline-indicator.md`
- `ux-contract-usage-dashboard.md`

### Issues Found

- No duplicate whole/sharded versions were found for PRD, architecture, epics, or UX.
- `epics.md` and `prd.md` were both modified on 2026-08-05 and reflect the ChainLens 34.1 commitment, async-only contract, and `estimated`/`resolvedMode` parser.
- `sprint-status.yaml` was updated on 2026-08-05; stories `9-2` and `9-3` explicitly reference the ChainLens 34.1 target date, `estimated`/`resolvedMode`, and the quality/deep async-only rule.
- The `epics.md` `### FR Coverage Map` and Epic 9 summary were missing `resolvedMode` in the story 9.2 parser summary. This was corrected during the v6 run (`epics.md:75`, `epics.md:129`, `epics.md:691`).
- No critical or major document conflicts were identified.

---

## 2. PRD Analysis

### ChainLens 34.1 Commitment, Async-Only Contract, and Parser Confirmation

The PRD explicitly records the new ChainLens dependency and the Nowing parser contract:

| Requirement | PRD Location | Commitment / Contract | Assessment |
| --- | --- | --- | --- |
| FR-37 Deep-Research Cost Metering | `prd.md:622` | `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` | Done |
| `done.usage.estimated` + `done.resolvedMode` parser | `prd.md:632`, `prd.md:645-646` | Parser reads `estimated` (sets `cost_basis`) and `resolvedMode` (for latency metrics / UX routing) | Done |
| ChainLens 34.1 full-pipeline cost target | `prd.md:638-639`, `prd.md:649`, `prd.md:891` | Story 34.1 in-progress, target completion **2026-08-19**; `estimated: false` when full-pipeline; canonical contract includes `done.resolvedMode` + `done.usage.{promptTokens, completionTokens, totalTokens, model, costDollars, estimated}` | Reflected |
| NFR-9 State A / State B gate | `prd.md:887-895` | **State A is default** (`DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED = false`). **Sync chat-mode only for `speed`/`balanced`**; **`quality` / `deep-research` / `deep-reasoning` = async-only in chat**. State B ratification requires ChainLens 34.1 full-pipeline cost + rerun 29-5 + Nowing e2e p95 `balanced` ≤ 30s. | Reflected |

### PRD Completeness Assessment

The PRD is complete for the current MVP scope. The targeted items are reconciled with `sprint-status.yaml` and the codebase. The remaining PRD tags are deliberate:

- **NFR-9** (`prd.md:818-888`) remains `[PARTIAL]` — State A (async deliverable) is done; State B (sync chat-mode) is a launch gate that requires ChainLens 34.1 full-pipeline cost (target 2026-08-19), a rerun of 29-5, and a Nowing e2e benchmark showing p95 `balanced` ≤ 30s before `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` is enabled.
- **NFR-10** (`prd.md:890-897`) is a deploy gate; `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` still has `baseline_ratified: false`, so the gate is not yet ratified.
- Post-MVP items (non-semantic memory types, dedupe threshold tuning, memory lifecycle UI) remain correctly labeled as non-MVP.

No new unimplemented capabilities were found in the PRD.

---

## 3. Epic Coverage Validation

### Targeted Story Status Tags (Verified Fixes)

| Story | Epic Location | Status Tag | Assessment |
| --- | --- | --- | --- |
| 8.11 Admin UI for Global LLM Model Configuration | `epics.md:528` | `[DONE per sprint-status: 8-11]` | Done |
| 8.12 Workspace Limits | `epics.md:565` | `[DONE per sprint-status: 8-12]` | Done |
| 8.13 PostHog Product Analytics | `epics.md:578` | `[DONE per sprint-status: 8-13]` | Done |
| 9.2 Deep-Research Cost Metering | `epics.md:686` | `[DONE — P0, parser + fallback in place; waits ChainLens 34.1 full-pipeline cost, target 2026-08-19]` | Done |
| 9.3 Latency Budget & State A→B Gate | `epics.md:728` | `[DONE per sprint-status: 9-3]` | Done |
| 9.6 Memory Provenance & Re-Validation | `epics.md:839` | `[DONE per sprint-status: 9-6]` | Done |
| 10.1 Batdongsan.com.vn Scraper | `epics.md:1016` | `[DONE per sprint-status: 10-1]` | Done |
| 10.4 Vietnam BĐS Listing Aggregator & Cross-Source Trust Score | `epics.md:1073` | `[DONE per sprint-status: 10-4]` | Done |
| 4.8h Mode-Aware Chat Policy for Latency/Cost | `epics.md:951-962` | Clean G/W/T; done | Done |
| 10.2 Chotot.vn / Nha Tot Scraper | `epics.md:1039` | `[DONE per sprint-status: 10-2]` | Done |
| 10.3 Muaban.net BDS Scraper | `epics.md:1058` | `[DONE per sprint-status: 10-3]` | Done |
| 11.1 Telegram Notification Foundation | `epics.md:1110` | `[done]` | Done |
| 11.2 Telegram Write-Back, Builder UI & Chat Resolution | `epics.md:1131` | `[done]` | Done |
| 11.3 Telegram Interactive Bot & Commands | `epics.md:1152` | `[done]` | Done |

### ChainLens 34.1 / Async-Only / Parser Coverage

The epic-level coverage map and sprint-status now explicitly tie these three items to the implementation:

- **`epics.md:75`** — FR-37 → E9.2 `[DONE, P0, parser done.usage.costDollars + done.usage.estimated + done.resolvedMode + fallback 60k micros; ...]`
- **`epics.md:129`** — Epic 9 summary repeats the parser fields and the quality/deep async-only rule, and notes the ChainLens 34.1 full-pipeline cost + Nowing e2e p95 `balanced` ≤ 30s gate for State B.
- **`epics.md:686-691`** — Story 9.2 header and implementation context state that the parser reads `costDollars`, `estimated`, and `resolvedMode` from `done.usage`, and that ChainLens 42-1 is writer-only (`estimated: true`) while ChainLens 34.1 (target 2026-08-19) will provide full-pipeline cost (`estimated: false`).
- **`epics.md:776-780`** — Story 9.3 AC: sync chat-mode only for `speed`/`balanced`; `quality`/`deep-research`/`deep-reasoning` remain async-only; State B ratification requires ChainLens 34.1 full-pipeline cost (target 2026-08-19) and Nowing e2e p95 `balanced` ≤ 30s.
- **`sprint-status.yaml:120`** — `9-2: done # parse costDollars + estimated + resolvedMode from ChainLens SSE done.usage (FR-37); fallback 60k micros only when missing; ChainLens 34.1 in-progress for full-pipeline cost (target 2026-08-19)`
- **`sprint-status.yaml:121`** — `9-3: done # State A async default; sync gated to speed/balanced; quality/deep async-only; State B ratification pending ChainLens 34.1 + Nowing e2e p95 balanced ≤30s`

### FR/NFR Coverage Map Verification

The stale coverage map issue called out in previous reports (`epics.md:75-86`) has been fully resolved. The current `### FR Coverage Map` (`epics.md:73-84`) now includes the `resolvedMode` field alongside `costDollars` and `estimated` for FR-37/E9.2, and the async-only/State B gate language for NFR-9/E9.3.

### FR/NFR Coverage Matrix

The overall coverage picture remains aligned between the PRD, the `epics.md` `### FR Coverage Map`, and `sprint-status.yaml`.

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
| FR-42 | Chat Response Benchmark | E4 (4.8a-h) | DONE |
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
| FR-37 | Deep-Research Cost Metering | E9.2 | DONE; parser reads `costDollars`, `estimated`, `resolvedMode`; waits ChainLens 34.1 full-pipeline cost (target 2026-08-19) |
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
| NFR-9 | Deep-Research Latency & Availability (State A/B) | E9.3 | PARTIAL — State A done; State B launch gate open; quality/deep async-only contract in place; ChainLens 34.1 target 2026-08-19 |
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

---

## 5. Epic Quality Review

### Epic-by-Epic Quality Summary

| Epic | User Value | Independence | Story Sizing | AC Format (G/W/T) | No Forward Deps | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| E1 Identity, Auth & Workspace RBAC | PASS | PASS | PASS | PASS | PASS | Brownfield; done. |
| E2 Connectors | PASS | PASS | PASS | PASS | PASS | 2.6-2.9 are `ready-for-dev` expansion; no forward dependencies. |
| E3 Knowledge Base + Long-Term Memory | PASS | PASS | PASS | PASS | PASS | 3.13/3.14 done; 3.15/3.16 `ready-for-dev`. |
| E4 Chat & Agents | PASS | PASS | PASS | PASS | PASS | 4.8a-h done; 4.7/4.8d `ready-for-dev`. |
| E5 Deliverables | PASS | PASS | PASS | PASS | PASS | Done. |
| E6 Automations | PASS | PASS | PASS | PASS | PASS | 6.6/6.7/6.9 gated after BDS pilot; no forward technical dependencies. |
| E7 Multi-surface Clients | PASS | PASS | PASS | PASS | PASS | 7.4/7.7 `ready-for-dev`; core clients done. |
| E8 Billing / Usage | PASS | PASS | PASS | PASS | PASS | 8.10-8.13 done. |
| E9 Deep Research | PASS | WARN | PASS | PASS | PASS | 9.1a -> 9.1b/9.2/9.3 -> 9.4 is architecture sequence, not business forward dep. |
| E10 Connector & Scraper Expansion | PASS | PASS | PASS | PASS | PASS | 10.1-10.4 done. |
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
- **10.1/10.2/10.3/10.4:** All are marked `done` in both `epics.md` and `sprint-status.yaml` (`sprint-status.yaml:127-132`).
- **11.1/11.2/11.3:** All are marked `done` in both `epics.md` and `sprint-status.yaml` (`sprint-status.yaml:134-138`).

### Acceptance Criteria Cleanliness Check

| Story | Location | Assessment |
| --- | --- | --- |
| 4.8h Mode-Aware Chat Policy for Latency/Cost | `epics.md:951-962` | Clean G/W/T; tool-call budget and `top_k`/`max_passages` details in implementation hints. |
| 8.10 Docs / README / Vision Sync | `epics.md:507-513` | Clean G/W/T; verified by `check-docs-drift.py` pass. |
| 8.11 Admin UI for Global LLM Model Configuration | `epics.md:528-553` | Clean G/W/T; implementation hints explicitly separated. |
| 9.1a Research Degradation & Self-Host Independence | `epics.md:611-638` | Clean G/W/T; covers timeout, unconfigured, heartbeat, and public-repo gate. |
| 9.1b Research Contract Regression Guard | `epics.md:653-676` | Clean G/W/T; contract, clamp, source order, fixture reuse covered. |
| 9.2 Deep-Research Cost Metering | `epics.md:686-725` | Clean G/W/T; real cost, `estimated`, `resolvedMode`, fallback, pricing gate covered. |
| 9.3 Latency Budget & State A→B Gate | `epics.md:728-796` | Clean G/W/T; State A async default, speed/balanced sync, quality/deep async-only, ChainLens 34.1 ratification gate. |
| 10.1 Batdongsan Scraper | `epics.md:1016-1027` | AC no longer prescribes the decode pipeline; pipeline is only in implementation hints. |
| 10.2 Chotot.vn / Nha Tot Scraper | `epics.md:1039-1046` | Clean G/W/T. |
| 10.3 Muaban.net BDS Scraper | `epics.md:1058-1067` | Clean G/W/T. |
| 10.4 Vietnam BĐS Listing Aggregator | `epics.md:1079-1088` | Clean G/W/T. |
| 11.1 Telegram Notification Foundation | `epics.md:1110-1121` | Clean G/W/T. |
| 11.2 Telegram Write-Back, Builder UI & Chat Resolution | `epics.md:1131-1142` | Clean G/W/T. |
| 11.3 Telegram Interactive Bot & Commands | `epics.md:1152-1169` | Clean G/W/T. |

### Epic Status Reconciliation

The final v6 run verified that the epic status convention between `sprint-status.yaml` and `epics.md` remains reconciled:

| Epic | `sprint-status.yaml` | `epics.md` | Reconciled |
| --- | --- | --- | --- |
| E3 | `epic-3: done` (`sprint-status.yaml:68`) | DONE (`epics.md:103`) | Yes |
| E4 | `epic-4: done` (`sprint-status.yaml:81`) | DONE (`epics.md:107`) | Yes |
| E7 | `epic-7: done` (`sprint-status.yaml:101`) | DONE (`epics.md:121`) | Yes |
| E9 | `epic-9: done` (`sprint-status.yaml:117`) | DONE (`epics.md:128`) | Yes |

All epics now carry the `done` status in both the implementation tracking file and the planning epic document, with inline comments documenting the remaining `ready-for-dev` expansion stories and the State B ratification gate.

### Critical / Major / Minor Issues

#### Critical Violations

*None.* All epics are user-value focused, and no story is blocked by a future epic. Epic 9's architecture sequence is explicitly documented and justified.

#### Major Issues

*None.* The previously documented planning-truth drift in the `epics.md` `### FR Coverage Map` and top-level `## Requirements Inventory` is fully resolved. The `resolvedMode` field was added to the story 9.2 parser summary during this run so the planning documents fully reflect the PRD contract.

#### Minor Concerns

1. **Launch-gate ratification still open for NFR-9 and NFR-10**
   - NFR-9 State B requires ChainLens 34.1 full-pipeline cost (target 2026-08-19), a rerun of 29-5, and a clean Nowing e2e benchmark showing p95 `balanced` ≤ 30s before `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` is enabled.
   - NFR-10 chat regression gate has thresholds in `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` but `baseline_ratified: false`.
   - These are launch gates, not implementation blockers, but they must be closed before broad production traffic.

2. **Per-mode sync enforcement is a State-B gate item, not yet in code**
   - The PRD (`prd.md:889`) and `epics.md` (`epics.md:776`) specify that sync chat-mode is only allowed for `speed`/`balanced`; `quality`/`deep-research`/`deep-reasoning` remain async-only.
   - The current `agent.py:177-180` and `rest.py:201-205` implement a global `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` flag that forces `chainlens.research` async when off, but do not yet add mode-aware gating when the flag is on.
   - Because the flag defaults to `False` (`config/__init__.py:1012-1013`) and State B requires explicit ratification, this is a non-blocking follow-up to be implemented before State B is enabled.

3. **Post-MVP expansion items remain tracked as `ready-for-dev`**
   - 3.15/3.16, 4.7/4.8d, 7.4/7.7, 6.6/6.7/6.9 are deliberate `ready-for-dev` or pilot-gated expansions. They are not launch blockers but should be revisited after MVP.

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

A targeted final v6 verification script was executed against the PRD, `epics.md`, `sprint-status.yaml`, and the ChainLens research executor.

- **Result:** `Targeted v6 verification: all checks passed`
- **All targeted checks passed.**

It confirmed:

- `prd.md:632` records that the parser reads `done.usage.estimated` and `done.resolvedMode`.
- `prd.md:639` records the **ChainLens 34.1** commitment: in-progress, target completion **2026-08-19**, canonical contract `done.resolvedMode` + `done.usage.{promptTokens, completionTokens, totalTokens, model, costDollars, estimated}` with `estimated: false` for full-pipeline cost.
- `prd.md:889` states **`quality` / `deep-research` / `deep-reasoning` = async-only in chat** and `mode=auto` resolves via `resolvedMode`.
- `epics.md:75` FR Coverage Map now lists `done.usage.costDollars` + `done.usage.estimated` + `done.resolvedMode` + fallback 60k micros for FR-37 → E9.2.
- `epics.md:129` Epic 9 summary includes the parser fields, the async-only contract, and the ChainLens 34.1 State B gate.
- `epics.md:691` story 9.2 implementation context states the parser reads `costDollars`, `estimated`, and `resolvedMode` from `done.usage`, and that ChainLens 34.1 (target 2026-08-19) will emit full-pipeline cost with `estimated: false`.
- `epics.md:776-778` story 9.3 AC defines the speed/balanced-only sync rule, the quality/deep async-only rule, and the ChainLens 34.1 ratification dependency.
- `sprint-status.yaml:120` records `9-2: done` with `costDollars` + `estimated` + `resolvedMode` parser and ChainLens 34.1 target 2026-08-19.
- `sprint-status.yaml:121` records `9-3: done` with State A async default, sync gated to `speed`/`balanced`, `quality`/`deep` async-only, and State B ratification pending ChainLens 34.1 + Nowing e2e p95 `balanced` ≤ 30s.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:457-518` (`_extract_cost`) parses `costDollars`, `estimated`, and `resolvedMode` from the terminal SSE `done`/`usage` frame and sets `cost_basis` to `estimated` or `actual`.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py:132` defines `cost_basis: Literal["actual", "estimated", "fallback"]`, and `schemas.py:136` defines `resolved_mode: str` on `ResearchOutput`.
- `nowing_backend/app/config/__init__.py:995-996` defaults `DEFAULT_RESEARCH_MODE` to `balanced`, and `config/__init__.py:1012-1013` defaults `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` to `False`, enforcing State A.
- `nowing_backend/app/capabilities/core/access/agent.py:177-180` and `rest.py:201-205` force `chainlens.research` to async when `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` is `False`.
- `check-docs-drift.py` passes.

### Overall Readiness Status

**READY**

The Nowing implementation is ready to proceed. The specific items targeted in this final v6 run are now correctly reflected:

- The **ChainLens 34.1 commitment** (target 2026-08-19) is recorded in the PRD (`prd.md:638-639`, `prd.md:891`, `prd.md:895`), `epics.md` (`epics.md:686`, `epics.md:691`, `epics.md:778`), and `sprint-status.yaml` (`sprint-status.yaml:120-121`).
- The **async-only contract for `quality` / `deep-research` / `deep-reasoning`** is in the PRD (`prd.md:889`), `epics.md` (`epics.md:776`, `epics.md:129`), and `sprint-status.yaml` (`sprint-status.yaml:121`).
- The **estimated/resolvedMode parser** is in the PRD (`prd.md:632`, `prd.md:645-646`), `epics.md` (`epics.md:75`, `epics.md:129`, `epics.md:691`), `sprint-status.yaml` (`sprint-status.yaml:120`), and the codebase (`executor.py:457-518`, `schemas.py:132`, `schemas.py:136`).
- `epics.md` was updated during this run to add `resolvedMode` to the story 9.2 parser summary so all three planning documents are consistent.
- `check-docs-drift.py` passes.
- `nowing_evals/src/nowing_evals/suites/memory/recall/gate.yaml:66` confirms the NFR-8 baseline is ratified (`baseline_ratified: true`).

**No critical or major issues remain.** The remaining items are launch-gate ratification, one minor code follow-up for per-mode sync enforcement before State B, and post-MVP `ready-for-dev` expansions — none of which are unimplemented capability.

### Critical Issues Requiring Immediate Action

*None.* No issue identified in this assessment blocks implementation or launch.

### Major Issues Requiring Attention

*None.* No major blockers remain. The ChainLens 34.1, async-only, and parser commitments are now reflected consistently across PRD, epics, and sprint-status.

### Remaining Non-Blocking Issues

1. **Launch-gate ratification still open for NFR-9 and NFR-10**
   - NFR-9 State B (sync chat-mode) is gated on ChainLens 34.1 full-pipeline cost (target 2026-08-19), a rerun of 29-5 with `deepseek-v3.2`, and a clean Nowing e2e benchmark showing p95 `balanced` ≤ 30s.
   - NFR-10 chat regression gate has thresholds in `nowing_evals/src/nowing_evals/suites/chat/regression/gate.yaml:1` but `baseline_ratified: false`.
   - These are launch gates, not implementation blockers, but they must be closed before broad production traffic.

2. **Per-mode sync enforcement for State B is not yet in code**
   - The PRD and epics state that sync chat-mode is only allowed for `speed`/`balanced`, while `quality`/`deep-research`/`deep-reasoning` remain async-only.
   - The current `agent.py:177-180` and `rest.py:201-205` only check the global `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED` flag. Mode-aware gating must be added before State B is enabled. Because the flag is `False` by default, this is a non-blocking follow-up.

3. **Ready-for-dev expansion stories remain on the backlog**
   - 3.15/3.16, 4.7/4.8d, 6.6/6.7/6.9, 7.4/7.7 are tracked as `ready-for-dev` or pilot-gated. None are required for the current MVP launch.

### Recommended Next Steps

1. Continue `nowing_evals` runs to ratify `NFR-10` (chat regression) and `NFR-9` State B thresholds once ChainLens 34.1 lands (target 2026-08-19).
2. Before enabling `DEEP_RESEARCH_SYNC_CHAT_MODE_ENABLED`, add mode-aware sync gating in `agent.py` and `rest.py` so only `speed`/`balanced` may run synchronously in chat.
3. Run `check-docs-drift.py` after any docs/README update to keep public docs aligned with code.
4. Pick up `ready-for-dev` expansion stories based on pilot feedback and post-MVP prioritization.

### Final Note

This final v6 assessment identified **no critical issues**, **no major blockers**, and **three minor non-blocking clusters** (launch-gate ratification, per-mode sync enforcement before State B, and `ready-for-dev` expansions) across the six workflow categories. The PRD, `epics.md`, and `sprint-status.yaml` now consistently reflect the ChainLens 34.1 commitment, the async-only contract for `quality`/`deep`, and the `estimated`/`resolvedMode` parser. The `docs-drift` check passes, and all launch gates are explicitly tracked. The project can proceed to implementation and public-repo readiness.
