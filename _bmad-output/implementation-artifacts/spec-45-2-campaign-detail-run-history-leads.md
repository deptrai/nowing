---
title: 'Epic 45.2 — Campaign detail page + run history + GET /campaigns/{id}/leads'
type: 'feature'
created: '2026-11-18'
status: 'ready-for-dev'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-45-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'  # Epic 45 ~5945-6021
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** List page (45.1) link tên campaign → `/leads/campaigns/{id}` nhưng route chưa tồn tại → 404. Junction `campaign_leads` (44.1) có **zero readers** — role `buyer`/`supplier` chỉ là write-only metadata; run history endpoint `GET /campaigns/{id}/runs` đã sẵn backend nhưng không có UI nào gọi.

**Approach:** Dựng detail page 2-tab (Runs + Leads), thêm endpoint `GET /campaigns/{id}/leads` join junction→leads (reader đầu tiên của campaign_leads — unlock queryable role). FE service bổ sung `listCampaignRuns` + `getCampaignLeads` + 2 response schemas.

## Boundaries & Constraints

**Always:**

- **Backend — NEW endpoint** `GET /{workspace_id}/campaigns/{campaign_id}/leads` trong `app/routes/campaign_routes.py` (đặt NGAY SAU `list_campaign_runs_route` ~:380, trước POST create; literal path `/{campaign_id}/leads` không xung đột routes):
  - Permission `RequirePermission(Permission.LEADS_READ.value)`, `await set_request_tenant_context(session, workspace_id=workspace_id)` (pattern :392).
  - `campaign = await _get_campaign_or_404(session, workspace_id, campaign_id)` (:325) → 404 chuẩn.
  - Query: `CampaignLead JOIN Lead ON (Lead.id == CampaignLead.lead_id AND Lead.workspace_id == CampaignLead.workspace_id)` — composite FK bắt buộc join 2 cột (`campaign_leads.lead_id` NOT NULL). Filter `CampaignLead.campaign_id == campaign.id`, order `CampaignLead.created_at.desc()`, phân trang `page`/`page_size` (ge=1 / 1-100, giống runs route :383-385).
  - Response `{items, total, limit, offset}`; item = `LeadRead.model_validate(lead).model_dump(mode="json")` merge `{"lead_role": cl.role, "run_id": str(cl.run_id) if cl.run_id else None, "added_at": cl.created_at.isoformat()}` — KHÔNG schema mới phía backend ngoài reuse `LeadRead` (`app/lead_intelligence/schemas.py:40`).
  - RLS leads có tenant+visibility policy — tenant ctx đã set; member giới hạn lead theo policy sẵn có (không override).
- **FE contracts** (`campaign.types.ts`): NEW `campaignRunListResponseSchema = z.object({items: z.array(campaignRunSchema), total: z.number(), limit: z.number(), offset: z.number()})`; NEW `campaignLeadItemSchema = z.object({id: z.string().uuid(), lead_role: z.enum(["buyer","supplier"]), run_id: z.string().uuid().nullable().optional(), added_at: z.string()}).passthrough()` — passthrough cho trường LeadRead còn lại (zod version check: nếu không hỗ trợ `.passthrough()` dùng `.catchall(z.any())`); NEW `campaignLeadListResponseSchema` cùng khung items/total/limit/offset. Export types.
- **FE service** (`leads-api.service.ts`): `listCampaignRuns(workspaceId, campaignId, {page?, page_size?})` → `GET /campaigns/{id}/runs` parse `campaignRunListResponseSchema`; `getCampaignLeads(workspaceId, campaignId, {page?, page_size?})` → `GET /campaigns/{id}/leads` parse `campaignLeadListResponseSchema`.
- **FE page** `app/dashboard/[workspace_id]/leads/campaigns/[campaign_id]/page.tsx` (NEW, server comp `params: Promise<{workspace_id, campaign_id}>`, `force-dynamic`) → client `components/leads/campaigns/CampaignDetail.tsx`:
  - Header: tên + status badge (7 status, khớp 45.1) + direction label + source badge ("auto" khi ≠created) + meta row (created_at, last_run_at, next_run_at, collected_leads_count, skipped_by_quota — hiện khi >0).
  - Config card render theo `direction`: demand → icp_config (keywords/locations/industries/min_fit_score từ `campaign.icp_config`), supply → `supply_criteria` (categories/locations/require_tax_id/min_rating/require_verified); launch_config hiển thị mode (one_off/recurring + schedule_* nếu có).
  - Tabs "Lượt chạy" (default) / "Leads" — server pagination riêng từng tab.
  - Runs tab: bảng status badge/trigger/started/finished/leads (`stats.accepted` hoặc `stats.total_accepted` — đọc key thực tế từ stats JSONB, fallback '-')/cost (`cost_micros` → hiển thị "usage" VND-approx hoặc micros raw kèm label; cost=null → '-')/error (tooltip/truncate).
  - Leads tab: bảng company_name/lead_role badge/source/added_at; empty state "Campaign chưa thu lead nào".
  - 404: campaign không tồn tại → empty state + link về list. 403 → message rõ.
- **i18n**: keys `leads.campaign_detail_*` + tab labels en/vi (parity test cover `leads.*`).
- **Breadcrumb/back**: nút "← Chiến dịch" về `/leads/campaigns`.

**Never:**

- KHÔNG lifecycle actions (launch/pause/resume/archive) — 45.3.
- KHÔNG edit config/schedule — 45.3. KHÔNG delete campaign.
- KHÔNG tạo schema backend mới cho campaign-leads ngoài reuse LeadRead + merge 3 fields.
- KHÔNG real-time/polling/auto-refresh — fetch-on-mount + nút refresh thủ công được phép.
- KHÔNG link lead row → lead detail route (route leads/{id} chưa có quy ước — chỉ hiển thị).
- KHÔNG đụng `open_campaign_run`/`execute_and_persist`/scheduler/quota.
- KHÔNG đổi `_run_to_response` nữa (45.1 đã thêm stats/cost_micros — đủ).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| DETAIL_OK | campaign tồn tại | header+config+tabs đúng | No error expected |
| DETAIL_404 | campaign_id sai | empty state + back link | 404 → UI rõ |
| RUNS_PAGED | 25 runs, page_size=20 | trang 2 hiện 5 rows | server pagination |
| LEADS_EMPTY | 0 junction | empty state riêng tab | No error expected |
| LEADS_ROLE | supply campaign | lead_role='supplier' badge | role từ junction |
| RUN_ERROR | run failed có error | hiển thị error truncated | graceful |
| COST_NULL | run chưa finalize | '-' không crash | null-safe |
| CONFIG_SUPPLY | direction=supply | render supply_criteria không icp | direction-branch |
| IMPLICIT | source='execute' | vẫn xem được detail (list ẩn nhưng direct URL OK) | No error expected |
| CROSS_WS | campaign workspace khác | 404 (RLS + workspace filter) | security |

</intent-contract>

## Code Map

- `nowing_backend/app/routes/campaign_routes.py` — += `list_campaign_leads_route` sau `list_campaign_runs_route` (:380-418); anchors `_get_campaign_or_404` :325, `set_request_tenant_context` :392 -- MODIFY
- `nowing_backend/app/models/campaigns.py` — `CampaignLead` join reference (read-only) -- READ
- `nowing_backend/app/lead_intelligence/schemas.py` — `LeadRead` :40 reuse -- READ
- `nowing_backend/tests/unit/routes/test_campaign_leads_route.py` — NEW (paged/role/404/empty/workspace isolation)
- `nowing_web/contracts/types/campaign.types.ts` — += 3 schemas/types -- MODIFY
- `nowing_web/lib/apis/leads-api.service.ts` — += `listCampaignRuns`, `getCampaignLeads` -- MODIFY
- `nowing_web/app/dashboard/[workspace_id]/leads/campaigns/[campaign_id]/page.tsx` — NEW server
- `nowing_web/components/leads/campaigns/CampaignDetail.tsx` — NEW client
- `nowing_web/messages/{en,vi}.json` — `leads.campaign_detail_*` -- MODIFY
- `nowing_web/components/leads/campaigns/CampaignList.tsx` — verify link đúng `/leads/campaigns/${campaign.id}` (đã pin 45.1) -- VERIFY

## Tasks & Acceptance

**Execution:**
- T1 backend leads endpoint + unit tests
- T2 FE schemas + service methods
- T3 detail page + CampaignDetail component + i18n
- T4 verify commands xanh

**Acceptance Criteria:**
- Given campaign có 2 runs + 3 junction leads, when GET `/campaigns/{id}/leads?page=1&page_size=10`, then `{items:3, total:3}` mỗi item có `lead_role` + `added_at` + fields LeadRead
- Given campaign workspace khác, when GET leads endpoint, then 404
- Given mở `/leads/campaigns/{id}`, then header hiển thị đủ status/direction/stats và Runs tab mặc định
- Given supply campaign, then config card render `supply_criteria` (không phải icp_config)
- Given runs tab có run failed `error='quota'`, then hiển thị lỗi không crash
- Given click tab Leads, then bảng lead_role badge đúng ('supplier' cho supply campaign)

## Spec Change Log

## Review Triage Log

## Design Notes

- `campaign_leads.created_at` = thời điểm attach (TimestampMixin) — dùng làm "added_at".
- Stats key leads-per-run: đọc từ `run.stats` JSONB — implementer kiểm tra key thực tế `persist_campaign_leads`/`finalize_campaign_run` ghi (44.1: `accepted_lead_ids` count → key có thể `accepted`/`total_accepted`/`leads_attached`); fallback '-'.
- `cost_micros` hiển thị dạng micros + label "usage" (giá trị thật = tổng token usage; chưa có pricing map → KHÔNG convert VND giả).

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/routes/test_campaign_leads_route.py tests/unit/routes/test_campaign_crud_routes.py -x -q` -- pass
- `cd nowing_web && npx tsc --noEmit` -- clean
- `npx vitest run tests/leads/i18n-parity` (hoặc node parity check nếu dev-server lock) -- parity en/vi
