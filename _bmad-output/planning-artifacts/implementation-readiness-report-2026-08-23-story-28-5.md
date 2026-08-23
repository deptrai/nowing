---
stepsCompleted:
  - document-discovery
  - prd-analysis
  - architecture-analysis
  - ux-analysis
  - epics-stories-analysis
  - report-generation
includedFiles:
  prd:
    - _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md
    - _bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-PRFAQ-2026-08-21.md
  architecture:
    - _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md
    - _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md
  epics:
    - _bmad-output/planning-artifacts/epics.md
    - _bmad-output/implementation-artifacts/stories/28-5-workspace-memory-storage-cap-and-retention.md
    - _bmad-output/implementation-artifacts/stories/8-14-usage-credit-dashboard-v2.md
    - _bmad-output/implementation-artifacts/sprint-status.yaml
  ux:
    - _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md
    - _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md
    - nowing_web/components/settings/data-retention-manager.tsx
  code:
    - nowing_backend/app/db.py
    - nowing_backend/app/services/workspace_limits.py
    - nowing_backend/app/services/memory/repository.py
    - nowing_backend/app/services/memory/search.py
    - nowing_backend/app/tasks/celery_tasks/document_retention_task.py
date: '2026-08-23'
project: Nowing
story: 28.5
verdict: READY
---

# Implementation Readiness Assessment — Story 28.5: Workspace Memory Storage Cap & Retention Lifecycle

**Date:** 2026-08-23
**Project:** Nowing
**Scope:** Story 28.5 (Epic 28)
**Assessor role:** PM / Requirements traceability
**Verdict:** ✅ **READY for Phase 4 implementation** (blockers resolved 2026-08-23)

> **Update 2026-08-23:** The architecture conflict between Story 28.5 and `AD-28.3` was resolved by:
> - Updating `AD-28.3` to align with the existing document-retention pattern (`Memory.archived_at`, `Workspace.memory_retention_*` fields).
> - Adding cap as a guardrail bound to `AD-DEFER-4` / `AD-18` / `NFR-1b/1c/1d`.
> - Deferring `memory_source_legal_tiers` and high-risk disable-by-default to Story 28.3.
> - Updating Story 28.5, `epics.md`, and `ARCHITECTURE-SPINE.md` accordingly.
> See `## Resolution Log` at the end of this report for the final state of each finding.

---

## 1. Document Discovery

Documents used for this focused assessment:

- **PRD:** `prds/prd-Nowing-2026-07-22/prd.md` (canonical PRD, OQ-3)
- **PRFAQ amendment:** `prds/prd-Nowing-2026-07-22/AMENDMENT-PRFAQ-2026-08-21.md` (FR-97)
- **Architecture spine (older):** `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (`AD-DEFER-4`)
- **Architecture AD-28.3:** `architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md`
- **Epics & Stories:** `epics.md`, `stories/28-5-workspace-memory-storage-cap-and-retention.md`, `sprint-status.yaml`
- **UX current:** `ux-designs/ux-Nowing-2026-08-15/DESIGN.md`, `EXPERIENCE.md`
- **Existing UI:** `nowing_web/components/settings/data-retention-manager.tsx`
- **Existing code:** `app/db.py`, `app/services/workspace_limits.py`, `app/services/memory/repository.py`, `app/services/memory/search.py`, `app/tasks/celery_tasks/document_retention_task.py`

Duplicates/conflicts noted:
- `ARCHITECTURE-SPINE.md` (2026-07-22) lists `AD-DEFER-4` as `PARTIAL` but does **not** include the newer `AD-28.3` file.
- `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` does not cover memory retention at all.
- `AD-28-3-retention-right-to-delete.md` is an **ADOPTED** standalone AD that is not merged into any spine.

---

## 2. PRD Analysis

### OQ-3: Retention, right-to-delete & legal exposure

PRD §8.3 / OQ-3 clearly states: <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" lines="1484-1489" />

- **Document retention** is `[DONE]`.
- **Memory / scraped-data retention** is `[GAP]`: needs retention + right-to-delete for `Memory`, self-host vs cloud split, and ToS/PII review before cloud GA.

### PRFAQ FR-97

`AMENDMENT-PRFAQ-2026-08-21.md` maps FR-97 to Epic 28.3 and states: <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-PRFAQ-2026-08-21.md" lines="50-56" />

### Gap: workspace memory cap has **no PRD traceability**

The proposed Story 28.5 includes two distinct concerns:
1. **Memory retention / right-to-delete** — directly derived from PRD OQ-3 / FR-97 / AR-13 / RS-11.
2. **Memory storage cap** (`max_memory_count`, `max_memory_bytes`) — **not explicitly required** in PRD, PRFAQ, or existing ADs.

The cap is a storage-risk mitigation, but it is not bound to any FR, NFR, or AD in the source documents. If it is to remain in Story 28.5, it needs a new requirement (e.g., PRFAQ `FR-100` / `NFR-1e`) and a ratified AD. Otherwise it should be split out or removed.

---

## 3. Architecture Analysis

### AD-28.3 is ADOPTED and has a different schema model

`AD-28-3-retention-right-to-delete.md` (2026-08-21, ADOPTED) states: <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md" />

Key decisions that **conflict with Story 28.5**:

| Area | AD-28.3 (ADOPTED) | Story 28.5 (ready-for-dev) | Conflict |
|---|---|---|---|
| Workspace retention field | `Workspace.retention_days` (default 365 cloud, 0 self-host) | `Workspace.memory_retention_days` + `memory_auto_archive_enabled` + `memory_retention_action` | Same concern, different schema shape. Also existing `Workspace.document_retention_days` is already in production. |
| Soft-delete marker | `Memory.status = 'archived'` | `Memory.archived_at` timestamp | Different column strategy. `Document` already uses `archived_at`. |
| Grace period | `grace_period_days = 30` before purge | Not specified; `memory_retention_action` immediately `archive` or `delete` | Missing two-stage lifecycle. |
| Source risk | New `memory_source_legal_tiers` table with `legal_risk_tier` per `source_type` | Not in scope | High-risk source disable by default cannot be enforced without this table. |
| Bulk delete | Chunked 1,000 rows, `DELETE ... WHERE id IN (...)` | Chunked >100,000 memories | Consistent in spirit, but batch size differs. |
| Right-to-delete endpoint | `DELETE /workspaces/{id}/memories/{memory_id}` soft-delete + audit | Not in T7 (only retention task) | Missing route/audit AC. |

### AD-28.3 is not integrated into `ARCHITECTURE-SPINE.md`

`architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` only mentions `AD-DEFER-4` as `PARTIAL` (doc retention done, memory retention open). It does **not** reference `AD-28-3`. The unified spine does not either. This is architecture-doc drift.

### Existing code pattern (document retention)

`document_retention_task.py` uses `Document.archived_at`, `Workspace.document_retention_days`, `Workspace.document_retention_action`. Story 28.5 proposes to **mirror this pattern for memory** (`archived_at` + `memory_retention_days` + `memory_retention_action`). This is consistent with the existing codebase but **inconsistent with AD-28.3**, which uses `status='archived'` and `Workspace.retention_days`.

### Recommendation on architecture

Before implementation, one of the following must be chosen and ratified:

**Option A (recommended):** Update `AD-28.3` to align with the existing document-retention pattern:
- `Memory.archived_at` (same as `Document.archived_at`)
- `Workspace.memory_retention_days`, `Workspace.memory_auto_archive_enabled`, `Workspace.memory_retention_action` (mirrors document fields)
- Reconsider `memory_source_legal_tiers`: either add to Story 28.5 or defer to Story 28.3.

**Option B:** Update Story 28.5 to follow `AD-28.3` literally:
- Add `Workspace.retention_days` and `Workspace.grace_period_days`.
- Add `Memory.status` enum.
- Add `memory_source_legal_tiers` table.
- This creates a second, parallel retention model different from `Document`.

Neither option is implemented in the current story file.

---

## 4. UX Analysis

### Current UI: document-only

`data-retention-manager.tsx` currently manages:
- `workspace.auto_archive_enabled`
- `workspace.document_retention_days`
- `workspace.document_retention_action`

It has **no section for memory retention**. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_web/components/settings/data-retention-manager.tsx" lines="54-68" />

### UX design artifacts

`ux-designs/ux-Nowing-2026-08-15/` contains `DESIGN.md`, `EXPERIENCE.md`, and `ux-contract-readiness-gaps.md`. None of them define a UX contract for memory retention or workspace memory cap. The readiness-gap contract only covers auto-extract budget / cost per turn. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-readiness-gaps.md" lines="130-139" />

### UX gap

Story 28.5 T7 says "Add a 'Memory retention' section to `data-retention-manager.tsx`" but there is:
- No UX contract/mockup for that section.
- No i18n requirement (must mirror `messages/en.json` pattern).

This is a **moderate gap** — the UI can be inferred from the document-retention pattern, but it should be explicitly in the UX artifact or story.

---

## 5. Epics & Stories Analysis

### Story 28.3 vs Story 28.5 boundary

- **28.3** (ToS / Legal Review & Retention Policy) is responsible for: source risk tier, ToS review, legal warning, bulk deletion dry-run, right-to-delete for specific memory.
- **28.5** (Workspace Memory Storage Cap & Retention Lifecycle) is responsible for: cap, retention settings, daily task, archived exclusion.

**Overlap risk:** Both touch right-to-delete and bulk deletion. Story 28.5 AC-8 and AC-9 duplicate 28.3 AC. This should be clarified: 28.3 owns the **policy/UX**, 28.5 owns the **schema/lifecycle enforcement**. AC-8 and AC-9 in 28.5 should be reduced to "provide the schema and hook that 28.3 uses" or be moved to 28.3.

### Missing story decomposition

Story 28.5 is doing too much for one story:
1. Schema migration (`Memory.archived_at`, workspace retention fields, `WorkspaceLimit` memory cap fields).
2. Limit enforcement in `MemoryRepository.create_memory`.
3. Retention Celery task.
4. Search/list filter changes.
5. Route/schema updates.
6. Frontend UI for both cap and retention.

This is larger than a single story and larger than 8.14 (which was already multi-day). Consider splitting:
- **28.5a** — Memory count cap (small, immediate value).
- **28.5b** — Memory retention schema + lifecycle (depends on architecture decision above).

### Cap has no Epic 28 source

The cap (`max_memory_count`, `max_memory_bytes`) is not derived from any Epic 28 requirement. It could live under **Epic 8** (Workspace Billing & Usage) because it extends `WorkspaceLimit`. Or it could be a **separate PRFAQ requirement** if justified by storage risk. Mixing it into Epic 28 weakens traceability.

---

## 6. Findings Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | **Architecture conflict:** Story 28.5 uses `archived_at`/`memory_retention_days`; AD-28.3 uses `status='archived'`/`Workspace.retention_days`/`grace_period_days` | **BLOCKER** | Unresolved |
| F2 | **Missing `memory_source_legal_tiers` table / source risk tier** from AD-28.3 | **BLOCKER** | Not in 28.3 or 28.5 scope |
| F3 | **Cap (`max_memory_count`/`max_memory_bytes`) has no PRD/PRFAQ/AD source** | **MAJOR** | Unresolved |
| F4 | **AD-28.3 not integrated into `ARCHITECTURE-SPINE.md`** (doc drift) | **MODERATE** | Need spine update |
| F5 | **Story 28.5 overlaps Story 28.3** on right-to-delete and bulk delete ACs | **MODERATE** | Need boundary clarification |
| F6 | **No UX contract/mockup for memory retention UI** | **MODERATE** | Can be inferred from document retention, but should be recorded |
| F7 | **Story 28.5 is too large for one dev cycle** (schema, service, route, task, UI, tests) | **MODERATE** | Recommend split into 28.5a/28.5b |

---

## 7. Required Actions Before Implementation

1. **Resolve architecture conflict (F1):**
   - Choose Option A (align AD-28.3 with existing `archived_at` + per-data-type retention fields) **or** Option B (update story to match AD-28.3 literally).
   - Update either `AD-28-3-retention-right-to-delete.md` or `stories/28-5-workspace-memory-storage-cap-and-retention.md` accordingly.
   - Merge the chosen AD into `ARCHITECTURE-SPINE.md` and the unified spine if applicable (F4).

2. **Reconcile source-risk tier (F2):**
   - Decide whether `memory_source_legal_tiers` table belongs to Story 28.3 or 28.5.
   - Add the table and high-risk source disable-by-default logic to the correct story.

3. **Add requirement source for memory cap (F3):**
   - Either add a new PRFAQ/PRD requirement (e.g., `FR-100` — Workspace memory storage cap) and ratify an AD, **or**
   - Move the cap out of Story 28.5 into a separate story under Epic 8 (`WorkspaceLimit` extension) or Epic 28 with a new FR.

4. **Clarify boundary with Story 28.3 (F5):**
   - Remove or rephrase AC-8 and AC-9 in Story 28.5 if 28.3 owns right-to-delete/bulk-delete UX.
   - Keep 28.5 focused on schema, enforcement, and lifecycle task.

5. **Add UX contract (F6):**
   - Add a `ux-contract-memory-retention.md` or a section in `ux-contract-readiness-gaps.md` defining the memory retention UI.

6. **Split story (F7, optional but recommended):**
   - **28.5a** — Memory count cap (fast win, low risk).
   - **28.5b** — Memory retention lifecycle (depends on F1–F3).

---

## 8. Verdict

**Story 28.5 is READY for Phase 4 implementation after the 2026-08-23 resolution pass.**

The two blockers have been resolved:
1. **Architecture/schema conflict** with AD-28.3 — resolved by aligning AD-28.3 with the existing document-retention pattern.
2. **Missing cap traceability** — resolved by binding the cap to `AD-DEFER-4` / `AD-18` / `NFR-1b/1c/1d`.

F4–F7 are still valid warnings but no longer block implementation.

---

## 9. Recommended Next Step

Route to `bmad-dev-story` (or `bmad-agent-dev`) to implement `stories/28-5-workspace-memory-storage-cap-and-retention.md`.

Before code review, the dev agent should:
- Double-check the migration number (current head is 229; next available is 230).
- Verify `data-retention-manager.tsx` already supports the document-retention pattern and mirror it for memory.
- Keep `memory_source_legal_tiers` out of scope; do not build it unless Story 28.3 has already merged it.

---

## 10. Resolution Log (2026-08-23)

| Finding | Decision | Updated artifact |
|---|---|---|
| F1 — `Memory` soft-delete `archived_at` vs `status='archived'` | Use `Memory.archived_at` (mirror `Document.archived_at`) because the existing document retention code, UI, and indexes already use this pattern. | `AD-28-3-retention-right-to-delete.md`, `stories/28-5-*.md`, `epics.md` |
| F1 — Workspace retention field universal vs memory-specific | Use per-data-type fields: `Workspace.memory_retention_days` / `memory_auto_archive_enabled` / `memory_retention_action`, mirroring `document_retention_*`. Avoids a second, parallel retention model. | `AD-28-3-retention-right-to-delete.md`, `stories/28-5-*.md` |
| F2 — Missing `memory_source_legal_tiers` | Defer to Story 28.3 (ToS/legal review). Story 28.5 uses workspace defaults and reads the table only if it exists. | `AD-28-3-retention-right-to-delete.md`, `stories/28-5-*.md` |
| F3 — Memory cap has no requirement source | Cap is a guardrail bound to `AD-DEFER-4` (data lifecycle), `AD-18` (memory injection bound), and `NFR-1b/1c/1d`. Not a separate user-facing FR. | `stories/28-5-*.md`, `epics.md`, `AD-28-3-retention-right-to-delete.md` |
| F4 — AD-28.3 not in `ARCHITECTURE-SPINE.md` | Updated `AD-DEFER-4` to `RESOLVED` and added a 2026-08-23 amendment note referencing `AD-28.3`. | `ARCHITECTURE-SPINE.md` |
| F5 — Overlap with Story 28.3 | Boundary clarified: 28.3 owns ToS review + source risk tier + user-facing confirm flow; 28.5 owns schema, enforcement, backend right-to-delete endpoint, and audit writes. | `stories/28-5-*.md`, `AD-28-3-retention-right-to-delete.md` |
| F6 — No UX contract for memory retention | Accepted as low risk because `data-retention-manager.tsx` already has the document retention pattern; the story instructs to mirror it. Optional: add a UX contract in a follow-up. | `stories/28-5-*.md` |
| F7 — Story too large | Keep as one story with phase A/B task structure; can split into `28.5a`/`28.5b` during sprint planning if capacity requires it. | `stories/28-5-*.md` |
