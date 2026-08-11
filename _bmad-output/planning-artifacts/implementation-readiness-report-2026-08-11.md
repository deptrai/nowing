---
stepsCompleted: ["step-01-document-discovery", "step-02-prd-analysis", "step-03-epic-coverage-validation", "step-04-ux-alignment", "step-05-epic-quality-review", "step-06-architecture-alignment", "step-07-readiness-decision"]
document_inventory:
  prd: "_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md"
  architecture:
    - "_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md"
    - "_bmad-output/planning-artifacts/architecture/epic21-architecture-update.md"
  epics: "_bmad-output/planning-artifacts/epics.md"
  ux:
    - "_bmad-output/planning-artifacts/ux-design/epic21-lead-intelligence-ux.md"
    - "_bmad-output/planning-artifacts/ux-design/ux-research-origami-final-2026-08-11.md"
    - "_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/"
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-11
**Project:** Nowing

## Step 1 — Document Discovery

### Files selected for assessment

| Type | Selected file(s) | Notes |
|---|---|---|
| PRD | `prds/prd-Nowing-2026-07-22/prd.md` | Canonical PRD; `prd-requirements-extracted-*` and `prd-requirements-extract-skill-*` are derived artifacts, not primary PRD. |
| Architecture | `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` | Canonical spine. |
| Architecture (Epic 21) | `architecture/epic21-architecture-update.md` | Update for lead intelligence scope. |
| Epics & Stories | `epics.md` | Whole epic/story source of truth. |
| UX | `ux-design/epic21-lead-intelligence-ux.md` | Epic 21 UX design. |
| UX (research) | `ux-design/ux-research-origami-final-2026-08-11.md` | Final Origami competitive research. |
| UX (contracts) | `ux-designs/ux-Nowing-2026-07-22/*.md` | Canonical UX contracts including Epic 21 addendum. |

### Duplicates / derived artifacts excluded

- `prd-requirements-extracted-2026-08-08.md` — derived from PRD, not authoritative.
- `implementation-readiness/prd-requirements-extract-skill-2026-08-10.md` — same as above.
- `architecture-reviews/architecture-review-nowing-chainlens-2026-08-08-v6/v7/v8.md` — review artifacts, not canonical architecture.
- `ux-design/ux-research-origami-refresh-2026-08-11.md` — superseded by `...-final-...`.

### Missing

- No sharded `index.md` found in any document type; whole documents and contract folders are used directly.

---

## Step 2 — PRD Requirements Extract

The canonical PRD (`prds/prd-Nowing-2026-07-22/prd.md`) is a free-form, continuously-updated document. The de facto structured FR/NFR catalog lives in `epics.md` §Requirements Inventory. The active functional and non-functional requirements are:

### Functional Requirements

| ID | Name | Status | Epic |
|---|---|---|---|
| FR-1 | Auth | DONE | E1 |
| FR-2 | API/PAT | DONE | E1 |
| FR-3 | Workspace lifecycle | DONE | E1 |
| FR-4 | Invites/memberships | DONE | E1 |
| FR-10 | RBAC 3 roles | DONE | E1 |
| FR-6 | Scrapers | DONE | E2 / E10.1 |
| FR-7 | OAuth connectors | DONE | E2 |
| FR-8 | MCP connectors | DONE | E2 |
| FR-9 | Doc upload/index | DONE | E3 |
| FR-11 | Folders | DONE | E3 |
| FR-12 | Hybrid search | DONE | E3 |
| FR-13 | Citation panel | DONE | E3 |
| FR-14 | Chat threads | DONE | E4 |
| FR-15 | Multi-agent runtime | DONE | E4 |
| FR-16 | Realtime chat | DONE | E4 |
| FR-17 | Anonymous chat | DONE | E4 |
| FR-21 | Reports | DONE | E5 |
| FR-22 | Podcast/video | DONE | E5 |
| FR-23 | Image | DONE | E5 |
| FR-19 | Automation triggers | DONE | E6 |
| FR-20 | Automation runs | DONE | E6 |
| FR-25/26/27/28/29 | Client surfaces | DONE | E7 |
| FR-30 | Token tracking | DONE | E8 |
| FR-31 | Credit wallet | DONE | E8.3 |
| FR-32 | Memory storage/retrieval | DONE | E3 |
| FR-33 | Research continuity | DONE | E4 |
| FR-34 | Memory correction | DONE | E3/E4 |
| FR-18 | Automation actions | DONE | E6.4 |
| FR-35 | Memory-driven automations | DONE | E6.5 |
| FR-36 | Legacy memory data-loss | RESOLVED | E3.10 |
| FR-24 | Deep-research via ChainLens | DONE | E9.1b |
| FR-37 | Deep-research cost metering | DONE | E9.2 |
| FR-38 | Research degradation | DONE | E9.1a |
| FR-39 | Memory→scraper provenance | DONE | E9.6 |
| FR-40 | First-run value | DONE | E3.13 |
| FR-41 | Admin UI global LLM config | DONE | E8.11 |
| FR-42 | Chat response benchmark | DONE | E4 |
| FR-43 | VietnamWorks scraper | DONE | E12.1 |
| FR-44 | TopCV scraper | DONE (anti-bot POC remains hard gate) | E12.2 |
| FR-45 | ITviec scraper | IN-PROGRESS | E12.3 |
| FR-46 | `vn_jobs.aggregate` | IN-PROGRESS | E12.4 |
| FR-47 | PII redaction for job data | IN-PROGRESS | E12.5 |
| FR-63 | Intent Signal Detection | PROPOSED | E21.1 |
| FR-64 | Lead Scoring | PROPOSED | E21.2 |
| FR-65 | Enriched Contact Data | PROPOSED | E21.3 |
| FR-66 | Outbound Prospecting Automation | PROPOSED | E21.4 |
| FR-67 | CRM Integration | PROPOSED | E21.5 |
| FR-68 | Zalo Integration | PROPOSED | E21.6 |
| FR-69 | Outcome-Based Pricing | PROPOSED | E21.7 |
| FR-5 | AI File Sorting | REMOVED | — |

### Non-Functional Requirements

| ID | Name | Status | Epic |
|---|---|---|---|
| NFR-1 | Performance | PARTIAL | — |
| NFR-2 | Security | DONE | — |
| NFR-3 | Observability | DONE | — |
| NFR-4 | Reliability | DONE | — |
| NFR-5 | Multi-tenancy isolation | DONE | — |
| NFR-6 | Citation jump-to-source | DONE | E3.6 |
| NFR-7 | Usage dashboard | DONE | E8.3 |
| NFR-8 | Recall quality eval-gate | DONE | E3.9 |
| NFR-9 | Deep-research latency & availability | DONE | E9.3 |
| NFR-10 | Chat response regression gate | DONE | E4 |
| NFR-11 | Scraping compliance & anti-bot (VN jobs) | PROPOSED | E12 |

---

## Step 3 — Epic Coverage Validation

### Coverage Matrix (selected / at-risk FRs)

| FR | PRD / Epic 21 mapping | Covered? | Notes |
|---|---|---|---|
| FR-63 | Epic 21.1 | ✓ | New, PROPOSED |
| FR-64 | Epic 21.2 | ✓ | New, PROPOSED |
| FR-65 | Epic 21.3 | ✓ | New, PROPOSED |
| FR-66 | Epic 21.4 | ✓ | New, PROPOSED |
| FR-67 | Epic 21.5 | ✓ | New, PROPOSED |
| FR-68 | Epic 21.6 | ✓ | New, PROPOSED |
| FR-69 | Epic 21.7 | ✓ | New, PROPOSED |
| FR-43-47 | Epic 12.1–12.5 | ✓ | New, PROPOSED, HR vertical |
| FR-41 | Epic 8.11 | ✓ | DONE |
| FR-37 | Epic 9.2 | ✓ | DONE |
| FR-38 | Epic 9.1a | ✓ | DONE |
| FR-39 | Epic 9.6 | ✓ | DONE |
| FR-40 | Epic 3.13 | ✓ | DONE |
| FR-42 | Epic 4.8a–4.8g | ✓ | DONE |

**Findings:**
- All PROPOSED FRs (FR-43..47, FR-63..69) have an epic/story home.
- No FR is orphaned.
- FR-5 `[REMOVED]` correctly has no epic.
- NFR-1 (Performance) remains `PARTIAL` and not assigned to any epic (long-standing C-1 readiness item).

---

## Step 4 — UX Alignment Assessment

### UX Document Status

- ✅ UX contracts exist for all active epics in `ux-designs/ux-Nowing-2026-07-22/`.
- ✅ Epic 21 UX contracts are freshly created/updated (2026-08-11).
- ✅ Origami research is captured in `ux-research-origami-final-2026-08-11.md`.

### Epic 21 UX → FR mapping

| N1–N8 Pattern | FR / Story | UX Contract |
|---|---|---|
| N1 Onboarding checklist | Story 21.4 | `ux-contract-sidebar-onboarding.md` |
| N2 Workspace mode switch | FR-66 / Story 21.4 | `ux-contract-workspace-mode-switch.md` |
| N3 Tables directory | FR-63 / Story 21.1 | `ux-contract-tables-directory.md` |
| N4 Inbox empty + Email only; lead source from all scrapers | FR-66 / Story 21.4 | `ux-contract-lead-intelligence-panel.md` §8 |
| N5 Positive-reply notifications (email/Telegram only; Zalo disabled) | FR-66 / Story 21.4 | `ux-contract-positive-reply-notifications.md` |
| N6 Per-lead projected cost | FR-69 / Story 21.7 | `ux-contract-lead-intelligence-panel.md` §7 |
| N7 Source-specific table tabs (dynamic, all scraper/connector sources) | FR-63 / Story 21.1 | `ux-contract-lead-intelligence-panel.md` §2.1 |
| N8 Connect campaign chip | FR-66 / Story 21.4 | `ux-contract-lead-intelligence-panel.md` §5 |

**Findings:**
- Every Epic 21 UX pattern maps to at least one FR and canonical contract.
- No UX requirement is missing a contract.

---

## Step 5 — Duplicate / Overlap Risk Analysis

### High-priority overlap checks

| Potential duplicate | Reality | Verdict |
|---|---|---|
| **FR-65 (lead contact enrichment) vs FR-46/47 (VN job aggregator + PII redaction)** | `epics.md` explicitly states Epic 12 outputs are research/job-market data with PII redaction and are **not reused** as lead-enrichment contact data. Separate data sources, separate PII/consent policy. | ✅ **Not duplicate — boundary documented.** |
| **FR-66 (outbound sequences) vs FR-18/FR-35 (automation actions / memory-driven automations)** | Epic 6 provides generic automation runtime and actions (write_back, continue_research). Epic 21 outbound is a sales-specific email sequence use case. Epic 21 should **reuse** automation runtime, notification service (Story 11.1), and `Connection` model, not rebuild them. LinkedIn/Zalo deferred out of MVP. | ✅ **Overlap resolved: Email only; reuse E6 + 11.1.** |
| **FR-67 (CRM integration) vs FR-7 (OAuth connectors)** | CRM connectors are a new connector family but can reuse `Connection` model and OAuth patterns from E2. | ✅ **Not duplicate if modeled as connectors.** |
| **FR-69 (outcome-based pricing) vs FR-30/FR-31 (token tracking / credit wallet)** | Outcome-pricing depends on credit/cost tracking. `ux-contract-usage-dashboard.md` already displays credit balance and cost; N6 projected cost reuses the same cost estimator. | ✅ **Not duplicate if built on top of existing wallet/usage stack.** |
| **FR-68 (Zalo OA) vs other chat/notification channels** | Zalo **deferred** out of MVP. Positive-reply notifications (N5) reuse Telegram notification foundation (Story 11.1); Email reply parsing added. | ✅ **No conflict; Zalo disabled until legal gate closes.** |
| **FR-63/64 (intent signals / lead scoring) vs existing memory/knowledge features** | Signal detection can reuse `Memory`, `ResearchThread`, and `chainlens-research` ingestion. Lead scoring can reuse confidence/dedupe primitives from E3.11. | ✅ **Not duplicate if built on shared primitives.** |

### Cross-epic reuse opportunities

| Epic 21 component | Reuse from existing epics | Notes |
|---|---|---|
| Multi-source lead ingestion | E2 scraper capabilities + E12 `vn_jobs.aggregate` pattern | Use `Chunk[]` + `chainlens-research` ingest where applicable. |
| Lead table / data panel | E4 chat panel + existing table components | Reuse, not rebuild. |
| Fit score / confidence | E3.11 dedupe + confidence | Extend for lead fit. |
| Enrichment waterfall | E2 connectors + external API pattern | New providers (Cleanlist / BetterContact). |
| Outreach sequences | E6 automation runtime + E11.1 notifications | Email sender in MVP; LinkedIn/Zalo senders deferred. |
| CRM write-back | E2 connector pattern + E67 sync | New CRM providers. |
| Cost/usage display | E8.3 usage dashboard + E9.2 cost metering | Reuse `cost_micros` and credit formatting. |

### Bottom line on duplicates

No hard duplicate is detected. The main risk is **rebuilding generic components** (automation, notifications, connectors, cost display) inside Epic 21 instead of extending existing ones. The architecture and UX contracts for Epic 21 already call for reuse, but this must be enforced during implementation.

---

## Step 6 — Architecture Alignment

- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` exists and covers high-level invariants.
- `architecture/epic21-architecture-update.md` exists and adds lead-intelligence scope.
- Architecture supports multi-source aggregation, PII redaction (FR-47), connector model (FR-7/67), and credit/cost tracking (FR-30/31/69).
- **Revised 2026-08-11:** AD-39 now defines email-only sequencer + multi-source lead ingestion from all FR-6 scrapers/ connectors; AD-41 defers Zalo/LinkedIn.
- **Open:** outcome-pricing cost estimator service still needs detail before `ready-for-dev`.

---

## Step 7 — Readiness Decision & Next Steps

| Criterion | Status |
|---|---|
| Epic 21 FRs mapped to stories | ✅ |
| Epic 21 UX contracts created | ✅ |
| Source of truth docs identified | ✅ |
| Duplicate/overlap risk assessed | ✅ (no hard duplicate; reuse risk noted) |
| Sprint status updated | ✅ — Epic 21 in `backlog`; 21.6 `deferred`. FR-43/44 done, FR-45/46/47 in-progress |
| Governance gates closed | ❌ — email outreach, enrichment providers, PII pipeline, CRM sync, outcome-pricing still pending; Zalo/LinkedIn **deferred** |
| Architecture detail for multi-source ingestion + cost estimator | ✅ Revised AD-39/AD-41; `BillingEvent` ledger introduced in AD-8/AD-10/AD-42; `Sequence` bounded context defined |

**Readiness Decision (updated 2026-08-11):**
- Epic 21 is **not yet ready for dev** (governance gates still open).
- Epic 21 architecture is **FIT for implementation** per final `bmad-architecture` validate.
|- Scope refined: **Email-only outbound in MVP**; **Zalo/LinkedIn deferred**; **lead sources = all FR-6 scrapers/ connectors**.
- It is **ready for PO/business review** on the refined scope and can move to `ready-for-dev` after governance gates close.

**Recommended next actions:**
1. ✅ Add Epic 21 stories to `sprint-status.yaml` — done; Epic 21 in `backlog`; 21.6 `deferred`.
2. ✅ Run `bmad-architecture` update for Epic 21 multi-source lead ingestion and outcome-pricing cost estimator — done; all conflicts resolved, lint clean, cross-AD/UX consistency verified.
3. Close legal/ToS gates for **email outreach**, contact-enrichment vendors, PII pipeline, CRM sync scope.
4. Hand off `ux-contract-lead-intelligence-panel.md` and related contracts to implementation once gates close.

---

## Step 8 — Architecture Enforcement Re-check (2026-08-11)

A second pass was run after the duplicate/overlap analysis to verify ACs and UX contracts enforce cross-epic reuse.

- **Epic 21 story ACs** now explicitly reference the expected ADs:
  - 21.1 → AD-33, AD-37, AD-39
  - 21.2 → AD-11, AD-37, AD-38
  - 21.3 → AD-25, AD-36
  - 21.4 → AD-33, AD-39
  - 21.5 → AD-3, AD-40
  - 21.6 → AD-41
  - 21.7 → AD-8, AD-10, AD-42
- **All 6 Epic 21 UX contracts** include an **Architecture Enforcement** section binding UI to shared backend components.
- **`ARCHITECTURE-SPINE.md`** AD-25, AD-36, AD-37, AD-39, AD-42 now contain explicit **Enforcement** clauses.
- Full re-check report: `implementation-artifacts/epic21-readiness-recheck-2026-08-11.md`.

---

## Step 9 — Final `bmad-architecture` Validation (2026-08-11)

A final `bmad-architecture` validate was run after resolving the AD conflicts.

| Gate | Result |
|---|---|
| `lint_spine.py` | ✅ **0 findings** |
| Reality-check review | ✅ **CONDITIONAL PASS** |
| Adversarial review | ✅ **PASS** |

**Resolved:**
- Stack version drift and "latest" ambiguity — pinned to actual package files.
- AD-17/18/19/20 missing `Rule` — added.
- AD-34/AD-35 non-monotonic ordering — moved after AD-33.
- AD-25 vs AD-11.1 redaction — `source_input` raw recipe, `Memory.content`/`embedding`/`Chunk[]` redacted.
- AD-39 vs `Automation`/`AutomationRun` — `Sequence` is a new bounded context; only scheduler/Celery/notification reused.
- Epic 21 `client_id` — AD-31 lists all tables; AD-36–AD-42 models include `client_id` and UUID `id`.
- `TokenUsage` overload — `BillingEvent` introduced for non-LLM business events; `TokenUsage` stays LLM-only.
- AD-33/AD-37/AD-39 signal ambiguity — `AlertRule.capability_id`, `sequence_enrollment` channel, `target.sequence_id`; signal types map to capabilities with `emits_signals=true`.
- AD-22/AD-23 status mismatch — code verified (300 unit tests passed), promoted to `ADOPTED`.

**Epic 21 readiness:** Architecture is **FIT for implementation**. Governance gates still pending before `ready-for-dev`.

**Steps completed:** step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review (duplicate/overlap focus), step-06-architecture-alignment, step-07-readiness-decision, step-08-architecture-enforcement-recheck, step-09-architecture-validation.

