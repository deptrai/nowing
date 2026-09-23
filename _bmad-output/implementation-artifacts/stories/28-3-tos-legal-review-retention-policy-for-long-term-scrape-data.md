---
story_key: 28-3-tos-legal-review-retention-policy-for-long-term-scrape-data
status: done
epic: 28
---

# Story 28.3: ToS / Legal Review & Retention Policy for Long-Term Scrape Data

**Status:** `done`  
**Epic:** Epic 28 — Self-Host Trust, Data Portability & Legal Readiness

## Story

As a data protection officer / cloud user,  
I want Nowing to have a documented ToS/legal review and a retention / right-to-delete policy for data kept in long-term memory,  
so that the cloud GA is legally safe and users can remove infringing or outdated content.

## Acceptance Criteria

- **Given** a list of scrape sources used by Nowing, **When** legal review is performed, **Then** a `tos-review-2026-08-21.md` document records: permitted long-term storage, attribution requirements, reproduction prohibitions, recommended retention windows, and source risk tier.
- **Given** a high-risk source (e.g. TikTok with restrictive ToS), **When** a cloud workspace owner browses settings, **Then** that source is disabled by default with an explicit legal warning and does not appear in auto-extract unless owner opts in.
- **Given** the ToS review is approved, **When** an admin initiates a bulk deletion by `source_type` + `source_id`, **Then** the system runs a dry-run that lists affected `Memory` rows and total bytes, and only purges after explicit confirmation, with all actions logged to `audit_events`.
- **Given** a workspace owner requests right-to-delete for a specific memory, **When** the erasure is confirmed, **Then** the memory, its versions, its relations, and its embedding are purged within the SLA, and an audit log entry is written to `audit_events`.

## Dev Notes

- Legal review: `_bmad-output/planning-artifacts/legal/tos-review-2026-08-21.md` (approved 2026-08-21)
- Bulk deletion: `app/services/governance_service.py` / `bulk_ops_service.py`
- Right-to-delete: `app/tasks/celery_tasks/memory_retention_task.py`
- FR-97 · AR-13 · RS-11 · INV-28.2 · AD-28.3

## Verification

- Legal artifact: `_bmad-output/planning-artifacts/legal/tos-review-2026-08-21.md`
- Tests: dry-run bulk deletion, right-to-delete audit logging
