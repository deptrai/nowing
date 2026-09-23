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

### Review Findings (bmad-code-review 2026-09-05)

#### [Review][Patch] 1. Location-aware routing bypassed for `CampaignSpec` objects [registry.py:526-527]

`resolve_adapters_for_campaign` detects a `CampaignSpec` instance by `hasattr(prompt, "__dict__")` and immediately delegates to `resolve_adapters_for_spec`, which performs legacy keyword/category matching without computing `location_coverage_score` or the 0.4/0.4/0.2 composite ranking. Both `LeadGenOrchestrator.execute_multi_source_lead_gen` and `LeadGenPlanner.plan_from_campaign` pass `CampaignSpec` objects in production, so the location-aware ranking logic is bypassed in the primary campaign paths. **AC-2.2, AC-2.3**

- Suggested fix: unify the two overloads so `CampaignSpec` is unpacked (query, category, location_profile) and routed through the composite-ranking path; or make `resolve_adapters_for_spec` location-aware.

#### [Review][Patch] 2. Inconsistent return type for `resolve_adapters_for_campaign` [registry.py:513-563]

Calling with a `CampaignSpec` returns `list[LeadSourceAdapter]`; calling with `(prompt, category, location_profile)` returns `tuple[list[LeadSourceAdapter], bool]`. `LeadGenPlanner.plan_from_campaign` expects a list and iterates over the result, so a tuple would raise `TypeError`. This overload should return a single, predictable type. **Architectural consistency**

- Suggested fix: always return the same shape (e.g. `tuple[list[LeadSourceAdapter], bool]`) and update both callers to consume the fallback flag; or keep list-only and expose a separate `resolve_adapters_for_campaign_with_fallback` method.

#### [Review][Patch] 3. Orchestrator does not pass `location_profile` to `pre_filter_by_icp` [lead_gen_orchestrator.py:465]

`execute_multi_source_lead_gen` calls `self.pre_filter_by_icp(record, icp_criteria)` without the `location_profile` keyword. Because the parameter defaults to `None`, `evaluate_hierarchical_location_match` returns `(True, 75.0)` for every record, so no geographic pre-filtering occurs during real multi-source runs. **AC-3.4**

- Suggested fix: extract `location_profile` from `campaign_spec` (once `CampaignSpec` has the field) and pass it to `pre_filter_by_icp(record, icp_criteria, location_profile=location_profile)`.

#### [Review][Patch] 4. `blend_location_fit_score` is dead code, not integrated into scoring pipeline [rubric.py:92-104, scoring/service.py, confidence/gate.py]

The function is defined and exported but never called. `LeadScoringService._fit_score`, `ConfidenceGate.evaluate_icp_fit`, and `LeadGenOrchestrator._score_and_enrich` do not blend location match scores, so AC-4's final fit score formula is not applied to production leads. **AC-4.1, AC-4.2**

- Suggested fix: wire `blend_location_fit_score` into the lead scoring path, passing the `location_match_score` computed during pre-filtering; or call it from `ConfidenceGate.evaluate_icp_fit` / `LeadScoringService._fit_score`.

#### [Review][Patch] 5. `CampaignSpec` and `ICPCriteria` lack `location_profile` field [campaign/schemas.py:61-113]

`LocationProfilePayload` exists in `lead_intelligence/schemas.py` but is not attached to `CampaignSpec` or `ICPCriteria`. Campaign requests cannot carry a structured `LocationProfile`, so the planner and orchestrator have no `location_profile` to consume. **AC-2, AC-3**

- Suggested fix: add `location_profile: LocationProfilePayload | None = None` to `CampaignSpec` and, if needed, to `ICPCriteria`; import `LocationProfilePayload` from `app.lead_intelligence.schemas`.

#### [Review][Patch] 6. Province codes collide with common Vietnamese abbreviations [lead_gen_orchestrator.py:264-270]

`prov_candidates` includes the raw 2-letter province code (e.g. `CT`, `DN`). With the regex `(?<![a-z0-9])CT(?![a-z0-9])`, text such as "CT TNHH" (công ty trách nhiệm hữu hạn) or "DN" inside "doanh nghiệp" will match Cần Thơ / Đà Nẵng and return a province score of 75.0. **AC-3.2, AC-3.3**

- Suggested fix: do not match raw 2-letter codes alone in `prov_candidates`; require at least 3-letter tokens or use a deny-list of common abbreviation collisions, or boost matching only when `province_name` or `aliases` are found.

#### [Review][Patch] 7. Ward name matching false positives on single-digit numbers [lead_gen_orchestrator.py:237-239]

Ward names such as "1", "2", or "10" are matched with `(?<![a-z0-9])<ward>(?![a-z0-9])`. This matches prices ("1 tỷ"), floor numbers ("tầng 1"), and room counts ("1 phòng ngủ"), producing a 100.0 exact-ward score for unrelated text. **AC-3.3**

- Suggested fix: require ward tokens to appear with a prefix like "phường", "P.", "P", or "phuong", or filter out purely numeric ward tokens that are not prefixed by a ward indicator.

#### [Review][Patch] 8. District matching does not verify target province for ambiguous districts [lead_gen_orchestrator.py:256-259]

`evaluate_hierarchical_location_match` returns `True, 90.0` as soon as any target district name matches text, without checking whether the text also contains the target province or contradicts it. Districts such as "Châu Thành" exist in multiple provinces and will match across provinces. **AC-3.3**

- Suggested fix: after a district name match, require either a target-province token or the absence of a contradictory province token in the same text, or use the `location_profile.district_codes` to scope the match with a province check.

#### [Review][Patch] 9. Province catalog only covers 10 provinces [divisions.py, lead_gen_orchestrator.py:262]

`PROVINCES_DATA` currently contains only 10 provinces. `evaluate_hierarchical_location_match` looks up `p_code` with `next(...)` and returns `(False, 0.0)` when the target province is not in the catalog, rejecting 100% of leads from the other 53 Vietnamese provinces. **AC-3.2**

- Suggested fix: expand `PROVINCES_DATA` to all 63 Vietnamese provinces, or fall back to `location_profile.province_name` and `location_profile.district_names` when the code is not in the catalog.

#### [Review][Patch] 10. `pre_filter_by_icp` omits `content_snippet` from text extraction [lead_gen_orchestrator.py:296-306]

AC-3.1 explicitly lists `city`, `address`, `title`, `description`, and `content_snippet` as fields to extract and normalize. `pre_filter_by_icp` does not include `content_snippet`, so adapters that store text excerpts in that field (e.g. social/search adapters) may produce false-negative location rejections. **AC-3.1**

- Suggested fix: add `str(data.get("content_snippet", ""))` to `text_parts`.

#### [Review][Patch] 11. `EnterpriseProcurementLeadAdapter` missing coverage profile [enterprise.py]

AC-1.3 requires existing canonical adapters (`BatdongsanAdapter`, `ChototAdapter`, `VietnamworksAdapter`, `EnterpriseProcurementLeadAdapter`, `SocialAdapter`) to declare coverage profiles. `enterprise.py` was not updated and inherits the base `supported_provinces = ["*"]` / `coverage_quality_by_location = {}` defaults. **AC-1.3**

- Suggested fix: add explicit `supported_provinces` and `coverage_quality_by_location` for `EnterpriseProcurementLeadAdapter` based on its actual coverage (nationwide for enterprise/tender data).

#### [Review][Patch] 12. Nationwide wildcard in all canonical adapters prevents fallback warning [batdongsan.py:32, chotot.py:33, social.py:28, vietnamworks.py]

Every canonical adapter includes `"*"` in `supported_provinces`. `calculate_location_coverage_score` returns a baseline `0.6` for any province when `"*"` is present, so `any_location_match` is always `True` and `location_fallback` is never `True` for realistic registry state. **AC-2.5**

- Suggested fix: either remove `"*"` from adapters that are not truly nationwide, or distinguish between explicit province coverage and wildcard fallback in the coverage map so fallback can still trigger when no explicit match exists.

#### [Review][Patch] 13. District coverage scoring returns on first match only [registry.py:485-492]

When `location_profile.district_codes` contains multiple districts, `calculate_location_coverage_score` returns the score for the first district found in `coverage_map`. It does not aggregate or choose the best score across all targeted districts. **AC-2.2**

- Suggested fix: compute the maximum quality score across all matching `d_codes` (or average if that is the intended contract) and fall back to province-level scoring only when no district matches.

#### [Review][Patch] 14. Word-boundary regex does not match technical guardrail [lead_gen_orchestrator.py:191]

Technical Guardrail #2 specifies `rf"(?<![\wÀ-ỹ]){re.escape(clean_keyword)}(?![\wÀ-ỹ])"`. The implementation uses `(?<![a-z0-9])...(?![a-z0-9])`, which treats accented Vietnamese characters as word-boundary characters and can produce incorrect matches. **Technical Guardrail #2**

- Suggested fix: use the documented pattern with `\wÀ-ỹ` (or equivalent Unicode-aware boundary) as in the spec.

#### [Review][Patch] 15. Composite ranking does not set execution priority or lead allocation quotas [registry.py:559-563]

AC-2.4 requires adapters with higher coverage quality to receive higher execution priority and larger lead allocation quotas. The current code only re-orders the adapter list; it does not update `priority` or compute `max_leads` quotas. **AC-2.4**

- Suggested fix: return per-adapter `priority`/`quota` metadata alongside the ranked adapters, or update the `SubTaskPlan` / source budget logic in `LeadGenPlanner` to consume the composite rank.

#### [Review][Patch] 16. Province match branch contains unreachable 65.0 score [lead_gen_orchestrator.py:271-276]

The code sets `score = 75.0 if not d_codes else 65.0`, but the next `if d_codes: return False, 0.0` means `65.0` is never returned. **Code quality**

- Suggested fix: remove the unreachable branch or change the logic to return `65.0` when `d_codes` are present but the district is not matched yet the province is matched (if broad matching is desired).

#### [Review][Patch] 17. Base adapter class uses mutable class-level defaults [base.py:209-210]

`supported_provinces: list[str] = ["*"]` and `coverage_quality_by_location: dict[str, str | float] = {}` are mutable objects defined at class level. In-place mutation by any subclass or instance will affect all other adapters that inherit the default. **Code quality / correctness**

- Suggested fix: use `Field(default_factory=list)` / `Field(default_factory=dict)` if these become Pydantic fields, or define them as instance attributes in `__init__`, or use immutable tuples/frozen dict defaults.

#### [Review][Patch] 18. `location_coverage_fallback` warning is not emitted or attached to plan summary [registry.py:562-563, planner.py]

The fallback flag is returned as a boolean in the tuple overload but is not converted into a warning log entry or attached to `LeadPlanSummaryCard` / `SubTaskPlan`. AC-2.5 and AC-5 require the warning to appear in the plan summary. **AC-2.5, AC-5**

- Suggested fix: log a warning when `location_fallback` is `True` and include a `warnings: list[str]` field in the planner/orchestrator response payload.

#### [Review][Patch] 19. Missing "Châu Thành" disambiguation unit test [test_location_prefilter.py]

AC-5 explicitly requires unit tests for boundary token matching including `"Quận 1" vs "Quận 12"` and `"Châu Thành" disambiguation`. The existing tests cover only the Quận cases. **AC-5**

- Suggested fix: add a test that passes a `LocationProfile` for a specific province with a "Châu Thành" district and verifies that a lead mentioning "Châu Thành" in a different province is rejected.

#### [Review][Patch] 20. Missing integration tests for end-to-end routing and fallback warning [tests/integration/]

AC-5 requires integration tests verifying end-to-end `resolve_adapters_for_campaign` with fallback warning. No integration test was added under `tests/integration/lead_intelligence/` for this behavior. **AC-5**

- Suggested fix: add an integration test that registers real adapters, calls `LeadGenPlanner.plan_from_campaign` or `LeadGenOrchestrator.execute_multi_source_lead_gen` with a `LocationProfile`, and asserts the fallback warning is raised when no adapter covers the target.

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


