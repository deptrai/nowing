---
title: 'Epic 44.2 — Campaign CRUD + launch + async run task'
type: 'feature'
created: '2026-11-18'
status: 'done'
baseline_revision: 81607ed32c089932ad180761467853a4089e1235
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-44-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-44-1-schema-opt-in-campaign-binding.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** FE `leads-api.service.ts:151-235` gọi `listCampaigns`/`getCampaign`/`updateCampaign`/`pauseCampaign`/`createCampaign`/`launchCampaign` — tất cả 404 dead; `handleSaveCampaign` (use-campaign-builder.ts:484-490) không chạy được. Campaign có bảng rồi (44.1) nhưng không có API surface.

**Approach:** Wire 6 endpoints vào `campaign_routes.py` hiện có, response mapper khớp FE `campaignSchema`, launch → `open_campaign_run` + celery task async theo `auto_refund_lead_task` pattern, `/execute` += `?async=true` cùng door.

## Boundaries & Constraints

**Always:**
- Endpoints trong `app/routes/campaign_routes.py` hiện có, prefix `/workspaces` (đã đăng ký routes/__init__.py:79,205):
  - `GET /{workspace_id}/campaigns` — paged (`page`/`page_size`, default 1/20, max 100), filter `status` theo FE enum, **default `WHERE source='created'`**, `?include_implicit=true` expose `'execute'`/`'api'` — `LEADS_READ`
  - `GET /{workspace_id}/campaigns/{campaign_id}` detail + `GET /{workspace_id}/campaigns/{campaign_id}/runs` (paged, mới nhất trước) — `LEADS_READ`
  - `POST /{workspace_id}/campaigns` — body = FE payload qua `CampaignSpec.from_payload`; lưu `input_payload` (raw dict) + `source='created'` + `created_by=auth.user_id`; response **full Campaign theo `campaignSchema`**; trùng `(workspace_id,name,direction)` → **409 + detail thân thiện tiếng Việt** (không 500) — `LEADS_WRITE`
  - `PATCH /{workspace_id}/campaigns/{campaign_id}` — update `name` + `status`; status user-settable CHỈ `{draft,scheduled,paused,archived}` (system-owned `running/completed/failed` → 422); name đổi vẫn unique-check → 409 — `LEADS_WRITE`
  - `POST /{workspace_id}/campaigns/{campaign_id}/launch` — `status=='paused'|'archived'` → 409; `open_campaign_run(campaign_id, trigger='api', session)` → `launch_campaign_run.apply_async(...)` → trả run shape `{id, campaign_id, status:'queued', ...}` — `LEADS_WRITE`. NOTE (44.1 impl fact): `open_campaign_run` đã set run `'running'` ngay khi insert — launch response map `'queued'` cho FE hoặc trả status thật; chọn 1, pin wire test.
- **Route ordering:** `/presets` + `/presets/{preset_id}` + `/reverse-icp` + `/plan` + `/execute` + `/sources/status` register TRƯỚC mọi route `/{campaign_id}` (FastAPI path precedence — `"/presets"` literal phải thắng `/{campaign_id}`).
- **Mapper:** `campaign_to_response(LeadCampaign) -> dict` trong `campaign_service.py` — ưu tiên `input_payload` giữ nguyên FE shape (`icp_config`/`source_budget_config`/`launch_config`/`sources`), fallback reconstruct từ `campaign_runs.spec_snapshot` mới nhất; `sources` min-1 theo `campaign.types.ts:45-56` — wire test conformance, backend là source-of-truth.
- **Celery task** `launch_campaign_run` trong `app/tasks/campaign_tasks.py` (NEW): `@shared_task(name="launch_campaign_run", bind=True, max_retries=1)` + `run_async_celery_task` wrap `_run()` + own `async_session_maker` + `set_request_tenant_context(session, workspace_id=...)` — pattern Y HỆT `auto_refund_lead_task` (phone_waterfall_worker.py:84-115), nếu thiếu tenant ctx thì RLS chặn insert. Body: load campaign+run (run đã `'running'` từ open_campaign_run — 44.1 impl), gọi `execute_and_persist(session, workspace_id, campaign_spec=spec_from_input_payload, campaign=campaign, campaign_run_id=run.id)`, exception → run 'failed'+error+commit., gọi `execute_and_persist(session, workspace_id, campaign_spec=spec_from_input_payload, campaign=campaign, campaign_run_id=run.id)`, exception → run 'failed'+error+commit.
- **Queue routing:** task route vào queue riêng `CAMPAIGN_QUEUE = f"{CELERY_TASK_DEFAULT_QUEUE}.campaigns"` khai báo cạnh `LEAD_SCRAPERS_QUEUE` (celery_app.py:263-265) + entry trong `task_routes` (:298-303); KHÔNG dùng `LEAD_SCRAPERS_QUEUE`, KHÔNG `time_limit=120` (campaign execute dài hơn scrape — `soft_time_limit` mặc định hoặc 600s).
- `/execute` += `?async=true` (Query): persist=true&async → get-or-create campaign + `open_campaign_run(trigger='api')` + `apply_async` → trả `{campaign_id, run_id, status:'queued'}` (response_model riêng hoặc union — pin contract); **`async=true&persist=false` → 422** (async implies persist — dev D7). Sync path nguyên trạng.
- PAT: reuse `leads:read`/`leads:write` qua `check_permission`/`check_workspace_access` seam — không scope mới.

**Never:**
- KHÔNG thêm file route mới / router mới; KHÔNG sửa `open_campaign_run` (44.3 mới đụng quota); KHÔNG queue run lại khi đang 'running' (lock đã 409); KHÔNG implement scheduler/`next_run_at` tick (44.3); KHÔNG sửa FE (chỉ wire endpoints FE đã gọi); KHÔNG backfill; KHÔNG đụng `webset_campaigns`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LIST_DEFAULT | `GET /campaigns` | chỉ `source='created'`, paged, FE Campaign[] | No error expected |
| LIST_IMPLICIT | `?include_implicit=true` | gồm 'execute'/'api' campaigns | No error expected |
| CREATE_OK | `POST /campaigns` supply payload | 201 + Campaign đúng `campaignSchema` (sources≥1) | No error expected |
| CREATE_DUP | trùng (ws,name,direction) | 409 + message "đã tồn tại" | HTTPException 409 |
| PATCH_STATUS | `status='running'` user-set | 422 | HTTPException 422 |
| LAUNCH_OK | campaign draft → POST launch | run 'queued' + task enqueued; run row = `open_campaign_run` | No error expected |
| LAUNCH_PAUSED | campaign paused → launch | 409 | HTTPException 409 |
| LAUNCH_RUNNING | run 'running' tồn tại | open_campaign_run raise → 409 | HTTPException 409 |
| EXECUTE_ASYNC | `?async=true&persist=true` | `{campaign_id, run_id, status:'queued'}` + task | No error expected |
| ASYNC_NOPERSIST | `?async=true&persist=false` | 422 | HTTPException 422 |
| TASK_PATH | task run: campaign 'X' | execute_and_persist opt-in, run → succeeded, junction có rows | exception → run 'failed'+error |
| TENANT_RLS | task session thiếu tenant ctx | (test asserts task SET context — RLS mở insert) | set_request_tenant_context |
| PATH_PRECEDENCE | `GET /campaigns/presets` | vẫn là presets handler, KHÔNG `/{campaign_id}` | regression |

</intent-contract>

## Code Map

- `app/routes/campaign_routes.py` -- 6 endpoints mới + `?async` param; ordering /presets trước /{campaign_id}
- `app/lead_intelligence/services/campaign_service.py` -- += `campaign_to_response` mapper (+ list/get helpers nếu cần); `open_campaign_run`/`get_or_create_campaign` từ 44.1 — CHỈ gọi, không sửa
- `app/tasks/campaign_tasks.py` -- **NEW** launch_campaign_run theo `auto_refund_lead_task` pattern
- `app/tasks/phone_waterfall_worker.py` :84-115 -- pattern reference (run_async_celery_task + own session + set_request_tenant_context)
- `app/celery_app.py` :263-265,:298-303 -- += CAMPAIGN_QUEUE const + task_routes entry
- `app/tenant_context.py` :17 -- `set_request_tenant_context`
- `nowing_web/services/leads-api.service.ts` :151-235 + `contracts/types/campaign.types.ts` :4-56 -- FE contract (read-only reference — campaignSchema, campaignStatusSchema, fields: id/name/status/icp_config/source_budget_config/launch_config/sources/leadCount/lastRunAt…)
- `tests/unit/routes/test_campaign_crud_routes.py` + `tests/unit/tasks/test_campaign_launch_task.py` + wire-contract test -- NEW
- `tests/integration/campaigns/test_campaign_crud_e2e.py` -- NEW (optional e2e: create→launch→list→runs)

## Tasks & Acceptance

**Execution:**
- `app/lead_intelligence/services/campaign_service.py` -- `campaign_to_response` mapper + list/get service helpers -- FE-shape chuẩn
- `app/routes/campaign_routes.py` -- 6 endpoints + async param + ordering -- thin route, service calls
- `app/tasks/campaign_tasks.py` -- launch task + queue routing -- auto_refund pattern verbatim
- `app/celery_app.py` -- CAMPAIGN_QUEUE + route entry -- 2-line diff
- tests -- unit crud/wire-contract/task; integration e2e nhẹ (reuse conftest real-PAT `tests/integration/lead_batch/conftest.py:44-101`)

**Acceptance Criteria:**
- Given 44.1 schema, khi FE gọi `listCampaigns`/`getCampaign`/`updateCampaign`/`pauseCampaign`/`createCampaign`/`launchCampaign`, then 0 lỗi 404, response parse qua `campaignSchema`
- Given campaign created, khi `POST /launch`, then `campaign_runs` row 'queued'→'running'→'succeeded'/'failed' và leads+ junction qua `execute_and_persist` opt-in
- Given `?async=true` execute, then response chứa `run_id` và task path giống launch
- Given `GET /campaigns/presets`, then vẫn trả presets (path precedence regression)
- Given PAT `leads:read` only, khi `POST /campaigns`, then 403; `GET /campaigns` → 200

## Spec Change Log

## Review Triage Log

## Design Notes

- Response mapper pin: `input_payload` truthy → merge `{id, status, created_at, leadCount?, lastRunAt?}` lên payload gốc (FE shape); fallback → build `icp_config`/`sources` từ `spec_snapshot` (implicit campaigns không có input_payload).
- `leadCount`/`lastRunAt`: derive từ `campaign_leads` count + `campaign_runs.finished_at` mới nhất — 2 query nhẹ, không denormalize v1.
- Task reuse `execute_and_persist` để giữ commit point duy nhất — task KHÔNG commit riêng ngoài finalize.

## Verification

**Commands:**
- `cd nowing_backend && pytest tests/unit/routes/test_campaign_crud_routes.py tests/unit/tasks/ -x -q` -- expected: pass
- `pytest tests/integration/campaigns/ -x -q` -- expected: pass
- `python -c "import app.tasks.campaign_tasks"` -- expected: import OK, task registered
- `pytest tests/unit/routes/ tests/unit/lead_intelligence/ -x -q` -- expected: không regression
