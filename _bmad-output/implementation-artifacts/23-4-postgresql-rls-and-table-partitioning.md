story_key: 23-4-postgresql-rls-and-table-partitioning
status: ready-for-dev
baseline_commit: a58f90266528e15693a279663ffb73a2a077f13b
epic: 23
story: 4
---

# Story 23.4: PostgreSQL Row-Level Security (RLS) & Table Partitioning for Multi-Million Lead Scale

Status: ready-for-dev

<!-- Note: Governed by FR-92, INV-23.4, INV-23.5, INV-23.6, and Architecture Spine: architecture-epic23-lead-infrastructure.md -->

## Story

As a platform engineer and database architect,
I want the core `leads` table partitioned across 16 hash shards and protected by PostgreSQL engine-level Row-Level Security (RLS), with composite foreign keys on all 6 dependent child tables and Zero-cache partition-root replication,
So that Nowing can store and query 5,000,000+ lead records with sub-10ms latency, zero cross-tenant data leakage, and zero downtime during migration.

---

## Acceptance Criteria

### AC-1 — 5-Phase Zero-Downtime Table Partitioning Migration
**Given** an active production PostgreSQL database with existing unpartitioned `leads` records,
**When** Alembic migration `217_partition_leads_table_zero_downtime.py` is executed,
**Then** the migration follows the 5-phase zero-downtime shadow table pattern:
1. **Phase 1 (Shadow Table Creation):** Creates `leads_partitioned` partitioned by `HASH (workspace_id)` with 16 hash shards (`leads_p0` .. `leads_p15`) and a fallback partition `leads_default`.
2. **Phase 2 (Dual-Writing Trigger):** Attaches trigger `sync_leads_to_partitioned_trg` on `leads` to mirror all live `INSERT`, `UPDATE`, and `DELETE` operations to `leads_partitioned`.
3. **Phase 3 (Online Batched Backfill):** Copies historical rows in chunks of 5,000 with `ON CONFLICT DO NOTHING` without table locking.
4. **Phase 4 (Atomic Swap):** Renames tables in an isolated transaction (< 50ms lock window): `leads` -> `leads_legacy_backup`, `leads_partitioned` -> `leads`, and drops the dual-write trigger.
5. **Phase 5 (RLS & Zero-Cache Reconnect):** Enables and forces Row-Level Security on `leads` using the standard Nowing tenant predicate and sets `publish_via_partition_root = true` on `zero_publication`.

### AC-2 — Composite Primary & Foreign Key Integrity across all 6 Dependent Tables
**Given** the partitioned `leads` table,
**When** inspected at the database schema level,
**Then** the Primary Key of `leads` is strictly defined as `PRIMARY KEY (id, workspace_id)`.
**And** the unique deduplication constraint is `UNIQUE (workspace_id, value_hmac)`.
**And** all 6 dependent child tables in `app/db.py` reference `leads` via composite foreign keys:
  1. `LeadScore`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE`
  2. `VerifiedContact`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE`
  3. `EnrichmentRequest`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE`
  4. `SignalEvent`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE`
  5. `OutboundMessage`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE SET NULL`
  6. `ZaloMessageLog`: `FOREIGN KEY (lead_id, workspace_id) REFERENCES leads (id, workspace_id) ON DELETE CASCADE`

### AC-3 — Fail-Closed PostgreSQL Engine Row-Level Security (RLS)
**Given** a database connection with tenant session variable `SET LOCAL app.workspace_id = '1'`,
**When** executing `SELECT * FROM leads` without any explicit `WHERE workspace_id = ...` clause,
**Then** PostgreSQL engine-level RLS strictly returns only rows where `workspace_id = 1` based on the predicate:
```sql
leads.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
```
**And** if `app.workspace_id` is empty or unset, the query returns 0 rows (Fail-Closed default).
**And** `ALTER TABLE leads FORCE ROW LEVEL SECURITY;` ensures that table owners and superusers cannot accidentally bypass tenant filtering in application queries.

### AC-4 — Partition Pruning Query Performance & Zero-Cache CDC Sync
**Given** a partitioned `leads` table populated with 50,000+ synthetic lead records across multiple workspaces,
**When** executing workspace-scoped queries (`SELECT * FROM leads WHERE workspace_id = :ws_id ORDER BY created_at DESC LIMIT 50`),
**Then** `EXPLAIN (ANALYZE, BUFFERS)` confirms partition pruning eliminates 15 out of 16 shards (`Partitions Removed: 15`), achieving p95 query latency < 15ms.
**And** Zero-cache logical replication (`zero_publication`) captures WAL mutations from the root table without schema parse errors or subscription disconnects.

---

## Tasks / Subtasks

- [ ] **Task 1: Alembic Migration `217_partition_leads_table_zero_downtime.py`**
  - [ ] Write Phase 1 DDL: `leads_partitioned` with `PARTITION BY HASH (workspace_id)`, 16 shards (`leads_p0`..`leads_p15`), and `leads_default`.
  - [ ] Write Phase 2 DDL: PL/pgSQL function `trg_sync_leads_dual_write()` and trigger `sync_leads_to_partitioned_trg`.
  - [ ] Write Phase 3 DML: Batched backfill loop with batch size 5,000.
  - [ ] Write Phase 4 DDL: Atomic table swap transaction with `ACCESS EXCLUSIVE` lock.
  - [ ] Write Phase 5 DDL: RLS read/write policies (`leads_tenant_read_policy`, `leads_tenant_write_policy`), `FORCE ROW LEVEL SECURITY`, and `ALTER PUBLICATION zero_publication SET (publish_via_partition_root = true);`.
  - [ ] Implement clean downgrade path (`downgrade()`) restoring unpartitioned structure from `leads_legacy_backup`.

- [ ] **Task 2: SQLAlchemy ORM Model & Relationship Updates (`nowing_backend/app/db.py`)**
  - [ ] Update `Lead` model: change `__table_args__` to include composite `PrimaryKeyConstraint('id', 'workspace_id')`.
  - [ ] Update all 6 child models with composite foreign key definitions:
    - [ ] `LeadScore` (line 4603): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`
    - [ ] `VerifiedContact` (line 4672): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`
    - [ ] `EnrichmentRequest` (line 4731): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`
    - [ ] `SignalEvent` (line 4799): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`
    - [ ] `OutboundMessage` (line 5262): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='SET NULL')`
    - [ ] `ZaloMessageLog` (line 5317): `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`
  - [ ] Update SQLAlchemy relationships (`lead`, `scores`, `contacts`, `logs`) with `foreign_keys` and `primaryjoin` specifications.

- [ ] **Task 3: Zero-Cache Publication & Session Middleware Sync**
  - [ ] Update `nowing_backend/app/zero_publication.py` to ensure `publish_via_partition_root = true` is enforced during database startup.
  - [ ] Verify database session manager sets `SET LOCAL app.workspace_id = :ws_id` on every transactional query and resets session state upon release.

- [ ] **Task 4: Automated Testing & Performance Benchmark Suite**
  - [ ] Unit tests in `tests/unit/db/test_partition_router.py`: hash modulo routing calculation.
  - [ ] Integration tests in `tests/integration/test_leads_partitioning_and_rls.py`:
    - RLS multi-tenant fail-closed boundary test (Workspace A cannot see Workspace B data).
    - `EXPLAIN ANALYZE` partition pruning test verifying single-shard scan.
    - Zero-cache publication sync verification test.
  - [ ] Run full regression suite: `uv run pytest tests/unit/ tests/integration/ -k "leads or dnc or partner" -q`.

---

## Dev Agent Guardrails & Architectural Invariants

- **INV-23.4 (Composite Partition Key):** Primary Key BẮT BUỘC là `(id, workspace_id)`. Mọi unique constraint phải chứa `workspace_id`.
- **INV-23.5 (Zero-Cache Partition CDC Replication):** Bắt buộc bật `ALTER PUBLICATION zero_publication SET (publish_via_partition_root = true);`.
- **INV-23.6 (Fail-Closed RLS Enforcement):** Bắt buộc `ALTER TABLE leads FORCE ROW LEVEL SECURITY;`. Mọi query phải set `app.workspace_id`.
- **Zero-Downtime Rule:** Tuyệt đối không dùng `ALTER TABLE leads PARTITION BY` trực tiếp; bắt buộc dùng shadow table + dual-write trigger.

---

## Verification Commands

```bash
# 1. Run Alembic Migration
cd nowing_backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run alembic upgrade head

# 2. Run Partitioning & RLS Integration Tests
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing uv run pytest tests/integration/test_leads_partitioning_and_rls.py -q

# 3. Verify Zero Publication configuration
uv run python -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5434/nowing')
with engine.connect() as conn:
    res = conn.execute(text(\"SELECT pubname, pubviaroot FROM pg_publication WHERE pubname = 'zero_publication'\")).fetchone()
    print('Publication status:', res)
    assert res[1] is True, 'publish_via_partition_root MUST be True'
"

# 4. Frontend Typecheck
cd ../nowing_web
pnpm tsc --noEmit
```
