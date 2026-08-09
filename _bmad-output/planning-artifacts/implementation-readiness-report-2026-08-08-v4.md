# Implementation Readiness Report — Nowing + chainlens-research Ecosystem (v4, 2026-08-08)

**Project:** Nowing ↔ chainlens-research  
**Date:** 2026-08-08  
**Scope:** Post-re-scope ecosystem alignment + blocker resolution  
**Assessor:** Winston (System Architect)  
**Status:** 🟢 **READY FOR IMPLEMENTATION — all planning blockers resolved; implementation and integration tests remain to be built before production.**

---

## 1. Readiness Dimensions (re-assessed)

| Dimension | Verdict | Evidence | Open Gaps |
|---|---|---|---|
| **PRD** | ✅ Complete | `prd-Nowing-2026-07-22/prd.md` has NG-5, re-scoped FR-46/49–52, removed FR-48, new FR-58..FR-62. | Code does not yet implement FR-58..FR-62. |
| **UX** | ✅ Covered | `ux-contract-ecosystem-search.md` + `ux-contract-private-data-provider.md` created. `ux-contract-canonical-entity.md` marked deprecated. | UI implementation pending. |
| **Architecture** | ✅ Ratified | Nowing `ARCHITECTURE-SPINE.md` sources/companion cross-references `chainlens-research` 2026-08-08 spine. `source` enum aligned. AD-34/AD-35 present. | Actual services (`NowingIngestService`, `NowingPrivateProvider`) not built. |
| **Epics & Stories** | ✅ Complete | `epics.md` re-scoped. `chainlens-research/epics.md` Epic 47 has 47-1..47-6 + 47-IT1. | Implementation not started. |
| **Interface Contracts** | ✅ Aligned | `source` enum: `public_crawl`, `nowing_scraper`, `brave`, `searxng`, `jina`, `exa`, `tavily`, `perplexity`, `private_provider`. `Chunk.metadata` required fields defined on both sides. | Need runtime schema validation tests. |
| **Tests / Validation** | 🟡 Planned | Story 47-IT1 defines cross-project integration tests. `bmad-nowing-integration-test` available. | No failing test or real CI gate exists yet. |
| **Migrations / Data** | 🟡 Documented | Epic 13 tech-debt entry in `deferred-work.md`; `epics.md` notes deprecation. | Code/tables not removed yet. |

---

## 2. What Changed Since v3

1. **B1 — PRD ecosystem FRs added:** FR-58 (scraper feed), FR-59 (gap-fill), FR-60 (`NowingPrivateProvider`), FR-61 (service auth/cost), FR-62 (`Chunk.metadata` schema).
2. **B2 — UX contracts created:** `ux-contract-ecosystem-search.md`, `ux-contract-private-data-provider.md`; deprecated canonical-entity UX contract.
3. **B3 — Tech-debt recorded:** `deferred-work.md` §"Tech-debt: Epic 13 code deprecation" + `epics.md` note.
4. **B4 — chainlens-research contracts ratified:** Cross-referenced architecture spines; aligned `source` enum; updated `binds`/`sources`.
5. **B5 — Integration test story added:** Story 47-IT1 in `chainlens-research/epics.md`.

---

## 3. Remaining Work (Implementation, not Readiness)

| # | Work | Owner | Depends on |
|---|---|---|---|
| 1 | Implement `chainlens-research` `POST /v1/ingest/scraper` (Story 47-1) | chainlens-research | Architecture AD-3 |
| 2 | Implement `chainlens-research` `POST /v1/gap-fill` + indexing jobs (Story 47-2) | chainlens-research | 47-1, AD-4 |
| 3 | Implement `NowingPrivateProvider` `POST /v1/private-data/search` (Story 47-3 / FR-60) | Nowing | AD-5 |
| 4 | Implement cross-project service auth + cost allocation (Story 47-4 / FR-61) | Both | 47-1, 47-3 |
| 5 | Implement `Nowing` `to_chunks()` in scrapers/aggregators (FR-58) | Nowing | 47-1, AD-34 |
| 6 | Run integration test Story 47-IT1 | QA / both | 47-1..47-4 |
| 7 | Deprecate/remove Epic 13 code (tech-debt) | Nowing | FR-58 live |

---

## 4. Recommendation

**Planning is complete.** Both PRDs, architecture spines, epics, UX contracts, and interface schemas are aligned. The next step is **implementation**:
- Start with **Story 47-1** (`POST /v1/ingest/scraper`) in `chainlens-research` and **Nowing scraper `to_chunks()`** in parallel; these two are the critical path.
- Follow with **47-3** (`NowingPrivateProvider`) and **47-4** (service auth/cost).
- Run **47-IT1** integration test gate before merging to `develop`.
