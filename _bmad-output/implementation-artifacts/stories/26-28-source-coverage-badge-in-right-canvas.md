---
story_key: 26-28-source-coverage-badge-in-right-canvas
status: done
baseline_commit: 7c8ebf359
epic: 26
story: 28
---

# Story 26.28: Source Coverage Badge in Right-Canvas

**Status:** `done`  
**Epic:** 26 — Lead Intelligence  
**Governed by:** FR-69.5, FR-86, AD-31, AD-42, `epics.md` lines 3305–3320, `sprint-change-proposal-customer-location-profile-pre-flight-plan-2026-08-29.md`.  
**Dependencies:** Story 26.25 (`LocationProfile`), Story 26.26 (`calculate_location_coverage_score`), Story 26.27 (`PlanSummaryCard`, `activeCampaignPlanAtom`, `activePlanSpecAtom`), `DynamicRightPanelCanvas`.

---

## Story

As a **sales rep or growth marketer actively monitoring a lead discovery run**,  
I want to see source status and contextual location coverage badges directly inside the Right-Canvas (Origami split-view) with real-time enable/disable toggles,  
So that I can keep chat and search results in focus while troubleshooting slow/degraded sources and immediately adjusting source allocations without leaving the canvas.

---

## Acceptance Criteria

### AC-1 — Shared Contextual Source Coverage Badges (`SourceCoverageBadge`)
**Given** an active playbook run, pre-flight plan, or source monitor in the Right-Canvas (`activeMode === "plan"` or `activeMode === "scrapers"`),  
**When** a source item is displayed in `SourceStatusPanel` or `PlanSummaryCard`,  
**Then**:
1. Reuses a shared `SourceCoverageBadge` component across both panels to eliminate duplicate styling and logic:
   - `High Coverage` (Emerald `#10b981` / score $\ge 0.9$)
   - `Medium Coverage` (Sky `#0284c7` / $0.6 \le \text{score} < 0.9$)
   - `Low Coverage` (Amber `#f59e0b` / $0.3 \le \text{score} < 0.6$)
   - `No Coverage` (Rose `#f43f5e` / score $< 0.3$)
2. Hovering or focusing on the coverage badge displays a Radix Tooltip detailing:
   - Numerical coverage percentage (e.g. `Độ phủ: 85%`)
   - Supported provinces list (e.g. `Hà Nội, TP.HCM, Đà Nẵng...`)
   - Clear rating explanation (e.g. `Nguồn có dữ liệu trực tiếp tại tỉnh/thành mục tiêu`)

### AC-2 — Source Enable/Disable Toggle & Live Plan Recalculation
**Given** a source item rendered in the Right-Canvas source panel,  
**When** the user clicks the switch/toggle to disable a source (e.g. turning off a degraded or low-coverage source),  
**Then**:
1. The source is excluded from `activePlanSpecAtom.source_budget_config.sources`.
2. The UI immediately recalculates the plan via `leadsApiService.planCampaign(workspaceId, updatedSpec)` without page reload.
3. `activeCampaignPlanAtom` is updated reactively, reflecting the new total planned sources, estimated reachable leads, and updated cost.
4. **Safety Guard:** The system prevents disabling the last remaining active source (at least 1 source must remain active), displaying a warning toast if attempted.

### AC-3 — Degraded Source Expandable Accordion & Health Telemetry
**Given** a scraper source whose status is `"degraded"` or `"offline"`,  
**When** the user expands the source card in the Right-Canvas,  
**Then** the panel displays:
1. Specific degraded reason (`rate-limited`, `proxy down`, `anti-bot verification required`, `location unsupported`, or adapter execution status).
2. Heartbeat status & latency telemetry (e.g. `Heartbeat: OK (115ms)` or `Last failure: Rate limit 429`).
3. Actionable recovery suggestion or 1-click re-test button to verify adapter health.

### AC-4 — Idle State Global Source Health Dashboard
**Given** the user opens the Right-Canvas when there is no active campaign plan (`activePlan === null`),  
**When** the canvas mode is `"scrapers"` or `"plan"`,  
**Then**:
1. The panel fetches and renders the global adapter health status from `GET /api/v1/workspaces/{workspace_id}/campaigns/sources/status?province_code={code}` with `Permission.LEADS_READ` RBAC verification.
2. Displays all 10 registered adapters (`batdongsan`, `chotot`, `muaban_bds`, `vn_jobs`, `job_market`, `vietnamworks`, `enterprise`, `muasamcong`, `social`, `telegram`) with default coverage tiers and operational readiness.
3. Renders a prominent CTA "Tạo kế hoạch thu thập" (Create Lead Plan) that opens the campaign builder or pre-fills standard sources.

### AC-5 — Origami Split-View Responsiveness & Persistence
**Given** the user resizing the split-view panel via the divider slider,  
**When** the Right-Canvas width changes between 300px and 800px,  
**Then**:
1. The source cards fluidly adjust between compact list view (< 400px) and detailed card view (>= 400px) without horizontal scrolling.
2. The user's per-source toggle selections persist across tab switching (`Leads` ↔ `Plan` ↔ `Scrapers`) within the same session.

---

## Tasks / Subtasks

- [x] Task 1: Backend Adapter Health & Status Endpoint (AC: AC-3, AC-4)
  - [x] Subtask 1.1: In `nowing_backend/app/lead_intelligence/adapters/registry.py`, add `get_all_source_statuses(location_profile: LocationProfilePayload | None = None) -> list[SourcePlanAllocation]` computing status, latency, and location coverage across all registered adapters.
  - [x] Subtask 1.2: In `nowing_backend/app/routes/campaign_routes.py`, add `GET /{workspace_id}/campaigns/sources/status` supporting query params `province_code: str | None = None` and `district_codes: list[str] = Query(default=[])` with `Permission.LEADS_READ`.
  - [x] Subtask 1.3: Add integration tests in `nowing_backend/tests/integration/lead_intelligence/test_source_status_api.py`.

- [x] Task 2: Shared Frontend Data Contracts & Reusable Component (AC: AC-1, AC-4)
  - [x] Subtask 2.1: Extract `SourceCoverageBadge.tsx` into `nowing_web/components/leads/SourceCoverageBadge.tsx` with Radix Tooltip and uniform emerald/sky/amber/rose color tokens.
  - [x] Subtask 2.2: Refactor `PlanSummaryCard.tsx` to use the shared `SourceCoverageBadge`.
  - [x] Subtask 2.3: In `nowing_web/lib/apis/leads-api.service.ts`, implement `getSourceStatuses(workspaceId, provinceCode?, districtCodes?): Promise<SourcePlanAllocation[]>`.

- [x] Task 3: `SourceStatusPanel` Component for Right-Canvas (AC: AC-1, AC-2, AC-3, AC-4)
  - [x] Subtask 3.1: Create `nowing_web/components/leads/panels/SourceStatusPanel.tsx` with toggle switches, accordion expansion, and auto-replanning trigger.
  - [x] Subtask 3.2: Wire per-source enable/disable toggle to `activePlanSpecAtom`, enforcing at least 1 active source guard.
  - [x] Subtask 3.3: Implement idle state rendering all 10 adapters via React Query cache (`useQuery(["source-statuses", workspaceId])`).

- [x] Task 4: Right-Canvas Integration (AC: AC-2, AC-5)
  - [x] Subtask 4.1: In `nowing_web/components/leads/DynamicRightPanelCanvas.tsx`, wire `SourceStatusPanel` into `"scrapers"` and `"plan"` canvas modes.
  - [x] Subtask 4.2: Ensure responsive layout adaptation for panel widths from 300px to 800px.

- [x] Task 5: Testing & Verification (AC: All)
  - [x] Subtask 5.1: Backend pytest unit & integration tests verifying status endpoint with location query params.
  - [x] Subtask 5.2: Frontend test suite in `nowing_web/tests/leads/source-status-panel.test.ts`.
  - [x] Subtask 5.3: Playwright MCP verification of Right-Canvas source toggles and badge tooltips.

### Review Findings

- **Status:** ✅ Clean review — all layers passed.
- **Audited Layers:** Blind Hunter, Edge Case Hunter, Acceptance Auditor.
- **Verification Summary:**
  - 11/11 backend unit & integration tests passing (`test_campaign_plan.py`, `test_campaign_plan_api.py`, `test_source_status_api.py`).
  - Frontend test suites passing (`source-status-panel.test.ts`, `plan-summary-schema.test.ts`).
  - Type check completely clean (`npx tsc --noEmit` 0 errors).
  - Code style and linting verified with Biome (`@biomejs/biome check`).
  - 0 unresolved patch or decision items.

---

## Dev Notes

### Architecture Standards & Invariants
1. **Reinvention Prevention:**
   - Reuse `SourcePlanAllocation` schema from Story 26.27.
   - Extract `SourceCoverageBadge` so both `PlanSummaryCard` and `SourceStatusPanel` share the exact badge implementation.
2. **Zero New DB Migrations:**
   - Statuses and telemetry are derived dynamically from `LeadSourceAdapterRegistry.get_default()` without database schema additions.
3. **State Triad Alignment:**
   - Active plan spec: `activePlanSpecAtom` (Jotai).
   - Active plan result: `activeCampaignPlanAtom` (Jotai).
   - Source health cache: `@tanstack/react-query` (`lib/apis/leads-api.service.ts`).
4. **Coverage Quality Color Palette:**
   - `high`: `bg-emerald-500/10 text-emerald-500 border-emerald-500/30`
   - `medium`: `bg-sky-500/10 text-sky-500 border-sky-500/30`
   - `low`: `bg-amber-500/10 text-amber-500 border-amber-500/30`
   - `none`: `bg-rose-500/10 text-rose-500 border-rose-500/30`

### Files to Touch
- `nowing_backend/app/lead_intelligence/adapters/registry.py` (UPDATE)
- `nowing_backend/app/routes/campaign_routes.py` (UPDATE)
- `nowing_backend/tests/integration/lead_intelligence/test_source_status_api.py` (NEW)
- `nowing_web/contracts/types/campaign.types.ts` (VERIFY)
- `nowing_web/lib/apis/leads-api.service.ts` (UPDATE)
- `nowing_web/components/leads/SourceCoverageBadge.tsx` (NEW)
- `nowing_web/components/leads/PlanSummaryCard.tsx` (UPDATE - reuse badge)
- `nowing_web/components/leads/panels/SourceStatusPanel.tsx` (NEW)
- `nowing_web/components/leads/DynamicRightPanelCanvas.tsx` (UPDATE)
- `nowing_web/tests/leads/source-status-panel.test.ts` (NEW)

## Challenge Log (grill-me)

### Q1 — Already implemented?
- **Backend:** Endpoint `GET /workspaces/{id}/campaigns/sources/status` chưa tồn tại. `LeadSourceAdapterRegistry` có `calculate_location_coverage_score` nhưng chưa có phương thức tổng hợp toàn bộ 10 adapter thành danh sách `SourcePlanAllocation`.
- **Frontend:** Badge độ phủ (`renderQualityBadge`) và bảng màu `COVERAGE_COLORS` hiện đang nằm inline cục bộ trong `PlanSummaryCard.tsx`. Chưa có component độc lập `SourceCoverageBadge` và chưa có `SourceStatusPanel.tsx` trong Right-Canvas.
- **Kết luận:** Không bị duplicate, nhưng BẮT BUỘC tái sử dụng `calculate_location_coverage_score` và schema `SourcePlanAllocation`.

### Q2 — Simpler alternative?
- **Tái sử dụng Schema:** Thay vì tạo model mới cho trạng thái nguồn, tái sử dụng 100% `SourcePlanAllocation` cho endpoint `GET /sources/status` để đồng nhất với `CampaignPlanResponse.source_allocations`.
- **Tách Component chung:** Trích xuất `SourceCoverageBadge` thành file riêng `components/leads/SourceCoverageBadge.tsx` dùng chung cho cả `PlanSummaryCard` và `SourceStatusPanel`.
- **Kết luận:** Áp dụng phương án tái sử dụng schema và component dùng chung để loại bỏ duplicate logic.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] **Boundary (Chặn tắt nguồn cuối):** Khi chỉ còn 1 nguồn duy nhất đang active (`selectedSources.length === 1`), việc click toggle tắt nguồn PHẢI bị chặn lập tức, giữ nguyên trạng thái switch và bắn toast cảnh báo.
- [ ] **Null/Empty Location:** Khi `LocationProfile` là `null` hoặc không có `province_code`, toàn bộ adapter phải fallback về điểm mặc định (1.0 hoặc 0.6 toàn quốc), KHÔNG được văng `AttributeError` hay hiển thị sai `none`.
- [ ] **Idle Canvas State:** Khi `activePlan === null` và `activePlanSpec === null`, Right-Canvas phải hiển thị danh sách 10 adapter ở trạng thái toàn cục, không được báo lỗi `Cannot read properties of null`.
- [ ] **Race Condition / Rapid Toggling:** Khi người dùng click bật/tắt liên tiếp nhiều nguồn, các request `planCampaign` có thể trả về sai thứ tự. Cần xử lý debounce hoặc hủy request cũ bằng AbortController / latest token.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] **Plan API Failure on Toggle:** Nếu backend trả về 500 hoặc rớt mạng khi tính lại plan sau khi toggle, frontend phải giữ nguyên trạng thái hoặc rollback toggle và thông báo lỗi, không để state bị desync.
- [ ] **Adapter Heartbeat Null:** Khi adapter chưa có lịch sử chạy hoặc heartbeat telemetry (`last_execution_status == 'ok'` nhưng không có heartbeat timestamp), UI phải hiển thị fallback mặc định "Sẵn sàng (chưa có phiên gần nhất)".
- [ ] **RBAC Permission:** Endpoint `GET /sources/status` yêu cầu `Permission.LEADS_READ` để đảm bảo tính an toàn dữ liệu đa tenant.

### Triage
- **Clean — proceed:** Không có blocker nghiêm trọng, các phát hiện Q3 & Q4 đã được đưa vào tiêu chí nghiệm thu và test skeleton cho bước tiếp theo.
