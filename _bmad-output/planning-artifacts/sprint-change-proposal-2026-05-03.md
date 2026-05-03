# Sprint Change Proposal

**Date:** 2026-05-03
**Triggering Issue:** Implementation Readiness Report flagged Critical Violations regarding Technical Epics (8, 10, 11) lacking direct user value, and missing traceability for Epic 10 and 13.

## 1. Issue Summary
- **Problem:** Epics 8 (Integration Testing), 10 (Crypto Data Layer), and 11 (Architecture Resilience) are structured as technical milestones rather than user-centric epics. Additionally, FR Coverage Map in `epics.md` is missing entries for FR36-FR40 and FR49-FR53. Epic 10 violates the "database creation when needed" rule by building a Big Design Up Front data layer.
- **Context:** Identified during the `bmad-check-implementation-readiness` workflow.

## 2. Impact Analysis
- **Epic Impact:** Epics 8, 10, and 11 need to be dissolved. Epic 9 and the new Institutional Terminal Epic will absorb their stories as prerequisites or NFRs.
- **Artifact Conflicts:** `prd.md` and `epics.md` contain structural misalignments. The FR mapping needs an overhaul.
- **Technical Impact:** No code impact. This is purely a planning and architectural traceability correction.

## 3. Recommended Approach
**Option 1: Direct Adjustment**
- **Rationale:** Since no code has been written for these epics, directly refactoring the backlog and documentation is the lowest risk and most efficient path.
- **Effort:** Medium
- **Risk:** Low

## 4. Detailed Change Proposals

### For `epics.md`
- **Delete** Epic 8 (Integration Testing). Convert FR-T1, T2, T3 into Acceptance Criteria for Epic 9 stories.
- **Delete** Epic 10 (Crypto Data Layer). Move FR36-FR40 into "Data Foundation Stories" within Epic 9, and move the watchlist feature to the Institutional Terminal Epic.
- **Delete** Epic 11 (Architecture Resilience).
- **Renumber:** Epic 12 becomes Epic 8. Epic 13 (Institutional Terminal) becomes Epic 9 or 10 depending on the final sequence.
- **Update** the `FR Coverage Map` to include all FRs up to FR53.

### For `prd.md`
- **Rename** "Persistent Shared Crypto Data Layer (Epic 10)" to "Crypto Data Layer Foundation".
- **Move** "Architecture Resilience & Stability (Epic 11)" (FR41-FR45) into the Non-Functional Requirements (NFRs) section.
- **Remove** references to Epic 8, 10, and 11 as standalone epics.

## 5. Implementation Handoff
- **Scope:** Moderate
- **Routing:** Product Owner / Developer agents
- **Responsibilities:** Developer agent will directly execute the file replacements (`prd.md`, `epics.md`, and `sprint-status.yaml`) to implement this proposal.