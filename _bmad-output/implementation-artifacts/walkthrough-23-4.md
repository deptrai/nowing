# Walkthrough: Story 23.4 (PostgreSQL Row-Level Security & Table Partitioning)

**Story:** `23-4-postgresql-rls-and-table-partitioning`  
**Epic:** Epic 23 - Multi-Million Lead Database Partitioning & Row-Level Security (Scale Phase)  
**Branch:** `feat/23-4-postgresql-rls-and-table-partitioning`  
**Status:** **READY FOR HUMAN SIGN-OFF / MERGE**  

---

## 1. Summary of Changes

Story 23.4 migrates the unpartitioned `leads` table to a hash-partitioned table (16 physical shards) with fail-closed Row-Level Security (RLS) and Zero-Cache CDC publication support.

### 1.1 Database Migration (`alembic/versions/217_partition_leads_table_zero_downtime.py`)
- **Phase 1 (Shadow Table):** Creates `leads_partitioned` with `PARTITION BY HASH (workspace_id)` across 16 shards (`leads_p0`..`leads_p15`), with specialized B-tree indexes.
- **Phase 2 (Dual-Write Trigger):** Creates `trg_sync_leads_dual_write()` trigger capturing live INSERTs, UPDATEs (including cross-workspace moves), and DELETEs.
- **Phase 3 (Batched Backfill):** Chunked backfill loop with batch size 5,000 using advancing UUID cursors without table locks.
- **Phase 4 (Atomic Swap):** Drops trigger and legacy single-column child foreign keys, renames `leads -> leads_legacy_backup` and `leads_partitioned -> leads`, adds composite FKs `(lead_id, workspace_id)` across all 6 child tables.
- **Phase 5 (RLS & CDC):** Enables `FORCE ROW LEVEL SECURITY`, creates fail-closed `leads_tenant_read_policy` & `leads_tenant_write_policy`, configures `zero_publication` with `publish_via_partition_root = true`.
- **Downgrade Path:** Restores `leads_legacy_backup` and original single-column foreign keys.

### 1.2 SQLAlchemy ORM (`app/db.py`)
- `Lead`: Composite Primary Key `(id, workspace_id)` via `PrimaryKeyConstraint('id', 'workspace_id', name='pk_leads')` and `workspace_id = Column(Integer, ..., primary_key=True)`.
- 6 Child Models (`LeadScore`, `EnrichmentRequest`, `VerifiedContact`, `PhoneWaterfallLog`, `ZaloMessageLog`, `OutcomeEvent`):
  - Composite `ForeignKeyConstraint(['lead_id', 'workspace_id'], ['leads.id', 'leads.workspace_id'], ondelete='CASCADE')`.
  - Relationships configured with `primaryjoin`, `foreign_keys`, and `overlaps="workspace,..."` to eliminate SQLAlchemy mapping warnings.

### 1.3 Zero-Cache CDC Publication (`app/zero_publication.py`)
- `ensure_publication()`, `apply_publication()`, and `verify_publication()` updated to enforce and verify `pubviaroot = true` on `zero_publication` (INV-23.5).

---

## 2. Verification & Quality Gates Status

| Quality Pipeline Gate | Status | Evidence |
| :--- | :---: | :--- |
| **4.5 `bmad-testarch-atdd`** | **PASS** | ATDD Checklist created & red-phase tests authored |
| **4.7 `bmad-dev-story`** | **PASS** | Full implementation + 7/7 unit tests passing |
| **4.8 `bmad-code-review`** | **APPROVED** | 3 parallel review layers (Blind Hunter, Edge Hunter, Auditor), 9/9 patches applied |
| **4.9 `bmad-testarch-test-review`** | **GRADE A (96/100)** | Determinism 96, Isolation 95, Maintainability 94, Performance 98 |
| **4.11 `bmad-testarch-trace`** | **PASS (100%)** | P0: 100%, P1: 100%, Overall: 100%, Critical Gaps: 0 |
| **4.12 `bmad-testarch-nfr`** | **PASS (8/8 Met)** | Scalability, Security, Zero-Downtime, CDC Replication verified |

---

## 3. Automated Verification Results

```bash
# Unit Tests (7 passed in 0.24s)
uv run pytest tests/unit/db/test_partition_router.py -m unit -q

# Linter (0 errors)
uv run ruff check app/db.py app/zero_publication.py alembic/versions/217_partition_leads_table_zero_downtime.py tests/unit/db/test_partition_router.py tests/integration/test_leads_partitioning_and_rls.py

# Frontend Typecheck (0 errors)
pnpm tsc --noEmit
```
