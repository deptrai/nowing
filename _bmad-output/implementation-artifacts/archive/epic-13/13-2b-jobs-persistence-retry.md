# Story 13.2b: Jobs Persistence & Retry `[DROPPED 2026-08-08]`

> **DROPPED per SCP 2026-08-08.** Nowing no longer builds `canonical_entities` tables, multi-domain index, or unified search corpus. `chainlens-research` owns the canonical index. This story file is retained for reference only.

**Status:** dropped
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing
**Priority:** P0

## Story

As a user,
I want job aggregator results persisted with provenance and reversible history,
So that search survives the originating request and merge decisions remain auditable.

## Acceptance Criteria

- **Dependency:** Story 13.1 and Epic 12 aggregator output contract.
- **Given** `vn_jobs.aggregate` completes, **Then** it uses the same tenant, idempotency, source-link and outbox contract as BDS without replacing its existing Jobs dedupe key, and extends `VnJobAggregateOutput` with the same additive `persistence_status` field.
- **Given** partial source failure, **Then** successful source results are persisted, failed sources remain visible in degradation metadata, and later retry can add missing source links without rewriting unrelated fields.

## Validation

- Integration tests: `test_jobs_persistence.py` verifies upsert, source_count, PII redaction, idempotency, partial persistence on failure.
- Capability regression: existing `test_vn_jobs_aggregate.py` still passes and includes `persistence_status`.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, AD-24, Jobs, canonical, persistence, outbox
