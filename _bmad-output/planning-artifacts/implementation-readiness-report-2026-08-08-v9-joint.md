# Joint Implementation Readiness Report — Nowing + chainlens-research

**Date:** 2026-08-08  
**Reviewer:** Implementation Readiness (PM)  
**Scope:** PRD, Architecture, Epics, Stories, UX, Sprint Status for both projects  
**Verdict:** 🟡 **CONDITIONAL — ready to start prerequisites, NOT ready for full Epic 47 dev until story files exist**

---

## Executive Summary

A full PM-style readiness re-check was run for both projects. The architecture alignment is correct, but the implementation layer has a critical gap: **Epic 47 stories in `chainlens-research` and Epic 20 stories in `Nowing` are marked `ready-for-dev` but have no dedicated story spec files.** This violates the BMAD convention that `ready-for-dev` means a story file exists. Other gaps are medium/low.

| Project | Status | Critical Blocker |
|---|---|---|
| **Nowing** | 🟡 Conditional | Missing AD-32, AD-33 stories; Epic 18 backlog; some Epic 12 ACs vague |
| **chainlens-research** | 🟡 Conditional | **Epic 47 has zero story files** despite 5 `ready-for-dev` entries |
| **Cross-project** | 🟡 Conditional | Ecosystem FRs/ADs covered in epics but lack detailed specs |

---

## 1. Nowing — Findings

### 1.1 FRs → Stories Traceability

| FR | Title | Coverage | Verdict |
|---|---|---|---|
| FR-56 | Public Agent-Chat API for Vertical Clients | Epic 18 stories 18.1–18.8 (`backlog`) | ⚠️ No story files |
| FR-57 | Agent Registry | Epic 18 stories 18.1–18.8 (`backlog`) | ⚠️ No story files |
| FR-58 | Scraper Feed to chainlens-research | **Epic 20.1** (`ready-for-dev`) | ✅ Covered |
| FR-59 | Gap-Fill Trigger | **Epic 20.2** (`ready-for-dev`) | ✅ Covered |
| FR-60 | Private Data Provider | **Epic 20.3** (`ready-for-dev`) | ✅ Covered |
| FR-61 | Cross-Project Service Auth & Cost Allocation | **Epic 20.4** (`ready-for-dev`) | ✅ Covered |
| FR-62 | Canonical Chunk Metadata Schema | **Epic 20.1** AC includes metadata fields | ⚠️ Partial; chainlens 47-5 owns strict schema |

**Note:** Earlier subagent flagged FR-59, FR-60, FR-62 as missing because it did not cross-reference the newly-added `Epic 20` stories. They are covered.

### 1.2 ADs → Stories Traceability

| AD | Title | Coverage | Verdict |
|---|---|---|---|
| AD-29–31 | Vertical Client Platform | Epic 18 (`backlog`, no story files) | ⚠️ High gap |
| AD-32 | Connector management: dedicated page | Story 7-4 pass 3 / deferred in 7-4-review | ⚠️ Track in 7-4-followup or new story |
| AD-33 | Generic Alert Engine | Epic 12 stories 12-6..12-9 | ✅ Convention; stories exist in epics |
| AD-34 | Nowing Scraper Feed Contract | **Epic 20.1** | ✅ Covered |
| AD-35 | No public/vertical search corpus in Nowing | **Epic 20.1/20.2/10.4** ACs | ✅ Covered |

### 1.3 Stories with Vague/Missing ACs

| Story | Issue |
|---|---|
| `12-2` TopCV Scraper | ACs too brief; missing pagination, rate-limit, PII, error-mode details |
| `12-3` ITviec Scraper | Story file not reviewed |
| `12-4` `vn_jobs.aggregate` | Story file not reviewed |
| `12-5` PII Redaction | Story file not reviewed |
| `18.1`–`18.8` | No story files; only high-level epics |

### 1.4 Sprint-Status vs Epics Consistency

| Check | Result |
|---|---|
| Epic 1–9, 12, 20 | Consistent ✅ |
| Epic 18 | `epic-18` not in `sprint-status.yaml`? Need verify. Currently stories in `backlog`. |
| Tech-debt items `td-1..td-7` | Exist in `sprint-status.yaml` but not in `epics.md` — acceptable for tech debt, but should be in `deferred-work.md` |
| `3-17`, `9-6c`, `10-5`, `20-1..20-4` | Added and aligned ✅ |

---

## 2. chainlens-research — Findings

### 2.1 FRs → Stories Traceability

| FR | Title | Epic | Story | Verdict |
|---|---|---|---|---|
| FR-32 | Scraper Feed Ingest | Epic 47 | `47-1` | ⚠️ No story file |
| FR-33 | Gap-Fill Indexing | Epic 47 | `47-2` | ⚠️ No story file |
| FR-34 | Private Data Provider | Epic 47 | `47-3` | ⚠️ No story file |
| FR-35 | Service Auth & Cost Allocation | Epic 47 | `47-4` | ⚠️ No story file |
| FR-36 | Canonical Chunk Schema | Epic 47 | `47-5` | ⚠️ No story file |
| FR-58-62 (Nowing ecosystem FRs) | N/A in chainlens PRD | N/A | N/A | ✅ Not in scope; covered by Nowing Epic 20 |

### 2.2 ADs → Stories Traceability

| AD | Title | Story | Verdict |
|---|---|---|---|
| AD-1 | Single canonical index | 47-1, 47-6 | ⚠️ 47-6 deferred; 47-1 no file |
| AD-2 | Public web crawling in chainlens | 47-6 | ⚠️ Deferred |
| AD-3 | Nowing scrapers feed index | 47-1 | ⚠️ No file |
| AD-4 | Nowing triggers gap-fill | 47-2 | ⚠️ No file |
| AD-5 | Private data not pre-indexed | 47-3 | ⚠️ No file |
| AD-6 | No duplicate indexing in Nowing | 47-1 | ⚠️ No file |
| AD-7 | Search contract `POST /api/v1/search` SSE | `42-2` done | ✅ Complete |

### 2.3 Epic 47 Story File Status (Critical)

| Story | sprint-status | Story file exists? |
|---|---|---|
| `47-1-scraper-feed-ingest` | `ready-for-dev` | ❌ NO |
| `47-2-gap-fill-indexing` | `ready-for-dev` | ❌ NO |
| `47-3-private-data-provider` | `ready-for-dev` | ❌ NO |
| `47-4-service-auth-cost-allocation` | `ready-for-dev` | ❌ NO |
| `47-5-chunk-metadata-schema` | `ready-for-dev` | ❌ NO |

This is a **P0 readiness blocker**. `ready-for-dev` means a story file exists.

### 2.4 Sprint-Status vs Epics Consistency

| Check | Result |
|---|---|
| Epic 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43 | Consistent ✅ |
| Epic 47 | Added `epic-47` entry ✅ |
| Epic 12, 15 | Added `epic-12` and `epic-15` entries ✅ |
| 47-1..47-5 status | `ready-for-dev` but no files — downgraded to `backlog` or files needed |

---

## 3. UX Contract Alignment

| Contract | Project | Status | Linked |
|---|---|---|---|
| `ux-contract-canonical-entity.md` | Nowing | DEPRECATED | ✅ Correct |
| `ux-contract-ecosystem-search.md` | Nowing | Active | Epic 47 (chainlens) |
| `ux-contract-private-data-provider.md` | Nowing | Active | Epic 20.3 |
| `ux-contract-agent-registry.md` | Nowing | Active | Epic 18 |
| `ux-developer-dashboard-...` | chainlens | Active | Epic 39 done |

---

## 4. Top Readiness Blockers (Cross-Project)

### #1 — Epic 47 (chainlens) has zero story files  🔴 CRITICAL
- **Impact:** `47-1` cannot start; `47-5` and `47-4` have no spec.
- **Action:** Run `bmad-create-story` for `47-1`–`47-5` (or create manually).

### #2 — Nowing Epic 18 has no story files  🟠 HIGH
- **Impact:** FR-56, FR-57, AD-29/30/31 accepted but no implementation path.
- **Action:** Create `18.1`–`18.8` story files or explicitly defer with an SCP.

### #3 — Nowing Epic 12 story ACs are too brief  🟡 MEDIUM
- **Impact:** Quality risk for HR vertical pilot.
- **Action:** Expand `12-2..12-5` ACs with pagination, rate-limit, error, PII detail.

### #4 — AD-32 (connector page) lacks explicit story  🟡 MEDIUM
- **Impact:** Connector management UX may diverge again.
- **Action:** Add to `7-4-followup` or create `7-4c` story.

### #5 — Nowing FR-62 coverage is split with chainlens  🟡 MEDIUM
- **Impact:** Who owns strict `Chunk` schema validation is clear (chainlens 47-5), but Nowing `to_chunks()` AC should reference the canonical schema contract.
- **Action:** Add a cross-reference in `20.1` to `47-5`.

---

## 5. Recommended Start Order (Phase 4)

**Recommended Phase 4 start order:**

1. **`47-1` (chainlens canonical `Chunk` schema + `source` enum)** — foundation.
2. **`47-2` (chainlens service auth + cost allocation)** — trust boundary.
3. **`20.4` (Nowing service auth + cost ledger)** — parallel with `47-2`.
4. **`47-3` (chainlens `POST /v1/ingest/scraper`)** + **`20.1` (Nowing `to_chunks()` + `NowingIngestService`)** — parallel; `20.1` depends on `47-1` and `20.4`.
5. Then **`47-4` (chainlens gap-fill)** + **`20.2` (Nowing gap-fill caller)**.
6. Then **`47-5` (chainlens `NowingPrivateProvider`)** + **`20.3` (Nowing private provider client)**, **`47-IT1`**.

---

## 6. Verdict & Next Steps

**Verdict:** 🟡 **CONDITIONAL**

- Architecture is ready.
- PRD and epics are aligned for the ecosystem integration.
- **The only P0 blocker is the absence of story spec files for `47-1`–`47-5` and (to a lesser extent) Epic 20/18.**

**Next steps to reach READY:**
1. Create `47-1`–`47-5` story files in `chainlens-research/_bmad-output/implementation-artifacts/stories/`.
2. Create `20-1`–`20-4` story files in `nowing/_bmad-output/implementation-artifacts/stories/`.
3. Decide whether to defer Epic 18 or create story files.
4. Expand `12-2`–`12-5` acceptance criteria.
5. Re-run readiness check.
