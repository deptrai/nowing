---
title: "Epic 13 — Validation Plan: Canonical Entity Storage & Multi-Domain Indexing"
project: Nowing
date: 2026-08-06
author: Mary (Business Analyst) + Party Mode consensus + Winston architecture hardening
status: draft
---

# Epic 13 — Validation Plan

## Purpose

Validate that Epic 13 provides tenant-safe, idempotent canonical persistence; reversible merge history; PII-safe provenance; and a unified rank-based search path whose quality and latency are measurable.

## Validation Boundaries

- **Backend unit/integration tests:** database schema, RLS, session context, outbox/idempotency, merge concurrency, PII and Celery behavior under `nowing_backend/tests/`.
- **Black-box eval suite:** quality and end-to-end latency through Nowing's public HTTP API under `nowing_evals/src/nowing_evals/suites/canonical/`. The eval package must not import backend modules.
- **Fixtures and generated run data:** `nowing_evals/data/canonical/fixtures/` and `nowing_evals/data/canonical/runs/`.
- **Report command:** the existing module CLI, `python -m nowing_evals report --suite canonical`.

---

## Story 13.1: Canonical Persistence, Tenancy & Convention

### Backend Test Matrix

| Test | Proposed path | Gate |
|------|---------------|------|
| Schema and constraints | `nowing_backend/tests/integration/canonical/test_canonical_schema.py` | Four canonical tables exist; FK, check and unique constraints match the story |
| Exact upsert key | `nowing_backend/tests/integration/canonical/test_canonical_upsert_key.py` | `(workspace_id, entity_type, fingerprint)` is both the unique constraint and conflict target |
| Source lineage | `nowing_backend/tests/integration/canonical/test_canonical_source_lineage.py` | Source identity/snapshot/URL can be authorized, grouped and reverted |
| Source uniqueness | `nowing_backend/tests/integration/canonical/test_canonical_source_unique_key.py` | Unique key is exactly `(workspace_id, entity_type, source_name, source_record_id)` |
| Required indexes | `nowing_backend/tests/integration/canonical/test_canonical_indexes.py` | Entity, FTS, HNSW, source FK/unique, history and outbox indexes exist |
| Migration lifecycle | `nowing_backend/tests/integration/canonical/test_canonical_migration.py` | Upgrade and clean downgrade succeed on an empty/no-production-write database; constraints and indexes are present |
| Domain convention | `nowing_backend/tests/unit/services/test_canonical_convention_compliance.py` | BDS and Jobs expose `fingerprint`, `merge`, `search_text` with the agreed signatures (named exports from existing aggregator modules are allowed) |
| BDS workspace context | `nowing_backend/tests/unit/capabilities/test_vn_bds_persistence_context.py` | Persistent BDS execution cannot run without explicit workspace context |
| SQL RLS isolation | `nowing_backend/tests/integration/canonical/test_canonical_rls_sql.py` | Real non-owner `NOBYPASSRLS` app role cannot read/write another workspace |
| RLS fails closed | `nowing_backend/tests/integration/canonical/test_canonical_rls_missing_context.py` | Missing/invalid `app.workspace_id` returns no rows or rejects writes; never exposes all rows |
| Pool context reset | `nowing_backend/tests/integration/canonical/test_canonical_rls_pool_reuse.py` | Reused pooled connection cannot retain the previous request's workspace |
| Celery context propagation | `nowing_backend/tests/integration/canonical/test_canonical_task_context.py` | Workspace is explicit in task payload and transaction-local context is set before DB access |
| Embedding backfill | `nowing_backend/tests/integration/canonical/test_canonical_embedding_backfill.py` | Retry is idempotent; stale entity version/model cannot overwrite a newer embedding |
| Zero publication | `nowing_backend/tests/integration/canonical/test_canonical_zero_publication.py` | Minimal review/list columns are published; snapshots/PII are excluded |

### Acceptance Gate

- All tests above pass against PostgreSQL using the same role shape as production.
- RLS tests do not run as table owner, superuser or a role with `BYPASSRLS`.
- Downgrade is tested only before production writes. After canonical data exists, rollback policy is forward-fix or an explicit export/migration; the test must not claim a destructive table drop is "no data loss."

---

## Story 13.2a: BDS Persistence & Retry

| Test | Proposed path | Gate |
|------|---------------|------|
| Context-required write | `nowing_backend/tests/integration/canonical/test_bds_persist_workspace.py` | BDS executor receives workspace context before persistence |
| Idempotent upsert | `nowing_backend/tests/integration/canonical/test_bds_persist_idempotency.py` | Repeating the same aggregate result creates no duplicate entity/source link |
| Best-effort response | `nowing_backend/tests/integration/canonical/test_bds_persist_best_effort.py` | DB failure does not erase aggregate output and returns explicit `persistence_status` |
| Durable retry | `nowing_backend/tests/integration/canonical/test_bds_persist_outbox.py` | Failure creates one durable retry item; retry preserves tenant and idempotency key |
| Terminal failure signal | `nowing_backend/tests/integration/canonical/test_bds_persist_alert.py` | Exhausted retries emit a low-cardinality metric/alert |

## Story 13.2b: Jobs Persistence & Retry

| Test | Proposed path | Gate |
|------|---------------|------|
| Jobs idempotency | `nowing_backend/tests/integration/canonical/test_jobs_persist_idempotency.py` | Existing Jobs fingerprint behavior is reused with canonical tenant/entity scope |
| Partial source failure | `nowing_backend/tests/integration/canonical/test_jobs_partial_source_failure.py` | Successful sources persist; degraded source metadata remains; later retry adds only missing links |
| Retry parity | `nowing_backend/tests/integration/canonical/test_jobs_persist_outbox.py` | Jobs uses the same durable outbox contract as BDS |

## Story 13.2c: Merge History, Conflict Resolution & Revert

| Test | Proposed path | Gate |
|------|---------------|------|
| Transitive BDS match | `nowing_backend/tests/unit/services/test_canonical_transitive_match.py` | A↔B and B↔C produce one cluster without changing existing BDS semantics |
| Concurrent merge | `nowing_backend/tests/integration/canonical/test_canonical_concurrent_merge.py` | Expected-version or row-lock contract produces no lost update |
| Audited revert | `nowing_backend/tests/integration/canonical/test_canonical_merge_revert.py` | Revert creates a new history transition and never overwrites later versions |
| Source-set restoration | `nowing_backend/tests/integration/canonical/test_canonical_source_revert.py` | Revert/split restores both canonical fields and linked-source state |
| Resolution contract | `nowing_backend/tests/integration/canonical/test_canonical_merge_conflict_resolution.py` | Actor, method, conflicts and before/after versions are complete and authorized |

## Story 13.2d: PII-Safe Canonicalization

| Test | Proposed path | Gate |
|------|---------------|------|
| Canonical PII scan | `nowing_backend/tests/integration/canonical/test_canonical_pii_scan.py` | Zero raw phone, email or person-name PII in canonical JSON/search text |
| Provenance/history/outbox scan | `nowing_backend/tests/integration/canonical/test_canonical_pii_all_stores.py` | Source snapshots, merge history and retry payloads are also clean |
| BDS contact protection | `nowing_backend/tests/unit/services/test_bds_canonical_pii.py` | `contact`/`phone_key` are removed, masked or one-way keyed before storage |
| Jobs text protection | `nowing_backend/tests/unit/services/test_jobs_canonical_pii.py` | JD/JR redaction occurs before every persistence boundary |
| Log hygiene | `nowing_backend/tests/integration/canonical/test_canonical_pii_logs.py` | Logs/metrics contain counts and status only |

## Story 13.2e: Dedup Benchmark & Release Gate

### Fixture Location

```text
nowing_evals/data/canonical/fixtures/
├── bds_dedup_tier15.jsonl
├── bds_dedup_tier30.jsonl
├── bds_dedup_tier70.jsonl
├── jobs_dedup_tier15.jsonl
├── jobs_dedup_tier30.jsonl
└── jobs_dedup_tier70.jsonl
```

Each fixture header must declare independent raw-record and entity counts:

```json
{
  "domain": "bds",
  "tier": "tier30",
  "total_raw_records": 1000,
  "total_ground_truth_entities": 600,
  "multi_source_ground_truth_entities": 180,
  "overlap_rate": 0.30,
  "sources": ["batdongsan", "chotot_bds", "muaban_bds"]
}
```

`overlap_rate` is validated as:

```text
multi_source_ground_truth_entities / total_ground_truth_entities
```

It is not inferred from `known_duplicates / total_raw_records`. A fixture validator must reject mismatched metadata before a benchmark run.

### Metric Definition

- Convert predicted clusters and ground-truth clusters into unordered duplicate record pairs.
- `TP` = predicted duplicate pair present in ground truth.
- `FP` = predicted duplicate pair absent from ground truth.
- `FN` = ground-truth duplicate pair split across predicted clusters.
- Report precision, recall and F1 for each domain × overlap tier, plus macro averages.
- Every domain/tier must meet `precision ≥ 0.95`, `recall ≥ 0.90`, and `F1 ≥ 0.92`; an average cannot hide a failing tier.

### Eval Package

```text
nowing_evals/src/nowing_evals/suites/canonical/
├── __init__.py
├── dedup/
│   ├── __init__.py
│   ├── ingest.py
│   ├── runner.py
│   └── metrics.py
└── search/
    ├── __init__.py
    ├── ingest.py
    ├── runner.py
    └── metrics.py
```

---

## Story 13.3: Unified Search

### Search Fixture

**Path:** `nowing_evals/data/canonical/fixtures/canonical_search_500.jsonl`

Each case contains one query, ranked relevance judgments for canonical entities and unmatched documents, and the source-document → canonical-entity grouping expected by the API. Linked source documents are not separate relevant top-level hits.

### Test Matrix

| Test | Location | Metric / gate |
|------|----------|---------------|
| Search quality | canonical eval `search` benchmark | Recall@10 ≥ 0.85; Precision@5 ≥ 0.80 |
| E2E latency | canonical eval `search` benchmark | p95 < 500 ms including query embedding, both corpora and fusion |
| Weighted RRF | `nowing_backend/tests/unit/retriever/test_canonical_weighted_rrf.py` | Uses ranks and workspace weights; never adds raw cosine distance to `ts_rank_cd` |
| Filter parity | `nowing_backend/tests/integration/canonical/test_canonical_search_filter_parity.py` | Workspace/date/status/type filters apply identically to vector and full-text paths |
| Pending/stale embedding | `nowing_backend/tests/integration/canonical/test_canonical_search_pending_embedding.py` | Full-text fallback works; stale/current-model mismatch is excluded from vector path |
| Cross-corpus collapse | canonical eval + backend integration test | Linked source documents collapse beneath canonical entity; duplicate top-level groups = 0 |
| Source expansion auth | `nowing_backend/tests/integration/canonical/test_canonical_source_expansion_auth.py` | `View N sources` exposes only current workspace's redacted lineage |
| A/B improvement | canonical eval `search` benchmark | Same query set/judgments; report baseline and relative change, target ≥10% relative recall improvement |

### A/B Methodology

```text
1. Run the fixed 500-query set against documents-only retrieval.
2. Run the same queries and relevance judgments against documents + canonical retrieval.
3. Compute absolute Recall@10 and Precision@5 for both arms.
4. Compute relative recall change = (canonical_recall - baseline_recall) / baseline_recall.
5. Report all metrics even when the 10% improvement target is not reached.
```

---

## Release Priorities

### P0 — Ship Blocking

- Schema, exact entity upsert key `(workspace_id, entity_type, fingerprint)`, source unique key `(workspace_id, entity_type, source_name, source_record_id)`, and required index tests.
- Real-role RLS isolation, missing-context, pooled-connection and Celery-context tests.
- BDS workspace-context gate before persistence is enabled.
- Idempotent writes and durable outbox/retry for both domains.
- Concurrent merge, audited revert and source-set restoration.
- PII scan across canonical data, lineage, history, outbox, logs and embeddings/search text.
- Weighted-RRF, filter parity, cross-corpus collapse and source-expansion authorization.
- Search quality and p95 latency gates.

### P1 — Quality Gate Before General Availability

- Six domain/tier dedup fixtures and fixture-metadata validation.
- Per-tier precision/recall/F1 gates and storage-savings report.
- Pending/stale embedding consistency and retry metrics.
- Partial-source recovery and terminal-failure alert verification.
- A/B search improvement report and manual relevance review.
- Zero publication shape verification for review/list surfaces.

---

## Commands

```bash
cd nowing_evals
python -m nowing_evals benchmarks list
python -m nowing_evals ingest canonical dedup
python -m nowing_evals run canonical dedup
python -m nowing_evals ingest canonical search
python -m nowing_evals run canonical search
python -m nowing_evals report --suite canonical
```

The canonical benchmark may add suite-specific flags, but it must register through the existing `python -m nowing_evals` CLI. Do not introduce a root-level `report.py` runner.

---

## Effort and Sequencing

| Phase | Dependency | Estimate |
|-------|------------|----------|
| Schema, source lineage, RLS role/session contract | Story 13.1 | 2–3 engineering days |
| BDS + Jobs idempotent persistence/outbox | Story 13.1; Jobs also Epic 12 | 2–3 days |
| Merge history, concurrency and revert | At least one persistence path | 2 days |
| PII hardening across all stores | Before persistence enablement | 1–2 days |
| Canonical eval package + six dedup fixtures | Stable persistence API | 2–3 days |
| Unified search + collapse + benchmark | Source lineage and embeddings | 2–3 days |
| **Total validation/architecture hardening** | Spread across Epic 13 | **~11–16 engineering days** |

---

## Data Sources

| Source | Use |
|--------|-----|
| HR pilot data after Epic 12 | Jobs fixture calibration and real-world error review |
| Existing BDS aggregator output | BDS fixtures, transitive-match and conflict cases |
| `nowing_evals/src/nowing_evals/suites/chat/regression/` | Reuse registry, CLI, HTTP client and report patterns |
| PostgreSQL catalog and `pg_size_pretty()` | Constraints, indexes, RLS role and storage measurements |
| Application metrics | Latency, retry, stale embedding and terminal persistence failures |

---

## Success Criteria Summary

| Criterion | Target |
|-----------|--------|
| Dedup precision | ≥ 0.95 for every domain/tier |
| Dedup recall | ≥ 0.90 for every domain/tier |
| Dedup F1 | ≥ 0.92 for every domain/tier |
| Search Recall@10 | ≥ 0.85 |
| Search Precision@5 | ≥ 0.80 |
| Search p95 latency | < 500 ms end-to-end |
| Cross-workspace access | 0 successful unauthorized reads/writes |
| Lost concurrent updates | 0 |
| Duplicate top-level search groups | 0 |
| PII leaks across all persistence/log surfaces | 0 |
| Duplicate entities/source links after retry | 0 |

---

**Document Status:** Draft — architecture gates are explicit; implementation can begin after Story 13.1 role/session design is accepted.
