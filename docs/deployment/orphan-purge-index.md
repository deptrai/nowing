# Orphan-Purge Partial Index

> **Story 11.7 T3** — query-plan optimisation for the weekly orphan-purge task.

## Background

`cleanup_orphaned_crypto_snapshots` (Story 11.3) runs weekly and deletes
`crypto_data_snapshots` rows whose `search_space_id` no longer points to a
live workspace, in batches of 1000. The query:

```sql
DELETE FROM crypto_data_snapshots
WHERE id IN (
    SELECT id FROM crypto_data_snapshots
    WHERE search_space_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM searchspaces
          WHERE searchspaces.id = crypto_data_snapshots.search_space_id
      )
    ORDER BY id ASC
    LIMIT 1000
)
```

## Why a new index

The pre-existing `ix_crypto_snapshots_cache_lookup` index leads with
`search_space_id`, so the `IS NOT NULL` filter benefits — but `id` is not in
the index, so `ORDER BY id ASC` falls back to a sort over all matching rows.
On a 10M-row table with millions of orphans this dominates batch latency.

## The fix

Migration `141_add_orphan_purge_partial_index` adds a **partial covering
index**:

```sql
CREATE INDEX CONCURRENTLY ix_crypto_snapshots_orphan_purge
ON crypto_data_snapshots (id ASC)
WHERE search_space_id IS NOT NULL;
```

Properties:
- **Partial**: only orphan-candidates indexed → smaller, faster.
- **Ordered by `id`**: matches the `ORDER BY id ASC` clause directly →
  index-only scan with LIMIT-1000 short-circuit.
- **CONCURRENTLY**: built without locking writers (cleanup task included).

## Acceptance / verification

Target: each batch (1000 deletes) completes in **< 60 s** on production
shape data.

`EXPLAIN ANALYZE` on staging-with-orphans should show:

```
Limit  (cost=...)
  ->  Nested Loop Anti Join
        ->  Index Scan using ix_crypto_snapshots_orphan_purge on crypto_data_snapshots
              Index Cond: ...
        ->  Index Only Scan using searchspaces_pkey on searchspaces
```

The key signals:
- **Index Scan** (NOT Seq Scan) on `crypto_data_snapshots`
- **Anti Join** (NOT Hash Join over the full table)
- The new `ix_crypto_snapshots_orphan_purge` named in the plan

## Operational notes

- The orphan-purge task already has a **per-session** `SET LOCAL
  statement_timeout = '60s'` (Story 11.3 round 2). If a batch exceeds 60 s,
  Postgres aborts and the task surfaces `status: failed` in its metric log.
- Migration 141 uses `CREATE INDEX CONCURRENTLY` so it does not block the
  weekly task. Apply outside of weekly Sunday window for safety.
- Rollback (`downgrade()`) is safe — the existing `ix_crypto_snapshots_cache_lookup`
  remains usable, just slower for orphan purge specifically.

## References

- Story 11.7 T3
- Migration: `nowing_backend/alembic/versions/141_add_orphan_purge_partial_index.py`
- Task: `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py:_async_cleanup_orphaned`
- Story 11.3 round 2 deferred item ([deferred-work.md](../../_bmad-output/implementation-artifacts/deferred-work.md) — `NOT EXISTS subquery có thể full-scan trên large table`)
