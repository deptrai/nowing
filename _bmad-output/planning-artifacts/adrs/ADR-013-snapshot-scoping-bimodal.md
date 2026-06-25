# ADR-013: Crypto Data Snapshots — Scoping Strategy

**Status:** Accepted (Answer A — bi-modal intentional)
**Date:** 2026-05-02 (proposed) → 2026-05-02 (accepted, Story 11.7 T4)
**Deciders:** Winston (Architect, recommending) — pending PM ratification
**Triggers:** Story 11-3 round-2 review; resolved by Story 11-7 T4

## Context

`crypto_data_snapshots` table has a nullable `search_space_id` foreign key to `searchspaces` (`ondelete=CASCADE`). Two code paths interact with this column with **inconsistent assumptions**:

### Write path: Refresh task

`nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py:_prefetch_category` (lines 88-174) writes new snapshots without passing `search_space_id`. Result: refreshed rows have `search_space_id = NULL`.

The refresh task's intent: pre-warm popular tokens that *some* user will likely query, regardless of which workspace.

### Cleanup path: Orphan purge

`crypto_refresh_tasks.py:_async_cleanup_orphaned` (lines 248-289) deletes rows where:

```sql
WHERE search_space_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM searchspaces WHERE id = crypto_data_snapshots.search_space_id)
```

The cleanup task's intent: remove snapshots whose owning workspace was deleted.

### Conflict

Refresh writes `search_space_id = NULL` rows. Cleanup never touches `NULL` rows. So the orphan purge **only** runs on a sub-population of snapshots — the ones that some other code path tagged with a `search_space_id`.

**Question:** Is this intentional bi-modal storage, or a bug?

There are **two coherent answers**, both viable:

### Answer A — Bi-modal is intentional

Snapshots come in two flavors:
- **Global cache rows** (`search_space_id = NULL`): pre-warmed by refresh task; reused across all workspaces; never expire by ownership (only by TTL); cleanup purges by `expires_at`, not by orphan check.
- **Per-workspace rows** (`search_space_id = <id>`): written by user-triggered tool calls (e.g., `get_token_data` invoked inside a chat with a specific search-space); workspace-scoped for billing/quota; cleanup purges when workspace deleted.

This matches what the cleanup task already does. Refresh task is correct (writes globals). Cleanup task is correct (purges per-workspace orphans only). **No code change needed**, only documentation.

### Answer B — Per-workspace is canonical, refresh is buggy

All snapshots should be workspace-scoped. The refresh task should:
- Discover which workspaces actively used a given token in the last N days.
- Refresh on behalf of those workspaces (write rows with their `search_space_id`).
- Skip refresh if no workspace has used a token recently (no consumer = no value).

This requires adding a query stage to `_prefetch_category` (read `search_space_id` distribution from existing rows, write back per workspace). More complex but eliminates the bi-modal column semantics.

## Decision

**Accepted: Answer A — Bi-modal storage is intentional. Document it explicitly.**

Story 11.7 T4 resolves the scoping question with the architect's recommendation
above. Documentation updates land alongside this ADR finalisation; PM ratification
is invited but not blocking — a different decision later would be a downstream
ADR-014.

### Decision rationale (Winston)

**Answer A — Bi-modal is intentional, but document it explicitly.**

Rationale:
- Lower implementation cost (zero code change for refresh path).
- Refresh task's value prop (pre-warm popular tokens) is naturally a "global cache" concern, not workspace-specific.
- Per-workspace rows already exist for fresh user-triggered queries; cleanup purges those correctly.
- Forcing refresh to be per-workspace would either (a) refresh redundantly across workspaces (storage bloat) or (b) require complex cross-workspace deduplication logic.

**Implementation (Story 11.7 T4):**
1. ✅ Update `nowing_backend/app/db.py` model docstring for `CryptoDataSnapshot` to document bi-modal semantics — landed in Story 11.7.
2. ✅ Add a comment in `_prefetch_category` (refresh task) confirming "global cache row" intent — landed in Story 11.7.
3. ✅ Story 11.3 spec already correctly scopes cleanup to per-workspace orphans (`search_space_id IS NOT NULL` filter). No further edit needed.
4. ✅ No production code change required — both write paths and the cleanup path were already correct under this interpretation.

If Answer B is chosen:
1. Refactor `_prefetch_category` to enumerate active workspaces per token and write per-workspace.
2. Migration: backfill existing global rows (`NULL` rows) into per-workspace rows or delete them.
3. New AC: cleanup task can use simpler query (no `IS NOT NULL` guard needed).
4. Effort: ~3-4 BE-days.

### Open questions for PM

1. **Billing implications** — Does any pricing tier limit "snapshot rows per workspace"? If yes, bi-modal makes accounting harder (which rows count?).
2. **Quota enforcement** — Story 11-5 enforces Pro entitlements at query time; does it matter whose snapshot is read? If quota is per-call (not per-row), bi-modal is fine.
3. **Workspace deletion expectations** — When a workspace deletes, should "their" snapshots disappear? If users expect total purge, Answer B is cleaner; if only their tagged rows, Answer A is fine.

## Consequences

### Answer A (recommended)
- **Positive:** Zero code change; pre-existing behavior documented.
- **Negative:** Mental model has 2 row types; future devs must understand the distinction.
- **Neutral:** Cleanup task narrowly scoped; matches current intent.

### Answer B
- **Positive:** Single, unified row semantics; cleanup is simpler.
- **Negative:** Refresh task complexity; backfill migration; potential storage bloat if cross-workspace dedup not implemented.

## Alternatives considered

3. **Drop `search_space_id` column entirely** — All snapshots are global. Rejected: Story 11-5's quota enforcement and workspace billing depend on tagging.
4. **Add a `scope` enum column** (`global` / `workspace`) instead of nullable FK — Cleaner but requires DB migration. Defer unless Answer B requires it.

## Owner

Story 11.7 T4 — **completed 2026-05-02**. Architect recommendation accepted on
process pending PM ratification (which would only be needed to override). Model
docstring + refresh-path comment updates landed in the same Story 11.7 commit.

If PM later requests Answer B (per-workspace canonical), open ADR-014 with
migration plan + storage impact estimate.
