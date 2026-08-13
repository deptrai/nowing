---
coverageBasis: acceptance_criteria
oracleResolutionMode: formal_requirements
oracleConfidence: high
oracleSources:
  - _bmad-output/implementation-artifacts/9-6c-memory-provenance-end-to-end-revalidation-gate.md
externalPointerStatus: not_used
---

# Traceability Matrix — Story 9-6c

## Coverage Oracle

- **Source:** Story `9-6c` acceptance criteria (AC-1 through AC-5)
- **Confidence:** high
- **External pointers:** not used

## Acceptance Criteria → Tests → Code

| AC | Requirement | Integration Test | Unit Test | Source Code |
|----|-------------|------------------|-----------|-------------|
| AC-1 | Scraper-run memory must carry `source_type`, `source_run_id`, `source_capability`, `source_input` recipe | `test_run_extraction_populates_recipe` (`test_memory_provenance_e2e_gate.py`) | `RunMemoryExtractionService` extraction tests in `test_memory_provenance_recipe.py` | `app/services/memory/run_extraction.py:396-415` |
| AC-2 | Revalidation succeeds after source `Run` is deleted using only the recipe | `test_revalidate_after_source_run_deleted` | — | `app/services/memory/revalidation_service.py:125-283` |
| AC-2 (mismatch) | Mismatch revalidation creates `MemoryVersion` and updates content/confidence | `test_revalidate_mismatch_creates_version_after_run_deleted` | `test_revalidate_mismatch_creates_version` | `app/services/memory/revalidation_service.py:267-283`, `app/services/memory/repository.py:484-505` |
| AC-3 | Non-scraper memory returns 422, not 500 | `test_revalidate_non_scraper_memory_returns_422` | `test_revalidate_not_revalidatable_when_source_type_is_not_scraper_run` | `app/services/memory/revalidation_service.py:157-162` |
| AC-4 | Revalidation is charged and a `Run` row with `origin="revalidate"` is recorded | `test_revalidate_records_cost_and_revalidate_run` | `test_revalidate_match_bumps_confidence` (cost assertion) | `app/services/memory/revalidation_service.py:232-243` |
| AC-5 | Missing/invalid recipe returns 422, not 500 | `test_revalidate_invalid_recipe_returns_422` | `test_revalidate_not_revalidatable_when_source_capability_is_none`, `test_revalidate_invalid_recipe` | `app/services/memory/revalidation_service.py:151-162` |
| — | `_extract_text` handles Pydantic, dict, plain object, fallback | — | `test_extract_text_*` suite (`test_revalidation_unit.py`) | `app/services/memory/revalidation_service.py:67-111` |
| — | `_normalize` case-folds and collapses whitespace | — | `test_normalize_*` suite (`test_revalidation_unit.py`) | `app/services/memory/revalidation_service.py:114-116` |

## Coverage Summary

| Category | Count | Notes |
|----------|-------|-------|
| Acceptance criteria | 5 | All mapped to at least one integration test |
| Integration tests | 6 | E2E gate covers all ACs |
| Unit tests (helper) | 25 | `_extract_text` and `_normalize` mutation-killed |
| Unit tests (service) | 9 | Error branches and happy paths |
| Code files touched | 0 (story is test-only) | Tests exercise existing `revalidation_service.py` and `run_extraction.py` |

## Quality Gate Decision

**PASS**

All 5 acceptance criteria are traceable to at least one integration test. The E2E gate proves the extraction → delete Run → revalidate flow. Unit tests kill 100% of scoped mutants on the pure helpers. No uncovered P0 paths.
