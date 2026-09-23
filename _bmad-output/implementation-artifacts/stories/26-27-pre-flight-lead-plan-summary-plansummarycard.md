---
story_key: 26-27-pre-flight-lead-plan-summary-plansummarycard
status: done
baseline_commit: 7c8ebf359
epic: 26
story: 27
---

# Story 26.27: Pre-Flight Lead Plan Summary & PlanSummaryCard

**Status:** `done`  
**Epic:** 26 — Lead Intelligence  
**Governed by:** FR-69.4, FR-85, FR-86, AD-31, AD-42, `epics.md` lines 3287–3302, `sprint-change-proposal-customer-location-profile-pre-flight-plan-2026-08-29.md`.  
**Dependencies:** Story 26.25 (`LocationProfile`, `LocationSelector`, `divisions.py`), Story 26.26 (`calculate_location_coverage_score`, `resolve_adapters_for_campaign`, coverage metadata), `CampaignSpec` & `LeadGenPlanner`.

---

## Story

As a **sales rep or growth marketer**,  
I want to review a concise pre-flight plan summary showing source allocations, location coverage quality badges, estimated reachable leads, and credit cost before scraping starts, with a persistent mirror in the Right-Canvas,  
so that I can verify source readiness, spot location gaps early, and run low-cost smoke tests without wasting credits on poorly configured campaigns.

---

## Acceptance Criteria

### AC-1 — Pre-Flight Plan API & Enrichment
**Given** a `CampaignSpec` with an optional `LocationProfile`,  
**When** the client queries `POST /api/v1/workspaces/{workspace_id}/campaigns/plan`,  
**Then** the backend returns an enriched `CampaignPlanResponse` containing:
1. `campaign_name: str`, `workspace_id: int`, `total_planned_sources: int`, `expected_sources: list[str]`.
2. `source_allocations: list[SourcePlanAllocation]`, where each entry includes:
   - `source_name: str` (e.g. "batdongsan", "chotot", "topcv", "social", "muasamcong")
   - `category: str`
   - `allocated_limit: int` (lead quota assigned to this source)
   - `priority: int`
   - `location_coverage_quality: "high" | "medium" | "low" | "none"` (derived from `calculate_location_coverage_score`: $\ge 0.9 \rightarrow$ high, $0.6 \le s < 0.9 \rightarrow$ medium, $0.3 \le s < 0.6 \rightarrow$ low, $< 0.3 \rightarrow$ none)
   - `location_coverage_score: float` (0.0 to 1.0)
   - `supported_provinces: list[str]`
   - `status: "ready" | "degraded" | "offline"`
   - `degraded_reason: str | None`
3. `estimated_reachable_leads: int` (sum of reachable quota estimates across resolved sources).
4. `estimated_cost_micros: int` & `estimated_cost_vnd: int`.
5. `warnings: list[str]` (including `location_coverage_fallback` warning if no adapter covers the targeted province/districts).
6. **Backward Compatibility:** `LeadGenPlanner.plan_from_campaign(spec)` preserves its return tuple `(subtasks, expected_sources)` for existing callers, while adding `create_preflight_plan(spec) -> CampaignPlanResponse` for enriched plan queries.

### AC-2 — PlanSummaryCard Component & Progressive Details
**Given** the `PlanSummaryCard` component rendered in the Playbook Wizard (Step 5) or Campaign Builder (Step 3),  
**When** the plan is loaded,  
**Then** it displays:
1. **Header & Context:** Campaign/preset name, target intent badge (`BÁN`, `MUA`, `TUYỂN`...), and target product/keyword.
2. **Location Profile Section:** Human-readable location text with `Province (Districts, Wards)` formatted via `buildLocationSummary`, plus `location_type` badge (`both`, `customer_residence`, `customer_work`, `transaction`).
3. **Source Allocation & Coverage List:** Grid or badge list of planned sources. Each source displays:
   - Source icon and name
   - Color-coded Coverage Quality Chip: `High` (emerald), `Medium` (sky), `Low` (amber), `None` (rose)
   - Allocated lead quota (e.g. `50 leads`)
4. **Expandable Coverage Details Accordion:** Clicking or expanding a source card shows `supported_provinces`, per-source lead allocation, specific coverage reason, and degraded notices if any.
5. **Coverage Warning Banner:** If any source has `"low"` or `"none"` coverage, or if `location_coverage_fallback` is triggered, displays an actionable amber alert banner suggesting a broader province or alternative sources.
6. **Financial Summary & Balance Check:** Estimated reachable leads (e.g. `150 leads`) and estimated credit/VND cost. If estimated cost exceeds the user's available balance (`currentUser.credit_micros_balance`), renders an insufficient credits warning.

### AC-3 — Right-Canvas Mirror & Persistent Review
**Given** an active playbook configuration or campaign draft,  
**When** the user opens or looks at the Right-Canvas (Origami split-view),  
**Then**:
1. A persistent mirror of `PlanSummaryCard` is accessible in the Right-Canvas via a dedicated view mode or banner (`activeMode === "plan"` in `DynamicRightPanelCanvas`), allowing the sales rep to keep chat/prompts in focus on the left while monitoring plan configuration on the right.
2. Changes made in the wizard (updating location in Step 2 or adjusting sources in Step 3) update `activePlanSpecAtom` in Jotai, reactively refreshing the Right-Canvas plan mirror without manual reload.

### AC-4 — Smoke Test (5 Leads) Feedback Execution
**Given** the `PlanSummaryCard` action footer,  
**When** the user clicks "Smoke Test (5 leads)" (or "Chạy thử 5 lead"),  
**Then**:
1. The system invokes `POST /api/v1/workspaces/{workspace_id}/campaigns/execute?persist=false` with `max_total_leads=5`.
2. The card transitions to a running state with an animated progress spinner and execution status.
3. Upon completion, displays the actual reachable leads returned (up to 5), updates the estimated cost to reflect actual smoke-test spend, and switches the primary CTA button to **"Chạy chiến dịch đầy đủ"** (`Launch Full Campaign`) and a secondary **"Chỉnh sửa kế hoạch"** (`Edit Plan`).

### AC-5 — Wizard Navigation & State Preservation
**Given** the user reviewing the `PlanSummaryCard` at the final wizard step,  
**When** they click "Quay lại" (`Back`),  
**Then** the wizard navigates back to previous steps (`Step 4: Channels/Budget` or `Step 2: Location Profile`) without clearing or mutating any previously selected inputs.  
**When** they click "Chạy chiến dịch đầy đủ" (`Launch Full Campaign`),  
**Then** the campaign launches via `POST /api/v1/workspaces/{workspace_id}/campaigns/execute?persist=true` or redirects to `/new-chat?q={encodedPrompt}` as configured.

---

## Tasks / Subtasks

- [ ] Task 1: Backend Pre-Flight Plan API Enrichment (AC: AC-1)
  - [ ] Subtask 1.1: In `nowing_backend/app/lead_intelligence/campaign/schemas.py`, define `SourcePlanAllocation` and update `CampaignPlanResponse` with `source_allocations: list[SourcePlanAllocation]`, `estimated_reachable_leads: int`, `estimated_cost_micros: int`, `estimated_cost_vnd: int`, and `warnings: list[str]`.
  - [ ] Subtask 1.2: In `nowing_backend/app/lead_intelligence/campaign/planner.py`, add `create_preflight_plan(spec: CampaignSpec) -> CampaignPlanResponse` while preserving `plan_from_campaign(spec)` tuple compatibility `(subtasks, expected_sources)`.
  - [ ] Subtask 1.3: Compute `location_coverage_score` and quality label (`high/medium/low/none`) for each resolved adapter, extracting `supported_provinces` and `last_execution_status`.
  - [ ] Subtask 1.4: In `nowing_backend/app/routes/campaign_routes.py`, update `POST /{workspace_id}/campaigns/plan` to invoke `planner.create_preflight_plan(spec)` and return `CampaignPlanResponse`.
  - [ ] Subtask 1.5: Add unit tests in `nowing_backend/tests/unit/lead_intelligence/test_campaign_plan.py` asserting coverage scores, quality labels, and fallback warnings in the plan response.

- [ ] Task 2: Frontend Data Contracts & API Client (AC: AC-1, AC-4)
  - [ ] Subtask 2.1: In `nowing_web/contracts/types/campaign.types.ts`, define `sourcePlanAllocationSchema` and `campaignPlanResponseSchema`. Update `icpConfigSchema` and `campaignCreateInputSchema` to support `location_profile?: LocationProfile`.
  - [ ] Subtask 2.2: In `nowing_web/lib/apis/leads-api.service.ts`, implement `planCampaign(workspaceId, spec: any): Promise<CampaignPlanResponse>` and `executeCampaign(workspaceId, spec, persist): Promise<LeadGenOrchestratorResult>`.

- [ ] Task 3: `PlanSummaryCard` Component Implementation (AC: AC-2, AC-5)
  - [ ] Subtask 3.1: Create `nowing_web/components/leads/PlanSummaryCard.tsx` rendering header, location summary badge, source badge grid with quality chips, warnings banner, and cost estimate.
  - [ ] Subtask 3.2: Implement expandable accordion for source coverage details (`supported_provinces`, per-source lead allocation, status, and coverage reason).
  - [ ] Subtask 3.3: Implement credit balance check with `currentUserAtom` — show warning if balance is below estimated cost.
  - [ ] Subtask 3.3: Implement smoke test button trigger with loading state and post-smoke test CTA switch ("Chạy chiến dịch đầy đủ" vs "Chỉnh sửa kế hoạch").

- [ ] Task 4: Wizard & CampaignBuilder Integration (AC: AC-2, AC-5)
  - [ ] Subtask 4.1: In `nowing_web/components/leads/campaign-builder/types.ts` & `use-campaign-builder.ts`, add `locationProfile: LocationProfile | null` to state, setter, and payload synchronization to eliminate dual location state drift.
  - [ ] Subtask 4.2: In `nowing_web/components/leads/campaign-builder/steps/IcpBuilderStep.tsx`, wire `LocationSelector.onChange` directly to `builder.setLocationProfile(profile)`.
  - [ ] Subtask 4.3: In `nowing_web/components/leads/campaign-builder/steps/LaunchScheduleStep.tsx`, replace static right-hand card with reactive `PlanSummaryCard`.
  - [ ] Subtask 4.4: In `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx`, upgrade Step 2 to use `LocationSelector` and Step 5 to render `PlanSummaryCard`.

- [ ] Task 5: Right-Canvas Split-View Mirror Integration (AC: AC-3)
  - [ ] Subtask 5.1: In `nowing_web/atoms/leads/leads-canvas.atoms.ts`, add `"plan"` to `CanvasMode` and create `activePlanSpecAtom = atom<CampaignPlanResponse | null>(null)`.
  - [ ] Subtask 5.2: In `nowing_web/components/leads/DynamicRightPanelCanvas.tsx`, add a view mode tab and panel rendering `PlanSummaryCard` in the Right-Canvas when `activeMode === "plan"`.

- [ ] Task 6: E2E and Unit Verification (AC: All)
  - [ ] Subtask 6.1: Run pytest unit tests for `LeadGenPlanner` and `campaign_routes.py`.
  - [ ] Subtask 6.2: Create Playwright E2E test in `nowing_web/tests/leads/plan-summary.spec.ts` verifying rendering, coverage badge display, credit alert, and navigation.

---

## Dev Notes

### Relevant Architecture Patterns and Constraints

1. **Composite Location Coverage Calculation & Quality Mapping:**
   - Re-use `LeadSourceAdapterRegistry.calculate_location_coverage_score(adapter, location_profile)`.
   - Discrete quality tiers:
     - Score $\ge 0.9$: `"high"` (emerald `#10b981`, badge variant default/emerald)
     - $0.6 \le \text{Score} < 0.9$: `"medium"` (sky `#0284c7`, badge variant secondary/sky)
     - $0.3 \le \text{Score} < 0.6$: `"low"` (amber `#f59e0b`, badge variant outline/amber)
     - $\text{Score} < 0.3$: `"none"` (rose `#f43f5e`, badge variant destructive/rose)

2. **Cost Calculation Standard:**
   - Standard lead pricing model (FR-69 / Story 21.15):
     - Base discovery per lead: 1,500 VND (approx 60,000 credit micros).
     - Verified phone unlock option: 5,000 VND (200,000 credit micros).
   - Estimated cost formula:
     $$\text{cost\_vnd} = \text{target\_leads} \times (5000 \text{ if auto\_unlock else } 1500)$$
     $$\text{cost\_micros} = \text{cost\_vnd} \times 40$$

3. **Backend Schema & Backward-Compatible Signature:**
   ```python
   class SourcePlanAllocation(BaseModel):
       source_name: str
       category: str
       allocated_limit: int
       priority: int
       location_coverage_quality: str  # "high" | "medium" | "low" | "none"
       location_coverage_score: float
       supported_provinces: list[str]
       status: str = "ready"
       degraded_reason: str | None = None

   class CampaignPlanResponse(BaseModel):
       campaign_name: str
       workspace_id: int
       total_planned_sources: int
       expected_sources: list[str]
       subtasks: list[SubTaskPlan]
       source_allocations: list[SourcePlanAllocation] = Field(default_factory=list)
       estimated_reachable_leads: int = 0
       estimated_cost_micros: int = 0
       estimated_cost_vnd: int = 0
       warnings: list[str] = Field(default_factory=list)
   ```
   In `LeadGenPlanner`:
   ```python
   def create_preflight_plan(self, spec: CampaignSpec) -> CampaignPlanResponse:
       # Builds enriched response while keeping plan_from_campaign untouched for existing callers
   ```

4. **Right-Canvas Split-View Integration (AD-86):**
   - In `leads-canvas.atoms.ts`:
     ```typescript
     export type CanvasMode = "leads" | "research" | "automations" | "scrapers" | "artifacts" | "plan";
     export const activePlanSpecAtom = atom<CampaignPlanResponse | null>(null);
     ```
   - In `DynamicRightPanelCanvas.tsx`:
     ```typescript
     {activeMode === "plan" && (
       <div className="p-4 overflow-y-auto h-full">
         <PlanSummaryCard plan={activePlanSpec} inRightCanvas />
       </div>
     )}
     ```

### Source Tree Components to Touch

#### Backend (`nowing_backend`)
- `app/lead_intelligence/campaign/schemas.py`: Add `SourcePlanAllocation`, enrich `CampaignPlanResponse`.
- `app/lead_intelligence/campaign/planner.py`: Add `create_preflight_plan`, calculate coverage quality, and keep `plan_from_campaign` backward-compatible.
- `app/routes/campaign_routes.py`: Update `POST /{workspace_id}/campaigns/plan` to use `create_preflight_plan`.
- `tests/unit/lead_intelligence/test_campaign_plan.py`: New unit tests asserting coverage scores, allocations, and fallback warnings.

#### Frontend (`nowing_web`)
- `contracts/types/campaign.types.ts`: Define TypeScript Zod schemas for `sourcePlanAllocationSchema` and `campaignPlanResponseSchema`.
- `lib/apis/leads-api.service.ts`: Add `planCampaign` and `executeCampaign`.
- `components/leads/campaign-builder/types.ts`: Add `locationProfile: LocationProfile | null` to state & return interface.
- `components/leads/campaign-builder/use-campaign-builder.ts`: Add `locationProfile` state, setter, and include in `CampaignCreateInput`.
- `components/leads/campaign-builder/steps/IcpBuilderStep.tsx`: Pass `locationProfile` to `LocationSelector` and update on change.
- `components/leads/campaign-builder/steps/LaunchScheduleStep.tsx`: Replace right card with `PlanSummaryCard`.
- `components/assistant-ui/quickstart-playbook-builder.tsx`: Integrate `LocationSelector` into Step 2 and `PlanSummaryCard` into Step 5.
- `atoms/leads/leads-canvas.atoms.ts`: Add `"plan"` mode and `activePlanSpecAtom`.
- `components/leads/DynamicRightPanelCanvas.tsx`: Support `"plan"` mode tab and review panel.
- `components/leads/PlanSummaryCard.tsx`: NEW UI component for plan summary & coverage badges.
- `tests/leads/plan-summary.spec.ts`: New Playwright E2E test.

### Testing Standards Summary
- **Backend:** `pytest nowing_backend/tests/unit/lead_intelligence/test_campaign_plan.py` with 100% assertions on coverage badges, quality labels, cost calculations, and fallback warnings.
- **Frontend Contract:** Biome formatting & strict TypeScript compilation (`pnpm exec tsc --noEmit`).
- **E2E Browser:** Playwright test verifying that `PlanSummaryCard` renders coverage quality badges, warns on unsupported locations or insufficient credits, and handles the smoke test trigger.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5 (`claude-sonnet-5[1m]`)

### Debug Log References
- Extracted requirements from `_bmad-output/planning-artifacts/epics.md` lines 3287–3302.
- Aligned with `sprint-change-proposal-customer-location-profile-pre-flight-plan-2026-08-29.md`.
- Completed validation against `checklist.md`, resolving dual location drift, backward compatibility, and credit check requirements.

### Completion Notes List
- Comprehensive story file enriched with 5 acceptance criteria, 6 structured tasks/subtasks, concrete Python/TypeScript schemas, backward compatibility guarantees, and UI/E2E testing specifications.

### File List
- `_bmad-output/implementation-artifacts/stories/26-27-pre-flight-lead-plan-summary-plansummarycard.md`

### Review Findings

Generated by `bmad-code-review` on 2026-09-05 13:45.

#### decision-needed
- [x] [Review][Decision] Smoke test scope — `PlanSummaryCard` currently has no smoke-test execution flow at all (AC-4 missing). Implement smoke test in Story 26.27 or leave for Story 26.29?

#### patch
- [x] [Review][Patch] `executeCampaign` missing in `leads-api.service.ts` — `nowing_web/lib/apis/leads-api.service.ts:185`
- [x] [Review][Patch] `icpConfigSchema`/`campaignCreateInputSchema` missing `location_profile` — `nowing_web/contracts/types/campaign.types.ts:30-41`
- [x] [Review][Patch] `LocationSelector.onChange` does not call `builder.setLocationProfile` — `nowing_web/components/leads/campaign-builder/steps/IcpBuilderStep.tsx:181`
- [x] [Review][Patch] `buildPlanSpec` omits `location_profile` — `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts:182`
- [x] [Review][Patch] `PlanSummaryCard` missing smoke-test trigger and CTA transition — `nowing_web/components/leads/PlanSummaryCard.tsx`
- [x] [Review][Patch] `PlanSummaryCard` missing credit balance check via `currentUserAtom` — `nowing_web/components/leads/PlanSummaryCard.tsx`
- [x] [Review][Patch] `PlanSummaryCard` missing intent badges, location summary, `location_type` badge — `nowing_web/components/leads/PlanSummaryCard.tsx`
- [x] [Review][Patch] `PlanSummaryCard` source list should be expandable accordion — `nowing_web/components/leads/PlanSummaryCard.tsx`
- [x] [Review][Patch] Coverage chip color mapping wrong (medium=sky, low=amber) — `nowing_web/components/leads/PlanSummaryCard.tsx:100-120`
- [x] [Review][Patch] `PlanSummaryCard` missing `inRightCanvas?: boolean` prop — `nowing_web/components/leads/PlanSummaryCard.tsx:18`
- [x] [Review][Patch] Wizard does not sync plan to `activeCampaignPlanAtom`/`activePlanSpecAtom` — `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts:1099`
- [x] [Review][Patch] `LaunchScheduleStep.onApplyPlan` saves draft instead of executing — `nowing_web/components/leads/campaign-builder/steps/LaunchScheduleStep.tsx:965`
- [x] [Review][Patch] `_estimate_cost` reads non-existent top-level `auto_unlock_verified_phones` — `nowing_backend/app/lead_intelligence/campaign/planner.py:552`
- [x] [Review][Patch] `planner.create_preflight_plan` imports `CampaignPlanResponse` from route layer — `nowing_backend/app/lead_intelligence/campaign/planner.py:563`
- [x] [Review][Patch] `plan-summary.spec.ts` is not a real Playwright E2E test — `nowing_web/tests/leads/plan-summary.spec.ts`
- [x] [Review][Patch] Plan API payload lacks `workspace_id` in body vs `CampaignSpec` requires it — `nowing_web/lib/apis/leads-api.service.ts:185-195` / `nowing_backend/app/routes/campaign_routes.py:97-111`

#### defer
- [x] [Review][Defer] Sprint status marked `done` prematurely for 26-27 — `sprint-status.yaml:214` (deferred to status sync)

### Real API & E2E Verification Record (2026-09-05)
1. **Real API Integration Testing:**
   - Ran `test_campaign_plan_api.py` against live PostgreSQL and FastAPI router.
   - `test_preflight_plan_with_location_profile_and_coverage`: PASSED (validated location coverage badges, score mapping, and cost calculation).
   - `test_smoke_test_execution_persist_false`: PASSED (executed real multi-source lead gen orchestrator with `limit=5` and `persist=false`).
2. **Playwright MCP Browser Control:**
   - Navigated live browser session to `http://localhost:3000/dashboard/799/new-chat?mode=leads`.
   - Verified Right-Canvas Origami split-view opens with "Pre-Flight Plan" tab.
   - Verified `PlanSummaryCard` renders with reactive plan data, location coverage chips (emerald/sky/amber/rose), credit balance calculation, and smoke test CTA.
   - Executed live `POST /campaigns/execute?persist=false` directly in session returning 5 discovered leads in ~5.0s.
3. **Automated Test Results:**
   - `pnpm exec tsx tests/leads/plan-summary-contract.test.ts`: PASSED
   - `pnpm exec tsx tests/leads/plan-summary-schema.test.ts`: PASSED
   - `pytest tests/unit/lead_intelligence/test_campaign_plan.py tests/integration/lead_intelligence/test_campaign_plan_api.py`: 9 passed.
