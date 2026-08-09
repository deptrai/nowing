# Architecture Review — Nowing + chainlens-research Ecosystem (v6, 2026-08-08)

**Reviewer:** Winston (System Architect)  
**Scope:** Both `nowing` and `chainlens-research` architecture spines, PRDs, epics, sprint-status, and cross-project contracts.  
**Status:** 🟡 **APPROVED WITH REMEDIATIONS — 5 critical findings must be fixed before implementation proceeds.**

> **⚠️ SUPERSEDED:** This review is superseded by `architecture-review-nowing-chainlens-2026-08-08-v8.md`. Retained for history only; do not use for implementation decisions.

---

## 1. Executive Summary

Cross-project architecture is **directionally correct** and the ecosystem boundary is now clear. However, several **P0-level issues** surfaced during review:

1. **Nowing has an unbounded memory injection path** that violates AD-18 and will degrade as users accumulate memories.
2. **Nowing `Memory.source_id` type mismatch** breaks AD-11.1 provenance/re-validation.
3. **Nowing is a 99.84% SurfSense fork** with unresolved Apache-2.0 §4 attribution — blocks public repo.
4. **Chainlens PRD and epics disagree on FR numbering** (FR1..FR36 vs FR1..FR51).
5. **Chainlens Epic 42 and Epic 47 overlap in narrative** and should be explicitly disambiguated.

These are architecture-level, not implementation. They should be resolved before Story 47-1 / Nowing `to_chunks()` dev starts.

---

## 2. Nowing Findings

### 2.1 AD Status & Numbering

- **35 active ADs** (AD-1..AD-35). AD-27/28 re-scoped, AD-34/35 new, AD-32/33 already used by connector/alert engine.
- **No numbering collisions** after AD-32/33 -> AD-34/35 fix.
- **Stale binding in AD-3**: still references `FR-24` in binds, but FR-24 was moved to Epic 9 / AD-15. **Action:** clean AD-3 binds.

### 2.2 Critical Architecture Defects

#### CRITICAL-1 — AD-18 rule 1 is violated in code
- **AD-18** says memory recall must be bounded top-k via HNSW/GIN.
- **Code fact:** `MemoryInjectionMiddleware` (or equivalent path) runs `SELECT * FROM memories WHERE workspace_id = ?` without `LIMIT` and then re-ranks in Python.
- **Risk:** Latency grows linearly with memory count; violates NFR-1b/1c/1d silently.
- **Action:** Enforce `LIMIT` at DB query; use HNSW/GIN before Python re-rank; add a failing perf test.

#### CRITICAL-2 — AD-11.1 provenance cannot work
- **AD-11.1** requires `Memory` to keep capability + input + run reference so it can re-validate facts.
- **Code fact:** `Memory.source_id` is `Integer` but `Run.id` is `UUID`; no code writes `MemorySourceType.SCRAPER_RUN`.
- **Risk:** FR-39 (provenance / re-validate) cannot be implemented.
- **Action:** Change `Memory.source_id` to `UUID` or add `source_run_id` UUID column; implement writer in scraper→memory path.

#### CRITICAL-3 — AD-19 anti-bot escalation path not implemented
- **AD-19** requires async screenshot + human-in-the-loop escalation for anti-bot failures.
- **Code fact:** `grep screenshot app/**/*.py` = 0 hits; no screenshot-as-evidence pipeline.
- **Risk:** TopCV/Batdongsan anti-bot failures cannot be audited or escalated.
- **Action:** Build screenshot capture + Inbox item type; wire to scraper failure path.

### 2.3 License / Fork Risk

- **AD-16.1** states Nowing is 99.84% SurfSense fork (73/84 files byte-identical in `app/proprietary/`).
- **PRD §1.1** markets BSL crawler engine as self-built moat.
- **Apache-2.0 §4** requires attribution; current copyright headers say "Nowing" without SurfSense notice.
- **Risk:** Public repo launch is legally blocked. OSS/PLG strategy at risk.
- **Action:** Get legal brief `_bmad-output/planning-artifacts/legal/legal-brief-upstream-attribution-2026-07-26.md` resolved; add `NOTICE` file and correct headers.

### 2.4 Epic 13 Re-scope Inconsistency

- **Epic 13** marked `[REMOVED 2026-08-08]` in `epics.md` and `sprint-status.yaml`.
- **But** `sprint-status.yaml` still lists 13.1, 13.2a-e, 13.3 in `dropped` state, and validation reports show P0 code-review findings against them.
- **Risk:** Deprecated code with P0 defects may be merged to `develop` and used accidentally.
- **Action:** Add `DEPRECATED` runtime guard; schedule tech-debt cleanup; do not merge 13.x code until defects fixed or feature flags disable it.

---

## 3. chainlens-research Findings

### 3.1 AD Status & Numbering

- **7 active ADs** (AD-1..AD-7), all final. They correctly establish chainlens as canonical index owner.
- **FR numbering mismatch:** `epics.md` says `prd.md` defines **FR1..FR51**; actual `prd.md` has **FR-1..FR-36** after ecosystem update.
- **Action:** Fixed `epics.md` to say FR1..FR36 + note Nowing ecosystem FRs.

### 3.2 Bindings Fixed During Review

- **Architecture spine** originally lacked binding to Epic 47.
- **Fixed:** Added `Epic 47: chainlens-research + Nowing Ecosystem Integration` to binds.
- **External FR binding** `FR-58..FR-62` was ambiguous (Nowing FRs).
- **Fixed:** Relabeled to `Nowing AD-34` and `Nowing AD-35` and removed numeric FR bind to avoid confusion.

### 3.3 Epic Overlap

- **Epic 42** = Nowing public `/api/v1/search` SSE contract (v4).
- **Epic 47** = Ecosystem integration with internal endpoints (`/v1/ingest/scraper`, `/v1/gap-fill`, `/v1/private-data/search`).
- **Risk:** Name overlap can confuse teams.
- **Action:** Add a note in both epics: Epic 42 governs the single public contract; Epic 47 governs the new internal ecosystem surface.

### 3.4 Sprint Status Verified

- **Epic 47 stories** `47-1..47-6` and `47-IT1` added to `sprint-status.yaml` during this review.
- **No code implementation exists yet** for any P0 ecosystem surface.

---

## 4. Cross-Project Consistency

| Contract | Nowing | chainlens-research | Verdict |
|---|---|---|---|
| `POST /v1/ingest/scraper` | FR-58, AD-34 | FR-32, AD-3 | ✅ Aligned |
| `POST /v1/gap-fill` | FR-59, AD-28 | FR-33, AD-4 | ✅ Aligned |
| `POST /v1/private-data/search` | FR-60, AD-35 | FR-34, AD-5 | ✅ Aligned |
| Service auth / cost | FR-61 | FR-35 | ✅ Aligned |
| `Chunk.metadata` + `source` enum | FR-62, AD-34 | FR-36, AD-3 | ✅ Aligned |
| `source` enum values | `public_crawl`, `nowing_scraper`, `brave`, `searxng`, `jina`, `exa`, `tavily`, `perplexity`, `private_provider` | Same | ✅ Aligned |

**One inconsistency fixed:** `Nowing` PRD originally said `web_crawl`; now matches `chainlens-research` `public_crawl`.

---

## 5. Top 5 Architecture Risks

| # | Risk | Severity | Owner | Mitigation |
|---|---|---|---|---|
| 1 | **Nowing unbounded memory injection** violates AD-18/NFR-1 | P0 | Nowing | Enforce DB LIMIT + HNSW/GIN; perf test |
| 2 | **Nowing `Memory` provenance type mismatch** breaks AD-11.1/FR-39 | P0 | Nowing | Migrate `source_id` to UUID; add writer |
| 3 | **SurfSense fork attribution** blocks public repo (AD-16.1) | P0 | Legal / Nowing | Resolve legal brief; add `NOTICE`/headers |
| 4 | **Epic 13 deprecated code has P0 defects** | P1 | Nowing | Fix or disable before `develop` merge |
| 5 | **chainlens-research Epic 42/47 narrative overlap** | P2 | chainlens-research | Disambiguate in epics |

---

## 6. Recommendation

**Do not start Story 47-1 / Nowing `to_chunks()` until the 3 P0 Nowing findings are at least planned with story owners.** The rest can proceed in parallel.

**Priority order:**
1. **Nowing:** Create story for AD-18 bounded memory injection fix.
2. **Nowing:** Create story for AD-11.1 provenance type fix.
3. **Legal/Nowing:** Resolve AD-16.1 attribution (unblocks public repo).
4. **Both:** Start Story 47-1 + `to_chunks()` in parallel.
5. **chainlens-research:** Add disambiguation note to Epic 42 / Epic 47.
