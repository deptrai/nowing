# Story 13.1: Canonical Persistence, Tenancy & Convention

**Status:** done
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P0

## Story

As a developer,
I want a canonical persistence contract with database-enforced tenancy and explicit source lineage,
So that every domain can persist and search merged entities safely without inventing a new matching engine.

## Acceptance Criteria

- **Given** the migration runs, **When** complete, **Then** it creates `canonical_entities`, `canonical_entity_sources`, `canonical_merge_history`, and `canonical_persist_outbox` with Alembic-owned indexes and downgrade support for a database that has not accepted production writes.
- **Given** `canonical_entities`, **Then** each row stores: `id` (UUID PK), `workspace_id` (Integer FK), `entity_type` (String), `canonical_title` (String), `canonical_data` (JSONB), `fingerprint` (String), `search_text` (Text), `source_count` (Integer), `confidence_score` (Float), `conflict_flags` (JSONB), `version` (Integer), `first_seen_at`, `last_seen_at`, `embedding` (Vector), `embedding_model_name`, `embedding_content_hash`, and `embedding_status` (`pending`/`ready`/`failed`).
- **Given** two domains can produce the same fingerprint text, **Then** the database unique constraint and every upsert target are exactly `(workspace_id, entity_type, fingerprint)`.
- **Given** provenance is required by search, review and revert flows, **Then** `canonical_entity_sources` stores `workspace_id`, `canonical_entity_id`, `entity_type`, `source_name`, `source_record_id`, redacted source snapshot, source URL, source timestamps and source fingerprint.
- **Given** the same source record can appear in only one active canonical entity per domain, **Then** the unique constraint on sources is exactly `(workspace_id, entity_type, source_name, source_record_id)`; `canonical_entity_id` is a FK index, not part of that uniqueness key.
- **Given** conflicts are stored as JSONB, **Then** each flag mirrors the existing BDS `ConflictFlag` shape (`type`, `reason`, optional range/source maps) rather than free-form strings.
- **Given** concurrent merge/revert is possible, **Then** writes use `version` for compare-and-swap or an equivalent row lock; no update may silently overwrite a later entity version.
- **Given** the application uses pooled SQLAlchemy sessions, **Then** every API request and Celery task opens a transaction and executes `SET LOCAL app.workspace_id = :workspace_id` before canonical reads/writes; the workspace ID is passed explicitly in task payloads and never inferred from process-global state.
- **Given** database RLS is the isolation boundary, **Then** all four tables use `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and policies based on `current_setting('app.workspace_id', true)`; the application role is non-owner and `NOBYPASSRLS`, while the unset/invalid workspace context fails closed.
- **Given** BDS currently has a context-free capability executor, **When** it becomes persistent, **Then** `vn_bds.aggregate` accepts the execution context/workspace explicitly before any write path is enabled. Jobs follows the same contract.
- **Given** AD-27, **Then** BDS and Jobs expose `fingerprint()`, `merge()`, and `search_text()` through the documented domain module boundary while reusing their current dedupe behavior; the three functions may live as named exports from existing modules (for example `dedupe.py` / `normalize.py`) and do not require three new files on day one.
- **Given** a canonical row is created or its `search_text` changes, **Then** commit succeeds with `embedding_status='pending'`; an idempotent Celery task keyed by `(entity_id, version, embedding_model_name)` populates the embedding only if the entity version still matches.
- **Given** search and review latency budgets, **Then** the migration creates at least: unique btree on `canonical_entities (workspace_id, entity_type, fingerprint)`; btree on `canonical_entities (workspace_id, entity_type, last_seen_at DESC)`; GIN/`to_tsvector` on `search_text`; HNSW/`vector_cosine_ops` on `embedding` (nullable-safe); btree on `canonical_entity_sources (canonical_entity_id)` and the source uniqueness key; btree on `canonical_merge_history (canonical_entity_id, created_at)` and `canonical_persist_outbox (status, next_attempt_at)`.
- **Given** search/review UI requires real-time state, **Then** the minimal non-PII columns for canonical entities, source links and merge history are added to `ZERO_PUBLICATION`; bulky snapshots remain REST-fetched.

## Validation

- Backend convention tests cover both domains and the exact module signatures.
- Migration tests verify upgrade, clean downgrade-before-writes, constraints and required indexes.
- Raw SQL tests run as the real non-owner application role and prove cross-workspace reads/writes, missing context and pooled-connection reuse fail closed.
- Celery tests prove workspace propagation, idempotent embedding backfill and stale-version protection.

## Tags

AD-27, AD-28, AD-2, AD-24, AD-25, pgvector, RLS, Celery
