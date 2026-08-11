---
date: 2026-08-11
---

# Implementation Readiness Re-check — Epic 21 Architecture Enforcement

**Date:** 2026-08-11
**Scope:** Verify that Epic 21 story ACs and UX contracts reflect the cross-epic architecture reuse rules.

## 1. Epic 21 Story AC Coverage (by expected AD)

| Story | ACs | Expected ADs | Missing |
|---|---|---|---|
| 21.1 | 5 | AD-33, AD-37, AD-39 | ✅ None |
| 21.2 | 4 | AD-37, AD-38, AD-11 | ✅ None |
| 21.3 | 4 | AD-25, AD-36 | ✅ None |
| 21.4 | 7 | AD-33, AD-39 | ✅ None |
| 21.5 | 4 | AD-3, AD-40 | ✅ None |
| 21.6 | 3 | AD-41 | ✅ None |
| 21.7 | 4 | AD-8, AD-10, AD-42 | ✅ None |

## 2. UX Contract Architecture Enforcement Check

| Contract | Has Enforcement Section? | ADs referenced |
|---|---|---|
| ux-contract-lead-intelligence-panel.md | ✅ | AD-10, AD-25, AD-3, AD-33, AD-36, AD-37, AD-39, AD-40, AD-42, AD-8 |
| ux-contract-epic21-addendum-2026-08-11.md | ✅ | AD-10, AD-3, AD-39, AD-42, AD-8 |
| ux-contract-positive-reply-notifications.md | ✅ | AD-39, AD-41 |
| ux-contract-sidebar-onboarding.md | ✅ |  |
| ux-contract-workspace-mode-switch.md | ✅ |  |
| ux-contract-tables-directory.md | ✅ | AD-39 |

## 3. Architecture Spine ADs with Enforcement Clauses

- AD-25: ✅ has Enforcement clause
- AD-36: ✅ has Enforcement clause
- AD-37: ✅ has Enforcement clause
- AD-39: ✅ has Enforcement clause
- AD-42: ✅ has Enforcement clause

## 4. Findings

- ✅ All expected cross-epic reuse ADs are referenced in the relevant story ACs.
- ✅ All 6 Epic 21 UX contracts include an Architecture Enforcement section.
- ✅ `ARCHITECTURE-SPINE.md` AD-25, AD-36, AD-37, AD-39, AD-42 all contain explicit Enforcement clauses.

## 5. Updated Readiness Decision

- Epic 21 remains **PROPOSED** and not ready for dev until governance gates close (email-outreach legal/ToS, vendor POC, PII pipeline, CRM sync scope, outcome-pricing attribution).
- The cross-epic reuse risks identified in the duplicate analysis are now **explicitly enforced** in architecture decisions and story ACs.
- Implementation can begin once governance gates close, using the existing `CapabilityRegistry`, `Automation`, `AlertRule`, `pii/redact.py`, `TokenUsage`/`credit_micros_balance`, and `Connection` infrastructure.