---
story_key: 30-8-epic-13-canonical-entity-cleanup
status: done
epic: 30
---

# Story 30.8: Epic 13 Canonical Entity Cleanup

**Status:** `done`  
**Epic:** Epic 30 — Technical Debt

## Story

As a platform operator,  
I want the deprecated `app/canonical/` entity subsystem removed,  
so that the codebase is not burdened by dead tables, routes, and models after entity storage migrated to `chainlens-research`.

## Acceptance Criteria

- **Given** `app/canonical/` exists, **When** the cleanup migration runs, **Then** it drops canonical tables, removes `canonical_entities_routes.py`, and deletes associated models and tests.
- **Given** zero live callers to `canonical_entities_routes.py`, **When** the cleanup is verified, **Then** no runtime references remain in `app/routes/`, `app/models/`, or `app/services/`.
- **Given** the migration `d33c362fa627` is applied, **When** `alembic upgrade head` completes, **Then** canonical tables are dropped and no data is lost from non-canonical tables.

## Dev Notes

- Migration: `d33c362fa627_drop_canonical_entities.py`
- Removed: `app/canonical/`, `app/routes/canonical_entities_routes.py`, canonical models, canonical tests
- Follows AD-SOC-3 / AD-DEFER-4 (entity storage offloaded to `chainlens-research`)

## Verification

- Migration: `d33c362fa627_drop_canonical_entities.py`
- Test: `grep -R canonical_entities_routes` returns no matches in `app/` and `tests/`
