# Implementation Readiness Report — Nowing (Post Re-scope 2026-08-08)

**Project:** Nowing  
**Date:** 2026-08-08  
**Scope:** Ecosystem alignment with `chainlens-research` (SCP 2026-08-08 adopted)  
**Assessor:** Winston (System Architect)  
**Status:** 🟡 **CONDITIONALLY READY — implementation can start for integration surfaces; UX and chainlens-research contracts remain open.**

---

## 1. Readiness Dimensions

| Dimension | Verdict | Evidence | Open Gaps |
|---|---|---|---|
| **PRD** | ✅ Updated | `prd-Nowing-2026-07-22/prd.md` updated: NG-5 added, FR-46/49–52 re-scoped, FR-48 removed, glossary updated. | FR-46/49–52 still say `[PROPOSED]`; no new FRs for `NowingPrivateProvider` or gap-fill trigger (`POST /v1/gap-fill`) in PRD. |
| **Architecture** | ✅ Aligned | `ARCHITECTURE-SPINE.md` now has AD-27/28 re-scoped, AD-34/35 new. AD-11 clarifies `Memory` boundary. | `chainlens-research` side of interface (`SearchProvider`, `NowingPrivateProvider`, `POST /v1/ingest/scraper`, `POST /v1/gap-fill`) must be accepted there. |
| **Epics & Stories** | ✅ Re-scoped | `epics.md` marks Epic 13 `[REMOVED]`, 10.4/12.4/E14–E17 `[RE-SCOPED]`, adds `POST /v1/ingest/scraper` ACs to scrapers. `sprint-status.yaml` drops Epic 13. | Epic 47 lives in `chainlens-research`; Nowing stories need to cross-reference it. No Nowing story files created for integration endpoints yet. |
| **UX** | ⚠️ Not covered | No new UX contract for ecosystem search / private data / scraper feed UX. | Requires `ux-contract-chainlens-ingest.md`, `ux-contract-private-provider.md`, or update to existing chat citation UX. |
| **Interface Contracts** | ⚠️ Partial | `ARCHITECTURE-SPINE.md` defines AD-34 (`Chunk[]` feed) and AD-35 (no local search corpus). | `chainlens-research` canonical `Chunk.metadata` schema and `SearchProvider` methods must be finalized and ratified on both sides. |
| **Tests / Validation** | ⚠️ Not started | No failing test for the new flow. Existing tests still pass for re-scoped stories. | Need integration tests for `POST /v1/ingest/scraper` auth, idempotency, PII, and `NowingPrivateProvider` RLS. |
| **Migrations / Data** | ⚠️ Risk | Epic 13 code (13.1–13.3) is already merged; `sprint-status.yaml` marks it `dropped` / deprecated. | Decision needed: keep code as-is and stop using it, or schedule deprecation/migration to remove `canonical_entities` tables. |

---

## 2. What Changed Since Last Report

1. **Removed duplicate canonical index:** Nowing no longer builds `canonical_entities`, multi-domain `pgvector`/`to_tsvector` index, or unified vertical search (Epic 13 dropped).
2. **Re-scoped domain aggregators:** `vn_jobs.aggregate` and BĐS aggregator normalize to `Chunk[]` and call `chainlens-research` `POST /v1/ingest/scraper`.
3. **Re-scoped scrapers (E2/E10/E12/E14–E17):** All domain scrapers now have an AC to feed `chainlens-research`.
4. **Re-scoped ADs:** AD-27/AD-28 moved indexing semantics to `chainlens-research`; AD-34/AD-35 added for Nowing feed contract and search-corpus boundary.
5. **Updated PRD:** NG-5 added; FR-48 removed; FR-46/49–52 re-scoped; `Chunk` glossary updated.

---

## 3. Remaining Blockers (C1–C5)

### C1 — PRD still lacks explicit ecosystem FRs
`prd-Nowing-2026-07-22/prd.md` does not contain FRs for:
- `NowingPrivateProvider` (`POST /v1/private-data/search`)
- Gap-fill trigger (`POST /v1/gap-fill` + `POST /v1/scraper/{scraperId}/run`)
- Cross-project service auth and cost allocation
- Canonical `Chunk.metadata` schema / `source` enum enforcement

**Recommendation:** Add `FR-56..FR-60` ecosystem integration requirements, or cross-reference `chainlens-research` Epic 47 from PRD.

### C2 — UX not designed
No UX contract exists for:
- How chat/agent surfaces `chainlens-research` vs private data
- How users know a search result comes from `chainlens-research` vs private memory
- Cost/credit attribution display for cross-project calls

**Recommendation:** Create/update UX contracts before UI work.

### C3 — `chainlens-research` contracts not ratified on both sides
Nowing has AD-34/AD-35. `chainlens-research` has Epic 47 stories but implementation has not started. The canonical `Chunk` schema, `SearchProvider` interface, and `NowingPrivateProvider` contract must be identical on both sides.

**Recommendation:** Run a joint architecture/code-review gate once `chainlens-research` side is drafted.

### C4 — Existing Epic 13 code is technical debt
`canonical_entities` tables, migrations, and unified search code are already in `develop` (status `dropped` in sprint-status). They will diverge from the new architecture if left in place.

**Recommendation:** Create a tech-debt story to remove/deactivate Epic 13 code, or at least gate new code from using it.

### C5 — No integration tests for cross-project flow
`POST /v1/ingest/scraper`, `POST /v1/private-data/search`, and gap-fill are not yet exercised by real integration tests.

**Recommendation:** Add `bmad-nowing-integration-test` or equivalent after chainlens-research endpoints are stubbed.

---

## 4. Recommendation

- **Nowing side is READY to start** implementation of: scraper feed service (`NowingIngestService`), PII pipeline, and aggregator `to_chunks()` steps.
- **NOT READY to ship** vertical search/chat until:
  1. `chainlens-research` `POST /v1/ingest/scraper` and `POST /api/v1/search` are implemented.
  2. UX contracts are added.
  3. Integration tests pass.

---

## 5. Next Steps

1. **Update PRD** to add ecosystem integration FRs (`NowingPrivateProvider`, gap-fill, service auth, cost allocation) — or cross-reference `chainlens-research` Epic 47.
2. **Create/update UX contracts** for ecosystem search and private data.
3. **Implement `chainlens-research` side** of `POST /v1/ingest/scraper`, `NowingPrivateProvider`, and canonical index.
4. **Schedule Epic 13 code deprecation** (tech-debt).
5. **Run joint interface regression gate** before first cross-project integration test.
