# Story 13.1: Canonical Persistence, Tenancy & Convention `[DROPPED 2026-08-08]`

> **DROPPED per SCP 2026-08-08.** Nowing no longer builds `canonical_entities` tables, multi-domain index, or unified search corpus. `chainlens-research` owns the canonical index. This story file is retained for reference only.

**Status:** dropped  
**Epic:** Epic 13 — Canonical Entity Storage & Multi-Domain Indexing  
**Priority:** P0

> **Note:** This quick-reference story has been archived. The canonical, comprehensive BMAD story file now lives at:
>
> `_bmad-output/implementation-artifacts/archive/epic-13/13-1-canonical-persistence-tenancy-convention.md`
>
> The validation report is at:
>
> `_bmad-output/implementation-artifacts/validation-reports/13-1-validation-report.md`

---

## Quick Reference

- **Baseline commit:** `72806b18de0df53071d7f310c1c3f7706cb12f96`
- **Scope:** Shared canonical persistence, database-enforced tenancy, source lineage, and BDS/Jobs domain conventions.
- **Key files:**
  - `nowing_backend/alembic/versions/193_add_canonical_entities.py`
  - `nowing_backend/app/db.py` (canonical models)
  - `nowing_backend/app/canonical/tenant_context.py`
  - `nowing_backend/app/canonical/services/canonical_persist_service.py`
  - `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py`
  - `nowing_backend/app/services/bds_aggregator/dedupe.py`
  - `nowing_backend/app/services/jobs_aggregator/dedupe.py`

For full acceptance criteria, dev notes, architecture guardrails, file list, and change log, see the canonical file linked above.
