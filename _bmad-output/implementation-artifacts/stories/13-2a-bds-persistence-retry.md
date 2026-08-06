# Story 13.2a: BDS Persistence & Retry

**Status:** done
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P0

## Story

As a user,
I want BĐS aggregator results persisted with provenance and reversible history,
So that search survives the originating request and merge decisions remain auditable.

## Acceptance Criteria

- **Dependency:** Story 13.1; may run before Epic 12.
- **Given** `vn_bds.aggregate` completes, **When** results are returned, **Then** the capability passes `workspace_id` through its execution context and idempotently upserts `canonical_entities` on `(workspace_id, entity_type, fingerprint)`.
- **Given** a source contributes to an entity, **Then** its redacted provenance is upserted into `canonical_entity_sources`; `source_count` is derived from distinct linked sources, not trusted from request payloads.
- **Given** persistence fails, **Then** aggregation still returns results with additive `persistence_status` on the existing aggregate output schema (`VnBdsAggregateOutput` / equivalent), while a durable outbox/retry record preserves the workspace, idempotency key and payload reference; retries cannot create duplicate entities or source links, and terminal failure emits a metric/alert.

## Validation

- Integration tests: `test_bds_persistence.py` verifies upsert, source_count, conflict flags, outbox on failure.
- Capability regression: existing `test_vn_bds_aggregate.py` still passes and includes `persistence_status`.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, AD-24, BĐS, canonical, persistence, outbox
