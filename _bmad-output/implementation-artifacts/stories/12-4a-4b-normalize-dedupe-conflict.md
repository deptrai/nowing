---
title: Story 12.4a+4b — Vietnam Job Normalization, Dedupe & Conflict Detection
epic: 12
story: 4a-4b
status: pending-human-review
priority: P0
baseline_commit: e0ed91f21
---

# Story 12.4a+4b — Vietnam Job Normalization, Dedupe & Conflict Detection

**Epic:** 12 — HR/Recruitment Vertical — Vietnam Job Market Pilot
**As a:** research analyst
**I want:** Vietnamese job market data from multiple sources normalized, deduplicated, and conflict-scored
**So that:** downstream ingest and the chat agent can work on a single trustworthy shape.

Covers epics.md stories **12.4a** (normalization) + **12.4b** (dedupe/confidence/conflict). These two are tightly coupled — normalize feeds dedupe — and share the same code files.

---

## Acceptance Criteria

### From 12.4a — Normalization

1. **Given** a query and optional filters (`location`, `salaryMin/Max`, `employmentType`, `experienceYears`), **When** `vn_jobs.aggregate` is called, **Then** it fan-outs to `vietnamworks.scrape`, `topcv.scrape`, `itviec.scrape` (default all 3; source list configurable; `maxItemsPerSource` and `maxPages` caps enforced per source).
2. **Given** results from multiple sources, **When** normalized, **Then** they map to `VnJobAggregatedListing` with `salary`, `location`, `employment_type`, `experience`, `posted_at`, and `source` fields.
3. **Given** a source fails or is blocked by anti-bot, **When** aggregation completes, **Then** it returns `degraded=true` with `degradation_reasons` drawn from `{SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}` and `degraded_source_ids`; successful source listings are still normalized.

### From 12.4b — Dedupe / Confidence / Conflict

4. **Given** normalized listings, **When** deduplicated, **Then** it matches by `company` + `title` + `location` + `posted_at` (±3 days) across sources; fuzzy title matching uses Jaro-Winkler ≥ 0.85 and location normalization uses `app/services/location_normalize/`.
5. **Given** two listings matched with salary difference ≤ 10%, **When** compared, **Then** `confidence_score ≥ 0.8` and `salary_consistency_score = stable`; the aggregated record is kept as a single record with `metadata.source_count` and `metadata.confidence_score`.
6. **Given** two listings matched with salary difference > 20% or a location mismatch, **When** compared, **Then** it sets `conflict_flag = SALARY_MISMATCH` or `LOCATION_MISMATCH`, lowers `confidence_score` to 0.5–0.7, and preserves both source records so `chainlens-research` can display conflict metadata.

---

## [BUILT] — DO NOT re-implement

- **Orchestrator** — `app/services/jobs_aggregator/orchestrator.py` (342 lines): `aggregate_jobs` fan-out → normalize → PII redact → dedupe → score → location filter → canonical persist. 8 unit tests passing.
- **Normalize** — `app/services/jobs_aggregator/normalize.py` (181 lines): `normalize_listing` maps raw → `VnJobAggregatedListing`. Salary parsing, post-date parsing (ISO + Vietnamese relative), location, source-record-id derivation.
- **Dedupe (basic)** — `app/services/jobs_aggregator/dedupe.py` (177 lines): `deduplicate` groups by `_canonical_key` (company + title + location + posted_at), merges salary/skills/urls/provenance, sets `source = "multiple"`.
- **Conflict detection (basic)** — `dedupe.py:46-84` (`_detect_conflict`): returns `(bool, float)` based on salary spread > 30% and location count > 1.
- **Schemas** — `app/services/jobs_aggregator/schemas.py` (96 lines): `VnJobAggregatedListing` (20 fields + 2 PrivateAttrs), `VnJobAggregateInput`, `VnJobAggregateOutput`.
- **PII redaction wired** — `orchestrator.py:33-42` (`_redact_listing`): runs `redact_job_pii` before dedupe.
- **Canonical persistence** — `orchestrator.py:185-266`: upserts to `canonical_entity` + source provenance + outbox on failure.
- **Unit tests** — `tests/unit/services/jobs_aggregator/`: `test_normalize.py` (1), `test_dedupe.py` (1), `test_orchestrator.py` (2). All passing.

## [GAP] — still to build

### Normalization gaps (AC-1, AC-2, AC-3)

1. **`experience_years` not normalized.** `normalize_listing` reads `raw.get("experience_years")` but scrapers don't populate it consistently. Need `_normalize_experience()` to parse text → int.
2. **Location normalization is trivial.** `normalize.py:109-113` just does `str(raw).strip()`. No diacritics normalization, no alias mapping ("HN" → "Hà Nội"). Aggregator-level filter (`orchestrator.py:318-324`) does exact lowercase match — misses "Hà Nội" vs "Ha Noi".
3. **`degraded_source_ids` not populated.** AC-3 requires it. `VnJobAggregateOutput` has `degradation_reasons` but no `degraded_source_ids` field.
4. **`degradation_reasons` format doesn't match AC enum.** AC says `{SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}`. Current code passes raw strings from source capabilities. Need to map to canonical enum.

### Dedupe gaps (AC-4, AC-5, AC-6)

5. **No fuzzy title matching.** `_canonical_key` uses exact `title.lower().strip()`. "Senior Data Engineer" vs "Data Engineer (Senior)" won't dedupe. AC-4 requires Jaro-Winkler ≥ 0.85.
6. **No `posted_at` ±3 days tolerance.** Exact date match only. AC-4 requires ±3 days window.
7. **`app/services/location_normalize/` does NOT exist.** AC-4 references it. Either build it or reuse BĐS aggregator pattern.
8. **No `conflict_flag` enum.** AC-6 requires `SALARY_MISMATCH` / `LOCATION_MISMATCH`. Current `_detect_conflict` returns `(bool, float)` only. Need `conflict_flags: list[str]` on `VnJobAggregatedListing`.
9. **No `source_count` on listing.** AC-5 requires `metadata.source_count`. `ChunkMetadata` has the field but `VnJobAggregatedListing` doesn't populate it. Add `source_count: int = 1`, set to `len(group)` during merge.
10. **Salary threshold mismatch.** AC-5 says ≤10% → stable, AC-6 says >20% → conflict. Current code uses 30% threshold. Align to 10%/20%.
11. **Both source records not preserved on conflict.** AC-6 says "preserves both source records". Current dedupe always returns one merged record. Need to return both when conflict detected.

---

## Tasks / Subtasks

- [x] AC-1: Verify fan-out + caps (AC: #1)
  - [x] Fan-out loop + `sources` param default
  - [x] Verify `maxItemsPerSource` enforced per source
- [x] AC-2: Normalize all fields (AC: #2)
  - [x] `salary`, `location`, `employment_type`, `posted_at`, `source`
  - [x] Add `_normalize_experience()` (text → int)
  - [x] Add Vietnamese location alias mapping
- [x] AC-3: Degradation tracking (AC: #3)
  - [x] Add `degraded_source_ids: list[str]` to `VnJobAggregateOutput`
  - [x] Map raw reasons to `{SOURCE_FAILED, ANTI_BOT, RATE_LIMIT, PARTIAL_DATA}`
- [x] AC-4: Fuzzy dedupe (AC: #4)
  - [x] Check `pyproject.toml` for `jellyfish`/`rapidfuzz`; add `rapidfuzz` if missing
  - [x] Replace exact title match with Jaro-Winkler ≥ 0.85
  - [x] Add ±3 days tolerance on `posted_at`
  - [x] Build or import location normalization
- [x] AC-5: Salary consistency + `source_count` (AC: #5)
  - [x] Add `source_count: int = 1` to `VnJobAggregatedListing`, set `len(group)` on merge
  - [x] Align salary threshold: ≤10% → `confidence_score ≥ 0.8`
- [x] AC-6: Conflict flags + preserve both records (AC: #6)
  - [x] Add `conflict_flags: list[str]` to listing (values: `SALARY_MISMATCH`, `LOCATION_MISMATCH`)
  - [x] Update `_detect_conflict` to return flag list
  - [x] Lower `confidence_score` to 0.5–0.7 on conflict
  - [x] Preserve both source records on conflict (via `_source_record_ids` PrivateAttr)

---

## Dev Notes

### Dependencies to check
```bash
cd nowing_backend && grep -E "jellyfish|rapidfuzz|fuzzywuzzy" pyproject.toml
```
Prefer `rapidfuzz` (C++ backed, fast, MIT). Add via `uv add rapidfuzz`.

### Existing patterns
- `app/proprietary/platforms/bds_aggregator/` — BĐS aggregator has dedupe + location normalize. Check for reusable location helper.
- `app/services/jobs_aggregator/dedupe.py` — read fully (177 lines) before changing.
- `app/services/jobs_aggregator/normalize.py` — read fully (181 lines) before changing.

### Architecture compliance
- **AD-3**: Scrapers BSL 1.1, capabilities Apache-2.0. Aggregator is Apache-2.0 in `app/services/`.
- **AD-25**: PII redaction before dedupe (already wired).
- **AD-34**: Chunk schema — aggregator produces data, route serializes. Don't merge ingest into orchestrator.

### Testing
```bash
cd nowing_backend && uv run pytest tests/unit/services/jobs_aggregator tests/unit/capabilities/vn_jobs -q
cd nowing_backend && ruff check app/services/jobs_aggregator
```

### References
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/jobs_aggregator/orchestrator.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/jobs_aggregator/normalize.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/jobs_aggregator/dedupe.py" />
- <ref_file file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/services/jobs_aggregator/schemas.py" />

---

## Challenge Log (grill-me)

### Q1 — Already implemented?

**CRITICAL FINDING — BĐS aggregator has reusable location normalization + conflict flag pattern.**

`app/services/bds_aggregator/` has a more mature version of every pattern 12.4a+4b needs:

| 12.4a+4b gap | BĐS equivalent | Location |
|---|---|---|
| Location normalize (diacritics + aliases) | `_remove_diacritics()`, `_to_slug()`, `_CITY_ALIASES`, `_CITY_OVERRIDES` (62 provinces + aliases) | `bds_aggregator/normalize.py:139-176` |
| `ConflictFlag` enum | `ConflictFlag(BaseModel)` with `type: Literal["price_conflict"]`, `reason`, structured fields | `bds_aggregator/schemas.py:27-35` |
| `source_count` on listing | `source_count: int = Field(default=0)` + set to `len(sources)` during merge | `bds_aggregator/schemas.py:66`, `dedupe.py:112` |
| `conflict_flags: list[ConflictFlag]` | `conflict_flags: list[ConflictFlag] = Field(default_factory=list)` | `bds_aggregator/schemas.py:72` |
| Price conflict detection (20% threshold) | `_detect_price_conflict()` with `ratio > 1.2 or relative_diff > 0.2` | `bds_aggregator/dedupe.py:136-164` |
| Union-find transitive dedupe | `deduplicate()` with union-find by phone/address/image keys | `bds_aggregator/dedupe.py:178-228` |

**Verdict:** NOT a HALT (different domain — BĐS vs jobs, can't import directly), but **MUST reuse patterns**:
- Extract `_remove_diacritics` + `_to_slug` + `_CITY_ALIASES` into a shared `app/services/location_normalize/` module (or copy into `jobs_aggregator/`).
- Copy `ConflictFlag` schema shape into `jobs_aggregator/schemas.py` with `type: Literal["SALARY_MISMATCH", "LOCATION_MISMATCH"]`.
- Copy `source_count` field pattern.

No fuzzy title matching library found in `pyproject.toml` (no `rapidfuzz`, `jellyfish`, `fuzzywuzzy`). `difflib.SequenceMatcher` is used in `tool_call_repair/middleware.py` — stdlib, already available.

### Q2 — Simpler alternative?

**CRITICAL FINDING — `difflib.SequenceMatcher` from stdlib may replace Jaro-Winkler.**

AC-4 says "Jaro-Winkler ≥ 0.85". But:
- No fuzzy match library is installed.
- `difflib.SequenceMatcher.ratio()` is stdlib, zero dependencies.
- `SequenceMatcher` ratio is NOT Jaro-Winkler — different algorithm, different scale. `SequenceMatcher` returns similarity ratio [0, 1] but uses a different formula (2*M/T where M = matches, T = total chars).
- For short strings (job titles, 30-60 chars), `SequenceMatcher.ratio()` and Jaro-Winkler give similar but not identical results. Threshold needs recalibration (e.g., 0.80 for `SequenceMatcher` ≈ 0.85 for Jaro-Winkler on short strings).

**Verdict:** **HALT for user decision** — see triage. Two options:
1. **Add `rapidfuzz`** (C++ backed, MIT, ~2MB) — exact Jaro-Winkler, fast, but new dependency.
2. **Use `difflib.SequenceMatcher`** — stdlib, zero deps, but NOT Jaro-Winkler. Threshold needs recalibration. Ponytail rule: "No new dependency if it can be avoided."

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary — Jaro-Winkler exactly 0.85:** AC says ≥ 0.85. Is 0.8499 a match or not? (Spec says no, but float precision may cause 0.8500001 vs 0.8499999.)
- [ ] **Boundary — `posted_at` exactly ±3 days:** 2026-08-05 vs 2026-08-08 — is 3 days inclusive or exclusive? AC says "±3 days" → inclusive.
- [ ] **Boundary — salary difference exactly 10%:** AC-5 says "≤ 10%" → stable. AC-6 says "> 20%" → conflict. What about 10.01%–19.99%? Spec doesn't say. Gray zone.
- [ ] **Boundary — salary difference exactly 20%:** AC-6 says "> 20%". Is 20.0% a conflict or gray zone? Spec says `>`, so 20.0% is NOT a conflict.
- [ ] **Null/empty — `posted_at` is None on one listing:** Can't compute ±3 days. Skip date matching? Fall back to company+title+location only?
- [ ] **Null/empty — `salary` is None/hidden/negotiable on both listings:** Can't compute salary difference. Treat as stable (no conflict) or skip salary comparison?
- [ ] **Null/empty — `salary` is None on one, present on other:** Asymmetric. Treat as no conflict (can't compare) or as `PARTIAL_DATA` degradation?
- [ ] **Null/empty — `company` is empty string:** `_canonical_key` uses `company.lower().strip()` → `""`. All empty-company listings will group together. Need to skip dedupe when company is empty.
- [ ] **Null/empty — `location` is None on one listing:** Location comparison: `""` vs `"Hà Nội"`. `_detect_conflict` uses `set(item.location for item in group)` → `{None, "Hà Nội"}` → len 2 → conflict. But None ≠ a real location mismatch.
- [ ] **Concurrent — same listing scraped by 2 sources simultaneously:** Not a concern for dedupe (in-memory), but canonical persistence may race. Already handled by `upsert_canonical_entity` (idempotent).
- [ ] **Scale — 100+ listings per source, 3 sources = 300+ comparisons:** Fuzzy match is O(n²) within each company+location group. With 300 listings and ~50 groups, worst case 6 comparisons per group. Acceptable. But if a query returns 1000+ listings, fuzzy match could be slow. Mark with `ponytail:` comment.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **`rapidfuzz` import fails (if chosen):** Fall back to `difflib.SequenceMatcher`? Or hard-fail? Spec doesn't say. Recommend: `try: from rapidfuzz import jaro_winkler_similarity; except ImportError: from difflib import SequenceMatcher`.
- [ ] **`_remove_diacritics` on non-Vietnamese text (e.g., English job titles):** `unicodedata.normalize("NFD")` works on all Unicode. Safe.
- [ ] **Location normalize returns None (unknown city):** `_to_slug("Mars Colony")` → `"mars-colony"` → not in `_CITY_ALIASES` → returns `None`. Aggregator filter (`orchestrator.py:318-324`) does exact match on raw location, so unknown locations just don't filter. Safe.
- [ ] **`_detect_conflict` with all salaries = 0:** `avg == 0` → returns `(False, 0.5)` in current code. But AC-5 says ≤10% → stable. 0 vs 0 = 0% difference → should be stable with `confidence_score ≥ 0.8`. Current code gives 0.5. Gap.
- [ ] **`_detect_conflict` with one salary = 0 (negotiable) and one = 30M:** `all_values = [0, 30000000]`. `avg = 15M`. `spread = 30M`. `relative_spread = 2.0` → conflict. But 0 means "negotiable/hidden", not "0 VND". Should skip 0-value salaries in comparison.
- [ ] **Chunk serializer receives `conflict_flags` as list of `ConflictFlag` objects (Pydantic) vs list of strings:** `ChunkMetadata.conflict_flags` is `list[dict[str, Any]]`. `VnJobAggregatedListing.conflict_flags` (if added as `list[str]`) won't serialize to dict. Need to convert. Or align types.

### Triage

| # | Finding | Severity | Action |
|---|---|---|---|
| Q1 | BĐS aggregator has reusable location normalize + ConflictFlag + source_count patterns | **Critical** | **HALT** — user decision: extract shared `app/services/location_normalize/` module, or copy into `jobs_aggregator/`? |
| Q2 | `difflib.SequenceMatcher` (stdlib) vs `rapidfuzz` (new dep) for fuzzy title match | **Critical** | **HALT** — user decision: add `rapidfuzz` for exact Jaro-Winkler, or use stdlib `SequenceMatcher` with recalibrated threshold? |
| Q3 | 11 edge cases unspecified (boundary, null/empty, scale) | Non-critical | Add to test skeleton (bmad-nowing-test-first-atdd) |
| Q4 | 6 failure modes unspecified (import fail, 0-salary, type mismatch) | Non-critical | Add to test skeleton; fix 0-salary handling in `_detect_conflict` |

**2 CRITICAL findings → HALT, cần user decision trước khi implement.**

### Resolved Decisions (2026-08-12)

**Q1 → Extract shared `app/services/location_normalize/` module.**
- Tạo `app/services/location_normalize/__init__.py` với `remove_diacritics()`, `to_slug()`, `CITY_ALIASES`, `CITY_CODES`, `resolve_city_code()`.
- Refactor `app/services/bds_aggregator/normalize.py` để import từ module mới (xóa local copies).
- `jobs_aggregator/normalize.py` import từ module mới.
- DRY, no cross-domain coupling, no duplication.

**Q2 → Add `rapidfuzz` via `uv add rapidfuzz`.**
- `from rapidfuzz.distance import JaroWinkler` — exact Jaro-Winkler similarity.
- No fallback — we control backend deps. `rapidfuzz` is C++ backed, MIT, ~2MB, industry standard.
- Threshold: `JaroWinkler.similarity(title_a, title_b) >= 0.85` (exact AC-4).
- Ponytail exception: AC explicitly names the algorithm, so the dep is justified.

---

## Dev Agent Record

### Debug Log

- Initial run: 2 existing tests failed after location normalization refactor (location now returns city code "HN" instead of "Hà Nội"). Fixed by updating test expectations.
- `_parse_salary` needed to distinguish "no salary fields at all" (hidden) from "salary_min=0, salary_max=0" (negotiable). Added `has_salary_fields` check.
- `_call_source` exceptions (KeyError, RuntimeError) were not caught in `aggregate_jobs` loop. Added try/except around `_call_source` call + None return handling.
- Union-find `find`/`union` functions defined inside loop triggered B023 (loop variable binding). Extracted to module-level `_union_find()` function.
- City codes table had 58 entries (missing 6 provinces). Added Dong Nai, Ha Nam, Hoa Binh, Quang Nam, Tay Ninh, Vinh Phuc → 64 entries.

### Completion Notes

- All 141 unit tests pass (55 dedupe + 42 normalize + 25 orchestrator + 11 location_normalize + 8 canonical conventions).
- All 32 BĐS aggregator + vn_jobs capability tests still pass (refactor is backwards-compatible).
- ruff check + format clean.
- `rapidfuzz` added to pyproject.toml dependencies.
- **Smoke test:** VietnamWorks and ITviec real APIs return live data; TopCV blocked by Cloudflare without proxy.
- **Bug found & fixed in smoke:** `salaryPeriodId=1` from VietnamWorks mapped to `"hour"` while raw text said `/tháng`. Added `_infer_salary_period_from_text` to override period from text.
- **Mutation gate re-run (final):** `dedupe.py` 99.5% (207/208 killed), `normalize.py` 99.5% (206/207 killed) — both well above 80% threshold. 52 new mutation-killing tests added across both modules.

### File List

- `app/services/location_normalize/__init__.py` — NEW: shared Vietnamese location normalization (64 provinces, diacritics, slug, city code resolution)
- `app/services/bds_aggregator/normalize.py` — MODIFIED: imports from shared location_normalize module (removed ~120 lines of duplicated code)
- `app/services/jobs_aggregator/schemas.py` — MODIFIED: added `conflict_flags`, `source_count`, `degraded_source_ids`
- `app/services/jobs_aggregator/normalize.py` — MODIFIED: added `_normalize_experience()`, use `resolve_city_code` for location, fix salary 0/0 vs hidden distinction, handle None skills/source_url
- `app/services/jobs_aggregator/dedupe.py` — REWRITTEN: Jaro-Winkler fuzzy title match, ±3 days date tolerance, conflict flags (SALARY_MISMATCH/LOCATION_MISMATCH), salary thresholds (10%/20%), source_count, union-find transitive dedupe, None location wildcard
- `app/services/jobs_aggregator/orchestrator.py` — MODIFIED: `degraded_source_ids` population, canonical enum mapping (`_DEGRADATION_ENUM_MAP`), exception handling around `_call_source`, None return handling
- `tests/unit/services/jobs_aggregator/test_normalize.py` — MODIFIED: unskipped 24 tests, fixed location expectation, fixed source name
- `tests/unit/services/jobs_aggregator/test_dedupe.py` — MODIFIED: unskipped 33 tests, fixed salary spread test values, added `_source_record_ids` to preserve-both test
- `tests/unit/services/jobs_aggregator/test_orchestrator.py` — MODIFIED: unskipped 25 tests, updated degradation_reasons assertion to canonical enum
- `tests/unit/services/location_normalize/test_location_normalize.py` — MODIFIED: unskipped 11 tests
- `pyproject.toml` — MODIFIED: added `rapidfuzz` dependency

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-08-12 | Green-phase implementation: all 6 ACs implemented, 93 tests passing | dev-story agent |
| 2026-08-12 | Test amplification: added mutation-killing boundary tests for dedupe + normalize; re-ran mutation gate | assistant |
| 2026-08-12 | Real-API smoke test: VietnamWorks + ITviec pass, TopCV blocked; salary-period inference bug fixed | assistant |
| 2026-08-13 | Mutation gate amplification: 52 new tests; dedupe 99.5%, normalize 99.5% — both above 80% threshold | assistant |

### Review Findings

- [x] [Review][Patch] Location filter bypass in orchestrator [orchestrator.py:352-358] — Filter uses naive string comparison `(item.location or "").lower().strip() == loc` instead of `resolve_city_code()`. After normalization, `item.location` is a city code (e.g., "HN"), but `input.location` could be "Hà Nội" or "hanoi". The filter will never match. Fix: resolve both sides to city codes before comparing.
- [x] [Review][Patch] Comment says "62-province" but table has 64 entries [location_normalize/__init__.py:6-7] — Comment says "62-province table" and "63 Vietnamese provinces" but `len(CITY_CODES) == 64`. Fix: update to "64-entry table covering all 63 Vietnamese provinces/municipalities".
- [x] [Review][Defer] Union-find path compression not reused in grouping [dedupe.py:271-273] — deferred, pre-existing pattern — Manual root-finding traversal at lines 271-273 doesn't reuse the `find()` function with path compression. Negligible impact since n ≤ 20 per group and traversal happens once per element.

### Review Findings — Round 2 (2026-08-13, post mutation-gate amplification)

- [x] [Review][Patch] Exception details leaked to degradation_reason [orchestrator.py:135,311] — `str(exc)` is stored directly in `degradation_reason` field, which may leak internal details to downstream systems. Fix: store canonical enum via `_map_degradation_reason` in the degraded dict, keep raw exception for logs only.
- [x] [Review][Defer] Location filter fallback for unknown cities [orchestrator.py:355-364] — deferred, edge case — When `resolve_city_code` returns None for both input and item, comparison falls back to raw lowercased strings. "hanoi" vs "Hà Nội" won't match. Only affects unknown cities not in the 64-province table.
- [x] [Review][Defer] New city codes visible to BĐS aggregator [location_normalize/__init__.py] — deferred, improvement not regression — Shared module adds DNA/HAN/HOB/QNA/TNI/VP codes not in original BĐS mapping. These are valid Vietnamese provinces; BĐS queries benefit from expanded coverage.
- [x] [Review][Defer] Salary period inference missing some English abbreviations [normalize.py:64-70] — deferred, current patterns cover all real VN job sources — Missing "hrly", "daily", "wkly", "mo", "yr", "annum". All 3 sources (VietnamWorks/TopCV/ITviec) use full forms or Vietnamese.
- [x] [Review][Defer] Unknown degradation reasons default to SOURCE_FAILED [orchestrator.py:49-60] — deferred, raw reason available in source_breakdown — Monitoring can use `source_breakdown[source].degradation_reason` for the raw string; canonical enum is for structured filtering.
- [x] [Review][Defer] No min<=max validation on salary values [dedupe.py:328-332] — deferred, scraper responsibility — Negative or inverted salary values pass through. Scrapers should validate; aggregator is defensive enough with zero-skip.
- [x] [Review][Defer] O(n²) dedupe within large company groups [dedupe.py:275-278] — deferred, documented with upgrade path — Ponytail comment acknowledges ceiling and suggests sort-by-posted_at + windowing for 1000+ listings per company.

### Test Quality Review (4.9 — 2026-08-13)

**Score:** 78/100 — Grade B (Approve with comments)
**Report:** `_bmad-output/test-artifacts/test-reviews/test-review-12-4a-4b-2026-08-13.md`

**Critical issues (deferred to tech-debt):**
- File length: all 3 test files exceed 500-line threshold (test_dedupe 2,136; test_normalize 812; test_orchestrator 668)
- Time-dependent tests: 6 tests use `datetime.date.today()` — should use freezegun
- Conditional assertions: 7 tests use `if len(merged) == 1:` guards

**Strengths:**
- 99.5% mutation scores (both modules)
- All 6 ACs fully covered (131 ATDD tests + 86 helper tests)
- Excellent boundary, edge case, and mutation-killing patterns

### Traceability Matrix (4.11 — 2026-08-13)

**Verdict:** PASS — all 6 ACs fully covered
**Report:** `_bmad-output/test-artifacts/traceability/traceability-matrix-12-4a-4b-2026-08-13.md`

| AC | Tests | Coverage |
|----|-------|----------|
| AC-1 (fan-out + caps) | 8 | Full |
| AC-2 (normalize fields) | 42 | Full |
| AC-3 (degradation tracking) | 17 | Full |
| AC-4 (fuzzy dedupe) | 14 | Full |
| AC-5 (salary consistency) | 8 | Full |
| AC-6 (conflict flags) | 16 | Full |

Total: 162 tests (105 AC-mapped + 57 helper). 0 gaps, 0 partial.

### NFR Evidence Audit (4.12 — 2026-08-13)

**Verdict:** APPROVED WITH CONCERNS (1 P1, 0 P0)
**Report:** `_bmad-output/test-artifacts/nfr-assessment-12-4a-4b-2026-08-13.md`

| NFR | Status | Notes |
|-----|--------|-------|
| Performance | CONCERNS | O(n²) documented, no benchmarks (P1) |
| Security | PASS | PII redaction (AD-25), exception leak patched |
| Reliability | PASS | Degradation tracking, outbox fallback |
| Maintainability | PASS | 99.5% mutation, shared module, documented tech debt |
| Observability | PASS | Logger.exception, canonical enum, source_breakdown |

**P1 gap:** Add performance benchmarks before high-volume scaling.

### Human Review Gate (4.13 — 2026-08-13)

**Status:** pending-human-review
**P0 areas touched:**

1. **Data integrity** — `orchestrator.py` changes `conflict_flags` data shape persisted to canonical storage:
   - Old: `[{"type": "salary_conflict", "reason": "salary or location mismatch across sources"}]`
   - New: `[{"type": "SALARY_MISMATCH"}, {"type": "LOCATION_MISMATCH"}]`
   - **Review:** Verify the new conflict_flags format is compatible with canonical entity consumers (ChainLens ingest, search, display)

2. **RAG / connector sync with side effects** — `serializer.py` changes job chunk serialization:
   - Adds 3 new job domains (itviec, topcv, vietnamworks) to `_JOB_DOMAINS`
   - Changes `content_type` from default to `"job"` for job domains
   - Adds `_DOMAIN_CANONICAL` mapping (itviec → itviec.com, etc.)
   - **Review:** Verify `content_type="job"` is the correct ChainLens filter value, and canonical domain names match ChainLens expectations

**What to review manually:**
- `orchestrator.py:225` — conflict_flags data shape change (canonical persist)
- `serializer.py:25,29-33,395-396` — chunk content_type and domain mapping changes
- Verify no downstream consumers break from the conflict_flags format change
- Verify ChainLens can filter on `content_type="job"` and recognizes the canonical domain names
