# Implementation Readiness Assessment — Epic 10 Chợ Tốt Multi-Category Scraper

**Date:** 2026-08-11
**Project:** Nowing
**Scope:** Epic 10 story 10.6 + 10.7 (Chợ Tốt multi-category expansion)
**Assessor:** Product / Architecture

---

## 1. Document Inventory

| Document | Status | Notes |
|---|---|---|
| PRD (`_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`) | ✅ exists | FR-6 (scraper expansion) covers this scope. |
| Architecture Spine (`_bmad-output/planning-artifacts/architecture/.../ARCHITECTURE-SPINE.md`) | ✅ exists | AD-3, AD-16, AD-19, AD-34/35, AD-25/26 relevant. |
| Epic 10 (`_bmad-output/planning-artifacts/epics.md` §Epic 10) | ✅ updated | Stories 10.6, 10.7 in scope. |
| Story 10.6 (`_bmad-output/implementation-artifacts/stories/10-6-chotot-multi-category-scraper.md`) | ✅ exists, ready-for-dev | |
| Story 10.7 (`_bmad-output/implementation-artifacts/stories/10-7-chotot-multi-category-capability.md`) | ✅ exists, ready-for-dev | |
| UX contract | ⚠️ none | Not required for backend scraper; capability surface is JSON/MCP. |

## 2. Requirement Traceability

| Requirement | Covered by | Assessment |
|---|---|---|
| FR-6 — scraper expansion | Epic 10, 10.6, 10.7 | ✅ fully covered |
| FR-30 — token tracking / billing | 10.7 | ✅ covered with `CHOTOT_ITEM` |
| FR-32 — memory/ingest (optional feed to ChainLens) | 10.6 (AD-34/35 note) | ⚠️ not explicitly wired; marked optional via `NowingIngestService` |
| NFR-4 — reliability / degradation | 10.6 AC #11, 10.7 AC #3/#4 | ✅ covered |
| NFR-11 — ToS / anti-bot / PII | 10.6 Dev Notes | ⚠️ high-level only; per-vertical ToS not yet verified |

## 3. Architecture Alignment

| AD | Alignment | Gap |
|---|---|---|
| AD-3 (capability self-register) | ✅ 10.7 registers `chotot.scrape` + deprecated `chotot_bds.scrape` | None |
| AD-16 (license boundary) | ✅ mapping/parser in `app/proprietary/`, capability in `app/capabilities/` | None |
| AD-19 (anti-bot) | ✅ reuses existing errors/escalation | None |
| AD-34/35 (scraper feed contract, no owned corpus) | ✅ output is listing, not Memory corpus | None |
| AD-25/26 (PII redaction, ToS gate) | ⚠️ mentioned as downstream concern | No explicit per-vertical ToS review task |

## 4. Story Quality

### Story 10.6 — Chợ Tốt Multi-Category Scraper

**Strengths:**
- ACs cover mapping, schema, parsers, unknown category, phone, detail URL.
- Includes a **spike** to discover `cg`/`st`/region/detail URL/phone — de-risks unknowns.
- Keeps existing anti-bot/phone helpers; reuse-focused.
- `ChototListing` generic with `attributes` bag is scalable.

**Gaps / Risks:**
1. **Unknown `st` semantics** is the biggest pre-implementation risk. If `st` differs by vertical, the fetcher may return wrong listings or empty.
2. **Detail URL pattern** — `/{list_id}.htm` may not work for all subdomains. Spike must confirm.
3. **Parser field names** (`make`, `model`, `salary_min`, etc.) are guesses until raw JSON is inspected.
4. **`ChototBdsListing` deprecation** — needs explicit migration path and test fixes.
5. **No performance / rate-limit AC** beyond existing patterns.

### Story 10.7 — Multi-Category Capability and Billing

**Strengths:**
- Single `chotot.scrape` + deprecated alias is the right architecture (boring, less churn).
- Generic `CHOTOT_ITEM` billing avoids enum explosion.
- ACs cover backward compatibility, pre-flight gate, degraded/unknown no-bill.

**Gaps / Risks:**
1. **No architecture decision record (AD note)** for capability/billing shape — task exists but must be completed before or during implementation.
2. **Existing `CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM` config** — story should decide whether to keep as alias or migrate to `CHOTOT_SCRAPE_MICROS_PER_ITEM`.
3. **`call_details["category"]` for cost analytics** is a good idea but not yet supported in `TokenUsage` schema; verify `record_token_usage` accepts arbitrary `call_details`.
4. **MCP/REST capability selfcheck list** — story mentions but not yet located.

## 5. Dependencies

| Dependency | Status | Impact |
|---|---|---|
| Existing `AsyncFetcher` + proxy rotation | ✅ ready | No new fetcher code |
| Existing `ChototBdsScraper` / `fetch.py` | ✅ ready | Refactor in place |
| `BillingUnit` enum + `billing.py` | ⚠️ needs update | Add `CHOTOT_ITEM`, config |
| `app/config/__init__.py` | ⚠️ needs update | Add `CHOTOT_SCRAPE_MICROS_PER_ITEM` |
| `NowingIngestService` / ChainLens (optional) | ✅ ready | Only if later ingest |
| Live Chợ Tốt gateway for spike | ⚠️ not yet run | Blocking 10.6 implementation start |

## 6. Implementation Order

1. **Spike (1–2h):** confirm `cg`/`st`/detail URL/region/phone for P0 verticals.
2. **Record AD note** for `chotot.scrape` capability and billing.
3. **Story 10.6:** mapping + schema + parser + tests.
4. **Story 10.7:** capability + billing + deprecated alias + tests.
5. **Regression:** `chotot_bds.scrape` still works.

## 7. Go / No-Go Verdict

**Verdict: Conditional GO**

**Conditions to start Story 10.6:**
- [ ] Run spike and confirm `cg`/`st`/`w=1` for at least vehicles + electronics + jobs.
- [ ] Confirm `loadRegions` works for non-BĐS categories or identify exception.
- [ ] Record AD note for capability shape (Option A) and billing generic unit.
- [ ] Confirm ToS/legal allows scraping for vehicles/electronics/jobs verticals (`AD-26`).

**Conditions to start Story 10.7:**
- [ ] Story 10.6 merged.
- [ ] `BillingUnit.CHOTOT_ITEM` and `CHOTOT_SCRAPE_MICROS_PER_ITEM` config added.
