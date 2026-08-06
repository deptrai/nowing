# Story 13.2c: Merge History, Conflict Resolution & Revert

**Status:** done
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P0

## Story

As a user,
I want merge history, conflict resolution, and revert capability for canonical entities,
So that every merge decision is auditable and reversible.

## Acceptance Criteria

- **Dependency:** Stories 13.2a or 13.2b can supply the first persisted entity.
- **Given** a merge, manual resolution, split or revert occurs, **Then** `canonical_merge_history` records the entity version before/after, linked-source set before/after, operation, actor (`user_id` or `system`), conflicts, method and timestamp.
- **Given** two writers update the same entity, **Then** exactly one expected-version write succeeds; the loser reloads/retries or surfaces a conflict, and `test_canonical_concurrent_merge.py` proves no lost update.
- **Given** an admin reverts a historical operation, **Then** the revert is a new audited transition against an expected current version; it never overwrites changes committed after the selected history item.
- **Given** review queue updates must be real time, **Then** Zero publishes only the columns required to render queue/list state; full snapshots are fetched through workspace-authorized REST endpoints.

## Validation

- Integration tests: `test_canonical_merge_history.py`, `test_canonical_revert.py`, `test_canonical_concurrent_merge.py`.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, canonical, merge, history, revert, concurrency, Zero
