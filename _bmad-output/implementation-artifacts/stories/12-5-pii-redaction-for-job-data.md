---
title: Story 12.5 — PII Redaction for Job Data
epic: 12
story: 5
status: ready-for-dev
priority: P0
---

# Story 12.5 — PII Redaction for Job Data

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot  
**As a:** workspace owner  
**I want:** job postings to be scanned for personal information before storage  
**So that:** Nowing does not accidentally retain candidate PII.

---

## Acceptance Criteria

1. **Given** `job_description` / `job_requirement` from any source, **When** PII redaction runs, **Then** it detects Vietnamese phone numbers and email addresses via regex.
2. **Given** person names in JD text, **When** detected, **Then** it flags via NER/heuristic and masks or drops the field.
3. **Given** detected PII, **When** logged, **Then** only counts are recorded (no values).
4. **Given** redaction runs, **When** storing to memory, **Then** the full raw JD is not stored unredacted.

---

## Non-AC Technical Notes

- Implementation skeleton exists at `app/services/pii/redact.py`.
- Wire `redact_job_pii` into `MemoryExtractionService` before LLM prompt (AD-25 Option A).
- Add unit tests for representative VietnamWorks, TopCV, and ITviec samples.

## References

- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/feature-brief-hr-vertical-vietnam-2026-08-05.md" />
