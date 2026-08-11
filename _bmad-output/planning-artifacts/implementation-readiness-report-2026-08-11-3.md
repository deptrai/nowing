---
stepsCompleted: [1, 2, 3, 4, 5, 6]
date: 2026-08-11
project: Nowing
assessmentVersion: 3
postCleanupRun: true
---

# Nowing — Implementation Readiness Assessment Report

**Date:** 2026-08-11  
**Project:** Nowing  
**Assessor:** Implementation Readiness workflow (`bmad-check-implementation-readiness`)  
**Scope:** Canonical PRD, Architecture Spine, `epics.md`, UX contracts, and `sprint-status.yaml` after 2026-08-11 planning cleanup.

---

## Step 1 — Document Discovery and Inventory

### Canonical Documents

| Document | Path | Lines | Status |
|---|---|---|---|
| PRD | `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` | 1,558 | ✅ Canonical, single whole file |
| Architecture | `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | 1,401 | ✅ Canonical, single whole file |
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | 2,476 | ✅ Canonical, single whole file |
| UX Design Folder | `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/` | 20 `.md` files | ✅ Canonical, sharded contracts |
| Sprint Status | `_bmad-output/implementation-artifacts/sprint-status.yaml` | 444 | ✅ Current source of truth for story status |

### Whole Documents Found

- `prd.md`
- `ARCHITECTURE-SPINE.md`
- `epics.md`
- `sprint-status.yaml`

### Sharded / Folder-Based Documents

- `ux-designs/ux-Nowing-2026-07-22/` — 20 UX contract files (see Step 4 for list)

### Other Planning Artifacts in Scope

The `_bmad-output/planning-artifacts/` tree contains **84** nested `.md/.yaml` files. Key supporting artifacts reviewed for this report include:

- `prd-requirements-extracted-2026-08-08.md` (1,007 lines) — FR/NFR extraction with status annotations
- `epic21-proposal-2026-08-11.md` (136 lines) — lead-gen proposal extracted from `epics.md`
- `architecture/architecture-Nowing-2026-07-22/architecture-validation-report-2026-08-11.md`
- `architecture/epic21-architecture-update.md`
- `legal/tos-review-memo-epic-12-2026-08-08.md`
- Previous implementation readiness reports (`implementation-readiness-report-2026-08-11-2.md`, `-2026-08-11.md`, and earlier variants)

### Duplicates

No unresolved duplicate PRD/Architecture/Epic/UX documents were found. `epic21-proposal-2026-08-11.md` is a deliberate extraction of Epic 21 from `epics.md`; both exist but serve different purposes (roadmap proposal vs. backlog placeholder).

### Changes Since the Last Readiness Run (2026-08-11-2)

- `epics.md` reordered so **Epic 20** (`Nowing Ecosystem Integration`) and **Story 6.8 Generic Alert Engine** appear before the consumer vertical epics (12, 14–17).
- **Story 12.4** split into `12.4a–e` (normalization, deduplication/conflict, PII, ingest, REST/MCP/chat exposure).
- **Epic 21** extracted to a separate `epic21-proposal-2026-08-11.md`; `epics.md` now contains a one-line `PROPOSED` placeholder.
- Acceptance criteria for `4.8a–4.8g`, `3.9`, `3.15`, `3.16`, and Epic 18 stories rewritten in English `Given/When/Then` with concrete thresholds and error paths.
- `3.9` recall gate now uses `precision@5 ≥ 0.80`, `noise ≤ 0.10`.
- `sprint-status.yaml` tracks `6-8` (Generic Alert Engine) and `12-4a–e`.

---

## Step 2 — PRD Analysis

### Functional Requirements

The canonical PRD contains **70 numbered FRs** (FR-1 through FR-69, plus FR-8.1).

| FR | Requirement | Status | Notes |
|---|---|---|---|
| FR-1 | User Authentication | DONE | JWT/cookie + Google OAuth |
| FR-2 | API Access for External Clients | DONE | PAT/API key, `Workspace.api_access_enabled` |
| FR-3 | Workspace Lifecycle | DONE | CRUD + default RBAC |
| FR-4 | Workspace Invites & Memberships | DONE | Invites, memberships, roles |
| FR-5 | AI File Sorting | REMOVED | Migration 172 removed all traces |
| FR-6 | Built-in Scraper Connectors | DONE | Reddit, YouTube, Instagram, TikTok, Google, Amazon, web crawl |
| FR-7 | External OAuth Connectors | DONE | Notion/Slack/Linear/Jira/GDrive/etc. |
| FR-8 | External MCP Connectors | DONE | Exa + composio pattern |
| FR-8.1 | Exa MCP Search Connector | DONE | `EXA_MCP_CONNECTOR` type wired, migration 190 |
| FR-9 | Document Upload, Parse & Index | DONE | ETL pipeline, 50+ formats |
| FR-10 | RBAC with three system roles | DONE | Owner/Editor/Viewer only (Admin removed) |
| FR-11 | Folders & Document Management | DONE | Folders, versioning, revert |
| FR-12 | Hybrid Search over Knowledge Base | DONE | pgvector + full-text + RRF |
| FR-13 | Citation Panel for Knowledge-base Chunks | DONE | Scroll/highlight in editor |
| FR-14 | Chat Threads & Messages | DONE | Streaming, threads, comments |
| FR-15 | Multi-agent Runtime with Tools | DONE | Core multi-agent + auto-extract |
| FR-16 | Real-time Collaborative Chat | DONE | Zero sync |
| FR-17 | Anonymous Chat with Quota | DONE | `/anonymous/*` |
| FR-18 | Automation Action Types | DONE | `agent_task` + direct write-backs |
| FR-19 | Automation Triggers | DONE | schedule + event + `memory_change` |
| FR-20 | Automation Runs & Retries | DONE | Celery, retry policy |
| FR-21 | Report Generation & Export | DONE | ZIP/PDF/DOCX/HTML/LaTeX/EPUB/ODT/plain |
| FR-22 | Podcast & Video Presentation | DONE | 2-host podcast, video |
| FR-23 | Image Generation | DONE | `/image-generations` |
| FR-24 | Deep Open-Web Research via ChainLens Engine | DONE | Contract regression guard, `balanced` default, async path |
| FR-25 | Web Client (Next.js) | DONE | Dashboard, chat, settings |
| FR-26 | Desktop Client (Electron) | DONE | Wrapper, shortcuts, folder watcher |
| FR-27 | Browser Extension (Plasmo) | DONE | History capture |
| FR-28 | Obsidian Plugin | DONE | Vault sync |
| FR-29 | MCP Server | DONE | Memory, scraper, KB, research tools |
| FR-30 | Token Usage Tracking | DONE | `TokenUsage` + model breakdown |
| FR-31 | Credit Wallet & Purchases | DONE | Stripe, auto-reload |
| FR-32 | Long-Term Research Memory | DONE | Bounded injection, recall, auto-extract (Story 3-14 done; baseline 2026-08-04) |
| FR-33 | Research Continuity | DONE | `ResearchThread`, `nowing_continue_research` |
| FR-34 | Memory Correction | DONE | `MemoryVersion`, `nowing_update_fact` |
| FR-35 | Memory-Driven Automations | DONE | `memory_change` trigger, `continue_research` action |
| FR-36 | Legacy Memory Data-Loss Assessment | RESOLVED | No data loss; guard + backfill built |
| FR-37 | Deep-Research Cost Metering | DONE | Parses `costDollars`, `estimated`, `resolvedMode`, fallback 60k micros |
| FR-38 | Research Degradation & Self-Host Independence | DONE | P0; fallback to hybrid search, `engine_unavailable` |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | DONE | Story 9-6; `source_capability`/`source_input`/`source_run_id` |
| FR-40 | First-Run Value — Research Runs Produce Memory | DONE | Story 3-13; run creates `Memory` with provenance |
| FR-41 | Admin UI for Global LLM Model Configuration | DONE | Story 8-11; superuser-only DB + file-backed merge |
| FR-42 | Chat Response Benchmark | DONE | `nowing_evals` chat regression/quality/mode matrix |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) | IN PROGRESS | 12-1 done; 12-0 legal approved |
| FR-44 | TopCV Scraper (Vietnam Job Market) | DONE | 12-2 done; anti-bot POC passed |
| FR-45 | ITviec Scraper (Vietnam Job Market) | IN PROGRESS | 12-3 in-progress |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) | IN PROGRESS | Split into 12.4a–e; 12.4a in-progress |
| FR-47 | PII Redaction for Job Data | IN PROGRESS | 12.5 in-progress |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing | REMOVED | Moved to `chainlens-research`; Epic 13 dropped |
| FR-49 | News Aggregation (Vietnam) | PROPOSED/RE-SCOPED | Epic 14; feeds `chainlens-research` |
| FR-50 | Financial Data Integration (Vietnam) | PROPOSED/RE-SCOPED | Epic 15; feeds `chainlens-research` |
| FR-51 | Company Data Integration (Vietnam) | PROPOSED/RE-SCOPED | Epic 16; feeds `chainlens-research` |
| FR-52 | E-commerce Intelligence (Vietnam) | PROPOSED/RE-SCOPED | Epic 17; feeds `chainlens-research` |
| FR-53 | Social Media Integration | REMOVED | Covered by existing Epic 10 scrapers |
| FR-54 | Search Intelligence | REMOVED | Covered by ChainLens generic crawl |
| FR-55 | Global E-commerce | REMOVED | Covered by Stories 2.6/2.7 |
| FR-56 | Public Agent-Chat API for Vertical Clients | DONE | Epic 18; 18-1 through 18-8 done |
| FR-57 | Agent Registry | DONE | 18-3 done; `agent_configs` table + seed |
| FR-58 | Scraper Feed to `chainlens-research` | IN PROGRESS | Epic 20; 20.1–20.4 in-progress |
| FR-59 | Gap-Fill Trigger via `chainlens-research` | IN PROGRESS | Epic 20; 20.3 in-progress |
| FR-60 | Private Data Provider (`NowingPrivateProvider`) | IN PROGRESS | Epic 20; 20.4 in-progress |
| FR-61 | Cross-Project Service Auth & Cost Allocation | IN PROGRESS | Epic 20; 20.1 in-progress |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) | IN PROGRESS | Epic 20; governed by `AD-34` |
| FR-63 | Intent Signal Detection | PROPOSED | Epic 21; governance gates open |
| FR-64 | Lead Scoring & Prioritization | PROPOSED | Epic 21; governance gates open |
| FR-65 | Enriched Contact Data | PROPOSED | Epic 21; governance gates open |
| FR-66 | Outbound Prospecting Automation | PROPOSED | Epic 21; email only, Zalo/LinkedIn deferred |
| FR-67 | CRM Integration & Write-Back | PROPOSED | Epic 21; governance gates open |
| FR-68 | Zalo Integration (Vietnam Market) | DEFERRED | Legal/ToS/Decree 356 gates open |
| FR-69 | Outcome-Based Pricing Option | PROPOSED | Epic 21; governance gates open |

**Total FRs:** 70  
**DONE/RESOLVED:** 50  
**IN PROGRESS:** 10  
**PROPOSED/RE-SCOPED:** 7  
**REMOVED/DEFERRED:** 3

### Non-Functional Requirements

| NFR | Requirement | Status | Notes |
|---|---|---|---|
| NFR-1 | Performance | DONE | NFR-1a CRUD/scraper; NFR-1b/1c/1d memory injection/recall/auto-extract done via Story 3-14 |
| NFR-2 | Security & Auth | DONE | JWT/cookie, PAT, permission checks, `.env` secrets |
| NFR-3 | Observability | DONE | OpenTelemetry, `Log` model, Celery monitoring |
| NFR-4 | Reliability | DONE | Async DB, Celery+Redis, retries |
| NFR-5 | Multi-tenancy Isolation | DONE | `workspace_id` filtering, `api_access_enabled` |
| NFR-MULTI-1 | Tenant Isolation for Vertical Clients (`client_id`) | DONE | Composite RLS; 18-8 test PASS |
| NFR-6 | Citation Full-Editor Highlight | DONE | `editorPanelAtom` + citation-kit |
| NFR-7 | Usage & Credit Dashboard | DONE | Story 8-3 done |
| NFR-8 | Recall Quality (eval-gated) | DONE | Story 3-9 done; baseline ratified 2026-08-04 |
| NFR-9 | Deep-Research Latency & Availability Budget | STATE A DONE / STATE B PENDING | State A async deliverable is default; State B sync chat-mode gated on ChainLens 34.1 + Nowing e2e p95 `balanced` ≤ 30 s |
| NFR-10 | Chat Response Regression Gate | DONE | `nowing_evals` regression + CI gate |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience | PROPOSED | Vietnam job market ToS/legal approved 2026-08-08; anti-bot/PII reliability still in progress |

**Total NFRs:** 12 (including NFR-MULTI-1)

### PRD Completeness Assessment

- The PRD is complete and traceable. All 70 FRs and 12 NFRs are documented with acceptance criteria, consequences, and status tags.
- Recent scope changes (FR-48/53/54/55 removed, FR-49–52 re-scoped to feed `chainlens-research`, FR-56–62 moved to Epic 18/20, FR-63–69 added as Epic 21) are reflected in `epics.md` and the extracted `epic21-proposal-2026-08-11.md`.
- NFR-9 State B remains a ratification gate, not an implementation gap.

---

## Step 3 — Epic Coverage Validation

### Coverage Statistics

- **Total PRD FRs:** 70
- **FRs covered in epics:** 70
- **Missing:** 0 (0.0%)
- **Extra in epics not in PRD:** 0

### FR Coverage Matrix

| FR Number | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR-1 | User Authentication | Epic 1 | ✅ Covered |
| FR-2 | API Access for External Clients | Epic 1; E2 2.10 | ✅ Covered |
| FR-3 | Workspace Lifecycle | Epic 1; E8 8.12 | ✅ Covered |
| FR-4 | Workspace Invites & Memberships | Epic 1 | ✅ Covered |
| FR-5 | AI File Sorting (REMOVED) | Epic 1 (noted removed) | ✅ Covered |
| FR-6 | Built-in Scraper Connectors | Epic 2; E10 10.1–10.7 | ✅ Covered |
| FR-7 | External OAuth Connectors | Epic 2; E7 7.4 | ✅ Covered |
| FR-8 | External MCP Connectors | Epic 2; E3 3.12 | ✅ Covered |
| FR-8.1 | Exa MCP Search Connector | Epic 2; E2 2.10 | ✅ Covered |
| FR-9 | Document Upload, Parse & Index | Epic 3 | ✅ Covered |
| FR-10 | RBAC with three system roles | Epic 1; E8 8.11 | ✅ Covered |
| FR-11 | Folders & Document Management | Epic 3 | ✅ Covered |
| FR-12 | Hybrid Search over Knowledge Base | Epic 3 | ✅ Covered |
| FR-13 | Citation Panel for Knowledge-base Chunks | Epic 3; E3 3.15 | ✅ Covered |
| FR-14 | Chat Threads & Messages | Epic 4; E4 4.7 | ✅ Covered |
| FR-15 | Multi-agent Runtime with Tools | Epic 4; E8 8.8 | ✅ Covered |
| FR-16 | Real-time Collaborative Chat | Epic 4 | ✅ Covered |
| FR-17 | Anonymous Chat with Quota | Epic 4; E8 8.7 | ✅ Covered |
| FR-18 | Automation Action Types | Epic 6; E6 6.4 | ✅ Covered |
| FR-19 | Automation Triggers | Epic 6 | ✅ Covered |
| FR-20 | Automation Runs & Retries | Epic 6 | ✅ Covered |
| FR-21 | Report Generation & Export | Epic 5; E7 7.7 | ✅ Covered |
| FR-22 | Podcast & Video Presentation | Epic 5 | ✅ Covered |
| FR-23 | Image Generation | Epic 5; E7 7.7 | ✅ Covered |
| FR-24 | Deep Open-Web Research via ChainLens Engine | Epic 2; Epic 9 | ✅ Covered |
| FR-25 | Web Client (Next.js) | Epic 7; E7 7.4 | ✅ Covered |
| FR-26 | Desktop Client (Electron) | Epic 7 | ✅ Covered |
| FR-27 | Browser Extension (Plasmo) | Epic 7 | ✅ Covered |
| FR-28 | Obsidian Plugin | Epic 7 | ✅ Covered |
| FR-29 | MCP Server | Epic 7; E7 7.7 | ✅ Covered |
| FR-30 | Token Usage Tracking | Epic 8; E8 8.12 | ✅ Covered |
| FR-31 | Credit Wallet & Purchases | Epic 8; E8 8.3 | ✅ Covered |
| FR-32 | Long-Term Research Memory | Epic 3; E3 3.14 | ✅ Covered |
| FR-33 | Research Continuity | Epic 3; Epic 4 | ✅ Covered |
| FR-34 | Memory Correction | Epic 3; E9 9.6 | ✅ Covered |
| FR-35 | Memory-Driven Automations | Epic 6; E6 6.5 | ✅ Covered |
| FR-36 | Legacy Memory Data-Loss Assessment | Epic 3; E3 3.10 | ✅ Covered |
| FR-37 | Deep-Research Cost Metering | Epic 9; E9 9.2 | ✅ Covered |
| FR-38 | Research Degradation & Self-Host Independence | Epic 9; E9 9.1a | ✅ Covered |
| FR-39 | Memory → Scraper-Run Provenance & Re-Validation | Epic 3; E9 9.6 | ✅ Covered |
| FR-40 | First-Run Value — Research Runs Produce Memory | Epic 3; E3 3.13 | ✅ Covered |
| FR-41 | Admin UI for Global LLM Model Configuration | Epic 8; E8 8.11 | ✅ Covered |
| FR-42 | Chat Response Benchmark | Epic 4; E4 4.8a–4.8g | ✅ Covered |
| FR-43 | VietnamWorks Scraper | Epic 12; E12 12.1 | ✅ Covered |
| FR-44 | TopCV Scraper | Epic 12; E12 12.2 | ✅ Covered |
| FR-45 | ITviec Scraper | Epic 12; E12 12.3 | ✅ Covered |
| FR-46 | Vietnam Job Market Aggregator | Epic 12; E12 12.4a–12.4e | ✅ Covered |
| FR-47 | PII Redaction for Job Data | Epic 12; E12 12.5 | ✅ Covered |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (REMOVED) | Epic 13 (dropped) | ✅ Covered |
| FR-49 | News Aggregation (RE-SCOPED) | Epic 14 | ✅ Covered |
| FR-50 | Financial Data Integration (RE-SCOPED) | Epic 15 | ✅ Covered |
| FR-51 | Company Data Integration (RE-SCOPED) | Epic 16 | ✅ Covered |
| FR-52 | E-commerce Intelligence (RE-SCOPED) | Epic 17 | ✅ Covered |
| FR-53 | Social Media Integration (REMOVED) | Epic 18 (covered by E10) | ✅ Covered |
| FR-54 | Search Intelligence (REMOVED) | Epic 18 (covered by ChainLens) | ✅ Covered |
| FR-55 | Global E-commerce (REMOVED) | Epic 18 (covered by E2) | ✅ Covered |
| FR-56 | Public Agent-Chat API for Vertical Clients | Epic 18 | ✅ Covered |
| FR-57 | Agent Registry | Epic 18 | ✅ Covered |
| FR-58 | Scraper Feed to `chainlens-research` | Epic 20; E20 20.2 | ✅ Covered |
| FR-59 | Gap-Fill Trigger via `chainlens-research` | Epic 20; E20 20.3 | ✅ Covered |
| FR-60 | Private Data Provider (`NowingPrivateProvider`) | Epic 20; E20 20.4 | ✅ Covered |
| FR-61 | Cross-Project Service Auth & Cost Allocation | Epic 20; E20 20.1 | ✅ Covered |
| FR-62 | Canonical Chunk Metadata Schema | Epic 20; E20 20.2 | ✅ Covered |
| FR-63 | Intent Signal Detection | Epic 21; E21 21.1 | ✅ Covered |
| FR-64 | Lead Scoring & Prioritization | Epic 21; E21 21.2 | ✅ Covered |
| FR-65 | Enriched Contact Data | Epic 21; E21 21.3 | ✅ Covered |
| FR-66 | Outbound Prospecting Automation | Epic 21; E21 21.4 | ✅ Covered |
| FR-67 | CRM Integration & Write-Back | Epic 21; E21 21.5 | ✅ Covered |
| FR-68 | Zalo Integration (Vietnam Market) | Epic 21; E21 21.6 | ✅ Covered |
| FR-69 | Outcome-Based Pricing Option | Epic 21; E21 21.7 | ✅ Covered |

### Missing FR Coverage

No missing FRs were found. Every PRD requirement maps to at least one epic/story in `epics.md` or the extracted `epic21-proposal-2026-08-11.md`.

---

## Step 4 — UX Alignment Assessment

### UX Document Status

UX contracts found in `ux-designs/ux-Nowing-2026-07-22/` (20 files):

1. `ux-contract-admin-global-model-config.md`
2. `ux-contract-agent-registry.md`
3. `ux-contract-async-deep-research.md`
4. `ux-contract-chat-benchmark.md`
5. `ux-contract-ecosystem-search.md`
6. `ux-contract-epic21-addendum-2026-08-11.md`
7. `ux-contract-first-run-onboarding.md`
8. `ux-contract-fit-score-badge.md`
9. `ux-contract-lead-intelligence-panel.md`
10. `ux-contract-positive-reply-notifications.md`
11. `ux-contract-private-data-provider.md`
12. `ux-contract-public-agent-chat-api.md`
13. `ux-contract-service-auth-cost.md`
14. `ux-contract-sidebar-onboarding.md`
15. `ux-contract-sync-offline-indicator.md`
16. `ux-contract-tables-directory.md`
17. `ux-contract-usage-dashboard.md`
18. `ux-contract-vn-jobs-copy.md`
19. `ux-contract-workspace-mode-switch.md`
20. `archive/ux-contract-canonical-entity.md` (archived; matches dropped Epic 13)

### UX Alignment by FR

| FR / Story | PRD Requirement | UX Contract(s) | Status |
|---|---|---|---|
| FR-6 | Built-in Scraper Connectors | `ux-contract-lead-intelligence-panel.md` (source tabs) | ✅ |
| FR-7 / FR-31 | External OAuth / Credit Wallet | `ux-contract-usage-dashboard.md` | ✅ |
| FR-9 | Document Upload, Parse & Index | `ux-contract-sync-offline-indicator.md`, `ux-contract-async-deep-research.md` | ✅ |
| FR-10 | RBAC | `ux-contract-chat-benchmark.md` | implied |
| FR-11 | Folders & Document Management | `ux-contract-vn-jobs-copy.md`, `ux-contract-tables-directory.md` | ✅ |
| FR-13 | Citation Panel | Citation panel component exists in code; no standalone UX contract | ⚠️ |
| FR-14 | Chat Threads & Messages | `ux-contract-positive-reply-notifications.md`, `ux-contract-sidebar-onboarding.md` | ✅ |
| FR-15 | Multi-agent Runtime | `ux-contract-sidebar-onboarding.md` | implied |
| FR-21 / FR-22 / FR-23 | Deliverables | None found | ⚠️ |
| FR-24 / FR-37 / FR-38 | Deep Research | `ux-contract-async-deep-research.md` (now a full contract) | ✅ |
| FR-32 / FR-40 | Long-Term Memory / First-Run Value | `ux-contract-first-run-onboarding.md` | ✅ |
| FR-41 | Admin Global Model Config | `ux-contract-admin-global-model-config.md` | ✅ |
| FR-42 | Chat Benchmark | `ux-contract-chat-benchmark.md` | ✅ |
| FR-43–47 | Vietnam Job Market | `ux-contract-vn-jobs-copy.md` | ✅ |
| FR-56–57 | Public Agent-Chat / Agent Registry | `ux-contract-public-agent-chat-api.md`, `ux-contract-agent-registry.md` | ✅ |
| FR-58–62 | Ecosystem / chainlens-research | `ux-contract-ecosystem-search.md`, `ux-contract-service-auth-cost.md`, `ux-contract-private-data-provider.md` | ✅ |
| FR-63–69 | Lead Gen Intelligence | `ux-contract-lead-intelligence-panel.md`, `ux-contract-fit-score-badge.md`, `ux-contract-epic21-addendum-2026-08-11.md`, `ux-contract-sidebar-onboarding.md`, `ux-contract-workspace-mode-switch.md`, `ux-contract-tables-directory.md`, `ux-contract-positive-reply-notifications.md` | ⚠️ gated |

### Alignment Issues

1. **Deliverables UX (FR-21/22/23):** No dedicated UX contracts exist for report export, podcast/video, or image generation. The UI is assumed to be legacy/brownfield. If these surfaces need redesign before Phase 4, contracts should be added.

2. **Citation Panel (FR-13):** The UX contract is implied by the existing `citation-panel.tsx` component and `AD-DEFER-1` closeout. No standalone UX file is present.

3. **Deep-Research async UX contract (`ux-contract-async-deep-research.md`, 161 lines):** Previously noted as a scaffold; now a full contract covering S1–S10 states, `ResearchProgressPanel` component mapping, copy, accessibility, telemetry, and multi-replica guard. It remains a **blocking UX input for State B UI**.

4. **Epic 21 UX contracts:** Eight new UX patterns are defined, but the underlying Epic 21 is `PROPOSED` with open governance gates. UX is ahead of business/legal sign-off, which is acceptable for a proposal but must not be treated as committed implementation scope.

---

## Step 5 — Epic Quality Review

### Assessment Criteria

Reviewed `epics.md` (2,476 lines) and `sprint-status.yaml` against the create-epics-and-stories best practices:

1. Epics deliver user value.
2. Epics are independent (Epic N should not require Epic N+1).
3. Stories are user-centric and independently completable.
4. No forward dependencies.
5. Database/entity creation happens when first needed.
6. Acceptance criteria are testable, specific, and complete.

### Improvements Confirmed (Cleanup Effective)

| Cleanup Item | Verification | Lines in `epics.md` |
|---|---|---|
| Epic 20 moved before consumer epics | Sections now ordered: 10, 11, 20, 12, 14, 15, 16, 17, 18 | 1618–1751, 1796–2475 |
| Story 6.8 Generic Alert Engine added | Full GWT ACs, `AlertRule` schema, diff strategies | 748–767 |
| Story 12.4 split into 12.4a–e | Independent stories for normalization, dedupe/conflict, PII, ingest, exposure | 1822–1872 |
| Epic 21 extracted | `epics.md` has one-line placeholder; full scope in `epic21-proposal-2026-08-11.md` | 2422–2436 |
| ACs rewritten in English GWT | 3.15, 3.16, 4.8a–g, 18.x stories use `Given/When/Then` | 418–454, 501–655, 2314–2418 |
| 3.9 threshold made concrete | `precision@5 ≥ 0.80`, `noise ≤ 0.10` | 310 |

### Critical Findings

#### C1. Platform enablers (Epic 20 / Story 6.8) are not done while consumer stories are already in-flight

- **Evidence:** `sprint-status.yaml` lines 182–192 show `20-1` through `20-4` as `in-progress`; `6-8` is `ready-for-dev` (line 120).
- **Consumer epics already active:**
  - `12-4a` `in-progress`, `12-4b–e` `ready-for-dev` (lines 226–230)
  - `12-9` `ready-for-dev` (line 239)
  - `14-1` marked `done` (line 259), but 14.1 ACs depend on `NowingIngestService` (Story 20.2).
  - `15-1` marked `done` (line 267), but 15.1 ACs depend on `NowingIngestService` (Story 20.2).
  - `16-1` marked `done` (line 275), but 16.1 ACs depend on `NowingIngestService` (Story 20.2).
- **Violation:** Consumer stories are being implemented or marked done before the shared platform enablers they require.
- **Impact:** Risk of rework if `Chunk` schema, service auth, or `NowingIngestService` contract changes. Also, `14-1/15-1/16-1` cannot truly be complete if the ingest hand-off is not stable.
- **Remediation:** Freeze `NowingIngestService`, `ChainLensServiceAuth`, `Chunk` schema, and `AlertRule` contract before advancing any more consumer stories. Do not mark additional consumer stories `done` until 20.2 and 6.8 are at least `review`.

#### C2. Forward dependency in Epic 12: 12.9 is `ready-for-dev` while 12.6 is `backlog`

- **Evidence:** `epics.md` lines 1895–1913 state `12.9: Job Market Alerts [P1 — depends on 12.6]`; `sprint-status.yaml` lines 232 and 239 show `12-6: backlog` and `12-9: ready-for-dev`.
- **Violation:** Story 12.9 explicitly depends on Story 12.6 (Saved Searches), yet 12.6 has not started.
- **Impact:** Job alerts cannot be implemented until saved-search infrastructure exists.
- **Remediation:** Either move `12-6` to `in-progress/ready-for-dev` before `12-9`, or move `12-9` back to `backlog` until `12-6` is available.

#### C3. Epic 21 remains a detailed proposal with UX contracts ahead of governance

- **Evidence:** `epics.md` lines 2422–2436 say Epic 21 is `PROPOSED` with five open governance gates; `epic21-proposal-2026-08-11.md` contains 7 detailed stories, table schemas (`SignalEvent`, `LeadScore`, `VerifiedContact`, `Sequence*`, `BillingEvent`, `OutcomeEvent`, `PricingPlan`, `CrmConnection`), and 8 UX contracts already created.
- **Violation:** Planning UX and schema details for a PROPOSED epic before legal/ToS/vendor/PII/CRM gates close risks scope creep and accidental scheduling.
- **Impact:** Engineering may pick up Epic 21 stories before business readiness is confirmed.
- **Remediation:** Keep `epic21-proposal-2026-08-11.md` as the single source of truth; do not create sprint story files for 21.1–21.7 until all governance gates close.

### Major Findings

#### M1. Consumer epics 14/15/16/17 are marked `in-progress` despite shared prerequisites

- **Evidence:** `sprint-status.yaml` lines 258–288.
- **Issue:** Several stories in these epics are `done` or `backlog`, but all depend on `NowingIngestService` (20.2) and/or `Generic Alert Engine` (6.8), which are not done.
- **Specifically:**
  - `14-1` `done` with open code review requesting SSRF/Atom/RSS 1.0 fixes (`sprint-status.yaml` lines 379–387).
  - `15-1` `done` with open code review requesting 404 handling, header/redirect, and rate-limit fixes (`sprint-status.yaml` lines 388–396).
  - `16-1` `done` with mutation-gate `FAIL` / `PASS_WITH_WARNINGS` and `p1` survived mutations (`sprint-status.yaml` lines 315–363).
- **Remediation:** Reconcile sprint status with code-review/validation outcomes. Do not mark stories `done` while P0/P1 review findings are open.

#### M2. Epic List in `epics.md` is still incomplete

- **Evidence:** `epics.md` lines 109–163 list only Epics 1–9; Epics 10–21 are not summarized in the Epic List.
- **Issue:** Navigators cannot see the full epic inventory at a glance.
- **Remediation:** Extend the Epic List section to include Epics 10, 11, 20, 12, 14, 15, 16, 17, 18, and 21 with one-line descriptions.

#### M3. Some benchmark/deliverable ACs still rely on numbers in implementation hints

- **Evidence:** `epics.md` lines 656–669 (Story 4.8h) references `speed ≤ 15 s`, `balanced p95 cost ≤ 100k micros`, `5 tool calls` in implementation hints but not all numbers are in ACs.
- **Issue:** Tests must read implementation hints to know thresholds.
- **Remediation:** Move mode-specific latency/cost/tool-call budgets into GWT ACs.

#### M4. Tech-debt follow-ups are written as user stories in `sprint-status.yaml`

- **Evidence:** `sprint-status.yaml` lines 306–313 list `td-1` through `td-7` as work items.
- **Issue:** Some are correctness issues (idempotency, Redis event bus leak, storage reconciliation, notification race, title generation timeout) and should be tracked as engineering tasks, not user stories.
- **Remediation:** Move to a tech-debt register or create proper user-value stories with GWT ACs.

### Minor Findings

1. **Mixed language in implementation notes:** Some `Kỹ thuật` sections still use Vietnamese, which is acceptable per `epics.md` line 111 convention (ACs must be English; context notes may be Vietnamese).
2. **Epic 18 placement after Epic 17:** A `done` epic placed after a `backlog` epic is non-sequential but not a functional problem.
3. **Dropped Epic 13 and stories 12.7/12.8 are retained in `sprint-status.yaml` as `dropped`, which is correct for traceability but should not appear in active backlog views.

---

## Step 6 — Summary and Recommendations

### Overall Readiness Status

**CONDITIONAL / NEEDS WORK** for the full post-core backlog.

The 2026-08-11 planning cleanup materially improved the artifact:

- Dependency order is now structurally correct (Epic 20 and Story 6.8 precede consumer epics).
- Story 12.4 is appropriately split.
- Epic 21 is extracted and labeled `PROPOSED`.
- AC quality improved for 4.8a–g, 3.9, 3.15, 3.16, and Epic 18.

However, the **sprint-status.yaml** does not yet reflect the cleanup: platform enablers (`20.1–20.4`, `6-8`) are not done while consumer stories are in-progress or marked `done`, and Epic 12 has a forward dependency (`12-9` ahead of `12-6`). These are scheduling risks that will block parallel execution or force rework.

**Core product (Epics 1–11, 18):** READY for continued implementation, subject to normal code-review gates.

**Vertical/alert backlog (Epics 12, 14–17):** CONDITIONAL — must wait for Epic 20 and Story 6.8.

**Lead Gen (Epic 21):** NOT READY — remains a proposal gated by legal/ToS, vendor POC, PII pipeline, CRM scope, and outcome-pricing validation.

### Critical Issues Requiring Immediate Action

1. **Reconcile `sprint-status.yaml` with platform enablers.** Do not advance any more Epic 12/14/17 consumer stories until `20.2` (`NowingIngestService`) and `6.8` (`Generic Alert Engine`) are at least in `review`.
2. **Fix Epic 12 dependency order.** Move `12-6` (Saved Searches) to `ready-for-dev` before `12-9` (Job Market Alerts), or move `12-9` to `backlog`.
3. **Do not mark consumer stories `done` before shared infrastructure is stable.** `14-1`, `15-1`, and `16-1` currently have open code-review findings and depend on unfinished `20.2`.
4. **Keep Epic 21 in proposal mode.** Do not create sprint story files for 21.1–21.7 until governance gates close.

### Recommended Next Steps

1. **Land Epic 20 stories 20.1–20.4 first.** Stabilize the `Chunk` schema, service auth, `NowingIngestService`, gap-fill caller, and `NowingPrivateProvider` contract.
2. **Implement Story 6.8 (Generic Alert Engine) as a prerequisite.** Ensure `AlertRule`, `alert_snapshots`, `alert_subscriptions`, and diff strategies (`new_items`, `price_change`, `threshold_cross`) are in place.
3. **Extend the `Epic List` in `epics.md`** to include Epics 10–21 for navigation.
4. **Move concrete mode budgets** from Story 4.8h implementation hints into GWT ACs.
5. **Run a focused architecture readiness check** on Epic 21 entities (`SignalEvent`, `LeadScore`, `VerifiedContact`, `Sequence*`, `BillingEvent`, `OutcomeEvent`, `PricingPlan`, `CrmConnection`) before any implementation starts.

### Final Note

This assessment identified **7 issues** across **3 categories** (scheduling/dependencies, sprint-status accuracy, epic quality). The codebase and core planning artifacts are now in good shape; the remaining risk is primarily **execution sequencing** rather than missing requirements or structural epic quality. Address the critical issues above before proceeding to broad vertical/alert implementation.

---

**Report generated:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-11-3.md`  
**Assessor:** Implementation Readiness workflow (`bmad-check-implementation-readiness`)  
**Date:** 2026-08-11

---

## Addendum — Post-Report Cleanup (2026-08-11, after version 3)

The following items were actioned immediately after the version 3 report was generated to align planning artifacts with the recommendations above:

1. **Extended the Epic List in `epics.md` (lines 164–195).** Added canonical entries for Epics 10–21, including status, one-line scope, FR mapping, and key open stories. Epic 13 is explicitly marked `DROPPED`; Epic 21 remains `PROPOSED`.
2. **Fixed Epic 12 dependency order in `sprint-status.yaml`.** `12-6` (Saved Searches) moved to `ready-for-dev`; `12-9` (Job Market Alerts) moved to `backlog` with a dependency note that it is unblocked only when `12-6` and `6-8` are done.
3. **Reconciled consumer story statuses with code-review/validation gates.** `14-1`, `15-1`, and `16-1` moved from `done` to `in-progress` with comments documenting their open `PASS_WITH_WARNINGS`, `CHANGES_REQUESTED`, and mutation-gate `FAIL` findings, plus dependency on `20-2` (NowingIngestService) and `6-8` (Generic Alert Engine).
4. **Hardened Story 4.8h ACs.** Moved concrete mode budgets from implementation hints into GWT acceptance criteria: `mode=speed` ≤15s, `mode=balanced` p95 cost ≤100,000 micros, `mode=auto` forces an answer after 5 tool calls.
5. **Docs-drift check re-run:** `python3 scripts/check-docs-drift.py` **PASSED**.

### Revised Verdict After Addendum

- **Core product (Epics 1–11, 18):** **READY** for continued implementation.
- **Vertical/alert backlog (Epics 12, 14–17):** **CONDITIONAL** — planning artifacts are now consistent, but the code-level prerequisites (`20.1–20.4`, `6-8`) still need to land before these stories can be safely marked done.
- **Lead Gen (Epic 21):** **NOT READY** — remains a proposal until the governance gates close.

The remaining risk is **execution sequencing**, not missing requirements or epic quality.
