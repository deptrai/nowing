---
stepsCompleted:
  - document-discovery
  - prd-analysis
  - epic-coverage-validation
  - ux-alignment
  - epic-quality-review
  - final-assessment
status: READY
prd_selected: _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
epics_selected: _bmad-output/planning-artifacts/epics.md
architecture_selected: _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md
ux_selected: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/*.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-09 (re-run; supersedes 2026-08-08 assessment)  
**Project:** Nowing  
**Assessor:** bmad-check-implementation-readiness  

---

## 1. Document Discovery

### Selected Documents

| Type | Selection | Notes |
|---|---|---|
| PRD | `prds/prd-Nowing-2026-07-22/prd.md` | 138,238 bytes, updated 2026-08-08; SCP 2026-08-08 amendments applied |
| Epics & Stories | `epics.md` | 242,426 bytes, updated 2026-08-09; Epic 12.4 and Epic 14–17 re-scoped to `chainlens-research` |
| Architecture | `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | 110,067 bytes, updated 2026-08-09; AD-34/AD-35 added |
| UX Contracts | `ux-designs/ux-Nowing-2026-07-22/*.md` | 12 active contracts + 1 archived; `ux-contract-async-deep-research.md` expanded |

### Duplicate / Superseded Files

- Architecture review files `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6/v7.md` are superseded; **v8** is retained as a review companion but the `ARCHITECTURE-SPINE.md` is the canonical design source.
- `architecture/unified-scope-chainlens-research-nowing-2026-08-08.md` is a narrow scoping doc for the 2026-08-08 SCP and is treated as reference, not the primary architecture.
- `epic-11-architecture-review-2026-08-03.md` is an older review artifact, superseded by `epics.md`.
- `ux-designs/ux-Nowing-2026-07-22/archive/ux-contract-canonical-entity.md` is archived because Epic 13 was dropped per SCP 2026-08-08.

---

## 2. PRD Analysis

- Total FRs extracted: **63**
- Total NFRs extracted: **12**
- Full extracted text: see `prd-requirements-extracted-2026-08-08.md` and `prd-requirements-2026-08-08.json`.

### Functional Requirements Summary

| FR | Title | PRD Status |
|---|---|---|
| FR-1 | User Authentication | — |
| FR-2 | API Access for External Clients | — |
| FR-3 | Workspace Lifecycle | — |
| FR-4 | Workspace Invites & Memberships | — |
| FR-10 | RBAC với ba system roles | — |
| FR-6 | Built-in Scraper Connectors | — |
| FR-7 | External OAuth Connectors | — |
| FR-8 | External MCP Connectors | — |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | PROPOSED |
| FR-44 | TopCV Scraper (Vietnam Job Market) | PROPOSED |
| FR-45 | ITviec Scraper (Vietnam Job Market) | PROPOSED |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | PROPOSED — re-scoped to `chainlens-research` |
| FR-47 | PII Redaction for Job Data | PROPOSED |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) | REMOVED |
| FR-49 | News Aggregation (Epic 14) | RE-SCOPED to `chainlens-research` |
| FR-50 | Financial Data Integration (Epic 15) | RE-SCOPED to `chainlens-research` |
| FR-51 | Company Data Integration (Epic 16) | RE-SCOPED to `chainlens-research` |
| FR-52 | E-commerce Intelligence (Epic 17) | RE-SCOPED to `chainlens-research` |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | DONE |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | — |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | DONE |
| FR-56 | Public Agent-Chat API for Vertical Clients | PROPOSED |
| FR-57 | Agent Registry | PROPOSED |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | PROPOSED |
| FR-59 | Gap-Fill Trigger via chainlens-research | PROPOSED |
| FR-60 | Private Data Provider (NowingPrivateProvider) | PROPOSED |
| FR-61 | Cross-Project Service Auth & Cost Allocation | PROPOSED |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | PROPOSED |
| FR-8.1 | Exa MCP Search Connector | DONE |
| FR-9 | Document Upload, Parse & Index | — |
| FR-11 | Folders & Document Management | — |
| FR-12 | Hybrid Search over Knowledge Base | — |
| FR-13 | Citation Panel for Knowledge-base Chunks | — |
| FR-32 | Long-Term Research Memory | DONE |
| FR-33 | Research Continuity | — |
| FR-34 | Memory Correction | — |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | RESOLVED |
| FR-40 | First-Run Value — Research Runs Produce Memory | DONE |
| FR-5 | AI File Sorting (REMOVED) | — |
| FR-14 | Chat Threads & Messages | — |
| FR-15 | Multi-agent Runtime with Tools | — |
| FR-16 | Real-time Collaborative Chat | — |
| FR-17 | Anonymous Chat with Quota | — |
| FR-42 | Chat Response Benchmark | — |
| FR-21 | Report Generation & Export | — |
| FR-22 | Podcast & Video Presentation | — |
| FR-23 | Image Generation | — |
| FR-18 | Automation Action Types | DONE |
| FR-19 | Automation Triggers | — |
| FR-20 | Automation Runs & Retries | — |
| FR-35 | Memory-Driven Automations | DONE |
| FR-25 | Web Client (Next.js) | — |
| FR-26 | Desktop Client (Electron) | — |
| FR-27 | Browser Extension (Plasmo) | — |
| FR-28 | Obsidian Plugin | — |
| FR-29 | MCP Server | — |
| FR-30 | Token Usage Tracking | — |
| FR-31 | Credit Wallet & Purchases | — |
| FR-41 | Admin UI cho Global LLM Model Configuration | DONE |
| FR-24 | Deep Open-Web Research via ChainLens Engine | DONE |
| FR-37 | Deep-Research Cost Metering | DONE |
| FR-38 | Research Degradation & Self-Host Independence | DONE |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | DONE |

### Non-Functional Requirements Summary

| NFR | Title | PRD Status |
|---|---|---|
| NFR-1 | Performance | — |
| NFR-2 | Security & Auth | — |
| NFR-3 | Observability | — |
| NFR-4 | Reliability | — |
| NFR-5 | Multi-tenancy Isolation | — |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients | PROPOSED |
| NFR-6 | Citation Full-Editor Highlight | DONE |
| NFR-7 | Usage & Credit Dashboard | DONE |
| NFR-8 | Recall Quality (eval-gated) | DONE |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | — |
| NFR-10 | Chat Response Regression Gate | — |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | PROPOSED |

### Additional Requirements / Constraints

- Three non-goals (NG-1/2/3) are permanently closed and block owned web index, Exa-style data sales, and ChainLens standalone productization.
- Open questions OQ-1/OQ-2 are intentionally deferred to backlog; OQ-3 (memory retention/right-to-delete) remains a legal gap before GA cloud; OQ-4/OQ-5/OQ-6 are resolved; OQ-7 answered; OQ-8 (HR vertical) legal review completed 2026-08-08.
- PRD contains reality-correction notes confirming memory layer, ChainLens engine boundary, and ecosystem alignment from 2026-08-08.
- FR-46/49/50/51/52 and FR-48 are explicitly re-scoped per SCP `sprint-change-proposal-2026-08-08-remove-duplicate-index.md`.

---

## 3. Epic Coverage Validation

### FR Coverage Matrix

| FR | PRD Title | Epic Coverage | Epic Status |
|---|---|---|---|
| FR-1 | User Authentication | E1 | ✅ DONE |
| FR-2 | API Access for External Clients | E1 | ✅ DONE |
| FR-3 | Workspace Lifecycle | E1 | ✅ DONE |
| FR-4 | Workspace Invites & Memberships | E1 | ✅ DONE |
| FR-10 | RBAC với ba system roles | E1 | ✅ DONE |
| FR-6 | Built-in Scraper Connectors | E2 / E10.1 | ✅ DONE |
| FR-7 | External OAuth Connectors | E2 | ✅ DONE |
| FR-8 | External MCP Connectors | E2 | ✅ DONE |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | E12.1 | 🟡 READY-FOR-DEV |
| FR-44 | TopCV Scraper (Vietnam Job Market) | E12.2 | 🟡 READY-FOR-DEV |
| FR-45 | ITviec Scraper (Vietnam Job Market) | E12.3 | 🟡 READY-FOR-DEV |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | E12.4 | 🟡 READY-FOR-DEV / RECONCILED to `chainlens-research` |
| FR-47 | PII Redaction for Job Data | E12.5 | 🟡 READY-FOR-DEV |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) | — | ⛔ REMOVED (Epic 13 DROPPED) |
| FR-49 | News Aggregation (Epic 14) | E14 | 🟡 P2 / RECONCILED to `chainlens-research` |
| FR-50 | Financial Data Integration (Epic 15) | E15 | 🟡 P2 / RECONCILED to `chainlens-research` |
| FR-51 | Company Data Integration (Epic 16) | E16 | 🟡 P2 / RECONCILED to `chainlens-research` |
| FR-52 | E-commerce Intelligence (Epic 17) | E17 | 🟡 P2 / RECONCILED to `chainlens-research` |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) | E2 / E10 | ✅ DONE (covered by existing scrapers) |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) | — | ⏸️ DEFERRED (ChainLens) |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) | E2 | ✅ DONE (covered by existing scrapers) |
| FR-56 | Public Agent-Chat API for Vertical Clients | E18.1 | 🟡 READY-FOR-DEV |
| FR-57 | Agent Registry | E18.3 | 🟡 READY-FOR-DEV |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) | E20.1 | 🟡 READY-FOR-DEV |
| FR-59 | Gap-Fill Trigger via chainlens-research | E20.2 | 🟡 READY-FOR-DEV |
| FR-60 | Private Data Provider (NowingPrivateProvider) | E20.3 | 🟡 READY-FOR-DEV |
| FR-61 | Cross-Project Service Auth & Cost Allocation | E20.4 | 🟡 READY-FOR-DEV |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | E20.1 (Story 20.1 → chainlens Story 47-5) | 🟡 READY-FOR-DEV |
| FR-8.1 | Exa MCP Search Connector | E2.10 | ✅ DONE |
| FR-9 | Document Upload, Parse & Index | E3 | ✅ DONE |
| FR-11 | Folders & Document Management | E3 | ✅ DONE |
| FR-12 | Hybrid Search over Knowledge Base | E3 | ✅ DONE |
| FR-13 | Citation Panel for Knowledge-base Chunks | E3 | ✅ DONE |
| FR-32 | Long-Term Research Memory | E3 | ✅ DONE |
| FR-33 | Research Continuity | E4 | ✅ DONE |
| FR-34 | Memory Correction | E3/E4 | ✅ DONE |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery | E3.10 | ✅ RESOLVED |
| FR-40 | First-Run Value — Research Runs Produce Memory | E3.13 | ✅ DONE |
| FR-5 | AI File Sorting (REMOVED) | — | ⛔ REMOVED |
| FR-14 | Chat Threads & Messages | E4 | ✅ DONE |
| FR-15 | Multi-agent Runtime with Tools | E4 | ✅ DONE |
| FR-16 | Real-time Collaborative Chat | E4 | ✅ DONE |
| FR-17 | Anonymous Chat with Quota | E4 | ✅ DONE |
| FR-42 | Chat Response Benchmark | E4 | ✅ DONE |
| FR-21 | Report Generation & Export | E5 | ✅ DONE |
| FR-22 | Podcast & Video Presentation | E5 | ✅ DONE |
| FR-23 | Image Generation | E5 | ✅ DONE |
| FR-18 | Automation Action Types | E6.4 | ✅ DONE |
| FR-19 | Automation Triggers | E6 | ✅ DONE |
| FR-20 | Automation Runs & Retries | E6 | ✅ DONE |
| FR-35 | Memory-Driven Automations | E6.5 | ✅ DONE |
| FR-25 | Web Client (Next.js) | E7 | ✅ DONE |
| FR-26 | Desktop Client (Electron) | E7 | ✅ DONE |
| FR-27 | Browser Extension (Plasmo) | E7 | ✅ DONE |
| FR-28 | Obsidian Plugin | E7 | ✅ DONE |
| FR-29 | MCP Server | E7 | ✅ DONE |
| FR-30 | Token Usage Tracking | E8 | ✅ DONE |
| FR-31 | Credit Wallet & Purchases | E8.3 | ✅ DONE |
| FR-41 | Admin UI cho Global LLM Model Configuration | E8.11 | ✅ DONE |
| FR-24 | Deep Open-Web Research via ChainLens Engine | E9.1b | ✅ DONE |
| FR-37 | Deep-Research Cost Metering | E9.2 | ✅ DONE |
| FR-38 | Research Degradation & Self-Host Independence | E9.1a | ✅ DONE |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation | E9.6 | ✅ DONE |

### NFR Coverage Matrix

| NFR | PRD Title | Epic Coverage | Epic Status |
|---|---|---|---|
| NFR-1 | Performance | E3.14 | ✅ DONE (1b/1c/1d); overall PARTIAL per epics map |
| NFR-2 | Security & Auth | E1 | ✅ DONE |
| NFR-3 | Observability | — | ✅ DONE |
| NFR-4 | Reliability | — | ✅ DONE |
| NFR-5 | Multi-tenancy Isolation | E1 | ✅ DONE |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients | E18 | 🟡 PROPOSED |
| NFR-6 | Citation Full-Editor Highlight | E3.6 | ✅ DONE |
| NFR-7 | Usage & Credit Dashboard | E8.3 | ✅ DONE |
| NFR-8 | Recall Quality (eval-gated) | E3.9 | ✅ DONE |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) | E9.3 | ✅ DONE (State A); State B pending ratification |
| NFR-10 | Chat Response Regression Gate | E4 | ✅ DONE |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | E12.5 / E12.2–12.4 | 🟡 READY-FOR-DEV |

### Coverage Statistics

- Total PRD FRs: **63**
- FRs with traceable epic coverage: **60**
- FRs intentionally removed (FR-5, FR-48) or deferred (FR-54): **3**
- Effective traceability coverage: **100.0%**
- Missing active FRs: **0**

### Missing FRs

No critical missing FRs. All active FRs trace to an epic or an explicit removal/defer decision.

---

## 4. UX Alignment Assessment

### UX Contract Inventory

| Contract | FRs / NFRs | AD Binds | Epic/Story | Status |
|---|---|---|---|---|
| ux-contract-admin-global-model-config | FR-41 | AD-8, AD-9 | Story 8.11 | Active |
| ux-contract-agent-registry | FR-57 | AD-29, AD-30, AD-31 | Epic 18 | Active |
| ux-contract-async-deep-research | FR-38, NFR-9 | AD-17, AD-18 | Story 9.3 | **Active — expanded to full contract** |
| ux-contract-chat-benchmark | FR-42, NFR-10 | — | Stories 4.8a–4.8g | Active |
| ux-contract-ecosystem-search | FR-58, FR-59, FR-62 | AD-34, AD-35 | Epic 20 | Active |
| ux-contract-first-run-onboarding | FR-40 | AD-18 | Story 3.13 | Active |
| ux-contract-private-data-provider | FR-60 | AD-15, AD-35 | Epic 20.3 | Active |
| ux-contract-public-agent-chat-api | FR-56 | AD-29, AD-30, AD-31 | Epic 18.1 | Active |
| ux-contract-service-auth-cost | FR-61 | AD-8, AD-15, AD-34, AD-35 | Epic 20.4 | Active |
| ux-contract-sync-offline-indicator | FR-38 | AD-4, AD-5, AD-18 | Stories 9.1a, 9.3 | Active |
| ux-contract-usage-dashboard | FR-31, NFR-7 | AD-8 | Stories 8.3, 8.12 | Active |
| ux-contract-vn-jobs-copy | FR-43–47 | AD-22–26 | Epic 12 | Active |
| ux-contract-canonical-entity (archive) | FR-48 [REMOVED] | AD-27/28 [RE-SCOPED] | Epic 13 [DROPPED] | Archived |

### Alignment Findings

1. **Ecosystem search contract is consistent with architecture.** `ux-contract-ecosystem-search.md` header binds AD-34/AD-35 and explicitly references `POST /v1/ingest/scraper`, matching the 2026-08-08 SCP. ✅
2. **Canonical entity UX contract archived.** `ux-contract-canonical-entity.md` was correctly archived to `ux-designs/.../archive/` after Epic 13 was dropped. ✅
3. **Public-agent-chat and service-auth-cost contracts created.** Two new UX contracts cover Epic 18 and Epic 20.4 and are active. ✅
4. **Async deep-research UX contract expanded.** `ux-contract-async-deep-research.md` now includes component mapping, state-by-state copy, accessibility requirements, telemetry events, and multi-replica guard. The scaffold warning is closed. ✅
5. **Vietnam jobs copy contract is still valid** as a copy-only spec; it does not need behavior changes because `vn_jobs.aggregate` output still surfaces a user-facing normalized view even though the canonical index now lives in `chainlens-research`. The `ingestJobId` field is a backend/provenance detail and does not require copy changes. ✅

---

## 5. Epic Quality Review

### Best-Practices Compliance Checklist

| Criterion | Verdict | Notes |
|---|---|---|
| Epics deliver user value | ✅ | All epics describe user outcomes; Epic 18/20 are user-facing platform/integration capabilities. |
| Epics function independently | ✅ | Epic 12 legal gate (Story 12.0) closed 2026-08-08; Epic 18 entry criteria are explicit and do not depend on dropped Epic 13. |
| Stories appropriately sized | ✅ | Epic 12 story files 12.2–12.4 now contain detailed Given/When/Then ACs. Epic 14–17 stories were re-scoped to feeder-only `Chunk[]` → `chainlens-research`. |
| No forward dependencies | ✅ | Story numbering within epics is sequential; dependencies point to previous stories or accepted architecture decisions. |
| Traceability to FRs maintained | ✅ | Epics and story files reference FRs and ADs explicitly. |
| Clear acceptance criteria | ✅ | Story 12.2–12.4, 18.1–18.8, and 20.1–20.4 use Given/When/Then format. |

### Quality Violations

#### 🟡 Minor Concerns
- **`chainlens-research` Story 47-1 is referenced** in `epics.md` §20.1 and `ux-contract-ecosystem-search.md` as the canonical `Chunk` schema owner; the actual story file lives in the external `chainlens-research` repo and should be verified before Nowing Epic 20 implementation begins.
- **`sprint-status.yaml` and `epics.md` status labels** should stay synchronized. `epics.md` §12.1–12.5 status tags were updated to `ready-for-dev P0` to match `sprint-status.yaml` in this re-run. Ensure any future edits keep both files in sync.

---

## 6. Final Assessment

### Overall Readiness Status

🟢 **READY FOR PHASE 4**

### Critical Issues Requiring Immediate Action

None. The three conditional issues from the 2026-08-08 assessment are resolved:

1. **Epic 14–17 scope reconciled with the 2026-08-08 SCP.** FR-49–52 now explicitly feed `chainlens-research` via `POST /v1/ingest/scraper`; stale canonical-indexing ACs and AD-27/AD-28 references have been removed or re-scoped. ✅
2. **Epic 12 story files strengthened.** Stories 12.2, 12.3, and 12.4 now contain detailed Given/When/Then ACs for pagination, rate-limits, anti-bot fallback, PII redaction, and `chainlens-research` ingest. ✅
3. **Async deep-research UX gap closed.** `ux-contract-async-deep-research.md` was expanded to a full UX contract with component mapping, copy, accessibility, telemetry, and multi-replica guard. ✅

### Additional Scope Alignment (discovered and fixed)

- **Epic 12.4 (`vn_jobs.aggregate`) was also re-scoped to feed `chainlens-research`.** The PRD/SCP already required this, but the epic body and story file still described a local REST/MCP/chat search corpus. Both `epics.md` §12.4 and `implementation-artifacts/stories/12-4-vietnam-job-aggregator.md` were updated to: produce `Chunk[]`, call `NowingIngestService.ingest()` → `POST /v1/ingest/scraper`, and return `ingestJobId` in `VnJobAggregateOutput`. This makes Epic 12 consistent with the 2026-08-08 architecture decision.
- **Epic 12.1–12.5 status tags** in `epics.md` were aligned to `ready-for-dev P0` to match `sprint-status.yaml` and the expanded story files.

### Recommended Next Steps

1. **Cross-repo verification:** Confirm `chainlens-research` Epic 47 story files (47-1–47-5) exist and that the `Chunk` schema, `POST /v1/ingest/scraper`, and `POST /api/v1/search` contracts match the Nowing side before Nowing Epic 20 implementation begins.
2. **TopCV anti-bot POC:** Story 12.2 remains gated by a successful anti-bot POC for TopCV (Cloudflare challenge). Do not merge until the POC passes or the source is explicitly disabled.
3. **Legal/ToS gate:** Story 12.0 is `done` and unblocks 12.1–12.5; keep the closed legal memos in `legal/` up to date if new sources are added.
4. **Keep `sprint-status.yaml`, `epics.md`, and story files synchronized** as any new P0/P2 re-scoping decisions land.
5. **Update `ux-contract-vn-jobs-copy.md` tool copy** only if user-facing copy for `vn_jobs.aggregate` is expanded to mention `ingestJobId` or `chainlens-research` sources; this is optional for launch.

### Final Note

This re-run identified **0 critical issues**, **0 major issues**, and **2 minor cross-repo/synchronization notes**. The 2026-08-08 conditional issues are closed, and the planning artifacts are now aligned with the 2026-08-08 SCP (`chainlens-research` owns the single canonical index). Phase 4 implementation can proceed, with the TopCV anti-bot POC remaining the only known technical pre-requisite for Epic 12.
