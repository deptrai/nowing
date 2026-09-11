---
title: 'Resolve core backend gaps: presentation pagination and workspace retention serialization'
type: 'bugfix'
created: '2026-09-11'
status: 'done'
baseline_commit: '51de5dcada7ae3f20dea07cd86749b9d78ae14c1'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Two concrete deferred review findings remain open in the core backend:
1. `GET /api/v1/presentations` returns all rows without `limit` and `offset` pagination bounds (Story 27.2a chunk B).
2. `GET /workspaces` and `GET /admin/users/workspaces` return default retention values in `WorkspaceWithStats` instead of reading the persisted `document_retention_*` and `memory_retention_*` columns from the `Workspace` entity (Story 3.7).

**Approach:**
1. Add `limit: int = Query(50, ge=1, le=100)` and `offset: int = Query(0, ge=0)` to `list_presentations` in `app/routes/presentation_routes.py`.
2. Populate `document_retention_days`, `auto_archive_enabled`, `document_retention_action`, `memory_retention_days`, `memory_auto_archive_enabled`, `memory_retention_action`, and `memory_auto_extract_enabled` when instantiating `WorkspaceWithStats` in `app/routes/workspaces_routes.py` and `app/routes/admin_users_routes.py`.
3. Add/update tests verifying presentation pagination and workspace retention serialization.
4. Mark the two findings as `Resolved` in `deferred-work.md`.

## Boundaries & Constraints

**Always:**
- Keep `WorkspaceWithStats` compatible with all existing consumers.
- Pagination in `list_presentations` must default to `limit=50, offset=0` and remain backward-compatible for clients not passing parameters.
- All existing tests in `test_presentation_routes_atdd.py` and workspace routes must remain green.

**Never:**
- Do not remove or rename existing fields in `WorkspaceWithStats`.
- Do not introduce breaking schema changes to REST response contracts.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| List presentations with limit/offset | `workspace_id=1, limit=10, offset=20` | Returns at most 10 items starting at offset 20 | 422 if limit < 1 or > 100 or offset < 0 |
| List workspaces with retention set | Workspace has `document_retention_days=30` | `WorkspaceWithStats.document_retention_days == 30` | Falls back to model attribute |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/routes/presentation_routes.py` -- `list_presentations` route definition and query params.
- `nowing_backend/app/routes/workspaces_routes.py` -- `read_workspaces` route constructing `WorkspaceWithStats`.
- `nowing_backend/app/routes/admin_users_routes.py` -- admin workspaces list constructing `WorkspaceWithStats`.
- `nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py` -- integration tests for presentation endpoints.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- ledger of deferred review findings.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/routes/presentation_routes.py` -- add `limit` and `offset` pagination parameters to `list_presentations`.
- [x] `nowing_backend/app/routes/workspaces_routes.py` -- pass persisted retention fields into `WorkspaceWithStats`.
- [x] `nowing_backend/app/routes/admin_users_routes.py` -- pass persisted retention fields into `WorkspaceWithStats`.
- [x] `nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py` -- add test verifying `limit` and `offset` pagination.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- mark both findings as Resolved.

**Acceptance Criteria:**
- Given `GET /api/v1/presentations`, when `limit` and `offset` query parameters are supplied, then the SQL query applies `.limit(limit).offset(offset)`.
- Given `GET /workspaces`, when a workspace has custom retention days, then `WorkspaceWithStats` returns the persisted values instead of default.
- Both findings in `deferred-work.md` are marked `Resolved`.

## Verification

**Commands:**
- `uv run pytest tests/integration/routes/test_presentation_routes_atdd.py -q` -- expected: all pass
- `uv run pytest tests/ -k "workspaces and stats" -q` -- expected: all pass


## Suggested Review Order

**Presentation Pagination**

- Add Query pagination parameters with default 50 and bounds to list_presentations
  [`presentation_routes.py:172`](../../nowing_backend/app/routes/presentation_routes.py#L172)

**Workspace Retention Serialization**

- Forward persisted retention fields to WorkspaceWithStats in user workspace listing
  [`workspaces_routes.py:240`](../../nowing_backend/app/routes/workspaces_routes.py#L240)

- Forward persisted retention fields to WorkspaceWithStats in admin workspace listing
  [`admin_users_routes.py:170`](../../nowing_backend/app/routes/admin_users_routes.py#L170)

**Tests & Deferred Ledger**

- Verify pagination bounds and disjoint pages in integration test
  [`test_presentation_routes_atdd.py:255`](../../nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py#L255)

- Verify persisted retention fields returned in GET /workspaces
  [`test_workspaces.py:80`](../../nowing_backend/tests/integration/routes/test_workspaces.py#L80)

- Update status to Resolved in ledger
  [`deferred-work.md:110`](../../_bmad-output/implementation-artifacts/deferred-work.md#L110)
