---
title: Story 12.5 — PII Redaction for Job Data
epic: 12
story: 5
status: done
priority: P0
---

# Story 12.5 — PII Redaction for Job Data

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** workspace owner  
**I want:** job postings to be scanned for personal information before storage  
**So that:** Nowing does not accidentally retain candidate PII.

---

## Acceptance Criteria

### AC-1 — Phone + email redaction
**Given** `job_description` / `job_requirement` from any source, **When** PII redaction runs, **Then** it detects Vietnamese phone numbers and email addresses via regex and replaces them with `<PHONE>` and `<EMAIL>`.

### AC-2 — Person name redaction
**Given** person names in JD text, **When** detected, **Then** it flags via NER/heuristic and masks or drops the field.

### AC-3 — Audit logging without values
**Given** detected PII, **When** logged, **Then** only counts are recorded (no values).

### AC-4 — No raw JD in memory
**Given** redaction runs, **When** storing to memory, **Then** the full raw JD is not stored unredacted.

---

## Current State

- Skeleton exists at `app/services/pii/redact.py`:
  - `RedactedText` dataclass with `phones_detected`, `emails_detected`, `names_detected`, `has_pii`.
  - `redact_job_pii(text)` alias for `redact_pii(text, context="job_data")`.
  - Regex for phones, emails, and Vietnamese names.
- Already wired into `app/services/jobs_aggregator/orchestrator.py:_redact_listing` (Story 12.4c/d/e).
- Already wired into `app/services/scraper_chunks/serializer.py` chunk content building (defense-in-depth).
- `record_vn_jobs_pii_detected` metric is called with structured counts (no values).

## Verification

### AC Coverage

| AC | Evidence | Status |
|----|----------|--------|
| AC-1 | `tests/unit/services/pii/test_redact.py::test_redacts_vietnamese_phone`, `test_redacts_email`, `test_redacts_*_sample` | ✅ |
| AC-2 | `tests/unit/services/pii/test_redact.py::test_redacts_person_name`, `_*_sample`; regex heuristic on Vietnamese surnames + capitalized words | ✅ |
| AC-3 | `tests/unit/services/jobs_aggregator/test_pii_redaction.py::test_redact_listing_logs_pii_counts_as_structured_log_not_values`; `record_vn_jobs_pii_detected` only emits counts | ✅ |
| AC-4 | `tests/integration/canonical/test_pii_safe_persistence.py::test_jobs_canonical_data_no_jd`; `canonical_pii.py:_redact_text_value` redacts `job_description` / `job_requirement` for `vn_job`; orchestrator + serializer redact output before chunking | ✅ |

### Tests Added

- `tests/unit/services/pii/test_redact.py` extended with representative VietnamWorks, TopCV, and ITviec sample tests.

## Implementation Notes

- Implemented in `app/services/pii/redact.py` and reused by `app/canonical/services/canonical_pii.py`.
- `redact_job_pii` is called from:
  - `app/services/jobs_aggregator/orchestrator.py:_redact_listing`
  - `app/services/scraper_chunks/serializer.py:_redact_text`
  - `app/canonical/services/canonical_pii.py:_redact_text_value`
- Name detection uses a regex heuristic (common Vietnamese surnames + capitalized words). This satisfies the AC which allows NER or heuristic, but has a known false-positive ceiling on company names like "Nguyễn Văn JSC". Documented as a `ponytail` upgrade path in code.
- Logs and metrics emit only counts, never PII values.

## Technical Requirements

- Pydantic / dataclass contracts must remain backward-compatible.
- All counts are `int`, non-negative.
- Redaction must be idempotent: `redact_job_pii(redact_job_pii(text).text)` should not change `<PHONE>` placeholders and counts should be 0 on second pass.
- Logs must never emit PII values; use `record_vn_jobs_pii_detected(source, pii_type, count)`.

## File Touch Plan

| Action | File |
|--------|------|
| Update | `app/services/pii/redact.py` (improve name detection) |
| Add tests | `tests/unit/services/pii/test_redact.py` |
| Add tests | `tests/unit/services/jobs_aggregator/test_pii_redaction.py` (extend with source samples) |
| Add integration test | `tests/integration/memory/test_memory_pii_redaction.py` or `tests/integration/services/jobs_aggregator/test_aggregator_pii_memory.py` |
| Verify | `app/services/memory/run_extraction.py` / `Memory` creation path |

## Test Commands

```bash
# Unit tests for redaction
uv run pytest tests/unit/services/pii tests/unit/services/jobs_aggregator/test_pii_redaction.py -q

# Integration test for memory path (requires Postgres + Redis)
uv run pytest tests/integration/services/jobs_aggregator -q

# Lint
ruff check app/services/pii tests/unit/services/pii
ruff format app/services/pii tests/unit/services/pii
```

## Architecture Compliance

- **AD-25**: PII redaction before chunk + ingest (already wired, verify completeness).
- **NFR-11**: Scraping compliance & anti-bot resilience (PII pipeline part).

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/pii/redact.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/jobs_aggregator/orchestrator.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/scraper_chunks/serializer.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md" />
