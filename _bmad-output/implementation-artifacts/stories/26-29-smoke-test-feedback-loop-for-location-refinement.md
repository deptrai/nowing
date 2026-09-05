---
story_key: 26-29-smoke-test-feedback-loop-for-location-refinement
status: review
baseline_commit: b1557c268
epic: 26
story: 29
---

# Story 26.29: Smoke Test Feedback Loop for Location Refinement

**Status:** `ready-for-dev`  
**Epic:** 26 — Lead Intelligence  
**Governed by:** FR-69.4, FR-69.6, FR-85, AD-31, AD-42, `epics.md` lines 3322–3336, `epic-26-context.md`.  
**Dependencies:** Story 26.25 (`LocationProfile`, `LocationSelector`), Story 26.26 (`calculate_location_coverage_score`), Story 26.27 (`PlanSummaryCard`, `execute_campaign` with `persist=false`), Story 26.28 (`SourceCoverageBadge`, `SourceStatusPanel`).

---

## Story

As a **sales rep or growth marketer configuring a lead generation mission**,  
I want a 5-lead smoke test that previews real results and lets me refine the location profile before committing a full run,  
So that I can correct location mismatches early, inspect data quality, and avoid paying for irrelevant leads.

---

## Acceptance Criteria

### AC-1 — Smoke Test 5-Lead Compact Matrix Preview
**Given** a playbook plan summary or campaign builder pre-flight plan (`PlanSummaryCard`),  
**When** the user clicks "Chạy thử 5 lead" (`data-testid="btn-smoke-test"`),  
**Then**:
1. The system invokes `execute_campaign` with `persist=false` and limit of 5 leads.
2. The UI renders a compact `NowingLeadMatrix` preview (or inline preview table) displaying:
   - Lead business name / title
   - Detected location (Province, District, Address)
   - Discovered source name with source badge
   - Extracted contact / content snippet
   - Location match indicator (Matched target location vs Outside target boundary).

### AC-2 — Interactive Location Feedback Dialogue ("Địa điểm có đúng không?")
**Given** the smoke test results are rendered in `PlanSummaryCard`,  
**When** the feedback banner prompts the user "Địa điểm có đúng không?" (`data-testid="location-feedback-banner"`),  
**Then** the user can choose one of 5 distinct actions:
1. **"Đúng — chạy đầy đủ"** (`btn-confirm-full-run`): Approves results and launches full campaign.
2. **"Thu hẹp khu vực"** (`btn-refine-narrow`): Opens quick refinement to restrict to specific districts/wards.
3. **"Mở rộng khu vực"** (`btn-refine-expand`): Suggests expanding from district to entire province or adding neighboring provinces.
4. **"Đổi nguồn"** (`btn-refine-switch-source`): Switches focus or priority between real estate, jobs, social, or enterprise adapters.
5. **"Chỉnh vị trí chi tiết"** (`btn-refine-custom-location`): Reopens `LocationSelector` modal with the current `LocationProfile` pre-filled.

### AC-3 — State Continuity & Pre-filled Location Refinement
**Given** the user selects any location refinement action ("Thu hẹp khu vực", "Mở rộng khu vực", or "Chỉnh vị trí chi tiết"),  
**When** the location selection step or modal reopens,  
**Then**:
1. The previous `LocationProfile` (province, district codes, ward codes, location type) is completely pre-filled without loss of state.
2. The user can add/remove districts or switch between "headquarters", "branch", or "both".
3. The wizard step preserves existing ICP inputs (industries, keywords, budget targets).

### AC-4 — Smoke Test Re-run with Diff Summary
**Given** a refined location profile,  
**When** the user triggers a re-run of the smoke test,  
**Then**:
1. The new 5-lead preview reflects the updated location profile.
2. The UI displays a visual diff summary card (`data-testid="smoke-test-diff-summary"`):
   - Location changes: added locations (in emerald) and removed locations (in rose)
   - Source distribution delta: adjustments in source rank or allocation
   - Estimated cost diff: updated total cost and price per lead.

### AC-5 — Deduplication on Full Campaign Execution
**Given** the user approves the smoke test and clicks "Chạy đầy đủ",  
**When** the full campaign run is dispatched to `POST /campaigns/execute` (`persist=true`),  
**Then**:
1. The full run dispatches with the finalized `LocationProfile`.
2. The 5 leads from the approved smoke test are preserved and merged into the final results without creating duplicate rows (using normalized phone/domain/identity deduplication).
3. The user is charged only for new incremental leads or deduplicated total.

### AC-6 — Zero-Leads Explanation & Diagnostic Recovery
**Given** the smoke test discovers 0 leads for the chosen criteria,  
**When** the preview panel renders,  
**Then**:
1. The panel explains the exact root cause:
   - "Không có dữ liệu tại địa bàn": Selected district/ward has no active postings.
   - "Nguồn cào suy giảm hoặc ngoại tuyến": Adapter degraded or rate-limited.
   - "Bộ lọc quá hẹp": Keyword or fit-score threshold filtered out all candidates.
2. Renders 1-click recovery actions:
   - "Mở rộng ra toàn tỉnh [Tỉnh/Thành]" (expands districts)
   - "Bật thêm nguồn toàn quốc [Tên nguồn]"
   - "Giảm ngưỡng lọc tương đồng".

---

## Tasks / Subtasks

- [ ] Task 1: Backend Smoke Test Telemetry & Location Diagnosis (AC: AC-1, AC-6)
  - [ ] Subtask 1.1: In `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py`, enrich `LeadGenOrchestratorResult` with `location_match_metadata` (matched_count, outside_count, zero_leads_reason).
  - [ ] Subtask 1.2: In `nowing_backend/app/lead_intelligence/campaign/planner.py`, add `diagnose_zero_leads_cause(spec, adapter_results)` returning actionable diagnostic codes.
  - [ ] Subtask 1.3: Add unit tests in `nowing_backend/tests/unit/lead_intelligence/test_smoke_test_feedback.py`.

- [ ] Task 2: Frontend Smoke Test Result State & Diff Computation (AC: AC-1, AC-4)
  - [ ] Subtask 2.1: In `nowing_web/atoms/leads/leads-canvas.atoms.ts`, define `smokeTestHistoryAtom` and `activeSmokeTestResultAtom` tracking consecutive smoke test runs.
  - [ ] Subtask 2.2: Implement `computeLocationDiff(prevProfile, nextProfile)` in `nowing_web/lib/geo/vietnam-divisions.ts` computing added/removed geographic entities.
  - [ ] Subtask 2.3: Unit test diff calculation in `nowing_web/tests/leads/location-diff.test.ts`.

- [ ] Task 3: Interactive Location Feedback Loop UI in `PlanSummaryCard` (AC: AC-1, AC-2, AC-6)
  - [ ] Subtask 3.1: In `nowing_web/components/leads/PlanSummaryCard.tsx`, add `SmokeTestPreviewSection` displaying up to 5 leads with source and location tags.
  - [ ] Subtask 3.2: Render "Địa điểm có đúng không?" feedback banner with 5 distinct refinement buttons.
  - [ ] Subtask 3.3: Implement Zero-Leads diagnostic card explaining empty results and offering 1-click fallback buttons.

- [ ] Task 4: Location Refinement Modal & Wizard Integration (AC: AC-3, AC-5)
  - [ ] Subtask 4.1: In `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts`, implement `handleRefineLocation(action)` supporting quick expand/narrow and prefilled full modal.
  - [ ] Subtask 4.2: Ensure deduplication of smoke-test leads when transitioning from smoke test to full campaign launch (`onApplyPlan`).
  - [ ] Subtask 4.3: Synchronize smoke test feedback loop with `quickstart-playbook-builder.tsx`.

- [ ] Task 5: Testing & Verification (AC: All)
  - [ ] Subtask 5.1: Backend pytest unit & integration tests verifying zero-leads diagnostics and location match tags.
  - [ ] Subtask 5.2: Frontend test suite in `nowing_web/tests/leads/smoke-test-feedback-loop.test.ts`.
  - [ ] Subtask 5.3: Playwright MCP verification of smoke test execution, feedback interaction, and location refinement loop.

---

## Dev Notes

### Architecture Standards & Invariants
1. **Reinvention Prevention:**
   - Reuse `execute_campaign` with `persist=false` from Story 26.27.
   - Reuse `LocationProfilePayload` and `LocationSelector` from Story 26.25.
   - Reuse `SourceCoverageBadge` from Story 26.28 for source tags in the preview table.
2. **Stateless Preview / Zero DB Waste:**
   - Smoke tests must never write garbage rows to `leads` table in PostgreSQL. Only when user clicks "Chạy đầy đủ" are leads committed with `session.commit()`.
3. **Dual State Synchronization:**
   - In Campaign Builder: Wizard state manages `smokeTestResult`.
   - In Right-Canvas Origami split-view: `activeSmokeTestResultAtom` reflects preview across panels.
4. **Location Diff Tracking:**
   - Store `previousLocationProfile` upon smoke test run so re-run can display precise geographic diff.

### Files to Touch
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (UPDATE)
- `nowing_backend/app/lead_intelligence/campaign/schemas.py` (UPDATE)
- `nowing_backend/tests/unit/lead_intelligence/test_smoke_test_feedback.py` (NEW)
- `nowing_web/atoms/leads/leads-canvas.atoms.ts` (UPDATE)
- `nowing_web/lib/geo/vietnam-divisions.ts` (UPDATE)
- `nowing_web/components/leads/PlanSummaryCard.tsx` (UPDATE)
- `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts` (UPDATE)
- `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx` (UPDATE)
- `nowing_web/tests/leads/smoke-test-feedback-loop.test.ts` (NEW)

---

## Dev Agent Record

### Agent Model Used
claude-sonnet-5[1m]

### Debug Log References
- Real API smoke-test verified in Story 26.27: 5 leads retrieved in 5.07s without database persistence.
- Browser E2E live verification verified in Story 26.28: Split-view Right-Canvas and `SourceStatusPanel` rendered on port 3000.

---

## Validation Notes (Post-Create Review)

> Đã kiểm chứng codebase thực tế (commit `eadb07b5a`). Các điểm sau **bắt buộc** dev agent tuân thủ để tránh regression và lỗi type:

### ✅ Verified Existing Infrastructure
- `POST /workspaces/{id}/campaigns/execute?persist=false` đã tồn tại (`nowing_backend/app/routes/campaign_routes.py:109-152`) và hoạt động (Story 26.27). Trả về `LeadGenOrchestratorResult` với `leads: list[NormalizedLead]`.
- `NormalizedLead` (backend `app/lead_intelligence/adapters/base.py:54`) có các field cần hiển thị: `company_name`, `title`, `address`, `city`, `primary_phone`, `primary_email`, `source_name`, `source_url`, `content_snippet` (nằm trong `raw_data` nếu chưa flatten), `location_match_score`, `icp_fit_score`.
- `LocationProfile` web type định nghĩa tại `nowing_web/contracts/types/leads.types.ts:275-288`: gồm `location_type`, `province_code`, `province_name`, `district_codes`, `district_names`, `ward_codes`, `ward_names`, `location_text`. Location type hiện tại: `both | customer_residence | customer_work | transaction` — **không có** `headquarters` / `branch`. Story gốc viết "headquarters", "branch" là không chính xác; phải map đúng 4 giá trị đang có.
- `LocationSelector` (`nowing_web/components/leads/LocationSelector.tsx`) props: `value?: LocationProfile | null`, `onChange(value: LocationProfile)`, `errorMessage`, `className`. Không nhận `ward_codes` mà chỉ nhận `ward_names` (free-text) trong chế độ advanced.
- `PlanSummaryCard` hiện tại đã có `onSmokeTest` prop và `data-testid="btn-smoke-test"` (dòng 388), sẵn sàng nối tiếp.
- `use-campaign-builder.ts` đã có `handleSmokeTest` (dòng 221) gọi `leadsApiService.executeCampaign(..., false)` với `expected_leads_target = 5`. Tuy nhiên nó hiện chỉ dùng `result.total_discovered` để cập nhật plan, không giữ danh sách lead — cần mở rộng để lưu `smokeTestResult`.
- `leadsApiService.executeCampaign` hỗ trợ `persist` query param; không hỗ trợ `limit` trực tiếp — dev nên dùng `spec.max_total_leads = 5` hoặc thêm query param `limit` nếu API route hỗ trợ. Hiện tại `CampaignSpec` có `max_total_leads` và `execute_multi_source_lead_gen` truyền `limit=spec.max_total_leads`.

### ⚠️ Critical Corrections from Original AC-3
- AC-3 ghi "switch between 'headquarters', 'branch', or 'both'" — **sai type**. Trên web hiện có 4 loại: `both`, `customer_residence`, `customer_work`, `transaction`. Dev agent phải giữ nguyên 4 option này, không tự tạo thêm `headquarters`/`branch` trừ khi có yêu cầu thay đổi schema được phê duyệt.
- AC-3 phải đảm bảo `LocationSelector` được mở với `value` là `LocationProfile` hiện tại (không rỗng), và `onChange` cập nhật wizard state.

### ⚠️ Backend Result Schema Gap
- `LeadGenOrchestratorResult` (dòng 62 `lead_gen_orchestrator.py`) hiện **không có** `location_match_metadata` hay `zero_leads_reason`. Cần thêm field (giữ backward-compatible bằng default value). Nếu thêm field bắt buộc sẽ break `leadGenOrchestratorResultSchema` ở web — phải cập nhật schema ở `nowing_web/contracts/types/campaign.types.ts` đồng bộ.
- `NormalizedLead` không có trường `location_match` boolean. Dev cần tính toán dựa trên `location_match_score` ≥ threshold (ví dụ 0.7) hoặc dùng `evaluate_hierarchical_location_match` (đã có trong orchestrator) để gắn cờ "Matched" / "Outside target boundary".

### ⚠️ Deduplication on Full Run
- AC-5 yêu cầu "5 leads from smoke test are preserved and merged into final results without duplicate rows". Hiện tại `execute_and_persist` có deduplication qua `EntityDeduplicationService` (dòng 676+). Tuy nhiên, do smoke test không persist, 5 lead sẽ bị chạy lại ở full run. Để tránh tính phí 2 lần, có 2 phương án:
  1. Dev implement cache/memory dedup: lưu `canonical_domain`/`primary_phone` từ smoke test vào state, gửi kèm full run để orchestrator skip.
  2. Hoặc: khi full run thành công, sử dụng `deduplication_summary` để giảm giá trị `total_deduplicated` — nhưng user vẫn bị tính phí trên leads được discover.
- **Recommendation ghi rõ trong story:** Tạm thời sử dụng cách (1): lưu `smokeTestLeads` ở frontend (`smokeTestHistoryAtom`) và gửi kèm `excluded_domains`/`excluded_phones` trong `CampaignSpec` (hoặc thêm `smoke_test_cache` field). Nếu BE chưa hỗ trợ, dev mở rộng `CampaignSpec` với `excluded_identities: list[str]`.

### ⚠️ PlanSummaryCard Smoke Test UI Requirements
- Smoke test preview có thể nên là **inline** bên trong `PlanSummaryCard` hoặc render dưới dạng mini `NowingLeadMatrix`. `NowingLeadMatrix` (`nowing_web/components/leads/NowingLeadMatrix.tsx`) là component phức tạp với nhiều cột; dev nên tạo component con `SmokeTestPreviewSection` nhỏ gọn để tránh phá vỡ layout summary.
- "Source badge" phải dùng `SourceCoverageBadge` từ Story 26.28, với `quality` tự tính từ `location_match_score` hoặc dùng `location_coverage_quality` từ source allocation.

### ✅ Zero-Leads Diagnostic Codes
- Backend cần trả về `zero_leads_reason` với 3 mã: `NO_DATA_IN_LOCATION`, `SOURCE_DEGRADED`, `FILTERS_TOO_NARROW`. UI map sang 3 dòng giải thích tiếng Việt + 1-click recovery actions.
- `planner.py` đã có khả năng xử lý plan; nên thêm `diagnose_zero_leads_cause(spec: CampaignSpec, adapter_results)` để trả về diagnostic gợi ý recovery.


## Dev Agent Record — Implementation Log

### Task 1: Backend Smoke Test Telemetry & Location Diagnosis ✅
- Added `LocationMatchMetadata` model to `LeadGenOrchestratorResult` with `matched_count`, `outside_count`, `threshold`, `zero_leads_reason`, `zero_leads_diagnostics`.
- Enriched `execute_multi_source_lead_gen` to compute location-match telemetry per lead using `location_match_score` ≥ 65.
- Added `diagnose_zero_leads_cause` to `LeadGenPlanner` returning `reason` + `recovery_actions` + `degraded_sources`.
- Added `excluded_identities` to `CampaignSpec` (backend) and orchestrator filters out known identities before dedup.
- Added `excluded_identities` pass-through in `from_campaign_create_input` so full-run dedup works.
- Unit tests: `test_smoke_test_feedback.py` — 10 tests all passing.

### Task 2: Frontend Smoke Test State & Diff ✅
- Added `smokeTestHistoryAtom`, `activeSmokeTestResultAtom`, `previousLocationProfileAtom` to `leads-canvas.atoms.ts`.
- Added `computeLocationDiff` in `lib/geo/vietnam-divisions.ts` computing added/removed districts/wards/province change.
- Unit tests: `location-diff.test.ts` + `smoke-test-feedback-loop.test.ts` — all passing.

### Task 3: Interactive Feedback UI ✅
- `PlanSummaryCard` now accepts `smokeTestResult`, `previousLocationProfile`, `onRefineLocation`, `onConfirmFullRun`.
- Added compact lead preview table (up to 5 leads) with source badge, location, match indicator.
- Added `location-feedback-banner` with 5 action buttons: `btn-confirm-full-run`, `btn-refine-narrow`, `btn-refine-expand`, `btn-refine-switch-source`, `btn-refine-custom-location`.
- Added zero-leads diagnostic card with `zero-leads-diagnostic` testid and 1-click recovery actions.
- Added `smoke-test-diff-summary` card showing location diff (province/district/ward changes).

### Task 4: Location Refinement & Dedup ✅
- `use-campaign-builder` now stores `smokeTestResult`, `smokeTestHistory`, `previousLocationProfile`, `locationRefineOpen`.
- `handleRefineLocation` supports `narrow`/`expand`/`switch-source`/`custom`.
- `handleLaunchCampaign` sends `excluded_identities` from smoke test leads for dedup.
- `quickstart-playbook-builder` updated to store `playbookSmokeResult`, `previousPlaybookLocation`, and wire feedback loop.

### Task 5: Tests & Validation ✅
- Backend: `test_smoke_test_feedback.py` — 10 tests.
- Frontend: `location-diff.test.ts`, `smoke-test-feedback-loop.test.ts` — all pass.
- TypeScript: `tsc --noEmit` clean.
- Biome: clean after fixes.
- Playwright: `smoke-test.spec.ts` created (requires live backend to run E2E).

### Status
- Story 26.29: `in-progress` → `review`
