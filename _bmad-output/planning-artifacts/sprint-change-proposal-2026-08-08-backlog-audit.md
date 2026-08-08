# Sprint Change Proposal: Backlog Audit — Conflict/Duplicate/Alignment

**Date:** 2026-08-08
**Trigger:** Implementation Readiness Report v3 + Correct Course workflow
**Scope:** Full backlog review (Epic 12-18) against shipped features (Epic 1-11) + Architecture Spine (AD-1 → AD-33)
**Mode:** Batch

## Section 1: Issue Summary

### Problem Statement

Implementation Readiness Report v3 identified 17 issues (all resolved). Correct Course workflow performed deeper analysis across 3 dimensions:

1. **Conflict/Duplicate with shipped features** — alert stories (12.6, 12.7, 14.3, 15.3, 16.3, 17.3) propose standalone implementations when Epic 6 + AD-33 already provide Generic Alert Engine
2. **Backlog health** — 15 Extended Epic stories missing from sprint-status.yaml, 2 tech debt stories (td-5, td-6) untracked
3. **Architecture alignment** — 10 stories missing critical AD references (AD-33, AD-27, AD-24), risking implementation without architectural guidance

### Evidence

- AD-33 (accepted 2026-08-08) explicitly binds Stories 12.6, 12.7, 12.9, 14.3, 15.3, 15.4, 16.3, 17.3, 17.4 as AlertRule templates
- Stories 12.6-12.9, 14.2-14.4, 15.2-15.4, 16.2-16.4, 17.2-17.4 exist in epics.md but NOT in sprint-status.yaml
- td-5, td-6 documented in deferred-work.md but missing from sprint-status.yaml tech-debt epic

## Section 2: Impact Analysis

### Epic Impact

| Epic | Impact | Details |
|------|--------|---------|
| Epic 12 | MAJOR | 4 stories need AD references; 12.6-12.9 need sprint-status entries |
| Epic 13 | NONE | Already well-aligned (AD-27, AD-28, AD-24 all referenced) |
| Epic 14 | MAJOR | 14.3 needs AD-33; 14.2-14.4 need sprint-status entries |
| Epic 15 | MAJOR | 15.3, 15.4 need AD-33; 15.2-15.4 need sprint-status entries |
| Epic 16 | MAJOR | 16.3 needs AD-33, 16.4 needs AD-27; 16.2-16.4 need sprint-status entries |
| Epic 17 | MAJOR | 17.3, 17.4 need AD-33; 17.2-17.4 need sprint-status entries |
| Epic 18 | NONE | Already well-aligned (AD-29, AD-30, AD-31 all referenced) |

### Story Impact

**Stories needing AD reference additions (15 stories):**

| Story | Missing ADs | Severity |
|-------|-------------|----------|
| 12.1 | AD-22 | MAJOR |
| 12.2 | AD-23 | MAJOR |
| 12.3 | AD-23 | MAJOR |
| 12.4 | AD-24, AD-27 | CRITICAL |
| 12.6 | AD-33 | CRITICAL |
| 12.7 | AD-27, AD-33 | CRITICAL |
| 12.8 | AD-27 | CRITICAL |
| 12.9 | AD-33 | MAJOR |
| 14.3 | AD-33 | CRITICAL |
| 15.3 | AD-33 | CRITICAL |
| 15.4 | AD-33 | CRITICAL |
| 16.3 | AD-33 | CRITICAL |
| 16.4 | AD-27 | CRITICAL |
| 17.3 | AD-33 | CRITICAL |
| 17.4 | AD-33 | CRITICAL |

**Stories needing sprint-status.yaml entries (15 stories):**

| Story | Status | Epic |
|-------|--------|------|
| 12-6 | backlog | Epic 12 |
| 12-7 | backlog | Epic 12 |
| 12-9 | backlog (P0) | Epic 12 |
| 14-2 | backlog | Epic 14 |
| 14-3 | backlog | Epic 14 |
| 14-4 | backlog | Epic 14 |
| 15-2 | backlog | Epic 15 |
| 15-3 | backlog | Epic 15 |
| 15-4 | backlog | Epic 15 |
| 16-2 | backlog | Epic 16 |
| 16-3 | backlog | Epic 16 |
| 17-2 | backlog | Epic 17 |
| 17-3 | backlog | Epic 17 |
| 17-4 | backlog | Epic 17 |

**Tech debt stories needing sprint-status entries (2 stories):**

| Story | Status | Source |
|-------|--------|--------|
| td-5 | backlog | deferred-work.md (title_gen.py timeout/retry) |
| td-6 | backlog | deferred-work.md (verify_chat_image_capability.py retries) |

### Artifact Conflicts

- **PRD:** No conflicts — all FRs remain valid
- **Architecture:** No violations found — only missing references to accepted ADs
- **UX:** No conflicts — UX contracts already aligned (verified in readiness report Step 4)

### Technical Impact

- **No code changes needed** — all changes are documentation/tracking
- **Risk if not fixed:** Alert stories implemented without AD-33 reference → standalone schedulers built instead of AlertRule templates → architecture debt
- **Risk if not fixed:** Extended Epic stories untracked → dev-story workflow can't pick them up

## Section 3: Recommended Approach

### Selected: Option 1 — Direct Adjustment

**Rationale:**
- All issues are documentation/tracking gaps, not architectural problems
- No code changes, no PRD changes, no architecture changes
- Low effort, low risk, high value (prevents future implementation mistakes)
- Effort: LOW (2-3 hours of documentation updates)
- Risk: LOW (additive changes only)

### Changes Applied

**1. epics.md — Add AD references to 15 stories**
- Add `_AD-XX_` footer references to stories missing them
- No AC changes, no story scope changes

**2. sprint-status.yaml — Add 15 Extended Epic stories + 2 tech debt stories**
- Add entries under respective epic sections
- All marked `backlog` (not yet ready for dev)
- 12-9 marked with P0 priority note

**3. sprint-status.yaml — Update last_updated**

## Section 4: PRD MVP Impact

**MVP NOT affected.** All changes are backlog documentation improvements. No FR changes, no scope changes, no priority changes to active sprint.

## Section 5: Agent Handoff Plan

| Role | Responsibility |
|------|---------------|
| Developer (this session) | Apply all documentation changes to epics.md + sprint-status.yaml |
| Product Owner | Review SCP, approve changes |
| Architect | Verify AD references are correct (no new ADs needed) |
| Dev Story agent | Pick up 12-1 through 12-5 (already ready-for-dev) |

## Section 6: Approval

**Status:** PENDING — awaiting user approval to apply changes

## Appendix: Conflict/Duplicate Findings

### Intentional Reuse (No Action Needed)

| Story | Shipped Feature | Why Intentional |
|-------|----------------|------------------|
| 12.4 (Job Aggregator) | Epic 10.4 (BDS Aggregator) | Copy-modify pattern, documented in epics.md |
| Epic 13 (Canonical Storage) | Epic 10.4/12.4 aggregators | Shared storage layer, not replacing domain matching |
| 18.1 (Public Agent-Chat) | Epic 4 (Chat endpoints) | Different auth model (PAT vs session) |
| 18.6 (Memory Tagging) | Epic 3 (Memory table) | Additive extension for multi-tenant isolation |
| 7.4 (Connectors Page) | Connector modal | UX enhancement, AD-32 deprecation plan |
| 6.7 (Schema-Driven UI) | Automation builder UI | Pattern to avoid per-tool UI debt |

### Alert Pattern Conflicts (Action: Add AD-33 References)

| Story | Alert Type | AD-33 Diff Strategy |
|-------|-----------|---------------------|
| 12.6 | Job market alerts | `new_items` |
| 12.7 | Property price alerts | `price_change` |
| 12.9 | Saved searches | `new_items` (template) |
| 14.3 | News alerts | `new_items` |
| 15.3 | Stock price alerts | `price_change` |
| 15.4 | Financial trend | `threshold_cross` |
| 16.3 | Company alerts | `threshold_cross` |
| 17.3 | Price drop alerts | `price_change` |
| 17.4 | Competitor tracking | `new_items` |

### Timeline Dependencies (Action: Add AD-27 References)

| Story | Dependency | Status |
|-------|-----------|--------|
| 12.8 | Epic 13 canonical storage | blocked |
| 16.4 | Epic 13 canonical storage | blocked |
