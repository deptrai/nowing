# Story 13.1: Canonical Persistence, Tenancy & Convention

**Status:** done  
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing  
**Priority:** P0  
**Baseline commit:** `72806b18de0df53071d7f310c1c3f7706cb12f96`  
**Sprint status:** `epic-13: done`, `13-1: done`

> **Ghi chú tiếng Việt:** Story này là nền tảng persistence chung cho mọi domain aggregator. Nó đã hoàn thành; file này là bản tổng hợp lại để phục vụ kiểm tra chất lượng BMAD và tài liệu tham khảo sau này.

---

## Story

As a developer,  
I want a canonical persistence contract with database-enforced tenancy and explicit source lineage,  
so that every domain can persist and search merged entities safely without inventing a new matching engine.

---

## Acceptance Criteria

1. [x] **Migration.** `alembic/versions/193_add_canonical_entities.py` creates `canonical_entities`, `canonical_entity_sources`, `canonical_merge_history`, and `canonical_persist_outbox`, with Alembic-owned indexes and downgrade support for databases that have not accepted production writes.
2. [x] **Entity columns.** `canonical_entities` stores all required columns: `id` (UUID PK), `workspace_id` (Integer FK), `entity_type`, `canonical_title`, `canonical_data` (JSONB), `fingerprint`, `search_text` (Text), `source_count`, `confidence_score`, `conflict_flags` (JSONB), `version`, `first_seen_at`, `last_seen_at`, `embedding` (Vector), `embedding_model_name`, `embedding_content_hash`, and `embedding_status` (`pending`/`ready`/`failed`).
3. [x] **Fingerprint uniqueness.** Unique constraint and upsert target are exactly `(workspace_id, entity_type, fingerprint)` so two domains may use the same fingerprint text without colliding.
4. [x] **Source provenance.** `canonical_entity_sources` stores `workspace_id`, `canonical_entity_id`, `entity_type`, `source_name`, `source_record_id`, redacted source snapshot, source URL, source timestamps (`first_seen_at`, `last_seen_at`) and source fingerprint.
5. [x] **Source uniqueness.** Unique constraint on sources is exactly `(workspace_id, entity_type, source_name, source_record_id)`; `canonical_entity_id` is a FK index, not part of the uniqueness key. A source record may move to a new canonical entity on conflict.
6. [x] **Conflict flag shape.** Conflicts stored in `conflict_flags` mirror the BDS `ConflictFlag` shape (`type`, `reason`, optional `price_range`/`source_maps`) rather than free-form strings.
7. [x] **Version compare-and-swap.** Writes use `version` for optimistic concurrency: rows are locked with `with_for_update()`, expected-version checks raise `ConcurrentUpdateError`, and updates include a `version == expected` compare-and-swap guard so no later version is silently overwritten.
8. [x] **Per-transaction tenant context.** API requests and Celery tasks set `app.workspace_id` per transaction using `SELECT set_config('app.workspace_id', :wid, true)`; the workspace ID is explicit and never from process-global state.
9. [x] **RLS fail-closed.** All four tables use `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and policies based on `current_setting('app.workspace_id', true)`. The application role is non-owner and `NOBYPASSRLS`; missing or invalid workspace context returns zero rows.
10. [x] **Domain convention boundary (AD-27).** `app/services/bds_aggregator/dedupe.py` and `app/services/jobs_aggregator/dedupe.py` expose `fingerprint()`, `merge()`, and `search_text()`; these are re-exported from each package `__init__.py` without requiring three new files on day one.
11. [x] **Embedding backfill.** On create or `search_text` change, `embedding_status` becomes `pending`; an idempotent Celery task keyed by `(entity_id, version, embedding_model_name)` populates the embedding only if the version still matches.
12. [x] **Required indexes.** Migration creates: unique btree on `canonical_entities (workspace_id, entity_type, fingerprint)`; btree on `(workspace_id, entity_type, last_seen_at DESC)`; GIN `to_tsvector` on `search_text`; partial HNSW `vector_cosine_ops` on `embedding` with `WHERE embedding IS NOT NULL`; btree on `canonical_entity_sources (canonical_entity_id)` and the source uniqueness index; btree on `canonical_merge_history (canonical_entity_id, created_at)`; and btree on `canonical_persist_outbox (status, next_attempt_at)`.
13. [x] **Zero publication.** Minimal non-PII columns for `canonical_entities`, `canonical_entity_sources`, `canonical_merge_history`, and `canonical_persist_outbox` are added to `ZERO_PUBLICATION` in `app/zero_publication.py`; bulky snapshots remain REST-fetched.
14. [x] **BDS/Jobs execution context contract.** `vn_bds.aggregate` and `vn_jobs.aggregate` are documented to accept `workspace_id` explicitly before any canonical write path is enabled.

---

## Tasks / Subtasks

- [x] AC 1: Alembic migration 193 with raw DDL, indexes, RLS policies, and Zero publication reconcile.
- [x] AC 2-5, 7, 9, 12: SQLAlchemy models and constraints in `app/db.py`.
- [x] AC 8: Tenant context helper `app/canonical/tenant_context.py`.
- [x] AC 6, 7, 11: `app/canonical/services/canonical_persist_service.py` upsert, merge history, and outbox staging.
- [x] AC 11: Idempotent Celery backfill task `app/canonical/tasks/backfill_canonical_embedding.py`.
- [x] AC 10: Domain convention exports in BDS/Jobs `dedupe.py` and `__init__.py`.
- [x] AC 13: Zero publication columns in `app/zero_publication.py`.
- [x] AC 1, 8, 9: Integration tests for migration, RLS, version, source uniqueness, embedding backfill, and domain conventions.

---

## Dev Notes

### Architecture Compliance

- **AD-2 (Async SQLAlchemy + Alembic + PostgreSQL/pgvector):** All canonical I/O uses `AsyncSession`. Schema change is captured by migration `193`. Models live in `app/db.py` on the shared `DeclarativeBase`. Vector search uses `pgvector.sqlalchemy.Vector`. [Source: ARCHITECTURE-SPINE.md#AD-2]
- **AD-27 (Canonical Entity Convention):** Each domain aggregator exposes `fingerprint`, `merge`, `search_text`. BDS and Jobs already own `dedupe.py`/`normalize.py`; 13.1 exports these from package `__init__.py` and proves them in `tests/unit/canonical/test_canonical_conventions.py`. [Source: ARCHITECTURE-SPINE.md#AD-27]
- **AD-28 (Unified Engine Trigger):** Shared canonical storage (this story) ships **before** any `DomainPlugin` engine refactor. 13.1 only establishes tables and conventions; the plugin trigger is future work. [Source: ARCHITECTURE-SPINE.md#AD-28]
- **AD-24/AD-25 inheritance:** Jobs fingerprint follows `company + title + location + posted_at` (AD-24). PII redaction is not a 13.1 deliverable (13.2d); however, `source_snapshot` and `canonical_data` are JSONB so later redaction can mutate values without schema changes.

### Project Structure Notes

All new 13.1 files belong under `nowing_backend/app/canonical/` or extend existing shared files:

| File | Purpose |
|------|---------|
| `nowing_backend/alembic/versions/193_add_canonical_entities.py` | Migration, indexes, RLS, Zero publication reconcile |
| `nowing_backend/app/db.py` (lines 3714-3937) | SQLAlchemy models, enums, indexes |
| `nowing_backend/app/canonical/tenant_context.py` | `set_canonical_workspace_id`, `canonical_workspace_context` |
| `nowing_backend/app/canonical/services/canonical_persist_service.py` | Upsert, source move, merge history, outbox, version CAS |
| `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py` | Celery backfill + `_backfill_canonical_embedding` |
| `nowing_backend/app/canonical/__init__.py` | Package marker |
| `nowing_backend/app/canonical/services/__init__.py` | Service package marker |
| `nowing_backend/app/canonical/tasks/__init__.py` | Task package marker |
| `nowing_backend/app/services/bds_aggregator/__init__.py` | Re-exports `fingerprint`, `merge`, `search_text` |
| `nowing_backend/app/services/bds_aggregator/dedupe.py` | Adds `fingerprint`, `merge`, `search_text` |
| `nowing_backend/app/services/jobs_aggregator/__init__.py` | Re-exports `fingerprint`, `merge`, `search_text` |
| `nowing_backend/app/services/jobs_aggregator/dedupe.py` | Adds `fingerprint`, `merge`, `search_text` |
| `nowing_backend/app/celery_app.py` | Registers `app.canonical.tasks.backfill_canonical_embedding` in `include` |
| `nowing_backend/app/zero_publication.py` | Adds canonical tables/columns to `ZERO_PUBLICATION` |

### Testing Requirements

Run from `nowing_backend/`:

```bash
# Migration / RLS / persistence
pytest tests/integration/canonical/test_canonical_persistence.py -q
# Embedding backfill idempotency
pytest tests/integration/canonical/test_canonical_embedding.py -q
# Domain convention signatures
pytest tests/unit/canonical/test_canonical_conventions.py -q
# Lint affected modules
ruff check app/db.py app/canonical/ app/services/bds_aggregator/dedupe.py app/services/jobs_aggregator/dedupe.py
```

### Previous Story Intelligence

- **Memory-layer pattern (Epic 3, migrations 177-179):** Already established `pgvector` `Vector` column, HNSW+GIN indexing, and RLS-ready workspace columns. 13.1 mirrors that pattern for canonical entities. [Source: epics.md#Epic-3, `app/db.py`]
- **Zero publication pattern:** Migrations 155/156 and `app/zero_publication.py` already reconcile column lists to avoid `ALTER COLUMN` on published columns. 13.1 uses the same `apply_publication` mechanism. [Source: `app/zero_publication.py`]
- **Tenant context pattern:** Workspace-scoped reads/writes already use `SET LOCAL`/`set_config` in other modules; 13.1 centralizes it in `app/canonical/tenant_context.py` with an explicit session marker.

### Security / Performance / RLS

- **RLS policy:** `current_setting('app.workspace_id', true)` is cast to integer and compared to `workspace_id`. Force RLS means the table owner is also subject to the policy; NOBYPASSRLS prevents role escalation. [Source: migration 193]
- **Partial HNSW index:** `CREATE INDEX ix_canonical_entities_embedding ON canonical_entities USING hnsw (embedding public.vector_cosine_ops) WHERE embedding IS NOT NULL` prevents index bloat on pending/failed rows and matches SQLAlchemy `postgresql_where=text("embedding IS NOT NULL")`. [Source: migration 193, `app/db.py` lines 3757-3763]
- **Embedding status lifecycle:** `pending` (created/changed) → Celery backfill → `ready` (success) or `failed` (empty search_text or embed error). [Source: `app/canonical/tasks/backfill_canonical_embedding.py`]
- **Source uniqueness move:** When a source `(workspace_id, entity_type, source_name, source_record_id)` is upserted against a different `canonical_entity_id`, the row is moved and `source_count` of both old and new entities is recomputed. [Source: `app/canonical/services/canonical_persist_service.py` lines 185-247]
- **PII:** This story does **not** implement redaction. 13.2d adds `app/canonical/services/canonical_pii.py`; the current `canonical_persist_service.py` at baseline 72806b18d does not redact. Do not add PII redaction in 13.1.

### Library Versions

From `nowing_backend/pyproject.toml`:

- `alembic>=1.13.0`
- `pgvector>=0.3.6`
- `SQLAlchemy` 2.x async (per `ARCHITECTURE-SPINE.md#Stack`)
- `asyncpg>=0.30.0`

`pgvector.sqlalchemy.Vector` is used for the column; the Alembic migration uses raw `vector(DIM)` SQL to avoid `alembic check` not recognizing the type, a known pgvector/Alembic friction point.

### Git Intelligence

- **Baseline / completion commit:** `72806b18de0df53071d7f310c1c3f7706cb12f96` — `Story 13.1: Canonical persistence, tenancy, and convention`.
- **Files changed at baseline:** 20 files, +1944/-7.
  - New: `alembic/versions/193_add_canonical_entities.py`, `app/canonical/tenant_context.py`, `app/canonical/services/canonical_persist_service.py`, `app/canonical/tasks/backfill_canonical_embedding.py`, `app/canonical/__init__.py`, `app/canonical/services/__init__.py`, `app/canonical/tasks/__init__.py`, plus tests.
  - Modified: `app/db.py`, `app/celery_app.py`, `app/services/bds_aggregator/__init__.py`, `app/services/bds_aggregator/dedupe.py`, `app/services/jobs_aggregator/__init__.py`, `app/services/jobs_aggregator/dedupe.py`, `app/zero_publication.py`, `pyproject.toml`.
- **Related commits after 13.1 (for reference only, out of scope):**
  - `18a1596a0` — Story 13.2a BDS persistence and retry
  - `e1f7b4e88` — Story 13.2b Jobs persistence and retry
  - `9350feb4b` — Story 13.2c merge history, conflict resolution, revert
  - `7f1c2379b` — Story 13.2d PII-safe canonicalization
  - `7f964ca4a` — Story 13.2e dedup benchmark & release gate
  - `eda4fcd76` — Story 13.3 unified canonical + document search API

---

## Dev Agent Record

### Agent Model Used

Not recorded in baseline commit.

### Debug Log References

- Commit `72806b18d` message contains the implementation summary.
- Integration test suite: `nowing_backend/tests/integration/canonical/test_canonical_persistence.py`

### Completion Notes List

1. Migration 193 creates tables, indexes, RLS, and reconciles `zero_publication`.
2. SQLAlchemy models in `app/db.py` reuse the existing `TimestampMixin`, `Vector`, JSONB patterns.
3. `tenant_context.py` provides an explicit, fail-closed `set_canonical_workspace_id` helper.
4. `canonical_persist_service.py` implements upsert with version CAS, source move, merge history, and outbox.
5. `backfill_canonical_embedding.py` is registered in Celery and is idempotent by `(entity_id, version, embedding_model_name)`.
6. BDS and Jobs `dedupe.py` expose convention functions; `__init__.py` re-exports them.
7. All integration and unit tests passed before the baseline commit.

### File List

- `nowing_backend/alembic/versions/193_add_canonical_entities.py`
- `nowing_backend/alembic/versions/194_add_canonical_merge_history_source_ids.py` *(follow-up migration, not in 13.1 baseline)*
- `nowing_backend/app/db.py`
- `nowing_backend/app/canonical/__init__.py`
- `nowing_backend/app/canonical/tenant_context.py`
- `nowing_backend/app/canonical/services/__init__.py`
- `nowing_backend/app/canonical/services/canonical_persist_service.py`
- `nowing_backend/app/canonical/tasks/__init__.py`
- `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py`
- `nowing_backend/app/services/bds_aggregator/__init__.py`
- `nowing_backend/app/services/bds_aggregator/dedupe.py`
- `nowing_backend/app/services/jobs_aggregator/__init__.py`
- `nowing_backend/app/services/jobs_aggregator/dedupe.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_backend/tests/integration/canonical/test_canonical_persistence.py`
- `nowing_backend/tests/integration/canonical/test_canonical_embedding.py`
- `nowing_backend/tests/unit/canonical/test_canonical_conventions.py`

---

## Change Log

| Commit | Date | Summary |
|--------|------|---------|
| `72806b18de0df53071d7f310c1c3f7706cb12f96` | 2026-08-06 | Story 13.1: canonical persistence, tenancy, and convention. Created migration 193, SQLAlchemy models, RLS, tenant context, persist service, embedding backfill task, and BDS/Jobs convention exports. |

---

## References

- PRD / Epic: `_bmad-output/planning-artifacts/epics.md` (Epic 13, lines 1331-1449)
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` (AD-2, AD-27, AD-28)
- Implementation readiness: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-06.md`
- UX contract: `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-canonical-entity.md`
- Validation report: `_bmad-output/implementation-artifacts/validation-reports/13-1-validation-report.md`
