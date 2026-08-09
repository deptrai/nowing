---
title: Story 12.9 — Saved Searches
epic: 12
story: 9
status: ready-for-dev
priority: P0
---

# Story 12.9 — Saved Searches

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot
**As a:** researcher
**I want:** to save complex search queries and auto-run them on schedule
**So that:** I always have fresh results without manual work.

---

## Acceptance Criteria

1. **Given** a search query with filters, **When** saved, **Then** it persists with `schedule: 'daily' | 'weekly' | 'none'`, `timezone`, and `enabled` flag; it appears in my saved searches list.
2. **Given** a saved search with `schedule='daily'`, **When** the automation scheduler triggers at the configured time (default 00:00 UTC), **Then** it runs as an Epic 6 automation via `RunService` and emits a run record.
3. **Given** run N and run N+1 complete, **When** delta is computed, **Then** `new_items = source_ids in run N+1 not present in run N` (by `sourceId`); `removed_items` and `changed_items` are also tagged.
4. **Given** `new_items > 0`, **When** the run completes, **Then** a notification is delivered via the configured channel (in-app, email, Telegram) with a link to the saved search and a summary count.
5. **Given** the saved search run fails or returns `degraded=true`, **When** it completes, **Then** the notification states the failure/degraded state and `degradation_reasons`, and the next scheduled run still fires unless `enabled=false`.

---

## Non-AC Technical Notes

- Saved searches must be implemented as an `AlertRule` template on the Generic Alert Engine (AD-33). Reuse Epic 6 Automation infrastructure (`RunService`, scheduler, notification dispatch).
- The `sourceId` used for delta comparison must be stable across runs (e.g., `jobId`/`canonical source id` for job listings).
- UI: saved search CRUD lives in the research dashboard; a `SavedSearchesManager` can reuse automation-list patterns.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/pilot-plan-c-memo-2026-08-05.md" />
