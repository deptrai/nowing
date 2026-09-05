---
title: 'Story 26.27: Pre-Flight Lead Plan Summary & PlanSummaryCard'
type: 'feature'
created: '2026-09-05'
status: 'completed'
baseline_commit: 7c8ebf3595498819d2fb29ced9788a9aa20fdd21
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-26-context.md
  - _bmad-output/implementation-artifacts/stories/26-27-pre-flight-lead-plan-summary-plansummarycard.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sales rep không thể xem trước chi tiết kế hoạch lead (phân bổ nguồn, chất lượng coverage theo địa bàn, chi phí tín dụng, cảnh báo rủi ro) trước khi chiến dịch chạy. Điều này dẫn đến chiến dịch cấu hình thiếu, tốn credit vô ích, hoặc phải launch mới phát hiện lỗi.

**Approach:** Bổ sung `POST /campaigns/plan` trả về `CampaignPlanResponse` phong phú với `source_allocations`, `warnings`, `estimated_cost_micros/vnd`; xây `PlanSummaryCard` hiển thị trong Campaign Builder Step 3, Quickstart Playbook Step 5 và Right-Canvas `plan` mode; tích hợp smoke test 5 lead không persist trước khi launch đầy đủ.

## Boundaries & Constraints

**Always:**
- `LeadGenPlanner.plan_from_campaign(spec)` phải giữ nguyên signature `tuple[list[SubTaskPlan], list[str]]` để không phá vỡ caller cũ.
- Bọc `create_preflight_plan(spec)` trả về `CampaignPlanResponse` mới; `plan_campaign` route gọi method này.
- `estimated_cost_vnd = max_total_leads × (5000 nếu auto_unlock else 1500)`; `estimated_cost_micros = cost_vnd × 40`.
- Coverage quality mapping: `>=0.9 high`, `0.6–0.9 medium`, `0.3–0.6 low`, `<0.3 none`; màu chip: emerald/sky/amber/rose.
- `PlanSummaryCard` sử dụng `currentUserAtom` để kiểm tra số dư tín dụng và cảnh báo khi `estimated_cost_micros > credit_micros_balance`.
- Cập nhật `activePlanSpecAtom` khi wizard thay đổi location/sources để Right-Canvas `plan` mode tự đồng bộ.

**Ask First:**
- Nếu muốn thay đổi mô hình giá (ví dụ: thêm tier) hoặc thay `cost_per_lead` mặc định.
- Nếu muốn hiển thị PlanSummaryCard ở bất kỳ màn hình nào khác ngoài Campaign Builder, Quickstart Playbook và Right-Canvas.
- Nếu muốn cho phép smoke test số lượng khác 5.

**Never:**
- Không đổi schema `CampaignPlanResponse` cũ thành incompatible (giữ `campaign_name`, `workspace_id`, `total_planned_sources`, `expected_sources`, `subtasks`).
- Không chạy `docker compose` start BE/FE; chỉ test local.
- Không triển khai production deploy.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | `CampaignSpec` có `LocationProfile` hợp lệ, adapter phù hợp | `CampaignPlanResponse` với `source_allocations` có coverage badge, `estimated_reachable_leads`, `estimated_cost_vnd/micros`, `warnings` rỗng | N/A |
| LOCATION_FALLBACK | Không adapter nào `supported_provinces` chứa tỉnh mục tiêu | `warnings` chứa `location_coverage_fallback`; source có quality `none` hoặc `low`; vẫn trả về fallback adapter | Không throw; UI hiển thị banner cảnh báo |
| INSUFFICIENT_CREDITS | `estimated_cost_micros > currentUser.credit_micros_balance` | `PlanSummaryCard` render banner insufficient credits; disable CTA Launch | Vẫn cho phép Smoke Test; không chặn plan API |
| SMOKE_TEST | Click "Chạy thử 5 lead" | Gọi `POST /campaigns/execute?persist=false` với `max_total_leads=5`; card chuyển loading → hiển thị actual leads/cost; CTA chuyển thành "Chạy đầy đủ" / "Chỉnh sửa" | Nếu API lỗi, hiển thị toast error và giữ trạng thái edit |
| EMPTY_SOURCES | `target_sources` rỗng và `resolve_adapters_for_campaign` không tìm được adapter | `total_planned_sources=0`, `source_allocations=[]`, `estimated_reachable_leads=0`, warning nguồn trống | UI hiển thị thông báo yêu cầu chọn nguồn |
| RIGHT_CANVAS_MIRROR | Chuyển `CanvasMode` sang `plan` | `DynamicRightPanelCanvas` render `PlanSummaryCard` từ `activePlanSpecAtom` | Nếu `activePlanSpecAtom` null, hiển thị empty state |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/lead_intelligence/campaign/schemas.py` -- thêm `SourcePlanAllocation`, làm giàu `CampaignPlanResponse`.
- `nowing_backend/app/lead_intelligence/campaign/planner.py` -- thêm `create_preflight_plan(spec)`; giữ `plan_from_campaign` cũ.
- `nowing_backend/app/lead_intelligence/adapters/registry.py` -- `calculate_location_coverage_score` (dòng 442), `resolve_adapters_for_campaign` (dòng 518) dùng để tính composite score và fallback.
- `nowing_backend/app/lead_intelligence/adapters/base.py` -- `LeadSourceAdapter` có `supported_provinces`, `coverage_quality_by_location`, `last_execution_status` (dòng 210–212).
- `nowing_backend/app/routes/campaign_routes.py` -- route `POST /{workspace_id}/campaigns/plan` gọi `create_preflight_plan`; route `execute` dùng `persist=false` cho smoke test.
- `nowing_backend/tests/unit/lead_intelligence/test_campaign_plan.py` -- bài test mới kiểm tra coverage score, quality label, warning.
- `nowing_web/contracts/types/campaign.types.ts` -- bổ sung `sourcePlanAllocationSchema`, `campaignPlanResponseSchema`, `CampaignPlanResponse` type.
- `nowing_web/contracts/types/leads.types.ts` -- `locationProfileSchema` (dòng 277) dùng để validate `LocationProfile`.
- `nowing_web/lib/apis/leads-api.service.ts` -- thêm `planCampaign` và `executeCampaign`.
- `nowing_web/components/leads/campaign-builder/types.ts` -- thêm `locationProfile` vào `CampaignBuilderState`.
- `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts` -- thêm state + setter `locationProfile`, đồng bộ vào `CampaignCreateInput`.
- `nowing_web/components/leads/campaign-builder/steps/IcpBuilderStep.tsx` -- `LocationSelector` lưu `LocationProfile` qua `setLocationProfile` thay vì chỉ push text.
- `nowing_web/components/leads/campaign-builder/steps/LaunchScheduleStep.tsx` -- thay card tóm tắt tĩnh bằng `PlanSummaryCard`.
- `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx` -- Step 2 dùng `LocationSelector`, Step 5 dùng `PlanSummaryCard`.
- `nowing_web/atoms/leads/leads-canvas.atoms.ts` -- thêm `"plan"` vào `CanvasMode`, tạo `activePlanSpecAtom`.
- `nowing_web/components/leads/DynamicRightPanelCanvas.tsx` -- thêm tab/mode `plan`, render `PlanSummaryCard` khi `activeMode === "plan"`.
- `nowing_web/components/leads/PlanSummaryCard.tsx` -- component mới: header, location badge, source grid, coverage chips, accordion, warning banner, cost balance, smoke test CTA.
- `nowing_web/lib/geo/vietnam-divisions.ts` -- `buildLocationSummary` (dòng 264) dùng để format chuỗi địa bàn.
- `nowing_web/tests/leads/plan-summary.spec.ts` -- E2E Playwright test mới.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/lead_intelligence/campaign/schemas.py` -- định nghĩa `SourcePlanAllocation` và làm giàu `CampaignPlanResponse` với `source_allocations`, `estimated_reachable_leads`, `estimated_cost_micros/vnd`, `warnings` -- để BE trả về đầy đủ metadata cho plan preview.
- [x] `nowing_backend/app/lead_intelligence/campaign/planner.py` -- thêm `create_preflight_plan(spec)` tính coverage score/quality, allocation, cost, warning; giữ `plan_from_campaign` cũ -- bảo toàn caller hiện có.
- [x] `nowing_backend/app/routes/campaign_routes.py` -- cập nhật `POST /campaigns/plan` gọi `create_preflight_plan` và trả `CampaignPlanResponse`; `execute` route hỗ trợ `persist=false` -- cung cấp API cho smoke test.
- [x] `nowing_backend/tests/unit/lead_intelligence/test_campaign_plan.py` -- viết unit test cho coverage score mapping, fallback warning, cost calculation -- đảm bảo logic pre-flight đúng.
- [x] `nowing_web/contracts/types/campaign.types.ts` -- bổ sung `sourcePlanAllocationSchema` và `campaignPlanResponseSchema` -- type-safe cho API plan.
- [x] `nowing_web/lib/apis/leads-api.service.ts` -- thêm `planCampaign` và `executeCampaign` -- client gọi BE.
- [x] `nowing_web/components/leads/campaign-builder/types.ts` + `use-campaign-builder.ts` -- thêm `locationProfile` state, setter và đưa vào payload -- loại bỏ dual location state drift.
- [x] `nowing_web/components/leads/campaign-builder/steps/IcpBuilderStep.tsx` -- `LocationSelector` cập nhật `locationProfile` thay vì chỉ push `location_text` -- duy trì profile đầy đủ.
- [x] `nowing_web/components/leads/campaign-builder/steps/LaunchScheduleStep.tsx` -- thay thế right card tĩnh bằng `PlanSummaryCard` -- hiển thị plan preview phản ứng.
- [x] `nowing_web/components/assistant-ui/quickstart-playbook-builder.tsx` -- Step 2 dùng `LocationSelector`, Step 5 dùng `PlanSummaryCard` + smoke test flow -- thống nhất trải nghiệm playbook.
- [x] `nowing_web/atoms/leads/leads-canvas.atoms.ts` -- thêm `CanvasMode` `"plan"` và `activePlanSpecAtom` -- cơ sở Right-Canvas mirror.
- [x] `nowing_web/components/leads/DynamicRightPanelCanvas.tsx` -- thêm tab `plan` và render `PlanSummaryCard` khi `activeMode === "plan"` -- Right-Canvas persistent mirror.
- [x] `nowing_web/components/leads/PlanSummaryCard.tsx` -- tạo component với header, location badge, source coverage grid/accordion, warning banner, cost balance, smoke test CTA -- giao diện chính của story.
- [x] `nowing_web/tests/leads/plan-summary.spec.ts` -- viết Playwright E2E kiểm tra badge coverage, warning, credit alert, smoke test flow -- bảo vệ hành trình người dùng.

**Acceptance Criteria:**
- [x] Given `CampaignSpec` có `LocationProfile` hợp lệ, khi gọi `POST /campaigns/plan`, thì backend trả về `CampaignPlanResponse` với `source_allocations` có `location_coverage_quality`, `location_coverage_score`, `supported_provinces`, `status`, `degraded_reason`, `estimated_reachable_leads`, `estimated_cost_micros`, `estimated_cost_vnd`, `warnings`.
- [x] Given `PlanSummaryCard` render ở Step 3 Campaign Builder hoặc Step 5 Quickstart Playbook, khi plan loaded, thì hiển thị tên chiến dịch, badge intent, location summary, source grid với coverage chip đúng màu, cost estimate, cảnh báo insufficient credits khi cần.
- [x] Given Right-Canvas đang ở `plan` mode, khi `activePlanSpecAtom` cập nhật, thì `PlanSummaryCard` render mirror không cần reload.
- [x] Given user click "Chạy thử 5 lead", khi smoke test chạy xong, thì card hiển thị actual leads/cost, CTA chuyển thành "Chạy đầy đủ" và "Chỉnh sửa kế hoạch".
- [x] Given user click "Quay lại" ở Step cuối, khi navigate back, thì wizard giữ nguyên tất cả input đã chọn.

## Spec Change Log

## Design Notes

`PlanSummaryCard` cần nhận prop `plan` kiểu `CampaignPlanResponse | null` và `inRightCanvas?: boolean` để tái sử dụng trong wizard lẫn Right-Canvas. Khi `inRightCanvas=true`, component thu gọn header, bỏ CTA footer, giữ accordion coverage. Right-Canvas sync thông qua Jotai: wizard cập nhật `activePlanSpecAtom` sau mỗi lần `planCampaign` trả kết quả hoặc khi state thay đổi ở Step 2/3.

Ví dụ coverage chip mapping:

```typescript
const COVERAGE_COLORS = {
  high:   { badge: "default",  class: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30" },
  medium: { badge: "secondary", class: "bg-sky-500/10 text-sky-500 border-sky-500/30" },
  low:    { badge: "outline",   class: "bg-amber-500/10 text-amber-500 border-amber-500/30" },
  none:   { badge: "destructive", class: "bg-rose-500/10 text-rose-500 border-rose-500/30" },
};
```

Cost calculation BE:

```python
cost_per_lead = 5000 if spec.source_budget_config.auto_unlock_verified_phones else 1500
estimated_cost_vnd = spec.max_total_leads * cost_per_lead
estimated_cost_micros = estimated_cost_vnd * 40
```

## Verification

**Commands:**
- `pytest nowing_backend/tests/unit/lead_intelligence/test_campaign_plan.py -v` -- expected: tất cả assertions pass (coverage score, quality label, fallback warning, cost).
- `pnpm exec tsc --noEmit -p nowing_web/tsconfig.json` -- expected: không còn lỗi type sau khi thêm `PlanSummaryCard`, `campaignPlanResponseSchema`, `activePlanSpecAtom`.
- `pnpm exec biome check --files-ignore-unknown=true nowing_web/components/leads/PlanSummaryCard.tsx` -- expected: định dạng + lint sạch.
- `pnpm exec playwright test nowing_web/tests/leads/plan-summary.spec.ts` -- expected: E2E pass.

**Manual checks (if no CLI):**
- Mở Campaign Builder, chọn Location ở Step 1, chuyển Step 3, kiểm tra `PlanSummaryCard` hiển thị source với coverage badge.
- Chuyển Right-Canvas sang tab Plan, xác nhận mirror đồng bộ khi thay đổi địa bàn ở Step 1.
