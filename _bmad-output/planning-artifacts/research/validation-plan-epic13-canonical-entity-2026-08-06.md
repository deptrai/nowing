---
title: "Epic 13 — Validation Plan: Canonical Entity Storage & Multi-Domain Indexing"
project: Nowing
date: 2026-08-06
author: Mary (Business Analyst) + Party Mode consensus
status: draft
---

# Epic 13 — Validation Plan

## Purpose

Validate that the canonical entity storage & indexing system (Epic 13) achieves its goals: deduplication accuracy, storage efficiency, search quality improvement, and PII compliance.

**Validation infrastructure:** `nowing_evals/` (existing eval framework, reused from chat regression + memory recall suites).

---

## Story 13.1: Schema & Convention — Validation

### Tests

| Test | File | What it validates |
|------|------|-------------------|
| Convention compliance | `test_canonical_convention_compliance.py` | All domains implement `fingerprint()`, `merge()`, `search_text()` with consistent signatures |
| RLS isolation | `test_canonical_rls_isolation.py` | Workspace A cannot query Workspace B's canonical entities |
| Migration rollback | `test_canonical_migration_rollback.py` | Alembic upgrade/downgrade clean, no data loss |

### Acceptance Criteria Met When
- All 3 tests pass (green)
- Zero manual workarounds needed

---

## Story 13.2: Persist Aggregator Output — Validation

### Benchmark Dataset

**File:** `nowing_evals/datasets/canonical_dedup_1000.json`

```json
{
  "metadata": {
    "total_listings": 1000,
    "unique_entities": 300,
    "known_duplicates": 700,
    "cross_source_overlap_pct": 70,
    "sources": ["batdongsan", "chotot", "muaban"]
  },
  "listings": [
    {
      "id": "listing_001",
      "source": "batdongsan",
      "raw_data": { ... },
      "canonical_entity_id": "entity_001"  // ground truth
    }
  ]
}
```

### Tests

| Test | File | Metrics | Target |
|------|------|---------|--------|
| Dedup accuracy | `test_dedup_accuracy.py` | Precision, Recall, F1 | P ≥ 0.95, R ≥ 0.90 |
| Merge correctness | `test_canonical_merge_revert.py` | Conflict resolution accuracy | ≥ 0.85 |
| PII compliance | `test_canonical_pii_scan.py` | PII leaks detected | 0 |
| Storage savings | `test_canonical_storage_savings.py` | `(raw - canonical) / raw` | ≥ 0.60 |

### Dedup Benchmark Methodology

```
1. Load canonical_dedup_1000.json
2. Run aggregator pipeline (BDS + Jobs) → write to canonical_entities
3. Compare output canonical_entities vs ground truth:
   - TP: correctly merged duplicates
   - FP: incorrectly merged distinct entities
   - FN: missed duplicates (still in raw_scrapes only)
4. Report precision, recall, F1
```

### Acceptance Criteria Met When
- Precision ≥ 0.95 (few false merges)
- Recall ≥ 0.90 (catches most duplicates)
- 0 PII leaks
- ≥ 60% storage reduction

---

## Story 13.3: Unified Search — Validation

### Benchmark Dataset

**File:** `nowing_evals/datasets/canonical_search_500.json`

```json
{
  "metadata": {
    "total_queries": 500,
    "expected_results_per_query": 10,
    "entity_types": ["property", "job"],
    "corpus_size": 5000
  },
  "queries": [
    {
      "query": "căn hộ 2PN Thủ Đức giá 3 tỷ",
      "expected_entity_ids": ["entity_042", "entity_198", ...],
      "expected_documents": ["doc_001", "doc_045", ...]
    }
  ]
}
```

### Tests

| Test | File | Metrics | Target |
|------|------|---------|--------|
| Search quality | `test_search_quality.py` | Recall@10, Precision@5 | R≥0.85, P≥0.80 |
| Search latency | `test_canonical_search_latency.py` | p95 latency | < 500ms |
| No duplicates | `test_canonical_no_duplicates.py` | Duplicate entity rate in results | 0 |
| A/B improvement | `test_canonical_ab_search.py` | Recall improvement vs documents-only | ≥ 10% relative |

### A/B Comparison Methodology

```
1. Run 500 queries against documents-only corpus → baseline recall
2. Run same 500 queries against documents + canonical corpus → new recall
3. Compare: (new - baseline) / baseline = relative improvement
4. Target: ≥ 10% improvement (canonical entities capture queries documents miss)
```

### Acceptance Criteria Met When
- Recall@10 ≥ 0.85
- Precision@5 ≥ 0.80
- p95 < 500ms
- 0 duplicate results in any query
- ≥ 10% recall improvement over documents-only

---

## Post-Implementation Validation Report

### Report Structure

| Section | Data Source | Key Metrics |
|---------|-------------|-------------|
| **1. Dedup Effectiveness** | `test_dedup_accuracy.py` | Precision, recall, F1 per domain |
| **2. Storage Impact** | `test_canonical_storage_savings.py` | GB saved, embedding cost reduction |
| **3. Search Quality** | `test_search_quality.py` | Recall@10, Precision@5, A/B improvement |
| **4. Performance** | `test_canonical_search_latency.py` | p50/p95/p99 latency |
| **5. Compliance** | `test_canonical_pii_scan.py` | PII leak count (target: 0) |
| **6. User Impact** | Manual review | Result relevance, duplicate perception |

### Report Output

```bash
cd nowing_evals
python report.py --suite canonical --format markdown --output reports/canonical-validation-2026-08-06.md
```

---

## Timeline

| Phase | When | Duration |
|-------|------|----------|
| **Benchmark dataset creation** | During Story 13.2 implementation | 1 day |
| **Unit + integration tests** | Alongside each story | 1 day per story |
| **Eval suite implementation** | After Story 13.2 complete | 2 days |
| **Benchmark run + report** | After all 3 stories complete | 1 day |
| **Total validation effort** | Spread across Epic 13 sprint | ~5.5 days |

---

## Data Sources

| Source | Use |
|--------|-----|
| HR pilot data (8 weeks) | Real-world dedup benchmark (Story 13.2) |
| Existing BDS aggregator output | Cross-source dedup validation |
| `nowing_evals/suites/chat/regression/` | Reuse eval runner infrastructure |
| PostgreSQL `pg_size_pretty()` | Storage measurement |
| Application logs | Latency measurement |

---

## Success Criteria Summary

| Criterion | Target | Measured By |
|-----------|--------|-------------|
| Dedup Precision | ≥ 0.95 | `test_dedup_accuracy.py` |
| Dedup Recall | ≥ 0.90 | `test_dedup_accuracy.py` |
| Storage Savings | ≥ 60% | `test_canonical_storage_savings.py` |
| Search Recall@10 | ≥ 0.85 | `test_search_quality.py` |
| Search Precision@5 | ≥ 0.80 | `test_search_quality.py` |
| Search p95 Latency | < 500ms | `test_canonical_search_latency.py` |
| PII Leaks | 0 | `test_canonical_pii_scan.py` |
| Duplicate Results | 0 | `test_canonical_no_duplicates.py` |

---

**Document Status:** Draft — ready for implementation alongside Epic 13 stories.
