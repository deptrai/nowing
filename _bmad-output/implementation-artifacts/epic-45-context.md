# Epic 45 Context: Campaign Productization — list/detail UI + lifecycle + schedule

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Epic 44 ship backend persistence nhưng "headless": `leads/campaigns/` chỉ có `new/`, `listCampaigns`/`getCampaign`/`pauseCampaign`/`updateCampaign` zero call sites ngoài `use-campaign-builder.ts`, và một lớp wire drift FE↔backend chưa được nối (pagination param lệch, response shape thiếu field, schedule fields unreachable qua API). Epic này sống hóa campaign surface theo chặng **Productized** (self-serve sau Concierge, trước Platform): contract reconcile FE↔backend, list page, detail/run-history, lifecycle actions (launch/pause/resume/archive), schedule editor, và e2e browser trên stack thật. Skeleton đã qua tech review 4-lens, 12/12 wire-gaps CONFIRMED.

## Stories

- Story 45.1: Wire-contract reconcile (types + API service + response mappers) + Campaign list page
- Story 45.2: Campaign detail + run history page (kèm endpoint campaign→leads)
- Story 45.3: Lifecycle actions + schedule editor (backend PATCH mở rộng)
- Story 45.4: E2E browser + ops verify (save/launch/list/schedule flow, worker/beat thật)

## Requirements & Constraints

**Wire-contract gaps đã verify (phải vá đúng quyết định đã chốt, không đổi hướng):**

- **G-1 [backend]:** `CampaignUpdateRequest` chỉ name+status → `schedule_frequency`/`schedule_cron`/`max_runs` unreachable qua API; `status='scheduled'` + `next_run_at=None` tick vô hình. Vá: PATCH += 3 fields + **recompute `next_run_at` cả khi đổi schedule fields LẪN status** (hiện chỉ recompute khi đổi status → stale bug); cron invalid → 422; `status='scheduled'` không có schedule → 422. POST create: map `launch_config.schedule_type='recurring'` + `cron_expression`/`start_time` → schedule_* scalars (builder "recurring" hiện lưu vào `input_payload` nhưng không wire — dead-on-arrival). **Decision: WIRE** — một nguồn truth = schedule_* scalars; `launch_config` chỉ là input.
- **G-2 [FE]:** `campaignStatusSchema` thiếu `'archived'` (runtime hôm nay không crash vì `safeParse` trả raw — chỉ type-unsafe + toast mơ hồ, nhưng vẫn phải thêm enum).
- **G-3 [FE+backend]:** `launchCampaign` parse `campaignSchema` nhưng backend trả run-shape `{id, campaign_id, status, trigger}`. FE += `campaignRunSchema` (id/campaign_id/status/trigger bắt buộc, còn lại optional) + đổi return type; backend `_run_to_response` += `stats`/`cost_micros`/`error` (cột đã có — chỉ expose). Đây là resolution của AI-44.1 (retro Epic 44).
- **G-4 [FE]:** `listCampaigns` gửi `limit`/`offset` nhưng backend đọc `page`/`page_size` → pagination âm thầm bị bỏ qua; thiếu param `include_implicit`. Sửa param names + thêm `include_implicit?: boolean`.
- **G-5 [backend+FE]:** `campaign_to_response` thiếu `direction`/`source`/`next_run_at`/`schedule_*`/`skipped_by_quota`/`supply_criteria` — FE `campaignSchema` cũng thiếu → detail page 45.2 không có contract. Vá cả 2 phía (mapper từ `input_payload` nếu supply, fallback `spec_snapshot`).
- **G-6 [backend]:** `_USER_SETTABLE_STATUSES` cho phép archived→scheduled tự do — vá guard `archived` → status khác → 422.

**Ràng buộc khác:**

- **Resume semantics:** không có resume endpoint, PATCH không set được `running` → **Resume = PATCH status='scheduled'** (yêu cầu đã có schedule; không có → UI disable + tooltip gợi Launch).
- 429 quota: FE hiển thị `detail` text từ server; backend optionally += `quota_reason` machine-readable (`runs_per_day`|`workspace_leads_per_day`) — nice-to-have.
- List mapper N+1 (2 query/campaign) — chấp nhận v1, ghi known-limitation. `updated_at = created_at` placeholder — note.
- i18n: key mới đồng bộ en+vi (parity test bắt pass).
- Không delete campaign (archive thay thế — chưa có API); PATCH chỉ name/status/schedule_* (no edit-spec sau create).

## Technical Decisions

- Kế thừa Epic 44 (đã ship): tables `lead_campaigns`/`campaign_runs`/`campaign_leads`; single seam `open_campaign_run` (mọi run insert qua đây, quota check trong seam: 10 runs/campaign/day + 500 leads/ws/day, vượt → 429 route / skip + `skipped_by_quota++` scheduled); implicit campaigns (`source='execute'|'api'`) ẩn mặc định, expose qua `include_implicit=true`; `next_run_at` materialized từ schedule_* scalars (không đào JSONB); meta-scheduler beat entry quét `next_run_at <= now()`.
- `campaign_leads` hiện zero reader — endpoint `GET /campaigns/{id}/leads` (45.2, paged join → leads trả field cơ bản + `role` + `created_at`) là consumer đầu tiên của junction.
- FE reconcile (45.1): `campaignSchema` += các field G-5; `campaignUpdateInputSchema` thu về khớp PATCH backend (schedule_* giữ optional, service lọc field thừa); save-flow `handleSaveCampaign` dùng `CampaignRun` return, launch fail → campaign đã tạo vẫn giữ + toast phân biệt "tạo OK, launch lỗi".
- Alembic: repo nhiều heads — chain off mainline head, không merge heads cũ (nếu có migration).
- Celery task pattern giữ nguyên từ 44 (RLS tenant context + queue riêng, không `time_limit=120`).

## UX & Interaction Patterns

- Nav: entry "Chiến dịch" top-level trong leads section; active-highlight đúng `/leads/campaigns` kể cả `/new`, `/[id]` (xử lý `isLeadsActive` endsWith).
- List page: bảng paged — name, status badge (đủ 7 value), direction label, collected_leads_count, last_run_at, created_at; empty state CTA "Tạo chiến dịch"; row → detail; toggle "Hiện auto-runs" → `include_implicit=true`.
- Detail page: header (name inline rename qua PATCH, status badge, direction, source label, `next_run_at` khi scheduled, `skipped_by_quota>0` badge); config readonly (demand → icp_config/source_budget_config; supply → supply_criteria); run history paged (status, trigger, started/finished/duration, stats, `cost_micros` label "usage" — không bill, error khi failed); tab "Leads" paged; 404/403 state rõ ràng.
- Actions theo status: draft/scheduled → Launch + Schedule; running → Pause; paused → Resume (PATCH 'scheduled', disable khi không có schedule) + Archive; completed/failed → Re-run + Archive. Confirm modal launch/archive; `isSubmitting`+Loader2 convention. Archived: badge + filter, action buttons disable.
- Schedule editor (drawer/modal): frequency HOẶC cron (client-validate cơ bản + 422 server), max_runs optional, `next_run_at` preview.
- e2e convention: Playwright sẵn, port backend **:8000** (không phải :4445), auth storageState + token helper có sẵn.

## Cross-Story Dependencies

- **45.1 là nền:** types/service/mapper reconcile phải xong trước — 45.2 render theo contract mới (direction, supply_criteria, next_run_at), 45.3 mở rộng PATCH trên nền schema đã khớp.
- 45.2 thêm endpoint backend mới (junction consumer) — depends mapper fields từ 45.1.
- 45.3 cross-stack: backend PATCH mở rộng + UI actions trên detail page của 45.2.
- 45.4 depends tất cả; carry-in **AI-44.2** (retro Epic 44): verify celery worker consume `nowing.campaigns` + beat `check-campaign-schedules` tick thật trên dev (schedule daily → quan sát run 'scheduled' tự tạo; không chạy được → ghi blocker + verify bằng invoke task trực tiếp).
- Regression e2e bắt buộc: double-click save không double-create; save-flow launch-fail toast.

## Epic 45 Non-Goals

- No `match_mode="pool"` / `corpus_scope="platform_b2b"` — Platform epic.
- No edit-spec sau create; no delete campaign (archive thay thế); no duplicate/clone.
- No charge/billing UI cho `cost_micros` — usage display only.
- No `campaign:*` PAT scope; no `automations/campaigns` (sequences); no `webset_campaigns`.
- No real-time run progress streaming, no bulk actions, no export list, no PDPD.
- No optimize N+1 list mapper v1 — known-limitation.
