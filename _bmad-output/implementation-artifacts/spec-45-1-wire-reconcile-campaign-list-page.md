---
title: 'Epic 45.1 — Wire-contract reconcile + Campaign list page'
type: 'feature'
created: '2026-11-18'
status: 'ready-for-dev'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-44-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'  # Epic 45 section ~5945-6021
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Campaign list/detail surface không tồn tại (FE `listCampaigns`/`getCampaign`/`pauseCampaign`/`updateCampaign` zero call sites ngoài `use-campaign-builder.ts`) và wire drift FE↔backend đã xác nhận ở review: `listCampaigns` gửi `limit/offset` nhưng backend đọc `page/page_size` → **pagination âm thầm chết**; `campaignStatusSchema` thiếu `'archived'`; `launchCampaign` parse `campaignSchema` vs run-shape; `campaign_to_response`/`_run_to_response` thiếu fields detail page cần; FE `campaignSchema` thiếu `direction`/`supply_criteria`/`last_run_at`.

**Approach:** Vá contract hai phía theo pin đã verify (Epic 45 G-2→G-5), rồi dựng list page + nav entry. Backend mapper mở rộng là điều kiện để 45.2/45.3 sau này không phải vá lại.

## Boundaries & Constraints

**Always:**

- **FE contracts** (`nowing_web/contracts/types/campaign.types.ts`):
  - `campaignStatusSchema` += `'archived'` → đủ 7 values `{draft,scheduled,running,paused,completed,failed,archived}` khớp `CampaignStatus` backend (`app/db/enums.py`).
  - `campaignSchema` += fields (giữ backward-safe — `direction` dùng `.default("demand")` như `status`, còn lại optional/nullable): `direction: z.enum(["demand","supply"]).default("demand")`, `supply_criteria` (reuse schema supply đã có trong file nếu tồn tại — `campaignCreateInputSchema` Epic 43.5 đã định nghĩa; KHÔNG định nghĩa lại), `source: z.enum(["created","execute","api"]).optional()`, `next_run_at: z.string().nullable().optional()`, `schedule_frequency: z.string().nullable().optional()`, `schedule_cron: z.string().nullable().optional()`, `max_runs: z.number().nullable().optional()`, `skipped_by_quota: z.number().optional()`, `last_run_at: z.string().nullable().optional()`.
  - **NEW** `campaignRunSchema = z.object({ id: z.string().uuid(), campaign_id: z.string().uuid(), status: z.string(), trigger: z.string(), started_at: z.string().nullable().optional(), finished_at: z.string().nullable().optional(), stats: z.record(z.string(), z.any()).optional(), cost_micros: z.number().nullable().optional(), error: z.string().nullable().optional() })` + export type `CampaignRun`.
- **FE service** (`nowing_web/lib/apis/leads-api.service.ts`):
  - `listCampaigns` (~:151-164): params → `{ page?: number; page_size?: number; status?: string; include_implicit?: boolean }`; qs gửi `page`/`page_size`/`status`/`include_implicit=true` (chỉ set khi true). Vá G-4.
  - `launchCampaign` (~:232): schema `campaignSchema` → `campaignRunSchema`, return `Promise<CampaignRun>`. Backend launch trả run-shape `{id,campaign_id,status,trigger,...}` (`campaign_routes.py:601-606` — sau patch có thêm stats/cost_micros/error).
  - `pauseCampaign`/`getCampaign`/`updateCampaign`/`createCampaign`: giữ `campaignSchema` (đã đúng — pause trả campaign-shape `:634`).
- **Backend mapper** (`nowing_backend/app/lead_intelligence/services/campaign_service.py`):
  - `campaign_to_response` (:471-490) += keys: `"direction": campaign.direction`, `"source": campaign.source`, `"next_run_at"` (isoformat|None), `"schedule_frequency"`, `"schedule_cron"`, `"max_runs"`, `"skipped_by_quota": campaign.skipped_by_quota or 0`, `"supply_criteria"`: ưu tiên `input_payload.get("supply_criteria")`; nếu None mà `direction=='supply'` → lấy từ `spec_snapshot.supply_criteria` của campaign_runs MỚI NHẤT (1 query nhẹ — chỉ khi supply, tránh N+1 cho demand list); còn lại → None.
  - `_run_to_response` (`app/routes/campaign_routes.py:311-320`) += `"stats": run.stats or {}`, `"cost_micros": run.cost_micros` (`error` đã có sẵn).
  - `list_campaigns` service (`:493+`): đã có `page`/`page_size`/`status`/`include_implicit` — KHÔNG đổi.
- **List page** `nowing_web/app/dashboard/[workspace_id]/leads/campaigns/page.tsx` (NEW): server component convention (`params: Promise<{workspace_id}>` → client component `workspaceId`, `export const dynamic = "force-dynamic"` như `new/page.tsx`). Client component NEW `components/leads/campaigns/CampaignList.tsx`: bảng bằng `components/ui/table.tsx` (KHÔNG có DataTable/react-table trong repo — dùng shadcn table trực tiếp), cột: Name (link → `/leads/campaigns/{id}` — route detail của 45.2, link dựng sẵn dù trang chưa có), Status badge (7 values, màu theo convention status hiện có — archived xám), Direction (demand→label "Tìm khách hàng"/supply→"Tìm nhà cung cấp" từ i18n), Leads (collected_leads_count), Last run (last_run_at — '-' khi null), Created (created_at format ngắn). Pagination page/page_size (server-driven, nút Prev/Next + "Trang X / Y" từ total). Toggle "Hiện auto-runs" (checkbox/switch) → re-fetch `include_implicit=true`. Empty state: text + CTA button → `/leads/campaigns/new`. Loading skeleton + error state (403/500 → message rõ, retry button).
- **Nav** (`nowing_web/components/layout/providers/LayoutDataProvider.tsx:305+`): thêm navItem mới `{title: tNav("campaigns"), url: /dashboard/${workspaceId}/leads/campaigns, icon: <icon phù hợp vd Target/ListChecks>, isActive: pathname?.includes("/leads/campaigns")}` — đặt ngay sau item leads (giữ `isLeadsActive` endsWith("/leads") nguyên trạng). i18n key `campaigns` += namespace nav ở **cả en.json và vi.json** (parity test `tests/leads/i18n-parity.test.ts:14` chỉ cover en/vi — 5 locale khác KHÔNG đụng).
- **Save-flow regression** (`use-campaign-builder.ts:484-490`): sau khi `launchCampaign` đổi type → cập nhật call site; launch fail (throw/return lỗi) → toast phân biệt rõ "Tạo chiến dịch thành công, launch thất bại: {msg}" thay vì gộp chung; campaign đã tạo KHÔNG rollback.
- **Test FE**: nếu repo có vitest/jest cho contracts → thêm parse test `campaignSchema` với response có archived/supply/direction. Kiểm tra `tests/leads/` trước — nếu không có harness FE unit test thì bỏ qua, rely e2e 45.4.
- **Test backend**: `tests/unit/services/test_campaign_mapper.py` hoặc mở rộng file test campaign_service hiện có — assert keys mới trong `campaign_to_response` (direction/source/next_run_at/supply_criteria cho supply campaign qua input_payload) và `_run_to_response` có `stats`/`cost_micros`.

**Never:**

- KHÔNG đổi `list_campaigns` service signature/`_USER_SETTABLE_STATUSES`/PATCH handler (schedule fields là 45.3).
- KHÔNG định nghĩa lại supply_criteria schema nếu đã tồn tại trong campaign.types.ts.
- KHÔNG thêm DataTable/react-table dependency mới — dùng `components/ui/table.tsx`.
- KHÔNG đụng `automations/campaigns` (sequences), `webset_campaigns`, 5 locale ngoài en/vi.
- KHÔNG build detail page (45.2) — link row dựng sẵn trỏ `/leads/campaigns/{id}` dù route chưa tồn tại.
- KHÔNG optimize N+1 mapper (documented known-limitation v1).
- KHÔNG optimistic nav label khác — chỉ 1 item mới.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LIST_OK | campaigns source='created' | rows đúng cột, total/ paging server | No error expected |
| LIST_EMPTY | 0 campaign | empty state + CTA /new | No error expected |
| LIST_IMPLICIT | toggle on | gọi include_implicit=true → thấy source execute/api badge | No error expected |
| ARCHIVED_ROW | campaign status archived | parse OK, badge xám | previously zod-fail |
| SUPPLY_ROW | direction=supply | direction label nhà cung cấp; supply_criteria parse | schema mới |
| LAUNCH_SAVE | builder save+launch | CampaignRun typed, toast đúng khi launch lỗi | toast phân biệt |
| PAGE_NAV | page=2 | backend nhận page/page_size thật (đổi được kết quả) | previously ignored |
| RUN_SHAPE | launch response | campaignRunSchema parse; stats/cost_micros optional | backward-safe |
| MAPPER_SUPPLY | campaign implicit supply, input_payload thiếu | supply_criteria từ run mới nhất spec_snapshot | fallback chain |

</intent-contract>

## Code Map

- `nowing_web/contracts/types/campaign.types.ts` -- enum + campaignSchema += fields + campaignRunSchema -- MODIFY
- `nowing_web/lib/apis/leads-api.service.ts` -- listCampaigns params (:151-164), launchCampaign schema (:232-235) -- MODIFY
- `nowing_web/components/leads/campaign-builder/use-campaign-builder.ts` -- save-flow toast/type (:484-490) -- MODIFY
- `nowing_web/app/dashboard/[workspace_id]/leads/campaigns/page.tsx` -- NEW (server wrapper)
- `nowing_web/components/leads/campaigns/CampaignList.tsx` -- NEW (client: table+pagination+toggle)
- `nowing_web/components/layout/providers/LayoutDataProvider.tsx` -- nav item (:305-330) -- MODIFY
- `nowing_web/messages/{en,vi}.json` -- nav.campaigns + list-page strings -- MODIFY
- `nowing_backend/app/lead_intelligence/services/campaign_service.py` -- `campaign_to_response` (:471-490) += fields -- MODIFY
- `nowing_backend/app/routes/campaign_routes.py` -- `_run_to_response` (:311-320) += stats/cost_micros -- MODIFY
- `nowing_backend/tests/unit/services/` -- mapper tests -- NEW/MODIFY

## Tasks & Acceptance

**Execution:**
- T1 backend mapper fields + tests
- T2 FE contracts (enum/schema/runSchema) + service params/type
- T3 CampaignList page + client component + nav + i18n
- T4 save-flow regression fix
- T5 verify commands chạy xanh

**Acceptance Criteria:**
- Given campaign status `archived` trong list response, when FE parse, then zod OK + badge hiển thị
- Given `listCampaigns(ws,{page:2,page_size:5})`, when gọi, then request có `?page=2&page_size=5` và backend trả trang 2
- Given supply campaign (input_payload có supply_criteria), when `campaign_to_response`, then response chứa `direction='supply'` + `supply_criteria` + `source`
- Given `/leads/campaigns` mở, then thấy bảng/empty-state; toggle auto-runs → thêm implicit rows
- Given builder save → launch fail, then toast "tạo OK, launch lỗi" và campaign vẫn tồn tại trong list sau refresh
- Given `_run_to_response`, then trả `{id,campaign_id,status,trigger,started_at,finished_at,stats,cost_micros,error}`

## Spec Change Log

## Review Triage Log

## Design Notes

- `last_run_at`/`collected_leads_count` đã có sẵn trong mapper (`:484-489`) — chỉ thiếu ở FE schema.
- Nav icon: chọn icon phù hợp từ lucide đang import (Target/ListChecks) — convention file dùng lucide-react.
- `run.stats`/`cost_micros` nullable → `.or {}`/`None` passthrough để response ổn định.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/services/ tests/unit/routes/ -x -q` -- expected: pass (mapper tests mới + regression)
- `cd nowing_web && npx tsc --noEmit` -- expected: 0 error
- `cd nowing_web && npm test -- tests/leads/i18n-parity` hoặc `npx vitest run tests/leads/` -- expected: parity pass
- `npx next lint` hoặc build page -- expected: 0 error trên files mới
