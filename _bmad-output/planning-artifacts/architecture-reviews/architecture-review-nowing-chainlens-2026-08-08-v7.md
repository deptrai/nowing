# Architecture Review — Nowing + chainlens-research Ecosystem (v7, 2026-08-08)

**Reviewer:** Winston (System Architect)  
**Scope:** Both `nowing` and `chainlens-research` architecture spines, PRDs, epics, sprint-status, and cross-project contracts.  
**Status:** 🟢 **APPROVED WITH CONDITIONS — cross-project architecture is aligned; one genuine P0 (AD-19 screenshot anti-bot) and two verification gaps remain.**

> **⚠️ SUPERSEDED:** This review is superseded by `architecture-review-nowing-chainlens-2026-08-08-v8.md`. Retained for history only; do not use for implementation decisions.

---

## 1. Executive Summary

Cross-project architecture is **directionally correct** and the ecosystem boundary is now clear. The 3 P0 Nowing findings from v6 were **re-checked against live code** and **2 of 3 are already implemented**. One architecture-level concern and two verification gaps remain.

| # | v6 Finding | Code Check Result | New Status |
|---|---|---|---|
| 1 | Unbounded memory injection (AD-18) | `MemoryInjectionMiddleware` uses `MemoryHybridSearch.search(top_k=...)` — bounded, uses HNSW/GIN indexes. | ✅ Resolved |
| 2 | `Memory.source_id` type mismatch (AD-11.1) | `Memory` has `source_run_id` UUID + `source_capability` + `source_input`; `RunMemoryExtractionService` writes recipe; `revalidate` API exists (9-6a/9-6b done). | ✅ Resolved |
| 3 | SurfSense attribution (AD-16.1) | `NOTICE` file exists and correctly attributes SurfSense; `app/capabilities/core/validation.py` still references SurfSense in attribution. | ✅ Resolved |
| 4 | Anti-bot screenshot escalation (AD-19) | Not yet found in code. | 🟡 Open |
| 5 | chainlens FR numbering mismatch | Fixed in `epics.md` and `ARCHITECTURE-SPINE.md` v6. | ✅ Resolved |
| 6 | chainlens Epic 42 / Epic 47 overlap | Needs disambiguation note. | 🟡 Minor |
| 7 | Epic 13 deprecated code with P0 defects | Still tracked in tech-debt; no new action. | 🟡 Watch |

---

## 2. Nowing Findings (Updated)

### 2.1 Already Implemented / Verified

#### AD-18 — Memory injection is bounded
- **Code:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/memory/middleware.py` — `MemoryInjectionMiddleware.abefore_agent` calls `MemoryHybridSearch.search(..., top_k=_MEMORY_INJECTION_TOP_K)`.
- **Schema:** `memories` table has `ix_memories_embedding` (HNSW) and `ix_memories_content_search` (GIN).
- **Conclusion:** Rule 1 of AD-18 is satisfied; O(top-k) retrieval, not O(N).

#### AD-11.1 — Memory provenance is implemented
- **Code:** `nowing_backend/app/db.py:2225-2230` — `Memory` has `source_run_id` (UUID), `source_capability` (String), `source_input` (JSONB).
- **Story 9-6a** (done) adds the schema and `RunMemoryExtractionService` copies recipe.
- **Story 9-6b** (done) adds `POST /workspaces/{id}/memories/{memory_id}/revalidate` API.
- **Conclusion:** Provenance and re-validation are implemented.

#### AD-16.1 — License attribution is in place
- **File:** `NOTICE` at repo root lists SurfSense provenance, fork commit, and license split (Apache-2.0 core / BSL 1.1 proprietary).
- **Code:** `nowing_backend/app/capabilities/core/validation.py:3` still references SurfSense.
- **Conclusion:** Attribution is sufficient for public repo; legal review already captured in `_bmad-output/planning-artifacts/legal/`.

### 2.2 Still Open

#### AD-19 — Anti-bot / CAPTCHA escalation not found
- **Architecture rule:** async screenshot + Inbox item when anti-bot/CAPTCHA blocks a scraper.
- **Code check:** No screenshot-as-evidence pipeline found.
- **Risk:** TopCV/Batdongsan anti-bot failures cannot be audited or escalated.
- **Action:** Create story `10.x` or `2.x` for screenshot + Inbox escalation.

#### Epic 13 — Deprecated code still has open P0 defects
- **Status:** `sprint-status.yaml` marks 13.1-13.3 as `dropped`; validation reports requested P0 fixes.
- **Risk:** Deprecated code may be merged with defects.
- **Action:** Keep in `deferred-work.md`; do not merge until fixed or fully removed.

---

## 3. chainlens-research Findings (Updated)

- **FR numbering:** `epics.md` and `ARCHITECTURE-SPINE.md` updated to FR1..FR36 + external Nowing FRs.
- **Epic 47 binding:** Added to architecture spine binds.
- **Sprint status:** Epic 47 stories `47-1..47-6`, `47-IT1` added to `sprint-status.yaml`.
- **Epic 42 / Epic 47 overlap:** Add disambiguation note in both epics.

---

## 4. Remaining Work Before Implementation

| # | Work | Owner | Severity |
|---|---|---|---|
| 1 | Verify AD-18 with perf test at N=10k memories — `Story 3.17` created | Nowing | P1 (verification gate) |
| 2 | Verify AD-11.1 with E2E revalidate after simulated 30-day run cleanup — `Story 9.6c` created | Nowing | P1 (verification gate) |
| 3 | Implement AD-19 anti-bot screenshot escalation — `Story 10.5` created | Nowing | P0 |
| 4 | Disambiguate Epic 42 vs Epic 47 in epics.md | chainlens-research | P2 |
| 5 | Resolve Epic 13 tech-debt | Nowing | P2 |

---

## 5. Recommendation

**The 3 originally-requested P0 stories are already implemented.** Instead of re-implementing them, create **verification/close-out stories** for AD-18 and AD-11.1 and one **implementation story** for AD-19. Then proceed with Story 47-1 and Nowing `to_chunks()`.
