# Architecture Review — Nowing + chainlens-research Ecosystem (v8, 2026-08-08)

**Reviewer:** Winston (System Architect)  
**Scope:** Both `nowing` and `chainlens-research` architecture spines, PRDs, epics, sprint-status, cross-project contracts, and architecture diagrams.  
**Status:** 🟡 **CONDITIONALLY READY FOR IMPLEMENTATION**

> **Note:** Reviews v6 and v7 (`architecture-review-nowing-chainlens-2026-08-08-v6.md` and `...-v7.md`) are **retired/superseded** by this v8 document. Use v8 as the current architecture readiness source of truth.

---

## 1. Executive Summary

A second, full re-review was performed. Two architecture diagrams were added to the ARCHITECTURE-SPINE files. The remaining Nowing-side ecosystem stories were captured in a new `Epic 20`. The architecture is **now consistent**, but implementation must follow a strict start order due to real dependencies.

| # | Finding | Resolution |
|---|---|---|
| 1 | Nowing had no stories for `to_chunks()`, `NowingIngestService`, gap-fill caller, `NowingPrivateProvider`, service auth | ✅ Added `Epic 20` with 4 stories (`20.1`–`20.4`) to `epics.md` and `sprint-status.yaml` |
| 2 | `MemoryInjectionMiddleware` unbounded (v6 AD-18) | ✅ Verified code uses `MemoryHybridSearch` with `top_k`; `Story 3.17` is a verification gate |
| 3 | `Memory` type mismatch (v6 AD-11.1) | ✅ Verified schema + writer + revalidate API; `Story 9.6c` is a verification gate |
| 4 | SurfSense attribution (v6 AD-16.1) | ✅ `NOTICE` file exists and is correct |
| 5 | Anti-bot screenshot escalation (AD-19) | 🟠 Open; `Story 10.5` created as P0 |
| 6 | chainlens-research `47-3` dependencies | 🟡 `47-3` (ingest endpoint) depends on `47-1` (Chunk schema) and `47-2` (service auth) — noted in `sprint-status.yaml` |
| 7 | Epic 13 deprecated code with P0 defects | 🟠 Still tracked as dropped; do not merge until cleaned |

---

## 2. Architecture Diagrams

- **Nowing:** `nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — `## Architecture Diagram` (Mermaid flowchart showing FastAPI monolith, memory, scrapers, chainlens-research SSE endpoints, gap-fill, private-data provider, billing, Redis, PostgreSQL/pgvector, S3).
- **chainlens-research:** `chainlens-research/_bmad-output/planning-artifacts/architecture/architecture-chainlens-research-2026-08-08/ARCHITECTURE-SPINE.md` — `## Architecture Diagram` (Mermaid flowchart showing OutputRouter, SearchPipeline, ResearchPipeline, Ingest Pipeline, Gap-Fill Job, Public Crawler, Nowing Scrapers, `NowingPrivateProvider`, Billing Ledger).

Both diagrams explicitly show the four cross-project contracts:

1. `POST /api/v1/search` SSE
2. `POST /v1/ingest/scraper`
3. `POST /v1/gap-fill`
4. `POST /v1/private-data/search`

---

## 3. Implementation Readiness Verdict

### 3.1 What is Ready

| Area | Evidence |
|---|---|
| Ecosystem boundary (who owns what index) | AD-1, AD-2, AD-3, AD-5, AD-6, AD-34, AD-35 — final in both spines |
| Cross-project interface contracts | PRD FR-58..FR-62; ARCHITECTURE-SPINE invariants; diagrams |
| Nowing-side work breakdown | `Epic 20` + `sprint-status.yaml` entries |
| chainlens-research-side work breakdown | `Epic 47` + `sprint-status.yaml` entries |
| Story 47-1 / Nowing `to_chunks()` dependency order | Documented in architecture readiness sections and `sprint-status.yaml` next steps |

### 3.2 What is NOT Ready

| # | Gap | Why it blocks | Owner |
|---|---|---|---|
| 1 | `Story 10.5` (AD-19 anti-bot screenshot) is open | Without it, HR/BĐS vertical anti-bot blocks cannot be audited | Nowing |
| 2 | `Story 47-1` (Chunk schema) must finish before `47-3` | `47-3` validates and stores `Chunk[]`; no schema means no validation | chainlens-research |
| 3 | `Story 47-2` (service auth) must finish before `47-3` | `47-3` is an internal endpoint; no auth guard means no trust boundary | chainlens-research |
| 4 | `Story 20.4` (Nowing service auth + cost ledger) must finish before `20.1`/`20.2`/`20.3` | Outbound calls and cost attribution need shared secret + `TokenUsage` mapping first | Nowing |

### 3.3 Recommended Start Order

**Phase 0 — Foundation (can run in parallel):**
- `47-1` (chainlens-research canonical `Chunk` schema + `source` enum) — no cross-project blocker.
- `47-2` (chainlens-research service auth + cost allocation) — trust boundary.
- `20.4` (Nowing service auth + cost ledger sync) — parallel with `47-2`; shared secret + `TokenUsage` mapping.

**Phase 1 — Ingest integration:**
- `47-3` (chainlens-research `POST /v1/ingest/scraper`) — **blocked until 47-1 and 47-2 done**.
- `20.1` (Nowing `to_chunks()` + `NowingIngestService`) — needs `47-1` (schema) and `20.4` (auth).

**Phase 2 — Gap-fill:**
- `47-4` (chainlens-research `POST /v1/gap-fill`) — after `47-3`.
- `20.2` (Nowing gap-fill caller) — after `47-4` + `20.1`.

**Phase 3 — Private data + hardening:**
- `47-5` (chainlens-research `NowingPrivateProvider`)
- `20.3` (Nowing private provider client) — after `47-5`.
- `47-IT1` (cross-project integration test gate) — after `47-1`..`47-5` and `20.1`..`20.4`.
- `3.17` and `9.6c` (verification gates)

**P0 parallel:**
- `10.5` (AD-19 anti-bot screenshot escalation) — should not block 47-1, but is required before HR/BĐS vertical pilot.

---

## 4. Final Recommendation

**Start implementation now on the foundation (`47-1`, `47-2`, `20.4`). Do NOT start `47-3` until Chunk schema (`47-1`) and service auth (`47-2`) are landed.** The architecture is aligned; the remaining work is implementation detail and one genuine P0 (AD-19 screenshot escalation).
