# Implementation Readiness Assessment Report

**Date:** 2026-08-10
**Project:** Nowing
**Assessment Type:** Comprehensive (skill-run)
**Source:** `bmad-check-implementation-readiness` workflow

---

## Document Inventory

### PRD Documents
- `prds/prd-Nowing-2026-07-22/prd.md` (~148 KB, canonical whole PRD)
- `prd-requirements-extracted-2026-08-08.md` (reference, marked STALE)

### Architecture Documents
- `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (~118 KB, canonical)
- `architecture/epic21-architecture-update.md` (pre-merge source, merged into SPINE)

### Epics & Stories
- `epics.md` (~203 KB, canonical whole epics/stories file)

### UX Design Documents
- `ux-designs/ux-Nowing-2026-07-22/ux-contract-*.md` (15 canonical UX contracts)
- `ux-design/epic21-lead-intelligence-ux.md` (merged full design reference)

---

## PRD Analysis

Source PRD: `prds/prd-Nowing-2026-07-22/prd.md`

### Functional Requirements

Total: 70 Functional Requirements extracted.

See full list in `implementation-readiness/prd-requirements-extract-skill-2026-08-10.md`.

Key status distribution:
- `[DONE]` / `[BUILT]`: core auth, workspace, RBAC, connectors, KB search, chat, memory, automations, clients, token/credit, deep research metering, degradation, provenance, admin model config.
- `[PROPOSED]`: Epic 21 lead intelligence (FR-63..FR-69), HR vertical scrapers (FR-43..FR-47), chainlens ecosystem integration (FR-58..FR-62), public agent-chat API / agent registry (FR-56..FR-57).
- `[REMOVED]` / `[RE-SCOPED]` / `[DEFERRED]`: FR-48 (Epic 13 moved to chainlens-research), FR-49..FR-52 (feed chainlens-research), FR-53..FR-55 (covered by existing scrapers), FR-5 (AI File Sorting removed).

### Non-Functional Requirements

Total: 12 Non-Functional Requirements extracted.

Includes performance, security/auth, observability, reliability, multi-tenancy, tenant isolation for vertical clients, citation highlight, usage/credit dashboard, recall quality eval gate, deep-research latency/availability, chat regression gate, scraping compliance & anti-bot resilience.

### Additional Requirements / Constraints

- Positioning freeze lifted 2026-08-10 per SCP `sprint-change-proposal-nowing-ai-gen-lead-positioning-2026-08-10.md`.
- NG-1 non-goal updated with exception for structured B2B lead-enrichment deliverables in Vietnam (FR-65/FR-69), subject to legal basis, consent, and audit.
- PII pipeline separated: HR/job data redacted (FR-47/AD-25); lead data stored with `consent_status`/`legal_basis` (pending implementation design).
- Scraper budget gate: 30–50 built-in scrapers; new built-in scrapers require anti-bot/ToS/cost POC.
- TopCV anti-bot POC hard gate before P0 build.
- CRM sync scope aligned: FR-67 phased read-first → write-back → bidirectional per AD-40.

### PRD Completeness Assessment

The PRD is comprehensive and reality-corrected with statuses. Recent 2026-08-10 changes added Epic 21 lead intelligence and resolved governance conflicts via SCP. Remaining open items are implementation gates (vendor contracts, legal/ToS, Zalo OA, PII pipeline) rather than documentation gaps.

---

## Epic Coverage Validation

### Coverage Matrix

See full matrix: `implementation-readiness/fr-coverage-matrix-skill-2026-08-10.md`.

| FR Number | PRD Title | Epic Coverage | Status |
|-----------|-----------|---------------|--------|
| FR-1 | User Authentication | E1 | ✓ Covered |
| FR-2 | API Access for External Clients | E1 | ✓ Covered |
| FR-3 | Workspace Lifecycle | E1/E8.12 | ✓ Covered |
| FR-4 | Workspace Invites & Memberships | E1 | ✓ Covered |
| FR-10 | RBAC với ba system roles | E1 | ✓ Covered |
| FR-6 | Built-in Scraper Connectors | E2/E10 | ✓ Covered |
| FR-7 | External OAuth Connectors | E2 | ✓ Covered |
| FR-8 | External MCP Connectors | E2 | ✓ Covered |
| FR-43..FR-47 | Vietnam job scrapers, aggregator, PII redaction | E12 | ✓ Covered |
| FR-48..FR-62 | Expanded domain/chainlens integration FRs | E13–E20 | ✓ Covered |
| FR-63..FR-69 | Lead Gen Intelligence | E21 | ✓ Covered |
| FR-8.1 | Exa MCP Search Connector | E2.10 | ✓ Covered |
| FR-9,11–13,32–34,36,40 | Knowledge Base + Long-Term Memory | E3 | ✓ Covered |
| FR-14–17,33,42 | Chat & Agents | E4 | ✓ Covered |
| FR-21–23 | Deliverables | E5 | ✓ Covered |
| FR-18–20,35 | Automations | E6 | ✓ Covered |
| FR-25–29 | Multi-surface Clients | E7 | ✓ Covered |
| FR-30,31,41 | Billing / Usage / Token | E8 | ✓ Covered |
| FR-24,37–39 | Deep Research | E9 | ✓ Covered |
| FR-5 | AI File Sorting | — | ❌ REMOVED (no epic; migration 172 removed) |

### Missing Requirements

- **FR-5: AI File Sorting** — intentionally removed from the product (migration 172); it remains as a historical note in the PRD but has no implementation epic. Not a gap.

### Coverage Statistics

- Total PRD FRs: **70**
- FRs covered in epics: **69** (98.6%)
- Coverage percentage: **98.6%**
- FRs intentionally removed with no epic: **1** (FR-5)

### Coverage Assessment

Epic coverage is comprehensive. Every active PRD FR has a traceable epic and story. Epic 21 (Lead Gen Intelligence) correctly covers FR-63..FR-69. The only uncovered FR is the removed FR-5. No implementation-ready FR is missing from the epics.

---

## UX Alignment Assessment

### UX Document Status

**Found:** 15 canonical UX contracts in `ux-designs/ux-Nowing-2026-07-22/`, plus `ux-design/epic21-lead-intelligence-ux.md` (merged full design reference).

Canonical UX contracts:
- `ux-contract-admin-global-model-config.md` (FR-41)
- `ux-contract-agent-registry.md` (FR-57)
- `ux-contract-async-deep-research.md` (FR-24)
- `ux-contract-chat-benchmark.md` (FR-42)
- `ux-contract-ecosystem-search.md` (FR-6, search)
- `ux-contract-first-run-onboarding.md` (FR-40, first-run value)
- `ux-contract-fit-score-badge.md` (FR-64)
- `ux-contract-lead-intelligence-panel.md` (FR-63..FR-69, Epic 21)
- `ux-contract-private-data-provider.md` (FR-60)
- `ux-contract-public-agent-chat-api.md` (FR-56)
- `ux-contract-service-auth-cost.md` (FR-30, FR-31, FR-61)
- `ux-contract-sync-offline-indicator.md` (NFR sync/offline)
- `ux-contract-usage-dashboard.md` (FR-31/NFR-7)
- `ux-contract-vn-jobs-copy.md` (FR-43..FR-47)

### Alignment Issues

- **Epic 21 lead intelligence UX is partially merged.** The lead-intelligence data panel and fit-score badge are covered by canonical contracts, but the full sequencer/CRM/Zalo flows in `epic21-lead-intelligence-ux.md` still need validation and possibly additional canonical contracts for:
  - Zalo OA connection setup (FR-68)
  - CRM connection & field mapping (FR-67)
  - Outcome-pricing display (FR-69)
- The architecture (AD-36..AD-42) supports the data models and API surfaces assumed by these UX contracts, but final UX validation depends on legal/ToS/vendor gates closing first.

### Warnings

- **No canonical UX contract for `FR-65` enriched contact detail view** beyond the lead-intelligence panel. The panel contract covers display at a list level; a drill-down contact card may be needed before implementation.
- **No UX contract for `FR-66` sequencer sequence builder** is in the canonical folder. The full design draft describes it, but a contract-level spec is recommended before dev.
- **FR-5 (AI File Sorting)** is removed, so no UX is needed.

### UX Alignment Conclusion

UX documentation exists and is mostly aligned with PRD and Architecture. The core new surfaces (lead panel, fit-score badge, usage dashboard, agent registry, public agent-chat API, VN jobs) have contracts. Epic 21-specific flows (Zalo, CRM, outcome-pricing, sequence builder) require additional UX contract work once implementation gates are validated.

---

## 4. Epic Quality Review

Source: `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md`

The epic quality review followed best practices for epic/story independence, user value, acceptance criteria quality, and database/entity creation discipline.

### Summary

| Metric | Count |
| --- | --- |
| Distinct epics reviewed | 20 (Epics 1–18, 20, 21; Epic 13 archived) |
| Story-level sections reviewed | 108 |
| Active `ready-for-dev` / P0 / P1 / P2 stories | 50 |
| Active stories missing explicit error-path acceptance criteria | 27 |
| **Critical violations** | **3** |
| **Major issues** | **7** |
| **Minor concerns** | **6** |

### Critical Violations (must fix before dev)

| Epic | Story | Problem | Remediation |
| --- | --- | --- | --- |
| 12 | `Story 12.6` Job Market Alerts | Forward dependency on later `12.9` (Saved Searches) | Reorder so `12.9` precedes `12.6` or merge them |
| 20 | `Story 20.1` Nowing Scraper + NowingIngestService | Requires later `20.4` ChainLensServiceAuth | Reorder `20.4` before `20.1/20.2/20.3` |
| 4 | `Story 4.8d` Chat quality benchmark | No formal AC, only one-line note | Add full G/W/T acceptance criteria with error paths |

### Major Issues

1. **Story 3.9** (DONE) baselines depend on later stories `3.10`, `3.14`, and `8.8`; remove or move baseline ACs to a follow-up story.
2. **Story 8.7** still references renumbered `8.4a` (`→ 8.8`); update and possibly reorder.
3. **Story 9.5** placeholder AC requires SCP approval before dev.
4. **Epic 13** is a pure technical/infrastructure epic; it is archived, so guard against reviving it.
5. **27 active P0/P1/P2 stories** lack explicit error-path acceptance criteria.
6. **Cross-cutting dependencies** on `NowingIngestService`, `ChainLensServiceAuth`, and the AD-33 Generic Alert Engine are assumed by earlier epics without concrete prerequisites.
7. **Epic 21** is `PROPOSED` but has seven detailed stories with incomplete metrics, error paths, and PII/consent gating.

### Minor Concerns

- Done benchmark stories (`4.8a–4.8g`) use one-line `_AC:` notes; acceptable for completed work but not a template.
- Dropped `12.7`/`12.8` have no ACs; acceptable for dropped items.
- Follow-up/tech-debt items are engineer-facing backlog items.
- Status-tag formatting inconsistencies.
- Mixed Vietnamese/English in epic notes.

### Epic Quality Conclusion

The backlog is mostly value-oriented and well-structured, but **the two active forward dependencies (12.6→12.9 and 20.1→20.4) and the missing AC on 4.8d block implementation of those stories** and must be fixed. A broad set of active stories need error-path acceptance criteria, and cross-cutting infrastructure prerequisites need to be made explicit before parallel development across verticals and alert features.

---

## 5. Final Assessment

### Overall Readiness Status

**⛔ NOT READY**

The Nowing planning artifacts are structurally coherent and aligned after the 2026-08-10 SCP, but the remaining P0/P1 implementation gates and the newly discovered epic-quality defects block execution:

1. **Governance / strategic gates** still open (legal/ToS, vendor contracts, Zalo OA business verification, PII/consent pipeline design).
2. **Epic quality defects** must be fixed before parallel development:
   - `Story 12.6` cannot start before later `Story 12.9` (forward dependency).
   - `Story 20.1` cannot start before later `Story 20.4` (forward dependency).
   - `Story 4.8d` lacks testable acceptance criteria.
3. **27 active P0/P1/P2 stories** are missing explicit error-path acceptance criteria.
4. **Cross-cutting dependencies** on `NowingIngestService`, `ChainLensServiceAuth`, and the AD-33 Generic Alert Engine are assumed by earlier epics without concrete implementation prerequisites.
5. **Epic 21** is still `PROPOSED`; its stories lack concrete metrics, error paths, and PII/consent gating.

### Critical Issues Requiring Immediate Action

| # | Issue | Location | Remediation |
| --- | --- | --- | --- |
| 1 | `Story 12.6` depends on later `12.9` | `epics.md` line 1980 | Reorder or merge `12.9` and `12.6` |
| 2 | `Story 20.1` depends on later `20.4` | `epics.md` lines 2211, 2251 | Reorder Epic 20 so `20.4` is first |
| 3 | `Story 4.8d` has no formal AC | `epics.md` line 1118 | Add full G/W/T acceptance criteria |
| 4 | 27 active stories lack error-path ACs | Multiple epics | Add at least one G/W/T error case per active story |
| 5 | `NowingIngestService` / `ChainLensServiceAuth` prerequisites not explicit | Epics 12, 14–17, 20 | Surface prerequisites in each story; implement `20.1` and `20.4` first |
| 6 | Epic 21 is `PROPOSED` but has `ready-for-dev` stories | `epics.md` / `implementation-artifacts/stories/21-*.md` | Keep Epic 21 in a proposal doc until gates close; then rewrite stories with metrics, error paths, and PII/consent gates |
| 7 | PII pipeline design not finalized | AD-38/FR-65/FR-69 | Legal review and consent model for lead-enrichment storage |

### Recommended Next Steps

1. **Fix epic ordering and acceptance criteria** in `epics.md` before any scheduling.
2. **Close open governance gates** (legal/ToS review, vendor POC, Zalo OA business verification).
3. **Design the PII/consent pipeline** and update AD-38 / Epic 21 stories with consent-status fields.
4. **Surface cross-cutting dependencies** (`20.1`, `20.4`, AD-33 Generic Alert Engine) as explicit prerequisites on all dependent stories.
5. **Rewrite Epic 21 stories** with concrete metrics, error paths, and PII/consent gating once governance closes.
6. **Re-run implementation readiness** after the above fixes and gate closures.

### Final Note

This assessment identified **3 critical, 7 major, and 6 minor** epic/story quality issues plus the previously tracked governance/strategic gaps. Address the critical epic-quality defects and open implementation gates before proceeding to development. The planning artifacts can be improved in-place without additional product discovery; the defects are structural and actionable.

---

**Assessment Date:** 2026-08-10
**Assessor:** Mary (Business Analyst) + Sally (UX Designer) + Winston (Architect) + Epic Quality Enforcer
**Report Status:** Final — post-SCP update + Epic Quality Review
