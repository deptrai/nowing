# Joint Implementation Readiness Report — Nowing + chainlens-research Ecosystem (v6, 2026-08-08)

**Project:** Nowing ↔ chainlens-research  
**Date:** 2026-08-08  
**Scope:** Cross-project ecosystem alignment (PRD, architecture, epics, UX, tests)  
**Assessor:** Winston (System Architect)  
**Status:** 🟢 **READY FOR IMPLEMENTATION — all cross-project planning artifacts are aligned.**

---

## 1. Cross-Project Readiness Dimensions

| Dimension | Nowing | chainlens-research | Cross-Project Verdict |
|---|---|---|---|
| **PRD** | ✅ NG-5 + FR-58..FR-62 added | ✅ FR-32..FR-36 added in §4.11 + §1.8 mapping | ✅ Aligned |
| **Architecture** | ✅ AD-27/28 re-scoped, AD-34/35 new; sources cross-ref chainlens spine | ✅ AD-1..AD-7; sources cross-ref Nowing PRD/spine; `source` enum canonical | ✅ Ratified |
| **Epics & Stories** | ✅ Epic 13 removed, 10.4/12.4/E14–E17 re-scoped, feed ACs added | ✅ Epic 47 with 47-1..47-6 + 47-IT1 | ✅ Complete |
| **UX Contracts** | ✅ `ux-contract-ecosystem-search.md`, `ux-contract-private-data-provider.md` | ⚠️ No dedicated UX contract yet | 🟡 Partial — chainlens-research UX mostly internal, but worth a one-pager for provider/debug UI |
| **Interface Contracts** | ✅ `POST /v1/ingest/scraper`, `/v1/gap-fill`, `/v1/private-data/search` in FR-58..62 | ✅ Same endpoints in FR-32..36 | ✅ Identical |
| **Chunk Schema / `source` Enum** | ✅ Nowing PRD FR-62 + AD-34 use canonical enum | ✅ FR-36 + AD-3 consistency convention | ✅ Aligned |
| **Integration Tests** | ✅ Story 47-IT1 defined in chainlens-research epics; `bmad-nowing-integration-test` skill available | ✅ Same story | 🟡 Planned — no code yet |
| **Tech-debt** | ✅ Epic 13 deprecation recorded in `deferred-work.md` + `epics.md` | N/A | ✅ Documented |
| **Sprint Status** | ✅ `sprint-status.yaml` drops Epic 13, keeps integration surface | ✅ `sprint-status.yaml` now has 47-1..47-6 + 47-IT1 | ✅ Aligned |

---

## 2. What Changed Since v4

1. **chainlens-research PRD updated:** `prd-chainlens-research-2026-07-23/prd.md` now has §1.8 Ecosystem Mapping and §4.11 with FR-32..FR-36.
2. **chainlens-research architecture binds:** Updated to `FR-1..FR-36` and `FR-58..FR-62`.
3. **Cross-project source/enum alignment:** `source` enum (`public_crawl`, `nowing_scraper`, `private_provider`, etc.) identical on both sides.
4. **chainlens-research sprint-status updated:** Added `47-1..47-6` and `47-IT1` with `ready-for-dev`/`backlog` status.
5. **Joint readiness:** This v6 report combines Nowing + chainlens-research into a single readiness view.

---

## 3. Remaining Gaps (Implementation, not Readiness)

| # | Gap | Owner | Severity |
|---|---|---|---|
| 1 | Implement `POST /v1/ingest/scraper` (Story 47-1) | chainlens-research | P0 |
| 2 | Implement `Nowing` scraper `to_chunks()` + `NowingIngestService` | Nowing | P0 |
| 3 | Implement `POST /v1/gap-fill` + indexing jobs (Story 47-2) | chainlens-research | P0 |
| 4 | Implement `NowingPrivateProvider` `POST /v1/private-data/search` (Story 47-3 / FR-60/34) | Nowing | P0 |
| 5 | Implement cross-project service auth + cost allocation (Story 47-4 / FR-61/35) | Both | P0 |
| 6 | Run Story 47-IT1 integration tests | QA / both | P1 |
| 7 | Deprecate/remove Epic 13 code in Nowing | Nowing | P2 |

---

## 4. Recommendation

**Cross-project planning is complete.** The two PRDs, architecture spines, epics, and interface contracts are now mutually consistent. The critical path is implementation of the three internal endpoints (`ingest`, `gap-fill`, `private-data/search`) plus the `Nowing` scraper feed adapter.

**Next step:** Start **Story 47-1** and the **Nowing `to_chunks()`** work in parallel; everything else depends on those two.
