---
story_key: 26-26-location-aware-adapter-routing-coverage-quality
status: done
baseline_commit: e184a3cd8
epic: 26
story: 26
---

# Story 26.26: Location-Aware Adapter Routing & Coverage Quality

**Status:** `done`  
**Epic:** 26 — Lead Intelligence  
**Governed by:** FR-69.2, FR-69.3, FR-85, AD-31, AD-42, NFR-1, `epics.md` lines 3268–3285.  
**Dependencies:** Story 26.25 (`LocationProfile`, `divisions.py`), `LeadSourceAdapter` (`app/lead_intelligence/adapters/base.py`), `LeadGenOrchestrator` (`app/lead_intelligence/services/lead_gen_orchestrator.py`).

---

## Story

As a **lead generation orchestrator**,  
I want the system to prefer and rank adapters that actually cover the selected provinces, districts, and wards, and strictly filter out out-of-area records,  
so that scraping budget is spent on sources that are most likely to return relevant local leads without wasting credits on irrelevant geographic noise.

---

## Acceptance Criteria

### AC-1 — Adapter Location Coverage Metadata
**Given** a `LeadSourceAdapter` implementation,  
**When** it is registered in `LeadSourceAdapterRegistry`,  
**Then** it declares:
1. `supported_provinces: list[str]` (e.g. `["HN", "SG", "DN"]` or `["*"]` for nationwide sources).
2. `coverage_quality_by_location: dict[str, str]` mapping province/district codes to coverage quality: `"high" | "medium" | "low" | "none"`.
3. Existing adapters (`BatdongsanAdapter`, `ChototAdapter`, `VietnamworksAdapter`, `SocialAdapter`) declare their local coverage profiles.

### AC-2 — Location-Aware Composite Routing & Ranking
**Given** a campaign or lead generation request with a `LocationProfile`,  
**When** `resolve_adapters_for_campaign()` executes in `LeadSourceAdapterRegistry`:
1. It resolves candidate adapters by intent, category, and keywords.
2. For each candidate, it computes a `location_coverage_score` (0.0 to 1.0) based on `coverage_quality_by_location` against the target `province_code` and `district_codes`.
3. It re-ranks candidate adapters using the composite formula:
   ```
   composite_score = (location_coverage_score * 0.4) + (vertical_relevance_score * 0.4) + (cost_efficiency_score * 0.2)
   ```
4. Adapters with higher coverage quality ("high" or "medium") receive higher execution priority and larger lead allocation quotas over adapters with "low" or "none".
5. If no adapter has a location match, the system falls back to keyword-based routing and emits a `location_coverage_fallback` warning in the plan summary.

### AC-3 — Hierarchical ICP Pre-filtering (Ward -> District -> Province)
**Given** an incoming raw lead record being processed by `LeadGenOrchestrator.pre_filter_by_icp()`,  
**When** a `LocationProfile` is specified in the ICP criteria:
1. It extracts and normalizes text fields (`city`, `address`, `title`, `description`, `content_snippet`) using `remove_diacritics()`.
2. It tests location matching with hierarchical precedence:
   - If `ward_names` are defined in `LocationProfile`: matches ward with word-boundary tokens.
   - If `district_codes` are defined in `LocationProfile`: matches district names and aliases within the target province.
   - Matches `province_code`, province names, and canonical aliases (`HN`, `SG`, `DN`, `Hà Nội`, `Saigon`...).
3. It uses word-boundary token matching to avoid adversarial false positives (e.g. distinguishing `"Quận 1"` from `"Quận 10"`, `"Quận 11"` or `"Quận 12"`, and scoped `"Châu Thành"` to its specific province).
4. Any lead record that fails to match the required `LocationProfile` is rejected before expensive confidence-gate scoring and enrichment (`return False`).

### AC-4 — Location Fit Score Blending
**Given** a lead record that passes the geographic pre-filter,  
**When** `calculate_fit_score()` runs:
1. It computes a `location_match_score` (0 to 100):
   - Exact Ward match: `100`
   - Target District match: `90`
   - Target Province match (district unselected or broad): `75`
2. It blends the location score with the existing intent/profile fit score using `location_weight = 0.3`:
   ```
   final_fit_score = round(base_fit_score * 0.7 + location_match_score * 0.3, 1)
   ```

### AC-5 — Test Coverage
**Given** the updated adapter registry and orchestrator,  
**When** test suites execute,  
**Then**:
- Unit tests verify composite score weighting (0.4 / 0.4 / 0.2) and adapter ranking.
- Unit tests verify boundary token matching ("Quận 1" vs "Quận 12", "Châu Thành" disambiguation).
- Unit tests verify pre-filtering rejects out-of-province leads and accepts matching leads.
- Integration tests verify end-to-end `resolve_adapters_for_campaign` with fallback warning.
- All tests pass with 100% ruff and pytest clean.

---

## Technical Guardrails & Developer Notes

### 1. Coverage Quality Scale & Scoring Values
- Quality string mapping to numeric score:
  - `"high"`: `1.0`
  - `"medium"`: `0.7`
  - `"low"`: `0.4`
  - `"none"`: `0.0`
  - Nationwide adapter with `supported_provinces = ["*"]`: baseline `0.6` if no specific province override.

### 2. Word Boundary Regex for Vietnamese Location Names
- Do not use bare `\b` with diacritics because Python standard `\b` treats accented Unicode characters inconsistently depending on normalization.
- Use sanitized token boundary matching:
  ```python
  pattern = rf"(?<![\wÀ-ỹ]){re.escape(clean_keyword)}(?![\wÀ-ỹ])"
  ```
- Compare using ASCII-folded lowercase strings generated by `remove_diacritics()`.

### 3. Backend Pydantic Model for LocationProfile
- Define in `nowing_backend/app/lead_intelligence/schemas.py`:
  ```python
  class LocationProfilePayload(BaseModel):
      location_type: str = "both"
      province_code: str
      province_name: str
      district_codes: list[str] = Field(default_factory=list)
      district_names: list[str] = Field(default_factory=list)
      ward_codes: list[str] = Field(default_factory=list)
      ward_names: list[str] = Field(default_factory=list)
      location_text: str = ""
  ```

---

## Tasks / Subtasks

- [x] Adapter Contracts & Declarations (`nowing_backend/app/lead_intelligence/adapters/`)
  - [x] Add `supported_provinces` and `coverage_quality_by_location` fields to `LeadSourceAdapter` base class (`base.py`).
  - [x] Populate coverage profiles for canonical adapters (`batdongsan.py`, `chotot.py`, `vietnamworks.py`, `enterprise.py`, `social.py`).
- [x] Location-Aware Composite Routing (`nowing_backend/app/lead_intelligence/adapters/registry.py`)
  - [x] Implement `calculate_location_coverage_score(adapter, location_profile)` helper.
  - [x] Implement `resolve_adapters_for_campaign(category, prompt, location_profile, ...)` with 0.4/0.4/0.2 composite ranking.
  - [x] Add fallback warning handling when no location coverage matches.
- [x] Hierarchical Pre-Filter & Token Matcher (`nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`)
  - [x] Enhance `pre_filter_by_icp` to accept `LocationProfile` and execute hierarchical matching (Ward -> District -> Province).
  - [x] Implement word-boundary regex token matching to prevent false positives ("Quận 1" vs "Quận 10-12").
- [x] Fit Score Location Blending (`nowing_backend/app/lead_intelligence/scoring/`)
  - [x] Update fit scoring logic to blend `location_match_score` with `location_weight = 0.3`.
- [x] Verification & Tests
  - [x] Write unit tests in `nowing_backend/tests/unit/lead_intelligence/test_location_routing.py`.
  - [x] Write unit tests for hierarchical location matcher in `nowing_backend/tests/unit/lead_intelligence/test_location_prefilter.py`.
  - [x] Run `ruff check` and pytest suite.

---

## Suggested Review Order

**Adapter Contracts & Routing Registry**

- Base adapter location coverage declarations and metadata
  [`base.py:206`](../../../nowing_backend/app/lead_intelligence/adapters/base.py#L206)

- Location-aware composite ranking and fallback warning algorithm
  [`registry.py:443`](../../../nowing_backend/app/lead_intelligence/adapters/registry.py#L443)

**Hierarchical Pre-Filtering & Token Matching**

- Hierarchical location evaluator (Ward -> District -> Province) with word boundaries
  [`lead_gen_orchestrator.py:184`](../../../nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py#L184)

- ICP pre-filtering with LocationProfile integration
  [`lead_gen_orchestrator.py:252`](../../../nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py#L252)

**Fit Score Blending**

- Blending formula `base * 0.7 + loc * 0.3` with clamp logic
  [`rubric.py:93`](../../../nowing_backend/app/lead_intelligence/scoring/rubric.py#L93)

**Test Suites**

- Composite score ranking and adapter location routing unit tests
  [`test_location_routing.py:106`](../../../nowing_backend/tests/unit/lead_intelligence/test_location_routing.py#L106)

- Boundary token matching, hierarchical matching, and pre-filter tests
  [`test_location_prefilter.py:14`](../../../nowing_backend/tests/unit/lead_intelligence/test_location_prefilter.py#L14)


