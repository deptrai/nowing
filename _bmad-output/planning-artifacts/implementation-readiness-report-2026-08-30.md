---
name: 'Implementation Readiness Report'
date: '2026-08-30'
project: Nowing
stepsCompleted:
  - step-03-epic-coverage-validation
  - step-01-document-discovery
  - step-02-prd-analysis
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-30
**Project:** Nowing

## Document Discovery

| Document Type | Selected File |
|---|---|
| PRD | `prds/prd-Nowing-2026-07-22/prd.md` |
| Architecture | `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` |
| Epics & Stories | `epics.md` |
| UX Design | `ux-designs/ux-Nowing-2026-08-25/` (primary), `ux-designs/ux-Nowing-2026-08-15/` (supplementary) |

**Notes:**
- PRD exists as both `prd-requirements-extracted-2026-08-08.md` and `prds/prd-Nowing-2026-07-22/prd.md`; canonical `prd.md` selected.
- `ux-design/` contains one-off UX files; `ux-designs/` is the canonical sharded UX directory.

## PRD Analysis

### Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | User Authentication |
| FR-2 | API Access for External Clients |
| FR-3 | Workspace Lifecycle |
| FR-4 | Workspace Invites & Memberships |
| FR-10 | RBAC với ba system roles |
| FR-6 | Built-in Scraper Connectors |
| FR-7 | External OAuth Connectors |
| FR-8 | External MCP Connectors |
| FR-43 | VietnamWorks Scraper (Vietnam Job Market) |
| FR-44 | TopCV Scraper (Vietnam Job Market) |
| FR-45 | ITviec Scraper (Vietnam Job Market) |
| FR-46 | Vietnam Job Market Aggregator (`vn_jobs.aggregate`) |
| FR-47 | PII Redaction for Job Data |
| FR-48 | Canonical Entity Storage & Multi-Domain Indexing (Epic 13) `[REMOVED 2026-08-08 — moved to chainlens-research]` |
| FR-49 | News Aggregation (Epic 14) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` |
| FR-50 | Financial Data Integration (Epic 15) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` |
| FR-51 | Company Data Integration (Epic 16) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` |
| FR-52 | E-commerce Intelligence (Epic 17) `[RE-SCOPED 2026-08-08 — feed to chainlens-research]` |
| FR-53 | Social Media Integration (Epic 18 — REMOVED, feature covered by E10) |
| FR-54 | Search Intelligence (Epic 19 — REMOVED, feature covered by ChainLens) |
| FR-55 | Global E-commerce (Epic 20 — REMOVED, feature covered by E2) |
| FR-56 | Public Agent-Chat API for Vertical Clients |
| FR-57 | Agent Registry |
| FR-58 | Scraper Feed to chainlens-research (Ecosystem Integration) |
| FR-59 | Gap-Fill Trigger via chainlens-research |
| FR-60 | Private Data Provider (NowingPrivateProvider) |
| FR-61 | Cross-Project Service Auth & Cost Allocation |
| FR-62 | Canonical Chunk Metadata Schema (`source` enum) |
| FR-63 | Intent Signal Detection `[IN-PROGRESS]` |
| FR-64 | Lead Scoring & Prioritization `[IN-PROGRESS]` |
| FR-65 | Enriched Contact Data `[IN-PROGRESS]` |
| FR-66 | Outbound Prospecting Automation `[IN-PROGRESS]` |
| FR-67 | CRM Integration & Write-Back `[IN-PROGRESS]` |
| FR-68 | Zalo Integration (Vietnam Market) `[IN-PROGRESS]` |
| FR-8.1 | Exa MCP Search Connector `[DONE 2026-08-05]` |
| FR-9 | Document Upload, Parse & Index |
| FR-11 | Folders & Document Management |
| FR-12 | Hybrid Search over Knowledge Base |
| FR-13 | Citation Panel for Knowledge-base Chunks |
| FR-32 | Long-Term Research Memory  `[DONE — story 3-14; baseline ratified 2026-08-04]` |
| FR-33 | Research Continuity |
| FR-34 | Memory Correction |
| FR-36 | Legacy Memory Data-Loss Assessment & Recovery  `[RESOLVED 2026-07-25 — KHÔNG mất dữ liệu]` |
| FR-40 | First-Run Value — Research Runs Produce Memory  `[DONE — story 3-13]` |
| FR-5 | AI File Sorting `[REMOVED]` |
| FR-14 | Chat Threads & Messages |
| FR-15 | Multi-agent Runtime with Tools `[BUILT — DONE per sprint-status: core multi-agent + tools + auto-extract]` |
| FR-16 | Real-time Collaborative Chat |
| FR-17 | Anonymous Chat with Quota |
| FR-42 | Chat Response Benchmark |
| FR-21 | Report Generation & Export |
| FR-22 | Podcast & Video Presentation |
| FR-23 | Image Generation |
| FR-18 | Automation Action Types  `[DONE — cải chính 2026-07-25]` |
| FR-19 | Automation Triggers |
| FR-20 | Automation Runs & Retries |
| FR-35 | Memory-Driven Automations  `[DONE — cải chính 2026-07-25]` |
| FR-25 | Web Client (Next.js) |
| FR-26 | Desktop Client (Electron) |
| FR-27 | Browser Extension (Plasmo) |
| FR-28 | Obsidian Plugin |
| FR-29 | MCP Server |
| FR-30 | Token Usage Tracking |
| FR-31 | Credit Wallet & Purchases |
| FR-41 | Admin UI cho Global LLM Model Configuration  `[DONE — story 8-11]` |
| FR-69 | Outcome-Based Pricing Option `[IN-PROGRESS]` (mới 2026-08-10) |
| FR-24 | Deep Open-Web Research via ChainLens Engine  `[DONE — contract + regression guard in place; mode default quality→balanced còn 9.3]` |
| FR-37 | Deep-Research Cost Metering  `[DONE — parser + fallback updated; ChainLens costDollars real observed 2026-08-02]` |
| FR-38 | Research Degradation & Self-Host Independence  `[DONE — P0, tiền đề trước khi public repo]` |
| FR-39 | Memory → Scraper-Run Provenance & Source Re-Validation  `[DONE — story 9-6]` |
| FR-93 | Full-Stack Web App Builder & Instant Hosting |
| FR-94 | Design View Mark Tool & Presentation Studio |

**Total FRs:** 72

### Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | Performance |
| NFR-2 | Security & Auth |
| NFR-3 | Observability |
| NFR-4 | Reliability |
| NFR-5 | Multi-tenancy Isolation |
| NFR-6 | Citation Full-Editor Highlight  `[DONE — cải chính 2026-07-25]` |
| NFR-7 | Usage & Credit Dashboard `[DONE]` |
| NFR-8 | Recall Quality (eval-gated) `[DONE — story 3-9]` |
| NFR-9 | Deep-Research Latency & Availability Budget (hai trạng thái) |
| NFR-10 | Chat Response Regression Gate |
| NFR-11 | Scraping Compliance & Anti-Bot Resilience |

**Total NFRs:** 11

### PRD Completeness Assessment

- FR inventory ranges FR-1 through FR-99 (with some FR renumbered/removed/rescoped).
- NFR inventory covers performance, security, observability, reliability, multi-tenancy, citation, recall quality, deep-research latency, chat regression, and scraping compliance.
- PRD `updated: 2026-08-25` and contains amendment integration for Epics 12, 21, 22, 23, 26, 27 and ecosystem alignment.
- Several FRs marked `[REMOVED]`, `[RE-SCOPED]`, or `[DONE]`, which must be reconciled with `epics.md` and `sprint-status.yaml` in subsequent steps.

## Epic Coverage Validation

### Coverage Matrix

Coverage analysis compares PRD requirement headings (FR-1..FR-94) against explicit `epics.md` references.

### Coverage Statistics

- **Total PRD FR headings:** 72
- **FRs covered in epics:** 72 (100%)
- **FR references also found in epics beyond PRD headings:** FR-70..FR-79 (Telegram, Epic 22), FR-80..FR-88 (Lead Gen, Epic 21), FR-89..FR-92 (Enterprise Lead Infrastructure, Epic 23), FR-95..FR-99 (Enterprise Readiness, Epic 28 / Epic 3) — these are sub-FR breakdowns ratified in epics inventory.

### Missing FR Coverage

No PRD FR heading is missing from `epics.md`.

### FRs in Epics Not in PRD Headings

The following FR numbers appear in `epics.md` but do **not** correspond to a top-level `#### FR-XX:` heading in `prd.md`:

- **FR-83** — referenced in `epics.md` as `[DONE]` but no matching PRD heading. Likely a sibling/placeholder of FR-82/84 in Epic 21.
- **FR-90, FR-91, FR-92** — Enterprise lead infrastructure sub-requirements (ratified in epics inventory; PRD mentions in §4.11 `FR-89..FR-92` as a group, not individual headings).
- **FR-96, FR-97, FR-98** — Enterprise Readiness & Compliance sub-requirements (ratified in epics inventory; PRD only lists `FR-95..FR-99` as a group in §6/§4.12).
- **FR-100..FR-104** — New Epic 29 (SaaS Operations & Admin Analytics) requirements added on 2026-08-29. **Not yet in canonical PRD** — this is a legitimate gap because Epic 29 is newer than the last PRD update (2026-08-25).
- **FR-69.2..FR-69.6** — Breakdown of FR-69 Customer Location Profile / Pre-Flight Lead Plan (Epic 26). Ratified in epics inventory as sub-FRs.

### Critical Gap

**FR-100..FR-104 (Epic 29)** are not reflected in `prd.md` because the PRD was last updated `2026-08-25` and Epic 29 was created `2026-08-29`. Recommendation: either amend `prd.md` with a 2026-08-29 PRD amendment ratifying FR-100..FR-104, or keep them as an epic-only addition with a documented traceability note.

## UX Alignment Assessment

### UX Document Status

✅ **Found.** Canonical UX documentation is sharded in `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/` and `ux-Nowing-2026-08-25/`:

- `DESIGN.md` + `EXPERIENCE.md` (Contextual Right Dock, updated 2026-08-25)
- `ux-contract-epic-27-autonomous-workstation.md`
- `ux-contract-first-run-onboarding.md`
- `ux-contract-readiness-gaps.md` (covers Agent Registry, Vertical Client, Benchmark, Pricing, CRM, Memory Bounds, and PRFAQ 1-4 UX contracts)
- `mockups/` HTML files (landing, auth, pricing, workspace lead panel)
- One-off files in `ux-design/` (epic21 wireframes, research origami, right panel fullscreen)

### Alignment Issues

1. **Epic 29.5 Memory Browser / Research Timeline (FR-104) — partial UX contract exists but traceability is stale.**
   - `ux-contract-readiness-gaps.md` §7.1 defines "Memory Browser / Research Timeline (UX-DR-PRFAQ-1)" with MB-1..MB-4.
   - However, the **Traceability table at §8 maps it to `E3 (post-MVP) / FR-95 / UX-DR-PRFAQ-1`**, which is outdated. Epic 29 was created 2026-08-29 and now owns FR-104 with UX-DR-PRFAQ-1 *and* UX-DR-PRFAQ-6.
   - **Recommendation:** Update the UX contract traceability to `Epic 29.5 / FR-104 / UX-DR-PRFAQ-1 / UX-DR-PRFAQ-6`.

2. **Epic 29.1–29.4 (SaaS admin operations console) — no UX contract found.**
   - UX-DR-PRFAQ-5 (SaaS admin operations console) is cited in `epics.md` Stories 29.1–29.4 and 29.6, but no dedicated UX contract exists for:
     - Custom workspace roles & permissions builder (29.1)
     - Workspace health & adoption analytics dashboard (29.2)
     - Tenant subscription tier & quota management (29.3)
     - Admin bulk operations console (29.4)
     - Data governance & retention policy console (29.6)
   - **Risk:** These stories contain specific UI routes (`/dashboard/[workspace_id]/settings/roles`, `/dashboard/[workspace_id]/health`, `/admin/saas/plans`, `/admin/saas/bulk-ops`, `/dashboard/[workspace_id]/governance`) but no wireframes, component patterns, or responsive behavior are documented.

3. **Architecture ↔ UX alignment for Epic 29.**
   - New AD-51..AD-55 in `ARCHITECTURE-SPINE.md` define data models and API contracts (`WorkspaceRole`, `WorkspaceLimit`, `subscription_change`, `bulk_op_job`, `workspace_health_daily`, `memory_review_queue`), but UX does not yet specify how these models surface in the UI (forms, tables, validation feedback, loading states, error states).

### Warnings

- **WARNING-UX-1:** Epic 29 is an `in-planning` / `backlog` epic. Missing UX contracts may be acceptable at this stage, but they **must** be produced before `create-story` implementation begins for 29.1–29.4.
- **WARNING-UX-2:** `FR-104` (memory browser) is a fast-follow item in PRFAQ. The existing UX contract (PRFAQ-1) is sufficient for 29.5 but should be renamed/duplicated as `UX-DR-PRFAQ-6` or explicitly linked to avoid confusion.
- **WARNING-UX-3:** No mockups or `EXPERIENCE.md` sections exist for `/admin/saas/*` routes. This is the largest UX gap for Epic 29.

### Summary

UX documentation exists and is broadly aligned with PRD for Epics already in flight. Epic 29 introduces new UX-DR-PRFAQ-5/6 requirements that are not yet reflected in UX contracts; 29.5 has a stale-traceability contract and 29.1–29.4 have none.

## Epic Quality Review

Focus: **Epic 29** (newly created 2026-08-29) and its 6 stories. Older epics (1–28) have already been implemented or reviewed in previous readiness reports; they are not re-audited here unless they affect Epic 29.

### Epic Structure Validation

#### User Value Focus

- **Epic 29 title:** "SaaS Operations, Advanced Admin Governance & Analyst Workspace" — user-centric (workspace Owner, Superadmin, Analyst).
- **Epic 29 goal:** Describes user outcome (SaaS operations console, health/adoption, memory browser).
- **Value Proposition:** Users can benefit from this epic even if later epics (Growth & Affiliate, etc.) never ship.
- **Verdict:** ✅ User-value epic, not a technical milestone.

#### Epic Independence

- **Dependencies declared:** Epic 1 (auth/RBAC), Epic 3 (memory), Epic 8 (billing), Epic 25 (admin platform), Epic 28 (retention).
- **All dependencies are backward-looking** (already `done` or in-progress, not future).
- **No forward dependency on a later epic.**
- **Verdict:** ✅ Independent as Epic N using only Epic 1–28 outputs.

#### Story Independence (Within-Epic)

| Story | Can complete independently? | Notes |
|---|---|---|
| 29.1 Custom Roles | ✅ | Extends existing `WorkspaceRole` (AD-9, AD-51). No future-story wait. |
| 29.2 Health Dashboard | ⚠️ Partial | Uses `analytics_read` permission that 29.1 defines. If 29.1 is not done, the dashboard can still gate on `Owner`/`Editor` until 29.1 lands. |
| 29.3 Subscription Tier | ✅ | Extends `WorkspaceLimit` + `plan_tier` (AD-8, AD-53). |
| 29.4 Bulk Ops | ⚠️ Partial | `assign_role` and `apply_tier` actions assume 29.1 and 29.3 exist. Other actions (`archive_inactive_workspaces`, `rotate_api_keys`, `revoke_membership`) can land independently. |
| 29.5 Memory Browser | ✅ | Bound to AD-11; no 29.1–29.4 wait. |
| 29.6 Governance Console | ⚠️ Partial | Relies on Story 28.3 policy (already exists) and `WorkspaceDncRecord`. UI-only, so it is independently completable. |

**Verdict:** No **forward** dependencies. Some **same-epic sequential** dependencies (29.2 on 29.1, 29.4 on 29.1/29.3) exist and are acceptable if stories ship in order.

### Acceptance Criteria Quality

All 6 stories use Given/When/Then, are testable, and have error/edge cases (409 Conflict, 403, reserved name, 7-day reversal, idempotency).

**Remaining AC issues (major, not critical):**

1. **29.2 "source coverage gaps"** is still not defined as a formula (e.g. "sources with 0 memories in last 30d" vs "enabled sources with < N documents"). Implementation will guess.
2. **29.3 `max_monthly_credits` / `max_sources` / `support_level`** are listed as `WorkspaceLimit` fields. Need to confirm they already exist or will be added in 29.3. Existing `WorkspaceLimit` has `max_documents/members/runs/storage_bytes/memory_count/memory_bytes` — `max_monthly_credits`, `max_sources`, `support_level`, `price_micros`, `currency` may be new columns.
3. **29.5 `< 300ms` at 100k memories** is now index-backed, which is good. Still no mention of pagination default (`limit`/`offset` or cursor).
4. **29.6 "Global DNC vs workspace DNC"** still has a leftover ambiguity: "Global DNC (Epic 25.6, `WorkspaceDncRecord` or global list) is configurable tùy deploy mode" — two different tables are conflated.

### Best Practices Compliance Checklist (Epic 29)

- [x] Epic delivers user value
- [x] Epic can function independently (using Epic 1–28)
- [x] Stories appropriately sized (6 stories, each independently shippable with sequential caveats)
- [x] No forward dependencies
- [x] Database tables created when needed (each story owns its tables: `workspace_health_daily`, `subscription_change`, `bulk_op_job`, `idempotency_keys`, `memory_review_queue`)
- [x] Clear acceptance criteria (Given/When/Then)
- [x] Traceability to FRs maintained (FR-100..FR-104)
- [ ] UX contracts for 29.1–29.4, 29.6 (see Step 4)
- [ ] PRD amendment for FR-100..FR-104 (see Step 3)

### Quality Findings by Severity

#### Critical Violations

None for Epic 29. No technical-milestone epic, no forward dependency, no epic-sized story.

#### Major Issues

1. **PRD not updated for FR-100..FR-104.** Epic 29 invented 5 new FRs that are not in `prd.md`. Traceability is one-way (epics → FRs) without a PRD source of truth.
2. **UX-DR-PRFAQ-5 has no UX contract.** Stories 29.1–29.4 and 29.6 specify UI routes without wireframes or EXPERIENCE.md. Implementation will invent UX.
3. **29.2 `analytics_read` permission** is introduced in 29.1; if 29.2 ships first, the dashboard will have no permission to check. Recommendation: either (a) ship 29.1 first, or (b) temporarily gate 29.2 on Owner/Editor until 29.1 lands.
4. **29.3 schema drift vs `WorkspaceLimit`.** AC lists `max_monthly_credits`, `max_sources`, `support_level`, `price_micros`, `currency` — these may not exist on the current `WorkspaceLimit` model. Story 29.3 must include a migration, not assume the columns exist.

#### Minor Concerns

1. **29.2 "source coverage gaps"** undefined.
2. **29.5 pagination default** unspecified.
3. **29.6 Global vs workspace DNC** wording still slightly conflates Epic 25.6 global DNC with `WorkspaceDncRecord`.
4. **29.4 `rotate_api_keys` MFA** is specified without a corresponding architecture decision on how MFA is stored/verified for superusers.
5. **Story files not created.** `sprint-status.yaml` correctly marks 29-1..29-6 as `backlog` (planning only). This is expected; `create-story` is the next workflow, not a quality defect.

### Remediation Guidance

1. **Before `create-story` 29.1:** Amend `prd.md` with FR-100..FR-104 (or write `AMENDMENT-Epic-29-SaaS-Admin-Analytics-2026-08-29.md`).
2. **Before `create-story` 29.1–29.4:** Author `ux-contract-epic-29-saas-admin.md` covering roles builder, health dashboard, plans, bulk-ops, governance. Re-point PRFAQ-1 memory browser contract to Epic 29.5 / FR-104.
3. **Story 29.2:** Define "source coverage gap" as a formula in AC (e.g. `enabled source types with 0 memories in selected range`).
4. **Story 29.3:** Explicitly list which `WorkspaceLimit` columns already exist vs which 29.3 will add.
5. **Story 29.5:** Specify default page size (e.g. 50) and cursor vs offset.
6. **Story 29.6:** Split "workspace DNC (`WorkspaceDncRecord`)" from "global DNC (Epic 25.6)" into two distinct AC bullets.


## Remediation Log (2026-08-30)

The following critical and major issues from the original assessment have been addressed:

### 1. PRD missing FR-100..FR-104 — RESOLVED

- Added new section `### 4.11 SaaS Operations, Advanced Admin Governance & Analyst Workspace` to `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`.
- Added FR-100, FR-101, FR-102, FR-103, FR-104 with full AC, consequences, status, and architecture binding.
- Updated PRD frontmatter `updated: 2026-08-30`.
- Updated consolidated amendments matrix in §0 with "SaaS Operations & Admin Governance" row.

### 2. Missing UX contracts for UX-DR-PRFAQ-5 — RESOLVED

- Created `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md`.
- Covered RB (Roles), HD (Health Dashboard), PM (Plan Management), BO (Bulk Ops), GV (Governance), and MB (Memory Browser) with mandatory UI states.
- Updated mapping to stories and architecture decisions.

### 3. 29.5 stale traceability (E3/FR-95) — RESOLVED

- Updated `ux-contract-readiness-gaps.md` §8 traceability: `Memory Browser / Research Timeline` now maps to `Epic 29.5 / FR-104 / UX-DR-PRFAQ-1+6`.

### 4. Epic 29 AC refinements — RESOLVED

- **29.2:** Defined `source coverage gap` formula; added fallback note for `analytics_read` if 29.1 not shipped.
- **29.3:** Clarified `WorkspaceLimit` plan-definition XOR constraint and which columns are added by 29.3.
- **29.4:** Noted `assign_role`/`apply_tier` same-epic dependencies.
- **29.5:** Added default page size 50 and page-size selector.
- **29.6:** Split workspace DNC (`WorkspaceDncRecord`) from global DNC (Epic 25.6) into two distinct AC bullets.

---

## Summary and Recommendations

### Overall Readiness Status

**READY FOR CREATE-STORY**

Sau khi bổ sung PRD, UX contract, và chỉnh sửa Epic 29 AC, các lỗ hổng traceability và thiết kế chính đã được khắc phục. Epic 29 giờ có FR đầy đủ trong PRD, UX contract rõ ràng, architecture spine AD-51..AD-55, và AC đã được làm rõ.

### Critical Issues Requiring Immediate Action

Không còn critical issue nào chặn `create-story`.

### Major Issues Remaining

1. **Story sizing vẫn lớn** — 29.1..29.6 mỗi story có 6–7 AC lớn. Khuyến nghị đội create-story xem xét tách nhỏ khi viết story files (ví dụ 29.4 dry-run vs execute).
2. **Thứ tự triển khai** — 29.1 nên ship trước 29.2/29.4 để `analytics_read` và `assign_role` có ý nghĩa.
3. **MFA cho `rotate_api_keys`** — UX contract đã có BO-6 nhưng cần architecture decision riêng về cách lưu trữ/xác minh MFA cho superadmin (nằm ngoài scope Epic 29 hiện tại, nên tách thành spike hoặc sub-story).

### Recommended Next Steps

1. Chạy `/bmad:bmm:workflows:create-story` cho 29.1..29.6, tuân thủ thứ tự 29.1 → 29.2 → 29.3 → 29.4 → 29.5 → 29.6.
2. Khi create-story, xem xét tách 29.4 thành dry-run + execute + idempotency sub-stories.
3. Chuẩn bị migration schema cho `workspace_health_daily`, `subscription_change`, `bulk_op_job`, `bulk_op_errors`, `idempotency_keys`, `memory_review_queue`.
4. Kiểm tra lại `WorkspaceLimit` columns hiện có trước khi viết migration cho 29.3.

### Final Note

Đánh giá ban đầu xác định 2 critical + 4 major + 3 minor. Sau remediation: 0 critical, 0 major chặn create-story, 1 major về sizing, 1 major về MFA cần spike. Epic 29 đã sẵn sàng để chuyển sang giai đoạn create-story.

---

**Assessor:** Implementation Readiness Facilitator  
**Remediation Date:** 2026-08-30
