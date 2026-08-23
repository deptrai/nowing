---
date: 2026-08-24
type: sprint-change-proposal
trigger: bmad-correct-course
---

# Sprint Change Proposal — Split Story 14.2 into 14.2a + 14.2b

## 1. Issue Summary

**Story 14.2: News Entity Enrichment** was validated on 2026-08-24 and found to be a single story containing two distinct risk/dependency profiles:

- **Phase A (Nowing-only):** entity extraction, `Chunk` metadata enrichment, PII redaction, `rss_indexer` refactor, and safe `NowingIngestService` failure handling. This work has no external blocker and can be developed immediately.
- **Phase B (chainlens-gated):** `chainlens-research` indexing and entity search / chat agent wiring. This work is blocked because `chainlens-research` does not yet support `metadata.entities` or expose an entity search endpoint.

Keeping both phases in one story created a status conflict: `epics.md` and `sprint-status.yaml` already marked `14-2` as `backlog` due to the external blocker, while a single combined story file could not cleanly express that part of it was ready for dev.

## 2. Impact Analysis

### Epic Impact

- **Epic 14 — News Aggregation (Vietnam)** is still viable. No epic scope is removed; the work is split into two clearer deliverables.
- `14.2a` can proceed without waiting for `chainlens-research`, reducing idle time on the epic.
- `14.2b` remains correctly blocked and does not consume dev capacity until the external contract lands.

### Story Impact

| Old | New | Status | Notes |
|---|---|---|---|
| `14-2` News Entity Enrichment | `14-2a` News Entity Extraction | `ready-for-dev` | All Nowing-side code changes |
| | `14-2b` News Entity Search | `backlog` | Gated on `chainlens-research` entity search contract |

### Artifact Conflicts

- `epics.md`: `Story 14.2` replaced by `Story 14.2a` and `Story 14.2b` with updated ACs and validation.
- `sprint-status.yaml`: `14-2` replaced by `14-2a: ready-for-dev` and `14-2b: backlog`.
- Story files:
  - `stories/14-2-news-entity-enrichment.md` renamed → `stories/14-2a-news-entity-extraction.md` and rewritten.
  - `stories/14-2b-news-entity-search.md` created.

### Technical Impact

- No production code changed; only planning artifacts are reorganized.
- `14.2a` is ready for `bmad-nowing-test-first-atdd` → `bmad-dev-story`.
- `14.2b` should not be implemented until `chainlens-research` exposes entity search; only a stub test is created now.

## 3. Recommended Approach

**Option 1 — Direct Adjustment (selected):** Split the story into two independent stories within Epic 14.

**Rationale:**
- The external dependency affects only entity search, not the extraction/metadata work.
- Splitting unlocks `14.2a` for immediate development, preserving epic velocity.
- `14.2b` stays accurately blocked in `backlog`, avoiding misleading `ready-for-dev` status.
- No rollback is needed; the original 14.2 content is preserved in the split.

**Effort:** Low (documentation/backlog reorganization only).
**Risk:** Low. If the chainlens contract changes, only `14.2b` needs update.

## 4. Detailed Change Proposals

### Story split

```
Story: 14-2 News Entity Enrichment
Section: full story

OLD:
- Single story with Phase A + Phase B, status backlog

NEW:
- Story 14.2a News Entity Extraction (ready-for-dev)
  - entity extraction, metadata, PII redaction, rss_indexer refactor, safe ingest
- Story 14.2b News Entity Search (backlog, blocked-by-external)
  - chainlens entity search contract + agent wiring

Rationale: Phase B is blocked by chainlens-research; Phase A can ship now.
```

### `epics.md`

```
Epic 14, Story 14.2

OLD:
- Story 14.2: News Entity Enrichment (blocked-by-external)

NEW:
- Story 14.2a: News Entity Extraction (P1, ready-for-dev)
- Story 14.2b: News Entity Search (P1, backlog, blocked-by-external)

Rationale: clearer scope, independent scheduling.
```

### `sprint-status.yaml`

```
OLD:
  14-2: backlog # blocked-by-external

NEW:
  14-2a: ready-for-dev
  14-2b: backlog # blocked-by-external

Rationale: 14.2a can be picked up by dev; 14.2b stays blocked.
```

## 5. Implementation Handoff

- **Scope classification:** Minor (planning artifact reorganization only; no code changes).
- **Handoff recipient:** Developer agent for `14.2a` when it reaches `bmad-dev-story`.
- **Product Owner / Developer coordination:** Not required; backlog entries already updated.
- **Success criteria:**
  - `14.2a` status is `ready-for-dev` and `14.2b` is `backlog`.
  - `epics.md` lists both split stories with correct ACs.
  - No remaining `14-2` references in `sprint-status.yaml` or `stories/`.

## 6. Approval

**Approved by:** Product / dev decision on 2026-08-24.
**Executed by:** `bmad-correct-course` workflow.
